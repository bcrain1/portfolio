"""Fixed-schema synthetic reconciliation miniature; standard library only."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

FIELDS = ["invoice_id", "customer_id", "amount"]
TRACE = ["source", "row", "invoice_id", "customer_id", "amount", "reason"]


def money(value):
    """Adapted from the original workbench's strict Decimal normalization."""
    text = str(value).strip()
    if not re.fullmatch(r"\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", text):
        raise ValueError("invalid amount")
    result = Decimal(text.replace("$", "").replace(",", ""))
    if result > Decimal("999999999.99"):
        raise ValueError("amount exceeds demo limit")
    return result.quantize(Decimal("0.01"))


def read_rows(path, source):
    """Retain CSV record ordinals (header is record 1)."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"{source}: expected columns {FIELDS}")
        result = []
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{source}: malformed record {number}")
            result.append({"source": source, "row": number, **row})
    return result


def normalize(rows):
    valid, rejected = [], []
    for original in rows:
        row = dict(original)
        try:
            for key in ["invoice_id", "customer_id"]:
                value = row[key].strip().upper()
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,39}", value):
                    raise ValueError(f"invalid {key}")
                row[key] = value
            row["amount"] = str(money(row["amount"]))
            valid.append(row)
        except ValueError as error:
            rejected.append({**original, "reason": str(error)})
    return valid, rejected


def reconcile(ledger, bank):
    """Match unique invoice IDs only; quarantine every ambiguous valid key."""
    left, bad_left = normalize(ledger)
    right, bad_right = normalize(bank)
    ambiguous = {
        key for side in [left, right]
        for key, count in Counter(row["invoice_id"] for row in side).items()
        if count > 1
    }
    # Even malformed records with a usable invoice key block auto-matching.
    invalid_keys = {
        row["invoice_id"].strip().upper() for row in bad_left + bad_right
        if re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,39}", row["invoice_id"].strip().upper())
    }
    duplicates = [
        {**row, "reason": "ambiguous invoice key; all valid occurrences held"}
        for row in left + right if row["invoice_id"] in ambiguous
    ]
    unmatched = [
        {**row, "reason": "invalid counterpart or same-key record; review required"}
        for row in left + right
        if row["invoice_id"] in invalid_keys and row["invoice_id"] not in ambiguous
    ]
    blocked = ambiguous | invalid_keys
    lmap = {row["invoice_id"]: row for row in left if row["invoice_id"] not in blocked}
    rmap = {row["invoice_id"]: row for row in right if row["invoice_id"] not in blocked}
    matched = []
    for key in sorted(lmap.keys() | rmap.keys()):
        a, b = lmap.get(key), rmap.get(key)
        if a and b and (a["customer_id"], a["amount"]) == (b["customer_id"], b["amount"]):
            matched.append({"invoice_id": key, "customer_id": a["customer_id"],
                            "amount": a["amount"], "ledger_row": a["row"], "bank_row": b["row"]})
        else:
            reason = "customer or amount mismatch" if a and b else "no counterpart"
            unmatched.extend({**row, "reason": reason} for row in [a, b] if row)
    rejected = bad_left + bad_right
    counts = {"input_rows": len(ledger) + len(bank), "matched_pairs": len(matched),
              "unmatched_rows": len(unmatched), "duplicate_rows": len(duplicates),
              "rejected_rows": len(rejected)}
    accounted = 2 * len(matched) + len(unmatched) + len(duplicates) + len(rejected)
    if accounted != counts["input_rows"]:
        raise AssertionError("row conservation failed")
    return {"matched": matched, "unmatched": unmatched, "duplicates": duplicates,
            "rejected": rejected, "summary": {**counts, "accounted_rows": accounted,
            "matched_total": str(sum((Decimal(row["amount"]) for row in matched), Decimal("0.00")))}}


def excel_safe(value):
    """Neutralize formula-leading rejected text when opening output in Excel."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: excel_safe(row[key]) for key in fields} for row in rows)


def run(input_dir, output_dir):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("output directory must differ from input directory")
    paths = [input_dir / "ledger.csv", input_dir / "bank.csv"]
    result = reconcile(read_rows(paths[0], "ledger"), read_rows(paths[1], "bank"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ["matched", "unmatched", "duplicates", "rejected"]:
        fields = ["invoice_id", "customer_id", "amount", "ledger_row", "bank_row"] if name == "matched" else TRACE
        write_csv(output_dir / f"{name}.csv", fields, result[name])
    manifest = {"classification": "synthetic demonstration", "summary": result["summary"],
                "input_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    (output_dir / "summary.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).parent / "examples")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "generated")
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output), indent=2))
