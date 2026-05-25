"""Batch execution helpers for the reference workflow."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from macrotrace.runtime.reference_workflow import execute_reference_workflow
from macrotrace.schemas import ExperimentConfig, Run, Scenario

CHECKPOINT_INTERVAL = 5


def _experiment_id(config: ExperimentConfig) -> str:
    """Build a deterministic experiment identifier from the config."""

    payload = config.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"experiment-{digest}"


def _checkpoint_path(config: ExperimentConfig) -> Path:
    """Return the checkpoint path for an experiment."""

    safe_name = config.experiment.name.lower().replace(" ", "-")
    return Path(".macrotrace-checkpoints") / f"{safe_name}.json"


def _load_checkpoint(config: ExperimentConfig) -> dict[str, object]:
    """Load checkpoint state when available."""

    checkpoint_path = _checkpoint_path(config)
    if not checkpoint_path.exists():
        return {"completed_runs": [], "runs": []}
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


def _save_checkpoint(config: ExperimentConfig, runs: list[Run]) -> None:
    """Persist completed runs to disk."""

    checkpoint_path = _checkpoint_path(config)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "completed_runs": [run.run_id for run in runs],
        "runs": [run.model_dump(mode="json") for run in runs],
    }
    checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_once(
    *,
    config: ExperimentConfig,
    scenario: Scenario,
    run_index: int,
) -> Run:
    """Execute one workflow run and return normalized run metadata."""

    experiment_id = _experiment_id(config)
    run_seed = config.experiment.seed + run_index
    started_at = datetime.now(tz=UTC)
    workflow_result = execute_reference_workflow(
        scenario,
        seed=run_seed,
        fault_names=config.fault_injections,
    )
    ended_at = datetime.now(tz=UTC)
    run_id = f"{workflow_result.workflow_id}-attempt-{run_index}"
    return Run(
        run_id=run_id,
        trace_id=f"trace-{workflow_result.workflow_id}",
        experiment_id=experiment_id,
        scenario_id=scenario.scenario_id,
        started_at=started_at,
        ended_at=ended_at,
        run_outcome=workflow_result.outcome,
        final_output=workflow_result.final_decision,
        final_decision=workflow_result.final_decision,
        human_review_requested=workflow_result.outcome.value == "review_required",
        cost_estimate_usd=0.0,
        latency_ms=max(int((ended_at - started_at).total_seconds() * 1000), 0),
        error_type=None,
    )


def execute_experiment(config: ExperimentConfig, scenarios: list[Scenario]) -> list[Run]:
    """Execute all configured scenario runs with checkpointing support."""

    checkpoint = _load_checkpoint(config)
    completed_runs = {
        str(run_id) for run_id in checkpoint.get("completed_runs", []) if isinstance(run_id, str)
    }
    restored_runs = [
        Run.model_validate(run_payload)
        for run_payload in checkpoint.get("runs", [])
        if isinstance(run_payload, dict)
    ]
    runs_by_id = {run.run_id: run for run in restored_runs}

    pending_work: list[tuple[Scenario, int]] = []
    for scenario in scenarios:
        for run_index in range(config.experiment.runs_per_scenario):
            workflow_id = hashlib.sha256(
                f"{config.experiment.seed + run_index}|{scenario.scenario_id}".encode()
            ).hexdigest()[:12]
            run_id = f"workflow-{workflow_id}-attempt-{run_index}"
            if run_id not in completed_runs:
                pending_work.append((scenario, run_index))

    completed = list(restored_runs)
    futures: dict[Future[Run], tuple[Scenario, int]] = {}
    try:
        with ThreadPoolExecutor(max_workers=config.experiment.max_concurrency) as executor:
            for scenario, run_index in pending_work:
                futures[
                    executor.submit(
                        _run_once,
                        config=config,
                        scenario=scenario,
                        run_index=run_index,
                    )
                ] = (scenario, run_index)

            for run_count, future in enumerate(as_completed(futures), start=1):
                run = future.result()
                runs_by_id[run.run_id] = run
                completed.append(run)
                if run_count % CHECKPOINT_INTERVAL == 0:
                    _save_checkpoint(config, sorted(completed, key=lambda item: item.run_id))
    except KeyboardInterrupt:
        _save_checkpoint(config, sorted(completed, key=lambda item: item.run_id))
        return sorted(runs_by_id.values(), key=lambda item: item.run_id)

    ordered_runs = sorted(runs_by_id.values(), key=lambda item: item.run_id)
    _save_checkpoint(config, ordered_runs)
    return ordered_runs
