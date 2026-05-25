"""LLM judge placeholders for future evaluation phases."""

from __future__ import annotations

from collections.abc import Sequence

from macrotrace.schemas.eval import EvalFinding
from macrotrace.schemas.scenario import Scenario
from macrotrace.schemas.trace import Run, TraceEvent


class DecisionExplanationEval:
    """Placeholder LLM judge for checking decision explanations."""

    name = "decision_explanation"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Evaluate whether the final decision is adequately explained.

        Raises:
            NotImplementedError: LLM judges are not implemented yet and require
                `OPENAI_API_KEY`.
        """

        raise NotImplementedError(
            "DecisionExplanationEval is not implemented yet and requires OPENAI_API_KEY."
        )


class TraceCoherenceEval:
    """Placeholder LLM judge for checking trace coherence."""

    name = "trace_coherence"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Evaluate whether the run trace is coherent with the final decision.

        Raises:
            NotImplementedError: LLM judges are not implemented yet and require
                `OPENAI_API_KEY`.
        """

        raise NotImplementedError(
            "TraceCoherenceEval is not implemented yet and requires OPENAI_API_KEY."
        )
