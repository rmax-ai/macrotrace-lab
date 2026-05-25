# MacroTrace Lab — Specification

## Scope

A local-first research system for evaluating agentic workflows at two levels: individual-run evaluation and population-level behavioural analysis. It ingests trace events from an agent workflow, attaches eval findings, converts traces into compact semantic documents, discovers recurring behaviour patterns via embeddings + clustering, ranks patterns by operational impact, and reconstructs trace graphs for high-impact patterns to produce a human investigation queue.

## Features

### Feature: Scenario Management
- Import scenarios from JSONL
- Generate synthetic scenario variants from templates
- Each scenario includes case_type, business signals, expected outcome, mishandling severity
- Controlled fault injection into workflow configurations

### Feature: Workflow Execution
- Reference multi-agent workflow (Research Procurement Review) with 6 specialist agents
- Repeatable runs with stored config + random seed
- Configurable max concurrency for batch execution

### Feature: Trace Capture
- Unique trace_id per run
- Normalized TraceEvent schema: agent activations, handoffs, tool calls, guardrails, decisions, errors
- Adapter-based runtime (OpenAI Agents SDK first, JSONL import for development)
- Local redaction of sensitive fields

### Feature: Lower-Level Evals
- 5 deterministic evaluators
- Optional LLM judge evaluators
- Typed EvalFinding with evidence event IDs
- Versioned evaluation rubrics

### Feature: Trace Document Construction
- Compact semantic documents from trace + findings
- Deterministic and versioned
- Controlled vocabulary for agents, events, findings, outcomes

### Feature: Pattern Discovery
- sentence-transformers embeddings
- UMAP dimensionality reduction
- HDBSCAN clustering
- c-TF-IDF keyword labels
- Impact ranking (prevalence × severity)

### Feature: Graph Diagnosis
- NetworkX execution graph per pattern
- Anchor event selection from severe findings
- Suspect scoring: proximity + frequency + bridge + role
- Ranked investigation queue with explanations

### Feature: Experiment Comparison
- Baseline vs intervention on same scenario dataset
- Pattern impact change metrics
- New pattern detection
- Side-effect monitoring (review rate, cost, latency)

### Feature: CLI & Dashboard
- Typer CLI with 10+ commands
- Streamlit multi-page dashboard (5 pages)
- Markdown report export

## Acceptance Criteria

### MVP Acceptance
- [ ] AC-1: `macrotrace init` creates SQLite DB with all tables
- [ ] AC-2: `macrotrace scenarios generate --count 200` produces 200 scenario JSONL records across 8 case types
- [ ] AC-3: `macrotrace runs execute` produces normalized trace events for every run
- [ ] AC-4: At least 5 deterministic evaluators produce stored EvalFindings per run
- [ ] AC-5: `macrotrace documents build` renders every run into a compact trace document
- [ ] AC-6: `macrotrace patterns discover` identifies non-noise clusters from seeded faults
- [ ] AC-7: Patterns are ranked by impact score (prevalence × severity)
- [ ] AC-8: Dashboard exposes representative traces behind each pattern
- [ ] AC-9: `macrotrace diagnose` produces ranked suspect list for selected pattern
- [ ] AC-10: `macrotrace compare` shows pattern change metrics between baseline and intervention
- [ ] AC-11: `macrotrace report export` produces Markdown with trace identifiers
- [ ] AC-12: Full pipeline runs without any API key (uses JSONL import + seeded data)
- [ ] AC-13: CI passes (ruff format --check, ruff check, mypy, pytest --cov > 80%)

### Research Validity Acceptance
- [ ] RV-1: Given an injected routing/policy defect and sufficient affected scenarios, top-3 ranked patterns contain a semantically accurate description of the injected defect
- [ ] RV-2: Graph diagnosis includes the responsible agent/tool/handoff within top-3 inspection targets
