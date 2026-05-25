"""MacroTrace Lab evaluation entrypoints."""

from __future__ import annotations

from macrotrace.db import get_session
from macrotrace.evals.engine import EvalPipeline
from macrotrace.schemas.eval import EvalFinding
from macrotrace.schemas.experiment import ExperimentConfig


def run_evals(experiment: str, config: ExperimentConfig | None) -> list[EvalFinding]:
    """Run evaluators for an experiment."""

    del config
    with get_session() as session:
        return EvalPipeline().run_evals(experiment_id=experiment, db_session=session)


def summarize_evals(experiment: str) -> None:
    """Summarize evaluator results for an experiment."""

    raise NotImplementedError(f"Evaluation summary is not implemented yet for '{experiment}'.")
