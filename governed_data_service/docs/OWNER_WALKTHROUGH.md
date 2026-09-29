# Owner walkthrough: 10 minutes

This is a local conversation aid using fictional data. It is not a production runbook.

## 0:00–1:00 — Frame the demo

Open the console and show the synthetic-data badge and identity selector. Explain: “The selector only changes a request header. It makes workflow policy visible but does not authenticate anyone.”

**Why expose an insecure selector?** It makes the authorization boundary reviewable in a small demo. A production service would receive identity from a trusted authentication layer.

## 1:00–3:00 — Read the published state

Review records, schema phase, and snapshot ID. SQLite stores the authoritative control-plane state and a pointer to one immutable Parquet version. The selected snapshot’s manifest checks file hashes and row counts.

**Why SQLite plus Parquet?** SQLite is practical for small serialized workflow state; Parquet represents immutable analytical versions. The pair distinguishes mutable approval decisions from published data.

## 3:00–5:00 — Propose and decide

As `analyst`, submit an update with the visible revision. As `reviewer`, approve with a reason and refresh. Point out the audit event and new snapshot pointer.

**What prevents lost updates?** Approval checks the version seen by the analyst again while the write transaction is held. A stale proposal fails instead of overwriting newer data.

**Why not direct editing?** The example makes review and audit an explicit policy choice. Direct editing is simpler but removes the demonstrated control point.

## 5:00–6:30 — Publication protocol

Explain the order: validate under the SQLite write transaction, create a unique Parquet snapshot and manifest, flush/close the files, then commit the record, audit, and pointer. Published versions are never overwritten.

**Is this fully transactional?** It is a local publication protocol, not a distributed transaction manager. A pre-commit failure can leave unreferenced files; they are not published and are not automatically deleted. Host durability limits still apply.

## 6:30–8:00 — Soft delete and history

Propose a delete, approve it, and show that the row leaves dataset reads while the audit event remains.

**Can reviewers approve their own work?** No. The service blocks author self-approval. The demo still does not prove real separation of duties because its identities are impersonable.

## 8:00–9:15 — Migration

As `admin`, run expand, backfill, and contract. Expand physically adds `measurement_value`; during coexistence, compare v1 `reading` and v2 `measurement_value`, while new writes dual-write. Contract rebuilds the SQLite table without the legacy field, and v1 then receives an explicit retirement response.

**Why three phases?** Expand preserves compatibility, backfill copies historic values, and contract verifies the complete compatibility invariant before the old view retires. The tradeoff is temporary dual-write complexity.

## 9:15–10:00 — Close honestly

State the boundaries: no production IAM, cloud deployment, replication, encryption/key management, tamper-proof log, or multi-host coordination. There is no employer data. The work is independent and synthetic; the owner should explain the workflow and limits in their own words.

## Reviewer prompts

- What invariant would matter most for a larger team?
- Where would trusted identity and audit retention live in a production design?
- How would you monitor orphan publication files without silently deleting evidence?
- When would a database-only analytical store be preferable to immutable snapshots?

## References

- [SQLite transaction control](https://www.sqlite.org/lang_transaction.html)
- [PyArrow Parquet `write_table`](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)

