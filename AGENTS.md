# AGENTS.md — Guidelines for MacroTrace Lab

This document captures the conventions and guidelines that all contributors and AI coding agents should follow when working on **MacroTrace Lab**.

---

## 1. Code Organisation

- **src layout.** All application code lives under `src/macrotrace/`. No top-level `.py` files.
- **One module per concern.** Each module in `src/macrotrace/` maps to a single domain concept (schemas, evals, discovery, diagnosis). Avoid catch-all `utils.py`.
- **Flat over nested.** Prefer shallow module trees. Only introduce sub-packages when a module exceeds ~400 lines.
- **CLI commands in `cli.py`** only — thin dispatch to `src/` modules. No business logic in CLI handlers.
- **Keep tests parallel.** Mirror `src/macrotrace/` structure under `tests/`. Unit tests in `tests/unit/`, integration in `tests/integration/`.

## 2. Type Hints

- **All public functions must have complete type annotations.** Use `from __future__ import annotations` at module top for deferred evaluation (PEP 604 syntax: `str | None` instead of `Optional[str]`).
- **Use `dataclass` or Pydantic `BaseModel` for data containers.** Prefer Pydantic v2 `BaseModel` for domain schemas (serialization, validation). Use `dataclass` for internal runtime state.
- **Use `TypeAlias` for complex types** (`type TraceID = str`).
- **Use `Protocol` for structural subtyping** (adapter interface, evaluator interface). Not ABC.
- **Avoid `Any`** — if truly necessary, document why in a `# type: ignore[annotation]` comment.
- **Use `Literal` for constrained string values** — see `RunOutcome`, `EventType`, `FindingType` in the spec.

## 3. Error Handling

- **Use typed custom exceptions** inheriting from `MacroTraceError(BaseException)` base class.
- **Never `except Exception: pass`.** Catch specific exceptions or use `contextlib.suppress`.
- **Prefer `Result` pattern** (monadic error handling) for internal pipes. Use exceptions only at module boundaries (CLI, API, adapter).
- **Log errors with `structlog`** — always include context vars (run_id, experiment_id, trace_id).
- **Fail fast on configuration errors.** Validate config at startup, not mid-run.

## 4. Testing

- **pytest is the only test framework.** No unittest.TestCase.
- **Unit tests go next to the source** in `tests/unit/` mirroring `src/` path. Integration tests in `tests/integration/`.
- **Fixture traces live in `tests/fixtures/`.** Seed with JSONL files.
- **Use `pytest.fixture` for shared state** (db session, embedding model stub, scenario generator).
- **Mock expensive operations:** embedding model calls, LLM judge calls, OpenAI API calls. Never call real models in unit tests.
- **Property-based tests** (`hypothesis`) for schema validation, trace normalization, and config parsing.
- **Run with:** `pytest -v --tb=short -x`
- **Coverage minimum:** 80% line coverage (run via `pytest --cov=src/macrotrace --cov-report=term-missing`).

## 5. Documentation

- **Every public module, class, and function must have a docstring.** Google-style or NumPy-style — pick one and stay consistent. (Recommend: Google-style for brevity.)
- **Every Pydantic model field must have a `description=`** for auto-generated docs.
- **Keep `docs/` in sync with every PR that changes user-visible behavior.** The `docs/` folder contains:
  - `docs/getting-started.md`
  - `docs/cli-reference.md`
  - `docs/api-reference.md` (optional — only if FastAPI REST API is added)
  - `docs/trace-schema.md`
  - `docs/eval-design.md`
  - `docs/experiment-protocol.md`
- **README.md must have a working quickstart that new users can copy-paste.**
- **Every experiment config YAML must have inline comments** explaining each field.

## 6. Imports

- **Use absolute imports** (`from macrotrace.schemas.trace import TraceEvent`), not relative.
- **Import order:** standard library → third-party → local. Each group separated by blank line.
- **Use `TYPE_CHECKING` for type-only imports** to avoid circular imports at runtime.
- **No star imports (`from x import *`)** unless `__all__` is explicitly defined.

## 7. Formatting and Linting

- **ruff for both formatting and linting.** Single tool, no black/isort/flake8.
  - Use `ruff format` for formatting (default config).
  - Use `ruff check --fix` for linting.
- **Minimum ruff rules:** `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`, `ARG`, `C4`, `T10`, `FA`, `RUF`.
- **Pre-commit hook:** `ruff format` + `ruff check --fix` + `mypy src/`.
- **CI gates:**
  ```bash
  ruff format --check .
  ruff check .
  mypy src/macrotrace
  pytest -v --tb=short -x --cov=src/macrotrace --cov-fail-under=80
  ```

## 8. Dependencies

- **Pin major versions in `pyproject.toml`.** Use `^` ranges (e.g. `pydantic >=2.5,<3.0`).
- **Minimize dependencies.** Every new dependency must justify itself.
- **Use `uv` for dependency management.** Lockfile (`uv.lock`) committed to repo.
- **Group dependencies:** `[project.dependencies]` for runtime, `[project.optional-dependencies.dev]` for dev.
- **No vendored code.** If you must modify a dependency, fork it.

## 9. Reproducibility

- **Pin `random_seed` in every experiment config.** Pass through pipeline to UMAP, HDBSCAN, scenario generation, and workflow runner.
- **Store `config_hash` per experiment.** Hash = sha256 of the resolved experiment config JSON.
- **Store `document_schema_version`, `eval_rubric_version`, `workflow_version` per experiment run.**
- **All data files are JSONL or JSON** — no pickle, no joblib.
- **Everything committed except `data/`** — traces and generated data are gitignored.

## 10. References

- **`PYTHON_DEVELOPMENT.md`** — day-to-day Python engineering: async patterns, testing, profiling, observability, structlog setup.
- **`PYTHON_API_DESIGN.md`** — API surface conventions: Pydantic schemas, Typer CLI patterns, FastAPI patterns, versioning.
- **`PYTHON_SYSTEM_DESIGN_PATTERNS.md`** — architecture patterns for the evaluation domain: adapter, pipeline, repository, event-driven, ensemble.
- **`PYTHON_PROJECT_ARCHITECTURE.md`** — module layout, layering, dependency direction, workspace structure.
- **`ARCHITECTURE.md`** — high-level system architecture and data flow.
- **`DECISIONS.md`** — design rationale for major choices.

---

*These guidelines apply to human contributors and AI coding agents alike. When in doubt, favour correctness, reproducibility, and clarity over cleverness.*
