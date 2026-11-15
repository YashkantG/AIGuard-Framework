# Finding reference

Every finding the scanner can report, with what it means and how serious it is.

## Pickle files

| ID | Severity | Meaning |
|---|---|---|
| AIG-SER-001 | medium | The file is a Python pickle. The format can run code on load, so every pickle gets this finding, including harmless ones. |
| AIG-SER-002 | critical | The pickle would call functions that can run commands, open files or reach the network when loaded. The description names them. Treat the file as malicious. |
| AIG-SER-003 | medium | The pickle uses helper functions that are sometimes chained together to run code indirectly. Legitimate models occasionally use them. |
| AIG-SER-004 | low | The pickle imports modules outside the common machine learning libraries. Usually a custom model class; worth confirming. |
| AIG-SER-005 | medium | The pickle is malformed or builds its import names at load time, so the scanner could not see everything it does. |

## Archives (.pt, .pth, .keras, .zip, .npz)

| ID | Severity | Meaning |
|---|---|---|
| AIG-ARC-001 | high | A file inside the archive has a path that would be written outside the extraction folder. |
| AIG-ARC-002 | medium | The archive contains Python source files, which may be imported when the model loads. |
| AIG-ARC-003 | medium | A file inside expands more than 200 times its compressed size, which is typical of a zip bomb. |
| AIG-ARC-004 | medium | The file starts like a ZIP archive but cannot be opened as one. |

Pickles found inside an archive are scanned and reported with the AIG-SER findings above; the location field names the archive member.

## Keras

| ID | Severity | Meaning |
|---|---|---|
| AIG-KER-001 | high | The model contains a Lambda layer, which stores Python code that runs when the model loads. |

## Format checks

| ID | Severity | Meaning |
|---|---|---|
| AIG-FMT-001 | low | The format is not one the scanner understands, so nothing was inspected. |
| AIG-FMT-002 | info | The file is in a data-only format (safetensors or GGUF) that cannot carry code. |
| AIG-FMT-003 | low | The file, or a file inside it, is larger than the inspection limit and was skipped. |
| AIG-FMT-004 | info | The file is ONNX. It was identified but custom operators were not inspected. |
| AIG-FMT-005 | medium | The file is named `.safetensors` but does not have a valid safetensors header. The extension is misleading. |

## Severity scale

- **critical / high**: do not load the file.
- **medium**: load only if the source is trusted.
- **low / info**: no known problem; noted for completeness.
