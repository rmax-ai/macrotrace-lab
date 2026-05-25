"""Fault injection helpers for the reference workflow."""

from __future__ import annotations

SUPPORTED_FAULTS = frozenset(
    {
        "skip_security_on_unknown_vendor",
        "coordinator_skip_security_on_low_cost",
        "coordinator_direct_to_procurement",
        "budget_agent_ignore_annualized_cost",
        "security_agent_skip_escalation",
        "policy_agent_omit_review_requirement",
        "procurement_bypass_existing_tool_check",
        "reviewer_skip_review",
    }
)


def apply_faults(workflow_config: dict[str, object], fault_names: list[str]) -> dict[str, object]:
    """Return a workflow configuration with the requested faults enabled."""

    resolved_config = dict(workflow_config)
    for fault_name in fault_names:
        if fault_name not in SUPPORTED_FAULTS:
            available = ", ".join(sorted(SUPPORTED_FAULTS))
            raise ValueError(f"Unsupported fault '{fault_name}'. Available faults: {available}")
        resolved_config[fault_name] = True
    return resolved_config
