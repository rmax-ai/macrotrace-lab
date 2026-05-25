"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from macrotrace.config import load_config
from macrotrace.exceptions import ConfigError


def test_load_config_reads_valid_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "valid.yaml"
    config_path.write_text(
        """
experiment:
  name: baseline
  workflow_name: workflow
  workflow_version: "1.0.0"
  scenario_dataset: dataset-1
  seed: 42
  runs_per_scenario: 2
  max_concurrency: 1
models:
  coordinator: gpt-5.5
  specialists: gpt-5.4-mini
  judge: gpt-5.5
discovery:
  include_runs: all
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  min_cluster_size: 2
  random_seed: 42
fault_injections: []
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.experiment.name == "baseline"
    assert config.discovery.random_seed == 42


def test_load_config_raises_for_invalid_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("experiment: [", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(config_path)


def test_load_config_raises_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError, match="does not exist"):
        load_config(missing_path)


def test_load_config_raises_when_required_fields_are_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-fields.yaml"
    config_path.write_text(
        """
experiment:
  name: baseline
models:
  coordinator: gpt-5.5
  specialists: gpt-5.4-mini
  judge: gpt-5.5
discovery:
  include_runs: all
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  min_cluster_size: 2
  random_seed: 42
fault_injections: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Configuration validation failed"):
        load_config(config_path)
