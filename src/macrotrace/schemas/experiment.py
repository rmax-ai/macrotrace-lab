"""Experiment metadata and configuration schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Experiment(BaseModel):
    """Metadata describing an executed experiment."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    experiment_id: str = Field(description="Unique identifier for the experiment.")
    name: str = Field(description="Human-readable name of the experiment.")
    created_at: datetime = Field(description="Timestamp when the experiment metadata was created.")
    workflow_name: str = Field(description="Workflow implementation name used by the experiment.")
    workflow_version: str = Field(description="Workflow version used by the experiment.")
    config_hash: str = Field(description="SHA256 hash of the fully resolved experiment config.")
    baseline_experiment_id: str | None = Field(
        default=None,
        description="Optional baseline experiment identifier for comparisons.",
    )
    scenario_dataset_id: str = Field(
        description="Scenario dataset identifier used by the experiment."
    )
    model_settings: dict[str, object] = Field(
        description="Resolved model configuration for the experiment."
    )
    agent_config: dict[str, object] = Field(
        description="Resolved agent configuration for the experiment."
    )
    fault_injections: list[str] = Field(description="Fault injections enabled for the experiment.")
    notes: str | None = Field(
        default=None,
        description="Optional notes attached to the experiment.",
    )


class ExperimentMetadata(BaseModel):
    """Top-level experiment execution settings loaded from YAML."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Human-readable experiment name.")
    workflow_name: str = Field(description="Workflow implementation name to execute.")
    workflow_version: str = Field(description="Workflow version identifier to execute.")
    scenario_dataset: str = Field(description="Scenario dataset path or identifier to load.")
    seed: int = Field(description="Base random seed for the experiment.")
    runs_per_scenario: int = Field(
        ge=1,
        description="Number of runs to execute per scenario in the dataset.",
    )
    max_concurrency: int = Field(
        ge=1,
        description="Maximum number of concurrent runs allowed during execution.",
    )


class ModelSettings(BaseModel):
    """Model selections used by the workflow and evaluators."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    coordinator: str = Field(description="Model identifier used for the coordinator agent.")
    specialists: str = Field(description="Model identifier used for specialist agents.")
    judge: str = Field(description="Model identifier used for the judge or evaluator.")


class DiscoverySettings(BaseModel):
    """Settings for the pattern discovery pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    include_runs: str = Field(description="Selector for which runs to include in discovery.")
    embedding_model: str = Field(description="Embedding model identifier for trace documents.")
    min_cluster_size: int = Field(
        ge=1,
        description="Minimum HDBSCAN cluster size for discovered behavior patterns.",
    )
    random_seed: int = Field(description="Random seed used by the discovery pipeline.")


class ExperimentConfig(BaseModel):
    """Validated experiment configuration loaded from YAML."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment: ExperimentMetadata = Field(description="Top-level experiment execution settings.")
    models: ModelSettings = Field(description="Model settings for workflow execution.")
    discovery: DiscoverySettings = Field(description="Pattern discovery pipeline settings.")
    fault_injections: list[str] = Field(description="Enabled fault injection identifiers.")
