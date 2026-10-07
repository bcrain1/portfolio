# Architecture and reuse

`deterministic fictional sources → receipt/as-of validation → duplicate and identity checks → valid advertiser/event records → SQLite advertiser metrics → fixed-reference comparison → policy gates → 500 decision views → offline HTML / CSV / JSON`

The Content Measurement Lab's clock parsing, Wilson calculation, deterministic generation pattern, receipt-before-conflict rule, advertiser/member-grain `EXISTS` approach and explicit noncausal interpretation informed this adaptation. The schema, stage validation, dimension fail-closed behavior, scenario fixtures, prioritization rules, quality gate, exports and UI are specific to this new entry. Original source files remain unchanged. This is a reuse of analytical and engineering components, not a relabeling of viewing metrics as advertising outcomes.

Runtime code uses Python standard library and in-memory SQLite. Inputs and scenario parameters are bounded by explicit accepted values. All browser data are local; DOM text uses textContent and there is no network dependency. The dashboard embeds JSON with closing-script sequences escaped and applies a restrictive content-security policy. No credentials, login, database service or deployment is part of the demo.

Reproducibility concerns semantic and generated file content: identical seed/input yields identical CSV/JSON/HTML. Generated database bytes and PDF metadata are not used as semantic correctness evidence. This is a compact offline teaching system, not a distributed production pipeline.
