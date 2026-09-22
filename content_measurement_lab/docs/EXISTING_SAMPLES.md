# Other selected work samples

These two existing, separate projects complement the new measurement lab.
Their READMEs were reviewed September 22, 2026. Their full test suites were not
rerun for this packet. Both are independent demonstrations with synthetic data.
No source from either project was copied into this lab or modified.

## Excel Automation & Data Reconciliation Workbench

Question: how can inconsistent business records be reconciled without silently
accepting ambiguous matches or creating duplicate target records on a rerun?

A local Python/Tkinter application validates a workbook contract, normalizes
Customers/Products/Transactions, surfaces validation errors and fuzzy duplicate
candidates, requires human disposition for ambiguous matches, and commits accepted
records transactionally. It exports Excel/CSV/HTML/JSON evidence and recognizes
identical reruns. Useful analytics connection: trustworthy inputs and explicit
exception handling before downstream metrics are calculated.

Boundary: synthetic local migration scenario; no paid-client system, production
deployment, independently established business savings or security certification.

## Reliable Event-Driven Operations Backend

Question: how can retries, conflicting resource requests and failed artifact
operations remain recoverable without losing their evidence?

A local FastAPI/SQLAlchemy/SQLite service with a Streamlit dashboard demonstrates
transactional allocation, idempotent event handling, operational monitoring and
SHA-256-verified backup. Lifecycle state and audit evidence make failures
inspectable. Useful analytics connection: reliable event processing and
traceability before trusting the outputs of a data product.

Boundary: single-host synthetic demonstration; not production-scale architecture,
client work, tamper-proof storage or a WORM ledger. Multi-instance concurrency,
authentication and authorization require additional work.
