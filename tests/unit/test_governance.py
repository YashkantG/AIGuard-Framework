from datetime import UTC, datetime, timedelta

import pytest

from aiguard.governance import (
    Policy,
    PolicyContext,
    assess_risk,
    build_report,
    evaluate,
    load_policies,
    render_markdown,
    summarize,
)
from aiguard.governance.policy_engine import register_check


def evidence(kind_status: dict[str, str], age_days: int = 0, **payloads) -> dict:
    created = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    return {
        kind: {
            "id": f"ev_{kind}",
            "status": status,
            "created_at": created,
            "payload": payloads.get(kind, {}),
        }
        for kind, status in kind_status.items()
    }


def context(**overrides) -> PolicyContext:
    defaults = dict(
        model={
            "impact_tier": "high",
            "description": "d",
            "owner": "o",
            "intended_use": "u",
            "human_oversight": "reviewer",
        },
        evidence=evidence(
            {
                "integrity": "pass",
                "security_assessment": "pass",
                "explanation": "generated",
                "risk_assessment": "low",
                "drift": "stable",
            },
            security_assessment={"highest_severity": "medium"},
        ),
        lineage={"has_dataset": True, "datasets_fingerprinted": True, "lineage_digest": "abc"},
        audit_event_count=3,
        audit_chain_valid=True,
    )
    return PolicyContext(**{**defaults, **overrides})


def results_by_id(ctx: PolicyContext) -> dict:
    return {r.policy_id: r for r in evaluate(load_policies(), ctx)}


def test_default_policies_load_and_all_pass_for_complete_model():
    policies = load_policies()
    assert len({p.id for p in policies}) == len(policies) == 9
    results = evaluate(policies, context())
    assert summarize(results) == {
        "status": "pass", "total": 9, "pass": 9, "fail": 0, "not_applicable": 0, "error": 0
    }  # fmt: skip
    assert results_by_id(context())["GOV-INT-001"].evidence_refs == ["ev_integrity"]


def test_failures_carry_explanation_and_remediation():
    ctx = context(
        model={"impact_tier": "high", "description": "", "owner": "o", "intended_use": "u"},
        evidence=evidence(
            {"integrity": "fail", "security_assessment": "fail"},
            security_assessment={"highest_severity": "critical"},
        ),
        lineage={"has_dataset": False},
        audit_chain_valid=False,
    )
    results = results_by_id(ctx)
    failed = {pid for pid, r in results.items() if r.status == "fail"}
    assert failed == set(results)  # nothing passes
    assert "description" in results["GOV-DOC-001"].explanation
    assert "critical" in results["GOV-SEC-001"].explanation
    assert all(r.remediation for r in results.values())


def test_tier_scoping_and_stale_evidence():
    ctx = context(
        model={"impact_tier": "limited", "description": "d", "owner": "o", "intended_use": "u"},
        evidence=evidence({"drift": "stable"}, age_days=45),
    )
    results = results_by_id(ctx)
    assert results["GOV-HUM-001"].status == "not_applicable"
    assert results["GOV-MON-001"].status == "fail"
    assert "45 days old" in results["GOV-MON-001"].explanation


def test_unknown_and_raising_checks_are_reported_not_hidden():
    @register_check("always_raises")
    def _boom(ctx, params):
        raise RuntimeError("boom")

    policies = [
        Policy(id="X-1", title="t", category="c", check="does_not_exist"),
        Policy(id="X-2", title="t", category="c", check="always_raises"),
    ]
    results = evaluate(policies, context())
    assert [r.status for r in results] == ["error", "error"]
    assert "boom" in results[1].explanation
    assert summarize(results)["status"] == "fail"


def test_custom_policy_file_validation(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(
        "policies:\n"
        "  - {id: A, title: t, category: c, check: audit_records_available}\n"
        "  - {id: A, title: t, category: c, check: audit_records_available}\n"
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_policies(path)


def test_risk_score_tracks_evidence():
    complete = context()
    low = assess_risk({**complete.model, "impact_tier": "minimal"}, complete.evidence)
    bare = assess_risk({"impact_tier": "high"}, {})
    bad = assess_risk(
        {"impact_tier": "high"},
        evidence(
            {"integrity": "fail", "security_assessment": "fail", "drift": "drift_detected"},
            security_assessment={"highest_severity": "critical"},
        ),
    )
    assert low["level"] == "low"
    assert low["score"] < bare["score"] < bad["score"] <= 100
    assert bad["level"] == "critical"
    assert sum(f["max_points"] for f in bad["factors"]) == 100


def test_compliance_report_markdown():
    ctx = context()
    results = [r.to_dict() for r in evaluate(load_policies(), ctx)]
    report = build_report(
        {"id": "mdl_1", "name": "demo", "version": "1.0", "sha256": "ab" * 32, **ctx.model},
        results,
        summarize(evaluate(load_policies(), ctx)),
        {"score": 10, "level": "low"},
        ctx.evidence,
        {"valid": True, "events_checked": 3, "head_hash": "ff"},
    )
    text = render_markdown(report)
    assert "# Governance evidence report: demo 1.0" in text
    assert "GOV-PRV-001" in text and "MAP" in text
    assert "does not constitute" in text
    assert report["controls"][0]["nist_ai_rmf_function"]
