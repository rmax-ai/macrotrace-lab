# PYTHON_PROJECT_ARCHITECTURE.md — Project Structure & Module Layout

## Project Layout

```
macrotrace-lab/
├── README.md
├── AGENTS.md
├── ARCHITECTURE.md
├── DECISIONS.md
├── ROADMAP.md
├── PYTHON_DEVELOPMENT.md
├── PYTHON_API_DESIGN.md
├── PYTHON_SYSTEM_DESIGN_PATTERNS.md
├── PYTHON_PROJECT_ARCHITECTURE.md
├── SPEC.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── Makefile
├── configs/
│   ├── default.yaml
│   ├── baseline-experiment.yaml
│   └── intervention-annual-cost-check.yaml
├── data/                        # gitignored
│   ├── scenarios/
│   │   ├── procurement_seed.jsonl
│   │   └── generated/
│   ├── traces/
│   ├── labels/
│   ├── documents/
│   ├── experiments/
│   └── exports/
├── docs/
│   ├── getting-started.md
│   ├── cli-reference.md
│   ├── api-reference.md          # optional — only if FastAPI added
│   ├── trace-schema.md
│   ├── eval-design.md
│   └── experiment-protocol.md
├── src/macrotrace/
│   ├── __init__.py
│   ├── cli.py                    # Typer app, thin dispatch
│   ├── config.py                 # Pydantic Settings + YAML loading
│   ├── db.py                     # SQLModel engine, session, migrations
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── scenario.py
│   │   ├── trace.py
│   │   ├── eval.py
│   │   ├── pattern.py
│   │   └── experiment.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── runner.py             # Batch execution engine
│   │   ├── reference_workflow.py # Research Procurement Review workflow
│   │   ├── agents.py             # Specialist agent definitions
│   │   ├── tools.py              # Simulated tools (get_budget, etc.)
│   │   └── fault_injection.py    # Configurable defect injection
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py               # TraceAdapter Protocol
│   │   ├── openai_agents.py     # OpenAI Agents SDK adapter
│   │   └── jsonl_import.py       # JSONL import adapter
│   ├── tracing/
│   │   ├── __init__.py
│   │   ├── collector.py          # Trace collection orchestrator
│   │   ├── normalizer.py         # Adapter dispatch + normalization
│   │   └── redaction.py          # Sensitive field redaction
│   ├── evals/
│   │   ├── __init__.py
│   │   ├── engine.py             # Evaluation pipeline runner
│   │   ├── deterministic.py      # Deterministic evaluator implementations
│   │   ├── llm_judge.py          # Optional LLM judge evaluator
│   │   └── rubrics/
│   │       ├── routing.yaml
│   │       ├── policy.yaml
│   │       └── review.yaml
│   ├── documents/
│   │   ├── __init__.py
│   │   └── trace_document_builder.py
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── embedding.py          # sentence-transformers wrapper
│   │   ├── clustering.py         # UMAP + HDBSCAN pipeline
│   │   ├── labeling.py           # c-TF-IDF keyword extraction
│   │   └── ranking.py            # Impact score computation
│   ├── diagnosis/
│   │   ├── __init__.py
│   │   ├── graph_builder.py      # NetworkX graph construction
│   │   ├── suspects.py           # Suspect scoring
│   │   └── explanations.py       # Human-readable suspect explanations
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── markdown_report.py    # Markdown experiment report
│   │   └── plots.py              # Plotly chart helpers
│   └── ui/
│       ├── __init__.py
│       └── streamlit_app.py      # Multi-page Streamlit dashboard
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   ├── clean_trace.jsonl
    │   ├── fault_traces/
    │   └── scenarios.jsonl
    ├── unit/
    │   ├── test_schemas.py
    │   ├── test_config.py
    │   ├── test_db.py
    │   ├── test_normalizer.py
    │   ├── test_evaluators.py
    │   ├── test_document_builder.py
    │   ├── test_discovery.py
    │   └── test_diagnosis.py
    ├── integration/
    │   ├── test_eval_pipeline.py
    │   ├── test_discovery_pipeline.py
    │   └── test_diagnosis_pipeline.py
    └── acceptance/
        └── test_protocol.py
```

