"""The AIGuard service: the single entry point used by the SDK, CLI and REST API.

Every state-changing operation stores its result as *evidence* and appends an
audit event in the same transaction, so governance policies can point at the
records that justify a pass or a fail.
"""

import hmac
import threading
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aiguard.audit import event_to_dict, record_event, verify_chain
from aiguard.config import Settings, get_settings
from aiguard.core.db import AuditRow, Database, EvidenceRow, LineageNodeRow, ModelRow
from aiguard.core.errors import ConflictError, InvalidInputError, NotFoundError
from aiguard.core.models import (
    AssessRequest,
    DriftRequest,
    ExplainRequest,
    LineageNodeCreate,
    ModelCreate,
)
from aiguard.explainability import surrogate_explanation
from aiguard.governance import compliance, policy_engine, risk_assessment
from aiguard.monitoring import detect_drift
from aiguard.provenance import lineage
from aiguard.security import vulnerability
from aiguard.security.integrity import calculate_model_hash

EVIDENCE_KINDS = (
    "integrity",
    "security_assessment",
    "drift",
    "explanation",
    "risk_assessment",
    "policy_evaluation",
)


def _evidence_dict(row: EvidenceRow, *, with_payload: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": row.id,
        "model_id": row.model_id,
        "kind": row.kind,
        "status": row.status,
        "summary": row.summary,
        "actor": row.actor,
        "created_at": row.created_at,
    }
    if with_payload:
        data["payload"] = row.payload
    return data


