import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lab

class MetricsTests(unittest.TestCase):
    def fixture(self, scenario='planning_friction'):
        return lab.pipeline(*lab.generate(scenario=scenario))[0]

    def test_known_planning_counts(self):
        v=lab.evaluate(self.fixture())
        self.assertEqual(v['cohorts']['current']['n'],300)
        self.assertEqual(v['cohorts']['current']['counts'],dict(planning_dropoff=180,launch_dropoff=24,launched=96))
        self.assertAlmostEqual(v['scores']['planning'],30)
        self.assertAlmostEqual(v['scores']['launch'],4)
        self.assertEqual(v['recommendation'],'investigate_planning')

    def test_recommendation_flips(self):
        self.assertEqual(lab.evaluate(self.fixture('launch_friction'))['recommendation'],'investigate_launch')
        self.assertEqual(lab.evaluate(self.fixture(),planning_recovery=0,launch_recovery=1)['recommendation'],'investigate_launch')
        self.assertEqual(lab.evaluate(self.fixture(),planning_recovery=0,launch_recovery=0)['recommendation'],'no_material_priority')

    def test_mix_shift(self):
        v=lab.analyze(self.fixture('mix_shift'))
        b,c=v['cohorts']['baseline'],v['cohorts']['current']
        self.assertAlmostEqual(b['raw_per100']['launched'],50)
        self.assertAlmostEqual(c['raw_per100']['launched'],106/300*100)
        self.assertAlmostEqual(b['standardized_per100']['launched'],c['standardized_per100']['launched'])
        self.assertAlmostEqual(v['weights']['emerging'],1/3)

    def test_empty(self):
        v=lab.evaluate([])
        self.assertEqual(v['recommendation'],'insufficient_evidence')
        self.assertIsNone(v['cohorts']['current']['raw_per100']['launched'])
        self.assertIsNone(v['scores']['planning'])

    def test_missing_support(self):
        rows=[r for r in self.fixture() if not(r['cohort']=='current' and r['segment']=='emerging')]
        v=lab.evaluate(rows)
        self.assertIsNone(v['cohorts']['current']['standardized_per100']['launched'])
        self.assertEqual(v['recommendation'],'insufficient_evidence')

    def test_quality_gate(self):
        self.assertEqual(lab.evaluate(self.fixture('telemetry_gap'))['recommendation'],'insufficient_evidence')

    def test_small_sample_gate(self):
        rows=[r for r in self.fixture() if r['advertiser_id'].endswith('001')]
        self.assertEqual(lab.evaluate(rows)['recommendation'],'insufficient_evidence')

    def test_wilson(self):
        self.assertIsNone(lab.wilson(0,0))
        self.assertAlmostEqual(lab.wilson(0,10)[1],27.75328,places=4)
        self.assertAlmostEqual(lab.wilson(10,10)[0],72.24672,places=4)

    def test_bounds_nested_and_denominators(self):
        for scenario in lab.SCENARIOS:
            rows=self.fixture(scenario)
            for v in lab.analyze(rows)['cohorts'].values():
                self.assertLessEqual(v['launched'],v['completed']); self.assertLessEqual(v['completed'],v['n'])
                self.assertEqual(sum(v['counts'].values()),v['n'])
                self.assertEqual(v['n']+sum(v['exclusions'].values()),v['total'])

    def test_recovery_input_validation(self):
        for bad in (-1,1.1,float('nan'),float('inf'),True,'0.5'):
            with self.assertRaises(ValueError): lab.evaluate([],planning_recovery=bad)

    def test_equal_scores_balanced(self):
        v=lab.evaluate(self.fixture(),planning_recovery=.1,launch_recovery=.75)
        self.assertAlmostEqual(v['scores']['planning'],v['scores']['launch'])
        self.assertEqual(v['recommendation'],'balanced_investigation')

    def test_immature_cannot_dilute_quality_gate(self):
        rows=self.fixture('telemetry_gap')
        immature=next(r for r in rows if r['exclusion']=='immature')
        rows += [dict(immature,advertiser_id=f'x{i}') for i in range(10000)]
        self.assertEqual(lab.evaluate(rows)['recommendation'],'insufficient_evidence')

    def test_custom_snapshot_preserved(self):
        rows,_=lab.pipeline(*lab.generate(),as_of='2026-10-06T00:00:00Z')
        self.assertEqual(lab.evaluate(rows)['as_of'],'2026-10-06T00:00:00Z')
        rows[0]['as_of']=lab.AS_OF
        with self.assertRaises(ValueError): lab.evaluate(rows)

    def test_determinism(self):
        self.assertEqual(lab.generate(),lab.generate())
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            lab.build(a);lab.build(b)
            for file in Path(a).iterdir(): self.assertEqual(file.read_bytes(),(Path(b)/file.name).read_bytes())

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.a=[dict(advertiser_id='a',segment='growth',cohort='current',started_at='2026-09-01T00:00:00Z',telemetry_complete=True)]
        self.e=[dict(event_id='s',advertiser_id='a',event_type='plan_started',event_at='2026-09-01T00:00:00Z',received_at='2026-09-01T00:00:01Z')]
    def result(self): return lab.pipeline(self.a,self.e)
    def test_duplicate_idempotent(self):
        self.e.append(dict(self.e[0],received_at='2026-09-02T00:00:00Z'))
        rows,q=self.result();self.assertEqual(rows[0]['eligible'],1);self.assertEqual(q['identical_duplicate_rows'],1)
    def test_conflict_quarantines(self):
        self.e.append(dict(self.e[0],event_type='plan_completed'))
        self.assertEqual(self.result()[0][0]['exclusion'],'invalid')
    def test_future_conflict_ignored(self):
        self.e.append(dict(self.e[0],event_type='campaign_launched',received_at='2026-10-08T00:00:00Z'))
        self.assertEqual(self.result()[0][0]['eligible'],1)
    def test_unknown_conflict_quarantines_known(self):
        self.e.append(dict(self.e[0],advertiser_id='unknown'))
        self.assertEqual(self.result()[0][0]['valid'],0)
    def test_missing_event_id_quarantines(self):
        self.e[0].pop('event_id');self.assertEqual(self.result()[0][0]['valid'],0)
    def test_unknown_or_missing_event_advertiser(self):
        for value in ('unknown',None):
            e=dict(self.e[0],event_id='unknown',advertiser_id=value)
            rows,q=lab.pipeline(self.a,self.e+[e])
            self.assertEqual(rows[0]['valid'],1)
            self.assertEqual(q['unknown_advertiser_rows'],1)
        e=dict(self.e[0],event_id='missing');e.pop('advertiser_id')
        self.assertEqual(lab.pipeline(self.a,self.e+[e])[0][0]['valid'],1)
    def test_invalid_clocks(self):
        for key,value in [('event_at','2026-09-01T00:00:00'),('received_at','bad'),('event_at','2026-09-02T00:00:00Z')]:
            original=copy.deepcopy(self.e);self.e[0][key]=value
            self.assertEqual(self.result()[0][0]['valid'],0);self.e=original
    def test_late_outside_window(self):
        self.e.append(dict(self.e[0],event_id='c',event_type='plan_completed',event_at='2026-09-16T00:00:00Z',received_at='2026-09-16T00:00:01Z'))
        rows,q=self.result();self.assertEqual(rows[0]['plan_completed'],0);self.assertEqual(rows[0]['eligible'],1);self.assertEqual(q['outside_window_rows'],1)
    def test_exact_boundary_included(self):
        self.e.append(dict(self.e[0],event_id='c',event_type='plan_completed',event_at='2026-09-15T00:00:00Z',received_at='2026-09-15T00:00:01Z'))
        self.assertEqual(self.result()[0][0]['plan_completed'],1)
    def test_orphan_launch_invalid(self):
        self.e.append(dict(self.e[0],event_id='l',event_type='campaign_launched'))
        self.assertEqual(self.result()[0][0]['valid'],0)
    def test_conflicting_dimension(self):
        self.a.append(dict(self.a[0],segment='emerging'))
        for dimensions in (self.a,list(reversed(self.a))):
            with self.assertRaisesRegex(ValueError,'conflicting advertiser dimensions'):
                lab.pipeline(dimensions,self.e)
    def test_dimension_conflict_order_cannot_change_gate(self):
        dimensions,events=lab.generate()
        conflicts=[dict(a,segment='growth') for a in dimensions if a['cohort']=='current' and a['segment']=='emerging'][:12]
        messages=[]
        for records in (dimensions+conflicts,conflicts+dimensions):
            with self.assertRaises(ValueError) as error: lab.pipeline(records,events)
            messages.append(str(error.exception))
        self.assertEqual(messages[0],messages[1])
    def test_fractional_timestamp_rejected(self):
        for timestamp in ('2026-09-15T00:00:00.500Z','2026-10-07T00:00:00.500Z','2026-10-07T00:00:00.0000001Z','2026-10-07T00:00:00+00:00:00.500'):
            with self.assertRaisesRegex(ValueError,'whole-second'): lab.epoch(timestamp)
        self.e.append(dict(self.e[0],event_id='c',event_type='plan_completed',event_at='2026-09-15T00:00:00.500Z',received_at='2026-09-15T00:00:01Z'))
        self.assertEqual(self.result()[0][0]['valid'],0)
    def test_missing_dimension(self):
        self.a[0].pop('segment');self.assertEqual(self.result()[0][0]['valid'],0)
    def test_missing_advertiser_id_fails_closed(self):
        self.a[0].pop('advertiser_id')
        with self.assertRaises(ValueError): self.result()
    def test_incomplete_and_immature_distinct(self):
        self.a[0]['telemetry_complete']=False;self.assertEqual(self.result()[0][0]['exclusion'],'incomplete')
        self.a[0]['started_at']='2026-10-05T00:00:00Z';self.e[0].update(event_at=self.a[0]['started_at'],received_at='2026-10-05T00:00:01Z')
        self.assertEqual(self.result()[0][0]['exclusion'],'immature')

if __name__=='__main__': unittest.main()
