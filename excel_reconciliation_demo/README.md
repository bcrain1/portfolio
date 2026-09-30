# Excel Automation & Data Reconciliation Workbench — runnable miniature

**Question:** Can two extracts be reconciled without hiding ambiguous keys or losing rejected rows?

This small, runnable Python demonstration compares two fictional invoice extracts.
It publishes a focused slice of the larger independent workbench: typed amount
normalization, conservative matching, exception routing, row-level evidence and
repeatable outputs. It uses synthetic data only and was developed with AI assistance.
It is not paid-client work or a production migration tool.

## Run it

Python 3.10 or newer; no third-party packages, installation, Excel application,
credentials or runtime network connection required. From this directory:

```text
python reconcile.py
python -m unittest discover -s tests -v
```

The first command reads `examples/ledger.csv` and `examples/bank.csv` and writes
five files into `generated/`. Repeating it overwrites only those named output
files. Inputs are never rewritten. To use another **synthetic** fixed-schema pair:

```text
python reconcile.py --input examples --output generated/replay
```

CSV inputs require exactly `invoice_id,customer_id,amount` in that order. One
invoice per unique key per side is required for automatic matching. IDs are
trimmed/uppercased; amounts use exact Decimal cents with US decimal/thousands
syntax. Negative amounts, excessive precision and malformed IDs are rejected.

## Expected evidence

| Outcome | Expected result | Inspect |
| --- | --- | --- |
| Matched | 3 pairs, total 15.50 | [matched.csv](sample_output/matched.csv) |
| Unmatched | 4 rows | [unmatched.csv](sample_output/unmatched.csv) |
| Duplicate quarantine | 3 rows | [duplicates.csv](sample_output/duplicates.csv) |
| Invalid input | 1 row | [rejected.csv](sample_output/rejected.csv) |

**14 input rows = 2 × 3 matched pairs + 4 unmatched + 3 duplicates + 1 rejected.**
The [summary](sample_output/summary.json) includes input SHA-256 hashes and exact
control totals. A matched amount is counted once per pair, not twice.
Each output references its source record number (header = record 1). These are
CSV record ordinals; quoted multiline cells can span multiple physical lines.

All valid occurrences of a duplicated invoice key, including its counterpart,
are held for review. A usable key on a rejected row also blocks a false unique
match. Customer/amount disagreements stay unmatched. No fuzzy matching,
automatic deduplication or silent winner selection occurs.

CSV outputs can be imported into Excel with **Data → From Text/CSV**; import
identifier columns as text. Formula-leading rejected text is apostrophe-prefixed
in output to prevent formula execution. Original inputs and record references
remain available for inspection. Native XLSX editing and Excel UI compatibility
are outside this miniature and have not been validated here.

## Checks and boundaries

The 12 automated tests cover hand-specified fixture results, row conservation,
strict currency handling, zero/empty inputs, ambiguous and invalid keys,
customer disagreement, malformed input rejection, spreadsheet-safe export,
input preservation and byte-identical reruns against the checked-in sample.

The `money()` normalization function is adapted from the original workbench;
the fixed two-file orchestration and test fixtures are new for this public
miniature. The original reusable engine, configurable ingestion, GUI, fuzzy
review workflow, transactional target database, XLSX report generator and
application packaging remain private. Repeated CSV generation demonstrates
determinism; it does **not** prove database upsert idempotency.

No original proof video is included because it demonstrates the larger private
application. No historical full-application test totals are claimed here.

## Repository license status

No repository-wide or project software license accompanies these files, and this
publication adds none. Public visibility allows GitHub viewing/forking under its
terms; it is not a permissive open-source license. See
[GitHub's licensing explanation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
