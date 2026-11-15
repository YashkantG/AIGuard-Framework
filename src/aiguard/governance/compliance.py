"""Compliance evidence reports, machine-readable (dict/JSON) and human-readable (Markdown).

The NIST AI RMF column is an indicative mapping to help readers navigate. It is
not a certification and does not establish regulatory compliance.
"""

from datetime import UTC, datetime
from typing import Any

DISCLAIMER = (
    "This report summarises evidence recorded by AIGuard. It does not constitute "
    "certification or regulatory compliance, and does not prove that the model is "
    "secure or unbiased."
)

# Policy category -> NIST AI RMF core function (indicative only).
NIST_AI_RMF_FUNCTION = {
    "documentation": "MAP",
    "provenance": "MAP",
    "risk": "MAP",
    "explainability": "MEASURE",
    "monitoring": "MEASURE",
    "security": "MEASURE",
    "integrity": "MANAGE",
    "oversight": "GOVERN",
    "audit": "GOVERN",
}


def build_report(
    model: dict[str, Any],
    policy_results: list[dict[str, Any]],
    policy_summary: dict[str, Any],
    risk: dict[str, Any] | None,
    evidence: dict[str, dict[str, Any]],
    audit_chain: dict[str, Any],
) -> dict[str, Any]:
    controls = [
        {**result, "nist_ai_rmf_function": NIST_AI_RMF_FUNCTION.get(result["category"], "-")}
        for result in policy_results
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": {
            key: model.get(key)
            for key in ("id", "name", "version", "framework", "owner", "impact_tier", "sha256")
        },
        "summary": policy_summary,
        "risk": {"score": risk["score"], "level": risk["level"]} if risk else None,
        "controls": controls,
        "evidence": {
            kind: {"id": item["id"], "status": item["status"], "created_at": item["created_at"]}
            for kind, item in sorted(evidence.items())
        },
        "audit_chain": {
            "valid": audit_chain["valid"],
            "events_checked": audit_chain["events_checked"],
            "head_hash": audit_chain.get("head_hash"),
        },
        "disclaimer": DISCLAIMER,
    }


def render_markdown(report: dict[str, Any]) -> str:
    model = report["model"]
    summary = report["summary"]
    lines = [
        f"# Governance evidence report: {model['name']} {model['version']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Model ID: `{model['id']}`",
        f"- SHA-256: `{model['sha256']}`",
        f"- Owner: {model['owner'] or 'not recorded'}",
        f"- Impact tier: {model['impact_tier']}",
        f"- Policy result: **{summary['status'].upper()}** "
        f"({summary['pass']} passed, {summary['fail']} failed, "
        f"{summary['not_applicable']} not applicable)",
    ]
    if report["risk"]:
        lines.append(f"- Risk: {report['risk']['level']} ({report['risk']['score']}/100)")
    chain = report["audit_chain"]
    lines.append(
        f"- Audit chain: {'verified' if chain['valid'] else 'FAILED VERIFICATION'} "
        f"({chain['events_checked']} events)"
    )
    lines += [
        "",
        "## Controls",
        "",
        "| Policy | Control | Status | NIST AI RMF | Evidence | Explanation |",
        "|---|---|---|---|---|---|",
    ]
    for control in report["controls"]:
        refs = ", ".join(control["evidence_refs"]) or "-"
        lines.append(
            f"| {control['policy_id']} | {control['title']} | {control['status']} | "
            f"{control['nist_ai_rmf_function']} | {refs} | {control['explanation']} |"
        )
    failed = [c for c in report["controls"] if c["status"] in ("fail", "error")]
    if failed:
        lines += ["", "## Corrective actions", ""]
        lines += [f"- **{c['policy_id']}**: {c['remediation']}" for c in failed]
    lines += ["", "## Evidence on record", ""]
    for kind, item in report["evidence"].items():
        lines.append(f"- {kind}: `{item['id']}` ({item['status']}, {item['created_at']})")
    lines += ["", "---", "", report["disclaimer"], ""]
    return "\n".join(lines)
