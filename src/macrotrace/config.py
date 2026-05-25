"""Configuration loading for MacroTrace Lab."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from yaml import YAMLError

from macrotrace.exceptions import ConfigError
from macrotrace.schemas.experiment import ExperimentConfig


class MacroTraceSettings(BaseSettings):
    """Runtime settings for CLI defaults and local development."""

    model_config = SettingsConfigDict(
        env_prefix="macrotrace_",
        extra="ignore",
        frozen=True,
    )

    default_config_path: Path = Field(
        default=Path("configs/default.yaml"),
        description="Default experiment config used by the CLI.",
    )


def load_config(config_path: Path) -> ExperimentConfig:
    """Load and validate an experiment configuration from YAML."""

    if not config_path.exists():
        raise ConfigError(f"Configuration file does not exist: {config_path}")

    if not config_path.is_file():
        raise ConfigError(f"Configuration path is not a file: {config_path}")

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration file {config_path}: {exc}") from exc
    except YAMLError as exc:
        raise ConfigError(f"Invalid YAML in configuration file {config_path}: {exc}") from exc

    if raw_config is None:
        raise ConfigError(f"Configuration file is empty: {config_path}")

    try:
        return ExperimentConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ConfigError(f"Configuration validation failed for {config_path}: {exc}") from exc
