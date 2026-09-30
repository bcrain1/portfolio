# Other selected work samples

Two runnable miniatures of the existing independent Upwork portfolio projects
are now included alongside the measurement lab. Both use synthetic inputs,
standard-library Python, reproducible sample outputs and their own tests. They
were prepared for public evaluation on September 30, 2026; the complete original
applications remain private.

## 1. Excel Automation & Data Reconciliation Workbench

[Run the miniature](../../excel_reconciliation_demo/README.md) ·
[Source](../../excel_reconciliation_demo/reconcile.py) ·
[Tests](../../excel_reconciliation_demo/tests/test_reconcile.py)

The public example reconciles two fixed-schema CSV extracts. It normalizes IDs
and exact decimal amounts, matches unique invoice keys, quarantines duplicates,
preserves unmatched/rejected records and accounts for every input row. Outputs
can be imported into Excel. The synthetic example has 14 input rows, 3 matched
pairs totaling 15.50, 4 unmatched rows, 3 duplicate rows and 1 rejected row.
Twelve tests verify the miniature; reruns reproduce the included output bytes.

The larger private application adds a Tkinter UI, workbook ingestion, configurable
rules, human review of fuzzy candidates, transactional target updates and
Excel/CSV/HTML/JSON exports. Those capabilities are not part of this public CSV
miniature. Its deterministic output rerun is not a claim of database idempotency.

## 2. Reliable Event-Driven Operations Backend

[Run the miniature](../../event_operations_demo/README.md) ·
[Source](../../event_operations_demo/operations.py) ·
[Tests](../../event_operations_demo/tests/test_operations.py)

The public example processes a synthetic in-memory event queue. Selected
transition rules, same-process idempotency, conflicting-ID rejection, recoverable
early events, simulated transient failures and bounded retries lead to an
inspectable JSON result. Four effects apply, seven retries are queued, one
duplicate is ignored and four failures enter the dead-letter list. Fourteen
tests verify the miniature and its reproducible sample output.

The larger private implementation uses FastAPI/SQLAlchemy/SQLite and Streamlit
for resource allocation, artifact custody and verified backup. Its integrated
service/persistence layer, allocation concurrency, backup/retention/deletion and
deployment tooling are excluded. The miniature has no durable state, real
external side effects, multi-worker coordination or production delivery guarantee.

## Provenance and boundaries

These are AI-assisted independent demonstrations, separate from employment
achievements. They contain no real client data or claim of paid-client usage,
production deployment, measured business savings or tamper-proof audit storage.
Historical full-application test counts and videos are not evidence for these
miniatures. The existing selected-work-samples PDF remains a historical overview
of the larger applications; the linked miniature READMEs define the code actually
published here.

No software license was added or changed. The repository currently has no
software license; public visibility should not be interpreted as a permissive
open-source reuse grant.
