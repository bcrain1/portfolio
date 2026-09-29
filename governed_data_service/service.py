"""Transactional core for the synthetic Governed Data Service demo.

SQLite is authoritative.  Parquet directories are immutable publications: a
writer creates and closes every file while holding ``BEGIN IMMEDIATE``, then
commits the SQLite record mutation and snapshot pointer together.  A crash can
leave an unreferenced directory, but readers only follow committed pointers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_PHASES = ("legacy", "expanded", "backfilled", "contracted")
SAFE_SNAPSHOT_ID = re.compile(r"^snap-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class InspectionValues(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    equipment_id: str | None = Field(default=None, min_length=1, max_length=64)
    observed_date: date | None = None
    metric: str | None = Field(default=None, min_length=1, max_length=64)
    reading: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    unit: str | None = Field(default=None, min_length=1, max_length=24)

    @field_validator("equipment_id", "metric")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is not None and not SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError("must use letters, digits, '.', '_' or '-'")
        return value

    @field_validator("reading", mode="before")
    @classmethod
    def reject_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("must be a number, not a boolean")
        return value

    @field_validator("reading")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("must be finite")
        return value


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    operation: Literal["create", "update", "delete"]
    inspection_id: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=0)
    values: InspectionValues
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("inspection_id")
    @classmethod
    def validate_inspection_id(cls, value: str) -> str:
        if not SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError("must use letters, digits, '.', '_' or '-'")
        return value

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "ProposalInput":
        supplied = self.values.model_fields_set
        all_fields = {"equipment_id", "observed_date", "metric", "reading", "unit"}
        if self.operation == "create":
            if self.expected_revision != 0:
                raise ValueError("create requires expected_revision=0")
            if supplied != all_fields or any(getattr(self.values, name) is None for name in all_fields):
                raise ValueError("create requires every value field")
        elif self.operation == "update":
            if self.expected_revision < 1:
                raise ValueError("update requires a positive expected_revision")
            if not supplied:
                raise ValueError("update requires at least one value field")
            if any(getattr(self.values, name) is None for name in supplied):
                raise ValueError("update fields cannot be null")
        else:
            if self.expected_revision < 1:
                raise ValueError("delete requires a positive expected_revision")
            if supplied:
                raise ValueError("delete requires empty values")
        return self


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=500)


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


SEED_ROWS = (
    ("INSP-1001", "PUMP-A17", "2026-09-20", "vibration", 2.4, "mm_s", 1, 0),
    ("INSP-1002", "FAN-B04", "2026-09-21", "temperature", 68.5, "deg_C", 1, 0),
    ("INSP-1003", "VALVE-C09", "2026-09-21", "pressure", 41.2, "bar", 1, 0),
    ("INSP-1004", "PUMP-A17", "2026-09-22", "temperature", 72.1, "deg_C", 1, 0),
)


class DataService:
    """SQLite journal and immutable Parquet publication manager."""

    def __init__(
        self,
        data_dir: str | os.PathLike[str],
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.db_path = self.data_dir / "governed.sqlite3"
        self.snapshots_dir = self.data_dir / "snapshots"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._local_lock = threading.RLock()
        self.fault_injector: Callable[[str], None] | None = None
        self._initialize()
        # Initialization itself is deliberately not fault injected. Tests can
        # fail later publications without making construction nondeterministic.
        self.fault_injector = fault_injector

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS metadata (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_phase TEXT NOT NULL,
                    current_snapshot TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS records (
                    inspection_id TEXT PRIMARY KEY,
                    equipment_id TEXT NOT NULL,
                    observed_date TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    reading REAL NOT NULL,
                    unit TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    inspection_id TEXT NOT NULL,
                    expected_revision INTEGER NOT NULL,
                    values_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    author TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewer TEXT,
                    review_reason TEXT,
                    review_snapshot_id TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    proposal_id TEXT,
                    inspection_id TEXT,
                    schema_phase TEXT NOT NULL,
                    snapshot_id TEXT,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    schema_phase TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency_receipts (
                    principal TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (principal, operation, idempotency_key)
                );
                """
            )

        # Serialize virgin seeding across processes/connections.
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO metadata(singleton,schema_phase,current_snapshot,updated_at) "
                "VALUES(1,'legacy',NULL,?)",
                (utc_now(),),
            )
            count = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            pointer = connection.execute(
                "SELECT current_snapshot FROM metadata WHERE singleton=1"
            ).fetchone()[0]
            if count == 0 and pointer is None:
                now = utc_now()
                connection.executemany(
                    "INSERT INTO records(inspection_id,equipment_id,observed_date,metric,reading,"
                    "unit,revision,deleted,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    [(*row[:5], row[5], row[6], row[7], now) for row in SEED_ROWS],
                )
                snapshot_id = self._new_snapshot_id()
                audit_id = connection.execute(
                    "INSERT INTO audit_events(event_type,actor,proposal_id,inspection_id,schema_phase,"
                    "snapshot_id,details_json,created_at) VALUES('SEED','system',NULL,NULL,'legacy',?,?,?)",
                    (snapshot_id, canonical_json({"records": len(SEED_ROWS), "fictional": True}), now),
                ).lastrowid
                self._publish_snapshot(connection, snapshot_id, "legacy", inject_faults=False)
                connection.execute(
                    "UPDATE metadata SET current_snapshot=?,updated_at=? WHERE singleton=1",
                    (snapshot_id, now),
                )
                connection.commit()
            else:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _trip(self, label: str) -> None:
        if self.fault_injector is not None:
            self.fault_injector(label)

    @staticmethod
    def _new_snapshot_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"snap-{stamp}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _new_proposal_id() -> str:
        return f"prop-{uuid.uuid4().hex[:16]}"

    def _idempotent_replay(
        self,
        connection: sqlite3.Connection,
        principal: str,
        operation: str,
        key: str,
        request_hash: str,
    ) -> tuple[dict[str, Any], int] | None:
        row = connection.execute(
            "SELECT request_hash,response_json,status_code FROM idempotency_receipts "
            "WHERE principal=? AND operation=? AND idempotency_key=?",
            (principal, operation, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise ServiceError(409, "idempotency key was already used with a different payload")
        return json.loads(row["response_json"]), int(row["status_code"])

    @staticmethod
    def _store_receipt(
        connection: sqlite3.Connection,
        principal: str,
        operation: str,
        key: str,
        request_hash: str,
        response: dict[str, Any],
        status_code: int,
    ) -> None:
        connection.execute(
            "INSERT INTO idempotency_receipts(principal,operation,idempotency_key,request_hash,"
            "response_json,status_code,created_at) VALUES(?,?,?,?,?,?,?)",
            (principal, operation, key, request_hash, canonical_json(response), status_code, utc_now()),
        )

    @staticmethod
    def _record_dict(row: sqlite3.Row, include_measurement: bool = True) -> dict[str, Any]:
        columns = set(row.keys())
        reading = row["reading"] if "reading" in columns else row["measurement_value"]
        result: dict[str, Any] = {
            "inspection_id": row["inspection_id"],
            "equipment_id": row["equipment_id"],
            "observed_date": row["observed_date"],
            "metric": row["metric"],
            # The canonical UI keeps a reading alias after the physical legacy
            # column is retired at contract.
            "reading": float(reading),
            "unit": row["unit"],
            "revision": int(row["revision"]),
            "deleted": bool(row["deleted"]),
        }
        if include_measurement and "measurement_value" in columns:
            value = row["measurement_value"]
            result["measurement_value"] = None if value is None else float(value)
        return result

    @staticmethod
    def _proposal_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "operation": row["operation"],
            "inspection_id": row["inspection_id"],
            "expected_revision": int(row["expected_revision"]),
            "values": json.loads(row["values_json"]),
            "reason": row["reason"],
            "author": row["author"],
            "status": row["status"],
            "created_at": row["created_at"],
            "reviewed_at": row["reviewed_at"],
            "reviewer": row["reviewer"],
            "review_reason": row["review_reason"],
            "snapshot_id": row["review_snapshot_id"],
        }

    def state(self) -> dict[str, Any]:
        phase, pointer, rows = self._current_published_rows()
        canonical: list[dict[str, Any]] = []
        for source in rows:
            item = dict(source)
            if "reading" not in item:
                item["reading"] = item["measurement_value"]
            canonical.append(item)
        canonical.sort(key=lambda item: item["inspection_id"])
        return {"schema_phase": phase, "current_snapshot": pointer, "records": canonical}

    def _current_published_rows(self) -> tuple[str, str, list[dict[str, Any]]]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            meta = connection.execute(
                "SELECT schema_phase,current_snapshot FROM metadata WHERE singleton=1"
            ).fetchone()
            phase = meta["schema_phase"]
            pointer = meta["current_snapshot"]
            connection.commit()
        if pointer is None:
            raise ServiceError(409, "no published snapshot is available")
        publication = self.read_snapshot(pointer)
        if publication["schema_phase"] != phase:
            raise ServiceError(409, "snapshot pointer and schema phase disagree")
        return phase, pointer, publication["records"]

    def records_for_client(self, client_version: int) -> list[dict[str, Any]]:
        phase, _pointer, rows = self._current_published_rows()
        if client_version == 1:
            if phase == "contracted":
                raise ServiceError(410, "client_version=1 was retired at schema contract")
            return [
                {
                    "inspection_id": row["inspection_id"],
                    "equipment_id": row["equipment_id"],
                    "observed_date": row["observed_date"],
                    "metric": row["metric"],
                    "reading": float(row["reading"]),
                    "unit": row["unit"],
                    "revision": int(row["revision"]),
                }
                for row in rows
            ]
        if client_version == 2:
            if phase == "legacy":
                raise ServiceError(409, "client_version=2 is available after schema expansion")
            return [
                {
                    "inspection_id": row["inspection_id"],
                    "equipment_id": row["equipment_id"],
                    "observed_date": row["observed_date"],
                    "metric": row["metric"],
                    # During expanded coexistence, untouched legacy rows have
                    # not been physically backfilled. The v2 compatibility
                    # view derives their value from reading so v2 is usable as
                    # soon as expansion completes.
                    "measurement_value": float(
                        row.get("measurement_value")
                        if row.get("measurement_value") is not None
                        else row["reading"]
                    ),
                    "unit": row["unit"],
                    "revision": int(row["revision"]),
                }
                for row in rows
            ]
        raise ServiceError(422, "client_version must be 1 or 2")

    def proposals(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM proposals ORDER BY created_at,id").fetchall()
        return [self._proposal_dict(row) for row in rows]

    def audit(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
        return [
            {
                "id": int(row["id"]),
                "event_type": row["event_type"],
                "actor": row["actor"],
                "proposal_id": row["proposal_id"],
                "inspection_id": row["inspection_id"],
                "schema_phase": row["schema_phase"],
                "snapshot_id": row["snapshot_id"],
                "details": json.loads(row["details_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def create_proposal(
        self, request: ProposalInput, principal: str, idempotency_key: str
    ) -> tuple[dict[str, Any], int]:
        body = request.model_dump(mode="json", exclude_none=False)
        digest = payload_hash(body)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._idempotent_replay(
                connection, principal, "create_proposal", idempotency_key, digest
            )
            if replay is not None:
                connection.commit()
                return replay
            current = connection.execute(
                "SELECT revision,deleted FROM records WHERE inspection_id=?",
                (request.inspection_id,),
            ).fetchone()
            if request.operation == "create":
                if current is not None:
                    raise ServiceError(409, "inspection_id already exists")
            else:
                if current is None or bool(current["deleted"]):
                    raise ServiceError(409, "inspection record is not active")
                if int(current["revision"]) != request.expected_revision:
                    raise ServiceError(409, "expected_revision does not match current revision")
            now = utc_now()
            proposal_id = self._new_proposal_id()
            values = request.values.model_dump(mode="json", exclude_unset=True)
            connection.execute(
                "INSERT INTO proposals(id,operation,inspection_id,expected_revision,values_json,reason,"
                "author,status,created_at) VALUES(?,?,?,?,?,?,?,'PENDING',?)",
                (
                    proposal_id,
                    request.operation,
                    request.inspection_id,
                    request.expected_revision,
                    canonical_json(values),
                    request.reason,
                    principal,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            response = self._proposal_dict(row)
            self._store_receipt(
                connection, principal, "create_proposal", idempotency_key, digest, response, 201
            )
            connection.commit()
            return response, 201
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def review_proposal(
        self,
        proposal_id: str,
        decision: Literal["approve", "reject"],
        request: ReviewInput,
        principal: str,
        idempotency_key: str,
    ) -> tuple[dict[str, Any], int]:
        operation_key = f"{decision}_proposal:{proposal_id}"
        body = request.model_dump(mode="json")
        digest = payload_hash(body)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._idempotent_replay(
                connection, principal, operation_key, idempotency_key, digest
            )
            if replay is not None:
                connection.commit()
                return replay
            proposal = connection.execute(
                "SELECT * FROM proposals WHERE id=?", (proposal_id,)
            ).fetchone()
            if proposal is None:
                raise ServiceError(404, "proposal not found")
            if proposal["status"] != "PENDING":
                raise ServiceError(409, "proposal has already been reviewed")
            if proposal["author"] == principal:
                raise ServiceError(403, "proposal authors cannot review their own proposals")

            now = utc_now()
            if decision == "reject":
                connection.execute(
                    "UPDATE proposals SET status='REJECTED',reviewed_at=?,reviewer=?,review_reason=? "
                    "WHERE id=?",
                    (now, principal, request.reason, proposal_id),
                )
                phase = connection.execute(
                    "SELECT schema_phase FROM metadata WHERE singleton=1"
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO audit_events(event_type,actor,proposal_id,inspection_id,schema_phase,"
                    "snapshot_id,details_json,created_at) VALUES('PROPOSAL_REJECTED',?,?,?,?,?,?,?)",
                    (
                        principal,
                        proposal_id,
                        proposal["inspection_id"],
                        phase,
                        None,
                        canonical_json({"reason": request.reason}),
                        now,
                    ),
                )
                row = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
                response = self._proposal_dict(row)
                self._store_receipt(
                    connection, principal, operation_key, idempotency_key, digest, response, 200
                )
                connection.commit()
                return response, 200

            phase = connection.execute(
                "SELECT schema_phase FROM metadata WHERE singleton=1"
            ).fetchone()[0]
            current = connection.execute(
                "SELECT * FROM records WHERE inspection_id=?", (proposal["inspection_id"],)
            ).fetchone()
            expected = int(proposal["expected_revision"])
            op = proposal["operation"]
            values = json.loads(proposal["values_json"])
            before = None if current is None else self._record_dict(current)
            if op == "create":
                if current is not None or expected != 0:
                    raise ServiceError(409, "proposal is stale: inspection_id already exists")
                if phase == "contracted":
                    connection.execute(
                        "INSERT INTO records(inspection_id,equipment_id,observed_date,metric,"
                        "measurement_value,unit,revision,deleted,updated_at) VALUES(?,?,?,?,?,?,1,0,?)",
                        (
                            proposal["inspection_id"], values["equipment_id"], values["observed_date"],
                            values["metric"], values["reading"], values["unit"], now,
                        ),
                    )
                elif phase == "legacy":
                    connection.execute(
                        "INSERT INTO records(inspection_id,equipment_id,observed_date,metric,reading,"
                        "unit,revision,deleted,updated_at) VALUES(?,?,?,?,?,?,1,0,?)",
                        (
                            proposal["inspection_id"], values["equipment_id"], values["observed_date"],
                            values["metric"], values["reading"], values["unit"], now,
                        ),
                    )
                else:
                    connection.execute(
                        "INSERT INTO records(inspection_id,equipment_id,observed_date,metric,reading,"
                        "measurement_value,unit,revision,deleted,updated_at) VALUES(?,?,?,?,?,?,?,?,0,?)",
                        (
                            proposal["inspection_id"], values["equipment_id"], values["observed_date"],
                            values["metric"], values["reading"], values["reading"], values["unit"], 1, now,
                        ),
                    )
            else:
                if current is None or bool(current["deleted"]) or int(current["revision"]) != expected:
                    raise ServiceError(409, "proposal is stale: record revision changed")
                new_revision = expected + 1
                if op == "delete":
                    connection.execute(
                        "UPDATE records SET revision=?,deleted=1,updated_at=? WHERE inspection_id=?",
                        (new_revision, now, proposal["inspection_id"]),
                    )
                else:
                    current_reading = (
                        current["reading"]
                        if "reading" in set(current.keys())
                        else current["measurement_value"]
                    )
                    merged = {
                        "equipment_id": current["equipment_id"],
                        "observed_date": current["observed_date"],
                        "metric": current["metric"],
                        "reading": float(current_reading),
                        "unit": current["unit"],
                    }
                    merged.update(values)
                    if phase == "contracted":
                        connection.execute(
                            "UPDATE records SET equipment_id=?,observed_date=?,metric=?,"
                            "measurement_value=?,unit=?,revision=?,updated_at=? WHERE inspection_id=?",
                            (
                                merged["equipment_id"], merged["observed_date"], merged["metric"],
                                merged["reading"], merged["unit"], new_revision, now,
                                proposal["inspection_id"],
                            ),
                        )
                    elif phase == "legacy":
                        connection.execute(
                            "UPDATE records SET equipment_id=?,observed_date=?,metric=?,reading=?,"
                            "unit=?,revision=?,updated_at=? WHERE inspection_id=?",
                            (
                                merged["equipment_id"], merged["observed_date"], merged["metric"],
                                merged["reading"], merged["unit"], new_revision, now,
                                proposal["inspection_id"],
                            ),
                        )
                    else:
                        connection.execute(
                            "UPDATE records SET equipment_id=?,observed_date=?,metric=?,reading=?,"
                            "measurement_value=?,unit=?,revision=?,updated_at=? WHERE inspection_id=?",
                            (
                                merged["equipment_id"], merged["observed_date"], merged["metric"],
                                merged["reading"], merged["reading"], merged["unit"], new_revision, now,
                                proposal["inspection_id"],
                            ),
                        )

            after_row = connection.execute(
                "SELECT * FROM records WHERE inspection_id=?", (proposal["inspection_id"],)
            ).fetchone()
            after = self._record_dict(after_row)
            snapshot_id = self._new_snapshot_id()
            connection.execute(
                "UPDATE proposals SET status='APPROVED',reviewed_at=?,reviewer=?,review_reason=?,"
                "review_snapshot_id=? WHERE id=?",
                (now, principal, request.reason, snapshot_id, proposal_id),
            )
            audit_id = connection.execute(
                "INSERT INTO audit_events(event_type,actor,proposal_id,inspection_id,schema_phase,"
                "snapshot_id,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    f"RECORD_{op.upper()}", principal, proposal_id, proposal["inspection_id"], phase,
                    snapshot_id,
                    canonical_json({"before": before, "after": after, "review_reason": request.reason}),
                    now,
                ),
            ).lastrowid
            self._publish_snapshot(connection, snapshot_id, phase, inject_faults=True)
            connection.execute(
                "UPDATE metadata SET current_snapshot=?,updated_at=? WHERE singleton=1",
                (snapshot_id, now),
            )
            row = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            response = self._proposal_dict(row)
            response["audit_id"] = int(audit_id)
            self._store_receipt(
                connection, principal, operation_key, idempotency_key, digest, response, 200
            )
            connection.commit()
            return response, 200
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(
        self, action: Literal["expand", "backfill", "contract"], principal: str, idempotency_key: str
    ) -> tuple[dict[str, Any], int]:
        digest = payload_hash({})
        operation_key = f"migration:{action}"
        expected = {"expand": "legacy", "backfill": "expanded", "contract": "backfilled"}
        target = {"expand": "expanded", "backfill": "backfilled", "contract": "contracted"}
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._idempotent_replay(
                connection, principal, operation_key, idempotency_key, digest
            )
            if replay is not None:
                connection.commit()
                return replay
            phase = connection.execute(
                "SELECT schema_phase FROM metadata WHERE singleton=1"
            ).fetchone()[0]
            if phase != expected[action]:
                raise ServiceError(409, f"migration {action} requires schema phase {expected[action]}")
            if action == "expand":
                connection.execute("ALTER TABLE records ADD COLUMN measurement_value REAL")
            if action == "backfill":
                connection.execute("UPDATE records SET measurement_value=reading")
            if action == "contract":
                invalid = connection.execute(
                    "SELECT COUNT(*) FROM records WHERE measurement_value IS NULL "
                    "OR measurement_value != reading"
                ).fetchone()[0]
                if invalid:
                    raise ServiceError(409, "contract invariants failed: backfill values differ")
                # Rebuild the authoritative table so the legacy stored field is
                # physically retired. /api/state derives its required `reading`
                # UI alias from measurement_value after this point.
                connection.execute(
                    """CREATE TABLE records_v2 (
                        inspection_id TEXT PRIMARY KEY,
                        equipment_id TEXT NOT NULL,
                        observed_date TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        measurement_value REAL NOT NULL,
                        unit TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision >= 1),
                        deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
                        updated_at TEXT NOT NULL
                    )"""
                )
                connection.execute(
                    """INSERT INTO records_v2(
                        inspection_id,equipment_id,observed_date,metric,measurement_value,
                        unit,revision,deleted,updated_at
                    )
                    SELECT inspection_id,equipment_id,observed_date,metric,measurement_value,
                           unit,revision,deleted,updated_at
                    FROM records"""
                )
                connection.execute("DROP TABLE records")
                connection.execute("ALTER TABLE records_v2 RENAME TO records")
            next_phase = target[action]
            now = utc_now()
            connection.execute(
                "UPDATE metadata SET schema_phase=?,updated_at=? WHERE singleton=1",
                (next_phase, now),
            )
            snapshot_id = self._new_snapshot_id()
            audit_id = connection.execute(
                "INSERT INTO audit_events(event_type,actor,proposal_id,inspection_id,schema_phase,"
                "snapshot_id,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    f"MIGRATION_{action.upper()}", principal, None, None, next_phase, snapshot_id,
                    canonical_json({"from": phase, "to": next_phase}), now,
                ),
            ).lastrowid
            self._publish_snapshot(connection, snapshot_id, next_phase, inject_faults=True)
            connection.execute(
                "UPDATE metadata SET current_snapshot=?,updated_at=? WHERE singleton=1",
                (snapshot_id, now),
            )
            response = {
                "schema_phase": next_phase,
                "current_snapshot": snapshot_id,
                "audit_id": int(audit_id),
            }
            self._store_receipt(
                connection, principal, operation_key, idempotency_key, digest, response, 200
            )
            connection.commit()
            return response, 200
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _publish_snapshot(
        self,
        connection: sqlite3.Connection,
        snapshot_id: str,
        schema_phase: str,
        inject_faults: bool,
    ) -> None:
        if inject_faults:
            self._trip("before_publication")
        snapshot_dir = self.snapshots_dir / snapshot_id
        # UUID-backed names make a collision exceptional; immutability means a
        # collision must fail rather than reuse or overwrite a prior version.
        snapshot_dir.mkdir(parents=False, exist_ok=False)
        rows = connection.execute(
            "SELECT * FROM records WHERE deleted=0 ORDER BY observed_date,inspection_id"
        ).fetchall()
        partitions: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            observed = row["observed_date"]
            try:
                date.fromisoformat(observed)
            except ValueError as exc:
                raise RuntimeError("authoritative record has invalid observed_date") from exc
            item = self._record_dict(row)
            if schema_phase == "legacy":
                item.pop("measurement_value", None)
            elif schema_phase == "contracted":
                item.pop("reading", None)
            partitions.setdefault(observed, []).append(item)

        files: list[dict[str, Any]] = []
        for observed, partition_rows in sorted(partitions.items()):
            relative = Path(f"observed_date={observed}") / "part-000.parquet"
            file_path = snapshot_dir / relative
            file_path.parent.mkdir(parents=True, exist_ok=False)
            table = pa.Table.from_pylist(partition_rows)
            pq.write_table(table, file_path, compression="snappy")
            # Windows rejects fsync on a read-only CRT descriptor. Reopen the
            # completed Parquet file read/write without changing its bytes.
            with file_path.open("r+b") as handle:
                os.fsync(handle.fileno())
            files.append(
                {
                    "path": relative.as_posix(),
                    "sha256": file_sha256(file_path),
                    "row_count": len(partition_rows),
                }
            )
        manifest = {
            "snapshot_id": snapshot_id,
            "schema_phase": schema_phase,
            "created_at": utc_now(),
            "row_count": len(rows),
            "partition_field": "observed_date",
            "files": files,
        }
        manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
        manifest_path = snapshot_dir / "manifest.json"
        with manifest_path.open("xb") as handle:
            handle.write(manifest_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if inject_faults:
            self._trip("after_files_before_commit")
        connection.execute(
            "INSERT INTO snapshots(id,schema_phase,row_count,manifest_hash,created_at) VALUES(?,?,?,?,?)",
            (snapshot_id, schema_phase, len(rows), manifest_hash, manifest["created_at"]),
        )

    def snapshots(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            current = connection.execute(
                "SELECT current_snapshot FROM metadata WHERE singleton=1"
            ).fetchone()[0]
            rows = connection.execute("SELECT * FROM snapshots ORDER BY created_at,id").fetchall()
            connection.commit()
        return [
            {
                "id": row["id"],
                "schema_phase": row["schema_phase"],
                "row_count": int(row["row_count"]),
                "manifest_hash": row["manifest_hash"],
                "created_at": row["created_at"],
                "current": row["id"] == current,
            }
            for row in rows
        ]

    def read_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        if not SAFE_SNAPSHOT_ID.fullmatch(snapshot_id):
            raise ServiceError(404, "snapshot not found")
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if row is None:
            raise ServiceError(404, "snapshot not found")
        snapshot_dir = (self.snapshots_dir / snapshot_id).resolve()
        if snapshot_dir.parent != self.snapshots_dir.resolve():
            raise ServiceError(400, "invalid snapshot location")
        manifest_path = snapshot_dir / "manifest.json"
        try:
            manifest_bytes = manifest_path.read_bytes()
        except OSError as exc:
            raise ServiceError(409, "snapshot manifest is unavailable") from exc
        if hashlib.sha256(manifest_bytes).hexdigest() != row["manifest_hash"]:
            raise ServiceError(409, "snapshot manifest hash mismatch")
        try:
            manifest = json.loads(manifest_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ServiceError(409, "snapshot manifest is invalid") from exc
        if (
            manifest.get("snapshot_id") != snapshot_id
            or manifest.get("schema_phase") != row["schema_phase"]
            or manifest.get("row_count") != int(row["row_count"])
            or not isinstance(manifest.get("files"), list)
        ):
            raise ServiceError(409, "snapshot manifest metadata mismatch")

        records: list[dict[str, Any]] = []
        total_rows = 0
        for entry in manifest["files"]:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "row_count"}:
                raise ServiceError(409, "snapshot manifest file entry is invalid")
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ServiceError(409, "snapshot manifest contains an unsafe path")
            file_path = (snapshot_dir / relative).resolve()
            if snapshot_dir not in file_path.parents:
                raise ServiceError(409, "snapshot file escapes its publication directory")
            try:
                actual_hash = file_sha256(file_path)
            except OSError as exc:
                raise ServiceError(409, "snapshot data file is unavailable or invalid") from exc
            if actual_hash != entry["sha256"]:
                raise ServiceError(409, "snapshot data file hash mismatch")
            try:
                # ParquetFile reads exactly this file. Dataset discovery here
                # would also infer the Hive partition folder and duplicate the
                # observed_date column that is intentionally stored in-row.
                parquet_file = pq.ParquetFile(file_path)
                try:
                    table = parquet_file.read()
                finally:
                    parquet_file.close()
            except (OSError, pa.ArrowException) as exc:
                raise ServiceError(409, "snapshot data file is unavailable or invalid") from exc
            if table.num_rows != entry["row_count"]:
                raise ServiceError(409, "snapshot data file row count mismatch")
            total_rows += table.num_rows
            records.extend(table.to_pylist())
        if total_rows != manifest["row_count"]:
            raise ServiceError(409, "snapshot total row count mismatch")
        records.sort(key=lambda item: item["inspection_id"])
        return {
            "snapshot_id": snapshot_id,
            "schema_phase": manifest["schema_phase"],
            "records": records,
            "manifest": manifest,
        }
