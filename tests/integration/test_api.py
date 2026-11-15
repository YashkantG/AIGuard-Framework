"""End-to-end flows through the REST API."""

import hashlib
import os
import pickle

import numpy as np

from tests.conftest import ANALYST, VIEWER


def register(client, **overrides):
    body = {"name": "fraud", "version": "1.0.0", **overrides}
    if "artifact_path" not in body:
        body.setdefault("sha256", "a" * 64)
    return client.post("/api/v1/models", json=body, headers=ANALYST)


def test_register_get_list(client, benign_artifact):
    response = register(client, artifact_path=benign_artifact.name, owner="Risk")
    assert response.status_code == 201
    model = response.json()
    assert model["sha256"] == hashlib.sha256(benign_artifact.read_bytes()).hexdigest()
    assert model["artifact_available"] and model["created_by"] == "api:ci"

    fetched = client.get(f"/api/v1/models/{model['id']}", headers=VIEWER).json()
    assert fetched["owner"] == "Risk"
    assert fetched["posture"]["integrity"] is None
    assert [m["id"] for m in client.get("/api/v1/models", headers=VIEWER).json()] == [model["id"]]


def test_duplicate_version_conflicts_and_missing_is_404(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert register(client, version="1.0.1").status_code == 201
    assert client.get("/api/v1/models/mdl_missing", headers=VIEWER).status_code == 404


def test_supplied_digest_must_match_artifact(client, benign_artifact):
    response = register(client, artifact_path=benign_artifact.name, sha256="b" * 64)
    assert response.status_code == 422


def test_integrity_verification_detects_tampering(client, model, benign_artifact):
    url = f"/api/v1/models/{model['id']}/verify"
    assert client.post(url, headers=ANALYST).json()["verified"] is True

    benign_artifact.write_bytes(benign_artifact.read_bytes() + b"\x00")
    result = client.post(url, headers=ANALYST).json()
    assert result["verified"] is False
    assert result["expected"] != result["actual"]
    posture = client.get(f"/api/v1/models/{model['id']}", headers=VIEWER).json()["posture"]
    assert posture["integrity"] == "fail"


def test_verify_with_client_digest_for_digest_only_model(client):
    model = register(client).json()
    url = f"/api/v1/models/{model['id']}/verify"
    assert client.post(url, headers=ANALYST).status_code == 422  # nothing to compare
    assert client.post(url, json={"sha256": "A" * 64}, headers=ANALYST).json()["verified"]
    result = client.post(url, json={"sha256": "c" * 64}, headers=ANALYST).json()
    assert not result["verified"] and result["source"] == "client_supplied_digest"


def test_security_assessment_flags_malicious_artifact(client, artifact_dir):
    class Payload:
        def __reduce__(self):
            return os.system, ("echo x",)

    (artifact_dir / "evil.pkl").write_bytes(pickle.dumps(Payload()))
    model = register(client, artifact_path="evil.pkl").json()
    result = client.post(f"/api/v1/models/{model['id']}/assess", headers=ANALYST).json()
    assert result["status"] == "fail"
    assert result["highest_severity"] == "critical"
    assert result["counts"]["critical"] == 1
    assert {"AIG-SER-002", "AIG-INT-001"} <= {f["id"] for f in result["findings"]}


def test_assessment_with_config_and_requirements(client, model):
    url = f"/api/v1/models/{model['id']}"
    client.post(f"{url}/verify", headers=ANALYST)
    body = {"deployment_config": {"tls_enabled": False}, "requirements": "numpy\n"}
    result = client.post(f"{url}/assess", json=body, headers=ANALYST).json()
    found = {f["id"] for f in result["findings"]}
    assert "AIG-DEP-001" in found and "AIG-INT-001" not in found
    assert any(f["location"] == "tls_enabled" and f["severity"] == "high" for f in result["findings"])


def test_drift_endpoint(client, model):
    rng = np.random.default_rng(0)
    body = {
        "features": {
            "stable": {"reference": rng.normal(size=300).tolist(), "current": rng.normal(size=300).tolist()},
            "shifted": {"reference": rng.normal(size=300).tolist(), "current": rng.normal(3, 1, 300).tolist()},
            "plan": {"reference": ["a", "b"] * 50, "current": ["a", "b"] * 50, "kind": "categorical"},
        }
    }  # fmt: skip
    url = f"/api/v1/models/{model['id']}/drift"
    result = client.post(url, json=body, headers=ANALYST).json()
    assert result["status"] == "drift_detected"
    assert result["drifted_features"] == ["shifted"]

    bad = {"features": {"x": {"reference": ["a", "b"], "current": [1, 2]}}}
    assert client.post(url, json=bad, headers=ANALYST).status_code == 422


def test_explain_endpoint(client, model):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(100, 2))
    body = {"feature_names": ["big", "small"], "X": X.tolist(), "predictions": (5 * X[:, 0] + X[:, 1]).tolist()}
    url = f"/api/v1/models/{model['id']}/explain"
    result = client.post(url, json=body, headers=ANALYST).json()
    assert result["features"][0]["feature"] == "big"
    assert result["fidelity_r2"] > 0.99
    assert "not real-world causation" in result["notice"]

    body["feature_names"] = ["only-one"]
    assert client.post(url, json=body, headers=ANALYST).status_code == 422


