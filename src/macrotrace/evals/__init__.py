"""MacroTrace Lab — evaluation engine and rubric system."""

from __future__ import annotations

from macrotrace.schemas.experiment import ExperimentConfig


def run_evals(experiment: str, config: ExperimentConfig | None) -> None:
    """Run evaluators for an experiment."""

    raise NotImplementedError(
        "Evaluation execution is not implemented yet. "
        f"experiment={experiment}, config_loaded={config is not None}."
    )


def summarize_evals(experiment: str) -> None:
    """Summarize evaluator results for an experiment."""

    raise NotImplementedError(f"Evaluation summary is not implemented yet for '{experiment}'.")
