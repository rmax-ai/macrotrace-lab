from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from macrotrace.db import (
    create_db_engine,
    create_experiment,
    create_run,
    create_scenario,
    create_trace_event,
    get_session,
    init_db,
    list_eval_findings,
)
from macrotrace.evals.deterministic import (
    ForbiddenApprovalEval,
    OutcomeCorrectnessEval,
    RequiredAgentActivationEval,
    ReviewGateEval,
    ToolFailureHandlingEval,
)
from macrotrace.evals.engine import EvalPipeline
from macrotrace.schemas import (
    EventType,
    Experiment,
    FindingType,
    Run,
    RunOutcome,
    Scenario,
    TraceEvent,
)


def test_outcome_correctness_eval_passes_when_outcomes_match() -> None:
    finding = OutcomeCorrectnessEval().evaluate(
        _run(outcome=RunOutcome.APPROVED),
        _scenario(expected_outcome="approved"),
        _terminal_events(),
    )

    assert finding.passed is True
    assert finding.finding_type is FindingType.NONE
    assert finding.severity == 0


def test_outcome_correctness_eval_fails_when_outcomes_mismatch() -> None:
    finding = OutcomeCorrectnessEval().evaluate(
        _run(outcome=RunOutcome.BLOCKED),
        _scenario(expected_outcome="approved"),
        _terminal_events(),
    )

    assert finding.passed is False
    assert finding.finding_type is FindingType.INCORRECT_DECISION
    assert finding.expected_behavior == "Expected workflow outcome 'approved'."


def test_required_agent_activation_eval_passes_when_agents_are_present() -> None:
    finding = RequiredAgentActivationEval().evaluate(
        _run(outcome=RunOutcome.APPROVED),
        _scenario(required_agents=["coordinator", "budget", "procurement"]),
        [
            _event(1, EventType.AGENT_STARTED, agent_name="coordinator"),
            _event(2, EventType.AGENT_STARTED, agent_name="budget"),
            _event(3, EventType.AGENT_STARTED, agent_name="procurement"),
        ],
    )

    assert finding.passed is True
    assert finding.finding_type is FindingType.NONE


def test_required_agent_activation_eval_fails_when_agent_is_missing() -> None:
    finding = RequiredAgentActivationEval().evaluate(
        _run(outcome=RunOutcome.APPROVED),
        _scenario(required_agents=["coordinator", "security", "procurement"]),
        [
            _event(1, EventType.AGENT_STARTED, agent_name="coordinator"),
            _event(2, EventType.AGENT_STARTED, agent_name="procurement"),
        ],
    )

    assert finding.passed is False
    assert finding.finding_type is FindingType.ROUTING_ERROR
    assert "security" in finding.observed_behavior


def test_review_gate_eval_passes_when_review_occurs() -> None:
    finding = ReviewGateEval().evaluate(
        _run(outcome=RunOutcome.REVIEW_REQUIRED, human_review_requested=True),
        _scenario(must_trigger_review=True),
        [_event(1, EventType.REVIEW_REQUESTED, agent_name="release_reviewer")],
    )

    assert finding.passed is True
    assert finding.finding_type is FindingType.NONE


def test_review_gate_eval_fails_when_review_is_missing() -> None:
    finding = ReviewGateEval().evaluate(
        _run(outcome=RunOutcome.APPROVED),
        _scenario(must_trigger_review=True),
        _terminal_events(),
    )

    assert finding.passed is False
    assert finding.finding_type is FindingType.MISSING_REVIEW


def test_forbidden_approval_eval_passes_when_approval_is_blocked() -> None:
    finding = ForbiddenApprovalEval().evaluate(
        _run(outcome=RunOutcome.BLOCKED),
        _scenario(must_not_auto_approve=True),
        _terminal_events(),
    )

    assert finding.passed is True
    assert finding.finding_type is FindingType.NONE


def test_forbidden_approval_eval_fails_when_auto_approval_occurs() -> None:
    finding = ForbiddenApprovalEval().evaluate(
        _run(outcome=RunOutcome.APPROVED),
        _scenario(must_not_auto_approve=True),
        _terminal_events(),
    )

    assert finding.passed is False
    assert finding.finding_type is FindingType.POLICY_VIOLATION


def test_tool_failure_handling_eval_passes_when_failure_is_caught() -> None:
    finding = ToolFailureHandlingEval().evaluate(
        _run(outcome=RunOutcome.FAILED, error_type="tool_timeout"),
        _scenario(expected_outcome="failed"),
        [
            _event(
                1,
                EventType.TOOL_CALLED,
                agent_name="security",
                tool_name="lookup_vendor_risk",
            ),
            _event(2, EventType.ERROR, agent_name="security"),
            _event(3, EventType.WORKFLOW_COMPLETED),
        ],
    )

    assert finding.passed is True
    assert finding.finding_type is FindingType.NONE


def test_tool_failure_handling_eval_fails_when_failure_is_uncaught() -> None:
    finding = ToolFailureHandlingEval().evaluate(
        _run(outcome=RunOutcome.APPROVED),
        _scenario(expected_outcome="approved"),
        [
            _event(
                1,
                EventType.TOOL_CALLED,
                agent_name="security",
                tool_name="lookup_vendor_risk",
            ),
            _event(2, EventType.DECISION, agent_name="release_reviewer"),
            _event(3, EventType.WORKFLOW_COMPLETED),
        ],
    )

    assert finding.passed is False
    assert finding.finding_type is FindingType.RUNTIME_FAILURE
    assert "lookup_vendor_risk" in finding.observed_behavior