class AIGuard:
    def __init__(self, settings: Settings | None = None, db: Database | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = db or Database(self.settings.database_url)
        self.artifact_dir = Path(self.settings.artifact_dir).resolve()
        self.policies = policy_engine.load_policies(self.settings.policy_file)
        # Serialises writers in this process so the audit chain cannot fork.
        # Across processes the unique constraint on prev_hash does the same job.
        self._write_lock = threading.RLock()

    # ------------------------------------------------------------------ helpers

    def resolve_artifact(self, path: str, *, trusted: bool = False) -> Path:
        """Resolve an artifact path.

        Untrusted callers (the API) may only reference files inside the
        configured artifact directory; symlinks and ``..`` are resolved first.
        """
        if trusted:
            resolved = Path(path).resolve()
        else:
            resolved = (self.artifact_dir / path).resolve()
            if not resolved.is_relative_to(self.artifact_dir):
                raise InvalidInputError("artifact_path must be inside the artifact directory")
        if not resolved.is_file():
            raise InvalidInputError("Artifact file not found")
        return resolved

    @staticmethod
    def _get_model(session: Session, model_id: str) -> ModelRow:
        row = session.get(ModelRow, model_id)
        if row is None:
            raise NotFoundError(f"Model {model_id} not found")
        return row

    @staticmethod
    def _model_dict(row: ModelRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "version": row.version,
            "framework": row.framework,
            "sha256": row.sha256,
            "size_bytes": row.size_bytes,
            "artifact_available": bool(row.artifact_uri and Path(row.artifact_uri).is_file()),
            "owner": row.owner,
            "description": row.description,
            "intended_use": row.intended_use,
            "impact_tier": row.impact_tier,
            "human_oversight": row.human_oversight,
            "extra": row.extra,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    @staticmethod
    def _add_evidence(
        session: Session,
        model_id: str,
        kind: str,
        status: str,
        summary: str,
        payload: dict[str, Any],
        actor: str,
    ) -> EvidenceRow:
        row = EvidenceRow(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            model_id=model_id,
            kind=kind,
            status=status,
            summary=summary,
            payload=payload,
            actor=actor,
        )
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def _latest_evidence(session: Session, model_id: str) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        rows = session.execute(
            select(EvidenceRow)
            .where(EvidenceRow.model_id == model_id)
            .order_by(EvidenceRow.seq.desc())
        ).scalars()
        for row in rows:
            latest.setdefault(row.kind, _evidence_dict(row))
        return latest

    @staticmethod
    def _model_lineage(session: Session, model_id: str) -> dict[str, Any]:
        node = session.execute(
            select(LineageNodeRow).where(
                LineageNodeRow.model_id == model_id, LineageNodeRow.node_type == "model_version"
            )
        ).scalar_one()
        return lineage.lineage_for_node(session, node.id)

    @staticmethod
    def _posture(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
        def status(kind: str) -> str | None:
            return evidence[kind]["status"] if kind in evidence else None

        risk = evidence.get("risk_assessment")
        return {
            "integrity": status("integrity"),
            "security": status("security_assessment"),
            "drift": status("drift"),
            "explanation": status("explanation"),
            "policy": status("policy_evaluation"),
            "risk_level": risk["payload"]["level"] if risk else None,
            "risk_score": risk["payload"]["score"] if risk else None,
        }

    # ------------------------------------------------------------------ registry

    def register_model(
        self, data: ModelCreate, actor: str = "sdk", *, trusted_path: bool = False
    ) -> dict[str, Any]:
        artifact_uri: str | None = None
        size: int | None = None
        if data.artifact_path:
            artifact = self.resolve_artifact(data.artifact_path, trusted=trusted_path)
            digest = calculate_model_hash(artifact)
            if data.sha256 and not hmac.compare_digest(digest, data.sha256.lower()):
                raise InvalidInputError("Supplied sha256 does not match the artifact")
            artifact_uri, size = str(artifact), artifact.stat().st_size
        else:
            assert data.sha256 is not None  # enforced by ModelCreate
            digest = data.sha256.lower()

        with self._write_lock, self.db.session() as session:
            row = ModelRow(
                id=f"mdl_{uuid.uuid4().hex[:12]}",
                name=data.name,
                version=data.version,
                framework=data.framework,
                artifact_uri=artifact_uri,
                sha256=digest,
                size_bytes=size,
                owner=data.owner,
                description=data.description,
                intended_use=data.intended_use,
                impact_tier=data.impact_tier,
                human_oversight=data.human_oversight,
                extra=data.extra,
                created_by=actor,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as exc:
                raise ConflictError(
                    f"Model {data.name} version {data.version} is already registered"
                ) from exc
            lineage.add_node(
                session,
                node_type="model_version",
                name=f"{row.name}:{row.version}",
                fingerprint=digest,
                model_id=row.id,
            )
            record_event(
                session,
                actor=actor,
                category="registry",
                action="model.register",
                result="success",
                model_id=row.id,
                model_version=row.version,
                details={"sha256": digest, "artifact_registered": artifact_uri is not None},
            )
            return self._model_dict(row)

    def get_model(self, model_id: str) -> dict[str, Any]:
        with self.db.session() as session:
            row = self._get_model(session, model_id)
            return {
                **self._model_dict(row),
                "posture": self._posture(self._latest_evidence(session, model_id)),
            }

    def list_models(self) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(select(ModelRow).order_by(ModelRow.created_at.desc())).scalars()
            return [
                {
                    **self._model_dict(row),
                    "posture": self._posture(self._latest_evidence(session, row.id)),
                }
                for row in rows
            ]

    # ------------------------------------------------------------------ integrity

    def verify_integrity(
        self,
        model_id: str,
        *,
        artifact_path: str | None = None,
        sha256: str | None = None,
        actor: str = "sdk",
        trusted_path: bool = False,
    ) -> dict[str, Any]:
        """Compare an artifact (or a client-computed digest) with the registered digest."""
        with self._write_lock, self.db.session() as session:
            row = self._get_model(session, model_id)
            if artifact_path:
                actual = calculate_model_hash(
                    self.resolve_artifact(artifact_path, trusted=trusted_path)
                )
                source = "supplied_artifact"
            elif sha256:
                actual, source = sha256.lower(), "client_supplied_digest"
            elif row.artifact_uri and Path(row.artifact_uri).is_file():
                actual, source = calculate_model_hash(row.artifact_uri), "registered_artifact"
            else:
                raise InvalidInputError(
                    "No artifact is available for this model; supply artifact_path or sha256"
                )
            verified = hmac.compare_digest(actual, row.sha256)
            status = "pass" if verified else "fail"
            payload = {
                "verified": verified,
                "algorithm": "sha256",
                "expected": row.sha256,
                "actual": actual,
                "source": source,
            }
            evidence = self._add_evidence(
                session,
                model_id,
                "integrity",
                status,
                "Digest matches registration" if verified else "Digest does NOT match registration",
                payload,
                actor,
            )
            record_event(
                session,
                actor=actor,
                category="integrity",
                action="model.verify",
                result=status,
                model_id=model_id,
                model_version=row.version,
                evidence_refs=[evidence.id],
                details={"source": source},
            )
            return {**payload, "evidence_id": evidence.id}

    # ------------------------------------------------------------------ security

    def assess_security(
        self, model_id: str, request: AssessRequest | None = None, actor: str = "sdk"
    ) -> dict[str, Any]:
        request = request or AssessRequest()
        with self._write_lock, self.db.session() as session:
            row = self._get_model(session, model_id)
            findings: list[vulnerability.Finding] = []
            artifact_format = None
            if row.artifact_uri and Path(row.artifact_uri).is_file():
                scan = vulnerability.scan_artifact(row.artifact_uri, self.settings.max_scan_bytes)
                artifact_format = scan["format"]
                findings.extend(scan["findings"])
            else:
                findings.append(
                    vulnerability.Finding(
                        id="AIG-ART-001",
                        title="Artifact not available for inspection",
                        severity="low",
                        description="Only a digest is registered, so the file was not inspected.",
                        recommendation="Register the artifact file to enable static inspection.",
                    )
                )

            integrity = self._latest_evidence(session, model_id).get("integrity")
            if integrity is None or integrity["status"] != "pass":
                findings.append(
                    vulnerability.Finding(
                        id="AIG-INT-001",
                        title="Missing integrity verification",
                        severity="medium",
                        description=(
                            "No passing integrity verification is on record."
                            if integrity is None
                            else "The latest integrity verification failed."
                        ),
                        recommendation="Verify the artifact digest before deployment.",
                        reference=vulnerability.OWASP_SUPPLY_CHAIN,
                    )
                )
            if request.deployment_config is not None:
                findings.extend(vulnerability.check_deployment_config(request.deployment_config))
            if request.requirements:
                findings.extend(vulnerability.check_requirements(request.requirements))

            counts = Counter(f.severity for f in findings)
            worst = vulnerability.highest_severity(findings)
            blocking = counts["high"] + counts["critical"]
            status = "fail" if blocking else "pass"
            payload = {
                "status": status,
                "artifact_format": artifact_format,
                "highest_severity": worst,
                "counts": {s: counts.get(s, 0) for s in vulnerability.SEVERITY_ORDER},
                "findings": [f.to_dict() for f in findings],
                "notice": "Findings and recommendations only; this does not prove a model secure.",
            }
            evidence = self._add_evidence(
                session,
                model_id,
                "security_assessment",
                status,
                f"{len(findings)} finding(s), highest severity: {worst or 'none'}",
                payload,
                actor,
            )
            record_event(
                session,
                actor=actor,
                category="security",
                action="model.assess",
                result=status,
                model_id=model_id,
                model_version=row.version,
                evidence_refs=[evidence.id],
                details={"findings": len(findings), "highest_severity": worst},
            )
            return {**payload, "evidence_id": evidence.id}

    # ------------------------------------------------------------------ drift

    def evaluate_drift(
        self, model_id: str, request: DriftRequest, actor: str = "sdk"
    ) -> dict[str, Any]:
        try:
            report = detect_drift(
                {name: spec.model_dump() for name, spec in request.features.items()},
                psi_threshold=request.psi_threshold,
                alpha=request.alpha,
            )
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc
        status = "drift_detected" if report["drift_detected"] else "stable"
        with self._write_lock, self.db.session() as session:
            row = self._get_model(session, model_id)
            drifted = report["drifted_features"]
            evidence = self._add_evidence(
                session,
                model_id,
                "drift",
                status,
                f"{len(drifted)} of {len(report['features'])} feature(s) drifted",
                report,
                actor,
            )
            record_event(
                session,
                actor=actor,
                category="monitoring",
                action="model.drift",
                result=status,
                model_id=model_id,
                model_version=row.version,
                evidence_refs=[evidence.id],
                details={"drifted_features": drifted},
            )
            return {**report, "status": status, "evidence_id": evidence.id}

    # ------------------------------------------------------------------ explainability

    def explain(self, model_id: str, request: ExplainRequest, actor: str = "sdk") -> dict[str, Any]:
        """Explain recorded predictions with a linear surrogate (the model is not executed)."""
        try:
            report = surrogate_explanation(
                request.X, request.predictions, feature_names=request.feature_names
            )
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc
        return self.record_explanation(model_id, report, actor)

    def record_explanation(
        self, model_id: str, report: dict[str, Any], actor: str = "sdk"
    ) -> dict[str, Any]:
        """Store an explanation report produced by any :mod:`aiguard.explainability` method."""
        with self._write_lock, self.db.session() as session:
            row = self._get_model(session, model_id)
            top = report["features"][0]["feature"] if report.get("features") else "n/a"
            evidence = self._add_evidence(
                session,
                model_id,
                "explanation",
                "generated",
                f"{report.get('method', 'explanation')}; top feature: {top}",
                report,
                actor,
            )
            record_event(
                session,
                actor=actor,
                category="explainability",
                action="model.explain",
                result="success",
                model_id=model_id,
                model_version=row.version,
                evidence_refs=[evidence.id],
                details={"method": report.get("method")},
            )
            return {**report, "evidence_id": evidence.id}

    # ------------------------------------------------------------------ governance

    def assess_risk(self, model_id: str, actor: str = "sdk") -> dict[str, Any]:
        with self._write_lock, self.db.session() as session:
            row = self._get_model(session, model_id)
            report = risk_assessment.assess_risk(
                self._model_dict(row), self._latest_evidence(session, model_id)
            )
            evidence = self._add_evidence(
                session,
                model_id,
                "risk_assessment",
                report["level"],
                f"Risk {report['level']} ({report['score']}/100)",
                report,
                actor,
            )
            record_event(
                session,
                actor=actor,
                category="governance",
                action="model.risk",
                result=report["level"],
                model_id=model_id,
                model_version=row.version,
                evidence_refs=[evidence.id],
                details={"score": report["score"]},
            )
            return {**report, "evidence_id": evidence.id}

    def _policy_context(self, session: Session, row: ModelRow) -> policy_engine.PolicyContext:
        count = session.execute(
            select(func.count()).select_from(AuditRow).where(AuditRow.model_id == row.id)
        ).scalar_one()
        return policy_engine.PolicyContext(
            model=self._model_dict(row),
            evidence=self._latest_evidence(session, row.id),
            lineage=self._model_lineage(session, row.id),
            audit_event_count=count,
            audit_chain_valid=verify_chain(session)["valid"],
        )

    def evaluate_policies(
        self, model_id: str, policy_ids: list[str] | None = None, actor: str = "sdk"
    ) -> dict[str, Any]:
        policies = self.policies
        if policy_ids is not None:
            known = {p.id for p in policies}
            unknown = sorted(set(policy_ids) - known)
            if unknown:
                raise InvalidInputError("Unknown policy id(s): " + ", ".join(unknown))
            policies = [p for p in policies if p.id in set(policy_ids)]
        with self._write_lock, self.db.session() as session:
            row = self._get_model(session, model_id)
            results = policy_engine.evaluate(policies, self._policy_context(session, row))
            summary = policy_engine.summarize(results)
            payload = {"summary": summary, "results": [r.to_dict() for r in results]}
            evidence = self._add_evidence(
                session,
                model_id,
                "policy_evaluation",
                summary["status"],
                f"{summary['pass']} passed, {summary['fail']} failed",
                payload,
                actor,
            )
            record_event(
                session,
                actor=actor,
                category="governance",
                action="policies.evaluate",
                result=summary["status"],
                model_id=model_id,
                model_version=row.version,
                evidence_refs=[evidence.id],
                details={"failed": [r.policy_id for r in results if r.status == "fail"]},
            )
            return {"model_id": model_id, **payload, "evidence_id": evidence.id}

    def list_policies(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.policies]

    def compliance_report(self, model_id: str) -> dict[str, Any]:
        """Read-only evidence report; does not create evidence or audit events."""
        with self.db.session() as session:
            row = self._get_model(session, model_id)
            context = self._policy_context(session, row)
            results = policy_engine.evaluate(self.policies, context)
            risk = context.evidence.get("risk_assessment")
            return compliance.build_report(
                context.model,
                [r.to_dict() for r in results],
                policy_engine.summarize(results),
                risk["payload"] if risk else None,
                context.evidence,
                verify_chain(session),
            )

    # ------------------------------------------------------------------ evidence & audit

    def list_evidence(self, model_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        with self.db.session() as session:
            self._get_model(session, model_id)
            query = select(EvidenceRow).where(EvidenceRow.model_id == model_id)
            if kind:
                query = query.where(EvidenceRow.kind == kind)
            rows = session.execute(query.order_by(EvidenceRow.seq.desc()).limit(200)).scalars()
            return [_evidence_dict(row) for row in rows]

    def latest_evidence(self, model_id: str) -> dict[str, dict[str, Any]]:
        with self.db.session() as session:
            self._get_model(session, model_id)
            return self._latest_evidence(session, model_id)

    def audit_history(self, model_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.session() as session:
            self._get_model(session, model_id)
            rows = session.execute(
                select(AuditRow)
                .where(AuditRow.model_id == model_id)
                .order_by(AuditRow.seq.desc())
                .limit(limit)
            ).scalars()
            return [event_to_dict(row) for row in rows]

    def audit_log(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(AuditRow).order_by(AuditRow.seq.desc()).limit(limit)
            ).scalars()
            return [event_to_dict(row) for row in rows]

    def verify_audit_chain(self) -> dict[str, Any]:
        with self.db.session() as session:
            return verify_chain(session)

    # ------------------------------------------------------------------ lineage

    def add_lineage_node(self, data: LineageNodeCreate, actor: str = "sdk") -> dict[str, Any]:
        if data.node_type == "model_version":
            raise InvalidInputError("Model version nodes are created by registering a model")
        with self._write_lock, self.db.session() as session:
            node = lineage.add_node(
                session,
                node_type=data.node_type,
                name=data.name,
                fingerprint=data.fingerprint,
                attributes=data.attributes,
            )
            record_event(
                session,
                actor=actor,
                category="provenance",
                action="lineage.node.add",
                result="success",
                details={"node_id": node.id, "node_type": node.node_type, "name": node.name},
            )
            return lineage.node_to_dict(node)

    def add_lineage_edge(self, src_id: str, dst_id: str, actor: str = "sdk") -> dict[str, str]:
        with self._write_lock, self.db.session() as session:
            lineage.add_edge(session, src_id, dst_id)
            dst = session.get(LineageNodeRow, dst_id)
            record_event(
                session,
                actor=actor,
                category="provenance",
                action="lineage.edge.add",
                result="success",
                model_id=dst.model_id if dst else None,
                details={"src_id": src_id, "dst_id": dst_id},
            )
            return {"src_id": src_id, "dst_id": dst_id}

    def model_node_id(self, model_id: str) -> str:
        with self.db.session() as session:
            self._get_model(session, model_id)
            return self._model_lineage(session, model_id)["root"]

    def model_lineage(self, model_id: str) -> dict[str, Any]:
        with self.db.session() as session:
            self._get_model(session, model_id)
            return self._model_lineage(session, model_id)

    # ------------------------------------------------------------------ dashboard

    def stats(self) -> dict[str, Any]:
        with self.db.session() as session:
            models = list(session.execute(select(ModelRow)).scalars())
            risk_levels: Counter[str] = Counter()
            policy: Counter[str] = Counter()
            integrity: Counter[str] = Counter()
            findings: Counter[str] = Counter()
            drifted = 0
            for row in models:
                evidence = self._latest_evidence(session, row.id)
                posture = self._posture(evidence)
                risk_levels[posture["risk_level"] or "unassessed"] += 1
                policy[posture["policy"] or "not_evaluated"] += 1
                integrity[posture["integrity"] or "unverified"] += 1
                drifted += posture["drift"] == "drift_detected"
                if "security_assessment" in evidence:
                    findings.update(evidence["security_assessment"]["payload"]["counts"])
            recent = session.execute(
                select(AuditRow).order_by(AuditRow.seq.desc()).limit(12)
            ).scalars()
            return {
                "models": len(models),
                "risk_levels": dict(risk_levels),
                "policy": dict(policy),
                "integrity": dict(integrity),
                "open_findings": {s: findings.get(s, 0) for s in vulnerability.SEVERITY_ORDER},
                "models_with_drift": drifted,
                "audit_events": session.execute(
                    select(func.count()).select_from(AuditRow)
                ).scalar_one(),
                "audit_chain": verify_chain(session),
                "policies_defined": len(self.policies),
                "recent_events": [event_to_dict(row) for row in recent],
            }
