from __future__ import annotations

from datetime import UTC, datetime

from macrotrace.documents import DOCUMENT_SCHEMA_VERSION, TraceDocumentBuilder
from macrotrace.schemas import (
    EvalFinding,
    EventType,
    FindingType,
    Run,
    RunOutcome,
    Scenario,
    TraceEvent,
)


def test_builds_valid_document_from_clean_run() -> None:
    builder = TraceDocumentBuilder()
    run = _run()
    scenario = _scenario()
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
            EventType.TOOL_CALLED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="budget",
            tool_name="lookup_budget",
        ),
        _event(
            4,
            EventType.TOOL_RESULT,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="budget",
            tool_name="lookup_budget",
            parent_event_id="event-3",
            output_summary="Budget is within threshold.",
        ),
        _event(
            5,
            EventType.DECISION,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="coordinator",
            output_summary="Approve purchase request.",
        ),
        _event(
            6,
            EventType.WORKFLOW_COMPLETED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            output_summary="Workflow completed successfully.",
        ),
    ]
    findings = [_finding(passed=True, finding_type=FindingType.NONE)]

    document = builder.build(run, scenario, events, findings)

    assert "RUN_ID: run-1" in document
    assert "EXPERIMENT: experiment-1" in document
    assert "CASE_TYPE: clean_purchase" in document
    assert "RUN_OUTCOME: approved" in document
    assert "EXPECTED_OUTCOME: approved" in document
    assert "SEVERITY_IF_MISHANDLED: 2" in document
    assert "REQUEST:\nApprove the standard software renewal request." in document
    assert "ENVIRONMENT:\nbudget_remaining_usd=5000\nvendor_risk=low" in document
    assert "ROUTE:\ncoordinator -> budget" in document
    assert "MISSING_EXPECTED_ROUTE:\nN/A" in document
    assert "TOOLS:\nlookup_budget returned Budget is within threshold." in document
    assert "DECISION:\napproved" in document
    assert "EVAL_FINDINGS:\nN/A" in document
    assert (
        "STATE_TRANSITIONS:\nagent_started -> agent_started -> tool_called -> "
        "tool_result -> decision -> workflow_completed" in document
    )
    assert (
        "SUMMARY:\nScenario clean_purchase ended with approved via coordinator -> "
        "budget, with no failing eval findings." in document
    )


def test_builds_valid_document_from_failed_run_with_findings() -> None:
    builder = TraceDocumentBuilder()
    run = _run(
        run_id="run-2",
        trace_id="trace-2",
        outcome=RunOutcome.APPROVED,
        final_decision=None,
        final_output="Approved without required review.",
        human_review_requested=False,
    )
    scenario = _scenario(
        scenario_id="scenario-2",
        case_type="vendor_risk_flag",
        expected_outcome="review_required",
        severity_if_mishandled=5,
        environmental_signals={"vendor_risk": "high", "requires_review": True},
        ground_truth={
            "must_activate_agents": ["coordinator", "security"],
            "must_trigger_review": True,
        },
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
            EventType.TOOL_CALLED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="coordinator",
            tool_name="lookup_vendor_risk",
        ),
        _event(
            3,
            EventType.DECISION,
            run_id=run.run_id,
            trace_id=run.trace_id,
            agent_name="coordinator",
            output_summary="Approved vendor despite unresolved risk.",
        ),
        _event(
            4,
            EventType.WORKFLOW_COMPLETED,
            run_id=run.run_id,
            trace_id=run.trace_id,
            output_summary="Workflow completed with unsafe fallback.",
        ),
    ]
    findings = [
        _finding(
            finding_id="finding-routing",
            passed=False,
            finding_type=FindingType.ROUTING_ERROR,
            severity=5,
            evidence_event_ids=["event-1"],
        ),
        _finding(
            finding_id="finding-review",
            passed=False,
            finding_type=FindingType.MISSING_REVIEW,
            severity=5,
            evidence_event_ids=["event-3", "event-4"],
        ),
        _finding(
            finding_id="finding-runtime",
            passed=False,
            finding_type=FindingType.RUNTIME_FAILURE,
            severity=4,
            evidence_event_ids=["event-2", "event-3"],
        ),
    ]

    document = builder.build(run, scenario, events, findings)

    assert "EXPECTED_OUTCOME: review_required" in document
    assert "MISSING_EXPECTED_ROUTE:\nsecurity" in document
    assert (
        "TOOLS:\nlookup_vendor_risk returned no_result\n"
        "coordinator returned Approved vendor despite unresolved risk." in document
    )
    assert (
        "EVAL_FINDINGS:\nmissing_review severity=5\nrouting_error severity=5\n"
        "runtime_failure severity=4" in document
    )
    assert (
        "SUMMARY:\nScenario vendor_risk_flag ended with approved via coordinator, "
        "with missing_review, routing_error, runtime_failure." in document
    )


def test_document_includes_all_required_sections() -> None:
    builder = TraceDocumentBuilder()

    document = builder.build(_run(), _scenario(), [], [])

    required_sections = [
        "REQUEST:",
        "ENVIRONMENT:",
        "ROUTE:",
        "MISSING_EXPECTED_ROUTE:",
        "TOOLS:",
        "DECISION:",
        "EVAL_FINDINGS:",
        "STATE_TRANSITIONS:",
        "SUMMARY:",
    ]

    for section in required_sections:
        assert section in document


