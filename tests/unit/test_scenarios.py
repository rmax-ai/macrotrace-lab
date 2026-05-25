"""Tests for scenario generation."""

from __future__ import annotations

import json
from pathlib import Path

from macrotrace.scenarios import generate_scenarios
from macrotrace.schemas.experiment import (
    DiscoverySettings,
    ExperimentConfig,
    ExperimentMetadata,
    ModelSettings,
)
from macrotrace.schemas.scenario import Scenario


def test_generate_scenarios_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    config = _build_config()
    output_path = tmp_path / "scenarios.jsonl"

    first_batch = generate_scenarios(config, count=12, seed=17, output=output_path)
    first_output = output_path.read_text(encoding="utf-8")

    second_batch = generate_scenarios(config, count=12, seed=17, output=output_path)
    second_output = output_path.read_text(encoding="utf-8")

    assert first_batch == second_batch
    assert first_output == second_output


def test_generate_scenarios_changes_with_different_seeds(tmp_path: Path) -> None:
    config = _build_config()

    first_batch = generate_scenarios(config, count=12, seed=17, output=tmp_path / "first.jsonl")
    second_batch = generate_scenarios(config, count=12, seed=18, output=tmp_path / "second.jsonl")

    assert first_batch != second_batch


def test_generate_scenarios_covers_all_case_types(tmp_path: Path) -> None:
    config = _build_config()

    scenarios = generate_scenarios(config, count=24, seed=99, output=tmp_path / "all.jsonl")

    assert {scenario.case_type for scenario in scenarios} == {
        "clean_purchase",
        "budget_threshold",
        "sensitive_data_vendor",
        "existing_tool_duplicate",
        "unclear_data_usage",
        "vendor_risk_flag",
        "policy_exception",
        "runtime_tool_failure",
    }


def test_generate_scenarios_returns_validated_models(tmp_path: Path) -> None:
    config = _build_config()

    scenarios = generate_scenarios(config, count=10, seed=7, output=tmp_path / "validated.jsonl")

    assert scenarios
    for scenario in scenarios:
        assert isinstance(scenario, Scenario)
        assert Scenario.model_validate(scenario.model_dump()) == scenario


def test_generate_scenarios_writes_valid_jsonl(tmp_path: Path) -> None:
    config = _build_config()
    output_dir = tmp_path / "generated"

    scenarios = generate_scenarios(config, count=8, seed=123, output=output_dir)
    output_path = output_dir / "procurement_v1.jsonl"

    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert output_path.exists()
    assert len(lines) == len(scenarios)
    decoded = [Scenario.model_validate(json.loads(line)) for line in lines]
    assert decoded == scenarios


def _build_config() -> ExperimentConfig:
    """Build a representative experiment config for scenario tests."""

    return ExperimentConfig(
        experiment=ExperimentMetadata(
            name="Baseline Procurement",
            workflow_name="reference_workflow",
            workflow_version="1.0.0",
            scenario_dataset="procurement_v1",
            seed=42,
            runs_per_scenario=2,
            max_concurrency=2,
        ),
        models=ModelSettings(
            coordinator="gpt-5.5",
            specialists="gpt-5.4-mini",
            judge="gpt-5.5",
        ),
        discovery=DiscoverySettings(
            include_runs="all",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            min_cluster_size=2,
            random_seed=42,
        ),
        fault_injections=[],
    )
