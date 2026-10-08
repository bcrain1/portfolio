# Release validation

Release: 2026-09-24 America/Chicago (2026-09-25 UTC). Local service release using synthetic inspection data.

## Automated checks

Command: `python -B -m unittest discover -s tests -v`.

Final frozen backend: **15/15 tests passed**, exit 0, 3.786 seconds on Windows / Python 3.12. The installed FastAPI/Starlette TestClient emitted a non-failing deprecation warning. Tests cover validation and demo roles; role checks before replay; idempotency and restart; altered-payload conflicts; stale concurrent proposals; review/rejection/soft deletion; retained audit and historical versions; pre-commit publication faults and unreachable orphan files; manifest/file tampering; physical expand/backfill/contract migration, client coexistence, and post-contract writes; and fresh demo generation.

Initial Windows file-flush and connection-cleanup failures were corrected before the passing baseline. Tests establish the specified local behaviors, not production authentication or power-loss guarantees.

## Independent critical review

A separate Sol reviewer found no essential correctness blocker in the frozen backend. Three isolated probes passed: abrupt child-process exit before approval commit followed by restart/retry; contract-migration rollback followed by restart/retry; and a concurrent reader observing complete old/new versions around commit. These were one-time review probes, **not three additional checked-in regression tests**. Preserving abrupt-exit and migration-fault cases in the regression suite is a future improvement.

The generator records its absolute output directory for local diagnostics. Released sample evidence removes that field, generated IDs, and workstation paths. Runtime databases and raw QA are excluded from the release package.

## Reproducibility

Two independently generated fresh datasets produced matching semantic results: four records preserved; INSP-1001 changed from 2.4 to 2.7 only after approval; five published snapshots; expanded, backfilled, then contracted phases; unchanged historical snapshot. IDs, timestamps, and binary file bytes intentionally differ. See `output/demo_semantic_evidence.json`.

## Browser checks

Actual Chrome interaction against the local FastAPI service verified:

- Analyst proposal displayed its values, reason, and expected revision while the current value remained 2.4.
- Reviewer approval changed the value to 2.7, incremented revision 1 to 2, cleared the pending count, and created an audit event and snapshot.
- The original snapshot remained readable with value 2.4 and revision 1.
- Expand exposed v2 values; backfill and contract preserved all four records; v1 showed its retirement error while v2 remained readable.
- Desktop layout and a 390-by-844 phone viewport were visually inspected. Phone tables intentionally scroll horizontally; form fields stack. The temporary viewport override was reset.
- Preview JSON height was bounded after visual inspection; final JavaScript syntax passed.

The summary PDF is two pages and was rendered for every-page visual inspection before delivery. This does not establish owner familiarity; review `OWNER_WALKTHROUGH.md` before presenting the project.

## Scope limits

Local impersonable identities, single-writer SQLite, local filesystem durability, retained unreferenced files, and a non-tamper-proof audit trail are explicit design limits. No cloud, multi-host, employer-data, production IAM, business-impact, or disaster-recovery claims are made. The supplied GitHub Actions workflow has not run remotely as part of this local release.
