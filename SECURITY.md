# Security policy

## Supported versions

AIGuard is in alpha. Only the latest commit on `main` receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue or pull request for a security problem.

Include, where you can:

- the affected version or commit;
- what an attacker can do, and what access they need;
- steps or a proof of concept to reproduce it.

This is a volunteer-maintained project. Expect an acknowledgement within about a week. Fixes are released on `main` with credit to the reporter unless you ask otherwise.

## Scope

In scope:

- authentication or authorisation bypass in the API;
- reading files outside the artifact directory;
- an artifact that causes code execution, or a crash, in the scanner;
- a dangerous artifact pattern that the scanner should detect but does not;
- audit-chain tampering that verification fails to detect;
- script injection in the dashboard.

Out of scope:

- anything requiring full database or host access (see the audit log limits in [docs/security-model.md](docs/security-model.md));
- the in-memory rate limiter not being shared across replicas;
- vulnerabilities in dependencies with no impact on AIGuard.
