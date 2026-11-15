"""Transparent, additive risk scoring.

The score is a sum of documented factors (0-100). It is a prioritisation aid
built from the evidence AIGuard holds; it is not a measure of real-world harm
and does not replace a risk review by people who know the use case.
"""

from typing import Any

_TIER_POINTS = {"minimal": 5, "limited": 15, "high": 30}
_SEVERITY_POINTS = {"critical": 25, "high": 18, "medium": 8, "low": 3, "info": 0}


def _level(score: int) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    return "high" if score < 75 else "critical"


def assess_risk(model: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Score a model from its metadata and its latest evidence per kind."""
    factors: list[dict[str, Any]] = []

    def add(name: str, points: int, maximum: int, rationale: str) -> None:
        factors.append(
            {"factor": name, "points": points, "max_points": maximum, "rationale": rationale}
        )

    tier = model.get("impact_tier", "limited")
    add("Declared impact", _TIER_POINTS.get(tier, 15), 30, f"Impact tier is '{tier}'.")

    security = evidence.get("security_assessment")
    if security is None:
        add("Security findings", 15, 25, "No security assessment has been run.")
    else:
        worst = security["payload"].get("highest_severity")
        add(
            "Security findings",
            _SEVERITY_POINTS.get(worst or "info", 0),
            25,
            f"Highest open finding: {worst or 'none'}.",
        )

    integrity = evidence.get("integrity")
    if integrity is None:
        add("Artifact integrity", 10, 20, "Integrity has never been verified.")
    elif integrity["status"] != "pass":
        add("Artifact integrity", 20, 20, "The latest integrity verification failed.")
    else:
        add("Artifact integrity", 0, 20, "The latest integrity verification passed.")

    drift = evidence.get("drift")
    if drift is None:
        add("Drift", 6, 10, "Drift has never been evaluated.")
    elif drift["status"] == "drift_detected":
        add("Drift", 10, 10, "The latest drift evaluation detected drift.")
    else:
        add("Drift", 0, 10, "The latest drift evaluation was stable.")

    required = ["description", "owner", "intended_use"]
    if tier == "high":
        required.append("human_oversight")
    missing = [f for f in required if not str(model.get(f) or "").strip()]
    gap_points = min(10, round(10 * len(missing) / len(required)))
    add(
        "Documentation gaps",
        gap_points,
        10,
        "Missing: " + ", ".join(missing) + "." if missing else "Documentation is complete.",
    )

    if evidence.get("explanation") is None:
        add("Explainability", 5, 5, "No explanation has been generated.")
    else:
        add("Explainability", 0, 5, "An explanation is on record.")

    score = sum(f["points"] for f in factors)
    return {
        "score": score,
        "max_score": 100,
        "level": _level(score),
        "factors": factors,
        "notice": "Indicative score derived from recorded evidence; not a substitute for review.",
    }
