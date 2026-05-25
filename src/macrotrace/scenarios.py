"""Scenario generation utilities."""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from macrotrace.schemas.scenario import CaseType, Scenario

if TYPE_CHECKING:
    from macrotrace.schemas.experiment import ExperimentConfig


@dataclass(frozen=True)
class ScenarioSeedData:
    """Structured seed data used to render a scenario template."""

    company_name: str
    team_name: str
    requester_name: str
    role_title: str
    tool_name: str
    vendor_name: str
    use_case: str
    integration_target: str
    justification: str
    monthly_cost_eur: int
    data_classification: str
    vendor_risk: str
    region_scope: str


COMPANY_NAMES: tuple[str, ...] = (
    "Northstar Biolabs",
    "Asteron Freight",
    "Lumen Retail Group",
    "Mariner Health Systems",
    "HelioForge Energy",
    "Pinebridge Analytics",
)

TEAM_NAMES: tuple[str, ...] = (
    "procurement ops",
    "revenue analytics",
    "customer success",
    "finance systems",
    "security engineering",
    "clinical operations",
)

REQUESTER_NAMES: tuple[str, ...] = (
    "Alex Chen",
    "Priya Nair",
    "Jordan Kim",
    "Mateo Silva",
    "Samira Haddad",
    "Elena Fischer",
)

ROLE_TITLES: tuple[str, ...] = (
    "operations manager",
    "staff analyst",
    "security lead",
    "research program manager",
    "finance director",
    "support automation owner",
)

TOOL_NAMES: tuple[str, ...] = (
    "SpendPilot",
    "InsightFlow",
    "VendorVista",
    "QueueSprint",
    "DataHarbor",
    "NoteForge",
    "ProcurePath",
    "RiskLens",
)

VENDOR_NAMES: tuple[str, ...] = (
    "AceroSoft",
    "BluePeak AI",
    "DeltaMesh",
    "NimbusForge",
    "OrbitStack",
    "SignalBloom",
    "TerraLedger",
    "VectorCrest",
)

USE_CASES: tuple[str, ...] = (
    "summarizing inbound support tickets",
    "tracking renewal risk across enterprise accounts",
    "automating monthly spend reconciliation",
    "drafting vendor onboarding checklists",
    "classifying incident postmortems",
    "building procurement request summaries",
)

INTEGRATION_TARGETS: tuple[str, ...] = (
    "our shared Google Drive folders",
    "the CRM export in Snowflake",
    "our Jira project backlog",
    "the procurement mailbox archive",
    "the internal contract repository",
    "our finance data warehouse",
)

JUSTIFICATIONS: tuple[str, ...] = (
    "the current manual process takes too long",
    "we need a pilot before next quarter planning",
    "the existing workflow is creating approval delays",
    "leadership asked for a lightweight solution this month",
    "the team needs coverage while headcount is frozen",
    "the current spreadsheet process is failing audits",
)

REGION_SCOPES: tuple[str, ...] = (
    "for the EU team only",
    "for the global support organization",
    "for the finance team in Germany",
    "for a six-week pilot in the UK",
    "for the shared operations team in EMEA",
    "for a cross-functional trial across two business units",
)

CASE_TYPES: tuple[CaseType, ...] = (
    "clean_purchase",
    "budget_threshold",
    "sensitive_data_vendor",
    "existing_tool_duplicate",
    "unclear_data_usage",
    "vendor_risk_flag",
    "policy_exception",
    "runtime_tool_failure",
)


def _required_agents_for_case_type(case_type: CaseType) -> list[str]:
    """Return the expected agent activations for a scenario type."""

    required_agents = ["coordinator", "budget", "policy", "procurement", "release_reviewer"]
    if case_type in {
        "sensitive_data_vendor",
        "unclear_data_usage",
        "vendor_risk_flag",
        "policy_exception",
        "runtime_tool_failure",
    }:
        return [*required_agents[:3], "security", *required_agents[3:]]
    return required_agents


