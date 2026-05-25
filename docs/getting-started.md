# Getting Started

## Installation

```bash
# Prerequisites: Python 3.12+, uv
git clone https://github.com/rmax-ai/macrotrace-lab
cd macrotrace-lab
uv sync
```

## Quickstart (No API Key Required)

The full pipeline works offline using the JSONL import adapter and seeded example data:

```bash
# 1. Initialize the database
macrotrace init

# 2. Generate 20 synthetic scenarios
macrotrace scenarios generate --count 20 --seed 42

# 3. Execute the reference workflow (simulated, no API calls needed)
macrotrace runs execute --experiment smoke_test --max-concurrency 4

# 4. Run the eval suite
macrotrace evals run --experiment smoke_test

# 5. Build compact trace documents
macrotrace documents build --experiment smoke_test

# 6. Discover behaviour patterns
macrotrace patterns discover --experiment smoke_test

# 7. Diagnose the top pattern
macrotrace diagnose --experiment smoke_test --pattern top

# 8. Launch the dashboard
macrotrace ui
```

## Full Experiment Workflow

```bash
# 1. Plan your experiment
#    Copy configs/default.yaml and customize

# 2. Generate scenarios
macrotrace scenarios generate --config my-experiment.yaml --count 300

# 3. Execute runs
macrotrace runs execute --experiment my_experiment

# 4. Run evals
macrotrace evals run --experiment my_experiment

# 5. Discover patterns
macrotrace patterns discover --experiment my_experiment

# 6. Compare intervention
macrotrace compare --baseline baseline_v1 --candidate my_experiment

# 7. Export report
macrotrace report export --experiment my_experiment --format markdown
```

## With OpenAI Agents SDK (Live Tracing)

```bash
# Set your API key
export OPENAI_API_KEY=sk-...

# Run with live agent execution
macrotrace runs execute --experiment live_baseline --adapter openai
```

## Data Format

All data is stored as JSONL in `data/`:

- `data/scenarios/` — Scenario definitions
- `data/traces/` — Raw and normalized trace events
- `data/labels/` — Eval findings
- `data/documents/` — Compact trace documents
- `data/experiments/` — Experiment metadata and results
- `data/exports/` — Generated reports

The SQLite database at `data/macrotrace.db` indexes all data for the dashboard.
