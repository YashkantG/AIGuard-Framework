"""Example 2: has the data changed since the model was trained?

    python examples/02_detect_drift.py

Compares training-time data with "current" data for three made-up features.
Income has shifted upwards, age has not, and a new payment method has appeared.
"""

import numpy as np

from aiguard.monitoring import detect_drift


def main() -> None:
    rng = np.random.default_rng(42)
    methods = ["card", "bank"]

    report = detect_drift(
        {
            "income": {
                "reference": rng.normal(50_000, 10_000, 1000),
                "current": rng.normal(58_000, 12_000, 1000),
            },
            "age": {
                "reference": rng.normal(40, 12, 1000),
                "current": rng.normal(40, 12, 1000),
            },
            "payment_method": {
                "reference": rng.choice(methods, 1000, p=[0.7, 0.3]),
                "current": rng.choice([*methods, "wallet"], 1000, p=[0.5, 0.2, 0.3]),
                "kind": "categorical",
            },
        }
    )

    print(f"{'feature':<16}{'PSI':>7}  result")
    for feature in report["features"]:
        result = "DRIFT" if feature["drift_detected"] else "stable"
        print(f"{feature['feature']:<16}{feature['psi']:>7.3f}  {result}")
    print("\nDrifted features:", ", ".join(report["drifted_features"]) or "none")


if __name__ == "__main__":
    main()
