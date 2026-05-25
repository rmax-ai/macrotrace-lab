# PYTHON_DEVELOPMENT.md — Python Engineering Guidelines for MacroTrace Lab

## Core Language Conventions

### Modern Python (3.12+)
- **Use `from __future__ import annotations`** at the top of every module. Enables PEP 604 union syntax (`str | None`) and deferred evaluation.
- **Prefer `match`/`case`** over chained `if/elif` for event type dispatch and state machine transitions.
- **Use `type` aliases** for complex types: `type RunID = str`.
- **Prefer `enum.StrEnum`** for string-constrained values (`RunOutcome`, `EventType`).
- **Use `dataclass(frozen=True, slots=True)`** for immutable internal data containers. Use Pydantic `BaseModel` for schemas that need validation or serialization.

### Type System
- **Never skip type annotations on public APIs.** Use `mypy --strict` as the reference.
- **Use `Self` return type** (PEP 673) for fluent builder methods.
- **Use `override` decorator** (PEP 698) when overriding methods in subclasses.
- **Use `typing.Protocol` for structural subtyping** — the adapter interface and evaluator interface are Protocols.
- **Use `TypeVar` with bounds** for generic algorithms (e.g. `E = TypeVar("E", bound="BaseEvent")`).

## Concurrency

- **Prefer synchronous code by default.** The MVP runs batch workloads locally. Async adds complexity with no benefit for SQLite + embedding workloads.
- **Use `concurrent.futures.ThreadPoolExecutor`** for parallel run execution (batch scenario execution). Max concurrency is configurable.
- **Use `ProcessPoolExecutor` only for CPU-bound work** (embedding, clustering) that would benefit from parallelism.
- **Avoid asyncio unless adding the FastAPI REST API.** If async is needed later, use `anyio` for structured concurrency.

## Testing

### Pytest Configuration (`pyproject.toml`)
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "llm: marks tests that call LLM judges (deselect by default)",
    "integration: marks slow integration tests",
]
filterwarnings = ["error"]
```

### Fixture Strategy
- **Scope fixtures appropriately.** `session` scope for DB schema creation, embedding model loading. `function` scope for per-test state.
- **Use `tmp_path` fixture** for any filesystem I/O.
- **Use `monkeypatch` for environment variable overrides** (config testing).
- **Mock at the adapter boundary**, not the implementation boundary. Mock the `embedding_service.encode()` call, not individual numpy operations.

### Property-Based Testing
- **Use `hypothesis`** for:
  - Schema validation: any valid dict must correctly deserialize to a Pydantic model
  - Trace normalization: any well-formed raw trace must produce valid normalized events
  - Config parsing: any valid YAML must produce a valid `ExperimentConfig`
  - Clustering: output `cluster_id` must be non-negative or `-1` (noise)

### Fixture Data
- **Keep fixture traces in `tests/fixtures/`** as JSONL files.
- **Use `pytest_generate_tests`** to parametrize tests over fixture files automatically.
- **Minimum fixture set:** 1 clean trace, 1 trace with each fault type, 1 mixed set.
- **Fixture traces are committed to the repo** (small, synthetic).

## Observability

### Logging with structlog
```python
import structlog

logger = structlog.get_logger(__name__)

# Always include context
logger.info("run.completed", run_id=run_id, outcome=outcome, latency_ms=latency)
logger.warning("eval.finding", finding_type="routing_error", severity=5, run_id=run_id)
logger.error("trace.normalization.failed", trace_id=trace_id, error=str(e))
```

### Configuration
```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### Log Level by Environment
- **Development:** `INFO`, structured to stdout
- **CLI batch:** `WARNING`, structured JSON
- **Dashboard:** `INFO`, structured to file

### Metrics
- Use **`loguru`-style counters via structlog** initially (log `run_count=N`, `finding_count=M`).
- No external monitoring system in MVP. Store aggregate metrics as experiment metadata.

## Performance

### Profiling
- **Profile before optimizing.** Use `py-spy` for wall-clock profiling, `cProfile` for function-level.
- **Warm up.** Run at least 3 iterations before measuring.
- **Focus on three hot paths:** embedding service, clustering pipeline, trace document construction.

### Allocation Patterns
- **Prefer generators over lists** for trace event processing: `(normalize(e) for e in raw_events)`.
- **Use `__slots__` on dataclasses** with many instances (`TraceEvent`, `EvalFinding`).
- **Preallocate numpy arrays** when vector sizes are known (embedding output).
- **Use `array` module or `numpy`** for large numeric sequences; avoid Python lists of floats.

### SQLite Performance
```python
# Always
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  # 64 MB
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

# Batch inserts inside a transaction
# Use executemany for bulk inserts
```

## Reproducibility

### Seed Management
```python
import random
import numpy as np

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    # UMAP has its own random_state param
    # HDBSCAN has its own random_state param (gen_min_span_tree)
```

### Determinism Requirements
- Scenario generation must be seed-deterministic.
- UMAP with `random_state` is deterministic within the same scikit-learn version.
- HDBSCAN with `gen_min_span_tree=True` is deterministic within the same version.
- Embedding models are deterministic for the same input (no dropout).
- Workflow runs with agents: seed affects LLM sampling; pin `temperature` and `seed` params per experiment.

## Production Readiness (MVP+)

### Graceful Shutdown
- CLI commands should handle `KeyboardInterrupt` and save partial results.
- Batch runner should checkpoint progress every N runs.

### Configuration Validation
- Validate config at startup: check all referenced files exist, required agents are defined, embedding model is available.
- Use Pydantic validators with `@field_validator` and `@model_validator`.

### Cleanup
- `macrotrace init` should be idempotent (no-op if DB exists).
- `macrotrace clean --experiment X` to remove traces and findings for an experiment.
