"""Scenario generation command hooks."""

from __future__ import annotations

from pathlib import Path

from macrotrace.schemas.experiment import ExperimentConfig


def generate_scenarios(
    config: ExperimentConfig,
    count: int,
    seed: int | None,
    output: Path | None,
) -> None:
    """Generate scenarios for an experiment."""

    raise NotImplementedError(
        "Scenario generation is not implemented yet. "
        f"Loaded experiment '{config.experiment.name}' "
        f"with count={count}, seed={seed}, output={output}."
    )
