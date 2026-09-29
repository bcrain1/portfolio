"""Initialize or inspect a local deterministic demo dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from service import DataService, ProposalInput, ReviewInput


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "runtime" / "data",
        help="Local service data directory (default: runtime/data)",
    )
    args = parser.parse_args()
    target = args.data_dir.resolve()
    if target.exists() and any(target.iterdir()):
        parser.error(f"refusing to overwrite non-empty data directory: {target}")

    service = DataService(target)
    initial = service.state()
    sample_request = {
        "operation": "update",
        "inspection_id": "INSP-1001",
        "expected_revision": 1,
        "values": {"reading": 2.7},
        "reason": "Fictional calibration follow-up",
    }
    proposal, _ = service.create_proposal(
        ProposalInput.model_validate(sample_request), "analyst", "demo-proposal-1"
    )
    approved, _ = service.review_proposal(
        proposal["id"],
        "approve",
        ReviewInput(reason="Synthetic reviewer acceptance"),
        "reviewer",
        "demo-approval-1",
    )
    migrations = []
    for action in ("expand", "backfill", "contract"):
        response, _ = service.migrate(action, "admin", f"demo-migration-{action}")
        migrations.append(response)
    final = service.state()
    original_snapshot = service.read_snapshot(initial["current_snapshot"])
    evidence = {
        "scope": "fictional-equipment-inspections-only",
        "data_dir": str(service.data_dir),
        "sample_input": sample_request,
        "proposal_id": proposal["id"],
        "approval_snapshot": approved["snapshot_id"],
        "migration_phases": [item["schema_phase"] for item in migrations],
        "initial": {
            "schema_phase": initial["schema_phase"],
            "record_count": len(initial["records"]),
            "INSP-1001_reading": next(
                row["reading"] for row in initial["records"] if row["inspection_id"] == "INSP-1001"
            ),
        },
        "final": {
            "schema_phase": final["schema_phase"],
            "record_count": len(final["records"]),
            "INSP-1001_reading": next(
                row["reading"] for row in final["records"] if row["inspection_id"] == "INSP-1001"
            ),
            "snapshot_count": len(service.snapshots()),
        },
        "invariants": {
            "historical_snapshot_unchanged": next(
                row["reading"]
                for row in original_snapshot["records"]
                if row["inspection_id"] == "INSP-1001"
            )
            == 2.4,
            "record_count_preserved": len(initial["records"]) == len(final["records"]),
            "migration_order_complete": final["schema_phase"] == "contracted",
        },
        "reproducibility_note": (
            "Semantic values and count invariants are deterministic; snapshot IDs, timestamps, "
            "and SQLite/Parquet bytes intentionally vary by run."
        ),
    }
    evidence_path = target / "demo_evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
