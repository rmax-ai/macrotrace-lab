"""Evaluation finding domain schema."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FindingType(StrEnum):
    """Finding categories emitted by evaluators."""

    ROUTING_ERROR = "routing_error"
    TOOL_USE_ERROR = "tool_use_error"
    POLICY_VIOLATION = "policy_violation"
    MISSING_REVIEW = "missing_review"
    INCORRECT_DECISION = "incorrect_decision"
    GROUNDING_FAILURE = "grounding_failure"
    RUNTIME_FAILURE = "runtime_failure"
    COST_ANOMALY = "cost_anomaly"
    LATENCY_ANOMALY = "latency_anomaly"
    NONE = "none"


class EvalFinding(BaseModel):
    """A typed evaluator finding attached to a workflow run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(description="Unique identifier for the finding.")
    run_id: str = Field(description="Identifier for the run this finding belongs to.")
    evaluator_name: str = Field(description="Name of the evaluator that produced the finding.")
    evaluator_version: str = Field(
        description="Version of the evaluator logic that produced the finding."
    )
    finding_type: FindingType = Field(description="Category of evaluation finding.")
    passed: bool = Field(description="Whether the evaluated check passed.")
    severity: int = Field(ge=0, le=5, description="Severity score from 0 to 5.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the finding from 0.0 to 1.0.",
    )
    evidence_event_ids: list[str] = Field(
        description="Event identifiers that support the finding conclusion."
    )
    explanation: str = Field(description="Human-readable explanation of the finding.")
    expected_behavior: str = Field(
        description="Expected behavior for the evaluated workflow condition."
    )
    observed_behavior: str = Field(
        description="Observed behavior that led to the evaluator result."
    )