def test_document_is_deterministic_for_same_inputs() -> None:
    builder = TraceDocumentBuilder()
    run = _run()
    scenario = _scenario()
    events = [
        _event(2, EventType.DECISION, output_summary="Approved."),
        _event(1, EventType.AGENT_STARTED, agent_name="coordinator"),
    ]
    findings = [
        _finding(
            finding_id="finding-b",
            passed=False,
            finding_type=FindingType.MISSING_REVIEW,
        ),
        _finding(
            finding_id="finding-a",
            passed=False,
            finding_type=FindingType.ROUTING_ERROR,
        ),
    ]

    first = builder.build(run, scenario, events, findings)
    second = builder.build(run, scenario, events, findings)

    assert first == second


def test_document_schema_version_is_stored() -> None:
    builder = TraceDocumentBuilder()

    builder.build(_run(), _scenario(), [], [])

    assert builder.document_schema_version == DOCUMENT_SCHEMA_VERSION


def test_missing_optional_data_renders_na() -> None:
    builder = TraceDocumentBuilder()
    run = _run(final_decision=None, final_output=None)
    scenario = _scenario(expected_outcome=None, environmental_signals={})

    document = builder.build(run, scenario, [], [])

    assert "EXPECTED_OUTCOME: N/A" in document
    assert "ENVIRONMENT:\nN/A" in document
    assert "ROUTE:\nN/A" in document
    assert "TOOLS:\nN/A" in document
    assert "DECISION:\nN/A" in document
    assert "STATE_TRANSITIONS:\nN/A" in document


def test_builder_preserves_section_links_to_event_ids() -> None:
    builder = TraceDocumentBuilder()
    run = _run()
    scenario = _scenario()
    events = [
        _event(
            1,
            EventType.AGENT_STARTED,
            agent_name="coordinator",
            input_summary="Start route",
        ),
        _event(2, EventType.DECISION, output_summary="Approved."),
    ]

    builder.build(run, scenario, events, [])

    assert builder.last_section_event_ids["ROUTE"] == ["event-1"]
    assert builder.last_section_event_ids["DECISION"] == ["event-2"]
    assert builder.last_section_event_ids["STATE_TRANSITIONS"] == ["event-1", "event-2"]


def _run(
    *,
    run_id: str = "run-1",
    trace_id: str = "trace-1",
    scenario_id: str = "scenario-1",
    experiment_id: str = "experiment-1",
    outcome: RunOutcome = RunOutcome.APPROVED,
    final_output: str | None = "Approved for purchase.",
    final_decision: str | None = "approved",
    human_review_requested: bool = False,
) -> Run:
    return Run(
        run_id=run_id,
        trace_id=trace_id,
        experiment_id=experiment_id,
        scenario_id=scenario_id,
        started_at=datetime(2026, 5, 25, tzinfo=UTC),
        ended_at=datetime(2026, 5, 25, 0, 1, tzinfo=UTC),
        run_outcome=outcome,
        final_output=final_output,
        final_decision=final_decision,
        human_review_requested=human_review_requested,
        cost_estimate_usd=0.25,
        latency_ms=1200,
        error_type=None,
    )


def _scenario(
    *,
    scenario_id: str = "scenario-1",
    case_type: str = "clean_purchase",
    expected_outcome: str | None = "approved",
    severity_if_mishandled: int = 2,
    environmental_signals: dict[str, int | str | float | bool | None] | None = None,
    ground_truth: dict[str, bool | list[str]] | None = None,
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        dataset_id="dataset-1",
        case_type=case_type,
        request_text="Approve the standard software renewal request.",
        expected_outcome=expected_outcome,
        ground_truth=(
            ground_truth
            if ground_truth is not None
            else {"must_activate_agents": ["coordinator", "budget"]}
        ),
        environmental_signals=(
            environmental_signals
            if environmental_signals is not None
            else {"budget_remaining_usd": 5000, "vendor_risk": "low"}
        ),
        severity_if_mishandled=severity_if_mishandled,
        tags=["test"],
    )


def _event(
    sequence_no: int,
    event_type: EventType,
    *,
    run_id: str = "run-1",
    trace_id: str = "trace-1",
    agent_name: str | None = None,
    tool_name: str | None = None,
    parent_event_id: str | None = None,
    input_summary: str | None = None,
    output_summary: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=f"event-{sequence_no}",
        trace_id=trace_id,
        run_id=run_id,
        sequence_no=sequence_no,
        timestamp=datetime(2026, 5, 25, 0, sequence_no, tzinfo=UTC),
        event_type=event_type,
        agent_name=agent_name,
        tool_name=tool_name,
        parent_event_id=parent_event_id,
        from_agent=None,
        to_agent=None,
        input_summary=input_summary,
        output_summary=output_summary,
        structured_payload={},
        policy_reference=None,
        severity=0,
        redacted=True,
    )


def _finding(
    *,
    finding_id: str = "finding-1",
    passed: bool,
    finding_type: FindingType,
    severity: int = 0,
    evidence_event_ids: list[str] | None = None,
) -> EvalFinding:
    return EvalFinding(
        finding_id=finding_id,
        run_id="run-1",
        evaluator_name="test_eval",
        evaluator_version="1.0.0",
        finding_type=finding_type,
        passed=passed,
        severity=severity,
        confidence=1.0,
        evidence_event_ids=evidence_event_ids or [],
        explanation="test explanation",
        expected_behavior="test expected behavior",
        observed_behavior="test observed behavior",
    )
