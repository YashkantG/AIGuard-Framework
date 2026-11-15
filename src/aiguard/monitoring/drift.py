"""Model Drift Detection Engine.

Numeric features use the Population Stability Index (PSI) and the two-sample
Kolmogorov-Smirnov test; categorical features use PSI over category
frequencies. The same functions apply to prediction distributions.

PSI thresholds of 0.1 and 0.25 are an industry rule of thumb, not a
statistical guarantee. Tune them for your data and sample sizes.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import stats

_FLOOR = 1e-4
MIN_RELIABLE_SAMPLES = 30


def _clean_numeric(values: Sequence[Any], label: str) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float).ravel()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} sample contains non-numeric values") from exc
    array = array[np.isfinite(array)]
    if array.size == 0:
        raise ValueError(f"{label} sample has no finite values")
    return array


def _psi_from_proportions(reference: np.ndarray, current: np.ndarray) -> float:
    ref = np.clip(reference, _FLOOR, None)
    cur = np.clip(current, _FLOOR, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def population_stability_index(
    reference: Sequence[Any], current: Sequence[Any], bins: int = 10
) -> float:
    """PSI between two numeric samples, binned on reference quantiles."""
    ref = _clean_numeric(reference, "reference")
    cur = _clean_numeric(current, "current")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if edges.size < 2:
        # Constant reference: everything not equal to that value has drifted.
        constant = edges[0]
        ref_p = np.array([1.0, 0.0])
        cur_same = float(np.mean(cur == constant))
        cur_p = np.array([cur_same, 1.0 - cur_same])
        return _psi_from_proportions(ref_p, cur_p)
    edges = edges.astype(float)
    edges[0], edges[-1] = -np.inf, np.inf
    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)
    return _psi_from_proportions(ref_counts / ref.size, cur_counts / cur.size)


def categorical_psi(reference: Sequence[Any], current: Sequence[Any]) -> float:
    """PSI over category frequencies; unseen categories count as drift."""
    if len(reference) == 0 or len(current) == 0:
        raise ValueError("samples must not be empty")
    ref_counts = Counter(str(v) for v in reference)
    cur_counts = Counter(str(v) for v in current)
    categories = sorted(set(ref_counts) | set(cur_counts))
    ref_p = np.array([ref_counts[c] / len(reference) for c in categories])
    cur_p = np.array([cur_counts[c] / len(current) for c in categories])
    return _psi_from_proportions(ref_p, cur_p)


def ks_test(reference: Sequence[Any], current: Sequence[Any]) -> dict[str, float]:
    """Two-sample Kolmogorov-Smirnov statistic and p-value."""
    result = stats.ks_2samp(
        _clean_numeric(reference, "reference"), _clean_numeric(current, "current")
    )
    return {"statistic": float(result.statistic), "p_value": float(result.pvalue)}


def _psi_level(psi: float) -> str:
    if psi < 0.1:
        return "stable"
    return "moderate" if psi < 0.25 else "significant"


def detect_feature_drift(
    name: str,
    reference: Sequence[Any],
    current: Sequence[Any],
    *,
    kind: str = "numeric",
    psi_threshold: float = 0.2,
    alpha: float = 0.05,
    min_ks_effect: float = 0.1,
) -> dict[str, Any]:
    """Assess one feature.

    A numeric feature is flagged when PSI reaches ``psi_threshold``, or when the
    KS test is significant *and* its statistic is at least ``min_ks_effect``.
    The effect-size condition stops large samples from flagging tiny shifts.
    """
    report: dict[str, Any] = {
        "feature": name,
        "kind": kind,
        "n_reference": len(reference),
        "n_current": len(current),
    }
    if kind == "categorical":
        psi = categorical_psi(reference, current)
        drifted = psi >= psi_threshold
    elif kind == "numeric":
        psi = population_stability_index(reference, current)
        ks = ks_test(reference, current)
        report["ks_statistic"] = ks["statistic"]
        report["ks_p_value"] = ks["p_value"]
        ks_flag = ks["p_value"] < alpha and ks["statistic"] >= min_ks_effect
        drifted = psi >= psi_threshold or ks_flag
        report["reference_mean"] = float(np.mean(_clean_numeric(reference, "reference")))
        report["current_mean"] = float(np.mean(_clean_numeric(current, "current")))
    else:
        raise ValueError(f"Unknown feature kind {kind!r}")
    report["psi"] = psi
    report["psi_level"] = _psi_level(psi)
    report["drift_detected"] = bool(drifted)
    report["low_sample_warning"] = (
        min(len(reference), len(current)) < MIN_RELIABLE_SAMPLES
    )
    return report


def detect_drift(
    features: Mapping[str, Mapping[str, Any]],
    *,
    psi_threshold: float = 0.2,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Assess several features: ``{name: {"reference": [...], "current": [...], "kind": ...}}``."""
    reports = [
        detect_feature_drift(
            name,
            spec["reference"],
            spec["current"],
            kind=spec.get("kind", "numeric"),
            psi_threshold=psi_threshold,
            alpha=alpha,
        )
        for name, spec in features.items()
    ]
    drifted = [r["feature"] for r in reports if r["drift_detected"]]
    return {
        "drift_detected": bool(drifted),
        "drifted_features": drifted,
        "features": reports,
        "psi_threshold": psi_threshold,
        "alpha": alpha,
        "methods": ["population_stability_index", "kolmogorov_smirnov"],
    }


def detect_threshold_drift(
    reference_value: float, current_value: float, threshold: float = 0.10
) -> dict[str, Any]:
    """Compare a single metric (e.g. accuracy) with its reference value."""
    difference = abs(current_value - reference_value)
    return {
        "drift_detected": difference > threshold,
        "difference": difference,
        "threshold": threshold,
    }
