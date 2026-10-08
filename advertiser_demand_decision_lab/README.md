# Advertiser Demand Decision Lab



Which stage deserves investigation first: completing a campaign plan, or launching a completed plan? This runnable Python/SQL case study connects comparable cohorts, data-quality gates, assumption sensitivity and a business recommendation. It is a separate entry adapted from the Content Measurement Lab; the original remains unchanged.

## Try it in two minutes

Open `output/dashboard.html` in a browser. It is a self-contained offline file: no server, network, account or dependency installation needed. A file preview may show source text; download and open the file locally to use the controls.

1. Start with Planning bottleneck and 50% recovery assumptions. The suggested investigation is planning completion.
2. Switch to Launch bottleneck. The recommendation changes to launch follow-through.
3. Select Advertiser mix shift only. Raw launch rate drops from 50% to 35.3%, but both adjusted rates are 50%. Composition is not within-segment deterioration.
4. Select Incomplete telemetry or No observations. The demo withholds a recommendation.
5. Change segment and recovery assumptions. Export the scoped cohort CSV and decision JSON. Exports retain synthetic labels, snapshot, selection and assumptions; an empty CSV contains one `scope_only` metadata record, not an advertiser.

Read `CASE_STUDY.md` or `output/CASE_STUDY.pdf` for the business/technical explanation. Review `docs/METRICS.md` before interpreting the scores.

## Reproduce

Python 3.11 or newer with SQLite window/function support from the standard distribution; runtime analysis has **no third-party dependencies**.

```console
python -B build.py
python -B -m unittest discover -s tests -v
```

The build writes only inside `output/`. It generates deterministic synthetic CSVs, validated advertiser-level metrics, precomputed decision JSON, an offline HTML dashboard and file hashes. Seed 42808 controls event timing/order; within-cell outcome totals are deliberately designed, not fitted to observed advertisers. No secrets, real datasets or database connection are required.

The included PDF can optionally be rebuilt with `python -B build_case_study.py` using ReportLab 4.4.9, the version used for this release. It is not needed to run the analysis or dashboard. Core output hashes omit the PDF; PDF container metadata is not treated as reproducible analytical evidence.

## What makes this more robust

- One first planning attempt per advertiser, shared 14-day follow-up and nested funnel stages avoid mixed denominators and event fanout.
- Missing telemetry and immature attempts remain exclusions rather than failed conversions. Quality and minimum-sample gates withhold unsupported recommendations.
- Exact event retries collapse; semantic conflicts quarantine known affected advertisers. Ambiguous advertiser dimension records fail closed instead of changing a segment's result by input order.
- As-of delivery filtering precedes conflict detection. Timezones and whole-second precision are validated; fractional clocks are rejected rather than silently rounded across boundaries.
- Baseline segment weights distinguish aggregate composition changes from within-segment differences. Missing support returns unavailable.
- Explicit recovery assumptions, diagnostic ties and a break-even point expose when the priority changes. Stage scores are not terminal launch or revenue forecasts.
- All 500 offered control combinations are precomputed by Python; the browser does not maintain a second statistical engine.
- Offline exports, zero-data behavior, responsive layout and deterministic outputs are tested. See `docs/VALIDATION.md` for actual release checks and limits.

## Source map

`lab.py` generates and validates fictional source rows, builds SQLite metrics and evaluates scenarios. `sql/metrics.sql` derives one row per attempt with `EXISTS` to avoid event fanout. `build.py` embeds results into `dashboard.html`. `docs/METRICS.md` defines populations, clocks and gates. `tests/` contains hand-computed and adversarial cases. `output/` contains the reproducible review artifacts.

## Limits

This is a diagnostic prototype, not an ad auction, budget allocator, causal estimator, production ML model or demand forecast. Real advertiser data access, instrumentation, domain review, repeated-attempt handling, intervention costs, seasonality, media supply, revenue outcomes and prospective evaluation remain outside scope. Source completeness is asserted by a synthetic flag; a real system needs independent reconciliation. The thresholds are illustrative policy, not empirically calibrated guarantees. A recovery in planning completion is not necessarily a recovery in final launches.

## Data and methodology

Advertisers and events are fictional, with designed scenario outcomes. No employer or client data is used. The analysis supports diagnostic comparison; it does not measure production impact or causal lift.
