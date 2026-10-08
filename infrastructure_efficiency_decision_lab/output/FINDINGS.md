# Infrastructure Efficiency Decision Lab — findings

## Decision

Advance the batch change to a controlled trial; hold the interactive change despite attractive modeled cost reductions because its latency guardrail fails. Streaming has a smaller modeled improvement. These are hypotheses to validate, not deployment approval.

| Service | Modeled unit-cost change | Worst interval p95 / budget | Decision |
|---|---:|---:|---|
| batch | 20.13% lower | 610 / 900 ms | CANDIDATE_FOR_CONTROLLED_TRIAL |
| interactive | 25.35% lower | 300 / 250 ms | HOLD |
| streaming | 2.77% lower | 200 / 220 ms | CANDIDATE_FOR_CONTROLLED_TRIAL |

## Workload-mix trap

Changing only the workload mix lowers pooled cost per successful task by 25.69%, but the baseline-mix standardized change is 0.0017%. The tiny residual reflects within-service hourly reweighting and integer rounding, not demonstrated efficiency. Always inspect service-specific denominators.

## Coverage and reconciliation

Accepted 165 of 168 hours across all services/scenarios. Excluded hours: 2026-01-05T02:00:00+00:00, 2026-01-05T05:00:00+00:00, 2026-01-05T09:00:00+00:00. Duplicate/conflict/missing-value evidence is in quality.json. Every component and shared allocation reconciles exactly in integer microdollars.

## Next experiment

For a real controlled trial, randomize or otherwise predefine comparable cohorts; preserve task semantics and workload mix; observe raw latency distributions, errors, saturation and operational burden; pre-register rollback thresholds. Validate telemetry completeness and actual contract prices. Recheck costs with uncertainty, rather than converting this simulation into an ROI promise.

## Data and methodology

Fictional prices and simulated telemetry; cost changes are modeled comparisons, not measured production savings.

## Limitations

- Fictional prices and simulated performance; not a real cost or latency benchmark.
- Output fingerprints compare synthetic fixtures only; not evidence of real-system semantic equivalence.
- Worst interval p95 is not a combined service/fleet p95.
- Cost totals cover accepted matched hours, not unknown excluded telemetry.
- Scenarios are designed examples, not causal estimates or production savings.
