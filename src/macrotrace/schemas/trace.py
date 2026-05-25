"""Trace and run domain schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

TraceID: TypeAlias = str  # noqa: UP040
RunID: TypeAlias = str  # noqa: UP040
EventID: TypeAlias = str  # noqa: UP040


class EventType(StrEnum):
    """Normalized workflow event types."""

    WORKFLOW_STARTED = "workflow_started"
    AGENT_STARTED = "agent_started"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    HANDOFF = "handoff"
    GUARDRAIL_TRIGGERED = "guardrail_triggered"
    REVIEW_REQUESTED = "review_requested"
    DECISION = "decision"
    ERROR = "error"
    WORKFLOW_COMPLETED = "workflow_completed"


class RunOutcome(StrEnum):
    """Possible terminal outcomes for a workflow run."""

    APPROVED = "approved"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"
    FAILED = "failed"


class TraceEvent(BaseModel):
    """A normalized trace event captured from a workflow execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: EventID = Field(description="Unique identifier for the trace event.")
    trace_id: TraceID = Field(description="Identifier for the trace the event belongs to.")
    run_id: RunID = Field(description="Identifier for the run the event belongs to.")
    sequence_no: int = Field(description="Monotonic sequence number within the trace.")
    timestamp: datetime = Field(description="Timestamp when the event occurred.")
    event_type: EventType = Field(description="Normalized type of event.")
    agent_name: str | None = Field(default=None, description="Agent associated with the event.")
    tool_name: str | None = Field(default=None, description="Tool associated with the event.")
    parent_event_id: EventID | None = Field(
        default=None,
        description="Parent event identifier when this event is causally linked to another event.",
    )
    from_agent: str | None = Field(
        default=None,
        description="Agent handing control off from this event, if applicable.",
    )
    to_agent: str | None = Field(
        default=None,
        description="Agent receiving control from this event, if applicable.",
    )
    input_summary: str | None = Field(
        default=None,
        description="Redacted summary of the input associated with the event.",
    )
    output_summary: str | None = Field(
        default=None,
        description="Redacted summary of the output associated with the event.",
    )
    structured_payload: dict[str, object] = Field(
        description="Structured event payload preserved after normalization."
    )
    policy_reference: str | None = Field(
        default=None,
        description="Policy identifier or citation relevant to the event, if any.",
    )
    severity: int = Field(ge=0, le=5, description="Event severity score from 0 to 5.")
    redacted: bool = Field(description="Whether the event content was redacted.")


class Run(BaseModel):
    """A workflow run and its terminal metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: RunID = Field(description="Unique identifier for the run.")
    trace_id: TraceID = Field(
        description="Identifier for the normalized trace produced by the run."
    )
    experiment_id: str = Field(description="Identifier for the experiment the run belongs to.")
    scenario_id: str = Field(description="Identifier for the source scenario.")
    started_at: datetime = Field(description="Timestamp when the run started.")
    ended_at: datetime | None = Field(default=None, description="Timestamp when the run ended.")
    run_outcome: RunOutcome = Field(description="Final outcome of the run.")
    final_output: str | None = Field(
        default=None,
        description="Final user-visible output produced by the workflow.",
    )
    final_decision: str | None = Field(
        default=None,
        description="Final decision or disposition recorded for the run.",
    )
    human_review_requested: bool = Field(
        description="Whether a human review step was requested during the run."
    )
    cost_estimate_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Estimated run cost in US dollars.",
    )
    latency_ms: int | None = Field(
        default=None,
        ge=0,
        description="Observed run latency in milliseconds.",
    )
    error_type: str | None = Field(
        default=None,
        description="Machine-readable error type when the run failed.",
    )


class RawTrace(BaseModel):
    """Raw adapter payload before normalization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: TraceID = Field(description="Identifier for the raw trace.")
    run_id: RunID = Field(description="Identifier for the run associated with the raw trace.")
    source_adapter: str = Field(description="Adapter that produced the raw trace payload.")
    payload: dict[str, object] = Field(description="Original raw trace payload from the adapter.")
