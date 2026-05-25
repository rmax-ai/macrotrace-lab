# PYTHON_API_DESIGN.md — API Design Principles for MacroTrace Lab

## Naming Conventions

### Python Conventions
- **`snake_case`** for functions, methods, variables, module names.
- **`PascalCase`** for classes, type aliases, enums.
- **`UPPER_CASE`** for module-level constants.
- **One leading underscore** for private/internal: `_normalize_event()`.
- **Two leading underscores** only for name mangling in inheritance (rarely needed).

### Domain-Specific Naming
- **Pydantic models** use singular nouns: `TraceEvent`, `EvalFinding`, `BehaviorPattern`.
- **Enum members** are `StrEnum` with uppercase: `RunOutcome.APPROVED`.
- **CLI command groups** use verbs: `macrotrace runs execute`, `macrotrace patterns discover`.
- **Adapter classes** follow `<Framework>Adapter` naming: `OpenAIAgentsAdapter`.
- **Evaluator classes** follow `<Function>Eval` naming: `ReviewGateEval`, `OutcomeCorrectnessEval`.
- **Service classes** use `<Domain>Service`: `EmbeddingService`, `ClusteringService`.

## Pydantic Schema Design

### Schema Conventions
```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import StrEnum

class RunOutcome(StrEnum):
    APPROVED = "approved"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"
    FAILED = "failed"

class EvalFinding(BaseModel):
    """A typed finding produced by a deterministic or LLM-based evaluator."""
    model_config = {"frozen": True, "extra": "forbid"}  # immutable, no extra fields

    finding_id: str = Field(description="Unique identifier for this finding")
    run_id: str = Field(description="Run this finding belongs to")
    evaluator_name: str = Field(description="Name of the evaluator that produced this")
    evaluator_version: str = Field(description="Semantic version of the evaluator")
    finding_type: FindingType = Field(description="Category of finding")
    passed: bool = Field(description="Whether the check passed")
    severity: int = Field(ge=0, le=5, description="Severity 0-5")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    evidence_event_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(default="")
```

### Rules
- **Every field gets a `description=`.** This powers auto-generated docs and dashboard tooltips.
- **Use `Field(ge=..., le=...)`** for bounded numeric values.
- **Use `model_config = {"frozen": True}`** for all domain models (immutable by default).
- **Use `model_config = {"extra": "forbid"}`** to catch typos in serialization.
- **Prefer `list[str]` over `List[str]`** (PEP 585).
- **Use `AliasGenerator`** for camelCase ↔ snake_case if serialization requires it (not needed for MVP — keep snake_case everywhere).

### Serialization
- **All models serialize to JSON/JSONL.** Use `.model_dump_json()` and `.model_validate_json()`.
- **Do not use pickle.** JSONL is the universal interchange format for this project.
- **Datetime fields use ISO 8601** (Pydantic default).
- **UUID fields as `str` initially** — plain strings are simpler for CLI debugging.

## CLI Design (Typer)

### Command Structure
```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(no_args_is_help=True)
runs_app = typer.Typer(no_args_is_help=True)
app.add_typer(runs_app, name="runs", help="Execute and manage workflow runs")

@runs_app.command("execute")
def execute_runs(
    experiment: str = typer.Argument(..., help="Experiment name or config path"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Override config file"),
    max_concurrency: int = typer.Option(10, "--max-concurrency", help="Max parallel runs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without executing"),
):
    """Execute workflow runs for an experiment."""
    ...
```

### CLI Conventions
- **Noun-verb subcommands**: `macrotrace runs execute`, `macrotrace patterns discover`, `macrotrace traces import`.
- **Global options** (verbose, config path) on the root app.
- **Use `typer.Argument` for required parameters**, `typer.Option` for optional ones.
- **Long options with `--`.** Short aliases only for common flags (`-c`, `-v`, `-o`).
- **CLI output is human-readable text** (not JSON). Use `rich` or `rich.table` for formatted output.
- **Progress bars** use `rich.progress` for batch operations.
- **`--dry-run` flag** available on all destructive/mutating commands.
- **`--help` auto-generated** by Typer — keep parameter `help=` strings descriptive.

### Config Loading
```python
def load_config(config_path: Path) -> ExperimentConfig:
    """Load and validate experiment config from YAML."""
    raw = yaml.safe_load(config_path.read_text())
    return ExperimentConfig.model_validate(raw)
```

## REST API (FastAPI — Optional / Future)

### Structure (if added)
```python
# src/macrotrace/api/
# ├── __init__.py
# ├── main.py          # FastAPI app
# ├── routers/
# │   ├── experiments.py
# │   ├── runs.py
# │   ├── patterns.py
# │   └── comparisons.py
# └── deps.py          # dependency injection

from fastapi import APIRouter, Depends

router = APIRouter(prefix="/experiments", tags=["experiments"])

@router.post("/")
def create_experiment(body: ExperimentCreate, db: Session = Depends(get_db)):
    ... return ExperimentOut
```

### API Conventions (If Added)
- **POST for mutations, GET for reads.** RESTful resource URLs.
- **Request/response models are Pydantic.** Separate `*Create`, `*Out`, `*Update` schemas.
- **Return `HTTPException` with structured detail** for errors.
- **Use dependency injection** for DB sessions, config, embedding service.
- **Prefix all routes with `/api/v1`** for versioning.

## Versioning

### Schema Versioning
- **Major schema changes get a new `document_schema_version`** in the trace document format.
- **Store version per experiment** so old experiments remain reproducible.
- **Backward compatibility** is not required for MVP — but version fields are mandatory.

### Evaluator Versioning
- **Each evaluator has a `version` field** (semantic string).
- **Store evaluator_version per finding.**
- **Incompatible rubric changes bump major version.**

## Error Architecture

### Exception Hierarchy
```python
class MacroTraceError(Exception):
    """Base exception for all MacroTrace errors."""
    pass

class ConfigError(MacroTraceError):
    """Invalid or missing configuration."""
    pass

class SchemaError(MacroTraceError):
    """Schema validation failed on input data."""
    pass

class WorkflowError(MacroTraceError):
    """Workflow execution error."""
    pass

class AdapterError(MacroTraceError):
    """Trace adapter failed to normalize events."""
    pass

class DiscoveryError(MacroTraceError):
    """Embedding or clustering pipeline error."""
    pass
```

### CLI Exit Codes
- **0:** Success
- **1:** General error (config, schema, I/O)
- **2:** Workflow execution failure
- **3:** No results (empty experiment, no patterns found)
