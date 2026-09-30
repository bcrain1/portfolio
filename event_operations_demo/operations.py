"""Synthetic event processor: bounded retries and process-local idempotency."""

import argparse
import json
from collections import Counter, deque
from pathlib import Path

# Selected reservation transitions adapted from the larger original demonstration.
TRANSITIONS = {
    "REQUESTED": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
EVENT_TARGET = {"assign": "ASSIGNED", "start": "ACTIVE", "complete": "COMPLETED", "cancel": "CANCELLED"}


def require_transition(current, target):
    if target not in TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current} -> {target}")


class Processor:
    """One in-memory queue, no real clock, threads, network or durable state."""

    def __init__(self, jobs, max_attempts=3):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be an integer from 1 to 10")
        if any(state not in TRANSITIONS for state in jobs.values()):
            raise ValueError("unknown initial state")
        self.jobs = dict(jobs)
        self.max_attempts = max_attempts
        self.identities = {}
        self.completed = set()
        self.effects = []
        self.audit = []
        self.dead_letters = []
        self.attempts = Counter()
        self.clock = 0

    def record(self, event, outcome, **details):
        self.audit.append({"sequence": len(self.audit) + 1, "tick": self.clock,
                           "event_id": event["event_id"], "outcome": outcome, **details})

    def process(self, events, transient_failures=None):
        """Validate the complete batch before mutation; failures occur before effect."""
        transient_failures = dict(transient_failures or {})
        if any(type(n) is not int or n < 0 for n in transient_failures.values()):
            raise ValueError("failure counts must be nonnegative integers")
        validated = []
        for event in events:
            if set(event) != {"event_id", "job_id", "kind"} or any(
                not isinstance(v, str) or not v or len(v) > 64 for v in event.values()
            ):
                raise ValueError("events require three nonempty bounded string fields")
            validated.append(dict(event))
        queue = deque((event, 1) for event in validated)
        while queue:
            event, attempt = queue.popleft()
            self.clock += 1
            identity = (event["job_id"], event["kind"])
            event_id = event["event_id"]
            previous = self.identities.get(event_id)
            if previous is not None and previous != identity:
                self.record(event, "ID_CONFLICT")
                self.dead_letters.append({**event, "reason": "ID_CONFLICT"})
                continue
            if event_id in self.completed:
                self.record(event, "DUPLICATE_IGNORED")
                continue
            # Retryable events retain their identity, but are not marked completed.
            self.identities[event_id] = identity
            self.attempts[event_id] += 1
            if event["job_id"] not in self.jobs or event["kind"] not in EVENT_TARGET:
                self.reject(event, "UNKNOWN_JOB_OR_KIND")
                continue
            current = self.jobs[event["job_id"]]
            target = EVENT_TARGET[event["kind"]]
            if current == target:
                self.completed.add(event_id)
                self.record(event, "ALREADY_IN_STATE", state=current)
                continue
            try:
                require_transition(current, target)
            except ValueError:
                # A start/complete arriving early can recover later in this batch.
                future = (current == "REQUESTED" and target in {"ACTIVE", "COMPLETED"}) or (
                    current == "ASSIGNED" and target == "COMPLETED"
                )
                if future:
                    self.retry(queue, event, attempt, "WAITING_FOR_PREDECESSOR")
                else:
                    self.reject(event, "INVALID_TRANSITION")
                continue
            if transient_failures.get(event_id, 0) > 0:
                transient_failures[event_id] -= 1
                self.retry(queue, event, attempt, "SIMULATED_TRANSIENT_FAILURE")
                continue
            self.jobs[event["job_id"]] = target
            self.effects.append({"event_id": event_id, "job_id": event["job_id"], "from": current, "to": target})
            self.completed.add(event_id)
            self.record(event, "APPLIED", attempt=attempt, before=current, after=target)
        return self.snapshot()

    def retry(self, queue, event, attempt, reason):
        if self.attempts[event["event_id"]] >= self.max_attempts:
            self.reject(event, "RETRY_EXHAUSTED", cause=reason)
        else:
            self.record(event, "RETRY_QUEUED", attempt=attempt, reason=reason)
            queue.append((event, attempt + 1))

    def reject(self, event, reason, **details):
        self.completed.add(event["event_id"])
        self.dead_letters.append({**event, "reason": reason, **details})
        self.record(event, reason, **details)

    def snapshot(self):
        return {"classification": "synthetic demonstration", "states": dict(self.jobs),
                "effects": list(self.effects), "dead_letters": list(self.dead_letters),
                "audit": list(self.audit), "summary": {"applied_effects": len(self.effects),
                "dead_letters": len(self.dead_letters), "outcomes": dict(Counter(row["outcome"] for row in self.audit))}}


def run(input_path, output_path):
    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("output must differ from input")
    scenario = json.loads(input_path.read_text(encoding="utf-8"))
    processor = Processor(scenario["jobs"], scenario["max_attempts"])
    result = processor.process(scenario["events"], scenario["transient_failures"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).parent / "examples" / "scenario.json")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "generated" / "evidence.json")
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output)["summary"], indent=2))
