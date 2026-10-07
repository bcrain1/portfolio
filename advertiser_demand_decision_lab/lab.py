"""Synthetic advertiser planning diagnostics; Python 3.10+, standard library only."""
from __future__ import annotations
import argparse, csv, json, math, random, re, sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AS_OF = '2026-10-07T00:00:00Z'
SEGMENTS = ('emerging', 'growth', 'established')
SCENARIOS = ('planning_friction', 'launch_friction', 'mix_shift', 'telemetry_gap', 'empty')
KINDS = ('plan_started', 'plan_completed', 'campaign_launched')
WINDOW = 14 * 86400

def epoch(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})',value):
        raise ValueError('whole-second ISO timestamp with timezone required')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('timezone required')
    if d.microsecond: raise ValueError('whole-second timestamp precision required')
    return int(d.timestamp())

def iso(s): return datetime.fromtimestamp(s, timezone.utc).isoformat().replace('+00:00','Z')

def generate(seed=42808, scenario='planning_friction'):
    if scenario not in SCENARIOS: raise ValueError('unknown scenario')
    if scenario=='empty': return [], []
    rng = random.Random(seed)
    advertisers, events = [], []
    # Exact count fixtures isolate within-segment changes from composition changes.
    for cohort in ('baseline','current'):
        sizes = [100,100,100] if scenario != 'mix_shift' or cohort == 'baseline' else [240,40,20]
        for segment, n in zip(SEGMENTS,sizes):
            si = SEGMENTS.index(segment)
            completion, launch = [(.50,.30),(.70,.50),(.90,.70)][si]
            if cohort == 'current' and scenario == 'planning_friction': completion, launch = [(.30,.24),(.40,.32),(.50,.40)][si]
            if cohort == 'current' and scenario == 'launch_friction': completion, launch = [(.80,.16),(.90,.18),(1.,.20)][si]
            for i in range(n):
                aid = f'{cohort}_{segment}_{i:03d}'
                start = epoch('2026-08-01T00:00:00Z' if cohort=='baseline' else '2026-09-01T00:00:00Z') + rng.randrange(10)*86400
                advertisers.append(dict(advertiser_id=aid,segment=segment,cohort=cohort,started_at=iso(start),telemetry_complete=True))
                for kind, offset in [('plan_started',0)] + ([('plan_completed',86400)] if i < round(n*completion) else []) + ([('campaign_launched',3*86400)] if i < round(n*launch) else []):
                    events.append(dict(event_id=f'{aid}_{kind}',advertiser_id=aid,event_type=kind,event_at=iso(start+offset),received_at=iso(start+offset+60)))
    # Exclusion fixtures are outside the controlled 600-advertiser eligible cohort.
    base = dict(advertisers[0])
    for suffix,changes in [('incomplete',dict(telemetry_complete=False)),('immature',dict(started_at='2026-10-05T00:00:00Z')),('conflict',{}),('bad_clock',{})]:
        a = dict(base,advertiser_id=f'fixture_{suffix}',cohort='current',**changes)
        advertisers.append(a)
        e = dict(event_id=f'fixture_{suffix}',advertiser_id=a['advertiser_id'],event_type='plan_started',event_at=a['started_at'],received_at=iso(epoch(a['started_at'])+60))
        events.append(e)
        if suffix=='conflict': events.append(dict(e,event_type='campaign_launched'))
        if suffix=='bad_clock': e['event_at']='missing'
    events.append(dict(events[0]))
    events.append(dict(events[1],received_at='2026-10-09T00:00:00Z',event_type='campaign_launched'))
    if scenario=='telemetry_gap':
        for a in advertisers:
            if a['cohort']=='current' and a['advertiser_id'].endswith(('0','1','2','3')): a['telemetry_complete']=False
    rng.shuffle(events)
    return advertisers, events

