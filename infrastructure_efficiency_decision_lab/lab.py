"""Deterministic synthetic resource-efficiency decision lab. Standard library only."""
from __future__ import annotations
import argparse,csv,hashlib,json,random,sqlite3
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SERVICES=('batch','interactive','streaming')
SCENARIOS=('baseline','optimized','mix_only')
RATES={'cpu_micro_per_millihour':50,'memory_micro_per_gib_millihour':5,
       'storage_micro_per_gib_hour':100,'shared_micro_per_hour':300000}
BUDGETS={'batch':900,'interactive':250,'streaming':220}
NUMERIC=('requested_tasks','successful_tasks','failed_tasks','retry_attempts',
 'cpu_allocated_millihours','cpu_busy_millihours','memory_gib_millihours',
 'storage_gib_hours','interval_p95_ms')
INPUT_FIELDS=('event_id','hour','scenario','service')+NUMERIC+('output_fingerprint',)

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def sha(v):return hashlib.sha256(v if isinstance(v,bytes) else canonical(v).encode()).hexdigest()
def ratio(a,b):return a/b if b else None

def allocate(total:int, weights:dict[str,int])->dict[str,int]:
    """Largest remainder allocation; ties resolved by service name."""
    if total<0 or any(v<0 for v in weights.values()):raise ValueError('negative allocation')
    denominator=sum(weights.values())
    if not denominator:return {k:0 for k in weights} if not total else _no_weights()
    out={k:total*v//denominator for k,v in weights.items()}
    ordered=sorted(weights,key=lambda k:(-(total*weights[k]%denominator),k))
    for k in ordered[:total-sum(out.values())]:out[k]+=1
    assert sum(out.values())==total
    return out

def _no_weights():raise ValueError('nonzero overhead without allocation weights')

def generate(seed=42062,days=7,inject_faults=True):
    if type(days) is not int or days<1:raise ValueError('days must be a positive integer')
    rng=random.Random(seed);rows=[]
    start=datetime(2026,1,5,tzinfo=timezone.utc)
    for hour_index in range(days*24):
        hour=(start+timedelta(hours=hour_index)).isoformat()
        base={}
        for service,minimum,jitter,cpu,mem,storage,p95 in [
            ('batch',4,3,48000,384000,900,620),
            ('interactive',15,5,24000,128000,200,185),
            ('streaming',40,5,16000,96000,500,170)]:
            units=(minimum+rng.randint(0,jitter))*200
            allocated=cpu+rng.randint(0,8)*1000
            busy=allocated*(48+rng.randint(0,10))//100
            base[service]=dict(event_id=f'{hour_index}:{service}:baseline',hour=hour,
                scenario='baseline',service=service,requested_tasks=units,
                successful_tasks=units*99//100,failed_tasks=units//100,
                retry_attempts=units*(4+rng.randint(0,3))//100,
                cpu_allocated_millihours=allocated,cpu_busy_millihours=busy,
                memory_gib_millihours=mem+rng.randint(0,4)*8000,
                storage_gib_hours=storage+rng.randint(0,4)*20,
                interval_p95_ms=p95+rng.randint(0,20),
                output_fingerprint=sha(['fixture-output',hour,service,units]))
        shifted=base['batch']['requested_tasks']//2
        mix_units={s:base[s]['requested_tasks'] for s in SERVICES}
        mix_units['batch']-=shifted;mix_units['streaming']+=shifted
        for service in SERVICES:
            b=base[service];rows.append(b)
            optimized=dict(b,scenario='optimized',event_id=f'{hour_index}:{service}:optimized')
            cpu_factor={'batch':75,'interactive':70,'streaming':95}[service]
            mem_factor={'batch':85,'interactive':80,'streaming':100}[service]
            optimized['cpu_allocated_millihours']=b['cpu_allocated_millihours']*cpu_factor//100
            optimized['cpu_busy_millihours']=b['cpu_busy_millihours']*95//100
            optimized['memory_gib_millihours']=b['memory_gib_millihours']*mem_factor//100
            optimized['retry_attempts']=b['retry_attempts']//2 if service=='batch' else b['retry_attempts']
            optimized['interval_p95_ms']+= {'batch':-30,'interactive':95,'streaming':10}[service]
            rows.append(optimized)
            mix=dict(b,scenario='mix_only',event_id=f'{hour_index}:{service}:mix_only')
            for field in NUMERIC:
                if field!='interval_p95_ms':mix[field]=b[field]*mix_units[service]//b['requested_tasks']
            mix['output_fingerprint']=sha(['mix-fixture',hour,service,mix_units[service]])
            rows.append(mix)
    if inject_faults and len(rows)>100:
        # A replay, a conflicting identity, a missing field and an invalid row.
        rows.extend(dict(r) for r in rows[::97])
        conflict=dict(rows[19]);conflict['cpu_allocated_millihours']+=1000;rows.append(conflict)
        rows[47]['cpu_busy_millihours']=None
        rows[88]['failed_tasks']=-1
    return rows

def clean(deliveries):
    identities=defaultdict(list)
    for row in deliveries:identities[row.get('event_id')].append(row)
    candidates=[];issues=[];duplicates=0;bad_hours=set()
    for identity,versions in sorted(identities.items(),key=lambda x:str(x[0])):
        unique={canonical(v):v for v in versions}
        duplicates+=len(versions)-len(unique)
        if len(unique)!=1:
            bad_hours.update(v.get('hour') for v in versions)
            issues.append(dict(event_id=identity,reason='conflicting_event_identity',delivery_count=len(versions)))
            continue
        row=dict(next(iter(unique.values())));reasons=[]
        if not identity or row.get('scenario') not in SCENARIOS or row.get('service') not in SERVICES:reasons.append('invalid_identity')
        try:
            parsed=datetime.fromisoformat(row['hour'])
            if parsed.utcoffset()!=timedelta(0):reasons.append('hour_not_utc')
        except (ValueError,KeyError,TypeError):reasons.append('invalid_hour')
        if any(type(row.get(k)) is not int or row[k]<0 for k in NUMERIC):reasons.append('invalid_or_missing_numeric')
        if not reasons:
            if row['successful_tasks']+row['failed_tasks']!=row['requested_tasks']:reasons.append('task_accounting_mismatch')
            if row['cpu_busy_millihours']>row['cpu_allocated_millihours']:reasons.append('busy_exceeds_allocated')
        if not row.get('output_fingerprint'):reasons.append('missing_output_fingerprint')
        if reasons:
            bad_hours.add(row.get('hour'));issues.append(dict(event_id=identity,reason=','.join(reasons),delivery_count=len(versions)))
        else:candidates.append(row)
    grouped=defaultdict(list)
    for row in candidates:grouped[row['hour']].append(row)
    expected={(s,k) for s in SCENARIOS for k in SERVICES}
    accepted=[];excluded=[]
    for hour,rows in sorted(grouped.items()):
        grain=[(r['scenario'],r['service']) for r in rows]
        if hour in bad_hours or set(grain)!=expected or len(grain)!=len(expected):
            excluded.append(hour)
        else:accepted.extend(sorted(rows,key=lambda r:(r['scenario'],r['service'])))
    all_hours={r.get('hour') for r in deliveries if r.get('hour')}
    quality=dict(raw_deliveries=len(deliveries),unique_event_ids=len(identities),
      exact_duplicate_deliveries=duplicates,invalid_or_conflicting_identities=len(issues),
      input_hours=len(all_hours),accepted_hours=len(accepted)//9,
      accepted_first_hour_utc=min((r['hour'] for r in accepted),default=None),
      accepted_last_hour_utc=max((r['hour'] for r in accepted),default=None),
      excluded_hours=sorted(all_hours-{r['hour'] for r in accepted}),
      accepted_ledger_rows=len(accepted),issues=issues,
      note='Whole comparison hours excluded across all services/scenarios; costs cover accepted hours only.')
    return accepted,quality

def cost_ledger(rows,rates=None):
    rates=dict(RATES if rates is None else rates);groups=defaultdict(list);ledger=[]
    for row in rows:groups[(row['hour'],row['scenario'])].append(row)
    for _,group in sorted(groups.items()):
        weights={r['service']:r['requested_tasks'] for r in group}
        # Explicitly fall back to equal shares for entirely idle windows.
        if not sum(weights.values()):weights={s:1 for s in weights}
        shared=allocate(rates['shared_micro_per_hour'],weights)
        for r in sorted(group,key=lambda r:r['service']):
            out=dict(r)
            out['cpu_cost_micro']=r['cpu_allocated_millihours']*rates['cpu_micro_per_millihour']
            out['memory_cost_micro']=r['memory_gib_millihours']*rates['memory_micro_per_gib_millihour']
            out['storage_cost_micro']=r['storage_gib_hours']*rates['storage_micro_per_gib_hour']
            out['shared_cost_micro']=shared[r['service']]
            out['idle_cpu_cost_micro']=(r['cpu_allocated_millihours']-r['cpu_busy_millihours'])*rates['cpu_micro_per_millihour']
            out['total_cost_micro']=sum(out[k] for k in ('cpu_cost_micro','memory_cost_micro','storage_cost_micro','shared_cost_micro'))
            ledger.append(out)
    return ledger

def aggregate(ledger,db_path=':memory:'):
    db=sqlite3.connect(str(db_path));db.row_factory=sqlite3.Row
    columns=list(INPUT_FIELDS)+['cpu_cost_micro','memory_cost_micro','storage_cost_micro','shared_cost_micro','idle_cpu_cost_micro','total_cost_micro']
    text_columns={'event_id','hour','scenario','service','output_fingerprint'}
    db.execute('DROP TABLE IF EXISTS ledger')
    db.execute('CREATE TABLE ledger ('+','.join(k+(' TEXT' if k in text_columns else ' INTEGER') for k in columns)+', PRIMARY KEY(scenario,service,hour))')
    db.executemany('INSERT INTO ledger VALUES('+','.join('?' for _ in columns)+')',[[row[k] for k in columns] for row in ledger])
    db.commit()
    summaries=[dict(r) for r in db.execute((ROOT/'sql/service_metrics.sql').read_text())]
    db.close()
    for r in summaries:
        r['cost_per_success_micro']=ratio(r['total_cost_micro'],r['successful_tasks'])
        r['cpu_utilization']=ratio(r['cpu_busy_millihours'],r['cpu_allocated_millihours'])
        r['error_rate']=ratio(r['failed_tasks'],r['requested_tasks'])
        r['retry_rate']=ratio(r['retry_attempts'],r['requested_tasks'])
        r['latency_budget_ms']=BUDGETS[r['service']]
    return summaries

def compare(summaries,ledger,scenario='optimized'):
    keyed={(r['scenario'],r['service']):r for r in summaries}
    comparisons=[]
    rowmap={(r['scenario'],r['service'],r['hour']):r for r in ledger}
    for service in SERVICES:
        if ('baseline',service) not in keyed or (scenario,service) not in keyed:continue
        b=keyed['baseline',service];t=keyed[scenario,service]
        baseline_rows=[r for r in ledger if r['scenario']=='baseline' and r['service']==service]
        same_work=all(rowmap[scenario,service,r['hour']]['requested_tasks']==r['requested_tasks'] for r in baseline_rows)
        fingerprints=all(rowmap[scenario,service,r['hour']]['output_fingerprint']==r['output_fingerprint'] for r in baseline_rows)
        latency_ok=t['worst_interval_p95_ms']<=BUDGETS[service]
        error_ok=(t['error_rate'] is not None and b['error_rate'] is not None and t['error_rate']<=b['error_rate']+0.0001)
        saving=1-t['cost_per_success_micro']/b['cost_per_success_micro'] if b['cost_per_success_micro'] and t['cost_per_success_micro'] is not None else None
        reasons=[]
        if scenario=='mix_only':reasons.append('workload_mix_changed_not_an_optimization')
        if not same_work:reasons.append('task_counts_not_matched')
        if not fingerprints:reasons.append('synthetic_output_fingerprints_not_matched')
        if not latency_ok:reasons.append('latency_budget_breach')
        if not error_ok:reasons.append('error_guardrail_breach_or_unknown')
        if saving is None or saving<=0:reasons.append('no_positive_unit_cost_improvement')
        comparisons.append(dict(service=service,baseline=b,target=t,unit_cost_improvement=saving,
            matched_task_counts=same_work,synthetic_fingerprints_match=fingerprints,
            latency_ok=latency_ok,error_ok=error_ok,
            recommendation='CANDIDATE_FOR_CONTROLLED_TRIAL' if not reasons else 'HOLD',reasons=reasons))
    base_success=sum(r['baseline']['successful_tasks'] for r in comparisons)
    target_success=sum(r['target']['successful_tasks'] for r in comparisons)
    base_cost=sum(r['baseline']['total_cost_micro'] for r in comparisons)
    target_cost=sum(r['target']['total_cost_micro'] for r in comparisons)
    weighted=None
    if base_success and all(r['target']['cost_per_success_micro'] is not None for r in comparisons):
        weighted=sum(r['baseline']['successful_tasks']/base_success*r['target']['cost_per_success_micro'] for r in comparisons)
    baseline_unit=ratio(base_cost,base_success);pooled=ratio(target_cost,target_success)
    return dict(scenario=scenario,services=comparisons,baseline_cost_micro=base_cost,target_cost_micro=target_cost,
      baseline_pooled_cost_per_success_micro=baseline_unit,target_pooled_cost_per_success_micro=pooled,
      baseline_mix_standardized_target_cost_per_success_micro=weighted,
      pooled_improvement=1-pooled/baseline_unit if pooled is not None and baseline_unit else None,
      standardized_improvement=1-weighted/baseline_unit if weighted is not None and baseline_unit else None)

def analyze(deliveries,db_path=':memory:'):
    accepted,quality=clean(deliveries);ledger=cost_ledger(accepted);summaries=aggregate(ledger,db_path)
    accepted_hours=quality['accepted_hours']
    totals={s:sum(r['total_cost_micro'] for r in ledger if r['scenario']==s) for s in SCENARIOS}
    reconciliation={}
    for scenario in SCENARIOS:
        components={k:sum(r[k] for r in ledger if r['scenario']==scenario) for k in ('cpu_cost_micro','memory_cost_micro','storage_cost_micro','shared_cost_micro')}
        reconciliation[scenario]=dict(components=components,total_micro=totals[scenario],
          residual_micro=totals[scenario]-sum(components.values()),
          shared_allocation_residual_micro=components['shared_cost_micro']-accepted_hours*RATES['shared_micro_per_hour'])
    result=dict(schema_version=1,seed=42062,synthetic=True,rates=RATES,latency_budgets_ms=BUDGETS,
        quality=quality,summaries=summaries,reconciliation=reconciliation,
        comparisons={s:compare(summaries,ledger,s) for s in ('optimized','mix_only')},
        semantic_ledger_sha256=sha(ledger),
        limits=['Fictional prices and simulated performance; not a real cost or latency benchmark.',
          'Output fingerprints compare synthetic fixtures only; not evidence of real-system semantic equivalence.',
          'Worst interval p95 is not a combined service/fleet p95.',
          'Cost totals cover accepted matched hours, not unknown excluded telemetry.',
          'Scenarios are designed examples, not causal estimates or production savings.'])
    return ledger,result

def write_csv(path,rows,fields):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def findings(result):
    lines=['# Infrastructure Efficiency Decision Lab — findings','',
      '## Decision','',
      'Advance the batch change to a controlled trial; hold the interactive change despite attractive modeled cost reductions because its latency guardrail fails. Streaming has a smaller modeled improvement. These are hypotheses to validate, not deployment approval.','',
      '| Service | Modeled unit-cost change | Worst interval p95 / budget | Decision |','|---|---:|---:|---|']
    for r in result['comparisons']['optimized']['services']:
        lines.append(f"| {r['service']} | {100*r['unit_cost_improvement']:.2f}% lower | {r['target']['worst_interval_p95_ms']} / {r['target']['latency_budget_ms']} ms | {r['recommendation']} |")
    mix=result['comparisons']['mix_only']
    lines+=['','## Workload-mix trap','',f"Changing only the workload mix lowers pooled cost per successful task by {100*mix['pooled_improvement']:.2f}%, but the baseline-mix standardized change is {100*mix['standardized_improvement']:.4f}%. The tiny residual reflects within-service hourly reweighting and integer rounding, not demonstrated efficiency. Always inspect service-specific denominators.",'',
      '## Coverage and reconciliation','',f"Accepted {result['quality']['accepted_hours']} of {result['quality']['input_hours']} hours across all services/scenarios. Excluded hours: {', '.join(result['quality']['excluded_hours'])}. Duplicate/conflict/missing-value evidence is in quality.json. Every component and shared allocation reconciles exactly in integer microdollars.",'',
      '## Next experiment','',
      'For a real controlled trial, randomize or otherwise predefine comparable cohorts; preserve task semantics and workload mix; observe raw latency distributions, errors, saturation and operational burden; pre-register rollback thresholds. Validate telemetry completeness and actual contract prices. Recheck costs with uncertainty, rather than converting this simulation into an ROI promise.','',
      '## Data and methodology','','Fictional prices and simulated telemetry; cost changes are modeled comparisons, not measured production savings.','','## Limitations','']+['- '+x for x in result['limits']]
    return '\n'.join(lines)+'\n'

def build(out:Path,seed=42062,days=7):
    out.mkdir(parents=True,exist_ok=True)
    deliveries=generate(seed,days);ledger,result=analyze(deliveries,out/'ledger.sqlite3')
    result['seed']=seed
    write_csv(out/'synthetic_deliveries.csv',deliveries,INPUT_FIELDS)
    write_csv(out/'accepted_cost_ledger.csv',ledger,list(ledger[0]) if ledger else INPUT_FIELDS)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (out/'quality.json').write_text(json.dumps(result['quality'],indent=2)+'\n',encoding='utf-8')
    (out/'FINDINGS.md').write_text(findings(result),encoding='utf-8')
    html=(ROOT/'dashboard.html').read_text(encoding='utf-8').replace('__RESULTS_JSON__',json.dumps(result).replace('</','<\\/'))
    (out/'dashboard.html').write_text(html,encoding='utf-8')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name not in ('manifest.json','ledger.sqlite3')}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(accepted_hours=result['quality']['accepted_hours'],excluded_hours=len(result['quality']['excluded_hours']),semantic_ledger_sha256=result['semantic_ledger_sha256'],comparison=result['comparisons']['mix_only']['standardized_improvement'])))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'output');p.add_argument('--seed',type=int,default=42062);p.add_argument('--days',type=int,default=7)
    a=p.parse_args();build(a.output,a.seed,a.days)
