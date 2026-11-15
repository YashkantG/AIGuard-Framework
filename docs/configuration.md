# Configuration and deployment

## Settings

AIGuard reads its settings from environment variables (or a `.env` file in the working directory).

| Variable | Default | Purpose |
|---|---|---|
| `AIGUARD_DATABASE_URL` | `sqlite:///./aiguard.db` | Where records are stored. Use `postgresql+psycopg://...` with the `postgres` extra for shared deployments. |
| `AIGUARD_ARTIFACT_DIR` | `./artifacts` | The only folder the API may read model files from. |
| `AIGUARD_API_KEYS` | none | Comma-separated `name:role:key` entries. Roles: `viewer`, `analyst`, `admin`. Keys need 16 or more characters. |
| `AIGUARD_RATE_LIMIT_PER_MINUTE` | `120` | Request limit per API key. |
| `AIGUARD_MAX_REQUEST_BYTES` | 20 MB | Largest accepted request body. |
| `AIGUARD_MAX_SCAN_BYTES` | 2 GB | Largest file the scanner will inspect. |
| `AIGUARD_POLICY_FILE` | built-in set | Path to your own policy YAML. See [governance](governance.md). |

If `AIGUARD_API_KEYS` is not set, `aiguard serve` prints a temporary admin key each time it starts. It never runs without authentication.

## Roles

| Role | Can do |
|---|---|
| `viewer` | Read models, evidence, reports and the audit log |
| `analyst` | Everything a viewer can, plus register models and run checks |
| `admin` | Same as analyst today; reserved for future administration features |

## Running the server

```bash
aiguard serve --host 127.0.0.1 --port 8000
```

The dashboard is at `/`, the API under `/api/v1`, and interactive API documentation at `/api/docs`.

## Docker with PostgreSQL

```bash
cd deployment/docker
cp .env.example .env    # then fill in real values
docker compose up --build
```

## Kubernetes

[`deployment/kubernetes/aiguard.yaml`](../deployment/kubernetes/aiguard.yaml) is an example manifest. The comments at the top list what to change before applying it.

## CI/CD

[`examples/github-actions/model-gate.yml`](../examples/github-actions/model-gate.yml) scans and verifies a model file in a GitHub Actions pipeline.

## Production notes

- Put TLS in front of the service. AIGuard does not terminate TLS itself.
- Run a single replica. The rate limiter lives in process memory.
- Keep API keys and database passwords in a secret manager, not in the repository.
- The Docker and Kubernetes files are examples; test them in your own environment before relying on them.