def pipeline(advertisers, events, as_of=AS_OF):
    cutoff = epoch(as_of)
    reasons, quarantine = Counter(), defaultdict(set)
    groups = defaultdict(list)
    for a in advertisers:
        aid = a.get('advertiser_id')
        if not isinstance(aid,str) or not aid: raise ValueError('advertiser dimension missing ID; cannot attribute denominator')
        groups[aid].append(a)
    dims = {}
    for aid, group in groups.items():
        a = dict(group[0]); dims[aid]=a
        if len({json.dumps(x,sort_keys=True) for x in group})>1:
            raise ValueError('conflicting advertiser dimensions; cohort or segment attribution is ambiguous')
        reasons['duplicate_dimension_rows'] += len(group)-1
        try:
            if a.get('segment') not in SEGMENTS or a.get('cohort') not in ('baseline','current') or type(a.get('telemetry_complete')) is not bool: raise ValueError()
            start=epoch(a['started_at'])
            if start>cutoff: quarantine[aid].add('future_start')
        except (ValueError,KeyError,TypeError,AttributeError): quarantine[aid].add('invalid_dimension')
    grouped=defaultdict(list)
    for e in events:
        aid=e.get('advertiser_id')
        try: receipt=epoch(e['received_at'])
        except (ValueError,KeyError,TypeError,AttributeError):
            reasons['invalid_receipt_rows']+=1
            if aid in dims: quarantine[aid].add('invalid_receipt')
            continue
        if receipt>cutoff: reasons['unavailable_delivery_rows']+=1; continue
        if aid not in dims: reasons['unknown_advertiser_rows']+=1
        if not isinstance(e.get('event_id'),str) or not e['event_id']:
            reasons['missing_event_id_rows']+=1
            if aid in dims: quarantine[aid].add('missing_event_id')
            continue
        grouped[e['event_id']].append(e)
    accepted=defaultdict(list)
    for eid, group in sorted(grouped.items()):
        payloads={json.dumps({k:v for k,v in e.items() if k!='received_at'},sort_keys=True) for e in group}
        if len(payloads)>1:
            reasons['conflicting_id_rows']+=len(group)
            for e in group:
                if e.get('advertiser_id') in dims: quarantine[e['advertiser_id']].add('conflicting_event_id')
            continue
        e=min(group,key=lambda x:epoch(x['received_at'])); aid=e.get('advertiser_id')
        if aid not in dims: continue
        reasons['identical_duplicate_rows']+=len(group)-1
        try:
            when,received,start=epoch(e['event_at']),epoch(e['received_at']),epoch(dims[aid]['started_at'])
            if e['event_type'] not in KINDS or received<when or when<start: raise ValueError()
            if when>start+WINDOW:
                reasons['outside_window_rows']+=1; continue
            if e['event_type']=='plan_started' and when!=start: raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError):
            reasons['invalid_event_rows']+=1; quarantine[aid].add('invalid_event'); continue
        accepted[aid].append((e['event_type'],when,eid))
    for aid in dims:
        observed=accepted[aid]; bykind=defaultdict(list)
        for kind,when,eid in observed: bykind[kind].append(when)
        if len(bykind['plan_started'])!=1 or any(len(v)>1 for v in bykind.values()): quarantine[aid].add('invalid_sequence')
        if bykind['campaign_launched'] and not bykind['plan_completed']: quarantine[aid].add('invalid_sequence')
        if bykind['campaign_launched'] and bykind['plan_completed'] and min(bykind['campaign_launched'])<max(bykind['plan_completed']): quarantine[aid].add('invalid_sequence')
    db=sqlite3.connect(':memory:'); db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE advertisers(advertiser_id TEXT PRIMARY KEY,segment TEXT,cohort TEXT,started_at TEXT,mature INT,complete INT,valid INT,eligible INT,exclusion TEXT); CREATE TABLE events(event_id TEXT PRIMARY KEY,advertiser_id TEXT,kind TEXT,event_s INT);')
    for aid,a in sorted(dims.items()):
        try: mature=epoch(a['started_at'])+WINDOW<=cutoff
        except (ValueError,KeyError,TypeError,AttributeError): mature=False
        complete=a.get('telemetry_complete') is True; valid=not quarantine[aid]
        exclusion='invalid' if not valid else 'immature' if not mature else 'incomplete' if not complete else 'eligible'
        db.execute('INSERT INTO advertisers VALUES(?,?,?,?,?,?,?,?,?)',(aid,a.get('segment'),a.get('cohort'),a.get('started_at'),int(mature),int(complete),int(valid),int(valid and mature and complete),exclusion))
        for kind,when,eid in accepted[aid]: db.execute('INSERT INTO events VALUES(?,?,?,?)',(eid,aid,kind,when))
    rows=[dict(r,as_of=as_of,synthetic=True) for r in db.execute((ROOT/'sql/metrics.sql').read_text())]; db.close()
    reasons.update(raw_event_rows=len(events),advertiser_rows=len(advertisers),unique_advertisers=len(rows),quarantined_advertisers=sum(bool(v) for v in quarantine.values()))
    return rows,dict(reasons)

def wilson(k,n):
    if not n:return None
    z=1.95996398454; p=k/n; den=1+z*z/n
    c=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [100*max(0,c-h),100*min(1,c+h)]

