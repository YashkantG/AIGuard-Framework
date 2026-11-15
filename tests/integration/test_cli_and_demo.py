import json
import os
import pickle

import pytest
from typer.testing import CliRunner

from aiguard.cli import app
from aiguard.config import get_settings
from aiguard.integrations.demo import seed_demo

runner = CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AIGUARD_DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    monkeypatch.setenv("AIGUARD_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_hash_and_scan_need_no_database(tmp_path):
    good = tmp_path / "ok.pkl"
    good.write_bytes(pickle.dumps({"a": 1}))
    assert len(runner.invoke(app, ["hash", str(good)]).output.strip()) == 64

    result = runner.invoke(app, ["scan", str(good)])
    assert result.exit_code == 0
    assert json.loads(result.output)["format"] == "pickle"
    assert runner.invoke(app, ["scan", str(good), "--fail-on", "medium"]).exit_code == 1

    class Payload:
        def __reduce__(self):
            return os.system, ("echo x",)

    bad = tmp_path / "bad.pkl"
    bad.write_bytes(pickle.dumps(Payload()))
    assert runner.invoke(app, ["scan", str(bad)]).exit_code == 1


def test_register_verify_gate_report(env):
    artifact = env / "model.bin"
    artifact.write_bytes(b"weights")
    result = runner.invoke(
        app, ["register", "demo", "1.0", str(artifact), "--owner", "me", "--description", "d"]
    )
    assert result.exit_code == 0, result.output
    model_id = json.loads(result.output)["id"]

    assert runner.invoke(app, ["verify", model_id]).exit_code == 0
    artifact.write_bytes(b"tampered")
    assert runner.invoke(app, ["verify", model_id]).exit_code == 1

    gate = runner.invoke(app, ["gate", model_id])
    assert gate.exit_code == 1
    assert "GOV-INT-001" in gate.output

    report = runner.invoke(app, ["report", model_id])
    assert report.exit_code == 0 and "# Governance evidence report: demo 1.0" in report.output
    assert runner.invoke(app, ["audit-verify"]).exit_code == 0
    assert runner.invoke(app, ["verify", "mdl_missing"]).exit_code == 2


def test_demo_seed_is_idempotent_and_covers_each_state(guard):
    assert len(seed_demo(guard)) == 3
    assert seed_demo(guard) == []  # second run registers nothing

    posture = {m["name"]: m["posture"] for m in guard.list_models()}
    assert posture["credit-scoring"]["policy"] == "pass"
    assert posture["churn-predictor"]["drift"] == "drift_detected"
    assert posture["sentiment-community"]["security"] == "fail"
    assert guard.verify_audit_chain()["valid"]
