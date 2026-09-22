"""Reproducible synthetic product analytics. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
AS_OF = datetime(2026, 8, 29, tzinfo=UTC)
KINDS = {"exposure", "play", "heartbeat", "playback_error"}


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def epoch(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return int(parsed.timestamp())


def generate(seed=41896, size=1600):
    """Known zero causal effect: return is drawn only from PRE-index activity tier.

    Exposure depends strongly on that tier. These are deliberately simulated
    propensities, not estimates of any streaming service's audience.
    """
    rng = random.Random(seed)
    members, events = [], []

    def event(uid, when, kind, content, device="tv", seconds=0):
        delay = rng.choice([5, 20, 60, 300, 3600, 86400, 172800])
        events.append(dict(event_id=f"e{len(events):07}", member_id=uid,
                           event_at=iso(when), received_at=iso(when + timedelta(seconds=delay)),
                           event_type=kind, content_type=content, device=device,
                           watched_seconds=seconds))

    def viewing(uid, when, content):
        device = rng.choice(["tv", "mobile", "web"])
        event(uid, when, "play", content, device)
        if rng.random() < .08:
            event(uid, when + timedelta(seconds=3), "playback_error", content, device)
        # No-heartbeat sessions demonstrate why playback starts != measured watch time.
        minutes = rng.randint(2, 24)
        for minute in range(1, minutes + 1):
            if rng.random() > .12:
                event(uid, when + timedelta(minutes=minute), "heartbeat", content, device, 60)

    for i in range(size):
        uid = f"member_{i:05}"
        high = i % 2 == 0
        index = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=rng.randrange(28), hours=rng.randrange(24))
        members.append(dict(member_id=uid, eligible_at=iso(index),
                            pre_period_active_days=8 if high else 2))
        exposed = rng.random() < (.86 if high else .28)
        returned = rng.random() < (.74 if high else .27)
        if exposed:
            event(uid, index + timedelta(seconds=10), "exposure", "live")
            if rng.random() < .69:
                viewing(uid, index + timedelta(minutes=2), "live")
        elif rng.random() < .55:
            viewing(uid, index + timedelta(minutes=2), "on_demand")
        if returned:
            viewing(uid, index + timedelta(days=rng.randint(2, 6), hours=1), "on_demand")
        # Separate long-horizon activity must not enter the seven-day numerator.
        if rng.random() < .15:
            viewing(uid, index + timedelta(days=9), "on_demand")

    # Identical transport retries, conflict, bad member, bad clock, bad payload.
    events.extend(dict(e) for e in events[::83])
    conflict = dict(events[20]); conflict["content_type"] = "on_demand" if conflict["content_type"] == "live" else "live"
    events.append(conflict)
    for changes in [dict(event_id="bad_member", member_id="unknown"),
                    dict(event_id="bad_clock", event_at="2026-08-01T00:00:00"),
                    dict(event_id="bad_seconds", watched_seconds=-10)]:
        bad = dict(events[30]); bad.update(changes); events.append(bad)
    rng.shuffle(events)  # event-time processing must survive arrival-order changes
    return members, events


def clean(members, events, as_of):
    """Reject conflicts before choosing an idempotent representative, then apply as-of."""
    member_ids = {m["member_id"] for m in members}
    grouped = defaultdict(list)
    reasons = Counter()
    for e in events:
        # Future deliveries must not affect a historical snapshot, even if they
        # conflict with a previously received payload for the same event ID.
        try:
            receipt = epoch(e["received_at"])
        except (KeyError, ValueError, TypeError):
            reasons["invalid_rows"] += 1
            continue
        if receipt > as_of:
            reasons["unavailable_delivery_rows"] += 1
            continue
        if not isinstance(e.get("event_id"), str) or not e["event_id"]:
            reasons["missing_event_id"] += 1
        else:
            grouped[e["event_id"]].append(e)
    output = []
    for key in sorted(grouped):
        rows = grouped[key]
        # received_at is transport metadata; the same payload can arrive more than once.
        payloads = {json.dumps({k: v for k, v in e.items() if k != "received_at"}, sort_keys=True) for e in rows}
        if len(payloads) != 1:
            reasons["conflicting_id_rows"] += len(rows)
            continue
        try:
            e = dict(min(rows, key=lambda row: epoch(row["received_at"])))
            event_s, received_s = epoch(e["event_at"]), epoch(e["received_at"])
            if e["member_id"] not in member_ids:
                raise ValueError("unknown_member")
            if e["event_type"] not in KINDS or e["content_type"] not in {"live", "on_demand"} or e["device"] not in {"tv", "mobile", "web"}:
                raise ValueError("invalid_dimension")
            seconds = e["watched_seconds"]
            if type(seconds) is not int or not 0 <= seconds <= 60 or (e["event_type"] != "heartbeat" and seconds != 0):
                raise ValueError("invalid_watch_seconds")
            if received_s < event_s:
                raise ValueError("received_before_event")
        except (ValueError, TypeError, KeyError):
            reasons["invalid_rows"] += len(rows)
            continue
        reasons["identical_duplicate_rows"] += len(rows) - 1
        e.update(event_s=event_s, received_s=received_s)
        output.append(e)
    reasons["accepted_unique_events"] = len(output)
    reasons["raw_rows"] = len(events)
    return output, dict(reasons)


def warehouse(members, events, as_of):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript((ROOT / "sql/01_schema.sql").read_text())
    db.executemany("INSERT INTO members VALUES(?,?,?)", [(m["member_id"], epoch(m["eligible_at"]), m["pre_period_active_days"]) for m in members])
    db.execute("INSERT INTO settings VALUES(?)", (as_of,))
    keys = ("event_id", "member_id", "event_s", "received_s", "event_type", "content_type", "device", "watched_seconds")
    db.executemany("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)", [tuple(e[k] for k in keys) for e in events])
    db.executescript((ROOT / "sql/02_sessions.sql").read_text())
    db.executescript((ROOT / "sql/03_member_metrics.sql").read_text())
    return db


def wilson(successes, n):
    if not n:
        return None
    z = 1.95996398454
    p = successes / n
    center = (p + z*z/(2*n)) / (1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0, center-half), min(1, center+half)]


def compare(rows):
    mature = [r for r in rows if r["mature"]]
    groups = {}
    for exposed in [0, 1]:
        subset = [r for r in mature if r["exposed"] == exposed]
        count = sum(r["returned"] for r in subset)
        groups[str(exposed)] = dict(n=len(subset), returned=count, rate=count/len(subset) if subset else None,
                                    ci95=wilson(count, len(subset)))
    strata = []
    standardized = {"0": 0., "1": 0.}
    supported = bool(mature)
    for tier in ["frequent", "occasional"]:
        base = [r for r in mature if r["baseline_tier"] == tier]
        weight = len(base)/len(mature) if mature else 0
        cell = dict(tier=tier, weight=weight)
        for exposed in [0, 1]:
            sample = [r for r in base if r["exposed"] == exposed]
            count = sum(r["returned"] for r in sample)
            cell[str(exposed)] = dict(n=len(sample), returned=count, rate=count/len(sample) if sample else None)
            if weight and not sample:
                supported = False
            elif sample:
                standardized[str(exposed)] += weight*count/len(sample)
        strata.append(cell)
    return dict(groups=groups, strata=strata, mature_n=len(mature),
                excluded_immature=len(rows)-len(mature),
                standardized=standardized if supported else None,
                standardized_gap=(standardized["1"]-standardized["0"]) if supported else None)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def build(output, seed=41896, size=1600):
    output.mkdir(parents=True, exist_ok=True)
    members, raw = generate(seed, size)
    accepted, quality = clean(members, raw, int(AS_OF.timestamp()))
    db = warehouse(members, accepted, int(AS_OF.timestamp()))
    rows = [dict(r) for r in db.execute("SELECT * FROM member_metrics ORDER BY member_id")]
    result = compare(rows)
    quality["late_over_24h_accepted"] = sum(e["received_s"]-e["event_s"] > 86400 for e in accepted)
    quality["play_sessions_without_heartbeat"] = db.execute("SELECT count(*) FROM sessions WHERE plays>0 AND heartbeats=0").fetchone()[0]
    result.update(quality=quality, seed=seed, members=len(members), as_of=iso(AS_OF), synthetic=True)
    for name, data in [("members.csv", members), ("raw_events.csv", raw), ("member_metrics.csv", rows)]:
        write_csv(output/name, data)
    write_csv(output/"sessions.csv", [dict(r) for r in db.execute("SELECT * FROM sessions ORDER BY member_id,device,session_number")])
    with sqlite3.connect(output/"analytics.sqlite3") as target:
        db.backup(target)
    db.close()
    (output/"results.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    dashboard = (ROOT/"dashboard.html").read_text(encoding="utf-8")
    payload = json.dumps(dict(rows=rows, result=result), separators=(",", ":")).replace("<", "\\u003c")
    (output/"dashboard.html").write_text(dashboard.replace("/*DATA*/null", payload), encoding="utf-8")
    (output/"FINDINGS.md").write_text(findings(result), encoding="utf-8")
    generated = ["members.csv", "raw_events.csv", "member_metrics.csv", "sessions.csv", "analytics.sqlite3", "results.json", "dashboard.html", "FINDINGS.md"]
    manifest = {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in sorted(generated)}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return result


def findings(r):
    a, b = r["groups"]["1"], r["groups"]["0"]
    gap = a["rate"]-b["rate"] if a["rate"] is not None and b["rate"] is not None else None
    fmt = lambda x: f"{x*100:.1f}%" if x is not None else "not estimable"
    return f"""# Measurement decision memo

