# A defensible campaign-planning investigation

Campaign-planning analytics that connects funnel bottlenecks, advertiser mix and recovery assumptions to a conditional investigation priority.

## Decision

Investigate planning completion first in the default fixture, but do not approve an intervention from this score alone. Among 300 usable current attempts, 120 complete a plan and 96 launch. Relative to the baseline's 210 completions and 150 launches, the shared-denominator planning drop-off increases by 30 percentage points. Validate abandonment reasons, inspect planning effort and distinguish genuine friction from intentional pauses.

Under 50% recovery assumptions, standardized diagnostic scores are 30 planning-stage drop-offs versus 4 post-plan drop-offs per 100 eligible attempts. They are stage-specific opportunities, not equivalent terminal outcomes or estimated business value. At a 50% launch-recovery assumption, planning recovery of about 6.7% makes the scores equal. A 2-point tie band is an illustrative decision rule, not statistical significance.

## The recommendation must be able to change

| Designed scenario | Raw launch rate, baseline → current | Adjusted current launch rate | Review outcome at 50% / 50% |
|---|---:|---:|---|
| Planning bottleneck | 50% → 32% | 32% | Investigate planning; scores 30 vs 4 |
| Launch bottleneck | 50% → 18% | 18% | Investigate launch; scores 5 vs 36 |
| Advertiser mix shift | 50% → 35.3% | 50% | No adjusted decline; current-stage priority is a separate question |
| Incomplete telemetry | Selected observed rates are not sufficient | Coverage gate applies | Hold and repair measurement |
| No observations | Unavailable | Unavailable | Hold; do not invent zero opportunity |

The mix-shift fixture changes the current segment composition while preserving segment-level outcomes. It exposes why a persuasive headline decline is not sufficient evidence of process deterioration. Its current-level investigation score may still favor planning, but that does not explain the raw decline.

## Measurement design

The unit is an advertiser's first planning attempt. Baseline and current cohorts share an inclusive 14-day outcome horizon. A usable attempt has mature follow-up, explicit complete telemetry, valid dimensions and correctly ordered start/completion/launch events. Every funnel rate uses the same eligible denominator. Planning drop-off + post-plan drop-off + launched equals that denominator.

Both periods are standardized to the selected baseline cohort's segment distribution. A missing positive-weight segment makes the comparison unavailable. Wilson intervals are shown only as illustrative binomial precision for raw proportions; exact-count synthetic fixtures do not produce empirical uncertainty about real advertisers. Adjusted rates, temporal change and causal effects have no claimed confidence intervals.

## Engineering choices and robustness

Python validates timezone-aware, whole-second event and receipt clocks before SQLite derives advertiser-grain metrics. Exact transport retries collapse; conflicting event IDs quarantine affected advertisers. A conflicting advertiser dimension aborts the run because arbitrary first-row attribution would bias segment exclusions. Future deliveries cannot retroactively create a historical conflict. Invalid or incomplete observations are visible exclusions, never automatic conversion failures.

Five scenarios, four segment selections and 25 recovery combinations produce 500 precomputed views. The HTML uses those values directly, exports a scoped CSV and complete decision JSON, and runs without external resources. This keeps the browser from silently diverging from the tested statistical implementation. The release records independent analytical and engineering reviews alongside automated and actual-browser checks.

## Improvement over the Content Measurement Lab

The original examines fictional viewing exposure and return. This separate entry introduces an advertiser planning/launch decision, two comparable temporal cohorts, explicit recovery sensitivity, a decision boundary, a pure-mix fixture and fail-closed coverage/no-data states. It retains the original's useful principles: one analytical unit, event-time discipline, validation before aggregation, defensible denominators, SQL lineage and honest interpretation. The original files are unchanged.

## What would make a real decision credible

Validate telemetry against an independent source and inspect who is excluded. Interview or review sampled advertisers at each bottleneck. Add intervention costs and a common terminal outcome before optimizing value. Account for repeat attempts, campaign complexity, intent, seasonality and supply constraints. Predefine a prospective evaluation, primary metric and quality guardrails. Those steps address the current uncertainty; adding a complex model or agent without them would not make the recommendation more defensible.

Owner review: explain the grain, fixed weights, missingness gate, mix-shift example, score-unit limitation and one reason the recommended priority changes. Run the dashboard and review both exports before describing this as demonstrated portfolio competence.

## Data and methodology

All advertisers, events and outcomes are fictional. No employer or client data is used. Scenario results are designed diagnostic examples, not measured production results or causal effects.
