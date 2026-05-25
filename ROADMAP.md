# Roadmap

## v0.1.0 — MVP (Current)

- [ ] Pydantic schemas for all domain models (trace, scenario, eval, pattern, experiment)
- [ ] SQLite database with SQLModel migrations
- [ ] CLI skeleton with `init`, `scenarios generate`, `runs execute`, `evals run`, `patterns discover`, `diagnose`, `compare`, `ui`, `report export`
- [ ] Reference procurement workflow with 6 specialist agents
- [ ] Synthetic scenario generator (8 case types, 300 scenarios)
- [ ] OpenAI Agents SDK trace adapter (live tracing)
- [ ] JSONL trace import adapter (API-key-free development)
- [ ] 5 deterministic evaluators (outcome correctness, required agents, review gate, forbidden approval, tool failure handling)
- [ ] Trace document builder (compact semantic compression)
- [ ] Local embedding service (sentence-transformers/all-MiniLM-L6-v2)
- [ ] UMAP + HDBSCAN clustering pipeline
- [ ] c-TF-IDF keyword extraction and label generation
- [ ] Impact ranking (prevalence × severity)
- [ ] NetworkX graph diagnosis with suspect scoring
- [ ] Experiment comparison (baseline vs intervention)
- [ ] Streamlit dashboard (5 pages: overview, pattern leaderboard, trace map, diagnosis, comparison)
- [ ] Markdown report export
- [ ] Fault injection system (configurable defects)
- [ ] Seeded example data for API-key-free demo
- [ ] CI pipeline (ruff, mypy, pytest, coverage)

## v0.2.0 — Enhancement

- [ ] LLM judge evaluators (decision grounding, trace coherence)
- [ ] LLM-assisted pattern label generation
- [ ] Pattern filtering and drill-down in dashboard
- [ ] Trace search and filtering by event type, agent, tool
- [ ] Export to shareable HTML reports (instead of just Markdown)
- [ ] Configurable embedding model (swap all-MiniLM-L6-v2 for larger model)
- [ ] Run trace validation command
- [ ] Human notes field on patterns and suspects

## v0.3.0 — Multi-Framework

- [ ] Google ADK trace adapter
- [ ] LangGraph trace adapter
- [ ] Custom MCP harness log adapter
- [ ] Cross-framework experiment comparison
- [ ] Performance benchmarking (latency, cost per framework)

## Future

- [ ] Outcome-linked scoring (researcher time saved, policy exposure, risk)
- [ ] Policy regression suites (auto-convert confirmed patterns into deterministic tests)
- [ ] Knowledge-layer diagnostics (missing docs, stale retrieval, metadata issues)
- [ ] Gateway-aware evaluation (identity, permissions, approval gates, audit)
- [ ] Multi-framework comparative research UI
- [ ] Streaming trace ingestion
- [ ] OpenTelemetry integration (receive traces via OTLP)