def test_eval_pipeline_runs_and_persists_findings(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "macrotrace.db")
    init_db(engine)
    timestamp = datetime(2026, 5, 25, tzinfo=UTC)

    scenario = _scenario(
        scenario_id="scenario-pipeline",
        expected_outcome="review_required",
        required_agents=[
            "coordinator",
            "budget",
            "policy",
            "security",
            "procurement",
            "release_reviewer",
        ],
        must_trigger_review=True,
        must_not_auto_approve=True,
    )
    experiment = Experiment(
        experiment_id="experiment-1",
        name="Eval Pipeline Test",
        created_at=timestamp,
        workflow_name="reference_workflow",
        workflow_version="1.0.0",
        config_hash="config-hash",
        baseline_experiment_id=None,
        scenario_dataset_id="dataset-1",
        model_settings={"coordinator": "test-model"},
        agent_config={"specialists": ["budget", "policy", "security"]},
        fault_injections=[],
        notes=None,
    )
    run = _run(
        run_id="run-pipeline",
        scenario_id=scenario.scenario_id,
        experiment_id=experiment.experiment_id,
        outcome=RunOutcome.REVIEW_REQUIRED,
        human_review_requested=True,
    )
    events = [
        _event(
            1,
            EventType.AGENT_STARTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="coordinator",
        ),
        _event(
            2,
            EventType.AGENT_STARTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="budget",
        ),
        _event(
            3,
            EventType.AGENT_STARTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="policy",
        ),
        _event(
            4,
            EventType.AGENT_STARTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="security",
        ),
        _event(
            5,
            EventType.AGENT_STARTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="procurement",
        ),
        _event(
            6,
            EventType.AGENT_STARTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="release_reviewer",
        ),
        _event(
            7,
            EventType.REVIEW_REQUESTED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="release_reviewer",
        ),
        _event(8, EventType.WORKFLOW_COMPLETED, run_id=run.run_id, trace_id=run.trace_id),
    ]

    with get_session(engine) as session:
        create_scenario(session, scenario)
        create_experiment(session, experiment)
        create_run(session, run)
        for event in events:
            create_trace_event(session, event)

        findings = EvalPipeline().run_evals(
            experiment_id=experiment.experiment_id,
            db_session=session,
        )

        assert len(findings) == 5
        assert len(list_eval_findings(session, run_id=run.run_id)) == 5
        assert all(finding.passed for finding in findings)


def _scenario(
    *,
    scenario_id: str = "scenario-1",
    expected_outcome: str | None = None,
    required_agents: list[str] | None = None,
    must_trigger_review: bool = False,
    must_not_auto_approve: bool = False,
) -> Scenario:
    """Build a test scenario."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id="dataset-1",
        case_type="runtime_tool_failure",
        request_text="Review the purchase request.",
        expected_outcome=expected_outcome,
        ground_truth={
            "must_activate_agents": required_agents or [],
            "must_trigger_review": must_trigger_review,
            "must_not_auto_approve": must_not_auto_approve,
        },
        environmental_signals={},
        severity_if_mishandled=4,
        tags=["evals"],
    )


def _run(
    *,
    run_id: str = "run-1",
    scenario_id: str = "scenario-1",
    experiment_id: str = "experiment-1",
    outcome: RunOutcome,
    human_review_requested: bool = False,
    error_type: str | None = None,
) -> Run:
    """Build a test run."""

    timestamp = datetime(2026, 5, 25, tzinfo=UTC)
    return Run(
        run_id=run_id,
        trace_id=f"trace-{run_id}",
        experiment_id=experiment_id,
        scenario_id=scenario_id,
        started_at=timestamp,
        ended_at=timestamp,
        run_outcome=outcome,
        final_output=None,
        final_decision=outcome.value,
        human_review_requested=human_review_requested,
        cost_estimate_usd=None,
        latency_ms=None,
        error_type=error_type,
    )


def _event(
    sequence_no: int,
    event_type: EventType,
    *,
    run_id: str = "run-1",
    trace_id: str = "trace-run-1",
    agent_name: str | None = None,
    tool_name: str | None = None,
) -> TraceEvent:
    """Build a test trace event."""

    return TraceEvent(
        event_id=f"{trace_id}-event-{sequence_no:03d}",
        trace_id=trace_id,
        run_id=run_id,
        sequence_no=sequence_no,
        timestamp=datetime(2026, 5, 25, tzinfo=UTC),
        event_type=event_type,
        agent_name=agent_name,
        tool_name=tool_name,
        parent_event_id=None,
        from_agent=None,
        to_agent=None,
        input_summary=None,
        output_summary=None,
        structured_payload={},
        policy_reference=None,
        severity=0,
        redacted=False,
    )


def _terminal_events() -> list[TraceEvent]:
    """Build a minimal decision/completion event sequence."""

    return [
        _event(1, EventType.DECISION, agent_name="release_reviewer"),
        _event(2, EventType.WORKFLOW_COMPLETED),
    ]
