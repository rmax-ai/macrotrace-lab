# CLI Reference

## Global Flags

| Flag | Description |
|------|-------------|
| `--verbose`, `-v` | Increase log verbosity |
| `--config`, `-c` | Default path to experiment YAML config |
| `--help`, `-h` | Show help message |

## Commands

### `macrotrace init`

Initialize the database schema.

```bash
macrotrace init
```

Idempotent and safe to run multiple times.

### `macrotrace scenarios generate`

Generate synthetic scenarios for an experiment.

```bash
macrotrace scenarios generate \
  --config configs/baseline-experiment.yaml \
  --count 300
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | inherited global default | Experiment config |
| `--count` | `100` | Number of scenarios to generate |
| `--seed` | experiment seed | Random seed override |
| `--output`, `-o` | — | Output directory |

### `macrotrace runs execute`

Execute workflow runs for an experiment.

```bash
macrotrace runs execute \
  --experiment baseline_procurement_workflow_v1 \
  --max-concurrency 10
```

| Option | Default | Description |
|--------|---------|-------------|
| `--experiment` | — | Experiment identifier |
| `--config`, `-c` | inherited global default | Override config file |
| `--max-concurrency` | — | Max parallel executions |
| `--adapter` | — | Trace adapter name |
| `--dry-run` | `false` | Validate without executing |

### `macrotrace traces import`

Import externally produced traces.

```bash
macrotrace traces import \
  --adapter jsonl \
  --path data/traces/import.jsonl
```

| Option | Default | Description |
|--------|---------|-------------|
| `--adapter` | required | Import adapter name |
| `--path` | required | Path to trace file |

### `macrotrace traces validate`

Validate trace events against the normalized schema.

```bash
macrotrace traces validate --experiment smoke_test
```

### `macrotrace evals run`

Run the evaluation suite for an experiment.

```bash
macrotrace evals run --experiment baseline_procurement_workflow_v1
```

| Option | Default | Description |
|--------|---------|-------------|
| `--experiment` | required | Experiment name |
| `--config`, `-c` | inherited global default | Override config |

### `macrotrace evals summary`

Show eval finding distribution for an experiment.

```bash
macrotrace evals summary --experiment baseline_procurement_workflow_v1
```

### `macrotrace documents build`

Build compact trace documents for an experiment.

```bash
macrotrace documents build --experiment baseline_procurement_workflow_v1
```

| Option | Default | Description |
|--------|---------|-------------|
| `--experiment` | required | Experiment name |
| `--schema-version` | `1.0.0` | Document schema version |

### `macrotrace patterns discover`

Discover behaviour patterns using embeddings + clustering.

```bash
macrotrace patterns discover --experiment baseline_procurement_workflow_v1
```

| Option | Default | Description |
|--------|---------|-------------|
| `--experiment` | required | Experiment name |
| `--include-all` | `false` | Also analyze successful traces |

### `macrotrace diagnose`

Diagnose the top pattern from an experiment.

```bash
macrotrace diagnose \
  --experiment baseline_procurement_workflow_v1 \
  --pattern top
```

| Option | Default | Description |
|--------|---------|-------------|
| `--experiment` | required | Experiment name |
| `--pattern` | `top` | Pattern ID or `top` for highest impact |

### `macrotrace compare`

Compare baseline and intervention experiments.

```bash
macrotrace compare \
  --baseline baseline_procurement_workflow_v1 \
  --candidate annual_cost_fix_v1
```

| Option | Default | Description |
|--------|---------|-------------|
| `--baseline` | required | Baseline experiment name |
| `--candidate` | required | Intervention experiment name |

### `macrotrace ui`

Launch the Streamlit dashboard.

```bash
macrotrace ui
```

Launches the Streamlit dashboard entrypoint when implemented.

### `macrotrace report export`

Export an experiment report as Markdown.

```bash
macrotrace report export \
  --experiment baseline_procurement_workflow_v1 \
  --format markdown \
  --output data/exports/report.md
```

| Option | Default | Description |
|--------|---------|-------------|
| `--experiment` | required | Experiment name |
| `--format` | `markdown` | Export format: `markdown` or `html` |
| `--output`, `-o` | stdout | Output file path |
