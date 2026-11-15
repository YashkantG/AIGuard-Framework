"""Example 1: check whether a model file is safe to load.

    python examples/01_scan_model_file.py

Writes two small pickle files, one harmless and one that would run a shell
command if loaded, then scans both. The scanner only reads the bytes; it never
loads the files.
"""

import pickle
import tempfile
from pathlib import Path

from aiguard.security import scan_artifact


def show(path: Path) -> None:
    result = scan_artifact(path)
    print(f"\n{path.name}  (format: {result['format']})")
    for finding in result["findings"]:
        print(f"  [{finding.severity.upper():<8}] {finding.title}")
        print(f"             fix: {finding.recommendation}")


def main() -> None:
    folder = Path(tempfile.mkdtemp(prefix="aiguard-scan-"))

    safe = folder / "safe_model.pkl"
    safe.write_bytes(pickle.dumps({"weights": [0.2, 0.5, 0.3], "bias": 0.1}))

    # Hand-written pickle bytes that call os.system("echo hello") when loaded.
    unsafe = folder / "downloaded_model.pkl"
    unsafe.write_bytes(b"cos\nsystem\n(S'echo hello'\ntR.")

    show(safe)
    show(unsafe)


if __name__ == "__main__":
    main()
