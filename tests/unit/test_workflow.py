from __future__ import annotations

from pathlib import Path

from macrotrace.runtime import (
    AgentContext,
    BudgetAgent,
    CoordinatorAgent,
    PolicyAgent,
    ProcurementAgent,
    ReleaseReviewerAgent,
    SecurityAgent,
    SimulatedToolset,
    ToolSeedConfig,
    apply_faults,
    execute_experiment,
    execute_reference_workflow,
)
from macrotrace.schemas import ExperimentConfig, RunOutcome, Scenario


def _scenario(
    *,
    scenario_id: str,
    case_type: str,
    request_text: str,
    expected_outcome: str | None,
    environmental_signals: dict[str, int | str | float | bool | None],
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        dataset_id="dataset-1",
        case_type=case_type,
        request_text=request_text,
        expected_outcome=expected_outcome,
        ground_truth={
            "must_activate_agents": True,
            "must_trigger_review": expected_outcome == "review_required",
            "must_not_auto_approve": expected_outcome == "blocked",
        },
        environmental_signals=environmental_signals,
        severity_if_mishandled=3,
        tags=["runtime"],
    )


def _config(
    *,
    fault_injections: list[str] | None = None,
    runs_per_scenario: int = 1,
) -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "experiment": {
                "name": "Reference Workflow Test",
                "workflow_name": "reference_workflow",
                "workflow_version": "1.0.0",
                "scenario_dataset": "tests/fixtures/runtime.jsonl",
                "seed": 42,
                "runs_per_scenario": runs_per_scenario,
                "max_concurrency": 2,
            },
            "models": {
                "coordinator": "test-model",
                "specialists": "test-model",
                "judge": "test-model",
            },
            "discovery": {
                "include_runs": "all",
                "embedding_model": "test-embedding",
                "min_cluster_size": 2,
                "random_seed": 42,
            },
            "fault_injections": fault_injections or [],
        }
    )


def test_workflow_approves_clean_purchase() -> None:
    scenario = _scenario(
        scenario_id="clean-1",
        case_type="clean_purchase",
        request_text="Buy a note-taking subscription for the research team.",
        expected_outcome="approved",
        environmental_signals={
            "department": "research",
            "item": "note taking subscription",
            "vendor": "Approved Notes",
            "vendor_known": True,
            "quoted_monthly_cost": 120.0,
            "quoted_annual_cost": 1_440.0,
            "data_description": "",
        },
    )

    result = execute_reference_workflow(scenario, seed=42)

    assert result.outcome is RunOutcome.APPROVED
    assert result.final_decision == "approved"
    assert result.trace_events[-1]["structured_payload"]["outcome"] == "approved"


def test_workflow_triggers_review_for_sensitive_data_vendor() -> None:
    scenario = _scenario(
        scenario_id="sensitive-1",
        case_type="sensitive_data_vendor",
        request_text="Use a new research annotation vendor for confidential interview transcripts.",
        expected_outcome="review_required",
        environmental_signals={
            "department": "research",
            "item": "annotation platform",
            "vendor": "Unknown Sensitive Systems",
            "vendor_known": False,
            "quoted_monthly_cost": 400.0,
            "quoted_annual_cost": 4_800.0,
            "data_description": "Confidential interview transcripts for internal research.",
        },
    )

    result = execute_reference_workflow(scenario, seed=42)

    assert result.outcome is RunOutcome.REVIEW_REQUIRED
    assert result.final_decision == "review_required"


def test_workflow_blocks_high_risk_scenario() -> None:
    scenario = _scenario(
        scenario_id="risk-1",
        case_type="vendor_risk_flag",
        request_text="Purchase a data platform from a recently breached vendor.",
        expected_outcome="blocked",
        environmental_signals={
            "department": "research",
            "item": "data platform",
            "vendor": "HighRisk Breach Analytics",
            "vendor_known": False,
            "quoted_monthly_cost": 1_200.0,
            "quoted_annual_cost": 14_400.0,
            "data_description": "Restricted genomic datasets.",
        },
    )

    result = execute_reference_workflow(scenario, seed=42)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.final_decision == "blocked"


