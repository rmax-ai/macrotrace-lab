"""Evaluation pipeline orchestration."""

from __future__ import annotations

from collections.abc import Sequence

import structlog
from sqlmodel import Session

from macrotrace.db import (
    create_eval_finding,
    list_runs,
    list_scenarios,
    list_trace_events,
)
from macrotrace.evals.deterministic import DEFAULT_DETERMINISTIC_EVALUATORS, Evaluator
from macrotrace.exceptions import EvalError
from macrotrace.schemas.eval import EvalFinding
from macrotrace.schemas.scenario import Scenario
from macrotrace.schemas.trace import TraceEvent

logger = structlog.get_logger(__name__)


class EvalPipeline:
    """Run deterministic evaluators over all runs in an experiment."""

    def __init__(self, evaluators: Sequence[Evaluator] | None = None) -> None:
        """Initialize the pipeline with an ordered evaluator set."""

        self._evaluators = tuple(evaluators or DEFAULT_DETERMINISTIC_EVALUATORS)

    def run_evals(self, experiment_id: str, db_session: Session) -> list[EvalFinding]:
        """Run all configured evaluators for every run in an experiment."""

        runs = list_runs(db_session, experiment_id=experiment_id)
        scenarios_by_id = {
            scenario.scenario_id: scenario for scenario in list_scenarios(db_session)
        }

        findings: list[EvalFinding] = []
        for run in runs:
            scenario = scenarios_by_id.get(run.scenario_id)
            if scenario is None:
                raise EvalError(
                    f"Run '{run.run_id}' references missing scenario '{run.scenario_id}'."
                )

            events = list_trace_events(db_session, run_id=run.run_id)
            findings.extend(
                self._evaluate_run(
                    db_session=db_session,
                    scenario=scenario,
                    events=events,
                    run_findings=[
                        evaluator.evaluate(run, scenario, events) for evaluator in self._evaluators
                    ],
                )
            )

        logger.info(
            "eval_pipeline_completed",
            experiment_id=experiment_id,
            run_count=len(runs),
            finding_count=len(findings),
        )
        return findings

    def _evaluate_run(
        self,
        *,
        db_session: Session,
        scenario: Scenario,
        events: Sequence[TraceEvent],
        run_findings: Sequence[EvalFinding],
    ) -> list[EvalFinding]:
        """Persist findings for one run and return the stored records."""

        stored_findings: list[EvalFinding] = []
        for finding in run_findings:
            stored_findings.append(create_eval_finding(db_session, finding))
            logger.info(
                "eval_finding_created",
                run_id=finding.run_id,
                scenario_id=scenario.scenario_id,
                finding_id=finding.finding_id,
                evaluator_name=finding.evaluator_name,
                finding_type=finding.finding_type.value,
                passed=finding.passed,
                evidence_event_count=len(finding.evidence_event_ids),
                trace_event_count=len(events),
            )
        return stored_findings
