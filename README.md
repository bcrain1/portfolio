# Brandon Crain — Analytics & Data Systems

Selected independent work demonstrating metric design, trustworthy data pipelines,
and clear analytical decisions. These projects use synthetic data and are separate from employment achievements.

## Excel Automation & Data Reconciliation Workbench

A runnable miniature reconciles two synthetic CSV extracts with exact decimal
amounts, conservative matching, duplicate quarantine and row-level exceptions.
All 14 input rows are accounted for. Outputs can be imported into Excel.

- [Run the demonstration](excel_reconciliation_demo/README.md)
- [Inspect matched, unmatched and duplicate outputs](excel_reconciliation_demo/sample_output)
- [12 automated tests](excel_reconciliation_demo/tests/test_reconcile.py)

This publishes a fixed-schema CSV workflow; the full configurable workbook
application, transactional migration engine and packaging remain private.

## Reliable Event-Driven Operations Backend

A runnable miniature handles synthetic job events with selected lifecycle rules,
duplicate suppression, conflicting-ID rejection, recoverable early events,
bounded retries and inspectable dead letters.

- [Run the demonstration](event_operations_demo/README.md)
- [Inspect the event and state evidence](event_operations_demo/sample_output/evidence.json)
- [14 automated tests](event_operations_demo/tests/test_operations.py)

This publishes an in-memory queue demonstration; the full integrated backend,
durable persistence, allocation, backup/retention and deployment tooling remain
private. Idempotency in this miniature does not survive process restart.

## New Content Experience Measurement Lab

**Question:** Does higher observed return justify expanding a new live-content experience?

An end-to-end Python/SQL project connects telemetry validation, event-time
sessionization, cohort metrics, uncertainty, and an interactive dashboard. It
shows how audience mix can produce a persuasive result without causal benefit.

- [Project and reproduction instructions](content_measurement_lab/README.md)
- [Two-page selected work samples (PDF)](content_measurement_lab/output/Brandon_Crain_Selected_Work_Samples.pdf)
- [Decision memo](content_measurement_lab/output/FINDINGS.md)
- [Metric definitions](content_measurement_lab/docs/METRICS.md)
- [Tests](content_measurement_lab/tests/test_lab.py)

To use the dashboard, download this repository using **Code → Download ZIP**,
extract it, and open `content_measurement_lab/output/dashboard.html` in a browser.
It runs offline without an account or API key. GitHub's file viewer displays the
HTML source rather than running the dashboard.

**Evidence:** 20 acceptance tests; reproducible analytical results; filters and
CSV export verified. Synthetic and not affiliated with Netflix.
No employer or client data is included. No production deployment or causal lift
is claimed.

## Governed Data Service

**Question:** How can teams review data changes while preserving audit history and schema compatibility?

A runnable Python/FastAPI service for fictional equipment inspections demonstrates
proposal review, stale-revision checks, retry-safe operations, immutable Parquet
snapshots, and expand/backfill/contract schema migration.

- [Project and local demo instructions](governed_data_service/README.md)
- [Two-page case study (PDF)](governed_data_service/output/Brandon_Crain_Governed_Data_Service.pdf)
- [Architecture](governed_data_service/docs/ARCHITECTURE.md)
- [Data contract](governed_data_service/docs/DATA_CONTRACT.md)
- [Walkthrough](governed_data_service/docs/OWNER_WALKTHROUGH.md)
- [Tests](governed_data_service/tests/test_service.py)

**Evidence:** 15 local automated tests passed. This is a synthetic, single-host
demonstration. The role selector is intentionally impersonable and is not
production authentication. Run the Python service locally to use the review
console; GitHub displays its HTML source.

## Infrastructure Efficiency Decision Lab

**Question:** Which resource-efficiency changes deserve a controlled trial when lower cost can hide worse latency or a different workload mix?

A runnable Python/SQLite miniature reconciles fictional infrastructure costs to
successful work, quarantines invalid comparison windows, checks latency and error
guardrails, and exposes misleading pooled savings from workload mix.

- [Project, reproduction instructions and walkthrough](infrastructure_efficiency_decision_lab/README.md)
- [Decision memo](infrastructure_efficiency_decision_lab/output/FINDINGS.md)
- [Offline dashboard source/download](infrastructure_efficiency_decision_lab/output/dashboard.html)
- [Cost ledger](infrastructure_efficiency_decision_lab/output/accepted_cost_ledger.csv)
- [Acceptance tests](infrastructure_efficiency_decision_lab/tests/test_lab.py)

Download this repository using **Code → Download ZIP**, extract it, and open
`infrastructure_efficiency_decision_lab/output/dashboard.html` in a browser.
GitHub's file viewer shows HTML source; the dashboard runs locally without
accounts, credentials or paid services.

**Evidence:** 20 Python tests, 24 dashboard control combinations, and two actual
Chrome CSV downloads checked. Exported rows preserve synthetic-data caveats,
accepted-period coverage and guardrail decisions. All data and prices are
fictional; no Netflix affiliation, actual production savings or causal impact
is claimed.

## Advertiser Demand Decision Lab

**Question:** Should an advertiser team investigate planning completion or campaign-launch follow-through first, and when would that recommendation change?

An independent Python/SQL analysis uses fictional advertiser events, mature
cohort funnels, telemetry checks, fixed-mix comparisons and recovery scenarios
to build a conditional recommendation. Stage-priority scores are diagnostic;
they are not predicted launches, revenue or causal effects.

- [Project and reproduction instructions](advertiser_demand_decision_lab/README.md)
- [Two-page case study](advertiser_demand_decision_lab/output/CASE_STUDY.pdf)
- [Metric definitions and limitations](advertiser_demand_decision_lab/docs/METRICS.md)
- [Offline dashboard source/download](advertiser_demand_decision_lab/output/dashboard.html)
- [Tests](advertiser_demand_decision_lab/tests/test_lab.py)

Download this repository using **Code > Download ZIP**, extract it, and open
`advertiser_demand_decision_lab/output/dashboard.html` in a browser. GitHub
shows HTML source; the self-contained demo runs locally without accounts,
credentials or network access.

**Evidence:** 30 automated tests, 500 dashboard control combinations and six
actual browser downloads checked. Independent mathematical and engineering
reviews and deterministic rebuild checks are documented in the project.
All data is fictional; no Netflix affiliation, employer-data use, production
deployment, causal lift or advertising-employment experience is claimed.
The original Content Measurement Lab remains a separate, preserved project.

## Implementation notes

Developed with AI assistance. Each project documents its methods, reproducible checks and limitations; these demonstrations are separate from employment achievements.