def generate_scenarios(
    config: ExperimentConfig,
    count: int,
    seed: int | None,
    output: Path | None,
) -> list[Scenario]:
    """Generate deterministic scenarios and persist them as JSONL."""

    if count < 1:
        raise ValueError("count must be at least 1")

    generation_seed = config.experiment.seed if seed is None else seed
    dataset_id = config.experiment.scenario_dataset
    output_path = _resolve_output_path(output=output, dataset_id=dataset_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(generation_seed)
    case_plan = _build_case_plan(count=count, rng=rng)
    scenarios = [
        _build_scenario(
            dataset_id=dataset_id,
            scenario_index=index,
            case_type=case_type,
            rng=rng,
            seed=generation_seed,
        )
        for index, case_type in enumerate(case_plan, start=1)
    ]

    output_path.write_text(
        "\n".join(json.dumps(scenario.model_dump(mode="json")) for scenario in scenarios) + "\n",
        encoding="utf-8",
    )
    return scenarios


def _resolve_output_path(output: Path | None, dataset_id: str) -> Path:
    """Resolve the JSONL output location for generated scenarios."""

    default_path = Path("data/scenarios") / f"{dataset_id}.jsonl"
    if output is None:
        return default_path
    if output.suffix == ".jsonl":
        return output
    return output / f"{dataset_id}.jsonl"


def _build_case_plan(count: int, rng: random.Random) -> list[CaseType]:
    """Build a deterministic list of case types to generate."""

    if count >= len(CASE_TYPES):
        repeated_types = list(CASE_TYPES) * (count // len(CASE_TYPES))
        repeated_types.extend(rng.sample(CASE_TYPES, count % len(CASE_TYPES)))
        rng.shuffle(repeated_types)
        return repeated_types
    return rng.sample(CASE_TYPES, count)


def _sample_seed_data(rng: random.Random, case_type: CaseType) -> ScenarioSeedData:
    """Sample deterministic seed data for scenario rendering."""

    cost_ranges: dict[CaseType, tuple[int, int]] = {
        "clean_purchase": (18, 140),
        "budget_threshold": (1200, 4200),
        "sensitive_data_vendor": (250, 1600),
        "existing_tool_duplicate": (150, 900),
        "unclear_data_usage": (120, 1400),
        "vendor_risk_flag": (600, 2600),
        "policy_exception": (900, 2400),
        "runtime_tool_failure": (80, 850),
    }
    classification_options: dict[CaseType, tuple[str, ...]] = {
        "clean_purchase": ("public",),
        "budget_threshold": ("internal", "public"),
        "sensitive_data_vendor": ("confidential", "restricted"),
        "existing_tool_duplicate": ("internal",),
        "unclear_data_usage": ("internal", "confidential"),
        "vendor_risk_flag": ("internal", "confidential"),
        "policy_exception": ("internal", "restricted"),
        "runtime_tool_failure": ("public", "internal"),
    }
    vendor_risk_options: dict[CaseType, tuple[str, ...]] = {
        "clean_purchase": ("low",),
        "budget_threshold": ("low", "medium"),
        "sensitive_data_vendor": ("medium", "high"),
        "existing_tool_duplicate": ("low",),
        "unclear_data_usage": ("medium",),
        "vendor_risk_flag": ("high",),
        "policy_exception": ("medium",),
        "runtime_tool_failure": ("low", "medium"),
    }
    min_cost, max_cost = cost_ranges[case_type]

    return ScenarioSeedData(
        company_name=rng.choice(COMPANY_NAMES),
        team_name=rng.choice(TEAM_NAMES),
        requester_name=rng.choice(REQUESTER_NAMES),
        role_title=rng.choice(ROLE_TITLES),
        tool_name=rng.choice(TOOL_NAMES),
        vendor_name=rng.choice(VENDOR_NAMES),
        use_case=rng.choice(USE_CASES),
        integration_target=rng.choice(INTEGRATION_TARGETS),
        justification=rng.choice(JUSTIFICATIONS),
        monthly_cost_eur=rng.randint(min_cost, max_cost),
        data_classification=rng.choice(classification_options[case_type]),
        vendor_risk=rng.choice(vendor_risk_options[case_type]),
        region_scope=rng.choice(REGION_SCOPES),
    )


def _build_scenario(
    dataset_id: str,
    scenario_index: int,
    case_type: CaseType,
    rng: random.Random,
    seed: int,
) -> Scenario:
    """Build a validated scenario for a given case type."""

    seed_data = _sample_seed_data(rng=rng, case_type=case_type)
    scenario_id = f"{dataset_id}-{seed}-{scenario_index:04d}"
    builders: dict[CaseType, Callable[[str, str, ScenarioSeedData], Scenario]] = {
        "clean_purchase": _build_clean_purchase,
        "budget_threshold": _build_budget_threshold,
        "sensitive_data_vendor": _build_sensitive_data_vendor,
        "existing_tool_duplicate": _build_existing_tool_duplicate,
        "unclear_data_usage": _build_unclear_data_usage,
        "vendor_risk_flag": _build_vendor_risk_flag,
        "policy_exception": _build_policy_exception,
        "runtime_tool_failure": _build_runtime_tool_failure,
    }
    return builders[case_type](scenario_id, dataset_id, seed_data)


def _build_clean_purchase(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a low-risk clean purchase scenario."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="clean_purchase",
        request_text=(
            f"{seed_data.requester_name}, {seed_data.role_title} at {seed_data.company_name}, "
            f"wants to buy {seed_data.tool_name} from {seed_data.vendor_name} for "
            f"{seed_data.use_case} {seed_data.region_scope}. The request is limited to public "
            f"marketing data and costs EUR {seed_data.monthly_cost_eur} per month."
        ),
        expected_outcome="approved",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("clean_purchase"),
            "must_trigger_review": False,
            "must_not_auto_approve": False,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": "public",
            "vendor_risk": "low",
        },
        severity_if_mishandled=1,
        tags=["low_risk", "public_data", "standard_purchase"],
    )


def _build_budget_threshold(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a scenario that exceeds the auto-approval cost limit."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="budget_threshold",
        request_text=(
            f"{seed_data.requester_name} from {seed_data.team_name} asked to approve "
            f"{seed_data.tool_name} by {seed_data.vendor_name} for {seed_data.use_case}. "
            f"The subscription is EUR {seed_data.monthly_cost_eur} per month and "
            f"{seed_data.justification}."
        ),
        expected_outcome="review_required",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("budget_threshold"),
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": seed_data.data_classification,
            "vendor_risk": seed_data.vendor_risk,
        },
        severity_if_mishandled=3,
        tags=["budget", "approval_limit", "finance_review"],
    )


