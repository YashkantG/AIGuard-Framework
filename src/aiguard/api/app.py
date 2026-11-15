"""FastAPI application: REST API under ``/api/v1`` and the dashboard at ``/``."""

import secrets
import sys
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from aiguard.api.security import Authenticator, Principal, RateLimiter
from aiguard.config import Settings, get_settings
from aiguard.core.errors import ConflictError, InvalidInputError, NotFoundError
from aiguard.core.models import (
    AssessRequest,
    DriftRequest,
    ExplainRequest,
    LineageEdgeCreate,
    LineageNodeCreate,
    ModelCreate,
    PolicyEvaluateRequest,
    VerifyRequest,
)
from aiguard.governance.compliance import render_markdown
from aiguard.service import AIGuard

STATIC_DIR = Path(__file__).parent / "static"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)


def create_app(service: AIGuard | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or (service.settings if service else get_settings())
    service = service or AIGuard(settings)

    keys = settings.parsed_api_keys()
    if not keys:
        # Secure by default: never start an unauthenticated API.
        bootstrap = secrets.token_urlsafe(32)
        keys = {bootstrap: ("bootstrap-admin", "admin")}
        print(
            "AIGUARD_API_KEYS is not set. Temporary admin API key for this process:\n"
            f"  {bootstrap}\n"
            "Set AIGUARD_API_KEYS=name:role:key[,...] for a stable configuration.",
            file=sys.stderr,
        )
    auth = Authenticator(keys, RateLimiter(settings.rate_limit_per_minute))
    viewer = Depends(auth.require("viewer"))
    analyst = Depends(auth.require("analyst"))

    from aiguard import __version__

    app = FastAPI(
        title="AIGuard Framework",
        version=__version__,
        description="AI model governance and security API.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.service = service

    @app.middleware("http")
    async def harden(request: Request, call_next: Any) -> Any:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_request_bytes:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.startswith("/api/docs"):
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(InvalidInputError)
    async def _invalid(_: Request, exc: InvalidInputError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    # ------------------------------------------------------------------ system

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/me", tags=["system"])
    def me(principal: Principal = viewer) -> dict[str, str]:
        return {"name": principal.name, "role": principal.role, "version": __version__}

    @app.get("/api/v1/stats", tags=["system"])
    def stats(_: Principal = viewer) -> dict[str, Any]:
        return service.stats()

    # ------------------------------------------------------------------ models

    @app.post("/api/v1/models", status_code=201, tags=["models"])
    def register_model(body: ModelCreate, principal: Principal = analyst) -> dict[str, Any]:
        return service.register_model(body, principal.actor)

    @app.get("/api/v1/models", tags=["models"])
    def list_models(_: Principal = viewer) -> list[dict[str, Any]]:
        return service.list_models()

    @app.get("/api/v1/models/{model_id}", tags=["models"])
    def get_model(model_id: str, _: Principal = viewer) -> dict[str, Any]:
        return service.get_model(model_id)

    @app.post("/api/v1/models/{model_id}/verify", tags=["integrity"])
    def verify(
        model_id: str, body: VerifyRequest | None = None, principal: Principal = analyst
    ) -> dict[str, Any]:
        body = body or VerifyRequest()
        return service.verify_integrity(
            model_id, artifact_path=body.artifact_path, sha256=body.sha256, actor=principal.actor
        )

    @app.post("/api/v1/models/{model_id}/explain", tags=["explainability"])
    def explain(
        model_id: str, body: ExplainRequest, principal: Principal = analyst
    ) -> dict[str, Any]:
        return service.explain(model_id, body, principal.actor)

    @app.post("/api/v1/models/{model_id}/assess", tags=["security"])
    def assess(
        model_id: str, body: AssessRequest | None = None, principal: Principal = analyst
    ) -> dict[str, Any]:
        return service.assess_security(model_id, body, principal.actor)

    @app.post("/api/v1/models/{model_id}/drift", tags=["monitoring"])
    def drift(model_id: str, body: DriftRequest, principal: Principal = analyst) -> dict[str, Any]:
        return service.evaluate_drift(model_id, body, principal.actor)

    @app.post("/api/v1/models/{model_id}/risk", tags=["governance"])
    def risk(model_id: str, principal: Principal = analyst) -> dict[str, Any]:
        return service.assess_risk(model_id, principal.actor)

    @app.get("/api/v1/models/{model_id}/audit", tags=["audit"])
    def model_audit(
        model_id: str,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
        _: Principal = viewer,
    ) -> list[dict[str, Any]]:
        return service.audit_history(model_id, limit)

    @app.get("/api/v1/models/{model_id}/evidence", tags=["evidence"])
    def model_evidence(model_id: str, _: Principal = viewer) -> dict[str, dict[str, Any]]:
        """Latest evidence of each kind."""
        return service.latest_evidence(model_id)

    @app.get("/api/v1/models/{model_id}/lineage", tags=["provenance"])
    def model_lineage(model_id: str, _: Principal = viewer) -> dict[str, Any]:
        return service.model_lineage(model_id)

    @app.get("/api/v1/models/{model_id}/report", tags=["governance"])
    def report(model_id: str, _: Principal = viewer) -> dict[str, Any]:
        return service.compliance_report(model_id)

    @app.get(
        "/api/v1/models/{model_id}/report.md", tags=["governance"], response_class=PlainTextResponse
    )
    def report_markdown(model_id: str, _: Principal = viewer) -> PlainTextResponse:
        text = render_markdown(service.compliance_report(model_id))
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")

    # ------------------------------------------------------------------ policies

    @app.get("/api/v1/policies", tags=["governance"])
    def policies(_: Principal = viewer) -> list[dict[str, Any]]:
        return service.list_policies()

    @app.post("/api/v1/policies/evaluate", tags=["governance"])
    def evaluate(body: PolicyEvaluateRequest, principal: Principal = analyst) -> dict[str, Any]:
        return service.evaluate_policies(body.model_id, body.policy_ids, principal.actor)

    # ------------------------------------------------------------------ lineage & audit

    @app.post("/api/v1/lineage/nodes", status_code=201, tags=["provenance"])
    def add_node(body: LineageNodeCreate, principal: Principal = analyst) -> dict[str, Any]:
        return service.add_lineage_node(body, principal.actor)

    @app.post("/api/v1/lineage/edges", status_code=201, tags=["provenance"])
    def add_edge(body: LineageEdgeCreate, principal: Principal = analyst) -> dict[str, str]:
        return service.add_lineage_edge(body.src_id, body.dst_id, principal.actor)

    @app.get("/api/v1/audit", tags=["audit"])
    def audit(
        limit: Annotated[int, Query(ge=1, le=1000)] = 200, _: Principal = viewer
    ) -> list[dict[str, Any]]:
        return service.audit_log(limit)

    @app.get("/api/v1/audit/verify", tags=["audit"])
    def audit_verify(_: Principal = viewer) -> dict[str, Any]:
        return service.verify_audit_chain()

    # ------------------------------------------------------------------ dashboard

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
