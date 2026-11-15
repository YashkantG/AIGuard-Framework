# AIGuard Framework

[![CI](https://github.com/YashkantG/AIGuard-Framework/actions/workflows/ci.yml/badge.svg)](https://github.com/YashkantG/AIGuard-Framework/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)

An open framework for AI model governance and security. AIGuard records what a model is, checks that it has not changed, inspects it for known risks, watches for drift, explains its behaviour, and turns governance requirements into executable policies backed by evidence.

**Status:** alpha (0.1.0). The API may change. See [Limitations](#limitations).

## What it does

| Capability | What you get |
|---|---|
| Model integrity | SHA-256 registration and verification, signed manifests |
| Security assessment | Static inspection of artifacts (pickle, archives, Keras, safetensors) without loading them; deployment and dependency checks |
| Drift detection | Population Stability Index and Kolmogorov-Smirnov tests for numeric and categorical data |
| Explainability | Permutation importance, occlusion attribution, linear surrogates, optional SHAP |
| Provenance | Dataset → transformation → training run → model → evaluation → deployment lineage, stored as fingerprints |
| Governance | YAML policies evaluated against recorded evidence, risk scoring, evidence reports |
| Audit | Hash-chained, tamper-evident event log |
| Interfaces | Python SDK, CLI, REST API, web dashboard, CI/CD gate |

## Quick start

```bash
git clone https://github.com/YashkantG/AIGuard-Framework.git
cd AIGuard-Framework
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Dashboard

```bash
aiguard seed-demo        # three synthetic models in different states
aiguard serve            # http://127.0.0.1:8000
```

`aiguard serve` prints a temporary admin API key when `AIGUARD_API_KEYS` is not set. Paste it into the sign-in screen. The dashboard shows posture across models and, per model, security findings, drift, feature attribution, policy results, lineage and audit history.

### Command line

```bash
aiguard scan model.pkl                    # static inspection, no database needed
aiguard register fraud 1.0.0 model.pkl --owner "Risk" --description "Fraud scoring"
aiguard verify <model-id>                 # exit 1 if the file no longer matches
aiguard assess <model-id>
aiguard gate <model-id>                   # exit 1 if any policy fails
aiguard report <model-id> --output report.md
aiguard audit-verify
```

### Python SDK

```python
from aiguard import AIGuard
from aiguard.core.models import ModelCreate

guard = AIGuard()
model = guard.register_model(
    ModelCreate(name="fraud", version="1.0.0", artifact_path="model.safetensors", owner="Risk")
)
guard.verify_integrity(model["id"])
guard.assess_security(model["id"])
guard.assess_risk(model["id"])
print(guard.evaluate_policies(model["id"])["summary"])
```

[examples/quickstart.py](examples/quickstart.py) runs the whole lifecycle on synthetic data.

### REST API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/models` | Register model |
| GET | `/api/v1/models/{id}` | Retrieve model metadata |
| POST | `/api/v1/models/{id}/verify` | Verify integrity |
| POST | `/api/v1/models/{id}/explain` | Generate explanations |
| POST | `/api/v1/models/{id}/assess` | Run security assessment |
| POST | `/api/v1/models/{id}/drift` | Evaluate drift |
| GET | `/api/v1/models/{id}/audit` | Retrieve audit history |
| POST | `/api/v1/policies/evaluate` | Evaluate governance policies |

Every endpoint requires an `X-API-Key` header. The full list is in [docs/api-reference.md](docs/api-reference.md) and, on a running server, at `/api/docs`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AIGUARD_DATABASE_URL` | `sqlite:///./aiguard.db` | SQLAlchemy URL. Use `postgresql+psycopg://...` with the `postgres` extra. |
| `AIGUARD_ARTIFACT_DIR` | `./artifacts` | The only directory the API may read artifacts from. |
| `AIGUARD_API_KEYS` | none | Comma-separated `name:role:key`. Roles: `viewer`, `analyst`, `admin`. Keys need 16+ characters. |
| `AIGUARD_RATE_LIMIT_PER_MINUTE` | `120` | Per-key request limit. |
| `AIGUARD_POLICY_FILE` | built-in set | Path to your own policy YAML. |

## Deployment

- Docker and PostgreSQL: [deployment/docker](deployment/docker)
- Kubernetes: [deployment/kubernetes/aiguard.yaml](deployment/kubernetes/aiguard.yaml)
- Pipeline gate for GitHub Actions: [examples/github-actions/model-gate.yml](examples/github-actions/model-gate.yml)

Put TLS in front of the service; AIGuard does not terminate TLS itself.

## Documentation

- [Architecture and design](docs/architecture.md)
- [Security model](docs/security-model.md)
- [Threat model](docs/threat-model.md)
- [Governance and policies](docs/governance.md)
- [API reference](docs/api-reference.md)

## Development

```bash
ruff check .
mypy
pytest --cov=aiguard
python benchmarks/run_benchmarks.py
```

## Limitations

- AIGuard reports findings, evidence and recommendations. It does not guarantee regulatory compliance and does not prove that a model is secure or unbiased.
- The artifact scanner matches known patterns. A clean scan means nothing known was found.
- Robustness testing uses random perturbations, not worst-case adversarial attacks.
- Feature attribution describes model behaviour. It is not evidence of causation.
- The audit log is tamper-evident, not tamper-proof: someone with full database access can rewrite the whole chain. Anchor the head hash externally.
- The service is designed to run as a single replica. The rate limiter is in process memory.
- Dependency checks flag unpinned requirements only. Use a software composition analysis tool for known vulnerabilities.
- Mappings to NIST AI RMF and similar frameworks are indicative and do not constitute certification.
- No adoption, accuracy or performance claims are made. The benchmark script exists so you can measure on your own hardware.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## License and independence

Apache License 2.0. See [LICENSE](LICENSE).

AIGuard is an independent open-source project built with public and synthetic data only. No employer affiliation, endorsement or ownership is implied.
