from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from macrotrace.schemas import (
    BehaviorPattern,
    DiagnosisSuspect,
    EvalFinding,
    EventType,
    Experiment,
    ExperimentConfig,
    FindingType,
    RawTrace,
    Run,
    RunOutcome,
    Scenario,
    TraceEvent,
)


def test_scenario_construction_and_round_trip() -> None:
    scenario = Scenario(
        scenario_id="scenario-1",
        dataset_id="dataset-1",
        case_type="vendor_risk_flag",
        request_text="Please buy the vendor tool.",
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
        severity_if_mishandled=4,
        tags=["vendor", "policy"],
    )

    encoded = scenario.model_dump_json()
    decoded = Scenario.model_validate_json(encoded)

    assert decoded == scenario
    assert decoded.case_type == "vendor_risk_flag"


def test_trace_models_round_trip() -> None:
    timestamp = datetime(2026, 5, 25, 12, 0, 0)
    event = TraceEvent(
        event_id="event-1",
        trace_id="trace-1",
        run_id="run-1",
        sequence_no=1,
        timestamp=timestamp,
        event_type=EventType.TOOL_CALLED,
        agent_name="coordinator",
        tool_name="budget_lookup",
        parent_event_id=None,
        from_agent=None,
        to_agent=None,
        input_summary="look up budget",
        output_summary=None,
        structured_payload={"tool_args": {"department": "research"}},
        policy_reference="PROC-101",
        severity=1,
        redacted=False,
    )
    run = Run(
        run_id="run-1",
        trace_id="trace-1",
        experiment_id="experiment-1",
        scenario_id="scenario-1",
        started_at=timestamp,
        ended_at=timestamp,
        run_outcome=RunOutcome.REVIEW_REQUIRED,
        final_output="Escalated for review.",
        final_decision="review_required",
        human_review_requested=True,
        cost_estimate_usd=0.42,
        latency_ms=2300,
        error_type=None,
    )
    raw_trace = RawTrace(
        trace_id="trace-1",
        run_id="run-1",
        source_adapter="jsonl_import",
        payload={"events": [{"type": "tool_called"}]},
    )

    assert TraceEvent.model_validate_json(event.model_dump_json()) == event
    assert Run.model_validate_json(run.model_dump_json()) == run
    assert RawTrace.model_validate_json(raw_trace.model_dump_json()) == raw_trace


def test_eval_pattern_and_experiment_models_round_trip() -> None:
    finding = EvalFinding(
        finding_id="finding-1",
        run_id="run-1",
        evaluator_name="ReviewGateEval",
        evaluator_version="1.0.0",
        finding_type=FindingType.MISSING_REVIEW,
        passed=False,
        severity=5,
        confidence=0.98,
        evidence_event_ids=["event-1"],
        explanation="Review was required but not requested.",
        expected_behavior="Route for human review.",
        observed_behavior="Auto-approved the purchase.",
    )
    pattern = BehaviorPattern(
        pattern_id="pattern-1",
        experiment_id="experiment-1",
        cluster_id=7,
        label="Missed review gate",
        keywords=["review", "approval"],
        trace_count=3,
        prevalence_share=0.3,
        severity_weighted_prevalence=1.2,
        impact_score=0.9,
        dominant_case_type="vendor_risk_flag",
        dominant_finding_type="missing_review",
        dominant_owner="coordinator",
        representative_run_ids=["run-1", "run-2"],
    )
    suspect = DiagnosisSuspect(
        suspect_id="suspect-1",
        pattern_id="pattern-1",
        node_signature="coordinator:decision",
        node_kind="decision",
        agent_name="coordinator",
        tool_name=None,
        proximity_score=0.9,
        frequency_score=0.8,
        bridge_score=0.6,
        role_score=0.7,
        suspect_score=0.85,
        trace_coverage_share=0.75,
        explanation="The coordinator is adjacent to the missing review decision.",
    )
    experiment = Experiment(
        experiment_id="experiment-1",
        name="Baseline",
        created_at=datetime(2026, 5, 25, 12, 0, 0),
        workflow_name="reference_workflow",
        workflow_version="1.0.0",
        config_hash="abc123",
        baseline_experiment_id=None,
        scenario_dataset_id="dataset-1",
        model_settings={"coordinator": "gpt-5.5"},
        agent_config={"specialists": ["policy", "procurement"]},
        fault_injections=["drop_review_handoff"],
        notes="Baseline run.",
    )

    assert EvalFinding.model_validate_json(finding.model_dump_json()) == finding
    assert BehaviorPattern.model_validate_json(pattern.model_dump_json()) == pattern
    assert DiagnosisSuspect.model_validate_json(suspect.model_dump_json()) == suspect
    assert Experiment.model_validate_json(experiment.model_dump_json()) == experiment


def test_experiment_config_validation() -> None:
    config = ExperimentConfig.model_validate(
        {
            "experiment": {
                "name": "Baseline",
                "workflow_name": "reference_workflow",
                "workflow_version": "1.0.0",
                "scenario_dataset": "configs/scenarios.yaml",
                "seed": 42,
                "runs_per_scenario": 3,
                "max_concurrency": 2,
            },
            "models": {
                "coordinator": "gpt-5.5",
                "specialists": "gpt-5.4-mini",
                "judge": "gpt-5.5",
            },
            "discovery": {
                "include_runs": "all",
                "embedding_model": "all-MiniLM-L6-v2",
                "min_cluster_size": 5,
                "random_seed": 42,
            },
            "fault_injections": ["drop_review_handoff"],
        }
    )

    assert config.experiment.runs_per_scenario == 3
    assert config.discovery.embedding_model == "all-MiniLM-L6-v2"


def test_enum_values_match_spec() -> None:
    assert EventType.WORKFLOW_STARTED.value == "workflow_started"
    assert EventType.WORKFLOW_COMPLETED.value == "workflow_completed"
    assert RunOutcome.APPROVED.value == "approved"
    assert RunOutcome.REVIEW_REQUIRED.value == "review_required"
    assert FindingType.COST_ANOMALY.value == "cost_anomaly"
    assert FindingType.NONE.value == "none"


def test_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Scenario(
            scenario_id="scenario-1",
            dataset_id="dataset-1",
            case_type="clean_purchase",
            request_text="Buy a keyboard.",
            expected_outcome=None,
            ground_truth={"must_activate_agents": True},
            environmental_signals={},
            severity_if_mishandled=1,
            tags=[],
            unexpected_field="boom",
        )
