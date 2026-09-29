"""FastAPI transport for the governed synthetic inspection service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Path as ApiPath, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from service import DataService, EmptyInput, ProposalInput, ReviewInput, ServiceError


PROJECT_DIR = Path(__file__).resolve().parent
VALID_USERS = {"analyst", "reviewer", "admin", "viewer"}


def _default_data_dir() -> Path:
    configured = os.environ.get("GDS_DATA_DIR")
    return Path(configured).expanduser() if configured else PROJECT_DIR / "runtime" / "data"


def _identity(x_demo_user: str | None = Header(default=None, alias="X-Demo-User")) -> str:
    principal = x_demo_user or "viewer"
    if principal not in VALID_USERS:
        raise HTTPException(status_code=401, detail="unknown demo identity")
    return principal


def _require(principal: str, role: str) -> None:
    if principal != role:
        raise HTTPException(status_code=403, detail=f"{role} role required")


def _idempotency_key(value: str | None) -> str:
    if value is None or not value.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    value = value.strip()
    if len(value) > 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key is too long")
    return value


def create_app(
    data_dir: str | os.PathLike[str] | None = None,
    *,
    fault_injector: Callable[[str], None] | None = None,
) -> FastAPI:
    """Create an isolated app; ``uvicorn app:create_app --factory`` is supported."""

    service = DataService(data_dir or _default_data_dir(), fault_injector=fault_injector)
    app = FastAPI(
        title="Governed Data Service",
        version="1.0.0",
        description=(
            "Local synthetic portfolio demo. X-Demo-User identities are impersonable "
            "demonstration roles, not production authentication."
        ),
    )
    app.state.service = service

    @app.exception_handler(ServiceError)
    async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(PROJECT_DIR / "static" / "index.html")

    @app.get("/api/state")
    def get_state() -> dict:
        return service.state()

    @app.get("/api/records")
    def get_records(client_version: int = Query(ge=1, le=2)) -> dict:
        return {"records": service.records_for_client(client_version)}

    @app.get("/api/proposals")
    def get_proposals() -> dict:
        return {"proposals": service.proposals()}

    @app.get("/api/audit")
    def get_audit() -> dict:
        return {"audit": service.audit()}

    @app.get("/api/snapshots")
    def get_snapshots() -> dict:
        return {"snapshots": service.snapshots()}

    @app.get("/api/snapshots/{snapshot_id}")
    def get_snapshot(snapshot_id: str = ApiPath(min_length=1, max_length=64)) -> dict:
        return service.read_snapshot(snapshot_id)

    @app.post("/api/proposals")
    def post_proposal(
        body: ProposalInput,
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        idempotency: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        principal = _identity(x_demo_user)
        _require(principal, "analyst")
        key = _idempotency_key(idempotency)
        response, status = service.create_proposal(body, principal, key)
        return JSONResponse(status_code=status, content=response)

    def review(
        proposal_id: str,
        decision: str,
        body: ReviewInput,
        x_demo_user: str | None,
        idempotency: str | None,
    ) -> JSONResponse:
        principal = _identity(x_demo_user)
        _require(principal, "reviewer")
        key = _idempotency_key(idempotency)
        response, status = service.review_proposal(
            proposal_id, decision, body, principal, key  # type: ignore[arg-type]
        )
        return JSONResponse(status_code=status, content=response)

    @app.post("/api/proposals/{proposal_id}/approve")
    def approve_proposal(
        body: ReviewInput,
        proposal_id: str = ApiPath(min_length=1, max_length=64),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        idempotency: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        return review(proposal_id, "approve", body, x_demo_user, idempotency)

    @app.post("/api/proposals/{proposal_id}/reject")
    def reject_proposal(
        body: ReviewInput,
        proposal_id: str = ApiPath(min_length=1, max_length=64),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        idempotency: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        return review(proposal_id, "reject", body, x_demo_user, idempotency)

    def migration(
        action: str,
        _body: EmptyInput,
        x_demo_user: str | None,
        idempotency: str | None,
    ) -> JSONResponse:
        principal = _identity(x_demo_user)
        _require(principal, "admin")
        key = _idempotency_key(idempotency)
        response, status = service.migrate(action, principal, key)  # type: ignore[arg-type]
        return JSONResponse(status_code=status, content=response)

    @app.post("/api/migrations/expand")
    def expand(
        body: EmptyInput,
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        idempotency: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        return migration("expand", body, x_demo_user, idempotency)

    @app.post("/api/migrations/backfill")
    def backfill(
        body: EmptyInput,
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        idempotency: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        return migration("backfill", body, x_demo_user, idempotency)

    @app.post("/api/migrations/contract")
    def contract(
        body: EmptyInput,
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        idempotency: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        return migration("contract", body, x_demo_user, idempotency)

    return app