def _build_sensitive_data_vendor(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a scenario involving confidential or restricted data."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="sensitive_data_vendor",
        request_text=(
            f"{seed_data.requester_name} wants to connect {seed_data.tool_name} from "
            f"{seed_data.vendor_name} to {seed_data.integration_target} for "
            f"{seed_data.use_case}. The workflow would include {seed_data.data_classification} "
            f"customer and internal operational data."
        ),
        expected_outcome="blocked",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("sensitive_data_vendor"),
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": seed_data.data_classification,
            "vendor_risk": seed_data.vendor_risk,
        },
        severity_if_mishandled=5,
        tags=["sensitive_data", "vendor_access", "security_block"],
    )


def _build_existing_tool_duplicate(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a duplicate tooling request scenario."""

    existing_tool = "ProcurePath Enterprise"
    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="existing_tool_duplicate",
        request_text=(
            f"{seed_data.requester_name} requested {seed_data.tool_name} from "
            f"{seed_data.vendor_name} for {seed_data.use_case}, but the team already has "
            f"{existing_tool} licensed for a similar workflow."
        ),
        expected_outcome="review_required",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("existing_tool_duplicate"),
            "must_trigger_review": False,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": "internal",
            "vendor_risk": "low",
        },
        severity_if_mishandled=2,
        tags=["duplicate_tool", "license_reuse", "procurement_review"],
    )


def _build_unclear_data_usage(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a scenario with ambiguous data handling requirements."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="unclear_data_usage",
        request_text=(
            f"{seed_data.requester_name} asked for {seed_data.tool_name} from "
            f"{seed_data.vendor_name} to help with {seed_data.use_case}. The request mentions "
            f"integrating with {seed_data.integration_target}, but it does not explain what data "
            "would be sent to the vendor or retained after processing."
        ),
        expected_outcome="review_required",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("unclear_data_usage"),
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": seed_data.data_classification,
            "vendor_risk": "medium",
        },
        severity_if_mishandled=4,
        tags=["ambiguous_scope", "data_handling", "clarification_needed"],
    )


def _build_vendor_risk_flag(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a scenario where the vendor has a known risk flag."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="vendor_risk_flag",
        request_text=(
            f"{seed_data.requester_name} wants approval for {seed_data.tool_name} from "
            f"{seed_data.vendor_name}. Procurement notes that the supplier has unresolved "
            "security questionnaire findings and a recent policy exception on record, but the "
            f"team still wants the tool for {seed_data.use_case}."
        ),
        expected_outcome="blocked",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("vendor_risk_flag"),
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": seed_data.data_classification,
            "vendor_risk": "high",
        },
        severity_if_mishandled=5,
        tags=["vendor_risk", "security_flag", "policy_concern"],
    )


def _build_policy_exception(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a scenario that requires explicit exception handling."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="policy_exception",
        request_text=(
            f"{seed_data.requester_name} from {seed_data.company_name} wants to use "
            f"{seed_data.tool_name} for {seed_data.use_case}. The request falls outside the "
            "standard purchasing policy and asks for an exception because "
            f"{seed_data.justification}."
        ),
        expected_outcome="review_required",
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("policy_exception"),
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": seed_data.data_classification,
            "vendor_risk": "medium",
        },
        severity_if_mishandled=4,
        tags=["policy_exception", "manual_justification", "review_gate"],
    )


def _build_runtime_tool_failure(
    scenario_id: str,
    dataset_id: str,
    seed_data: ScenarioSeedData,
) -> Scenario:
    """Create a fault-handling scenario with missing tool lookup results."""

    return Scenario(
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        case_type="runtime_tool_failure",
        request_text=(
            f"{seed_data.requester_name} asked for {seed_data.tool_name} from "
            f"{seed_data.vendor_name} for {seed_data.use_case}, but the vendor and policy "
            "lookup tools timed out during evaluation. The system must avoid auto-approval when "
            "critical checks cannot complete."
        ),
        expected_outcome=None,
        ground_truth={
            "must_activate_agents": _required_agents_for_case_type("runtime_tool_failure"),
            "must_trigger_review": True,
            "must_not_auto_approve": True,
        },
        environmental_signals={
            "monthly_cost_eur": seed_data.monthly_cost_eur,
            "data_classification": seed_data.data_classification,
            "vendor_risk": seed_data.vendor_risk,
            "tool_lookup_failed": True,
        },
        severity_if_mishandled=3,
        tags=["fault_injection", "tool_failure", "safe_fallback"],
    )
