# Release validation

Reviewed October 7, 2026, within the bounded synthetic offline-demo scope.

- **30 Python tests passed**, including hand-computed counts and weights, pure mix shift, recommendation changes, zero observations, missing support, quality thresholds, duplicate/conflicting identities, absent clocks/IDs, late/future receipts, inclusive windows, fractional timestamps, deterministic files and immutable snapshot handling.
- Independent analytical reviewer recomputed consequential scenario results directly from raw events and verified the pure-mix example. No remaining mathematical blocker was found.
- Independent engineering reviewer reproduced and verified fixes for input-order-dependent conflicting dimensions and fractional-clock boundary leakage. No remaining engineering blocker was found in the reviewed scope.
- Actual local Chrome checked **all 500 control combinations**, reset and expandable details, desktop and mobile layouts, and six downloaded exports. No browser exceptions, network requests or page-width overflow occurred. The final default desktop/mobile and no-data views were inspected visually.
- Three downloaded CSVs (ordinary, coverage-hold and empty) were compared to source metric records. Empty export metadata is explicit `scope_only`, not a manufactured advertiser. Decision JSON snapshots preserve assumptions and scope.
- Rebuilding core outputs produced identical bytes. Original Content Measurement Lab file hashes remained identical. The two-page PDF was rendered and both pages inspected.

## Review findings resolved

Receipt/as-of checks precede event conflict resolution. Conflicting advertiser dimensions now stop the run instead of selecting an arbitrary cohort/segment. Fractional timestamps are rejected before epoch conversion. Invalid/missing coverage cannot be diluted by immature records. Snapshot labels reflect the actual analytical cutoff. Quarantine counts measure affected advertisers rather than dictionary accesses. Unknown-advertiser conflicts cannot silently preserve a contaminated known event.

## Limits of validation

Tests concern this fixed synthetic implementation, not production readiness, statistical identification or real advertising data quality. Thresholds are illustrative. There is no deployed multi-user service, load/performance certification, accessibility certification or external integration. Browser checks used Chrome on this Windows environment; other browser engines were not tested. Original source code was preserved, not revalidated as a separate product.

The final stage-priority scores remain explicitly noncausal and are not equal business outcomes. Fixed-count fixtures make Wilson intervals illustrations of a binomial approximation, not empirical uncertainty about real advertisers. Publication is owner-approved; these checks do not imply employer submission.
