# Security model

How AIGuard protects itself and the records it keeps. For the threats this is designed against, see the [threat model](threat-model.md).

## Trust boundaries

| Zone | Trust | Handling |
|---|---|---|
| External model artifacts | Untrusted | Inspected as bytes. Never unpickled, imported or executed. |
| API request bodies | Untrusted | Validated by strict schemas: unknown fields rejected, sizes bounded. |
| Artifact paths from the API | Untrusted | Resolved (including symlinks) and required to stay inside `AIGUARD_ARTIFACT_DIR`. |
| Registered digests and metadata | Trusted after registration | Stored in the database; changes are visible in the audit log. |
| Audit records | Tamper-evident | Hash-chained; verified on demand and before policy evaluation. |
| CLI and SDK callers | Trusted | They run with the operator's own file access. |

## Authentication and authorisation

- Every `/api/v1` endpoint requires an `X-API-Key` header. Only `/healthz`, the dashboard's static files and the OpenAPI document are public.
- Keys are compared in constant time against every configured key.
- Roles are ordered `viewer` < `analyst` < `admin`. Reads need `viewer`; anything that creates evidence or records needs `analyst`.
- Authentication runs before request validation, so unauthenticated callers learn nothing from validation errors.
- If `AIGUARD_API_KEYS` is unset, the server generates a random admin key for that process and prints it to stderr. It never starts unauthenticated. Malformed key configuration stops startup.
- The audit actor comes from the authenticated key, never from the request body.

## Request limits

- Per-key sliding-window rate limit (default 120 requests per minute).
- Request bodies over 20 MB are rejected before parsing.
- Arrays are bounded: 100,000 values per drift sample, 200 features, 5,000 explanation rows.

## Artifact inspection

`aiguard.security.vulnerability` disassembles pickle streams with `pickletools` and reads archives member by member. It reports:

- imports of code-execution primitives (`os.system`, `subprocess`, `eval`, and similar);
- indirect-call helpers and unrecognised modules;
- archive members that escape the extraction directory, bundled Python source, extreme compression ratios;
- Keras Lambda layers;
- files whose extension does not match their content.

Member reads are capped, and files above `AIGUARD_MAX_SCAN_BYTES` are skipped with a finding.

## Dashboard

- Served with a Content-Security-Policy of `default-src 'self'` and no inline scripts or styles.
- No third-party scripts, fonts or network calls.
- API data is written to the page as text, never as HTML.
- The API key is held in `sessionStorage` for the tab only.

## Audit log

Each event stores the SHA-256 of its own content and the hash of the previous event. Verification recomputes every hash and link, and reports the first inconsistency.

This is tamper **evidence**, not tamper **prevention**. Someone with full write access to the database can rewrite the chain from any point onward. To detect that, record the head hash (shown on the dashboard's audit page and returned by `/api/v1/audit/verify`) somewhere that person cannot change.

A unique constraint on the previous-hash column stops two writers from extending the same chain head.

## Deployment guidance

- Terminate TLS in front of the service.
- Run as the unprivileged user provided in the image, with a read-only root filesystem.
- Supply keys and database credentials through a secret manager, not through files in the repository.
- Run one replica; see the note in the Kubernetes manifest.
- Pin and scan dependencies. CI runs lint, type checks and tests on every change.

## What is not covered

- Encryption at rest is the responsibility of the database and storage layer.
- There is no key management integration yet; manifest signing uses a caller-supplied HMAC key.
- API keys are static. There is no rotation endpoint, SSO or per-model permission.
