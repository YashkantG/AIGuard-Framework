# Contributing to AIGuard

Thanks for your interest. Bug reports, reviews, new checks and documentation fixes are all welcome.

## Set up

```bash
git clone https://github.com/YashkantG/AIGuard-Framework.git
cd AIGuard-Framework
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Before you open a pull request

```bash
ruff check .
mypy
pytest --cov=aiguard
```

CI runs the same three commands on Python 3.12 and 3.13.

## Guidelines

- **Tests come with the change.** Unit tests live in `tests/unit`, API flows in `tests/integration`, and anything about untrusted input or access control in `tests/security`.
- **Never execute an untrusted artifact.** Scanner code must not unpickle, import or run what it inspects. Tests may *create* malicious pickles with `pickle.dumps`; they must never load them.
- **Use synthetic or public data only.** Do not add proprietary datasets, models, credentials or internal material from any employer.
- **Be precise about claims.** Findings are findings, not proof of security. Do not add accuracy, performance or adoption claims without a reproducible measurement.
- **New security checks** need a stable finding ID (`AIG-XXX-NNN`), a severity, a recommendation, and a test for both a positive and a negative case.
- **New policy checks** are registered with `register_check` and documented in `docs/governance.md`.
- Keep changes focused. Separate refactors from behaviour changes.

## Contributions and licensing

By contributing you agree that your contribution is licensed under the Apache License 2.0, and you confirm that you have the right to submit it. If your employment agreement covers work like this, get any clearance you need first.

## Reporting security issues

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).
