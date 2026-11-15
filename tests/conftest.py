import pickle
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aiguard import AIGuard, Settings
from aiguard.api import create_app
from aiguard.core.models import ModelCreate

ADMIN = {"X-API-Key": "admin-key-0123456789"}
ANALYST = {"X-API-Key": "analyst-key-0123456789"}
VIEWER = {"X-API-Key": "viewer-key-0123456789"}
API_KEYS = (
    "alice:admin:admin-key-0123456789,"
    "ci:analyst:analyst-key-0123456789,"
    "auditor:viewer:viewer-key-0123456789"
)


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    return directory


@pytest.fixture
def settings(artifact_dir: Path) -> Settings:
    return Settings(database_url="sqlite://", artifact_dir=artifact_dir, api_keys=API_KEYS)


@pytest.fixture
def guard(settings: Settings) -> AIGuard:
    return AIGuard(settings)


@pytest.fixture
def client(guard: AIGuard) -> TestClient:
    return TestClient(create_app(guard))


@pytest.fixture
def benign_artifact(artifact_dir: Path) -> Path:
    path = artifact_dir / "model.pkl"
    path.write_bytes(pickle.dumps({"weights": [0.1, 0.2, 0.3]}, protocol=4))
    return path


@pytest.fixture
def model(guard: AIGuard, benign_artifact: Path) -> dict:
    return guard.register_model(
        ModelCreate(
            name="demo",
            version="1.0.0",
            framework="scikit-learn",
            artifact_path=benign_artifact.name,
            owner="ML Team",
            description="A demo model.",
            intended_use="Testing.",
        ),
        actor="test",
    )
