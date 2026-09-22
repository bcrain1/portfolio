# Measurement decision memo

Independent synthetic demonstration; no Netflix or employer data. Seed 41896.
Snapshot: 2026-08-29T00:00:00Z. This is an illustrative result, not a business finding.

## Decision
Do not infer an incremental retention benefit from the raw comparison. Validate
instrumentation and exposure logging, then design a randomized exposure study
before making a causal claim or using this result to justify a rollout.

## Evidence
- Eligible members: 1600; seven-day event-time-mature cohorts: 1194.
- Excluded from ALL displayed member rates due to incomplete follow-up: 406.
- Exposed return rate: 64.0% (445/695).
- Unexposed return rate: 33.7% (168/499).
- Raw difference: 30.4 percentage points.
- Difference standardized to pooled PRE-index activity mix: 4.6 percentage points.

The simulator deliberately assigns exposure more often to frequent viewers.
Return probability depends on baseline activity, with no causal exposure effect.
Standardization demonstrates this measured confounder; it does not prove causal
identification in real data or eliminate unmeasured selection bias.

## Measurement cautions
Eligibility is indexed before exposure. Exposure is within the first hour;
initial engagement is the first 24 hours. Return means a new playback start
strictly after 24 hours and at or before 168 hours, anchored to eligibility for
BOTH cohorts. A playback start is not proof of completed viewing or satisfaction.
Observed watch time sums unique valid heartbeat seconds; missing telemetry can
undercount it. A 7-day event-time horizon is required, but late-arriving telemetry
can still revise a mature cohort. Reprocess new snapshots and test a 48-hour
arrival buffer before treating recent rates as stable.

Wilson intervals describe sampling uncertainty under an independent-member
binomial approximation; they do not correct bias. This is not an A/B test.
No p-value, causal lift, Netflix benchmark, or production-scale claim is made.

## Next analysis
Track play errors, no-heartbeat sessions, and ingestion latency alongside adoption.
Measure content substitution and satisfaction separately; return alone is not
enough to define value. Randomize exposure at member level with a prospectively
chosen primary metric, sample-size calculation and guardrails. That experiment
is a proposal, not an implemented or completed study.
