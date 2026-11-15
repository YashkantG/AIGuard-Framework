"""Request schemas shared by the SDK, CLI and REST API."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[A-Fa-f0-9]{64}$")]
ImpactTier = Literal["minimal", "limited", "high"]
NodeType = Literal[
    "dataset", "transformation", "training_run", "model_version", "evaluation", "deployment"
]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class ModelCreate(Schema):
    name: str = Field(min_length=1, max_length=200, pattern=r"^[\w .\-/]+$")
    version: str = Field(min_length=1, max_length=50, pattern=r"^[\w.\-+]+$")
    framework: str = Field(default="unknown", max_length=50)
    #: Path relative to the configured artifact directory.
    artifact_path: str | None = Field(default=None, max_length=1024)
    #: Required when no artifact_path is given.
    sha256: Sha256 | None = None
    owner: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=5000)
    intended_use: str = Field(default="", max_length=5000)
    impact_tier: ImpactTier = "limited"
    human_oversight: str = Field(default="", max_length=2000)
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _needs_artifact_or_hash(self) -> "ModelCreate":
        if not self.artifact_path and not self.sha256:
            raise ValueError("Provide artifact_path or sha256")
        return self


class VerifyRequest(Schema):
    artifact_path: str | None = Field(default=None, max_length=1024)
    sha256: Sha256 | None = None


class AssessRequest(Schema):
    #: Declared deployment controls, e.g. ``{"tls_enabled": true}``.
    deployment_config: dict[str, bool] | None = None
    #: Contents of a requirements.txt file to check for unpinned dependencies.
    requirements: str | None = Field(default=None, max_length=200_000)


class DriftFeature(Schema):
    reference: list[float | str] = Field(min_length=1, max_length=100_000)
    current: list[float | str] = Field(min_length=1, max_length=100_000)
    kind: Literal["numeric", "categorical"] = "numeric"


class DriftRequest(Schema):
    features: dict[str, DriftFeature] = Field(min_length=1, max_length=200)
    psi_threshold: float = Field(default=0.2, gt=0, le=10)
    alpha: float = Field(default=0.05, gt=0, lt=1)


class ExplainRequest(Schema):
    feature_names: list[str] = Field(min_length=1, max_length=200)
    X: list[list[float]] = Field(min_length=3, max_length=5000)
    predictions: list[float] = Field(min_length=3, max_length=5000)


class PolicyEvaluateRequest(Schema):
    model_id: str
    policy_ids: list[str] | None = None


class LineageNodeCreate(Schema):
    node_type: NodeType
    name: str = Field(min_length=1, max_length=200)
    fingerprint: Sha256 | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class LineageEdgeCreate(Schema):
    src_id: str
    dst_id: str
