from __future__ import annotations

import concurrent.futures
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import create_app
from service import DataService, ProposalInput, ReviewInput, ServiceError, file_sha256


ANALYST = {"X-Demo-User": "analyst"}
REVIEWER = {"X-Demo-User": "reviewer"}
ADMIN = {"X-Demo-User": "admin"}


class GovernedServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.app = create_app(self.data_dir)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    @staticmethod
    def proposal_body(
        *,
        inspection_id: str = "INSP-1001",
        expected_revision: int = 1,
        reading: float = 2.7,
    ) -> dict:
        return {
            "operation": "update",
            "inspection_id": inspection_id,
            "expected_revision": expected_revision,
            "values": {"reading": reading},
            "reason": "Synthetic follow-up inspection",
        }

    def propose(self, body: dict | None = None, key: str = "proposal-1") -> dict:
        response = self.client.post(
            "/api/proposals",
            json=body or self.proposal_body(),
            headers={**ANALYST, "Idempotency-Key": key},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def approve(self, proposal_id: str, key: str = "approval-1") -> dict:
        response = self.client.post(
            f"/api/proposals/{proposal_id}/approve",
            json={"reason": "Independent synthetic review"},
            headers={**REVIEWER, "Idempotency-Key": key},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def migrate(self, action: str, key: str | None = None) -> dict:
        response = self.client.post(
            f"/api/migrations/{action}",
            json={},
            headers={**ADMIN, "Idempotency-Key": key or f"migration-{action}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_seed_is_typed_partitioned_and_manifest_verified(self) -> None:
        state = self.client.get("/api/state").json()
        self.assertEqual(state["schema_phase"], "legacy")
        self.assertEqual(len(state["records"]), 4)
        self.assertIsInstance(state["records"][0]["reading"], float)
        self.assertIsInstance(state["records"][0]["revision"], int)
        self.assertIsInstance(state["records"][0]["deleted"], bool)

        snapshot = self.client.get(f"/api/snapshots/{state['current_snapshot']}")
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        publication = snapshot.json()
        self.assertEqual(publication["manifest"]["row_count"], 4)
        self.assertEqual(sum(f["row_count"] for f in publication["manifest"]["files"]), 4)
        self.assertTrue(
            all(f["path"].startswith("observed_date=") for f in publication["manifest"]["files"])
        )

    def test_role_checks_run_before_idempotency_replay(self) -> None:
        body = self.proposal_body()
        proposal = self.propose(body, "role-first")
        replay_without_role = self.client.post(
            "/api/proposals",
            json=body,
            headers={"Idempotency-Key": "role-first"},
        )
        self.assertEqual(replay_without_role.status_code, 403)
        unknown = self.client.post(
            "/api/proposals",
            json=body,
            headers={"X-Demo-User": "intruder", "Idempotency-Key": "role-first"},
        )
        self.assertEqual(unknown.status_code, 401)
        replay = self.client.post(
            "/api/proposals", json=body, headers={**ANALYST, "Idempotency-Key": "role-first"}
        )
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.json()["id"], proposal["id"])

    def test_invalid_operations_are_rejected(self) -> None:
        missing_key = self.client.post("/api/proposals", json=self.proposal_body(), headers=ANALYST)
        self.assertEqual(missing_key.status_code, 400)
        unauthorized = self.client.post(
            "/api/proposals",
            json=self.proposal_body(),
            headers={"Idempotency-Key": "x"},
        )
        self.assertEqual(unauthorized.status_code, 403)

        cases = [
            {**self.proposal_body(), "undeclared": "field"},
            {**self.proposal_body(), "values": {"reading": True}},
            {
                "operation": "update",
                "inspection_id": "INSP-1001",
                "expected_revision": 1,
                "values": {"reading": None},
                "reason": "Null clear is invalid",
            },
            {
                "operation": "create",
                "inspection_id": "INSP-NEW",
                "expected_revision": 0,
                "values": {
                    "equipment_id": "PUMP-X",
                    "observed_date": "2026-02-30",
                    "metric": "pressure",
                    "reading": 3.0,
                    "unit": "bar",
                },
                "reason": "Impossible date",
            },
            {
                "operation": "delete",
                "inspection_id": "INSP-1001",
                "expected_revision": 1,
                "values": {"reading": 1.0},
                "reason": "Delete must not carry values",
            },
        ]
        for index, body in enumerate(cases):
            with self.subTest(index=index):
                response = self.client.post(
                    "/api/proposals",
                    json=body,
                    headers={**ANALYST, "Idempotency-Key": f"invalid-{index}"},
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("detail", response.json())

        with self.assertRaises(ValidationError):
            ProposalInput.model_validate({**self.proposal_body(), "values": {"reading": math.nan}})
        self.assertEqual(self.client.get("/api/records?client_version=2").status_code, 409)
        self.assertEqual(self.client.get("/api/records?client_version=3").status_code, 422)

    def test_idempotency_conflict_and_replay_after_restart(self) -> None:
        body = self.proposal_body()
        first = self.propose(body, "durable-key")
        restarted = TestClient(create_app(self.data_dir))
        try:
            replay = restarted.post(
                "/api/proposals",
                json=body,
                headers={**ANALYST, "Idempotency-Key": "durable-key"},
            )
            self.assertEqual(replay.status_code, 201)
            self.assertEqual(replay.json(), first)
            changed = restarted.post(
                "/api/proposals",
                json={**body, "reason": "Changed payload"},
                headers={**ANALYST, "Idempotency-Key": "durable-key"},
            )
            self.assertEqual(changed.status_code, 409)
        finally:
            restarted.close()

    def test_approval_replay_after_restart_is_exactly_once(self) -> None:
        proposal = self.propose()
        approved = self.approve(proposal["id"], "approve-durable")
        audit_count = len(self.client.get("/api/audit").json()["audit"])
        snapshot_count = len(self.client.get("/api/snapshots").json()["snapshots"])
        restarted = TestClient(create_app(self.data_dir))
        try:
            replay = restarted.post(
                f"/api/proposals/{proposal['id']}/approve",
                json={"reason": "Independent synthetic review"},
                headers={**REVIEWER, "Idempotency-Key": "approve-durable"},
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.json(), approved)
            self.assertEqual(len(restarted.get("/api/audit").json()["audit"]), audit_count)
            self.assertEqual(
                len(restarted.get("/api/snapshots").json()["snapshots"]), snapshot_count
            )
        finally:
            restarted.close()

    def test_review_update_and_soft_delete_are_audited(self) -> None:
        updated = self.approve(self.propose()["id"])
        self.assertEqual(updated["status"], "APPROVED")
        row = next(
            item
            for item in self.client.get("/api/state").json()["records"]
            if item["inspection_id"] == "INSP-1001"
        )
        self.assertEqual(row["revision"], 2)
        self.assertEqual(row["reading"], 2.7)

        delete_body = {
            "operation": "delete",
            "inspection_id": "INSP-1001",
            "expected_revision": 2,
            "values": {},
            "reason": "Synthetic retirement",
        }
        deleted = self.approve(self.propose(delete_body, "delete-proposal")["id"], "delete-approval")
        self.assertEqual(deleted["status"], "APPROVED")
        ids = {row["inspection_id"] for row in self.client.get("/api/state").json()["records"]}
        self.assertNotIn("INSP-1001", ids)
        event = self.client.get("/api/audit").json()["audit"][-1]
        self.assertEqual(event["event_type"], "RECORD_DELETE")
        self.assertTrue(event["details"]["after"]["deleted"])

        recreate = {
            "operation": "create",
            "inspection_id": "INSP-1001",
            "expected_revision": 0,
            "values": {
                "equipment_id": "PUMP-X",
                "observed_date": "2026-09-23",
                "metric": "pressure",
                "reading": 5.0,
                "unit": "bar",
            },
            "reason": "Must not resurrect a governed ID",
        }
        response = self.client.post(
            "/api/proposals",
            json=recreate,
            headers={**ANALYST, "Idempotency-Key": "no-resurrection"},
        )
        self.assertEqual(response.status_code, 409)

    def test_rejection_is_audited_without_dataset_publication(self) -> None:
        proposal = self.propose()
        before = self.client.get("/api/state").json()["current_snapshot"]
        before_count = len(self.client.get("/api/snapshots").json()["snapshots"])
        response = self.client.post(
            f"/api/proposals/{proposal['id']}/reject",
            json={"reason": "Insufficient synthetic rationale"},
            headers={**REVIEWER, "Idempotency-Key": "reject-1"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "REJECTED")
        self.assertEqual(self.client.get("/api/state").json()["current_snapshot"], before)
        self.assertEqual(len(self.client.get("/api/snapshots").json()["snapshots"]), before_count)
        self.assertEqual(
            self.client.get("/api/audit").json()["audit"][-1]["event_type"],
            "PROPOSAL_REJECTED",
        )

    def test_two_stale_edits_serialize_and_only_one_approves(self) -> None:
        first = self.propose(self.proposal_body(reading=2.8), "concurrent-proposal-a")
        second = self.propose(self.proposal_body(reading=2.9), "concurrent-proposal-b")
        service: DataService = self.app.state.service

        def approve_direct(proposal_id: str, key: str) -> int:
            try:
                service.review_proposal(
                    proposal_id,
                    "approve",
                    ReviewInput(reason="Concurrent reviewer"),
                    "reviewer",
                    key,
                )
                return 200
            except ServiceError as exc:
                return exc.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda pair: approve_direct(*pair),
                    [(first["id"], "concurrent-a"), (second["id"], "concurrent-b")],
                )
            )
        self.assertEqual(sorted(results), [200, 409])
        proposals = {item["id"]: item for item in service.proposals()}
        self.assertEqual(
            sorted([proposals[first["id"]]["status"], proposals[second["id"]]["status"]]),
            ["APPROVED", "PENDING"],
        )
        self.assertEqual(len(service.snapshots()), 2)

    def test_failure_before_publication_rolls_back_everything(self) -> None:
        proposal = self.propose()
        service: DataService = self.app.state.service
        before_state = service.state()
        before_audit = len(service.audit())
        before_dirs = {path.name for path in service.snapshots_dir.iterdir()}

        def fail(label: str) -> None:
            if label == "before_publication":
                raise RuntimeError("injected before publication")

        service.fault_injector = fail
        with self.assertRaisesRegex(RuntimeError, "injected before publication"):
            service.review_proposal(
                proposal["id"],
                "approve",
                ReviewInput(reason="Will fault"),
                "reviewer",
                "fault-before",
            )
        self.assertEqual(service.state(), before_state)
        self.assertEqual(len(service.audit()), before_audit)
        self.assertEqual({path.name for path in service.snapshots_dir.iterdir()}, before_dirs)
        self.assertEqual(service.proposals()[0]["status"], "PENDING")
        service.fault_injector = None
        response, _ = service.review_proposal(
            proposal["id"],
            "approve",
            ReviewInput(reason="Will fault"),
            "reviewer",
            "fault-before",
        )
        self.assertEqual(response["status"], "APPROVED")

    def test_failure_after_files_leaves_unpublished_unreadable_orphan(self) -> None:
        proposal = self.propose()
        service: DataService = self.app.state.service
        before_pointer = service.state()["current_snapshot"]
        before_published = {item["id"] for item in service.snapshots()}
        before_dirs = {path.name for path in service.snapshots_dir.iterdir()}

        def fail(label: str) -> None:
            if label == "after_files_before_commit":
                raise RuntimeError("injected after files")

        service.fault_injector = fail
        with self.assertRaisesRegex(RuntimeError, "injected after files"):
            service.review_proposal(
                proposal["id"],
                "approve",
                ReviewInput(reason="Will leave orphan"),
                "reviewer",
                "fault-after",
            )
        after_dirs = {path.name for path in service.snapshots_dir.iterdir()}
        orphan_ids = after_dirs - before_dirs
        self.assertEqual(len(orphan_ids), 1)
        orphan_id = next(iter(orphan_ids))
        self.assertEqual(service.state()["current_snapshot"], before_pointer)
        self.assertEqual({item["id"] for item in service.snapshots()}, before_published)
        self.assertEqual(service.proposals()[0]["status"], "PENDING")
        self.assertEqual(self.client.get(f"/api/snapshots/{orphan_id}").status_code, 404)
        service.fault_injector = None
        response, _ = service.review_proposal(
            proposal["id"],
            "approve",
            ReviewInput(reason="Will leave orphan"),
            "reviewer",
            "fault-after",
        )
        self.assertNotEqual(response["snapshot_id"], orphan_id)
        self.assertTrue((service.snapshots_dir / orphan_id).exists())

    def test_historical_read_remains_immutable(self) -> None:
        original = self.client.get("/api/state").json()["current_snapshot"]
        self.approve(self.propose()["id"])
        current = self.client.get("/api/state").json()["current_snapshot"]
        self.assertNotEqual(original, current)
        old_rows = self.client.get(f"/api/snapshots/{original}").json()["records"]
        new_rows = self.client.get(f"/api/snapshots/{current}").json()["records"]
        old = next(row for row in old_rows if row["inspection_id"] == "INSP-1001")
        new = next(row for row in new_rows if row["inspection_id"] == "INSP-1001")
        self.assertEqual(old["reading"], 2.4)
        self.assertEqual(new["reading"], 2.7)

    def test_manifest_and_data_tampering_are_detected(self) -> None:
        service: DataService = self.app.state.service
        snapshot_id = service.state()["current_snapshot"]
        snapshot_dir = service.snapshots_dir / snapshot_id
        manifest_path = snapshot_dir / "manifest.json"
        original_manifest = manifest_path.read_bytes()
        manifest = json.loads(original_manifest)
        manifest["row_count"] += 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(self.client.get(f"/api/snapshots/{snapshot_id}").status_code, 409)
        self.assertEqual(self.client.get("/api/state").status_code, 409)

        manifest_path.write_bytes(original_manifest)
        data_path = snapshot_dir / Path(manifest["files"][0]["path"])
        original_data = data_path.read_bytes()
        data_path.write_bytes(original_data + b"tamper")
        self.assertEqual(self.client.get(f"/api/snapshots/{snapshot_id}").status_code, 409)

    def test_expand_backfill_contract_preserve_values_and_retire_field(self) -> None:
        with closing(sqlite3.connect(self.app.state.service.db_path)) as connection:
            legacy_columns = {row[1] for row in connection.execute("PRAGMA table_info(records)")}
        self.assertIn("reading", legacy_columns)
        self.assertNotIn("measurement_value", legacy_columns)
        self.assertEqual(
            self.client.post(
                "/api/migrations/backfill",
                json={},
                headers={**ADMIN, "Idempotency-Key": "wrong-order"},
            ).status_code,
            409,
        )
        legacy = self.client.get("/api/records?client_version=1").json()["records"]
        legacy_values = {row["inspection_id"]: row["reading"] for row in legacy}

        self.migrate("expand")
        with closing(sqlite3.connect(self.app.state.service.db_path)) as connection:
            expanded_columns = {row[1] for row in connection.execute("PRAGMA table_info(records)")}
        self.assertIn("reading", expanded_columns)
        self.assertIn("measurement_value", expanded_columns)
        expanded_v2 = self.client.get("/api/records?client_version=2")
        self.assertEqual(expanded_v2.status_code, 200, expanded_v2.text)
        self.assertEqual(
            {row["inspection_id"]: row["measurement_value"] for row in expanded_v2.json()["records"]},
            legacy_values,
        )

        # A coexistence write dual-writes reading and measurement_value.
        proposal = self.propose(self.proposal_body(reading=3.1), "expanded-update")
        self.approve(proposal["id"], "expanded-approval")
        self.migrate("backfill")
        backfilled = self.client.get("/api/state").json()
        for row in backfilled["records"]:
            self.assertEqual(row["reading"], row["measurement_value"])
        pre_contract = {
            row["inspection_id"]: row["reading"]
            for row in self.client.get("/api/records?client_version=1").json()["records"]
        }

        contracted = self.migrate("contract")
        self.assertEqual(contracted["schema_phase"], "contracted")
        self.assertEqual(self.client.get("/api/records?client_version=1").status_code, 410)
        v2 = self.client.get("/api/records?client_version=2")
        self.assertEqual(v2.status_code, 200, v2.text)
        self.assertEqual(
            {row["inspection_id"]: row["measurement_value"] for row in v2.json()["records"]},
            pre_contract,
        )
        state = self.client.get("/api/state").json()
        self.assertTrue(all("reading" in row for row in state["records"]))
        snapshot = self.client.get(f"/api/snapshots/{contracted['current_snapshot']}").json()
        self.assertTrue(all("reading" not in row for row in snapshot["records"]))
        self.assertTrue(all("measurement_value" in row for row in snapshot["records"]))
        with closing(sqlite3.connect(self.app.state.service.db_path)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(records)")}
        self.assertNotIn("reading", columns)
        self.assertIn("measurement_value", columns)

        # New writes remain valid after physical contract.
        current = next(row for row in state["records"] if row["inspection_id"] == "INSP-1002")
        post = self.propose(
            self.proposal_body(
                inspection_id="INSP-1002",
                expected_revision=current["revision"],
                reading=69.0,
            ),
            "post-contract-proposal",
        )
        self.approve(post["id"], "post-contract-approval")
        value = next(
            row["measurement_value"]
            for row in self.client.get("/api/records?client_version=2").json()["records"]
            if row["inspection_id"] == "INSP-1002"
        )
        self.assertEqual(value, 69.0)

    def test_migration_replay_survives_restart_without_new_snapshot(self) -> None:
        first = self.migrate("expand", "expand-replay")
        snapshot_count = len(self.app.state.service.snapshots())
        restarted = DataService(self.data_dir)
        replay, status = restarted.migrate("expand", "admin", "expand-replay")
        self.assertEqual(status, 200)
        self.assertEqual(replay, first)
        self.assertEqual(len(restarted.snapshots()), snapshot_count)

    def test_generate_demo_builds_fresh_semantic_evidence(self) -> None:
        target = self.data_dir / "generated-demo"
        command = [sys.executable, "-B", "generate_demo.py", "--data-dir", str(target)]
        result = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["migration_phases"], ["expanded", "backfilled", "contracted"])
        self.assertTrue(all(evidence["invariants"].values()))
        self.assertEqual(evidence["initial"]["record_count"], evidence["final"]["record_count"])
        self.assertEqual(
            json.loads((target / "demo_evidence.json").read_text(encoding="utf-8"))["final"],
            evidence["final"],
        )
        second = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("refusing to overwrite", second.stderr)


if __name__ == "__main__":
    unittest.main()
