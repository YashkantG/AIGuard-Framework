"""Synthetic demo data so the dashboard has something to show.

Everything here is generated: no real models or datasets are involved. The
"suspicious" artifact is a hand-written pickle that references ``os.system``
with a harmless ``echo``; AIGuard only disassembles it and never loads it.
"""

import hashlib
import json
import pickle
import struct
from pathlib import Path
from typing import Any

import numpy as np

from aiguard.core.errors import ConflictError
from aiguard.core.models import (
    AssessRequest,
    DriftFeature,
    DriftRequest,
    ExplainRequest,
    LineageNodeCreate,
    ModelCreate,
)
from aiguard.service import AIGuard

ACTOR = "demo-seed"


def _write_safetensors(path: Path, rng: np.random.Generator) -> None:
    weights = rng.normal(size=256).astype("<f4").tobytes()
    header = json.dumps(
        {"weights": {"dtype": "F32", "shape": [256], "data_offsets": [0, len(weights)]}}
    ).encode()
    path.write_bytes(struct.pack("<Q", len(header)) + header + weights)


def _write_benign_pickle(path: Path, rng: np.random.Generator) -> None:
    payload = {"coefficients": rng.normal(size=8).tolist(), "intercept": 0.25}
    path.write_bytes(pickle.dumps(payload, protocol=4))


def _write_suspicious_pickle(path: Path) -> None:
    # Protocol-0 opcodes: GLOBAL os.system, MARK, STRING, TUPLE, REDUCE, STOP.
    path.write_bytes(b"cos\nsystem\n(S'echo aiguard-demo'\ntR.")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _lineage(guard: AIGuard, model_id: str, dataset: str) -> None:
    def node(node_type: Any, name: str, fingerprint: str | None = None, **attrs: Any) -> str:
        created = guard.add_lineage_node(
            LineageNodeCreate(
                node_type=node_type, name=name, fingerprint=fingerprint, attributes=attrs
            ),
            ACTOR,
        )
        return str(created["id"])

    data = node("dataset", dataset, _sha(dataset), rows=48_000, source="synthetic")
    prep = node("transformation", "clean-and-encode", _sha(dataset + "prep"), script="prep.py")
    run = node("training_run", "train-2026-11", seed=42, learning_rate=0.05)
    evaluation = node("evaluation", "holdout-eval", auc=0.91)
    model_node = guard.model_node_id(model_id)
    for src, dst in [(data, prep), (prep, run), (run, model_node), (model_node, evaluation)]:
        guard.add_lineage_edge(src, dst, ACTOR)


def _drift_request(rng: np.random.Generator, shift: float) -> DriftRequest:
    def feature(mean: float, drift: float) -> DriftFeature:
        return DriftFeature(
            reference=rng.normal(mean, 1.0, 600).round(4).tolist(),
            current=rng.normal(mean + drift, 1.0 + drift / 2, 600).round(4).tolist(),
        )

    channels = ["web", "branch", "mobile"]
    return DriftRequest(
        features={
            "income": feature(5.0, shift),
            "account_age": feature(3.0, 0.0),
            "utilisation": feature(0.0, shift / 2),
            "channel": DriftFeature(
                reference=rng.choice(channels, 600, p=[0.5, 0.3, 0.2]).tolist(),
                current=rng.choice(
                    channels, 600, p=[0.5 - shift / 4, 0.3, 0.2 + shift / 4]
                ).tolist(),
                kind="categorical",
            ),
        }
    )


def _explain_request(rng: np.random.Generator) -> ExplainRequest:
    names = ["income", "account_age", "utilisation", "recent_enquiries", "tenure"]
    X = rng.normal(size=(300, len(names)))
    weights = np.array([1.6, 0.4, -1.1, -0.7, 0.1])
    scores = 1 / (1 + np.exp(-(X @ weights + rng.normal(0, 0.2, 300))))
    return ExplainRequest(
        feature_names=names, X=X.round(4).tolist(), predictions=scores.round(4).tolist()
    )


def seed_demo(guard: AIGuard) -> list[dict[str, Any]]:
    """Register three synthetic models in different governance states."""
    rng = np.random.default_rng(7)
    guard.artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_safetensors(guard.artifact_dir / "credit-scoring.safetensors", rng)
    _write_benign_pickle(guard.artifact_dir / "churn-model.pkl", rng)
    _write_suspicious_pickle(guard.artifact_dir / "sentiment-community.pkl")

    specs = [
        ModelCreate(
            name="credit-scoring",
            version="2.1.0",
            framework="pytorch",
            artifact_path="credit-scoring.safetensors",
            owner="Risk Analytics",
            description="Scores consumer credit applications (synthetic demo).",
            intended_use="Decision support for underwriters; not for automated rejection.",
            impact_tier="high",
            human_oversight="Underwriting lead reviews every decline; overrides are logged.",
        ),
        ModelCreate(
            name="churn-predictor",
            version="1.4.2",
            framework="scikit-learn",
            artifact_path="churn-model.pkl",
            owner="Growth",
            description="Predicts subscription churn in the next 30 days (synthetic demo).",
            intended_use="Prioritising retention campaigns.",
            impact_tier="limited",
        ),
        ModelCreate(
            name="sentiment-community",
            version="0.3.0",
            framework="unknown",
            artifact_path="sentiment-community.pkl",
            impact_tier="minimal",
        ),
    ]
    registered = []
    for spec in specs:
        try:
            registered.append(guard.register_model(spec, ACTOR))
        except ConflictError:
            continue
    if len(registered) < len(specs):
        return registered  # already seeded

    credit, churn, sentiment = (m["id"] for m in registered)
    secure_config = {
        "authentication_enabled": True,
        "tls_enabled": True,
        "integrity_check_on_load": True,
        "allow_pickle": False,
        "rate_limiting_enabled": True,
        "input_validation_enabled": True,
        "debug_mode": False,
        "runs_as_root": False,
        "egress_restricted": True,
    }

    # Well-governed model: everything on record.
    _lineage(guard, credit, "applications-2026Q3")
    guard.verify_integrity(credit, actor=ACTOR)
    guard.assess_security(credit, AssessRequest(deployment_config=secure_config), ACTOR)
    guard.evaluate_drift(credit, _drift_request(rng, 0.0), ACTOR)
    guard.explain(credit, _explain_request(rng), ACTOR)
    guard.assess_risk(credit, ACTOR)
    guard.evaluate_policies(credit, actor=ACTOR)

    # Partly governed model: drift detected, no lineage, loose configuration.
    guard.verify_integrity(churn, actor=ACTOR)
    guard.assess_security(
        churn,
        AssessRequest(
            deployment_config={
                **secure_config,
                "allow_pickle": True,
                "rate_limiting_enabled": False,
            },
            requirements="scikit-learn>=1.4\nnumpy\npandas==2.2.3\n",
        ),
        ACTOR,
    )
    guard.evaluate_drift(churn, _drift_request(rng, 0.9), ACTOR)
    guard.assess_risk(churn, ACTOR)
    guard.evaluate_policies(churn, actor=ACTOR)

    # Untrusted third-party artifact: scanner flags it.
    guard.assess_security(sentiment, actor=ACTOR)
    guard.assess_risk(sentiment, ACTOR)
    guard.evaluate_policies(sentiment, actor=ACTOR)
    return registered
