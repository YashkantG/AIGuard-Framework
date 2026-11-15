#!/usr/bin/env python3
"""Check a machine learning model file for hidden code before it is loaded.

    python scan_model.py MODEL_FILE [--json] [--fail-on SEVERITY]

The file is only read as bytes. It is never unpickled, imported or run.
Standard library only: no packages to install, no network access.

Exit codes: 0 = nothing at or above the --fail-on severity (default: high),
1 = at least one such finding, 2 = the file could not be read.

A clean result means no known pattern matched. It is not proof of safety.

Part of AIGuard Framework (Apache-2.0): https://github.com/YashkantG/AIGuard-Framework
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pickletools
import re
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

SEVERITY_ORDER = ("info", "low", "medium", "high", "critical")
REFERENCE = "OWASP ML Security Top 10 - ML06: AI Supply Chain Attacks"


def finding(
    fid: str, title: str, severity: str, description: str, fix: str, location: str = ""
) -> dict[str, str]:
    return {
        "id": fid,
        "title": title,
        "severity": severity,
        "description": description,
        "recommendation": fix,
        "location": location,
        "reference": REFERENCE if severity in ("high", "critical") else "",
    }


# ------------------------------------------------------------------ pickle

# Modules whose callables can run commands, touch files or reach the network.
RISKY_MODULES = {
    "os", "posix", "nt", "subprocess", "sys", "socket", "shutil", "runpy", "importlib",
    "pty", "ctypes", "webbrowser", "pickle", "_pickle", "marshal", "code", "codeop",
    "multiprocessing", "urllib", "http", "requests", "ftplib", "smtplib", "telnetlib",
    "pip", "pydoc", "commands", "popen2", "asyncio", "zipfile", "tarfile", "types",
    "inspect", "timeit", "trace", "bdb", "pdb",
}
RISKY_BUILTINS = {
    "eval", "exec", "compile", "open", "__import__", "getattr", "setattr", "delattr",
    "breakpoint", "input", "globals", "locals", "vars", "memoryview", "apply", "execfile",
}
SAFE_BUILTINS = {
    "set", "frozenset", "dict", "list", "tuple", "bytearray", "bytes", "complex", "object",
    "slice", "range", "int", "float", "str", "bool", "print", "len", "long", "unicode",
}
INDIRECT_CALL_HELPERS = {
    ("operator", "attrgetter"), ("operator", "methodcaller"), ("operator", "itemgetter"),
    ("functools", "partial"), ("functools", "reduce"),
}
KNOWN_ML_ROOTS = {
    "numpy", "sklearn", "scipy", "pandas", "torch", "xgboost", "lightgbm", "catboost",
    "joblib", "collections", "copyreg", "copy_reg", "_codecs", "datetime", "decimal",
    "fractions", "enum", "array", "uuid", "re", "_collections", "tensorflow", "keras",
    "transformers", "tokenizers", "cloudpickle", "dill",
}
STRING_OPS = {
    "SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "UNICODE",
    "STRING", "BINSTRING", "SHORT_BINSTRING",
}
PUT_OPS = {"PUT", "BINPUT", "LONG_BINPUT"}
GET_OPS = {"GET", "BINGET", "LONG_BINGET"}
MAX_PICKLES_PER_STREAM = 32


def pickle_imports(stream: BinaryIO, size: int) -> tuple[set[tuple[str, str]], bool, bool]:
    """Disassemble concatenated pickles. Returns (imports, unresolved, parse_error)."""
    imports: set[tuple[str, str]] = set()
    unresolved = False
    parsed_any = False
    for _ in range(MAX_PICKLES_PER_STREAM):
        if stream.tell() >= size:
            break
        strings: list[str] = []
        memo: dict[int, Any] = {}
        last: Any = None
        try:
            for opcode, arg, _pos in pickletools.genops(stream):
                name = opcode.name
                if name in STRING_OPS:
                    last = arg
                    strings.append(str(arg))
                elif name in PUT_OPS:
                    memo[int(arg or 0)] = last
                elif name == "MEMOIZE":
                    memo[len(memo)] = last
                elif name in GET_OPS:
                    last = memo.get(int(arg or 0))
                    if isinstance(last, str):
                        strings.append(last)
                elif name in ("FRAME", "PROTO"):
                    continue
                else:
                    if name in ("GLOBAL", "INST"):
                        module, _, attr = str(arg).partition(" ")
                        imports.add((module, attr))
                    elif name == "STACK_GLOBAL":
                        if len(strings) >= 2:
                            imports.add((strings[-2], strings[-1]))
                        else:
                            unresolved = True
                    last = None
            parsed_any = True
        except Exception:
            # Data after the first pickle (for example joblib arrays) is normal.
            return imports, unresolved, not parsed_any
    return imports, unresolved, False


def grade_import(module: str, attr: str) -> str | None:
    root = module.split(".")[0]
    if module in ("builtins", "__builtin__", "__builtins__"):
        if attr in RISKY_BUILTINS:
            return "critical"
        return None if attr in SAFE_BUILTINS else "medium"
    if root in RISKY_MODULES:
        return "critical"
    if (module, attr) in INDIRECT_CALL_HELPERS:
        return "medium"
    return None if root in KNOWN_ML_ROOTS else "low"


def scan_pickle_stream(stream: BinaryIO, size: int, location: str = "") -> list[dict[str, str]]:
    findings = [
        finding(
            "AIG-SER-001",
            "Pickle-based serialization",
            "medium",
            "The file uses Python pickle. Loading a pickle can run code, so the file is "
            "only as trustworthy as its source.",
            "Prefer a data-only format such as safetensors or ONNX, and only load pickles "
            "from a source you trust.",
            location,
        )
    ]
    imports, unresolved, parse_error = pickle_imports(stream, size)
    graded: dict[str, list[str]] = {"critical": [], "medium": [], "low": []}
    for module, attr in sorted(imports):
        severity = grade_import(module, attr)
        if severity:
            graded[severity].append(f"{module}.{attr}")
    if graded["critical"]:
        findings.append(
            finding(
                "AIG-SER-002",
                "Pickle references code-execution primitives",
                "critical",
                "When loaded, the pickle would call functions that can run commands, open "
                "files or reach the network: " + ", ".join(graded["critical"]) + ".",
                "Do not load this file. Get it again from a trusted source.",
                location,
            )
        )
    if graded["medium"]:
        findings.append(
            finding(
                "AIG-SER-003",
                "Pickle references indirect-call helpers",
                "medium",
                "These imports are sometimes used to build code-execution chains: "
                + ", ".join(graded["medium"]) + ".",
                "Find out why the model needs these before loading it.",
                location,
            )
        )
    if graded["low"]:
        findings.append(
            finding(
                "AIG-SER-004",
                "Pickle imports unrecognised modules",
                "low",
                "Imports outside the common ML libraries: " + ", ".join(graded["low"][:25]) + ".",
                "Confirm these modules are expected for this model.",
                location,
            )
        )
    if unresolved or parse_error:
        findings.append(
            finding(
                "AIG-SER-005",
                "Pickle could not be fully analysed",
                "medium",
                "The stream is malformed or builds import names dynamically, so the list of "
                "imports may be incomplete.",
                "Treat the file as untrusted until it is inspected by hand.",
                location,
            )
        )
    return findings


# ------------------------------------------------------------------ other formats

PICKLE_EXTENSIONS = {".pkl", ".pickle", ".joblib", ".pt", ".pth", ".ckpt", ".bin", ".sav", ".dill"}
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 10_000
LAMBDA_LAYER = re.compile(r'"class_name"\s*:\s*"Lambda"')


def too_large(location: str) -> dict[str, str]:
    return finding(
        "AIG-FMT-003",
        "Content too large to inspect",
        "low",
        "The content exceeds the inspection limit and was not scanned.",
        "Raise --max-bytes or inspect the file in an isolated environment.",
        location,
    )


def lambda_layer(location: str) -> dict[str, str]:
    return finding(
        "AIG-KER-001",
        "Keras Lambda layer",
        "high",
        "Lambda layers carry serialized Python code that runs when the model loads.",
        "Load with safe mode enabled, or replace the Lambda with a built-in layer.",
        location,
    )


def data_only(fmt: str, description: str) -> dict[str, str]:
    return finding(
        "AIG-FMT-002",
        f"Data-only format ({fmt})",
        "info",
        description,
        "Still check the file's SHA-256 against the publisher's value.",
    )


def scan_zip(path: Path) -> tuple[str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    fmt = "zip-archive"
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return fmt, [
            finding(
                "AIG-ARC-004",
                "Corrupt archive",
                "medium",
                "The file has a ZIP signature but cannot be opened as an archive.",
                "Download the file again and compare its SHA-256.",
            )
        ]
    with archive:
        for info in archive.infolist()[:MAX_MEMBERS]:
            name = info.filename
            lower = name.lower()
            if name.startswith(("/", "\\")) or ".." in Path(name).parts or ":" in name:
                findings.append(
                    finding(
                        "AIG-ARC-001",
                        "Archive member escapes the extraction folder",
                        "high",
                        f"Member name {name!r} would be written outside the target folder.",
                        "Do not extract this archive with a plain extractor.",
                        name,
                    )
                )
            if lower.endswith(".py"):
                findings.append(
                    finding(
                        "AIG-ARC-002",
                        "Archive bundles Python source",
                        "medium",
                        "Bundled code may be imported when the model is loaded.",
                        "Read the bundled source before loading the model.",
                        name,
                    )
                )
            if info.file_size > 50 * 1024 * 1024 and info.compress_size > 0:
                if info.file_size / info.compress_size > 200:
                    findings.append(
                        finding(
                            "AIG-ARC-003",
                            "Extreme compression ratio",
                            "medium",
                            "A member expands more than 200x, typical of a zip bomb.",
                            "Extract only with size limits in place.",
                            name,
                        )
                    )
            if lower.endswith((".pkl", ".pickle")):
                fmt = "zip-archive-with-pickle"
                if info.file_size > MAX_MEMBER_BYTES:
                    findings.append(too_large(name))
                    continue
                with archive.open(info) as member:
                    data = member.read(MAX_MEMBER_BYTES)
                findings.extend(scan_pickle_stream(io.BytesIO(data), len(data), name))
            elif lower.endswith("config.json") and info.file_size < 5 * 1024 * 1024:
                with archive.open(info) as member:
                    text = member.read().decode("utf-8", errors="replace")
                if LAMBDA_LAYER.search(text):
                    findings.append(lambda_layer(name))
    return fmt, findings


def valid_safetensors(path: Path, size: int) -> bool:
    with open(path, "rb") as handle:
        header = handle.read(8)
        if len(header) < 8:
            return False
        (length,) = struct.unpack("<Q", header)
        if length <= 0 or length > min(size - 8, 100 * 1024 * 1024):
            return False
        try:
            return isinstance(json.loads(handle.read(length)), dict)
        except (ValueError, UnicodeDecodeError):
            return False


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path, max_bytes: int = 2 * 1024**3) -> dict[str, Any]:
    """Statically inspect one model file."""
    size = path.stat().st_size
    suffix = path.suffix.lower()
    result: dict[str, Any] = {"file": str(path), "size_bytes": size, "sha256": sha256_of(path)}
    if size > max_bytes:
        return {**result, "format": "unknown", "findings": [too_large(path.name)]}
    with open(path, "rb") as handle:
        head = handle.read(16)

    fmt = "unknown"
    findings: list[dict[str, str]] = []
    if head.startswith(b"PK\x03\x04"):
        fmt, findings = scan_zip(path)
    elif suffix == ".safetensors":
        if valid_safetensors(path, size):
            fmt = "safetensors"
            findings = [data_only(fmt, "safetensors stores tensors and metadata only.")]
        else:
            fmt = "invalid-safetensors"
            findings = [
                finding(
                    "AIG-FMT-005",
                    "File extension does not match content",
                    "medium",
                    "The file is named .safetensors but has no valid safetensors header.",
                    "Do not trust the extension; find out what this file really is.",
                )
            ]
    elif head.startswith(b"\x89HDF\r\n\x1a\n"):
        fmt = "hdf5"
        with open(path, "rb") as handle:
            if LAMBDA_LAYER.search(handle.read(MAX_MEMBER_BYTES).decode("latin-1")):
                findings.append(lambda_layer(path.name))
    elif head.startswith(b"GGUF"):
        fmt = "gguf"
        findings = [data_only(fmt, "GGUF stores weights and metadata only.")]
    elif suffix == ".onnx":
        fmt = "onnx"
        findings = [
            finding(
                "AIG-FMT-004",
                "ONNX graph not inspected in depth",
                "info",
                "ONNX is a data format, but custom operators were not checked.",
                "Check for custom operator domains before serving the model.",
            )
        ]
    elif suffix in PICKLE_EXTENSIONS or (len(head) > 1 and head[0] == 0x80 and 2 <= head[1] <= 5):
        fmt = "pickle"
        with open(path, "rb") as handle:
            findings = scan_pickle_stream(handle, size, path.name)
    else:
        findings = [
            finding(
                "AIG-FMT-001",
                "Unrecognised file format",
                "low",
                "This is not a format the scanner can inspect, so nothing was checked.",
                "Inspect the file with a format-specific tool.",
            )
        ]

    findings.sort(key=lambda f: -SEVERITY_ORDER.index(f["severity"]))
    worst = findings[0]["severity"] if findings else None
    if worst in ("critical", "high"):
        verdict = "DO NOT LOAD"
    elif worst == "medium":
        verdict = "LOAD ONLY IF YOU TRUST THE SOURCE"
    else:
        verdict = "NO KNOWN PROBLEMS FOUND"
    return {**result, "format": fmt, "verdict": verdict, "highest_severity": worst,
            "findings": findings}


def render(result: dict[str, Any]) -> str:
    lines = [
        f"File:     {result['file']}",
        f"Format:   {result['format']}",
        f"SHA-256:  {result['sha256']}",
        f"Verdict:  {result.get('verdict', 'NOT SCANNED')}",
        "",
    ]
    for item in result["findings"]:
        lines.append(f"[{item['severity'].upper()}] {item['id']}  {item['title']}")
        lines.append(f"    {item['description']}")
        lines.append(f"    Fix: {item['recommendation']}")
        if item["location"]:
            lines.append(f"    Location: {item['location']}")
    lines += ["", "A clean result means no known pattern matched. It is not proof of safety."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a model file for hidden code without loading it."
    )
    parser.add_argument("path", type=Path, help="model file to inspect")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--fail-on", choices=SEVERITY_ORDER, default="high",
                        help="exit 1 at or above this severity (default: high)")
    parser.add_argument("--max-bytes", type=int, default=2 * 1024**3,
                        help="skip files larger than this (default: 2 GB)")
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(f"Error: {args.path} is not a file", file=sys.stderr)
        return 2
    try:
        result = scan_file(args.path, args.max_bytes)
    except OSError as exc:
        print(f"Error: could not read {args.path}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2) if args.json else render(result))
    threshold = SEVERITY_ORDER.index(args.fail_on)
    blocked = any(SEVERITY_ORDER.index(f["severity"]) >= threshold for f in result["findings"])
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
