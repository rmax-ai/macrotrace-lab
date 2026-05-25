# Decisions

## Major Assumptions

1. Agent traces from a single workflow type (procurement review) generalize to other workflow types.
2. 50–2,000 runs per experiment is sufficient for meaningful pattern discovery.
3. Local sentence-transformers embeddings capture enough semantics for useful behavioral clustering.
4. Deterministic evals cover the most important failure modes; LLM judges are optional amplification.
5. A single developer laptop can run the full pipeline without cloud services.

## Architecture Decisions

### Adapter pattern for runtime abstraction
**Chosen:** `TraceAdapter` Protocol that normalizes framework-native events into `TraceEvent`.
**Why:** Prevents coupling to any single agent framework. The OpenAI Agents SDK adapter is the first implementation; JSONL import provides an API-key-free development path.
**Rejected:** Direct coupling to OpenAI SDK event types throughout the pipeline.

### Embedding + clustering over rule-based pattern discovery
**Chosen:** BERTopic-style pipeline: sentence-transformers → UMAP → HDBSCAN → c-TF-IDF.
**Why:** The cookbook demonstrates this discovers patterns the author didn't hardcode. Rule-based approaches can't find unexpected recurring behaviors.
**Rejected:** Regex patterns, keyword matching, manual classification.

### Local embedding model (all-MiniLM-L6-v2)
**Chosen:** `sentence-transformers/all-MiniLM-L6-v2` — 384-dim, ~80MB, runs on CPU.
**Why:** Free, deterministic, no API key needed. Large enough for 2,000 documents.
**Rejected:** OpenAI embeddings (API cost, non-deterministic, requires internet), larger local models (slower, more RAM).

### Impact score = prevalence × severity-weighted prevalence
**Chosen:** Direct reproduction of the cookbook's triage formula.
**Why:** Explainable, verifiable, and matches the research paper's methodology. A single composite score for ranking.
**Rejected:** ML-based ranking (black-box), simple count ranking (ignores severity).

### SQLite + SQLModel
**Chosen:** SQLite with WAL mode, SQLModel for ORM-like access.
**Why:** Zero configuration, portable database file, SQLModel provides type-safe queries. SQLite handles the MVP's data volume easily.
**Rejected:** PostgreSQL (operational overhead), DuckDB (columnar not needed for transactional access), raw SQL (no type safety).

### Typer over Click/argparse
**Chosen:** Typer with automatic `--help` generation and type-based argument parsing.
**Why:** Pydantic-compatible type system, auto-generated help, less boilerplate than Click, much less than argparse.
**Rejected:** Click (more verbose for simple commands), argparse (manual help strings).

### CLI-first, Streamlit second
**Chosen:** CLI as the primary interface for batch analysis; Streamlit for interactive exploration.
**Why:** The core workflow is parameterized batch execution. Dashboard is for browsing results, not running experiments.
**Rejected:** Web-only (requires server), Jupyter notebook as primary (not scriptable).

### Deterministic evals before LLM judges
**Chosen:** Five mandatory deterministic evaluators cover the MVP's key correctness checks. LLM judges are optional.
**Why:** Deterministic = reliable, fast, zero cost, versionable. LLM judges add capability but also cost, latency, and non-determinism.
**Rejected:** LLM-only evaluation (unreliable, expensive, not reproducible).

### JSONL for data interchange
**Chosen:** All trace, scenario, finding, and document data in JSONL format.
**Why:** Human-readable, diffable, processable line-by-line, no schema registry needed. Standard in ML eval tooling.
**Rejected:** Parquet (binary, harder to debug), SQL dumps (tool-dependent), pickle (dangerous).

### structlog over standard logging
**Chosen:** structlog with JSON output and context variable merging.
**Why:** Structured logs that can be machine-parsed. Context vars (run_id, experiment_id) automatically attached.
**Rejected:** Standard logging (stringly-typed, open to abuse), loguru (vendor lock-in).

### Frozen immutability for domain models
**Chosen:** All Pydantic schemas use `model_config = {"frozen": True}`.
**Why:** Domain models should not be mutated after creation. Prevents accidental corruption of trace data.
**Rejected:** Mutable models (risk of accidental mutation in large pipelines).

## Known Limitations

- all-MiniLM-L6-v2 has 384-dim embeddings — fine for 2K documents, may be insufficient for 50K+.
- UMAP + HDBSCAN parameters are sensitive. Defaults work for prototype but need tuning for production datasets.
- Single-process batch execution limits throughput. No distributed runner.
- Trace documents in English only. Non-English traces may cluster differently.
- No streaming support — all traces loaded into memory for analysis.
- LLM judge dependency on OpenAI API key (optional, but blocks that feature path).
- The data/ directory is not encrypted. Synthetic data only in MVP.