def test_full_governance_flow(client, model):
    mid = model["id"]
    url = f"/api/v1/models/{mid}"
    evaluate = lambda: client.post(  # noqa: E731
        "/api/v1/policies/evaluate", json={"model_id": mid}, headers=ANALYST
    ).json()

    first = evaluate()
    assert first["summary"]["status"] == "fail"
    failed = {r["policy_id"] for r in first["results"] if r["status"] == "fail"}
    assert {"GOV-PRV-001", "GOV-INT-001", "GOV-SEC-001", "GOV-XAI-001", "GOV-MON-001"} <= failed

    # Record lineage: dataset -> training run -> model.
    node = lambda **body: client.post("/api/v1/lineage/nodes", json=body, headers=ANALYST).json()  # noqa: E731
    dataset = node(node_type="dataset", name="train-set", fingerprint="d" * 64)
    run = node(node_type="training_run", name="run-1", attributes={"seed": 1})
    root = client.get(f"{url}/lineage", headers=VIEWER).json()["root"]
    for src, dst in [(dataset["id"], run["id"]), (run["id"], root)]:
        edge = client.post("/api/v1/lineage/edges", json={"src_id": src, "dst_id": dst}, headers=ANALYST)
        assert edge.status_code == 201

    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 2))
    client.post(f"{url}/verify", headers=ANALYST)
    client.post(f"{url}/assess", headers=ANALYST)
    client.post(
        f"{url}/drift",
        json={"features": {"x": {"reference": X[:, 0].tolist(), "current": X[:, 0].tolist()}}},
        headers=ANALYST,
    )
    client.post(
        f"{url}/explain",
        json={"feature_names": ["a", "b"], "X": X.tolist(), "predictions": X[:, 0].tolist()},
        headers=ANALYST,
    )
    risk = client.post(f"{url}/risk", headers=ANALYST).json()
    assert risk["level"] == "low"

    final = evaluate()
    assert final["summary"]["status"] == "pass", final["results"]
    assert final["summary"]["not_applicable"] == 1  # human oversight: high tier only

    lineage = client.get(f"{url}/lineage", headers=VIEWER).json()
    assert lineage["has_dataset"] and len(lineage["nodes"]) == 3

    report = client.get(f"{url}/report", headers=VIEWER).json()
    assert report["summary"]["status"] == "pass" and report["audit_chain"]["valid"]
    markdown = client.get(f"{url}/report.md", headers=VIEWER)
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "| GOV-INT-001 |" in markdown.text

    subset = client.post(
        "/api/v1/policies/evaluate",
        json={"model_id": mid, "policy_ids": ["GOV-INT-001"]},
        headers=ANALYST,
    ).json()
    assert subset["summary"]["total"] == 1
    unknown = client.post(
        "/api/v1/policies/evaluate", json={"model_id": mid, "policy_ids": ["NOPE"]}, headers=ANALYST
    )
    assert unknown.status_code == 422


def test_audit_trail_and_stats(client, model):
    mid = model["id"]
    client.post(f"/api/v1/models/{mid}/verify", headers=ANALYST)
    client.post(f"/api/v1/models/{mid}/risk", headers=ANALYST)

    history = client.get(f"/api/v1/models/{mid}/audit", headers=VIEWER).json()
    assert [e["action"] for e in history] == ["model.risk", "model.verify", "model.register"]
    assert history[1]["evidence_refs"][0].startswith("ev_")
    for field in ("id", "timestamp", "actor", "model_version", "category", "result", "event_hash"):
        assert history[0][field]

    chain = client.get("/api/v1/audit/verify", headers=VIEWER).json()
    assert chain["valid"] and chain["events_checked"] == 3
    assert len(client.get("/api/v1/audit?limit=2", headers=VIEWER).json()) == 2

    stats = client.get("/api/v1/stats", headers=VIEWER).json()
    assert stats["models"] == 1 and stats["audit_events"] == 3
    assert stats["integrity"] == {"pass": 1}
    assert stats["policy"] == {"not_evaluated": 1}

    evidence = client.get(f"/api/v1/models/{mid}/evidence", headers=VIEWER).json()
    assert set(evidence) == {"integrity", "risk_assessment"}


def test_lineage_rules_over_api(client, model):
    model_node = lambda: client.post(  # noqa: E731
        "/api/v1/lineage/nodes", json={"node_type": "model_version", "name": "x"}, headers=ANALYST
    )
    assert model_node().status_code == 422  # only registration creates these
    bad_edge = client.post(
        "/api/v1/lineage/edges", json={"src_id": "ln_a", "dst_id": "ln_b"}, headers=ANALYST
    )
    assert bad_edge.status_code == 404


def test_dashboard_assets_are_served(client):
    assert "AIGuard" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/api/openapi.json").json()["info"]["title"] == "AIGuard Framework"
