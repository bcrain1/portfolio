"""Hand-checkable fixtures exercise failure modes, not only successful demo output."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import lab

BASE=lab.epoch('2026-08-01T00:00:00Z')
def stamp(n):
    from datetime import datetime,timezone
    return lab.iso(datetime.fromtimestamp(BASE+n,timezone.utc))
def member(name='a',offset=0,days=8):
    return dict(member_id=name,eligible_at=stamp(offset),pre_period_active_days=days)
def event(key='e',at=0,kind='play',seconds=0,uid='a',device='tv',received=None):
    return dict(event_id=key,member_id=uid,event_at=stamp(at),received_at=stamp(at if received is None else received),event_type=kind,content_type='live',device=device,watched_seconds=seconds)
def db_for(events,members=None,asof=BASE+604800):
    ms=members or [member()];clean,q=lab.clean(ms,events,asof)
    return lab.warehouse(ms,clean,asof)

class QualityTests(unittest.TestCase):
    def test_identical_retry_does_not_double_watch(self):
        a=event('h',60,'heartbeat',60);b=dict(a,received_at=stamp(100))
        clean,q=lab.clean([member()],[event(),a,b],BASE+1000)
        self.assertEqual(q['identical_duplicate_rows'],1)
        self.assertEqual(sum(e['watched_seconds'] for e in clean),60)
    def test_conflicting_ids_quarantine_all(self):
        a=event();b=dict(a,content_type='on_demand')
        clean,q=lab.clean([member()],[a,b],BASE+1000)
        self.assertEqual(clean,[]);self.assertEqual(q['conflicting_id_rows'],2)
    def test_unknown_member_and_naive_clock_rejected(self):
        clean,q=lab.clean([member()],[event(uid='bad'),dict(event('bad_clock'),event_at='2026-08-01T00:00:00')],BASE+1000)
        self.assertEqual(clean,[]);self.assertEqual(q['invalid_rows'],2)
    def test_asof_holds_late_arrival_until_available(self):
        e=event(received=100)
        self.assertEqual(lab.clean([member()],[e],BASE+50)[0],[])
        self.assertEqual(len(lab.clean([member()],[e],BASE+100)[0]),1)
    def test_invalid_heartbeat_seconds_rejected(self):
        clean,q=lab.clean([member()],[event('h',60,'heartbeat',61),event('n',1,'heartbeat',-1)],BASE+1000)
        self.assertEqual(clean,[]);self.assertEqual(q['invalid_rows'],2)
    def test_timezone_offsets_normalize(self):
        self.assertEqual(lab.epoch('2026-07-31T19:00:00-05:00'),BASE)
    def test_future_conflicting_delivery_does_not_leak_into_snapshot(self):
        a=event();b=dict(a,content_type='on_demand',received_at=stamp(200))
        clean,q=lab.clean([member()],[a,b],BASE+100)
        self.assertEqual(len(clean),1);self.assertEqual(q['unavailable_delivery_rows'],1)
        clean,q=lab.clean([member()],[a,b],BASE+300)
        self.assertEqual(clean,[]);self.assertEqual(q['conflicting_id_rows'],2)

class MetricTests(unittest.TestCase):
    def test_play_precedes_telemetry_at_same_timestamp(self):
        with db_for([event('zplay',0),event('aheartbeat',0,'heartbeat',60)]) as db:
            row=db.execute('SELECT count(*),sum(observed_watch_seconds),sum(plays) FROM sessions').fetchone()
            self.assertEqual(row[:],(1,60,1))
    def test_database_foreign_key_enforced(self):
        with db_for([]) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO events VALUES('bad','missing',0,0,'play','live','tv',0)")
    def test_exact_gap_and_explicit_play(self):
        with db_for([event(),event('h1',1800,'heartbeat',60),event('h2',3601,'heartbeat',60),event('p2',3602)]) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],3)
    def test_sessions_cross_midnight_and_separate_devices(self):
        with db_for([event(at=86390),event('h',86420,'heartbeat',60),event('p2',86425,device='mobile')]) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],2)
    def test_heartbeat_only_is_not_playback(self):
        with db_for([event('h',100,'heartbeat',60)]) as db:
            row=db.execute('SELECT * FROM member_metrics').fetchone()
            self.assertEqual(row['live_started'],0)
    def test_return_boundaries_and_censoring(self):
        ms=[member('at24'),member('after24'),member('at7'),member('after7'),member('immature',1)]
        es=[event('a',86400,uid='at24'),event('b',86401,uid='after24'),event('c',604800,uid='at7'),event('d',604801,uid='after7')]
        with db_for(es,ms) as db:
            result={r['member_id']:dict(r) for r in db.execute('SELECT * FROM member_metrics')}
        self.assertEqual([result[x]['returned'] for x in ['at24','after24','at7','after7']],[0,1,1,0])
        self.assertEqual(result['immature']['mature'],0)
        self.assertEqual(result['at7']['mature'],1)
    def test_exposure_boundary_first_hour_only(self):
        with db_for([event('a',3600,'exposure')]) as db:
            self.assertEqual(db.execute('SELECT exposed FROM member_metrics').fetchone()[0],0)
    def test_duplicate_joins_do_not_inflate_member_grain(self):
        with db_for([event(),event('h1',60,'heartbeat',60),event('h2',120,'heartbeat',60),event('x',10,'exposure')]) as db:
            self.assertEqual(db.execute('SELECT count(*),sum(exposed),sum(live_started) FROM member_metrics').fetchone()[:],(1,1,1))
    def test_missing_heartbeats_not_imputed_to_engagement(self):
        with db_for([event(),event('h',1200,'heartbeat',60)]) as db:
            self.assertEqual(db.execute('SELECT live_engaged FROM member_metrics').fetchone()[0],0)
    def test_pooled_standardization_hand_calculation(self):
        rows=[]
        # Raw exposed=74%, unexposed=26%; both strata have identical rates (80%,20%).
        for tier,e,n,k in [('frequent',1,90,72),('frequent',0,10,8),('occasional',1,10,2),('occasional',0,90,18)]:
            rows += [dict(mature=1,exposed=e,baseline_tier=tier,returned=int(i<k)) for i in range(n)]
        r=lab.compare(rows)
        self.assertAlmostEqual(r['groups']['1']['rate']-r['groups']['0']['rate'],.48)
        self.assertAlmostEqual(r['standardized_gap'],0)
        self.assertAlmostEqual(r['standardized']['1'],.5)
    def test_empty_and_missing_comparison_cells(self):
        self.assertIsNone(lab.compare([])['standardized'])
        self.assertIsNone(lab.compare([dict(mature=1,exposed=1,returned=1,baseline_tier='frequent')])['standardized'])
    def test_wilson_known_boundaries(self):
        self.assertIsNone(lab.wilson(0,0))
        self.assertAlmostEqual(lab.wilson(0,10)[1],.2775328,places=6)
        self.assertAlmostEqual(lab.wilson(10,10)[0],.7224672,places=6)
    def test_reproducible_data_and_arrival_order_invariance(self):
        ms,es=lab.generate(size=120)
        self.assertEqual((ms,es),lab.generate(size=120))
        clean1,_=lab.clean(ms,es,int(lab.AS_OF.timestamp()));clean2,_=lab.clean(ms,list(reversed(es)),int(lab.AS_OF.timestamp()))
        self.assertEqual(clean1,clean2)

if __name__=='__main__': unittest.main()
