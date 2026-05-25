"""Tests for the Typer CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import macrotrace.cli as cli
from macrotrace.schemas.experiment import (
    DiscoverySettings,
    ExperimentConfig,
    ExperimentMetadata,
    ModelSettings,
)

runner = CliRunner()


@pytest.mark.parametrize(
    ("args", "expected_text"),
    [
        (["--help"], "MacroTrace Lab command line interface."),
        (["init", "--help"], "Initialize the MacroTrace database."),
        (["scenarios", "generate", "--help"], "Generate scenarios for an experiment."),
        (["runs", "execute", "--help"], "Execute workflow runs for an experiment."),
        (["traces", "import", "--help"], "Import externally produced traces."),
        (["traces", "validate", "--help"], "Validate normalized traces for an experiment."),
        (["evals", "run", "--help"], "Run the evaluation suite for an experiment."),
        (["evals", "summary", "--help"], "Summarize evaluation results for an experiment."),
        (["documents", "build", "--help"], "Build trace documents for an experiment."),
        (["patterns", "discover", "--help"], "Discover recurring behavior patterns."),
        (["diagnose", "--help"], "Diagnose a discovered behavior pattern."),
        (["compare", "--help"], "Compare two experiments."),
        (["ui", "--help"], "Launch the research UI."),
        (["report", "export", "--help"], "Export an experiment report."),
    ],
)
def test_each_command_exposes_help(args: list[str], expected_text: str) -> None:
    result = runner.invoke(cli.app, args)

    assert result.exit_code == 0
    assert expected_text in result.output


def test_runs_execute_parses_options_and_passes_loaded_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: dict[str, object] = {}
    config_path = tmp_path / "config.yaml"
    config_path.write_text("experiment: {}", encoding="utf-8")
    loaded_config = ExperimentConfig(
        experiment=ExperimentMetadata(
            name="baseline",
            workflow_name="workflow",
            workflow_version="1.0.0",
            scenario_dataset="dataset-1",
            seed=42,
            runs_per_scenario=2,
            max_concurrency=1,
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

    def fake_load_config(path: Path) -> ExperimentConfig:
        calls["config_path"] = path
        return loaded_config

    def fake_execute_runs(
        experiment: str | None,
        config: ExperimentConfig | None,
        max_concurrency: int | None,
        adapter: str | None,
        dry_run: bool,
    ) -> None:
        calls["experiment"] = experiment
        calls["config"] = config
        calls["max_concurrency"] = max_concurrency
        calls["adapter"] = adapter
        calls["dry_run"] = dry_run

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "execute_runs", fake_execute_runs)

    result = runner.invoke(
        cli.app,
        [
            "runs",
            "execute",
            "--experiment",
            "baseline",
            "--config",
            str(config_path),
            "--max-concurrency",
            "4",
            "--adapter",
            "jsonl",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert calls == {
        "config_path": config_path,
        "experiment": "baseline",
        "config": loaded_config,
        "max_concurrency": 4,
        "adapter": "jsonl",
        "dry_run": True,
    }


def test_init_command_initializes_database(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def fake_init_db() -> None:
        called["value"] = True

    monkeypatch.setattr(cli, "init_db", fake_init_db)

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0
    assert called["value"] is True
    assert "Initialized the MacroTrace database schema." in result.output


def test_scenarios_generate_surfaces_config_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_config(_: Path) -> ExperimentConfig:
        raise cli.ConfigError("bad config")

    monkeypatch.setattr(cli, "load_config", fake_load_config)

    result = runner.invoke(cli.app, ["scenarios", "generate"])

    assert result.exit_code == 1
    assert "bad config" in result.output
