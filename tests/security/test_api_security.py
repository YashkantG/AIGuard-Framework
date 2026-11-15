"""Authentication, authorisation, input validation and resource limits."""

import pytest
from fastapi.testclient import TestClient

from aiguard import AIGuard, Settings
from aiguard.api import create_app
from tests.conftest import ADMIN, ANALYST, VIEWER

READ_ENDPOINTS = [
    "/api/v1/me", "/api/v1/stats", "/api/v1/models", "/api/v1/policies",
    "/api/v1/audit", "/api/v1/audit/verify", "/api/v1/models/mdl_x",
    "/api/v1/models/mdl_x/audit", "/api/v1/models/mdl_x/report",
]  # fmt: skip
WRITE_ENDPOINTS = [
    "/api/v1/models", "/api/v1/policies/evaluate", "/api/v1/lineage/nodes",
    "/api/v1/lineage/edges", "/api/v1/models/mdl_x/verify", "/api/v1/models/mdl_x/assess",
    "/api/v1/models/mdl_x/drift", "/api/v1/models/mdl_x/explain", "/api/v1/models/mdl_x/risk",
]  # fmt: skip


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_reads_require_a_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "wrong-key-0123456789"}).status_code == 401


@pytest.mark.parametrize("path", WRITE_ENDPOINTS)
def test_writes_require_a_key_and_the_analyst_role(client, path):
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers=VIEWER).status_code == 403


def test_authentication_runs_before_validation(client):
    # An unauthenticated caller must not learn anything from validation errors.
    response = client.post("/api/v1/models", json={"nonsense": True})
    assert response.status_code == 401


def test_roles(client, model):
    assert client.get("/api/v1/me", headers=VIEWER).json()["role"] == "viewer"
    assert client.get(f"/api/v1/models/{model['id']}", headers=VIEWER).status_code == 200
    assert client.post(f"/api/v1/models/{model['id']}/risk", headers=ANALYST).status_code == 200
    assert client.post(f"/api/v1/models/{model['id']}/risk", headers=ADMIN).status_code == 200


def test_actor_is_recorded_from_the_key_not_the_request(client, model):
    client.post(f"/api/v1/models/{model['id']}/risk", headers=ANALYST)
    latest = client.get(f"/api/v1/models/{model['id']}/audit", headers=VIEWER).json()[0]
    assert latest["actor"] == "api:ci"


@pytest.mark.parametrize(
    "artifact_path",
    ["../secret.txt", "..\\secret.txt", "sub/../../secret.txt", "/etc/passwd", "C:\\Windows\\win.ini"],
)
def test_artifact_path_cannot_escape_the_artifact_directory(client, artifact_dir, artifact_path):
    (artifact_dir.parent / "secret.txt").write_text("top secret")
    body = {"name": "m", "version": "1", "artifact_path": artifact_path}
    response = client.post("/api/v1/models", json=body, headers=ANALYST)
    assert response.status_code == 422
    assert "top secret" not in response.text


def test_symlink_escape_is_rejected(client, artifact_dir):
    outside = artifact_dir.parent / "outside.bin"
    outside.write_bytes(b"data")
    link = artifact_dir / "link.bin"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted on this system")
    body = {"name": "m", "version": "1", "artifact_path": "link.bin"}
    assert client.post("/api/v1/models", json=body, headers=ANALYST).status_code == 422


def test_verify_cannot_read_outside_files(client, model, artifact_dir):
    (artifact_dir.parent / "secret.txt").write_text("top secret")
    response = client.post(
        f"/api/v1/models/{model['id']}/verify",
        json={"artifact_path": "../secret.txt"},
        headers=ANALYST,
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"name": "m", "version": "1"},  # neither artifact nor digest
        {"name": "m", "version": "1", "sha256": "xyz"},
        {"name": "<script>alert(1)</script>", "version": "1", "sha256": "a" * 64},
        {"name": "m", "version": "1", "sha256": "a" * 64, "impact_tier": "extreme"},
        {"name": "m", "version": "1", "sha256": "a" * 64, "unexpected": "field"},
        {"name": "m" * 500, "version": "1", "sha256": "a" * 64},
    ],
)
def test_invalid_registration_is_rejected(client, body):
    assert client.post("/api/v1/models", json=body, headers=ANALYST).status_code == 422


def test_oversized_inputs_are_rejected(client, model):
    too_many_rows = {"feature_names": ["a"], "X": [[0.0]] * 5001, "predictions": [0.0] * 5001}
    url = f"/api/v1/models/{model['id']}"
    assert client.post(f"{url}/explain", json=too_many_rows, headers=ANALYST).status_code == 422
    assert client.get(f"{url}/audit?limit=100000", headers=VIEWER).status_code == 422

    response = client.post(
        f"{url}/assess", content=b"{}", headers={**ANALYST, "Content-Length": str(10**9)}
    )
    assert response.status_code == 413


def test_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert client.get("/api/v1/me", headers=VIEWER).headers["Cache-Control"] == "no-store"


def test_rate_limit(guard):
    guard.settings.rate_limit_per_minute = 3
    limited = TestClient(create_app(guard))
    codes = [limited.get("/api/v1/me", headers=VIEWER).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    # Limits are per caller.
    assert limited.get("/api/v1/me", headers=ADMIN).status_code == 200


def test_bootstrap_key_when_none_configured(artifact_dir, capsys):
    settings = Settings(database_url="sqlite://", artifact_dir=artifact_dir, api_keys="")
    open_client = TestClient(create_app(AIGuard(settings)))
    assert open_client.get("/api/v1/models").status_code == 401  # never unauthenticated
    key = capsys.readouterr().err.split("\n")[1].strip()
    assert open_client.get("/api/v1/me", headers={"X-API-Key": key}).json()["role"] == "admin"


@pytest.mark.parametrize("keys", ["nokey", "a:superuser:0123456789abcdef", "a:admin:short"])
def test_bad_key_configuration_fails_closed(artifact_dir, keys):
    settings = Settings(database_url="sqlite://", artifact_dir=artifact_dir, api_keys=keys)
    with pytest.raises(ValueError):
        create_app(AIGuard(settings))


def test_health_is_public_and_minimal(client):
    assert client.get("/healthz").json() == {"status": "ok"}
