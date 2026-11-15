"""AI Explainability Engine.

Three model-agnostic methods need only NumPy:

* :func:`permutation_importance` - global importance from a prediction function.
* :func:`local_attribution` - per-prediction occlusion attribution.
* :func:`surrogate_explanation` - a linear surrogate fitted to recorded
  predictions, usable when the model itself must not be executed.

:func:`shap_explanation` wraps SHAP when the optional dependency is installed.

Every report carries :data:`ATTRIBUTION_NOTICE`: these methods describe how a
model's output relates to its inputs. They do not show causal effects.
"""

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

ATTRIBUTION_NOTICE = (
    "Feature attribution describes the model's behaviour, not real-world causation. "
    "A highly attributed feature is not proof that it causes the outcome."
)

PredictFn = Callable[[np.ndarray], Any]


def _names(feature_names: Sequence[str] | None, n_features: int) -> list[str]:
    if feature_names is None:
        return [f"feature_{i}" for i in range(n_features)]
    if len(feature_names) != n_features:
        raise ValueError("feature_names length does not match the number of columns")
    return [str(n) for n in feature_names]


def _as_matrix(X: Any) -> np.ndarray:
    data = np.asarray(X, dtype=float)
    if data.ndim != 2 or data.size == 0:
        raise ValueError("X must be a non-empty 2-D array")
    if not np.all(np.isfinite(data)):
        raise ValueError("X contains NaN or infinite values")
    return data


def _ranked(names: list[str], values: np.ndarray, **extra: np.ndarray) -> list[dict[str, Any]]:
    order = np.argsort(-np.abs(values))
    rows = []
    for i in order:
        row: dict[str, Any] = {"feature": names[i], "importance": float(values[i])}
        row.update({key: float(arr[i]) for key, arr in extra.items()})
        rows.append(row)
    return rows


def permutation_importance(
    predict_fn: PredictFn,
    X: Any,
    y: Any,
    *,
    feature_names: Sequence[str] | None = None,
    metric: Callable[[np.ndarray, np.ndarray], float] | None = None,
    n_repeats: int = 5,
    seed: int = 0,
) -> dict[str, Any]:
    """Global importance: drop in score when one feature's values are shuffled.

    ``metric(y_true, y_pred)`` must return a score where higher is better.
    Accuracy is used by default.
    """
    data = _as_matrix(X)
    target = np.asarray(y)
    if target.shape[0] != data.shape[0]:
        raise ValueError("X and y have different numbers of rows")
    names = _names(feature_names, data.shape[1])
    score = metric or (lambda t, p: float(np.mean(np.asarray(p) == t)))
    rng = np.random.default_rng(seed)
    baseline = score(target, np.asarray(predict_fn(data)))

    drops = np.zeros((data.shape[1], n_repeats))
    for column in range(data.shape[1]):
        for repeat in range(n_repeats):
            shuffled = data.copy()
            shuffled[:, column] = rng.permutation(shuffled[:, column])
            drops[column, repeat] = baseline - score(target, np.asarray(predict_fn(shuffled)))

    return {
        "method": "permutation_importance",
        "scope": "global",
        "baseline_score": float(baseline),
        "n_repeats": n_repeats,
        "features": _ranked(names, drops.mean(axis=1), std=drops.std(axis=1)),
        "notice": ATTRIBUTION_NOTICE,
    }


def local_attribution(
    predict_fn: PredictFn,
    x: Any,
    background: Any,
    *,
    feature_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Local occlusion attribution for one row.

    Each feature is replaced by its background mean; the attribution is the
    resulting change in the model output. ``predict_fn`` should return a
    numeric score (a probability or a regression value).
    """
    row = np.asarray(x, dtype=float).ravel()
    reference = _as_matrix(background).mean(axis=0)
    if reference.shape[0] != row.shape[0]:
        raise ValueError("x and background have different numbers of features")
    names = _names(feature_names, row.shape[0])

    occluded = np.tile(row, (row.shape[0], 1))
    np.fill_diagonal(occluded, reference)
    stacked = np.vstack([row, occluded])
    outputs = np.asarray(predict_fn(stacked), dtype=float).ravel()
    attributions = outputs[0] - outputs[1:]

    return {
        "method": "occlusion",
        "scope": "local",
        "prediction": float(outputs[0]),
        "features": _ranked(names, attributions, value=row),
        "notice": ATTRIBUTION_NOTICE,
    }


def surrogate_explanation(
    X: Any, predictions: Any, *, feature_names: Sequence[str] | None = None
) -> dict[str, Any]:
    """Fit a linear surrogate to recorded (input, prediction) pairs.

    The model is never executed. ``fidelity_r2`` says how well the surrogate
    reproduces the predictions; a low value means the linear picture is a poor
    summary of the model and the importances should not be relied on.
    """
    data = _as_matrix(X)
    target = np.asarray(predictions, dtype=float).ravel()
    n_rows, n_features = data.shape
    if target.shape[0] != n_rows:
        raise ValueError("X and predictions have different numbers of rows")
    if n_rows < n_features + 2:
        raise ValueError("Need at least n_features + 2 rows to fit a surrogate")
    names = _names(feature_names, n_features)

    mean, std = data.mean(axis=0), data.std(axis=0)
    varying = std > 0
    standardized = np.zeros_like(data)
    standardized[:, varying] = (data[:, varying] - mean[varying]) / std[varying]
    design = np.column_stack([np.ones(n_rows), standardized])
    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)

    residual = target - design @ coefficients
    total = float(np.sum((target - target.mean()) ** 2))
    fidelity = 1.0 - float(np.sum(residual**2)) / total if total > 0 else 1.0
    weights = coefficients[1:]
    scale = float(np.sum(np.abs(weights))) or 1.0

    return {
        "method": "linear_surrogate",
        "scope": "global",
        "n_samples": n_rows,
        "fidelity_r2": fidelity,
        "intercept": float(coefficients[0]),
        "features": _ranked(names, np.abs(weights) / scale, coefficient=weights),
        "notice": ATTRIBUTION_NOTICE,
    }


def shap_explanation(
    predict_fn: PredictFn,
    X: Any,
    background: Any,
    *,
    feature_names: Sequence[str] | None = None,
    max_evals: int | None = None,
) -> dict[str, Any]:
    """SHAP feature attribution (requires ``pip install aiguard-framework[explain]``)."""
    try:
        import shap
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError("Install the 'explain' extra to use SHAP explanations") from exc

    data = _as_matrix(X)
    names = _names(feature_names, data.shape[1])
    explainer = shap.Explainer(predict_fn, _as_matrix(background), feature_names=names)
    kwargs = {"max_evals": max_evals} if max_evals else {}
    values = np.asarray(explainer(data, **kwargs).values)
    if values.ndim == 3:  # multi-output: average magnitude over outputs
        values = np.abs(values).mean(axis=2)
    return {
        "method": "shap",
        "scope": "global",
        "n_samples": int(data.shape[0]),
        "features": _ranked(names, np.abs(values).mean(axis=0)),
        "local_values": values.tolist(),
        "notice": ATTRIBUTION_NOTICE,
    }
