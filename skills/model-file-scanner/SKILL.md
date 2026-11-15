---
name: model-file-scanner
description: Checks a machine learning model file for hidden code before it is loaded. Use when the user downloads, receives or is about to load a model file (.pkl, .pickle, .joblib, .pt, .pth, .ckpt, .bin, .safetensors, .keras, .h5, .onnx, .gguf), asks whether a model file is safe, or wants a model's SHA-256 fingerprint. The file is read as bytes only and is never loaded or executed.
license: Apache-2.0
---

# Model File Scanner

Model files in pickle-based formats can run code the moment they are loaded. This skill inspects a model file without loading it and reports what loading it would do.

## When to use it

- The user has downloaded a model from a hub, a colleague or an email and wants to load it.
- The user asks "is this model file safe?" or "can I trust this checkpoint?".
- Code you are about to write or run calls `torch.load`, `pickle.load`, `joblib.load` or similar on a file whose origin is not clearly trusted.
- The user wants the SHA-256 fingerprint of a model file to compare with a published value.

Scan first, then load. Do not load the file to "see what is inside".

## How to run it

The scanner is a single Python file with no dependencies (Python 3.9 or newer).

```bash
python scripts/scan_model.py path/to/model.pkl
```

For results you will process yourself, ask for JSON:

```bash
python scripts/scan_model.py path/to/model.pkl --json
```

Options:

- `--fail-on SEVERITY` sets the exit-code threshold (`info`, `low`, `medium`, `high`, `critical`; default `high`).
- `--max-bytes N` skips files larger than N bytes (default 2 GB).

Exit codes: `0` nothing at or above the threshold, `1` at least one such finding, `2` the file could not be read.

To check a folder, run the scanner once per model file.

## Reading the result

The output gives the detected format, the SHA-256 fingerprint, a verdict and a list of findings.

| Verdict | Meaning | What to do |
|---|---|---|
| `DO NOT LOAD` | A high or critical finding: loading would call functions that can run commands, access files or reach the network, or the archive is built to escape its folder. | Tell the user not to load the file. Do not load it yourself, even to investigate. |
| `LOAD ONLY IF YOU TRUST THE SOURCE` | Medium findings only. A plain pickle always gets this, because the format itself can run code. | Tell the user what was found and ask whether the source is trusted before loading. |
| `NO KNOWN PROBLEMS FOUND` | Only low or informational findings, or none. | Loading is reasonable. Still mention the limits below. |

Each finding has an ID, a severity, a plain description and a fix. The IDs are explained in `references/findings.md`.

## What to tell the user

1. Give the verdict first, in one sentence.
2. List each finding at medium severity or above with its fix, in plain words.
3. Give the SHA-256 fingerprint so they can compare it with the publisher's value.
4. If the file is a pickle from an untrusted source, suggest asking for a safetensors or ONNX version.

Report only what the scanner found. Do not describe a file as "safe", "verified" or "secure"; say that no known problem was found.

## Limits

- The scanner matches known patterns. A new or heavily disguised payload may not be recognised.
- A clean result is not proof of safety.
- ONNX graphs are identified but custom operators are not inspected.
- It checks what loading the file would do. It does not judge whether the model's predictions are accurate, fair or backdoored.

## About

Taken from [AIGuard Framework](https://github.com/YashkantG/AIGuard-Framework), an open-source toolkit for model integrity, drift detection, explainability and governance. Apache License 2.0.
