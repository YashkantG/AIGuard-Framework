"""Reproducible micro-benchmarks on synthetic data.

    python benchmarks/run_benchmarks.py [--output results.json]

Numbers depend on the machine. The script records the platform next to the
results so that runs can be compared honestly; the project publishes no
performance claims of its own.
"""

import argparse
import json
import os
import pickle
import platform
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from aiguard import AIGuard, Settings, __version__
from aiguard.core.models import ModelCreate
from aiguard.monitoring import detect_feature_drift
from aiguard.security import calculate_model_hash, scan_artifact

SEED = 20260101


def timed(fn: Callable[[], Any], repeats: int) -> dict[str, float]:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return {
        "median_ms": float(np.median(samples) * 1000),
        "p95_ms": float(np.percentile(samples, 95) * 1000),
        "repeats": repeats,
    }


def bench_integrity(work: Path) -> dict[str, Any]:
    size_mb = 64
    path = work / "weights.bin"
    path.write_bytes(os.urandom(size_mb * 1024 * 1024))
    result = timed(lambda: calculate_model_hash(path), 5)
    result["throughput_mb_per_s"] = size_mb / (result["median_ms"] / 1000)

    # Detection: every single-byte modification must change the digest.
    expected = calculate_model_hash(path)
    rng = np.random.default_rng(SEED)
    data = bytearray(path.read_bytes())
    trials, detected = 20, 0
    for offset in rng.integers(0, len(data), trials):
        original = data[offset]
        data[offset] ^= 0x01
        path.write_bytes(data)
        detected += calculate_model_hash(path) != expected
        data[offset] = original
    result["tamper_detection"] = {"trials": trials, "detected": detected}
    return result


def bench_scan(work: Path) -> dict[str, float]:
    path = work / "model.pkl"
    rng = np.random.default_rng(SEED)
    path.write_bytes(pickle.dumps({f"layer_{i}": rng.normal(size=20_000) for i in range(50)}))
    return {**timed(lambda: scan_artifact(path), 10), "artifact_mb": path.stat().st_size / 1e6}


def bench_drift() -> dict[str, Any]:
    """Detection quality on synthetic mean shifts, 200 trials per scenario."""
    rng = np.random.default_rng(SEED)
    scenarios: dict[str, Any] = {}
    for shift in (0.0, 0.1, 0.25, 0.5, 1.0):
        flagged = sum(
            detect_feature_drift("x", rng.normal(size=1000), rng.normal(shift, 1, 1000))[
                "drift_detected"
            ]
            for _ in range(200)
        )
        scenarios[f"mean_shift_{shift}_sigma"] = {"trials": 200, "flagged": int(flagged)}
    reference, current = rng.normal(size=10_000), rng.normal(0.3, 1, 10_000)
    return {
        "scenarios": scenarios,
        "latency_10k": timed(lambda: detect_feature_drift("x", reference, current), 20),
    }


def bench_service(work: Path) -> dict[str, Any]:
    guard = AIGuard(
        Settings(database_url=f"sqlite:///{(work / 'bench.db').as_posix()}", artifact_dir=work)
    )
    counter = iter(range(10**6))

    def register() -> None:
        index = next(counter)
        guard.register_model(
            ModelCreate(name="bench", version=str(index), sha256=f"{index:064x}"), "bench"
        )

    registration = timed(register, 200)
    model_id = guard.list_models()[0]["id"]
    return {
        "model_registration": registration,
        "policy_evaluation": timed(lambda: guard.evaluate_policies(model_id, actor="bench"), 50),
        "audit_chain_verification": {
            **timed(guard.verify_audit_chain, 5),
            "events": guard.verify_audit_chain()["events_checked"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="aiguard-bench-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        results = {
            "aiguard_version": __version__,
            "seed": SEED,
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "numpy": np.__version__,
            },
            "integrity_sha256_64mb": bench_integrity(work),
            "artifact_scan": bench_scan(work),
            "drift": bench_drift(),
            "service_sqlite": bench_service(work),
        }
    text = json.dumps(results, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
