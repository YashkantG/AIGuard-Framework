# API reference

Base path: `/api/v1`. Send the API key in the `X-API-Key` header. A running server also serves interactive documentation at `/api/docs`.

Errors are JSON: `{"detail": "..."}`. Status codes: 401 missing or invalid key, 403 insufficient role, 404 not found, 409 conflict, 413 body too large, 422 invalid input, 429 rate limited.

## Models

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/models` | analyst | Register a model version |
| GET | `/models` | viewer | List models with their posture |
| GET | `/models/{id}` | viewer | Model metadata and posture |
| POST | `/models/{id}/verify` | analyst | Verify integrity |
| POST | `/models/{id}/assess` | analyst | Run a security assessment |
| POST | `/models/{id}/drift` | analyst | Evaluate drift |
| POST | `/models/{id}/explain` | analyst | Explain recorded predictions |
| POST | `/models/{id}/risk` | analyst | Assess risk |
| GET | `/models/{id}/evidence` | viewer | Latest evidence of each kind |
| GET | `/models/{id}/lineage` | viewer | Lineage graph |
| GET | `/models/{id}/audit` | viewer | Audit history (`?limit=`) |
| GET | `/models/{id}/report` | viewer | Evidence report (JSON) |
| GET | `/models/{id}/report.md` | viewer | Evidence report (Markdown) |

### Register

```bash
curl -X POST http://127.0.0.1:8000/api/v1/models \
  -H "X-API-Key: $AIGUARD_KEY" -H "Content-Type: application/json" \
  -d '{"name": "fraud", "version": "1.0.0", "artifact_path": "fraud.safetensors",
       "owner": "Risk", "description": "Fraud scoring", "intended_use": "Decision support",
       "impact_tier": "high", "human_oversight": "Analyst reviews every block"}'
```

Give `artifact_path` (relative to the server's artifact directory) or `sha256` (a digest you computed). `impact_tier` is `minimal`, `limited` or `high`.

### Verify

An empty body verifies the registered file. `{"artifact_path": "..."}` verifies another file in the artifact directory. `{"sha256": "..."}` compares a digest you computed; the evidence records that the digest was client-supplied.

### Assess

```json
{
  "deployment_config": {"authentication_enabled": true, "tls_enabled": true, "allow_pickle": false},
  "requirements": "numpy==2.1.0\nscikit-learn>=1.4\n"
}
```

Both fields are optional. Recognised controls: `authentication_enabled`, `tls_enabled`, `integrity_check_on_load`, `allow_pickle`, `rate_limiting_enabled`, `input_validation_enabled`, `debug_mode`, `runs_as_root`, `egress_restricted`.

### Drift

```json
{
  "features": {
    "income": {"reference": [5.1, 4.9, 5.3], "current": [6.2, 6.0, 5.8]},
    "channel": {"reference": ["web", "branch"], "current": ["web", "web"], "kind": "categorical"}
  },
  "psi_threshold": 0.2,
  "alpha": 0.05
}
```

### Explain

```json
{"feature_names": ["a", "b"], "X": [[1, 2], [2, 1], [3, 5], [4, 2]], "predictions": [0.2, 0.4, 0.7, 0.6]}
```

Fits a linear surrogate to recorded inputs and predictions. The model itself is not executed. Check `fidelity_r2` before relying on the result. For permutation importance, occlusion attribution or SHAP, use the Python SDK and store the report with `AIGuard.record_explanation`.

## Policies

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/policies` | viewer | List defined policies |
| POST | `/policies/evaluate` | analyst | Evaluate policies for a model |

```json
{"model_id": "mdl_1a2b3c4d5e6f", "policy_ids": ["GOV-INT-001"]}
```

Omit `policy_ids` to evaluate all policies.

## Lineage

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/lineage/nodes` | analyst | Add a dataset, transformation, training run, evaluation or deployment |
| POST | `/lineage/edges` | analyst | Link two nodes (`src_id` feeds `dst_id`) |

Model version nodes are created by registration; find a model's node as `root` in `GET /models/{id}/lineage`. Edges must follow the lineage order and cannot form cycles.

## Audit and system

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/audit` | viewer | Recent events across all models (`?limit=`) |
| GET | `/audit/verify` | viewer | Verify the hash chain |
| GET | `/stats` | viewer | Aggregate posture for the dashboard |
| GET | `/me` | viewer | The caller's name and role |

`GET /healthz` (outside `/api/v1`) needs no key and returns `{"status": "ok"}`.
