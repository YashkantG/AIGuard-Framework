import numpy as np
import pytest

from aiguard.explainability import (
    ATTRIBUTION_NOTICE,
    local_attribution,
    permutation_importance,
    surrogate_explanation,
)
from aiguard.security import robustness_test


@pytest.fixture
def data():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 3))
    return X, ["strong", "weak", "noise"]


def score(X):
    return 3.0 * X[:, 0] + 0.5 * X[:, 1]


def classify(X):
    return (score(X) > 0).astype(int)


def test_permutation_importance_ranks_features(data):
    X, names = data
    report = permutation_importance(classify, X, classify(X), feature_names=names)
    assert [f["feature"] for f in report["features"]][0] == "strong"
    by_name = {f["feature"]: f["importance"] for f in report["features"]}
    assert by_name["strong"] > by_name["weak"] > by_name["noise"] - 1e-9
    assert by_name["noise"] == pytest.approx(0.0)
    assert report["notice"] == ATTRIBUTION_NOTICE


def test_local_attribution_matches_linear_model(data):
    X, names = data
    report = local_attribution(score, [2.0, 2.0, 2.0], X, feature_names=names)
    by_name = {f["feature"]: f["importance"] for f in report["features"]}
    mean = X.mean(axis=0)
    assert by_name["strong"] == pytest.approx(3.0 * (2.0 - mean[0]))
    assert by_name["weak"] == pytest.approx(0.5 * (2.0 - mean[1]))
    assert by_name["noise"] == pytest.approx(0.0)


def test_surrogate_recovers_linear_weights(data):
    X, names = data
    report = surrogate_explanation(X, score(X), feature_names=names)
    assert report["fidelity_r2"] == pytest.approx(1.0)
    assert report["features"][0]["feature"] == "strong"
    assert sum(f["importance"] for f in report["features"]) == pytest.approx(1.0)
    assert report["features"][0]["coefficient"] > 0


def test_surrogate_reports_low_fidelity_for_nonlinear_model(data):
    X, _ = data
    report = surrogate_explanation(X, X[:, 0] ** 2)
    assert report["fidelity_r2"] < 0.3


def test_surrogate_input_validation():
    with pytest.raises(ValueError):
        surrogate_explanation([[1.0, 2.0], [2.0, 3.0]], [1.0, 2.0])  # too few rows
    with pytest.raises(ValueError):
        surrogate_explanation([[1.0], [2.0], [3.0]], [1.0, 2.0])  # length mismatch
    with pytest.raises(ValueError):
        surrogate_explanation([[1.0], [float("nan")], [3.0]], [1.0, 2.0, 3.0])


def test_robustness_distinguishes_stable_and_fragile_models(data):
    X, _ = data
    stable = robustness_test(lambda x: np.zeros(len(x), dtype=int), X)
    fragile = robustness_test(lambda x: (np.sin(500 * x[:, 0]) > 0).astype(int), X)
    assert stable["stability"] == 1.0
    assert fragile["stability"] < 0.8
    assert "not a worst-case" in stable["limitations"]


def test_robustness_regression_and_validation(data):
    X, _ = data
    report = robustness_test(score, X, task="regression", epsilon=0.1)
    assert report["metric"] == "mean_abs_change"
    assert report["worst_case_observed"] > 0
    with pytest.raises(ValueError):
        robustness_test(score, X, epsilon=0)
    with pytest.raises(ValueError):
        robustness_test(score, [1.0, 2.0])
