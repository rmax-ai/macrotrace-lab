"""Typer CLI for MacroTrace Lab."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import structlog
import typer
from rich.console import Console
from rich.table import Table

from macrotrace.config import MacroTraceSettings, load_config
from macrotrace.db import init_db
from macrotrace.diagnosis import compare_experiments, diagnose_pattern
from macrotrace.discovery import discover_patterns
from macrotrace.documents import build_documents
from macrotrace.evals import run_evals, summarize_evals
from macrotrace.exceptions import ConfigError, MacroTraceError, WorkflowError
from macrotrace.logging_config import configure_logging
from macrotrace.reporting import ReportFormat, export_report
from macrotrace.runs import execute_runs
from macrotrace.scenarios import generate_scenarios
from macrotrace.schemas.experiment import ExperimentConfig
from macrotrace.traces import import_traces, validate_traces
from macrotrace.ui import launch_ui

console = Console()
settings = MacroTraceSettings()
logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AppState:
    """Global CLI state shared across commands."""

    config_path: Path
    verbose: bool


app = typer.Typer(
    help="MacroTrace Lab command line interface.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
scenarios_app = typer.Typer(help="Generate and manage scenario datasets.", no_args_is_help=True)
runs_app = typer.Typer(help="Execute workflow runs.", no_args_is_help=True)
traces_app = typer.Typer(help="Import and validate traces.", no_args_is_help=True)
evals_app = typer.Typer(help="Run and summarize evaluations.", no_args_is_help=True)
documents_app = typer.Typer(help="Build trace documents.", no_args_is_help=True)
patterns_app = typer.Typer(help="Discover recurring behavior patterns.", no_args_is_help=True)
report_app = typer.Typer(help="Export experiment reports.", no_args_is_help=True)

app.add_typer(scenarios_app, name="scenarios")
app.add_typer(runs_app, name="runs")
app.add_typer(traces_app, name="traces")
app.add_typer(evals_app, name="evals")
app.add_typer(documents_app, name="documents")
app.add_typer(patterns_app, name="patterns")
app.add_typer(report_app, name="report")


def _get_state(ctx: typer.Context) -> AppState:
    """Return the application state from the Typer context."""

    state = ctx.obj
    if not isinstance(state, AppState):
        raise ConfigError("CLI state was not initialized.")
    return state


def _resolve_config_path(ctx: typer.Context, config: Path | None) -> Path:
    """Resolve the config path for a command."""

    return config if config is not None else _get_state(ctx).config_path


def _load_config_if_present(config_path: Path | None) -> ExperimentConfig | None:
    """Load a configuration file when a path is provided."""

    if config_path is None:
        return None
    return load_config(config_path)


def _exit_for_error(exc: BaseException) -> typer.Exit:
    """Map exceptions to CLI exit codes."""

    if isinstance(exc, WorkflowError):
        return typer.Exit(code=2)
    return typer.Exit(code=1)


def _handle_command_error(exc: BaseException) -> None:
    """Render a command failure and exit with the right status code."""

    console.print(f"[red]Error:[/red] {exc}")
    raise _exit_for_error(exc)


def _print_success(title: str, message: str) -> None:
    """Render a small success table for completed commands."""

    table = Table(title=title)
    table.add_column("Status")
    table.add_column("Details")
    table.add_row("ok", message)
    console.print(table)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option("--verbose", "-v", count=True, help="Increase log verbosity."),
    ] = 0,
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Default experiment config path for commands that accept configuration.",
        ),
    ] = settings.default_config_path,
) -> None:
    """Configure the CLI runtime and shared options."""

    configure_logging(verbose=verbose > 0)
    ctx.obj = AppState(config_path=config, verbose=verbose > 0)
    logger.debug("cli_initialized", config_path=str(config), verbose=verbose > 0)


@app.command("init")
def init_command() -> None:
    """Initialize the MacroTrace database."""

    try:
        init_db()
    except MacroTraceError as exc:
        _handle_command_error(exc)
    _print_success("Database", "Initialized the MacroTrace database schema.")


@scenarios_app.command("generate")
def scenarios_generate_command(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Experiment config to load before generation."),
    ] = None,
    count: Annotated[
        int,
        typer.Option("--count", help="Number of scenarios to generate."),
    ] = 100,
    seed: Annotated[
        int | None,
        typer.Option("--seed", help="Override the experiment seed for generation."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for generated scenarios."),
    ] = None,
) -> None:
    """Generate scenarios for an experiment."""

    try:
        experiment_config = load_config(_resolve_config_path(ctx, config))
        generate_scenarios(experiment_config, count=count, seed=seed, output=output)
    except (ConfigError, NotImplementedError) as exc:
        _handle_command_error(exc)


@runs_app.command("execute")
def runs_execute_command(
    ctx: typer.Context,
    experiment: Annotated[
        str | None,
        typer.Option("--experiment", help="Experiment identifier to execute."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Experiment config to validate before execution."),
    ] = None,
    max_concurrency: Annotated[
        int | None,
        typer.Option("--max-concurrency", help="Override the run concurrency limit."),
    ] = None,
    adapter: Annotated[
        str | None,
        typer.Option("--adapter", help="Trace adapter used for execution."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate inputs without executing runs."),
    ] = False,
) -> None:
    """Execute workflow runs for an experiment."""

    try:
        resolved_config = _load_config_if_present(_resolve_config_path(ctx, config))
        execute_runs(
            experiment=experiment,
            config=resolved_config,
            max_concurrency=max_concurrency,
            adapter=adapter,
            dry_run=dry_run,
        )
    except (ConfigError, NotImplementedError) as exc:
        _handle_command_error(exc)


@traces_app.command("import")
def traces_import_command(
    adapter: Annotated[
        str,
        typer.Option("--adapter", help="Trace adapter used to interpret the input file."),
    ],
    path: Annotated[
        Path,
        typer.Option("--path", help="Path to the trace payload to import."),
    ],
) -> None:
    """Import externally produced traces."""

    try:
        import_traces(adapter=adapter, path=path)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@traces_app.command("validate")
def traces_validate_command(
    experiment: Annotated[
        str,
        typer.Option(
            "--experiment",
            help="Experiment identifier whose traces should be validated.",
        ),
    ],
) -> None:
    """Validate normalized traces for an experiment."""

    try:
        validate_traces(experiment=experiment)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@evals_app.command("run")
def evals_run_command(
    ctx: typer.Context,
    experiment: Annotated[
        str,
        typer.Option("--experiment", help="Experiment identifier to evaluate."),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Experiment config to validate before evaluation."),
    ] = None,
) -> None:
    """Run the evaluation suite for an experiment."""

    try:
        experiment_config = _load_config_if_present(_resolve_config_path(ctx, config))
        run_evals(experiment=experiment, config=experiment_config)
    except (ConfigError, NotImplementedError) as exc:
        _handle_command_error(exc)


@evals_app.command("summary")
def evals_summary_command(
    experiment: Annotated[
        str,
        typer.Option("--experiment", help="Experiment identifier to summarize."),
    ],
) -> None:
    """Summarize evaluation results for an experiment."""

    try:
        summarize_evals(experiment=experiment)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@documents_app.command("build")
def documents_build_command(
    experiment: Annotated[
        str,
        typer.Option("--experiment", help="Experiment identifier to render into trace documents."),
    ],
    schema_version: Annotated[
        str | None,
        typer.Option("--schema-version", help="Override the trace document schema version."),
    ] = None,
) -> None:
    """Build trace documents for an experiment."""

    try:
        build_documents(experiment=experiment, schema_version=schema_version)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@patterns_app.command("discover")
def patterns_discover_command(
    experiment: Annotated[
        str,
        typer.Option("--experiment", help="Experiment identifier to analyze."),
    ],
    include_all: Annotated[
        bool,
        typer.Option("--include-all", help="Include successful traces in discovery."),
    ] = False,
) -> None:
    """Discover recurring behavior patterns."""

    try:
        discover_patterns(experiment=experiment, include_all=include_all)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@app.command("diagnose")
def diagnose_command(
    experiment: Annotated[
        str,
        typer.Option("--experiment", help="Experiment identifier to diagnose."),
    ],
    pattern: Annotated[
        str,
        typer.Option("--pattern", help="Pattern identifier or selector to diagnose."),
    ],
) -> None:
    """Diagnose a discovered behavior pattern."""

    try:
        diagnose_pattern(experiment=experiment, pattern=pattern)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@app.command("compare")
def compare_command(
    baseline: Annotated[
        str,
        typer.Option("--baseline", help="Baseline experiment identifier."),
    ],
    candidate: Annotated[
        str,
        typer.Option("--candidate", help="Candidate experiment identifier."),
    ],
) -> None:
    """Compare two experiments."""

    try:
        compare_experiments(baseline=baseline, candidate=candidate)
    except NotImplementedError as exc:
        _handle_command_error(exc)


@app.command("ui")
def ui_command() -> None:
    """Launch the research UI."""

    try:
        launch_ui()
    except NotImplementedError as exc:
        _handle_command_error(exc)


@report_app.command("export")
def report_export_command(
    experiment: Annotated[
        str,
        typer.Option("--experiment", help="Experiment identifier to export."),
    ],
    output_format: Annotated[
        ReportFormat,
        typer.Option("--format", help="Export format."),
    ] = "markdown",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the exported report to a file."),
    ] = None,
) -> None:
    """Export an experiment report."""

    try:
        export_report(experiment=experiment, output_format=output_format, output=output)
    except NotImplementedError as exc:
        _handle_command_error(exc)
