"""Example 4: the full lifecycle on a real scikit-learn model (synthetic data).

    pip install -e ".[dev]"
    python examples/04_full_lifecycle.py

Trains a small scikit-learn model, registers it, and walks through integrity,
security, drift, explainability, lineage, risk and policy evaluation.
"""

import pickle
import tempfile
from pathlib import Path

import numpy as np
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

from aiguard import AIGuard, Settings
from aiguard.core.models import DriftFeature, DriftRequest, LineageNodeCreate, ModelCreate
from aiguard.explainability import permutation_importance
from aiguard.governance import render_markdown
from aiguard.provenance import fingerprint_file
from aiguard.security import robustness_test


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="aiguard-quickstart-"))
    artifacts = work / "artifacts"
    artifacts.mkdir()
    database_url = f"sqlite:///{(work / 'aiguard.db').as_posix()}"
    guard = AIGuard(Settings(database_url=database_url, artifact_dir=artifacts))

    # 1. Train a model on synthetic data and save the artifacts.
    X, y = make_classification(n_samples=600, n_features=5, n_informative=3, random_state=0)
    names = [f"feature_{i}" for i in range(X.shape[1])]
    classifier = LogisticRegression(max_iter=500).fit(X[:400], y[:400])
    np.savetxt(artifacts / "train.csv", X[:400], delimiter=",")
    (artifacts / "classifier.pkl").write_bytes(pickle.dumps(classifier))

    # 2. Register it: the SHA-256 digest is recorded.
    model = guard.register_model(
        ModelCreate(
            name="quickstart-classifier",
            version="1.0.0",
            framework="scikit-learn",
            artifact_path="classifier.pkl",
            owner="You",
            description="Logistic regression on synthetic data.",
            intended_use="Demonstrating AIGuard.",
        )
    )
    model_id = model["id"]
    print(f"Registered {model_id} sha256={model['sha256'][:16]}...")

    # 3. Lineage: dataset -> training run -> model.
    dataset = guard.add_lineage_node(
        LineageNodeCreate(
            node_type="dataset",
            name="synthetic-train",
            fingerprint=fingerprint_file(artifacts / "train.csv"),
            attributes={"rows": 400},
        )
    )
    run = guard.add_lineage_node(
        LineageNodeCreate(node_type="training_run", name="run-1", attributes={"max_iter": 500})
    )
    guard.add_lineage_edge(dataset["id"], run["id"])
    guard.add_lineage_edge(run["id"], guard.model_node_id(model_id))

    # 4. Integrity and security.
    print("Integrity verified:", guard.verify_integrity(model_id)["verified"])
    assessment = guard.assess_security(model_id)
    print(f"Security: {assessment['status']} (highest: {assessment['highest_severity']})")
    for finding in assessment["findings"]:
        print(f"  [{finding['severity']}] {finding['title']}")

    # 5. Drift: compare training data with held-out data.
    drift = guard.evaluate_drift(
        model_id,
        DriftRequest(
            features={
                name: DriftFeature(reference=X[:400, i].tolist(), current=X[400:, i].tolist())
                for i, name in enumerate(names)
            }
        ),
    )
    print("Drift detected:", drift["drift_detected"], drift["drifted_features"])

    # 6. Explainability and robustness, run locally against the live model.
    importance = permutation_importance(classifier.predict, X[400:], y[400:], feature_names=names)
    guard.record_explanation(model_id, importance)
    print("Most important feature:", importance["features"][0]["feature"])
    stability = robustness_test(classifier.predict, X[400:], epsilon=0.05)["stability"]
    print(f"Stability under 0.05 sigma noise: {stability:.2%}")

    # 7. Risk and governance policies.
    risk = guard.assess_risk(model_id)
    print(f"Risk: {risk['level']} ({risk['score']}/100)")
    evaluation = guard.evaluate_policies(model_id)
    for result in evaluation["results"]:
        print(f"  {result['status']:<15}{result['policy_id']}  {result['explanation']}")

    report = work / "report.md"
    report.write_text(render_markdown(guard.compliance_report(model_id)), encoding="utf-8")
    print("Audit chain valid:", guard.verify_audit_chain()["valid"])
    print("Evidence report:", report)


if __name__ == "__main__":
    main()
