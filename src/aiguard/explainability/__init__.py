"""Feature attribution and explanation reports."""

from aiguard.explainability.explainer import (
    ATTRIBUTION_NOTICE,
    local_attribution,
    permutation_importance,
    shap_explanation,
    surrogate_explanation,
)

__all__ = [
    "ATTRIBUTION_NOTICE",
    "local_attribution",
    "permutation_importance",
    "shap_explanation",
    "surrogate_explanation",
]
