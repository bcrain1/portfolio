import copy,json,random,sqlite3,sys,tempfile,unittest
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lab

class DecisionLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=lab.generate();cls.ledger,cls.result=lab.analyze(cls.raw)
    def test_integer_allocation_conserves(self):
        for total in range(21):
            self.assertEqual(sum(lab.allocate(total,{'a':3,'b':7,'c':11}).values()),total)
    def test_allocation_ties_stable(self):
        self.assertEqual(lab.allocate(1,{'b':1,'a':1}),{'b':0,'a':1})
    def test_no_unexplained_overhead(self):
        with self.assertRaises(ValueError):lab.allocate(1,{'a':0})
    def test_invalid_weight(self):
        with self.assertRaises(ValueError):lab.allocate(1,{'a':-1})
    def test_faults_quarantine_three_whole_hours(self):
        q=self.result['quality'];self.assertEqual(q['accepted_hours'],165);self.assertEqual(len(q['excluded_hours']),3)
        self.assertEqual(q['accepted_ledger_rows'],165*9)
    def test_exact_replay_has_no_cost_effect(self):
        clean=lab.generate(inject_faults=False);a,_=lab.analyze(clean);b,_=lab.analyze(clean+clean[:10]);self.assertEqual(a,b)
    def test_conflict_excludes_all_comparisons(self):
        raw=lab.generate(days=1,inject_faults=False);other=dict(raw[0]);other['cpu_allocated_millihours']+=1
        rows,q=lab.clean(raw+[other]);self.assertEqual(q['accepted_hours'],23);self.assertFalse(any(r['hour']==raw[0]['hour'] for r in rows))
    def test_missing_service_excludes_hour(self):
        raw=lab.generate(days=1,inject_faults=False);_,q=lab.clean(raw[1:]);self.assertEqual(q['accepted_hours'],23)
    def test_invalid_numeric_excludes_hour(self):
        for value in (None,-1,True,1.2):
            raw=lab.generate(days=1,inject_faults=False);raw[0]['failed_tasks']=value
            self.assertEqual(lab.clean(raw)[1]['accepted_hours'],23)
    def test_busy_cannot_exceed_capacity(self):
        raw=lab.generate(days=1,inject_faults=False);raw[0]['cpu_busy_millihours']=10**9
        self.assertEqual(lab.clean(raw)[1]['accepted_hours'],23)
    def test_reconciles_every_component(self):
        for row in self.result['reconciliation'].values():
            self.assertEqual(row['residual_micro'],0);self.assertEqual(row['shared_allocation_residual_micro'],0)
    def test_zero_success_is_unknown(self):
        raw=lab.generate(days=1,inject_faults=False)
        for r in raw:r['failed_tasks']=r['requested_tasks'];r['successful_tasks']=0
        _,result=lab.analyze(raw)
        self.assertTrue(all(r['cost_per_success_micro'] is None for r in result['summaries']))
        self.assertTrue(all(r['recommendation']=='HOLD' for r in result['comparisons']['optimized']['services']))
    def test_latency_vetoes_cheaper_change(self):
        row=next(r for r in self.result['comparisons']['optimized']['services'] if r['service']=='interactive')
        self.assertGreater(row['unit_cost_improvement'],0.2);self.assertEqual(row['recommendation'],'HOLD');self.assertFalse(row['latency_ok'])
    def test_semantic_mismatch_veto(self):
        raw=lab.generate(days=1,inject_faults=False)
        next(r for r in raw if r['scenario']=='optimized' and r['service']=='batch')['output_fingerprint']='different'
        _,result=lab.analyze(raw);row=next(r for r in result['comparisons']['optimized']['services'] if r['service']=='batch')
        self.assertIn('synthetic_output_fingerprints_not_matched',row['reasons'])
    def test_error_regression_veto(self):
        raw=lab.generate(days=1,inject_faults=False)
        for r in raw:
            if r['scenario']=='optimized':r['failed_tasks']+=100;r['successful_tasks']-=100
        _,result=lab.analyze(raw);self.assertTrue(all(not r['error_ok'] for r in result['comparisons']['optimized']['services']))
    def test_mix_adjustment_removes_false_savings(self):
        r=self.result['comparisons']['mix_only'];self.assertGreater(r['pooled_improvement'],0.2);self.assertLess(abs(r['standardized_improvement']),0.0001)
        self.assertTrue(all(s['recommendation']=='HOLD' for s in r['services']))
    def test_delivery_order_does_not_change_ledger(self):
        raw=copy.deepcopy(self.raw);random.Random(1).shuffle(raw)
        ledger,result=lab.analyze(raw);self.assertEqual(ledger,self.ledger);self.assertEqual(result['semantic_ledger_sha256'],self.result['semantic_ledger_sha256'])
    def test_seed_deterministic(self):
        self.assertEqual(lab.generate(4,1),lab.generate(4,1));self.assertNotEqual(lab.generate(4,1),lab.generate(5,1))
    def test_sql_sum_matches_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.db';lab.aggregate(self.ledger,path)
            with closing(sqlite3.connect(path)) as db:self.assertEqual(db.execute('SELECT SUM(total_cost_micro) FROM ledger').fetchone()[0],sum(r['total_cost_micro'] for r in self.ledger))
    def test_reproducible_delivery_files(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            lab.build(Path(a));lab.build(Path(b))
            self.assertEqual(json.loads((Path(a)/'manifest.json').read_text()),json.loads((Path(b)/'manifest.json').read_text()))

if __name__=='__main__':unittest.main()
