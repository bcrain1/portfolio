# Release boundary

Release checks cover the local review workflow, data integrity and recovery behavior. Inspection data and rules are synthetic; production authentication and distributed deployment remain outside scope.

Before sharing: read OWNER_WALKTHROUGH.md and be ready to explain the publication pointer, retry identity, stale-revision check, schema compatibility and demo authentication boundary.

The ZIP contains source, deterministic tests, a local review console, documentation and a two-page case study. Runtime databases, virtual environments, internal QA and private planning metadata are excluded. No employer-specific data or operator credentials are needed.

The workflow at .github/workflows/tests.yml is ready for a standalone repository. For the existing portfolio monorepo, place it at the repository root .github/workflows/governed-data-service.yml; it detects the governed_data_service subfolder. A supplied workflow is not evidence that remote CI has run. Current local checks are documented separately in VALIDATION.md.

Only the project lead publishes within owner authorization. Verify the final allowlist and remote file hashes, preserve existing repository content, and record the commit receipt. No automatic deployment, application submission or new paid service is part of this project.
