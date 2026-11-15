"""Model Integrity Engine: SHA-256 fingerprints and signed manifests."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_CHUNK = 1024 * 1024


def calculate_model_hash(model_path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    sha256 = hashlib.sha256()
    with open(model_path, "rb") as model_file:
        for chunk in iter(lambda: model_file.read(_CHUNK), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_model_integrity(model_path: str | Path, expected_hash: str) -> bool:
    """True when the file's digest matches ``expected_hash`` (constant-time compare)."""
    actual = calculate_model_hash(model_path)
    return hmac.compare_digest(actual, expected_hash.strip().lower())


def build_manifest(model_path: str | Path, **metadata: Any) -> dict[str, Any]:
    """Describe an artifact so it can be verified later, optionally with a signature."""
    path = Path(model_path)
    return {
        "artifact": path.name,
        "algorithm": "sha256",
        "digest": calculate_model_hash(path),
        "size_bytes": path.stat().st_size,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "metadata": metadata,
    }


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    unsigned = {k: v for k, v in manifest.items() if k != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_manifest(manifest: dict[str, Any], key: bytes) -> dict[str, Any]:
    """Return a copy of the manifest with an HMAC-SHA256 signature.

    HMAC needs the verifier to hold the same secret. Use an asymmetric scheme
    (for example Sigstore) when verifiers must not be able to sign.
    """
    if len(key) < 32:
        raise ValueError("Signing key must be at least 32 bytes")
    signature = hmac.new(key, _manifest_bytes(manifest), hashlib.sha256).hexdigest()
    return {**manifest, "signature": {"algorithm": "hmac-sha256", "value": signature}}


def verify_manifest_signature(manifest: dict[str, Any], key: bytes) -> bool:
    signature = manifest.get("signature") or {}
    if signature.get("algorithm") != "hmac-sha256":
        return False
    expected = hmac.new(key, _manifest_bytes(manifest), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature.get("value", "")))
