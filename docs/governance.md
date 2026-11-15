# Governance and policies

AIGuard turns governance requirements into checks that run against recorded evidence.

## Evidence

Every operation stores its result as evidence and appends an audit event in the same transaction.

| Kind | Created by | Status values |
|---|---|---|
| `integrity` | verify | `pass`, `fail` |
| `security_assessment` | assess | `pass`, `fail` (fail = a high or critical finding) |
| `drift` | drift | `stable`, `drift_detected` |
| `explanation` | explain | `generated` |
| `risk_assessment` | risk | `low`, `medium`, `high`, `critical` |
| `policy_evaluation` | policies/evaluate | `pass`, `fail` |

Policies always look at the latest evidence of each kind.

## Built-in policies

| ID | Requirement | Passes when |
|---|---|---|
| GOV-DOC-001 | Documentation is complete | Description, owner and intended use are filled in. |
| GOV-PRV-001 | Training data provenance is recorded | Lineage reaches at least one dataset, and every upstream dataset has a fingerprint. |
| GOV-INT-001 | Artifact integrity is verified | The latest verification passed. |
| GOV-SEC-001 | No open high-severity findings | An assessment exists with nothing above medium. |
| GOV-XAI-001 | An explanation is available | Explanation evidence exists. |
| GOV-RSK-001 | Risk assessment is complete | Risk evidence exists. |
| GOV-MON-001 | Drift monitoring is current | Drift was evaluated in the last 30 days. |
| GOV-HUM-001 | Human oversight is defined | For high-impact models, an oversight process is recorded. |
| GOV-AUD-001 | Audit records are available | The model has audit events and the chain verifies. |

Each result carries the policy identifier, status (`pass`, `fail`, `not_applicable`, `error`), evidence references, an explanation, and a corrective action when it fails.

## Writing your own policies

Policies are YAML. Copy [`default_policies.yaml`](../src/aiguard/governance/default_policies.yaml), edit it, keep it in version control, and set `AIGUARD_POLICY_FILE`.

```yaml
version: 1
policies:
  - id: ORG-MON-007
    title: Drift is checked weekly for high-impact models
    category: monitoring
    severity: high
    check: evidence_status
    params: {kind: drift, max_age_days: 7, required_status: stable}
    applies_to_tiers: [high]
    remediation: Evaluate drift on this week's production sample.
```

Available checks: `documentation_complete`, `dataset_provenance`, `evidence_status`, `no_open_findings`, `human_oversight_defined`, `audit_records_available`.

Register a custom check in Python:

```python
from aiguard.governance.policy_engine import register_check

@register_check("owner_is_a_team")
def owner_is_a_team(ctx, params):
    ok = ctx.model["owner"].endswith("Team")
    return ok, [], "Owner is a team." if ok else "Owner must be a team, not a person."
```

A check that raises is reported as `error` and fails the evaluation; it does not hide other results.

## Risk score

An additive score from 0 to 100:

| Factor | Maximum |
|---|---|
| Declared impact tier | 30 |
| Highest open security finding | 25 |
| Artifact integrity | 20 |
| Drift | 10 |
| Documentation gaps | 10 |
| Explainability | 5 |

Levels: low (under 25), medium (25–49), high (50–74), critical (75 and above). Missing evidence scores as partial risk, since unknown is not the same as safe.

The score is a prioritisation aid. It is not a measure of real-world harm.

## Evidence reports

`aiguard report <model-id>` and `GET /api/v1/models/{id}/report` produce a report with the model identity, each control's status and evidence, corrective actions, and the audit chain status, in JSON or Markdown.

The report's NIST AI RMF column is an indicative mapping from policy category to core function. It does not constitute certification or regulatory compliance.
