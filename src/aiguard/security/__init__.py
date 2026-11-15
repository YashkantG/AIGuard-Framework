"""Model integrity, artifact inspection and robustness testing."""

from aiguard.security.adversarial import robustness_test
from aiguard.security.integrity import (
    build_manifest,
    calculate_model_hash,
    sign_manifest,
    verify_manifest_signature,
    verify_model_integrity,
)
from aiguard.security.vulnerability import (
    Finding,
    check_deployment_config,
    check_requirements,
    scan_artifact,
)

__all__ = [
    "Finding",
    "build_manifest",
    "calculate_model_hash",
    "check_deployment_config",
    "check_requirements",
    "robustness_test",
    "scan_artifact",
    "sign_manifest",
    "verify_manifest_signature",
    "verify_model_integrity",
]
