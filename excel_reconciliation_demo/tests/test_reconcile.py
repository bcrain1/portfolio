import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from reconcile import money, read_rows, reconcile, run

ROOT = Path(__file__).resolve().parents[1]


def row(key, amount="1.00", customer="CUST-A", source="ledger", number=2):
    return dict(source=source, row=number, invoice_id=key, customer_id=customer, amount=amount)


class ReconciliationTests(unittest.TestCase):
    def test_fixture_expected_classifications_and_conservation(self):
        result = reconcile(read_rows(ROOT / "examples/ledger.csv", "ledger"),
                           read_rows(ROOT / "examples/bank.csv", "bank"))
        self.assertEqual(result["summary"], {"input_rows": 14, "matched_pairs": 3,
            "unmatched_rows": 4, "duplicate_rows": 3, "rejected_rows": 1,
            "accounted_rows": 14, "matched_total": "15.50"})
        self.assertEqual([r["invoice_id"] for r in result["matched"]], ["INV-001", "INV-005", "INV-007"])
        self.assertEqual({(r["source"], r["row"]) for r in result["duplicates"]},
                         {("ledger", 5), ("ledger", 6), ("bank", 4)})
        self.assertEqual({(r["source"], r["row"]) for r in result["unmatched"]},
                         {("ledger", 3), ("ledger", 4), ("bank", 3), ("bank", 6)})
        self.assertEqual(result["rejected"][0]["row"], 8)

    def test_currency_is_exact_and_zero_is_valid(self):
        self.assertEqual(money(" $1,234.50 "), Decimal("1234.50"))
        self.assertEqual(money("0"), Decimal("0.00"))
        self.assertEqual(money("0.1") + money("0.2"), Decimal("0.30"))

    def test_invalid_currency_is_not_rounded_or_coerced(self):
        for value in ["NaN", "Infinity", "1.001", "-1", "1,23", "", "1e2", "1000000000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                money(value)

    def test_case_and_whitespace_normalize(self):
        result = reconcile([row(" inv-a ", " $1.00 ", " cust-a ")], [row("INV-A", source="bank")])
        self.assertEqual(len(result["matched"]), 1)

    def test_conflicting_duplicates_hold_all_counterparts(self):
        result = reconcile([row("A"), row("A", "2.00", number=3)], [row("A", source="bank")])
        self.assertEqual(len(result["duplicates"]), 3)
        self.assertEqual(result["matched"], [])

    def test_duplicate_on_bank_side_blocks_matching(self):
        result = reconcile([row("A")], [row("A", source="bank"), row("A", source="bank", number=3)])
        self.assertEqual(len(result["duplicates"]), 3)

    def test_customer_mismatch_is_not_accepted(self):
        result = reconcile([row("A")], [row("A", customer="CUST-B", source="bank")])
        self.assertEqual(len(result["unmatched"]), 2)
        self.assertEqual(result["matched"], [])

    def test_invalid_same_key_prevents_false_unique_match(self):
        result = reconcile([row("A"), row("A", "bad", number=3)], [row("A", source="bank")])
        self.assertEqual(result["matched"], [])
        self.assertEqual(len(result["unmatched"]), 2)
        self.assertEqual(len(result["rejected"]), 1)

    def test_empty_input_is_valid(self):
        result = reconcile([], [])
        self.assertEqual(result["summary"]["matched_total"], "0.00")
        self.assertEqual(result["summary"]["accounted_rows"], 0)

    def test_bad_header_or_record_fails_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for content in ["wrong,columns\na,b\n", "invoice_id,customer_id,amount\nA,C\n"]:
                (root / "ledger.csv").write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    run(root, root / "output")
                self.assertFalse((root / "output").exists())

    def test_rerun_outputs_are_identical_and_inputs_preserved(self):
        before = {p.name: p.read_bytes() for p in (ROOT / "examples").iterdir()}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            run(ROOT / "examples", out)
            first = {p.name: p.read_bytes() for p in out.iterdir()}
            run(ROOT / "examples", out)
            self.assertEqual(first, {p.name: p.read_bytes() for p in out.iterdir()})
            for name, content in first.items():
                self.assertEqual(content, (ROOT / "sample_output" / name).read_bytes())
            self.assertEqual(json.loads(first["summary.json"])["summary"]["input_rows"], 14)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (ROOT / "examples").iterdir()})

    def test_rejected_formula_text_is_neutralized_for_excel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ledger.csv").write_text("invoice_id,customer_id,amount\n=1+1,CUST-A,1\n", encoding="utf-8")
            (root / "bank.csv").write_text("invoice_id,customer_id,amount\n", encoding="utf-8")
            run(root, root / "output")
            with (root / "output/rejected.csv").open(newline="", encoding="utf-8") as handle:
                self.assertEqual(next(csv.DictReader(handle))["invoice_id"], "'=1+1")


if __name__ == "__main__":
    unittest.main()
