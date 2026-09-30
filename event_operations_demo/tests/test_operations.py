import json
import tempfile
import unittest
from pathlib import Path

from operations import Processor, require_transition, run

ROOT = Path(__file__).resolve().parents[1]


def event(identity, kind="assign", job="JOB-A"):
    return {"event_id": identity, "job_id": job, "kind": kind}


class OperationsTests(unittest.TestCase):
    def test_fixture_reaches_expected_states_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(ROOT / "examples/scenario.json", Path(directory) / "evidence.json")
        self.assertEqual(result["states"], {"JOB-A": "COMPLETED", "JOB-B": "CANCELLED", "JOB-C": "REQUESTED"})
        self.assertEqual(result["summary"]["applied_effects"], 4)
        self.assertEqual(result["summary"]["dead_letters"], 4)
        self.assertEqual({r["reason"] for r in result["dead_letters"]},
                         {"ID_CONFLICT", "INVALID_TRANSITION", "RETRY_EXHAUSTED", "UNKNOWN_JOB_OR_KIND"})

    def test_duplicate_delivery_produces_one_effect(self):
        p = Processor({"JOB-A": "REQUESTED"})
        result = p.process([event("A"), event("A")])
        self.assertEqual(len(result["effects"]), 1)
        self.assertEqual(result["audit"][-1]["outcome"], "DUPLICATE_IGNORED")

    def test_conflicting_payload_cannot_reuse_event_id(self):
        p = Processor({"JOB-A": "REQUESTED", "JOB-B": "REQUESTED"})
        p.process([event("A"), event("A", job="JOB-B")])
        self.assertEqual(p.jobs["JOB-B"], "REQUESTED")
        self.assertEqual(p.audit[-1]["outcome"], "ID_CONFLICT")

    def test_retry_succeeds_without_duplicate_effect(self):
        p = Processor({"JOB-A": "REQUESTED"})
        p.process([event("A")], {"A": 2})
        self.assertEqual(p.attempts["A"], 3)
        self.assertEqual(len(p.effects), 1)
        self.assertEqual(p.dead_letters, [])

    def test_exhausted_retry_does_not_mutate_job(self):
        p = Processor({"JOB-A": "REQUESTED"})
        p.process([event("A")], {"A": 100})
        self.assertEqual(p.attempts["A"], 3)
        self.assertEqual(p.jobs["JOB-A"], "REQUESTED")
        self.assertEqual(p.effects, [])
        self.assertEqual(p.dead_letters[0]["reason"], "RETRY_EXHAUSTED")

    def test_out_of_order_start_recovers_after_assignment(self):
        p = Processor({"JOB-A": "REQUESTED"})
        p.process([event("S", "start"), event("A")])
        self.assertEqual(p.jobs["JOB-A"], "ACTIVE")
        self.assertEqual([r["event_id"] for r in p.effects], ["A", "S"])

    def test_missing_predecessor_eventually_dead_letters(self):
        p = Processor({"JOB-A": "REQUESTED"}, max_attempts=2)
        p.process([event("S", "start")])
        self.assertEqual(p.attempts["S"], 2)
        self.assertEqual(p.dead_letters[0]["cause"], "WAITING_FOR_PREDECESSOR")

    def test_terminal_state_cannot_restart(self):
        with self.assertRaises(ValueError):
            require_transition("COMPLETED", "ACTIVE")
        p = Processor({"JOB-A": "CANCELLED"})
        p.process([event("A")])
        self.assertEqual(p.jobs["JOB-A"], "CANCELLED")
        self.assertEqual(p.dead_letters[0]["reason"], "INVALID_TRANSITION")

    def test_unknown_job_or_kind_is_quarantined(self):
        p = Processor({"JOB-A": "REQUESTED"})
        p.process([event("U", "unsupported"), event("M", job="MISSING")])
        self.assertEqual(len(p.dead_letters), 2)
        self.assertEqual(p.effects, [])

    def test_batch_validation_precedes_any_mutation(self):
        p = Processor({"JOB-A": "REQUESTED"})
        with self.assertRaises(ValueError):
            p.process([event("A"), {"event_id": "bad"}])
        self.assertEqual(p.jobs["JOB-A"], "REQUESTED")
        self.assertEqual(p.audit, [])

    def test_replay_same_process_retains_idempotency(self):
        p = Processor({"JOB-A": "REQUESTED"})
        p.process([event("A")])
        p.process([event("A")])
        self.assertEqual(len(p.effects), 1)

    def test_new_id_same_state_is_a_noop(self):
        p = Processor({"JOB-A": "REQUESTED"})
        p.process([event("A"), event("B")])
        self.assertEqual(len(p.effects), 1)
        self.assertEqual(p.audit[-1]["outcome"], "ALREADY_IN_STATE")

    def test_audit_sequence_and_sample_output_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "evidence.json"
            result = run(ROOT / "examples/scenario.json", out)
            first = out.read_bytes()
            run(ROOT / "examples/scenario.json", out)
            self.assertEqual(first, out.read_bytes())
            self.assertEqual(first, (ROOT / "sample_output/evidence.json").read_bytes())
        self.assertEqual([r["sequence"] for r in result["audit"]], list(range(1, len(result["audit"]) + 1)))

    def test_invalid_retry_policy_is_rejected(self):
        for attempts in [0, 11, 1.5, True]:
            with self.subTest(attempts=attempts), self.assertRaises(ValueError):
                Processor({}, attempts)


if __name__ == "__main__":
    unittest.main()
