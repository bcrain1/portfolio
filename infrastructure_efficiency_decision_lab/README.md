# Infrastructure Efficiency Decision Lab

Decide which infrastructure changes deserve a controlled trial by connecting cost allocation, successful work, latency guardrails and workload mix.



## Start here

Open `output/dashboard.html` in a browser. It works offline, with service/scenario filters, CPU-price sensitivity and comparison CSV export. Read `output/FINDINGS.md` for the decision memo.

CSV exports retain the synthetic-data caveat, accepted first/last hour (inclusive), accepted/input/excluded hour counts, price sensitivity, and per-service decision and guardrail fields. The period bounds do not imply complete coverage; quarantined hours remain excluded.

From this project directory, rebuild with Python 3.10+ (standard library only):

```sh
python -B lab.py
python -B -m unittest discover -s tests -v
```

The generated SQLite database is excluded from Git; `python -B lab.py` creates it locally. Node.js 24+ is optional for `node tests/dashboard_checks.cjs`. The real-browser export check is optional: `node tests/browser_export_check.cjs <Chromium executable> <empty QA output directory>`. It launches a separate temporary browser profile.

GitHub displays HTML source. Download the repository ZIP, extract it, then open `output/dashboard.html` locally.

## What the example demonstrates

- Reconcile CPU, memory, storage and allocated shared overhead using integer microdollars.
- Compute cost per successful task, retries, errors and CPU utilization with explicit denominators.
- Reject a cheaper interactive-service scenario when latency exceeds its budget.
- Expose a workload-mix trap: pooled unit cost improves without meaningful within-service efficiency.
- Deduplicate replayed events, quarantine conflicting or invalid telemetry, and compare identical accepted windows.
- Preserve an auditable SQLite ledger, SQL aggregations, quality report and reproducible file hashes.

The default seven-day example retains 165 of 168 hours after deliberately injected faults. Batch shows 20.13% lower modeled unit cost and passes the configured guardrails. Interactive shows 25.35% lower cost but fails its 250 ms latency budget at 300 ms. Changing workload mix alone produces a misleading 25.69% pooled reduction; baseline-mix standardization reduces that to approximately zero.

## Data and methodology

All workloads, prices and performance scenarios are fictional. Reported cost changes are modeled comparisons, not measured production savings. No employer data is used.

## Model and architecture

`generate → validate/deduplicate → matched-hour quarantine → integer cost ledger → SQLite aggregation → decisions → offline dashboard`

Input grain: one scenario/service/hour. Three services and three scenarios share comparison hours. Base successful work is 99% of requests. The optimized scenario preserves task counts and fixture-output fingerprints while reducing allocated resources; the interactive scenario deliberately worsens latency. These are designed examples, not empirical benchmark measurements.

CPU costs $0.05 per allocated vCPU-hour; memory $0.005 per GiB-hour; storage $0.0001 per GiB-hour; shared overhead $0.30 per scenario-hour. Shared cost is allocated by requested tasks using largest remainders, with service-name tie breaking. An entirely idle window uses equal shares. Idle CPU cost is a subset of CPU cost, never an extra ledger charge. It represents allocated-minus-busy capacity, not proven recoverable savings.

SQL in `sql/service_metrics.sql` sums numerator/denominator components before calculating ratios. Baseline-mix standardization weights target service unit costs by baseline successful work. The maximum hourly p95 is explicitly labeled **worst interval p95**, never fleet or combined p95. CPU-price sensitivity changes modeled costs only; it does not simulate new performance.

## Evidence and scope

- `output/accepted_cost_ledger.csv`, `output/ledger.sqlite3`: accepted row-level cost evidence.
- `output/quality.json`: exact replays, rejected identities and excluded hours.
- `output/results.json`: service metrics, guardrails, reconciliation and semantic ledger SHA-256.
- `output/manifest.json`: hashes for deterministic text/CSV/HTML artifacts; SQLite file bytes are not treated as canonical.
- `tests/test_lab.py`: conservation, denominator safety, data failure handling, semantic/latency/error vetoes, mix adjustment and reproducibility.

No cloud account, paid service, credentials or network access is required. The prototype does not ingest real billing exports, infer optimal capacity, aggregate true latency percentiles, prove output equivalence, model deployment effort, or estimate causal ROI. Full missing hours outside the input coverage cannot be discovered without an expected calendar. Excluded-hour cost is unknown and not extrapolated.

## Five-minute walkthrough

1. Start with all services and capacity optimization. Inspect cost and the interactive latency veto.
2. Filter to batch; connect its service-level cost reduction to a controlled-trial hypothesis.
3. Switch to workload-mix trap. Compare pooled versus standardized improvement.
4. Move CPU price sensitivity; distinguish economic sensitivity from performance evidence.
5. Inspect coverage and reconciliation, then open the findings memo and test suite.

For a real experiment, predefine comparable cohorts, validate actual contract prices and task semantics, capture raw latency distributions and saturation, and preregister rollback criteria. Quantify uncertainty and operational effort before recommending investment.