def test_fault_injection_changes_workflow_behavior() -> None:
    scenario = _scenario(
        scenario_id="fault-1",
        case_type="sensitive_data_vendor",
        request_text="Route a sensitive purchase that should normally require review.",
        expected_outcome="review_required",
        environmental_signals={
            "department": "research",
            "item": "analysis workspace",
            "vendor": "Unknown Sensitive Systems",
            "vendor_known": False,
            "quoted_monthly_cost": 250.0,
            "quoted_annual_cost": 3_000.0,
            "data_description": "Confidential interview transcripts.",
        },
    )

    clean = execute_reference_workflow(scenario, seed=42)
    faulty = execute_reference_workflow(
        scenario,
        seed=42,
        fault_names=[
            "skip_security_on_unknown_vendor",
            "policy_agent_omit_review_requirement",
            "reviewer_skip_review",
        ],
    )

    assert clean.outcome is RunOutcome.REVIEW_REQUIRED
    assert faulty.outcome is RunOutcome.APPROVED


def test_batch_runner_executes_multiple_scenarios() -> None:
    checkpoint_dir = Path(".macrotrace-checkpoints")
    if checkpoint_dir.exists():
        for checkpoint in checkpoint_dir.glob("reference-workflow-test.json"):
            checkpoint.unlink()

    scenarios = [
        _scenario(
            scenario_id="batch-clean",
            case_type="clean_purchase",
            request_text="Buy a documentation tool.",
            expected_outcome="approved",
            environmental_signals={
                "department": "research",
                "item": "documentation tool",
                "vendor": "Approved Notes",
                "vendor_known": True,
                "quoted_monthly_cost": 90.0,
                "quoted_annual_cost": 1_080.0,
                "data_description": "",
            },
        ),
        _scenario(
            scenario_id="batch-review",
            case_type="sensitive_data_vendor",
            request_text="Buy a sensitive data processor.",
            expected_outcome="review_required",
            environmental_signals={
                "department": "research",
                "item": "sensitive processor",
                "vendor": "Unknown Sensitive Systems",
                "vendor_known": False,
                "quoted_monthly_cost": 300.0,
                "quoted_annual_cost": 3_600.0,
                "data_description": "Confidential participant records.",
            },
        ),
    ]

    runs = execute_experiment(_config(runs_per_scenario=2), scenarios)

    assert len(runs) == 4
    assert any(run.run_outcome is RunOutcome.APPROVED for run in runs)
    assert any(run.run_outcome is RunOutcome.REVIEW_REQUIRED for run in runs)


def test_tools_are_deterministic_for_same_seed() -> None:
    first = SimulatedToolset(ToolSeedConfig(seed=99))
    second = SimulatedToolset(ToolSeedConfig(seed=99))

    assert first.get_budget("research") == second.get_budget("research")
    assert first.estimate_cost("annotation platform", "Vendor A") == second.estimate_cost(
        "annotation platform", "Vendor A"
    )
    assert first.lookup_existing_contract(
        "Approved Contract Vendor"
    ) == second.lookup_existing_contract("Approved Contract Vendor")


def test_each_agent_runs_in_isolation() -> None:
    request = {
        "department": "research",
        "item": "analysis workspace",
        "vendor": "Unknown Sensitive Systems",
        "vendor_known": False,
        "quoted_monthly_cost": 400.0,
        "quoted_annual_cost": 4_800.0,
        "data_description": "Confidential transcripts.",
        "request_text": "Review a new sensitive vendor.",
    }
    tools = SimulatedToolset(ToolSeedConfig(seed=7))
    workflow_config = apply_faults({}, [])

    coordinator = CoordinatorAgent().run(
        AgentContext(
            scenario_id="isolation-1",
            request=request,
            workflow_config=workflow_config,
            tools=tools,
        )
    )
    budget = BudgetAgent().run(
        AgentContext(
            scenario_id="isolation-1",
            request=request,
            workflow_config=workflow_config,
            tools=tools,
        )
    )
    security = SecurityAgent().run(
        AgentContext(
            scenario_id="isolation-1",
            request=request,
            workflow_config=workflow_config,
            tools=tools,
        )
    )
    policy = PolicyAgent().run(
        AgentContext(
            scenario_id="isolation-1",
            request=request,
            workflow_config=workflow_config,
            tools=tools,
        )
    )
    procurement = ProcurementAgent().run(
        AgentContext(
            scenario_id="isolation-1",
            request=request,
            workflow_config=workflow_config,
            tools=tools,
            results={"budget": budget, "security": security, "policy": policy},
        )
    )
    reviewer = ReleaseReviewerAgent().run(
        AgentContext(
            scenario_id="isolation-1",
            request=request,
            workflow_config=workflow_config,
            tools=tools,
            results={"procurement": procurement},
        )
    )

    assert coordinator["decision"] == "route"
    assert budget["decision"] in {"clear", "review_required"}
    assert security["decision"] == "review_required"
    assert policy["decision"] == "review_required"
    assert procurement["decision"] == "review_required"
    assert reviewer["decision"] == "review_required"
