# Threat model

Threats considered in the design, what AIGuard does about each, and what remains.

| Threat | Mitigation in AIGuard | Residual risk |
|---|---|---|
| Model tampering | SHA-256 digest recorded at registration; verification before deployment; failures recorded as evidence and block the integrity policy. | A digest registered from an already-tampered file is trusted. Verify the source at registration. |
| Malicious model files | Static inspection without loading; critical findings for code-execution imports; policy blocks high and critical findings. | Pattern-based: novel or obfuscated payloads may not be recognised. |
| Unauthorised access | API keys on every endpoint, role checks, constant-time comparison, no unauthenticated mode. | Static keys can leak. Rotate them and keep them in a secret manager. |
| API exploitation | Strict schemas, bounded inputs, body size limit, rate limiting, path confinement for artifacts. | The rate limiter is per process and in memory. |
| Dataset manipulation | Dataset fingerprints in lineage; a lineage digest that changes when any upstream input changes. | Fingerprints are supplied by the caller; AIGuard does not read the datasets. |
| Audit modification | Hash chain with verification; chain validity is itself a policy. | A database administrator can rewrite the whole chain. Anchor the head hash externally. |
| Dependency compromise | Unpinned-requirement findings; pinned, minimal runtime dependencies; CI on every change. | No vulnerability database lookup. Use a software composition analysis tool. |
| Adversarial inputs | Random-perturbation robustness test in the SDK. | Not a worst-case attack. Use a dedicated adversarial library for that. |
| Cross-site scripting in the dashboard | Strict Content-Security-Policy; data rendered as text; no third-party scripts. | None known. |
| Information disclosure through errors | Authentication precedes validation; path errors do not reveal file contents. | Error messages distinguish "outside the artifact directory" from "not found". |

## Assumptions

- The host, database and artifact storage are administered by trusted operators.
- TLS is terminated in front of the service.
- CLI and SDK users are trusted to the extent of their own operating-system permissions.

## Out of scope

- Attacks on the model's training process itself (data poisoning is detected only insofar as dataset fingerprints change).
- Model extraction and membership inference against a served model.
- Prompt injection and other LLM application risks. The reference frameworks are listed in the [architecture document](architecture.md#16-standards-and-reference-frameworks).
