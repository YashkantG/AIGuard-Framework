import hashlib

import pytest

from aiguard.security.integrity import (
    build_manifest,
    calculate_model_hash,
    sign_manifest,
    verify_manifest_signature,
    verify_model_integrity,
)


def test_hash_matches_hashlib(tmp_path):
    path = tmp_path / "m.bin"
    data = b"x" * (3 * 1024 * 1024 + 17)  # spans several read chunks
    path.write_bytes(data)
    assert calculate_model_hash(path) == hashlib.sha256(data).hexdigest()


def test_verify_detects_single_byte_change(tmp_path):
    path = tmp_path / "m.bin"
    path.write_bytes(b"model-weights")
    expected = calculate_model_hash(path)
    assert verify_model_integrity(path, expected)
    assert verify_model_integrity(path, expected.upper())

    path.write_bytes(b"model-weightz")
    assert not verify_model_integrity(path, expected)


def test_signed_manifest_roundtrip_and_tamper(tmp_path):
    path = tmp_path / "m.bin"
    path.write_bytes(b"abc")
    key = b"k" * 32
    manifest = sign_manifest(build_manifest(path, stage="prod"), key)

    assert manifest["digest"] == hashlib.sha256(b"abc").hexdigest()
    assert verify_manifest_signature(manifest, key)
    assert not verify_manifest_signature(manifest, b"z" * 32)
    assert not verify_manifest_signature({**manifest, "digest": "0" * 64}, key)
    assert not verify_manifest_signature(build_manifest(path), key)


def test_short_signing_key_rejected(tmp_path):
    path = tmp_path / "m.bin"
    path.write_bytes(b"abc")
    with pytest.raises(ValueError):
        sign_manifest(build_manifest(path), b"short")
