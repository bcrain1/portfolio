# Metric contract

All records are fictional, deterministic fixtures. No advertiser, Netflix, customer or employer data is used. This is a diagnostic decision miniature, not a demand forecast, causal estimator or production system.

## Grain, clock and eligibility

One immutable advertiser ID identifies its first planning attempt. Segment is fixed at that attempt: emerging, growth or established. Baseline attempts start August 1–10, current attempts September 1–10, 2026. These intentionally separated cohorts use the same inclusive 14-day window. Fixed snapshot: October 7, 2026 UTC. Follow-up closes at started_at + 14 days. Timestamp timezone is required; received_at must not precede event_at. Deliveries after the snapshot are excluded **before** duplicate conflict resolution. Valid events delivered by the snapshot after the outcome window still count if event_at falls within the window. Events occurring after day 14 do not count.

Eligibility requires mature follow-up, explicit telemetry_complete=true, valid dimensions and a valid nested event sequence. A missing completion event becomes a dropoff only for an eligible advertiser. The completeness flag is synthetic ground truth here; in production it would require independent source reconciliation or coverage checks. Future deliveries alone cannot establish completeness. A valid initial plan_started event must coincide with the dimension anchor; at most one of each event type is allowed. Launch requires an earlier or simultaneous completion. Timestamp equality is permitted; it cannot establish ordering within timestamp precision.

Exact retries (same payload excluding receipt clock) collapse. Conflicting event IDs quarantine every known affected advertiser; they are not counted as failures. Missing event IDs and invalid event clocks quarantine identifiable advertisers. Unknown advertisers are counted as rejected events; conflicting IDs can still quarantine a known counterpart. A missing dimension ID or conflicting advertiser dimensions fails the run because its denominator or cohort/segment membership cannot be attributed safely. No first-row winner is selected. Exclusions have one precedence category: invalid, then immature, then incomplete. Separate mature/complete/valid flags retain overlapping reasons.

The miniature accepts ISO timestamps with whole seconds and a Z or signed HH:MM timezone only. Fractional seconds, including sub-microsecond values and fractional timezone offsets, are rejected rather than truncated across snapshot or outcome-window boundaries. Invalid event or dimension timestamps follow the exclusion rules above; an invalid snapshot timestamp fails the run.

## Funnel and standardization

Every displayed funnel count uses exactly the same eligible denominator, N. Planning dropoff = N - completed; post-plan launch dropoff = completed - launched. Each rate = count / N * 100. The latter is **not** a conditional launch rate among completers. Planning dropoff + launch dropoff + launched = N. Baseline and current rates use their own eligible N; changing coverage may select a different population, so exclusions are shown by cohort and segment.

Reference weights are baseline eligible segment counts divided by baseline eligible N, scoped to the selected segment filter. Both cohorts' segment-specific rates are reweighted to this same baseline composition. This answers: what would each cohort's rates look like at the baseline observed eligible segment mix? It does not adjust other confounding. No baseline or a missing current cell with positive reference weight makes the standardized result unavailable, never zero. Zero baseline-weight cells are outside this estimand.

Wilson 95% intervals apply only to raw binary proportions, per 100 eligible. They are descriptive binomial summaries under independent-unit assumptions, not evidence of experimental causality or uncertainty intervals for the reweighted estimator. No interval is returned at N=0. Synthetic exact-count fixtures were constructed for demonstrable outcomes; their intervals do not measure real-world forecast confidence.

## Diagnostic priority and safeguards

Planning score = current standardized planning-dropoff rate * assumed planning recovery fraction. Launch score = current standardized post-plan dropoff rate * assumed launch recovery fraction. Recovery controls are user assumptions, not fitted effects. The scores measure stage-specific diagnostic opportunities, **not equal business value or predicted launches**: recovering a plan does not guarantee a launch. No cost, advertiser budget, sales capacity, inventory or demand-elasticity model is included. Compare historical raw and standardized changes separately from this current-level investigation ranking.

Hold if support is absent, any positive-reference-weight cell has fewer than 20 eligible advertisers in either cohort, or incomplete + invalid exceeds 10% of eligible + incomplete + invalid in either cohort. The quality denominator excludes known immature records; invalid timestamps are conservatively included as invalid. These are explicit demonstration thresholds, not empirically optimized rules. Scores below 1 per 100 yield no material priority; gaps below 2 yield balanced investigation. Otherwise prioritize the larger diagnostic opportunity. Equality is never assigned an arbitrary winner.

## Fixtures and reproducibility

Seed 42808 controls event timing/shuffle. Within-cell outcome counts are exact and deterministic: planning_friction favors a planning investigation; launch_friction favors a launch investigation; mix_shift changes only current segment composition; telemetry_gap suppresses current completeness to demonstrate a hold; empty demonstrates no-data behavior. In mix_shift, raw launches fall from 50% to 35.333% while baseline-weighted launches remain 50%. This is compositional evidence, not proof that segment explains a real business decline.

`python lab.py --output output` writes raw fixture CSVs, advertiser metric CSVs and data.json. The JSON includes all scenarios, quality counters and 500 precomputed views for offline controls. Metric rows and decision views include synthetic labels and as-of dates. Data has no network dependency. Tests cover hand-computed counts/rates, missing support, Wilson bounds, changes in priority, deterministic bytes and malformed/late/duplicate inputs.
