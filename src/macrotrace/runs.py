"""Workflow run execution command hooks."""

from __future__ import annotations

from macrotrace.schemas.experiment import ExperimentConfig


def execute_runs(
    experiment: str | None,
    config: ExperimentConfig | None,
    max_concurrency: int | None,
    adapter: str | None,
    dry_run: bool,
) -> None:
    """Execute workflow runs for an experiment."""

    experiment_name = experiment
    if experiment_name is None and config is not None:
        experiment_name = config.experiment.name

    raise NotImplementedError(
        "Run execution is not implemented yet. "
        f"experiment={experiment_name}, max_concurrency={max_concurrency}, "
        f"adapter={adapter}, dry_run={dry_run}."
    )
