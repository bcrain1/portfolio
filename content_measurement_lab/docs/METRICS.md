# Measurement contract

## Question and population

The hypothetical product is a live-content discovery experience. The analytical
unit is an eligible member, not an event, device, impression, or session.
`members.eligible_s` is the pre-exposure index time. The synthetic population
contains 1,600 members indexed in August 2026. Pre-period active days are simulated
covariates known at index, not derived from post-exposure activity. There is no
geographic, demographic, billing or personally identifying data.

Snapshot: 2026-08-29 00:00 UTC. Accept only events that both occurred and arrived
by this instant. Use event time to construct sessions. Every member rate below
requires `eligible_s + 604800 <= as_of`. Maturity does not guarantee complete
telemetry: events arriving later can revise historical observations.

## Metric definitions

| Metric | Numerator | Denominator / scope |
|---|---|---|
| Exposure reach | Members with live exposure in [index, index + 1h) | Mature eligible members |
| Live-start conversion | Exposed members with a live session start in [index, index + 24h) | Mature exposed members |
| Meaningful viewing | Exposed members with >=600 observed seconds in one live session starting in first 24h | Mature exposed members |
| Start-to-engagement | Same meaningful-viewing members | Mature exposed live starters |
| Return, by exposure group | Members with any new playback start in (index + 24h, index + 168h] | All mature eligible members in that exposure group, including initial non-starters |
| Live error incidence | Exposed live starters with >=1 playback-error event in a first-day live session | Mature exposed live starters |

The first-day condition applies to session START, not every heartbeat's time.
A session may cross the 24-hour boundary. The dashboard funnel intersects
engagement with exposed live starters, so stages are nested. A ten-minute
threshold is illustrative, not a validated satisfaction metric.

## Session and quality rules

1. Withhold deliveries received after the snapshot before examining payload conflicts. Group available transport deliveries by event ID. Identical payload retries share a
   representative with the earliest `received_at`; ingestion time is not part
   of the semantic payload. Quarantine ALL rows for a conflicting semantic ID.
2. Reject unknown members, unzoned/unparseable times, invalid dimensions,
   received-before-event clocks and watch values outside 0-60 seconds. Only
   heartbeat records may carry nonzero watch seconds.
3. Retain valid events only when occurrence and ingestion are both at/before the
   snapshot. Unavailable events are neither invalid nor evidence of zero activity.
4. Partition by member/device. A play, content change or gap strictly greater
   than 30 minutes starts a new session. An exact 30-minute gap stays together.
   Order equal timestamps with plays first, then by event ID. Multiple simultaneous
   starts on the same device remain ambiguous; a real instrumented session ID is better.
5. Orphan telemetry stays observable but never counts as a playback start.
6. Observed watch seconds sum unique valid heartbeat increments. No interpolation
   or imputation. Missing heartbeats can undercount engagement. The synthetic
   emitter guarantees non-overlapping increments; a production contract must
   also detect overlaps even when event IDs differ.

Exposure is an observed event. Missing exposure records can contaminate the
comparison cohort. “Unexposed” means no qualifying observed exposure; it is not
a randomized holdout. There is only one live content identity in this toy model,
not multiple live titles with potentially different session identities.

## Descriptive adjustment and uncertainty

Two pre-index strata: frequent (5+ active days in prior 14 days), occasional
(under 5). For each stratum, compute each group's return rate, then weight both
groups using the pooled mature population's stratum proportions. Changing the
dashboard filter recomputes those pooled weights. A missing positive-weight
comparison cell makes standardization not estimable.

For the default dataset, raw difference = 30.36 percentage points; standardized
difference = 4.63 points. The simulator's return probability depends on baseline
activity, not exposure. Neither the observed residual nor an interval excluding
zero would override that known design. In real data, covariate adjustment alone
would not establish exchangeability or remove unmeasured confounding.

Wilson 95% intervals are shown for unadjusted group proportions, assuming
independent member-level binomial observations. No adjusted interval, significance
test or causal estimate is reported. Cohort filters are exploratory and may create
small samples. Shared households, repeated eligibility and time-varying
confounders are outside this model.

## Measurement before rollout

Proposed next steps: validate logging, compare mature results after an additional
48-hour arrival buffer, check substitution of other viewing, and choose a
prospective randomized exposure design with satisfaction and quality guardrails.
These are recommendations, not implemented analyses or a completed experiment.
