# Experiment Protocol

## Prerequisites

- Python 3.12+ with `uv`
- `OPENAI_API_KEY` set (for live tracing) OR run with JSONL import adapter (no key needed)

## Step-by-Step Protocol

### 1. Define the Experiment

Create a YAML config file:

```yaml
experiment:
  name: my_research_experiment
  workflow_version: "0.1.0"
  scenario_dataset: procurement_v1
  seed: 42
  runs_per_scenario: 5
  max_concurrency: 10

models:
  coordinator: gpt-4.1-mini
  specialists: gpt-4.1-mini
  judge: gpt-4.1-mini

fault_injections:
  - coordinator_skip_security_on_unknown_vendor
```

### 2. Generate Scenarios

```bash
macrotrace scenarios generate --config my_experiment.yaml --count 300
```

The system generates scenarios across 8 case types.

### 3. Run Baseline

```bash
macrotrace runs execute --experiment my_experiment
macrotrace evals run --experiment my_experiment
macrotrace documents build --experiment my_experiment
macrotrace patterns discover --experiment my_experiment
macrotrace diagnose --experiment my_experiment --pattern top
```

### 4. Inspect Results

```bash
macrotrace ui
```

Or export a report:

```bash
macrotrace report export --experiment my_experiment
```

### 5. Define and Run Intervention

1. Modify the workflow configuration (routing rules, agent prompts, tool behavior)
2. Create a new experiment config pointing to the modified workflow
3. Run on the same scenario dataset:

```bash
macrotrace runs execute --experiment my_intervention
macrotrace evals run --experiment my_intervention
macrotrace patterns discover --experiment my_intervention
```

### 6. Compare

```bash
macrotrace compare --baseline my_experiment --candidate my_intervention
```

### 7. Document

```bash
macrotrace report export --experiment my_experiment
macrotrace report export --experiment my_intervention
```

## Minimum Experimental Protocol

| Phase | Runs | Purpose |
|-------|------|---------|
| Smoke | 20 | Development — verify pipeline works |
| Discovery | 100 | Preliminary pattern identification |
| Baseline | 300 | Establish pattern distribution |
| Intervention | 300 | Measure pattern change |
| Comparison | — | Report delta |

## Reproducibility Checklist

- [ ] Seed is pinned in config
- [ ] Config hash is stored with experiment
- [ ] Workflow version is recorded
- [ ] Document schema version is recorded
- [ ] Evaluator versions are recorded per finding
- [ ] All data files are JSONL (no pickle)
- [ ] Raw traces are retained separately from documents
