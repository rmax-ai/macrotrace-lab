# PYTHON_SYSTEM_DESIGN_PATTERNS.md — Architecture Patterns for MacroTrace Lab

## Architectural Patterns

### Adapter Pattern (Framework Abstraction)
The core architectural pattern — all agent frameworks produce the same normalized `TraceEvent` schema.

```python
from typing import Protocol, Any
from macrotrace.schemas.trace import TraceEvent, RawTrace

class TraceAdapter(Protocol):
    """Adapter interface for any agent framework trace source."""
    def normalize(self, raw_trace: RawTrace) -> list[TraceEvent]:
        """Convert a framework-native trace into normalized TraceEvents."""
        ...

class JsonlImportAdapter:
    """Adapter for importing pre-recorded traces from JSONL."""
    def normalize(self, raw_trace: RawTrace) -> list[TraceEvent]:
        raw_events = raw_trace.payload["events"]
        return [TraceEvent(**e) for e in raw_events]

class OpenAIAgentsAdapter:
    """Adapter for OpenAI Agents SDK traces."""
    def normalize(self, raw_trace: RawTrace) -> list[TraceEvent]:
        # Transform OpenAI SDK span events → TraceEvent
        ...
```

### Pipeline Pattern (Evaluation Pipeline)
The evaluation pipeline is a linear transformation chain. Each stage takes input from the previous and passes results forward.

```python
from dataclasses import dataclass, field

@dataclass
class EvalContext:
    run: "Run"
    scenario: "Scenario"
    events: list["TraceEvent"]
    findings: list["EvalFinding"] = field(default_factory=list)

class EvalPipeline:
    def __init__(self, evaluators: list["BaseEvaluator"]):
        self.evaluators = evaluators

    def run(self, ctx: EvalContext) -> EvalContext:
        for evaluator in self.evaluators:
            finding = evaluator.evaluate(ctx.run, ctx.scenario, ctx.events)
            ctx.findings.append(finding)
        return ctx
```

### Document Builder Pattern (Semantic Compression)
Transforms a trace + findings into a compact representation for clustering. This is a deterministic, versioned transformation.

```python
class TraceDocumentBuilder:
    """Builds compact semantic documents from traces and eval findings."""

    def __init__(self, schema_version: str = "1.0.0"):
        self.schema_version = schema_version

    def build(self, run: Run, scenario: Scenario, events: list[TraceEvent],
              findings: list[EvalFinding]) -> str:
        # Compose document string using controlled vocabulary
        # See trace-document specification (SPEC section 11)
        ...
```

### Strategy Pattern (Evaluators)
Each evaluator is a pluggable strategy with a common interface.

```python
class BaseEvaluator(ABC):
    """Base class for all run-level evaluators."""
    name: str
    version: str

    @abstractmethod
    def evaluate(self, run: Run, scenario: Scenario,
                 events: list[TraceEvent]) -> EvalFinding:
        ...

class ReviewGateEval(BaseEvaluator):
    name = "review_gate"
    version = "1.0.0"

    def evaluate(self, run, scenario, events) -> EvalFinding:
        required = scenario.ground_truth.get("must_trigger_review", False)
        observed = any(e.event_type == "review_requested" for e in events)
        if required and not observed:
            return EvalFinding(finding_type="missing_review", passed=False, ...)
        return EvalFinding(finding_type="missing_review", passed=True, ...)
```

### Repository Pattern (Data Access)
Abstracted data access behind a repository interface.

```python
class ExperimentRepository:
    """Data access for experiments, runs, traces, findings."""

    def __init__(self, db: Database):
        self.db = db

    def get_experiment(self, experiment_id: str) -> Experiment | None: ...
    def get_runs(self, experiment_id: str) -> list[Run]: ...
    def save_findings(self, findings: list[EvalFinding]): ...
    def get_patterns(self, experiment_id: str) -> list[BehaviorPattern]: ...
```

