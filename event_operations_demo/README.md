# Reliable Event-Driven Operations Backend

**Question:** Can duplicate, early and temporarily failing events be handled with
bounded retries and a clear record of what actually changed?

Process repeated and out-of-order job events with a clear record of what changed. The dependency-free Python workflow combines lifecycle rules, event-ID conflict detection, process-local duplicate suppression, bounded retries and inspectable dead letters.

## Run it

Python 3.10 or newer. No packages, credentials, server, database or runtime network
connection required. From this directory:

```text
python operations.py
python -m unittest discover -s tests -v
```

The first command reads [scenario.json](examples/scenario.json) and writes
`generated/evidence.json`. Each CLI run starts with fresh in-memory state and
overwrites that one output. Inputs remain unchanged. To choose an alternate
**synthetic** scenario or destination:

```text
python operations.py --input examples/scenario.json --output generated/replay.json
```

## Read the result

[Checked-in evidence](sample_output/evidence.json) records every attempted action,
its synthetic queue tick, applied state change and dead-letter reason.

| Job | Final state | Explanation |
| --- | --- | --- |
| JOB-A | COMPLETED | Early start waits; assignment recovers from one transient failure; start and completion follow |
| JOB-B | CANCELLED | Duplicate cancellation has no second effect; restarting is rejected |
| JOB-C | REQUESTED | Assignment fails three times, then enters the dead-letter list |

Expected totals: **4 applied effects, 7 queued retries, 1 ignored duplicate and
4 dead letters**. Dead letters distinguish conflicting event ID, invalid
transition, unsupported event kind and exhausted retry budget.

## Behavior to inspect

- Legal lifecycle: REQUESTED → ASSIGNED → ACTIVE → COMPLETED; cancellation is
  allowed only from REQUESTED or ASSIGNED. Terminal states cannot restart.
- An event ID is bound to `(job_id, kind)`. Reusing it with a different payload
  is rejected. Replaying the same completed ID causes no second effect.
- A new ID targeting the current state is recorded as a no-op.
- Early start/completion events return to the queue while their predecessors
  can run. Every ID has a bounded attempt budget (default 3). Exhaustion is
  terminal for that ID in this processor; there is no automatic redrive.
- Synthetic transient failures occur **before** a state change. The scenario
  deliberately models no ambiguous remote success or crash between an effect
  and its acknowledgment.
- The complete batch shape is validated before processing. Retry scheduling
  uses deterministic queue ticks, with no sleeping or real-time backoff.

The 14 automated tests cover explicit final states, duplicates, conflicting IDs,
transient recovery, exhausted retries, out-of-order delivery, absent predecessors,
terminal-state safety, unknown inputs, pre-mutation validation, same-process
replay, no-op transitions, retry bounds and exact sample-output reproduction.

## Data and implementation scope

The queue and three jobs are synthetic. Processing is local and in memory.

## Public/private boundary

The selected transition rules and transition guard are adapted from the original
backend demonstration. The small queue processor, fixtures and tests are new for
this public miniature. The original integrated service layer, SQLAlchemy/SQLite
persistence, API/dashboard, allocation concurrency controls, artifact custody,
backup/retention/deletion implementation and deployment tooling remain private.

All state, identities and audit entries are held in memory. Idempotency does not
survive restart. The mutable JSON audit is not tamper-proof. There is no durable
queue, multi-worker concurrency, authentication, real external side effect,
transactional outbox, crash recovery or production delivery guarantee. A real
service needs separate engineering and verification for those capabilities.

Original proof videos and historical full-backend test counts are not included;
they describe the larger private application, not this miniature.

## Repository license status

No repository-wide or project software license accompanies these files, and this
publication adds none. Public visibility allows GitHub viewing/forking under its
terms; it is not a permissive open-source license. See
[GitHub's licensing explanation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
