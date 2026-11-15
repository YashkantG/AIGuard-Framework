"""Input-perturbation robustness testing.

This measures how often small random perturbations change a model's output.
It is a black-box smoke test: it does not search for worst-case adversarial
examples, so a high stability score is not evidence of adversarial robustness.
"""

from collections.abc import Callable
from typing import Any, Literal

import numpy as np

PredictFn = Callable[[np.ndarray], Any]


def robustness_test(
    predict_fn: PredictFn,
    X: Any,
    *,
    epsilon: float = 0.05,
    n_trials: int = 10,
    task: Literal["classification", "regression"] = "classification",
    seed: int = 0,
) -> dict[str, Any]:
    """Perturb each feature by up to ``epsilon`` standard deviations and compare outputs.

    Two perturbation types are used: Gaussian noise, and "corner" noise where
    every feature moves by exactly ``epsilon`` standard deviations in a random
    direction (the largest step inside the same box).
    """
    data = np.asarray(X, dtype=float)
    if data.ndim != 2 or data.shape[0] == 0:
        raise ValueError("X must be a non-empty 2-D array")
    if epsilon <= 0 or n_trials <= 0:
        raise ValueError("epsilon and n_trials must be positive")

    rng = np.random.default_rng(seed)
    scale = data.std(axis=0)
    scale[scale == 0] = 1.0
    baseline = np.asarray(predict_fn(data))

    results: dict[str, list[float]] = {"gaussian": [], "corner": []}
    for _ in range(n_trials):
        noise = {
            "gaussian": rng.normal(0.0, epsilon, size=data.shape) * scale,
            "corner": rng.choice([-epsilon, epsilon], size=data.shape) * scale,
        }
        for kind, delta in noise.items():
            perturbed = np.asarray(predict_fn(data + delta))
            if task == "classification":
                results[kind].append(float(np.mean(perturbed != baseline)))
            else:
                results[kind].append(float(np.mean(np.abs(perturbed - baseline))))

    metric = "flip_rate" if task == "classification" else "mean_abs_change"
    summary = {
        kind: {"mean": float(np.mean(v)), "max": float(np.max(v))} for kind, v in results.items()
    }
    worst = max(s["max"] for s in summary.values())
    report: dict[str, Any] = {
        "task": task,
        "metric": metric,
        "epsilon": epsilon,
        "n_trials": n_trials,
        "n_samples": int(data.shape[0]),
        "perturbations": summary,
        "worst_case_observed": worst,
        "limitations": (
            "Random perturbations only. This is not a worst-case adversarial attack; "
            "use a dedicated attack library for that."
        ),
    }
    if task == "classification":
        report["stability"] = 1.0 - worst
    return report
