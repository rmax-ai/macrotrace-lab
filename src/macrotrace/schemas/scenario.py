"""Scenario domain schema."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

CaseType: TypeAlias = Literal[  # noqa: UP040
    "clean_purchase",
    "budget_threshold",
    "sensitive_data_vendor",
    "existing_tool_duplicate",
    "unclear_data_usage",
    "vendor_risk_flag",
    "policy_exception",
    "runtime_tool_failure",
]
GroundTruthValue: TypeAlias = bool | list[str]  # noqa: UP040


class Scenario(BaseModel):
    """A single scenario used to exercise the workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(description="Unique identifier for the scenario.")
    dataset_id: str = Field(description="Identifier for the dataset that contains the scenario.")
    case_type: CaseType = Field(description="Scenario case type classification.")
    request_text: str = Field(description="End-user request presented to the workflow.")
    expected_outcome: str | None = Field(
        default=None,
        description="Expected workflow outcome for the scenario, when defined.",
    )
    ground_truth: dict[str, GroundTruthValue] = Field(
        description="Expected control decisions and review requirements for this scenario."
    )
    environmental_signals: dict[str, int | str | float | bool | None] = Field(
        description="Structured business and policy signals relevant to the scenario."
    )
    severity_if_mishandled: int = Field(
        ge=1,
        le=5,
        description="Severity of harm if the scenario is handled incorrectly, from 1 to 5.",
    )
    tags: list[str] = Field(description="Free-form tags associated with the scenario.")
