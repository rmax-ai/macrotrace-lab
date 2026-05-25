"""Pattern discovery and diagnosis domain schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BehaviorPattern(BaseModel):
    """A recurring behavior cluster discovered across runs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(description="Unique identifier for the discovered behavior pattern.")
    experiment_id: str = Field(description="Experiment identifier for the pattern.")
    cluster_id: int = Field(description="Cluster identifier assigned by the discovery pipeline.")
    label: str = Field(description="Human-readable label for the pattern.")
    keywords: list[str] = Field(description="Keywords summarizing the pattern.")
    trace_count: int = Field(ge=0, description="Number of traces assigned to the pattern.")
    prevalence_share: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of included traces represented by the pattern.",
    )
    severity_weighted_prevalence: float = Field(
        ge=0.0,
        description="Prevalence weighted by severity across runs in the pattern.",
    )
    impact_score: float = Field(ge=0.0, description="Overall impact score used for ranking.")
    dominant_case_type: str | None = Field(
        default=None,
        description="Most common scenario case type represented in the pattern.",
    )
    dominant_finding_type: str | None = Field(
        default=None,
        description="Most common finding type represented in the pattern.",
    )
    dominant_owner: str | None = Field(
        default=None,
        description="Most likely owning team, agent, or component for the pattern.",
    )
    representative_run_ids: list[str] = Field(
        description="Representative run identifiers used for inspection."
    )


class DiagnosisSuspect(BaseModel):
    """A ranked suspect node associated with a behavior pattern."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suspect_id: str = Field(description="Unique identifier for the diagnosis suspect.")
    pattern_id: str = Field(description="Pattern identifier this suspect belongs to.")
    node_signature: str = Field(description="Stable graph node signature for the suspect.")
    node_kind: str = Field(description="Kind of graph node represented by the suspect.")
    agent_name: str | None = Field(default=None, description="Agent associated with the suspect.")
    tool_name: str | None = Field(default=None, description="Tool associated with the suspect.")
    proximity_score: float = Field(
        ge=0.0,
        description="Proximity-based score relative to anchor failure events.",
    )
    frequency_score: float = Field(
        ge=0.0,
        description="Frequency-based score across traces in the pattern.",
    )
    bridge_score: float = Field(
        ge=0.0,
        description="Bridge centrality score within the execution graph.",
    )
    role_score: float = Field(ge=0.0, description="Role prior score for the suspect node.")
    suspect_score: float = Field(
        ge=0.0,
        description="Final combined suspect score used for ranking.",
    )
    trace_coverage_share: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of traces in the pattern covered by the suspect.",
    )
    explanation: str = Field(description="Human-readable explanation for the suspect ranking.")
