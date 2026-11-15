"""The standalone skill script must agree with the library scanner and stay dependency-free."""

import ast
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path

import pytest

from aiguard.security import scan_artifact

SKILL_DIR = Path(__file__).parents[2] / "skills" / "model-file-scanner"
SCRIPT = SKILL_DIR / "scripts" / "scan_model.py"

spec = importlib.util.spec_from_file_location("skill_scan_model", SCRIPT)
assert spec and spec.loader
skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill)


class Payload:
    def __reduce__(self):
        return os.system, ("echo x",)


@pytest.fixture
def files(tmp_path):
    safe = tmp_path / "safe.pkl"
    safe.write_bytes(pickle.dumps({"weights": [1, 2, 3]}))
    evil = tmp_path / "evil.pkl"
    evil.write_bytes(pickle.dumps(Payload()))
    text = tmp_path / "notes.txt"
    text.write_bytes(b"hello")
    return {"safe": safe, "evil": evil, "text": text}


def test_skill_has_valid_frontmatter():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    header = text.split("---\n")[1]
    assert "name: model-file-scanner" in header
    assert "description: " in header


def test_script_uses_only_the_standard_library():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= set(sys.stdlib_module_names)
    # A scanner that reads untrusted files must not shell out or use the network.
    assert not roots & {"subprocess", "socket", "urllib", "http", "requests", "os"}


@pytest.mark.parametrize("name", ["safe", "evil", "text"])
def test_skill_matches_library_scanner(files, name):
    ours = skill.scan_file(files[name])
    library = scan_artifact(files[name])
    assert ours["format"] == library["format"]
    assert {f["id"] for f in ours["findings"]} == {f.id for f in library["findings"]}


def test_verdicts_and_exit_codes(files, capsys):
    assert skill.scan_file(files["evil"])["verdict"] == "DO NOT LOAD"
    assert skill.scan_file(files["safe"])["verdict"] == "LOAD ONLY IF YOU TRUST THE SOURCE"
    assert skill.scan_file(files["text"])["verdict"] == "NO KNOWN PROBLEMS FOUND"

    assert skill.main([str(files["evil"])]) == 1
    assert skill.main([str(files["safe"])]) == 0
    assert skill.main([str(files["safe"]), "--fail-on", "medium"]) == 1
    assert skill.main([str(files["safe"].with_name("missing.pkl"))]) == 2
    capsys.readouterr()


def test_json_output_is_complete(files, capsys):
    skill.main([str(files["evil"]), "--json"])
    result = json.loads(capsys.readouterr().out)
    assert len(result["sha256"]) == 64
    assert result["highest_severity"] == "critical"
    assert result["findings"][0]["id"] == "AIG-SER-002"  # most severe first
    assert all(f["recommendation"] for f in result["findings"])
