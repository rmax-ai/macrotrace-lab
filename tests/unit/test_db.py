from __future__ import annotations

from datetime import datetime
from pathlib import Path

from macrotrace.db import (
    create_behavior_pattern,
    create_db_engine,
    create_diagnosis_suspect,
    create_eval_finding,
    create_experiment,
    create_raw_trace,
    create_run,
    create_scenario,
    create_trace_event,
    get_session,
    get_sqlite_pragma,
    init_db,
    list_behavior_patterns,
    list_diagnosis_suspects,
    list_eval_findings,
    list_experiments,
    list_raw_traces,
    list_runs,
    list_scenarios,
    list_trace_events,
)
from macrotrace.schemas import (
    BehaviorPattern,
    DiagnosisSuspect,
    EvalFinding,
    EventType,
    Experiment,
    FindingType,
    RawTrace,
    Run,
    RunOutcome,
    Scenario,
    TraceEvent,
)


def test_init_db_and_pragmas(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "macrotrace.db")
    init_db(engine)

    with get_session(engine) as session:
        assert get_sqlite_pragma(session, "journal_mode")[0] == "wal"
        assert get_sqlite_pragma(session, "synchronous")[0] == 1
        assert get_sqlite_pragma(session, "foreign_keys")[0] == 1
        assert get_sqlite_pragma(session, "busy_timeout")[0] == 5000


def test_insert_and_list_round_trip(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "macrotrace.db")
    init_db(engine)
    now = datetime(2026, 5, 25, 12, 0, 0)

    scenario = Scenario(
        scenario_id="scenario-1",
        dataset_id="dataset-1",
        case_type="vendor_risk_flag",
        request_text="Purchase the analytics suite.",
        expected_outcome="review_required",
        ground_truth={
            "must_activate_agents": True,
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": 5000,
            "data_classification": "restricted",
            "vendor_risk": "high",
        },
        severity_if_mishandled=5,
        tags=["vendor", "risk"],
    )
    experiment = Experiment(
        experiment_id="experiment-1",
        name="Baseline",
        created_at=now,
        workflow_name="reference_workflow",
        workflow_version="1.0.0",
        config_hash="hash-1",
        baseline_experiment_id=None,
        scenario_dataset_id="dataset-1",
        model_settings={"coordinator": "gpt-5.5"},
        agent_config={"specialists": ["policy"]},
        fault_injections=["drop_review_handoff"],
        notes="note",
    )
    run = Run(
        run_id="run-1",
        trace_id="trace-1",
        experiment_id="experiment-1",
        scenario_id="scenario-1",
        started_at=now,
        ended_at=now,
        run_outcome=RunOutcome.REVIEW_REQUIRED,
        final_output="Escalated to human review.",
        final_decision="review_required",
        human_review_requested=True,
        cost_estimate_usd=0.34,
        latency_ms=1250,
        error_type=None,
    )
    trace_event = TraceEvent(
        event_id="event-1",
        trace_id="trace-1",
        run_id="run-1",
        sequence_no=1,
        timestamp=now,
        event_type=EventType.REVIEW_REQUESTED,
        agent_name="coordinator",
        tool_name=None,
        parent_event_id=None,
        from_agent="coordinator",
        to_agent="reviewer",
        input_summary="needs review",
        output_summary="review requested",
        structured_payload={"reason": "vendor_risk"},
        policy_reference="PROC-101",
        severity=4,
        redacted=False,
    )
    raw_trace = RawTrace(
        trace_id="trace-1",
        run_id="run-1",
        source_adapter="jsonl_import",
        payload={"raw": True},
    )
    finding = EvalFinding(
        finding_id="finding-1",
        run_id="run-1",
        evaluator_name="ReviewGateEval",
        evaluator_version="1.0.0",
        finding_type=FindingType.MISSING_REVIEW,
        passed=False,
        severity=5,
        confidence=0.97,
        evidence_event_ids=["event-1"],
        explanation="Review was omitted.",
        expected_behavior="Request review.",
        observed_behavior="Decision bypassed review.",
    )
    pattern = BehaviorPattern(
        pattern_id="pattern-1",
        experiment_id="experiment-1",
        cluster_id=2,
        label="Missed review path",
        keywords=["review", "bypass"],
        trace_count=1,
        prevalence_share=1.0,
        severity_weighted_prevalence=5.0,
        impact_score=5.0,
        dominant_case_type="vendor_risk_flag",
        dominant_finding_type="missing_review",
        dominant_owner="coordinator",
        representative_run_ids=["run-1"],
    )
    suspect = DiagnosisSuspect(
        suspect_id="suspect-1",
        pattern_id="pattern-1",
        node_signature="coordinator:review_gate",
        node_kind="agent",
        agent_name="coordinator",
        tool_name=None,
        proximity_score=0.9,
        frequency_score=0.8,
        bridge_score=0.6,
        role_score=0.7,
        suspect_score=0.88,
        trace_coverage_share=1.0,
        explanation="Coordinator is central to the faulty review path.",
    )

    with get_session(engine) as session:
        assert create_scenario(session, scenario) == scenario
        assert create_experiment(session, experiment) == experiment
        assert create_run(session, run) == run
        assert create_trace_event(session, trace_event) == trace_event
        assert create_raw_trace(session, raw_trace) == raw_trace
        assert create_eval_finding(session, finding) == finding
        assert create_behavior_pattern(session, pattern) == pattern
        assert create_diagnosis_suspect(session, suspect) == suspect

        assert list_scenarios(session) == [scenario]
        assert list_experiments(session) == [experiment]
        assert list_runs(session) == [run]
        assert list_runs(session, experiment_id="experiment-1") == [run]
        assert list_trace_events(session) == [trace_event]
        assert list_trace_events(session, run_id="run-1") == [trace_event]
        assert list_raw_traces(session) == [raw_trace]
        assert list_raw_traces(session, run_id="run-1") == [raw_trace]
        assert list_eval_findings(session) == [finding]
        assert list_eval_findings(session, run_id="run-1") == [finding]
        assert list_behavior_patterns(session) == [pattern]
        assert list_behavior_patterns(session, experiment_id="experiment-1") == [pattern]
        assert list_diagnosis_suspects(session) == [suspect]
        assert list_diagnosis_suspects(session, pattern_id="pattern-1") == [suspect]
