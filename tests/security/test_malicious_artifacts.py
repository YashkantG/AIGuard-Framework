"""Artifacts are untrusted: the scanner must flag dangerous content without running it."""

import io
import json
import os
import pickle
import struct
import subprocess
import zipfile
from collections import OrderedDict

import numpy as np
import pytest

from aiguard.security import check_deployment_config, check_requirements, scan_artifact
from aiguard.security.vulnerability import highest_severity


class Payload:
    """Pickles to a call of ``fn(*args)``. Only ever dumped in these tests, never loaded."""

    def __init__(self, fn, *args):
        self.fn, self.args = fn, args

    def __reduce__(self):
        return self.fn, self.args


def ids(result):
    return {f.id for f in result["findings"]}


@pytest.mark.parametrize("protocol", [0, 2, 4, 5])
@pytest.mark.parametrize(
    "fn,args",
    [(os.system, ("echo x",)), (subprocess.Popen, (["echo"],)), (eval, ("1+1",)), (exec, ("",))],
)
def test_code_execution_pickles_are_critical(tmp_path, protocol, fn, args):
    path = tmp_path / "evil.pkl"
    path.write_bytes(pickle.dumps(Payload(fn, *args), protocol=protocol))
    result = scan_artifact(path)
    assert result["format"] == "pickle"
    assert "AIG-SER-002" in ids(result)
    assert highest_severity(result["findings"]) == "critical"


def test_scanning_does_not_execute_the_payload(tmp_path):
    marker = tmp_path / "executed"
    path = tmp_path / "evil.pkl"
    path.write_bytes(pickle.dumps(Payload(os.mkdir, str(marker))))
    result = scan_artifact(path)
    assert "AIG-SER-002" in ids(result)
    assert not marker.exists()


def test_benign_pickles_are_not_critical(tmp_path):
    path = tmp_path / "ok.pkl"
    payload = {"w": np.arange(6.0).reshape(2, 3), "meta": OrderedDict(a=1), "tags": {"x", "y"}}
    path.write_bytes(pickle.dumps(payload, protocol=4))
    result = scan_artifact(path)
    assert ids(result) == {"AIG-SER-001"}  # the format itself, nothing else
    assert highest_severity(result["findings"]) == "medium"


def test_pickle_detected_by_content_not_extension(tmp_path):
    path = tmp_path / "weights.dat"
    path.write_bytes(pickle.dumps(Payload(os.system, "echo x"), protocol=4))
    assert "AIG-SER-002" in ids(scan_artifact(path))


def test_payload_hidden_in_second_pickle_is_found(tmp_path):
    # Legacy torch files concatenate several pickles in one stream.
    path = tmp_path / "legacy.pt"
    path.write_bytes(pickle.dumps(12345) + pickle.dumps(Payload(os.system, "echo x")))
    assert "AIG-SER-002" in ids(scan_artifact(path))


def test_truncated_pickle_is_reported(tmp_path):
    path = tmp_path / "broken.pkl"
    path.write_bytes(pickle.dumps({"a": list(range(100))}, protocol=4)[:20])
    assert "AIG-SER-005" in ids(scan_artifact(path))


def test_unknown_imports_are_low_severity(tmp_path):
    path = tmp_path / "custom.pkl"
    path.write_bytes(b"cmycompany.models\nScorer\n)R.")
    result = scan_artifact(path)
    assert "AIG-SER-004" in ids(result)
    assert "AIG-SER-002" not in ids(result)


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def test_torch_style_archive_is_scanned(tmp_path):
    path = tmp_path / "model.pt"
    make_zip(path, {"archive/data.pkl": pickle.dumps(Payload(os.system, "echo x"), protocol=2)})
    result = scan_artifact(path)
    assert result["format"] == "zip-archive-with-pickle"
    assert "AIG-SER-002" in ids(result)


def test_archive_traversal_embedded_code_and_lambda(tmp_path):
    path = tmp_path / "model.keras"
    make_zip(
        path,
        {
            "../../etc/cron.d/job": b"x",
            "hooks/loader.py": b"import os",
            "config.json": json.dumps({"layers": [{"class_name": "Lambda"}]}),
        },
    )
    assert {"AIG-ARC-001", "AIG-ARC-002", "AIG-KER-001"} <= ids(scan_artifact(path))


def test_corrupt_archive(tmp_path):
    path = tmp_path / "model.zip"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 40)
    assert ids(scan_artifact(path)) == {"AIG-ARC-004"}


def test_safetensors_valid_and_spoofed(tmp_path):
    header = json.dumps({"w": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
    good = tmp_path / "good.safetensors"
    good.write_bytes(struct.pack("<Q", len(header)) + header + b"\x00" * 4)
    result = scan_artifact(good)
    assert result["format"] == "safetensors"
    assert highest_severity(result["findings"]) == "info"

    spoofed = tmp_path / "spoofed.safetensors"
    spoofed.write_bytes(b"cos\nsystem\n(S'echo x'\ntR.")
    assert ids(scan_artifact(spoofed)) == {"AIG-FMT-005"}


def test_unknown_and_oversized_files(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes(b"hello")
    assert ids(scan_artifact(path)) == {"AIG-FMT-001"}
    assert ids(scan_artifact(path, max_bytes=2)) == {"AIG-FMT-003"}


def test_scan_pickle_stream_accepts_bytesio():
    from aiguard.security.vulnerability import scan_pickle_stream

    data = pickle.dumps(Payload(os.system, "echo x"))
    assert any(f.severity == "critical" for f in scan_pickle_stream(io.BytesIO(data), len(data)))


def test_deployment_config_checks():
    secure = {
        "authentication_enabled": True, "tls_enabled": True, "integrity_check_on_load": True,
        "allow_pickle": False, "rate_limiting_enabled": True, "input_validation_enabled": True,
        "debug_mode": False, "runs_as_root": False, "egress_restricted": True,
    }  # fmt: skip
    assert check_deployment_config(secure) == []

    insecure = check_deployment_config({**secure, "tls_enabled": False, "allow_pickle": True})
    assert {f.location for f in insecure} == {"tls_enabled", "allow_pickle"}
    assert all(f.severity == "high" for f in insecure)

    undeclared = check_deployment_config({})
    assert len(undeclared) == len(secure)
    assert all(f.severity == "low" for f in undeclared)


def test_requirements_pinning():
    pinned = "numpy==2.1.0\nscikit-learn==1.5.2  # comment\n-r base.txt\n\n"
    assert check_requirements(pinned) == []
    findings = check_requirements("numpy>=1.26\npandas\nrequests==2.*\nscipy==1.14.1\n")
    assert len(findings) == 1
    for name in ("numpy", "pandas", "requests"):
        assert name in findings[0].description
    assert "scipy" not in findings[0].description