def analyze(rows,segment='all'):
    if segment not in ('all',)+SEGMENTS: raise ValueError('unknown segment')
    scoped=[r for r in rows if segment=='all' or r['segment']==segment]
    baseline=[r for r in scoped if r['cohort']=='baseline' and r['eligible']]
    weights={s:sum(r['segment']==s for r in baseline)/len(baseline) for s in SEGMENTS} if baseline else {}
    result=dict(segment=segment,weights=weights,cohorts={},exclusions_by_cell=[])
    for cohort in ('baseline','current'):
        allrows=[r for r in scoped if r['cohort']==cohort]; good=[r for r in allrows if r['eligible']]
        n=len(good); completed=sum(r['plan_completed'] for r in good); launched=sum(r['campaign_launched'] for r in good)
        counts=dict(planning_dropoff=n-completed,launch_dropoff=completed-launched,launched=launched)
        cells={s:[r for r in good if r['segment']==s] for s in SEGMENTS}
        support=bool(weights) and all(cells[s] for s,w in weights.items() if w>0)
        std={}
        for metric in counts:
            def val(r): return 1-r['plan_completed'] if metric=='planning_dropoff' else r['plan_completed']-r['campaign_launched'] if metric=='launch_dropoff' else r['campaign_launched']
            std[metric]=sum(w*sum(val(r) for r in cells[s])/len(cells[s])*100 for s,w in weights.items() if w>0) if support else None
        result['cohorts'][cohort]=dict(n=n,started=n,completed=completed,launched=launched,counts=counts,raw_per100={k:100*v/n if n else None for k,v in counts.items()},wilson_per100={k:wilson(v,n) for k,v in counts.items()},standardized_per100=std,support=support,total=len(allrows),exclusions=dict(Counter(r['exclusion'] for r in allrows if not r['eligible'])),segment_n={s:len(cells[s]) for s in SEGMENTS})
        for s in SEGMENTS:
            cell=[r for r in allrows if r['segment']==s]
            result['exclusions_by_cell'].append(dict(cohort=cohort,segment=s,total=len(cell),eligible=sum(r['eligible'] for r in cell),exclusions=dict(Counter(r['exclusion'] for r in cell if not r['eligible']))))
    return result

def evaluate(rows,segment='all',planning_recovery=.5,launch_recovery=.5):
    for x in (planning_recovery,launch_recovery):
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1: raise ValueError('recovery fraction must be finite 0..1')
    result=analyze(rows,segment); gates=[]
    for c,v in result['cohorts'].items():
        if not v['support']: gates.append(c+': missing baseline-weighted segment support')
        if any(v['segment_n'][s]<20 for s,w in result['weights'].items() if w>0): gates.append(c+': fewer than 20 eligible advertisers in a supported segment')
        # Incomplete/quarantined mature observations affect interpretability; immature is expected censoring.
        excluded=v['exclusions'].get('invalid',0)+v['exclusions'].get('incomplete',0)
        quality_denominator=v['n']+excluded
        if quality_denominator and excluded/quality_denominator>.10: gates.append(c+': more than 10% incomplete or invalid among eligible + incomplete + invalid advertisers')
    current=result['cohorts']['current']['standardized_per100']
    scores=dict(planning=None if current['planning_dropoff'] is None else current['planning_dropoff']*planning_recovery,launch=None if current['launch_dropoff'] is None else current['launch_dropoff']*launch_recovery)
    if gates: recommendation='insufficient_evidence'
    elif max(scores.values())<1: recommendation='no_material_priority'
    elif abs(scores['planning']-scores['launch'])<2: recommendation='balanced_investigation'
    else: recommendation='investigate_planning' if scores['planning']>scores['launch'] else 'investigate_launch'
    snapshots={r.get('as_of',AS_OF) for r in rows}
    if len(snapshots)>1: raise ValueError('mixed as-of snapshots')
    result.update(synthetic=True,as_of=next(iter(snapshots),AS_OF),scores=scores,recommendation=recommendation,gates=gates,assumptions=dict(planning_recovery=planning_recovery,launch_recovery=launch_recovery),score_units='Assumed recoverable stage-specific dropoffs per 100 eligible advertisers; not comparable business value, predicted launches or causal lift')
    return result

def build(outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    data=dict(synthetic=True,as_of=AS_OF,seed=42808,segments=list(SEGMENTS),scenarios={},views={})
    for scenario in SCENARIOS:
        advertisers,events=generate(scenario=scenario); rows,quality=pipeline(advertisers,events)
        data['scenarios'][scenario]=dict(rows=rows,quality=quality)
        for segment in ('all',)+SEGMENTS:
            for p in (0.,.25,.5,.75,1.):
                for l in (0.,.25,.5,.75,1.): data['views'][f'{scenario}|{segment}|{p}|{l}']=evaluate(rows,segment,p,l)
        for name,records in [('advertisers',advertisers),('events',events),('metrics',rows)]:
            with (outdir/f'{scenario}_{name}.csv').open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=list(records[0]) if records else ['synthetic_no_data']);writer.writeheader();writer.writerows(records)
    (outdir/'data.json').write_text(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False),encoding='utf-8')
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'output'));args=parser.parse_args();build(args.output)