## Domain-Specific Patterns

### Discovery Pipeline (BERTopic-style)
```python
@dataclass
class DiscoveryPipeline:
    embedding_service: EmbeddingService
    reducer: UMAPReducer
    clusterer: HDBSCANClusterer
    labeler: PatternLabeler
    ranker: PatternRanker

    def discover(self, documents: list[str],
                 run_metadata: dict) -> list[BehaviorPattern]:
        vectors = self.embedding_service.encode(documents)
        reduced = self.reducer.fit_transform(vectors)
        cluster_ids = self.clusterer.fit_predict(reduced)
        keywords = self.labeler.compute_keywords(documents, cluster_ids)
        patterns = self.labeler.build_patterns(documents, cluster_ids, keywords, run_metadata)
        return self.ranker.rank(patterns)
```

### Diagnosis Graph Pipeline
```python
@dataclass
class DiagnosisPipeline:
    graph_builder: TraceGraphBuilder
    suspect_scorer: SuspectScorer

    def diagnose(self, pattern: BehaviorPattern,
                 runs: list[Run], events: dict[str, list[TraceEvent]],
                 findings: list[EvalFinding]) -> list[DiagnosisSuspect]:
        graph = self.graph_builder.build_combined_graph(runs, events, findings)
        anchors = self.graph_builder.select_anchors(findings)
        suspects = self.suspect_scorer.score(graph, anchors)
        return sorted(suspects, key=lambda s: s.suspect_score, reverse=True)
```

### Experiment Comparison
```python
@dataclass
class ExperimentComparator:
    def compare(self, baseline: ExperimentResult,
                candidate: ExperimentResult) -> ComparisonReport:
        return ComparisonReport(
            target_pattern_change=self._pattern_delta(baseline, candidate),
            new_patterns=self._new_patterns(baseline, candidate),
            resolved_patterns=self._resolved_patterns(baseline, candidate),
            outcome_shift=self._outcome_distribution_shift(baseline, candidate),
            review_rate_change=self._rate_change(baseline.review_rate, candidate.review_rate),
        )
```

## Concurrency Patterns

### Batch Runner with ThreadPool
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def execute_batch(scenarios: list[Scenario], config: ExperimentConfig,
                  max_concurrency: int = 10) -> list[Run]:
    results = []
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        futures = {
            executor.submit(execute_single, scenario, config): scenario
            for scenario in scenarios
        }
        with tqdm(total=len(futures)) as pbar:
            for future in as_completed(futures):
                results.append(future.result())
                pbar.update(1)
    return results
```

### Checkpointing
```python
def execute_batch_with_checkpoint(scenarios, config, checkpoint_path: Path):
    completed = _load_checkpoint(checkpoint_path)
    remaining = [s for s in scenarios if s.scenario_id not in completed]
    for scenario in remaining:
        run = execute_single(scenario, config)
        completed.add(scenario.scenario_id)
        _save_checkpoint(checkpoint_path, completed)
```

## Anti-Patterns for This Project

### ❌ Shared mutable state across pipeline stages
Each pipeline stage is a transformation. Do not mutate inputs.

### ❌ Heavy framework dependencies
Prefer lightweight libraries. SQLModel over SQLAlchemy ORM, Typer over Click, structlog over loguru.

### ❌ Premature async
Synchronous Python is simpler, debuggable, and sufficient for local batch workloads. Add async only when the FastAPI REST API is needed.

### ❌ Coupling to OpenAI SDK
The adapter pattern is critical. Every agent framework goes through `TraceAdapter.normalize()`. No framework-specific code outside the adapters package.

### ❌ Magic numbers in clustering
All UMAP and HDBSCAN parameters must be documented and configurable in experiment YAML. Never hardcode.

### ❌ Storing raw LLM responses in trace documents
Trace documents contain only evaluation-relevant semantic features. Raw outputs go in `data/traces/` only.
