# New Content Experience Measurement Lab

**Independent portfolio demonstration · Synthetic data · AI-assisted implementation**

An end-to-end Python/SQL example of defining useful product metrics, repairing
telemetry, and explaining why a persuasive dashboard result is not a causal claim.
Prepared for Brandon Crain's analytics engineering portfolio. No Netflix, Samsung,
client, account, or personal viewing data is used. Not affiliated with Netflix.

## The decision

Should a hypothetical streaming service expand a new live-content experience
because exposed members appear more likely to return?

**The demonstration's answer: do not use the raw return difference as evidence
of incremental benefit.** In this deliberately confounded simulation, exposure
has no causal effect. More active viewers are simply more likely to be exposed.
The useful work is connecting a decision, defensible definitions, inspectable
SQL, uncertainty, and an honest recommendation.

## See the result

Open **[output/dashboard.html](output/dashboard.html)** in a browser. It works
offline: no server, account, API key, runtime LLM, or network request is needed.
Filter by prior activity and eligibility date; inspect denominators, confidence
intervals, audience mix and data-quality exclusions. Export the filtered
member-level metrics as CSV.

Read **[output/FINDINGS.md](output/FINDINGS.md)** for the decision memo and
**[docs/METRICS.md](docs/METRICS.md)** for exact definitions.

### Default reproducible result

| Measure | Synthetic snapshot |
|---|---:|
| Eligible members | 1,600 |
| Mature seven-day cohorts | 1,194 |
| Exposed return rate | 64.0% (445 / 695) |
| Unexposed return rate | 33.7% (168 / 499) |
| Raw difference | +30.4 percentage points |
| Standardized difference, common pre-index activity mix | +4.6 percentage points |

These numbers describe the fixed seed only. The residual standardized gap is
not an effect estimate: finite-sample variation and telemetry selection remain.
Knowing the simulator's design is different from identifying a causal effect in
real observational data. No business result or hiring outcome is claimed.

## Run locally

Python 3.11+ with SQLite window-function support (SQLite 3.25+). Core build and
tests use the Python standard library only. No installation required:

```console
python lab.py
python -m unittest discover -s tests -v
```

Generated outputs: deterministic CSV fixtures, SQLite analytical tables,
member-level metrics, JSON results, offline interactive dashboard, and a
Markdown findings memo. The build overwrites generated files inside `output/`;
keep manual edits outside that directory. Source files are never modified. Raw
deliveries, session CSVs, and the SQLite database are generated locally with
`python lab.py` and are excluded from GitHub. `output/manifest.json` is the
original reproducibility record, not an upload inventory.

Optional two-page work-samples PDF (requires ReportLab):

```console
python -m pip install -r requirements-pdf.txt
python build_summary.py
```

The PDF includes this demonstration and two separate existing synthetic
projects. Their source repositories are not bundled here; their code is not
needed to reproduce this lab. See `docs/EXISTING_SAMPLES.md`.

## Repository map

```text
lab.py                    synthetic generator, validation, reproducible pipeline
sql/01_schema.sql         explicit member and event grain
sql/02_sessions.sql       event-time sessionization using window functions
sql/03_member_metrics.sql cohort and funnel metrics without fanout
dashboard.html            offline interactive dashboard template
tests/test_lab.py         hand-calculated and failure-mode acceptance cases
build_summary.py          optional two-page PDF export
docs/METRICS.md            metric contract, boundaries and uncertainty
docs/ARCHITECTURE.md       design choices and production limitations
docs/OWNER_WALKTHROUGH.md  questions and a review exercise
output/                   generated reproducible example outputs
```

## What the project demonstrates

- A common eligibility anchor avoids comparing cohorts with different clocks.
- One row per member prevents event-volume and join-fanout inflation.
- Duplicate retries are idempotent; conflicting IDs are quarantined.
- UTC event time and ingestion time serve different purposes.
- Immature cohorts stay out of every displayed member rate.
- Missing heartbeats remain unobserved, not invented viewing time.
- Descriptive adjustment and causal inference are explicitly separated.
- A reviewer can trace dashboard numbers back to SQL, fixtures and tests.

## Authorship and publication

Created with Codex assistance for Brandon Crain; AI-assisted implementation and
editorial work are disclosed. This owner-approved portfolio publication does not
establish past employment experience, production deployment, or sole unaided
authorship. Review and run the implementation before representing it as
demonstrated competence.

Download [the two-page selected-work-samples PDF](output/Brandon_Crain_Selected_Work_Samples.pdf).
GitHub displays the HTML source; download [the offline dashboard](output/dashboard.html)
and open the downloaded file locally in a browser to use its filters and CSV export.
