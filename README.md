# MacroTrace Lab

**Small-Scale Macro-Evaluation System for Agentic Workflows**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)]()
[![CI](https://github.com/rmax-ai/macrotrace-lab/actions/workflows/ci.yml/badge.svg)]()

MacroTrace Lab is a local-first research system that evaluates agentic workflows at scale — discovering recurring failure patterns across hundreds of traced runs, ranking them by operational impact, and diagnosing upstream components for human investigation.

---

## Quickstart

```bash
# Install
uv sync

# Initialize database
macrotrace init

# Generate 50 synthetic scenarios and run the reference workflow
macrotrace scenarios generate --count 50 --seed 42
macrotrace runs execute --experiment smoke_test

# Run evals, discover patterns, and inspect results
macrotrace evals run --experiment smoke_test
macrotrace patterns discover --experiment smoke_test
macrotrace diagnose --experiment smoke_test --pattern top

# Launch the dashboard
macrotrace ui
```

**No API key required.** The JSONL import adapter and seeded example data let you run the full pipeline offline.

## Architecture Overview

```
Scenarios ──▶ Workflow Runner ──▶ Trace Capture ──▶ Normalization
    ──▶ Lower-Level Evals ──▶ Trace Documents ──▶ Embeddings
    ──▶ UMAP ──▶ HDBSCAN ──▶ Impact Ranking ──▶ Graph Diagnosis
    ──▶ Human Review ──▶ Intervention
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full component diagram and data flow.

## Documentation

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and data flow |
| [SPEC.md](SPEC.md) | Acceptance criteria and feature list |
| [DECISIONS.md](DECISIONS.md) | Design rationale and trade-offs |
| [ROADMAP.md](ROADMAP.md) | Development roadmap |
| [AGENTS.md](AGENTS.md) | Development conventions for contributors |
| [PYTHON_DEVELOPMENT.md](PYTHON_DEVELOPMENT.md) | Python engineering guidelines |
| [PYTHON_API_DESIGN.md](PYTHON_API_DESIGN.md) | API design conventions |
| [PYTHON_SYSTEM_DESIGN_PATTERNS.md](PYTHON_SYSTEM_DESIGN_PATTERNS.md) | Architecture patterns |
| [PYTHON_PROJECT_ARCHITECTURE.md](PYTHON_PROJECT_ARCHITECTURE.md) | Module layout and layering |
| [docs/getting-started.md](docs/getting-started.md) | Installation and walkthrough |
| [docs/cli-reference.md](docs/cli-reference.md) | CLI command reference |
| [docs/trace-schema.md](docs/trace-schema.md) | Normalized trace event schema |
| [docs/eval-design.md](docs/eval-design.md) | Evaluation rubric design |
| [docs/experiment-protocol.md](docs/experiment-protocol.md) | Running experiments |

## Reference Workflow

The MVP includes the **Research Procurement Review** workflow — a multi-agent system that evaluates software/tool procurement requests:

| Agent | Responsibility |
|-------|---------------|
| CoordinatorAgent | Route request and coordinate workflow |
| BudgetAgent | Check available budget and spend threshold |
| SecurityAgent | Inspect data sensitivity and vendor access risk |
| PolicyAgent | Determine approval/blocking requirements |
| ProcurementAgent | Produce purchase recommendation |
| ReleaseReviewerAgent | Approve, block, or request human review |

8 scenario types capture realistic procurement edge cases, and configurable fault injection creates known defects for evaluation.

## CLI Commands

```bash
macrotrace init                          # Initialize database
macrotrace scenarios generate --count N  # Generate scenarios
macrotrace runs execute --experiment X   # Execute workflow runs
macrotrace traces import --adapter jsonl # Import pre-recorded traces
macrotrace evals run --experiment X      # Run eval suite
macrotrace documents build --experiment X# Build trace documents
macrotrace patterns discover --experiment X  # Discover patterns
macrotrace diagnose --experiment X       # Diagnose top pattern
macrotrace compare --baseline X --candidate Y  # Compare experiments
macrotrace ui                            # Launch dashboard
macrotrace report export --experiment X  # Export report
```

## Project Structure

```
macrotrace-lab/
├── src/macrotrace/       # Application code
│   ├── cli.py            # Typer CLI
│   ├── schemas/          # Pydantic domain models
│   ├── runtime/          # Workflow runner + agents + tools
│   ├── adapters/         # Trace adapter interface + implementations
│   ├── evals/            # Evaluation engine + rubrics
│   ├── discovery/        # Embedding + clustering pipeline
│   ├── diagnosis/        # Graph-based suspect analysis
│   ├── reporting/        # Markdown + plot generation
│   └── ui/               # Streamlit dashboard
├── configs/              # Experiment YAML configurations
├── data/                 # Generated traces and evals (gitignored)
├── docs/                 # User-facing documentation
└── tests/                # Unit, integration, acceptance tests
```

## Development

```bash
# Setup
uv sync --group dev

# Format and lint
ruff format .
ruff check --fix

# Type check
mypy src/macrotrace

# Test
pytest -v --tb=short --cov=src/macrotrace

# Run a full smoke test (no API key needed)
make smoke-test
```

## License

MIT — see [LICENSE](LICENSE).
