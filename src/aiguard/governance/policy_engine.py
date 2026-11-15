"""Governance Policy Engine: governance requirements as executable checks.

Policies are data (YAML); checks are small registered functions. A policy
evaluation returns the policy identifier, a status, references to the evidence
used, an explanation and a recommended corrective action.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from aiguard.security.vulnerability import SEVERITY_ORDER


@dataclass(frozen=True)
class Policy:
    id: str
    title: str
    category: str
    check: str
    severity: str = "medium"
    description: str = ""
    remediation: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    applies_to_tiers: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyContext:
    """Everything a check may look at. Built by the service layer."""

    model: dict[str, Any]
    #: Latest evidence per kind: ``{kind: {"id", "status", "payload", "created_at"}}``.
    evidence: dict[str, dict[str, Any]]
    lineage: dict[str, Any]
    audit_event_count: int
    audit_chain_valid: bool
    now: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PolicyResult:
    policy_id: str
    title: str
    category: str
    severity: str
    status: str  # pass | fail | not_applicable | error
    evidence_refs: list[str]
    explanation: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CheckOutcome = tuple[bool, list[str], str]
CheckFn = Callable[[PolicyContext, dict[str, Any]], CheckOutcome]
CHECKS: dict[str, CheckFn] = {}


def register_check(name: str) -> Callable[[CheckFn], CheckFn]:
    """Register a custom check so policies can refer to it by name."""

    def decorator(fn: CheckFn) -> CheckFn:
        CHECKS[name] = fn
        return fn

    return decorator


@register_check("documentation_complete")
def _documentation_complete(ctx: PolicyContext, params: dict[str, Any]) -> CheckOutcome:
    required = params.get("required_fields", ["description", "owner", "intended_use"])
    missing = [f for f in required if not str(ctx.model.get(f) or "").strip()]
    if missing:
        return False, [], "Missing documentation fields: " + ", ".join(missing) + "."
    return True, [], "All required documentation fields are present."


@register_check("dataset_provenance")
def _dataset_provenance(ctx: PolicyContext, params: dict[str, Any]) -> CheckOutcome:
    if not ctx.lineage.get("has_dataset"):
        return False, [], "No dataset is linked upstream of this model."
    if not ctx.lineage.get("datasets_fingerprinted"):
        return False, [], "A linked dataset has no fingerprint, so it cannot be verified."
    digest = ctx.lineage.get("lineage_digest")
    return True, [f"lineage:{digest}"], "Lineage reaches a fingerprinted dataset."


@register_check("evidence_status")
def _evidence_status(ctx: PolicyContext, params: dict[str, Any]) -> CheckOutcome:
    kind = params["kind"]
    label = kind.replace("_", " ")
    item = ctx.evidence.get(kind)
    if item is None:
        return False, [], f"No {label} evidence has been recorded."
    refs = [item["id"]]
    required = params.get("required_status")
    if required and item["status"] != required:
        return False, refs, f"Latest {label} result is '{item['status']}', expected '{required}'."
    max_age = params.get("max_age_days")
    if max_age is not None:
        age = ctx.now - datetime.fromisoformat(item["created_at"])
        if age > timedelta(days=max_age):
            return False, refs, f"Latest {label} evidence is {age.days} days old (limit {max_age})."
    return True, refs, f"Latest {label} evidence: '{item['status']}'."


@register_check("no_open_findings")
def _no_open_findings(ctx: PolicyContext, params: dict[str, Any]) -> CheckOutcome:
    item = ctx.evidence.get("security_assessment")
    if item is None:
        return False, [], "No security assessment has been run."
    limit = params.get("max_severity", "medium")
    worst = item["payload"].get("highest_severity")
    if worst and SEVERITY_ORDER.index(worst) > SEVERITY_ORDER.index(limit):
        return False, [item["id"]], f"Open findings reach '{worst}' severity (limit '{limit}')."
    return True, [item["id"]], f"No findings above '{limit}' severity."


@register_check("human_oversight_defined")
def _human_oversight(ctx: PolicyContext, params: dict[str, Any]) -> CheckOutcome:
    if str(ctx.model.get("human_oversight") or "").strip():
        return True, [], "A human oversight process is recorded."
    return False, [], "No human oversight process is recorded."


@register_check("audit_records_available")
def _audit_records(ctx: PolicyContext, params: dict[str, Any]) -> CheckOutcome:
    if not ctx.audit_chain_valid:
        return False, [], "The audit chain failed verification."
    if ctx.audit_event_count < 1:
        return False, [], "No audit events exist for this model."
    return True, [], f"{ctx.audit_event_count} audit event(s); chain verifies."


def load_policies(path: str | Path | None = None) -> list[Policy]:
    """Load policies from YAML; the built-in set is used when no path is given."""
    if path is None:
        text = resources.files("aiguard.governance").joinpath("default_policies.yaml").read_text(
            encoding="utf-8"
        )
    else:
        text = Path(path).read_text(encoding="utf-8")
    document = yaml.safe_load(text) or {}
    policies = []
    seen: set[str] = set()
    for raw in document.get("policies", []):
        tiers = raw.get("applies_to_tiers")
        policy = Policy(
            id=str(raw["id"]),
            title=str(raw["title"]),
            category=str(raw["category"]),
            check=str(raw["check"]),
            severity=str(raw.get("severity", "medium")),
            description=str(raw.get("description", "")),
            remediation=str(raw.get("remediation", "")),
            params=dict(raw.get("params") or {}),
            applies_to_tiers=tuple(tiers) if tiers else None,
        )
        if policy.id in seen:
            raise ValueError(f"Duplicate policy id {policy.id}")
        if policy.severity not in SEVERITY_ORDER:
            raise ValueError(f"Policy {policy.id} has unknown severity {policy.severity!r}")
        seen.add(policy.id)
        policies.append(policy)
    return policies


def evaluate(policies: list[Policy], ctx: PolicyContext) -> list[PolicyResult]:
    results = []
    for policy in policies:
        status, explanation = "error", ""
        refs: list[str] = []
        tier = ctx.model.get("impact_tier")
        if policy.applies_to_tiers and tier not in policy.applies_to_tiers:
            status = "not_applicable"
            explanation = f"Applies to impact tier(s) {', '.join(policy.applies_to_tiers)} only."
        elif policy.check not in CHECKS:
            explanation = f"Unknown check '{policy.check}'."
        else:
            try:
                passed, refs, explanation = CHECKS[policy.check](ctx, policy.params)
                status = "pass" if passed else "fail"
            except Exception as exc:  # a broken policy must not hide the others
                explanation = f"Check raised {type(exc).__name__}: {exc}"
        results.append(
            PolicyResult(
                policy_id=policy.id,
                title=policy.title,
                category=policy.category,
                severity=policy.severity,
                status=status,
                evidence_refs=list(refs),
                explanation=explanation,
                remediation=policy.remediation if status in ("fail", "error") else "",
            )
        )
    return results


def summarize(results: list[PolicyResult]) -> dict[str, Any]:
    counts = {"pass": 0, "fail": 0, "not_applicable": 0, "error": 0}
    for result in results:
        counts[result.status] += 1
    return {
        "status": "pass" if counts["fail"] == 0 and counts["error"] == 0 else "fail",
        "total": len(results),
        **counts,
    }