Independent synthetic demonstration; no Netflix or employer data. Seed {r['seed']}.
Snapshot: {r['as_of']}. This is an illustrative result, not a business finding.

## Decision
Do not infer an incremental retention benefit from the raw comparison. Validate
instrumentation and exposure logging, then design a randomized exposure study
before making a causal claim or using this result to justify a rollout.

## Evidence
- Eligible members: {r['members']}; seven-day event-time-mature cohorts: {r['mature_n']}.
- Excluded from ALL displayed member rates due to incomplete follow-up: {r['excluded_immature']}.
- Exposed return rate: {fmt(a['rate'])} ({a['returned']}/{a['n']}).
- Unexposed return rate: {fmt(b['rate'])} ({b['returned']}/{b['n']}).
- Raw difference: {gap*100:.1f} percentage points.
- Difference standardized to pooled PRE-index activity mix: {r['standardized_gap']*100:.1f} percentage points.

The simulator deliberately assigns exposure more often to frequent viewers.
Return probability depends on baseline activity, with no causal exposure effect.
Standardization demonstrates this measured confounder; it does not prove causal
identification in real data or eliminate unmeasured selection bias.

## Measurement cautions
Eligibility is indexed before exposure. Exposure is within the first hour;
initial engagement is the first 24 hours. Return means a new playback start
strictly after 24 hours and at or before 168 hours, anchored to eligibility for
BOTH cohorts. A playback start is not proof of completed viewing or satisfaction.
Observed watch time sums unique valid heartbeat seconds; missing telemetry can
undercount it. A 7-day event-time horizon is required, but late-arriving telemetry
can still revise a mature cohort. Reprocess new snapshots and test a 48-hour
arrival buffer before treating recent rates as stable.

Wilson intervals describe sampling uncertainty under an independent-member
binomial approximation; they do not correct bias. This is not an A/B test.
No p-value, causal lift, Netflix benchmark, or production-scale claim is made.

## Next analysis
Track play errors, no-heartbeat sessions, and ingestion latency alongside adoption.
Measure content substitution and satisfaction separately; return alone is not
enough to define value. Randomize exposure at member level with a prospectively
chosen primary metric, sample-size calculation and guardrails. That experiment
is a proposal, not an implemented or completed study.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT/"output")
    parser.add_argument("--seed", type=int, default=41896)
    parser.add_argument("--members", type=int, default=1600)
    args = parser.parse_args()
    if args.members < 100:
        parser.error("at least 100 members required for the demo")
    print(json.dumps(build(args.output, args.seed, args.members), indent=2))
