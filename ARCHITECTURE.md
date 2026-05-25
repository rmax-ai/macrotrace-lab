# MacroTrace Lab — Architecture

## Problem Statement

Run-level evals can identify whether a single agent execution failed. They do not answer: *Which failure behaviours recur across many runs? Which agent, tool, handoff, or policy is repeatedly involved? Which defect should I investigate first?*

MacroTrace Lab converts agent traces into a population-level research object — discovering recurring behaviour patterns, ranking them by operational impact, and diagnosing upstream inspection targets.

## Design Goals

1. **Reproducibility:** Same traces + same config = same patterns. Fully seed-controlled pipeline.
2. **Adapter isolation:** All agent frameworks produce the same normalized trace schema. Swap frameworks without changing the eval pipeline.
3. **Local-first:** Run on a laptop with SQLite and local embeddings. No hosted services required for core analysis.
4. **Verifiable:** Every chart and metric traceable to stored rows. No black-box scores.
5. **Cautious diagnosis:** Suspect scores are prioritization heuristics, not causal claims.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Workflow Runtime                                │
│  ┌──────────┐  ┌────────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ Scenario │  │  Workflow      │  │ Specialist │  │  Simulated  │  │
│  │ Generator│──▶│  Runner        │──▶│ Agents     │──▶│  Tools      │  │
│  └──────────┘  └────────────────┘  └────────────┘  └─────────────┘  │
│                                 │                                    │
│                          ┌──────▼──────┐                            │
│                          │  Trace      │                            │
│                          │  Adapter    │                            │
│                          └──────┬──────┘                            │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
              ┌─────▼─────┐ ┌────▼────┐ ┌──────▼──────┐
              │ Raw Trace │ │ SQLite  │ │  Eval       │
              │ JSONL     │ │         │ │  Labels     │
              └───────────┘ └─────────┘ └─────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      Evaluation Pipeline                              │
│                                                                      │
│  Raw Traces ──▶ Normalizer ──▶ Eval Engine ──▶ Doc Builder          │
│                                                      │               │
│                                                      ▼               │
│                                              Embedding Service       │
│                                                      │               │
│                                                      ▼               │
│                                          UMAP ──▶ HDBSCAN            │
│                                                      │               │
│                                                      ▼               │
│                                           c-TF-IDF Keywords          │
│                                                      │               │
│                                                      ▼               │
│                                              Impact Ranking          │
│                                                      │               │
│                                                      ▼               │
│                                            Graph Diagnosis           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Research Interface                               │
│                                                                      │
│  ┌──────────┐    ┌──────────────────┐    ┌────────────────────┐      │
│  │   CLI    │    │  Streamlit       │    │  Markdown Report   │      │
│  │  (Typer) │    │  Dashboard       │    │  Export            │      │
│  └──────────┘    └──────────────────┘    └────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Full Experiment Loop
```
Scenario Dataset ──▶ Workflow Runner ──▶ Trace Capture ──▶ Run Normalization
    ──▶ Lower-Level Evals ──▶ Trace Document ──▶ Pattern Discovery
    ──▶ Impact Ranking ──▶ Graph Diagnosis ──▶ Human Review ──▶ Intervention
```

## Module Layout

```
src/macrotrace/
├── cli.py              Typer CLI (thin dispatch)
├── config.py           Pydantic Settings + YAML config
├── db.py               SQLModel engine + session
├── schemas/            Pure Pydantic models (trace, scenario, eval, pattern, experiment)
├── runtime/            Workflow runner, agents, tools, fault injection
├── adapters/           TraceAdapter Protocol + framework implementations
├── tracing/            Normalization, collection, redaction
├── evals/              Deterministic + optional LLM evaluators
├── documents/          Trace document builder
├── discovery/          Embedding, UMAP, HDBSCAN, labeling, ranking
├── diagnosis/          NetworkX graph builder, suspect scoring
├── reporting/          Markdown report + Plotly charts
└── ui/                 Streamlit multi-page app
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Adapter-based runtime | Any agent framework can be ingested; framework-specific code is isolated |
| Embeddings + clustering over rule-based | Discovers patterns the author didn't anticipate; follows OpenAI cookbook approach |
| Local sentence-transformers | Free, deterministic, no API calls needed for core discovery |
| SQLite + SQLModel | Zero-config, portable, inspectable with any SQLite viewer |
| CLI-first, Streamlit second | Batch analysis is the primary workflow; dashboard is for exploration |
| JSONL as interchange format | Universal, inspectable, diffable, no binary dependencies |
| Deterministic evals before LLM judges | MVP reliability; LLM judges are optional add-ons |
| Impact = prevalence × severity | Reproduces cookbook's explainable triage heuristic |

## Trade-offs

| Choice | Trade-off |
|--------|-----------|
| all-MiniLM-L6-v2 | Fast/lightweight but less semantic nuance than larger models |
| UMAP + HDBSCAN | Proven for text clustering but sensitive to parameters |
| Single-process batch | Simple and debuggable; not for 100K+ run datasets |
| Frozen Pydantic models | Immutability guarantees but requires explicit construction patterns |
| Streamlit | Fastest path to interactive UI; limited customization vs. React |
