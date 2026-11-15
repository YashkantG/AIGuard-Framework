import numpy as np
import pytest

from aiguard.monitoring import (
    categorical_psi,
    detect_drift,
    detect_feature_drift,
    detect_threshold_drift,
    ks_test,
    population_stability_index,
)


@pytest.fixture
def rng():
    return np.random.default_rng(0)


def test_psi_is_near_zero_for_same_distribution(rng):
    assert population_stability_index(rng.normal(size=5000), rng.normal(size=5000)) < 0.02


def test_psi_grows_with_shift(rng):
    reference = rng.normal(size=5000)
    small = population_stability_index(reference, rng.normal(0.3, 1, 5000))
    large = population_stability_index(reference, rng.normal(1.5, 1, 5000))
    assert 0.02 < small < large
    assert large > 0.25


def test_psi_handles_constant_reference():
    assert population_stability_index([1.0] * 50, [1.0] * 50) == pytest.approx(0.0)
    assert population_stability_index([1.0] * 50, [2.0] * 50) > 1


def test_psi_ignores_nan_and_rejects_empty(rng):
    values = rng.normal(size=200).tolist()
    assert population_stability_index(values + [float("nan")], values) < 0.01
    with pytest.raises(ValueError):
        population_stability_index([float("nan")], values)
    with pytest.raises(ValueError):
        population_stability_index(["a", "b"], values)


def test_categorical_psi_detects_new_category():
    reference = ["a"] * 70 + ["b"] * 30
    assert categorical_psi(reference, reference) == pytest.approx(0.0)
    assert categorical_psi(reference, ["a"] * 40 + ["b"] * 30 + ["c"] * 30) > 0.25


def test_ks_test_separates_distributions(rng):
    same = ks_test(rng.normal(size=1000), rng.normal(size=1000))
    shifted = ks_test(rng.normal(size=1000), rng.normal(1, 1, 1000))
    assert same["p_value"] > 0.01
    assert shifted["p_value"] < 1e-6
    assert shifted["statistic"] > same["statistic"]


def test_large_sample_tiny_shift_is_not_flagged(rng):
    # Statistically significant but practically negligible: the effect-size guard applies.
    report = detect_feature_drift(
        "x", rng.normal(size=200_000), rng.normal(0.03, 1, 200_000)
    )
    assert report["ks_p_value"] < 0.05
    assert not report["drift_detected"]


def test_detect_drift_report(rng):
    report = detect_drift(
        {
            "stable": {"reference": rng.normal(size=800), "current": rng.normal(size=800)},
            "shifted": {"reference": rng.normal(size=800), "current": rng.normal(2, 1, 800)},
            "category": {
                "reference": ["a", "b"] * 100,
                "current": ["a"] * 200,
                "kind": "categorical",
            },
        }
    )
    assert report["drift_detected"]
    assert report["drifted_features"] == ["shifted", "category"]
    assert all(isinstance(f["psi"], float) for f in report["features"])


def test_low_sample_warning_and_unknown_kind():
    assert detect_feature_drift("x", [1, 2, 3], [1, 2, 4])["low_sample_warning"]
    with pytest.raises(ValueError):
        detect_feature_drift("x", [1], [1], kind="image")


def test_threshold_drift():
    assert detect_threshold_drift(0.90, 0.75)["drift_detected"]
    assert not detect_threshold_drift(0.90, 0.85)["drift_detected"]
