# Data contract

## Canonical record

The seeded dataset is fictional equipment-inspection data. Canonical UI rows always include `reading` and `revision`.

| Field | Meaning | Constraint |
| --- | --- | --- |
| `inspection_id` | Stable inspection identifier | Required target for update/delete |
| `equipment_id` | Fictional equipment ID | Required on create; accepted on update |
| `observed_date` | Observation date | ISO `YYYY-MM-DD` |
| `metric` | Measured condition | Bounded demo value |
| `reading` | Numeric observation | Bounded demo value |
| `unit` | Reading unit | Required with reading |
| `revision` | Optimistic-concurrency version | Checked on approval |
| `deleted` | Soft-delete marker | Omitted from dataset reads, retained in audit context |

Extra/invalid fields, dates, and values are rejected. User-controlled storage paths are not part of the contract.

## Endpoints

| Endpoint | Response |
| --- | --- |
| `GET /api/state` | `{schema_phase, current_snapshot, records}` |
| `GET /api/proposals` | `{proposals: []}` |
| `GET /api/audit` | `{audit: []}` |
| `GET /api/snapshots` | `{snapshots: []}` |
| `GET /api/snapshots/{snapshot_id}` | Verified immutable records and manifest |
| `GET /api/records?client_version=1|2` | Supported compatibility view |

`POST /api/proposals` requires `X-Demo-User: analyst`, an `Idempotency-Key`, and `{operation, inspection_id, expected_revision, values, reason}`. Operation is `create`, `update`, or `delete`; create expects revision `0`, updates are patch semantics, and delete has empty `values`.

`POST /api/proposals/{id}/approve` and `/reject` require a reviewer, an idempotency key, and `{"reason":"..."}`. An author cannot self-approve. Approval repeats the revision check inside the transaction; stale proposals conflict (`409`). One accepted change creates one audit event and one dataset revision.

`POST /api/migrations/{expand|backfill|contract}` requires `X-Demo-User: admin`, an idempotency key, and `{}`. Invalid phase order conflicts (`409`). Successful responses include the new `schema_phase`, `current_snapshot`, and audit ID.

Same key + demo principal + operation + payload replays its stored response. Changed payload with that key conflicts (`409`); identity/role are checked before replay. Errors use `{"detail":"human-readable explanation"}`.

## Compatibility

v1 exposes `reading`. Expand physically adds v2 `measurement_value` with the same numeric value/unit semantics and dual-writes new changes. Backfill copies historical values. Contract requires completed backfill and performs equality/non-null verification, then rebuilds the SQLite table without the legacy column; v1 receives an explicit `410`, while v2 remains supported. `/api/state` stays canonical with `reading` and `revision`; contracted Parquet data exposes `measurement_value`.

## References

- [SQLite transaction control](https://www.sqlite.org/lang_transaction.html)
- [PyArrow Parquet `write_table`](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