## Layering & Dependency Rules

### Layer Hierarchy

Layers must only depend downward:

```
CLI / UI (entry points)
    → Services (runner, eval engine, discovery pipeline, diagnosis pipeline)
        → Domain (schemas, models, protocols)
            → Infrastructure (DB, embedding service, file I/O)
                → Utility (exceptions, logging setup, type aliases)
```

### Dependency Direction Enforcement

```
src/macrotrace/
├── cli.py            ──▶ calls: runner, eval engine, discovery, diagnosis, report
├── config.py         ──▶ calls: schemas.experiment
├── db.py             ──▶ calls: schemas.* (all)
├── schemas/          ──▶ calls: nothing (pure data models)
├── runtime/          ──▶ calls: schemas.*, adapters, tracing
├── adapters/         ──▶ calls: schemas.trace
├── tracing/          ──▶ calls: schemas.trace, adapters
├── evals/            ──▶ calls: schemas.*, db
├── documents/        ──▶ calls: schemas.*
├── discovery/        ──▶ calls: schemas.*, documents
├── diagnosis/        ──▶ calls: schemas.*, discovery
├── reporting/        ──▶ calls: schemas.*, discovery
├── ui/               ──▶ calls: schemas.*, db, discovery, diagnosis
```

### Forbidden Dependencies

- **Tests may not import runtime modules directly.** Test through public API (CLI commands or service methods).
- **CLI may not import adapter or tracing modules directly.** CLI dispatches to services, services use adapters.
- **Schemas may not import from any other package.** They are pure data models.
- **No circular imports.** Use `TYPE_CHECKING` blocks for type-only cross-references.

## Package Boundaries

### `src/macrotrace/schemas/` — Pure Data Models
- No dependencies on other `macrotrace` modules.
- Pydantic v2 `BaseModel` classes with `frozen=True`.
- `StrEnum` types for constrained values.
- `model_config = {"extra": "forbid"}` throughout.

### `src/macrotrace/runtime/` — Workflow Execution
- Depends on `schemas.*` and `adapters.*`.
- Implements the reference workflow as self-contained agent code.
- Contains `runner.py` for batch execution and checkpointing.
- `fault_injection.py` modifies workflow config before execution (no changes to agent code).

### `src/macrotrace/evals/` — Evaluation Engine
- Depends on `schemas.*` and `db.*`.
- `deterministic.py` contains all rule-based evaluators.
- `llm_judge.py` wraps LLM API calls behind an optional interface.
- `engine.py` orchestrates evaluator execution per run.

### `src/macrotrace/discovery/` — Pattern Discovery Pipeline
- Depends on `schemas.*` and `documents.*`.
- `embedding.py` wraps `sentence-transformers`.
- `clustering.py` wraps UMAP + HDBSCAN.
- `labeling.py` implements c-TF-IDF keyword extraction.
- `ranking.py` computes impact scores.

### `src/macrotrace/diagnosis/` — Graph-Based Diagnosis
- Depends on `schemas.*` and `discovery.*`.
- `graph_builder.py` uses NetworkX.
- `suspects.py` implements the scoring formula.
- `explanations.py` generates human-readable suspect descriptions.

## CI/CD Integration

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          python-version: 3.12
      - run: uv sync
      - run: ruff format --check .
      - run: ruff check .
      - run: mypy src/macrotrace
      - run: pytest -v --tb=short --cov=src/macrotrace --cov-fail-under=80
      - run: python -m macrotrace init
      - run: python -m macrotrace scenarios generate --count 20 --seed 42
```

## Workspace Strategy

### Single Package (MVP)
- One Python package: `macrotrace`.
- Tests in `tests/` with no separate package.
- `pyproject.toml` at root with single `[project]` section.

### Future Monorepo (Beyond MVP)
If the project grows to include:
- A separate `macrotrace-agent` library
- A `macrotrace-gateway` service
- Benchmark runners

...consider a `uv` workspace with `[tool.uv.workspace]` and members as sub-packages. For MVP, single package is sufficient.
