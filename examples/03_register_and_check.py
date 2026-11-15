"""Example 3: register a model, then catch a change to its file.

    python examples/03_register_and_check.py

Registers a model file, verifies it, modifies one byte, verifies again, and
finally asks which governance policies the model passes.
"""

import tempfile
from pathlib import Path

from aiguard import AIGuard, Settings
from aiguard.core.models import ModelCreate


def main() -> None:
    folder = Path(tempfile.mkdtemp(prefix="aiguard-register-"))
    model_file = folder / "model.bin"
    model_file.write_bytes(b"pretend these are model weights")

    database_url = f"sqlite:///{(folder / 'aiguard.db').as_posix()}"
    guard = AIGuard(Settings(database_url=database_url, artifact_dir=folder))

    model = guard.register_model(
        ModelCreate(
            name="spam-filter",
            version="1.0.0",
            artifact_path="model.bin",
            owner="Mail Team",
            description="Flags spam emails.",
            intended_use="Sorting incoming mail into the spam folder.",
        )
    )
    model_id = model["id"]
    print("Registered:", model["name"], model["version"])
    print("Fingerprint:", model["sha256"][:16] + "...")

    print("\nFile unchanged  -> verified:", guard.verify_integrity(model_id)["verified"])

    model_file.write_bytes(b"pretend these are model weightz")  # one byte differs
    print("File modified   -> verified:", guard.verify_integrity(model_id)["verified"])

    print("\nGovernance policies:")
    for result in guard.evaluate_policies(model_id)["results"]:
        print(f"  {result['status']:<15}{result['title']}")

    print("\nAudit log intact:", guard.verify_audit_chain()["valid"])


if __name__ == "__main__":
    main()
