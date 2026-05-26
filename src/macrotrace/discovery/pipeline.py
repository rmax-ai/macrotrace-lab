"""Embedding-based behavior pattern discovery pipeline."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Protocol

import numpy as np
import structlog
from sqlmodel import Session

from macrotrace.db import (
    create_behavior_pattern,
    get_scenario,
    get_session,
    list_behavior_patterns,
    list_eval_findings,
    list_runs,
    list_trace_events,
)
from macrotrace.documents import DOCUMENT_SCHEMA_VERSION, TraceDocumentBuilder
from macrotrace.exceptions import DiscoveryError
from macrotrace.schemas.eval import EvalFinding
from macrotrace.schemas.pattern import BehaviorPattern
from macrotrace.schemas.scenario import Scenario
from macrotrace.schemas.trace import Run, TraceEvent

logger = structlog.get_logger(__name__)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "approved",
    "case",
    "ended",
    "experiment",
    "for",
    "if",
    "in",
    "is",
    "n",
    "na",
    "no",
    "of",
    "or",
    "review",
    "run",
    "scenario",
    "severity",
    "the",
    "to",
    "via",
    "with",
}


@dataclass(frozen=True)
class PatternLabel:
    """Generated label metadata for a discovered cluster."""

    cluster_id: int
    label: str
    keywords: list[str]
    label_quality: float


@dataclass
class PatternResult:
    """In-memory representation of a discovered behavior pattern."""

    cluster_id: int
    label: str
    keywords: list[str]
    label_quality: float
    trace_count: int
    prevalence_share: float
    severity_weighted_prevalence: float
    impact_score: float
    max_severities: list[float]
    run_ids: list[str]
    representative_run_ids: list[str]
    dominant_case_type: str | None
    dominant_finding_type: str | None


class DocumentStore:
    """Load and build discovery documents from persisted workflow artifacts."""

    def __init__(self, include_all: bool = False) -> None:
        """Initialize the store with run inclusion behavior."""

        self.include_all = include_all

    def get_experiment_traces(
        self,
        session: Session,
        experiment_id: str,
    ) -> list[tuple[Run, Scenario, list[TraceEvent], list[EvalFinding]]]:
        """Load runs, scenarios, events, and findings for one experiment."""

        loaded: list[tuple[Run, Scenario, list[TraceEvent], list[EvalFinding]]] = []
        for run in list_runs(session, experiment_id=experiment_id):
            findings = list_eval_findings(session, run_id=run.run_id)
            failing_findings = [finding for finding in findings if not finding.passed]
            if not self.include_all and not failing_findings:
                continue
            scenario = get_scenario(session, run.scenario_id)
            events = list_trace_events(session, run_id=run.run_id)
            loaded.append((run, scenario, events, findings))
        return loaded

    def build_document_text(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
        findings: Sequence[EvalFinding],
        builder: TraceDocumentBuilder,
    ) -> tuple[str, float]:
        """Build one trace document and return its text plus max failing severity."""

        document_text = builder.build(run=run, scenario=scenario, events=events, findings=findings)
        failing_findings = [finding for finding in findings if not finding.passed]
        max_severity = float(max((finding.severity for finding in failing_findings), default=0))
        return document_text, max_severity


class TextEmbedder:
    """Sentence-transformers wrapper with process-local model caching."""

    class _SentenceTransformerLike(Protocol):
        """Protocol for the encode interface used by the embedder."""

        def encode(
            self,
            texts: list[str],
            *,
            convert_to_numpy: bool,
            show_progress_bar: bool,
        ) -> np.ndarray: ...

    _MODEL_CACHE: ClassVar[dict[str, _SentenceTransformerLike]] = {}

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the embedder."""

        self.model_name = model_name

    @classmethod
    def _get_model(cls, model_name: str) -> _SentenceTransformerLike:
        """Load or reuse a cached sentence-transformer model."""

        if model_name not in cls._MODEL_CACHE:
            from sentence_transformers import SentenceTransformer

            cls._MODEL_CACHE[model_name] = SentenceTransformer(model_name)
        return cls._MODEL_CACHE[model_name]

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed trace documents as float32 vectors."""

        logger.info("embedding_documents_started", count=len(texts), model_name=self.model_name)
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        model = self._get_model(self.model_name)
        embeddings = np.asarray(
            model.encode(texts, convert_to_numpy=True, show_progress_bar=False),
            dtype=np.float32,
        )
        logger.info(
            "embedding_documents_completed",
            count=len(texts),
            model_name=self.model_name,
            dimensions=int(embeddings.shape[1]),
        )
        return embeddings


class DimensionalityReducer:
    """UMAP wrapper for deterministic dimensionality reduction."""

    def reduce(
        self,
        embeddings: np.ndarray,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        n_components: int = 2,
        random_state: int = 42,
    ) -> np.ndarray:
        """Reduce high-dimensional embeddings with UMAP."""

        if embeddings.size == 0:
            return np.zeros((0, n_components), dtype=np.float32)
        if embeddings.shape[0] == 1:
            return np.zeros((1, n_components), dtype=np.float32)

        import umap

        reducer = umap.UMAP(
            n_neighbors=min(n_neighbors, embeddings.shape[0] - 1),
            min_dist=min_dist,
            n_components=n_components,
            random_state=random_state,
        )
        reduced = reducer.fit_transform(embeddings)
        return np.asarray(reduced, dtype=np.float32)


class ClusterEngine:
    """HDBSCAN wrapper for density-based clustering."""

    def cluster(
        self,
        embeddings_2d: np.ndarray,
        min_cluster_size: int = 5,
        min_samples: int | None = None,
        prediction_data: bool = True,
    ) -> np.ndarray:
        """Cluster reduced embeddings and return cluster labels."""

        if embeddings_2d.size == 0:
            return np.zeros((0,), dtype=np.int64)
        if embeddings_2d.shape[0] == 1:
            return np.asarray([0], dtype=np.int64)

        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            prediction_data=prediction_data,
        )
        return np.asarray(clusterer.fit_predict(embeddings_2d), dtype=np.int64)


class KeywordExtractor:
    """Cluster label generator based on simple c-TF-IDF keyword scoring."""

    def extract_labels(self, documents: list[str], labels: np.ndarray) -> list[PatternLabel]:
        """Generate top keyword labels for each non-noise cluster."""

        grouped_documents: dict[int, list[str]] = defaultdict(list)
        for document, label in zip(documents, labels.tolist(), strict=True):
            if label == -1:
                continue
            grouped_documents[int(label)].append(document)

        global_counts: Counter[str] = Counter()
        cluster_counts: dict[int, Counter[str]] = {}
        for cluster_id, cluster_documents in grouped_documents.items():
            counts: Counter[str] = Counter()
            for document in cluster_documents:
                counts.update(_tokenize(document))
            cluster_counts[cluster_id] = counts
            global_counts.update(counts)

        pattern_labels: list[PatternLabel] = []
        for cluster_id, counts in sorted(cluster_counts.items()):
            scored_terms = [
                (term, count / global_counts[term])
                for term, count in counts.items()
                if global_counts[term] > 0
            ]
            scored_terms.sort(key=lambda item: (-item[1], -counts[item[0]], item[0]))
            top_terms = scored_terms[:3]
            keywords = [term for term, _score in top_terms]
            label_quality = float(sum(score for _term, score in top_terms))
            label = "/".join(keywords) if keywords else "unlabeled-pattern"
            pattern_labels.append(
                PatternLabel(
                    cluster_id=cluster_id,
                    label=label,
                    keywords=keywords,
                    label_quality=label_quality,
                )
            )

        return pattern_labels


class ImpactRanker:
    """Compute impact metrics and rank patterns."""

    def rank(self, patterns: list[PatternResult]) -> list[PatternResult]:
        """Update impact metrics and return patterns sorted by impact score."""

        total_traces = sum(pattern.trace_count for pattern in patterns)
        if total_traces == 0:
            return patterns

        for pattern in patterns:
            prevalence_share = pattern.trace_count / total_traces
            mean_severity = (
                float(np.mean(np.asarray(pattern.max_severities, dtype=np.float32)))
                if pattern.max_severities
                else 0.0
            )
            severity_weighted_prevalence = mean_severity * prevalence_share
            pattern.prevalence_share = prevalence_share
            pattern.severity_weighted_prevalence = severity_weighted_prevalence
            pattern.impact_score = prevalence_share * severity_weighted_prevalence

        return sorted(
            patterns,
            key=lambda pattern: (-pattern.impact_score, -pattern.trace_count, pattern.cluster_id),
        )


def discover_patterns(
    experiment_id: str | None = None,
    include_all: bool = False,
    *,
    experiment: str | None = None,
) -> list[PatternResult]:
    """Discover and persist behavior patterns for an experiment."""

    resolved_experiment_id = experiment_id or experiment
    if resolved_experiment_id is None:
        raise DiscoveryError("discover_patterns requires an experiment identifier.")

    store = DocumentStore(include_all=include_all)
    builder = TraceDocumentBuilder(document_schema_version=DOCUMENT_SCHEMA_VERSION)
    embedder = TextEmbedder()
    reducer = DimensionalityReducer()
    cluster_engine = ClusterEngine()
    extractor = KeywordExtractor()
    ranker = ImpactRanker()

    with get_session() as session:
        trace_rows = store.get_experiment_traces(session, resolved_experiment_id)
        if not trace_rows:
            logger.info(
                "pattern_discovery_completed",
                experiment_id=resolved_experiment_id,
                trace_count=0,
                pattern_count=0,
                include_all=include_all,
            )
            return []

        documents: list[str] = []
        max_severities: list[float] = []
        runs: list[Run] = []
        scenarios: list[Scenario] = []
        findings_by_run: list[list[EvalFinding]] = []

        for run, scenario, events, findings in trace_rows:
            document_text, max_severity = store.build_document_text(
                run=run,
                scenario=scenario,
                events=events,
                findings=findings,
                builder=builder,
            )
            documents.append(document_text)
            max_severities.append(max_severity)
            runs.append(run)
            scenarios.append(scenario)
            findings_by_run.append(findings)

        embeddings = embedder.embed(documents)
        reduced_embeddings = reducer.reduce(embeddings)
        labels = cluster_engine.cluster(reduced_embeddings)
        pattern_labels = {
            label.cluster_id: label for label in extractor.extract_labels(documents, labels)
        }
        patterns = _build_pattern_results(
            runs=runs,
            scenarios=scenarios,
            findings_by_run=findings_by_run,
            labels=labels,
            reduced_embeddings=reduced_embeddings,
            max_severities=max_severities,
            pattern_labels=pattern_labels,
        )
        ranked_patterns = ranker.rank(patterns)
        existing_pattern_ids = {
            pattern.pattern_id
            for pattern in list_behavior_patterns(session, experiment_id=resolved_experiment_id)
        }

        for pattern in ranked_patterns:
            pattern_id = _build_pattern_id(
                experiment_id=resolved_experiment_id,
                cluster_id=pattern.cluster_id,
                existing_pattern_ids=existing_pattern_ids,
            )
            existing_pattern_ids.add(pattern_id)
            create_behavior_pattern(
                session,
                BehaviorPattern(
                    pattern_id=pattern_id,
                    experiment_id=resolved_experiment_id,
                    cluster_id=pattern.cluster_id,
                    label=pattern.label,
                    keywords=pattern.keywords,
                    trace_count=pattern.trace_count,
                    prevalence_share=pattern.prevalence_share,
                    severity_weighted_prevalence=pattern.severity_weighted_prevalence,
                    impact_score=pattern.impact_score,
                    dominant_case_type=pattern.dominant_case_type,
                    dominant_finding_type=pattern.dominant_finding_type,
                    dominant_owner=None,
                    representative_run_ids=pattern.representative_run_ids,
                ),
            )

        logger.info(
            "pattern_discovery_completed",
            experiment_id=resolved_experiment_id,
            trace_count=len(documents),
            pattern_count=len(ranked_patterns),
            include_all=include_all,
            patterns=[
                {
                    "cluster_id": pattern.cluster_id,
                    "label": pattern.label,
                    "trace_count": pattern.trace_count,
                    "impact_score": pattern.impact_score,
                }
                for pattern in ranked_patterns
            ],
        )
        return ranked_patterns


def _build_pattern_results(
    *,
    runs: Sequence[Run],
    scenarios: Sequence[Scenario],
    findings_by_run: Sequence[Sequence[EvalFinding]],
    labels: np.ndarray,
    reduced_embeddings: np.ndarray,
    max_severities: Sequence[float],
    pattern_labels: dict[int, PatternLabel],
) -> list[PatternResult]:
    """Aggregate per-trace metadata into per-cluster pattern results."""

    cluster_indices: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels.tolist()):
        if label == -1:
            continue
        cluster_indices[int(label)].append(index)

    patterns: list[PatternResult] = []
    for cluster_id, indices in sorted(cluster_indices.items()):
        case_types = [scenarios[index].case_type for index in indices]
        finding_types = [
            finding.finding_type.value
            for index in indices
            for finding in findings_by_run[index]
            if not finding.passed
        ]
        representative_run_ids = _representative_run_ids(
            cluster_embeddings=reduced_embeddings[indices],
            run_ids=[runs[index].run_id for index in indices],
        )
        label = pattern_labels.get(
            cluster_id,
            PatternLabel(
                cluster_id=cluster_id,
                label=f"cluster-{cluster_id}",
                keywords=[],
                label_quality=0.0,
            ),
        )
        patterns.append(
            PatternResult(
                cluster_id=cluster_id,
                label=label.label,
                keywords=label.keywords,
                label_quality=label.label_quality,
                trace_count=len(indices),
                prevalence_share=0.0,
                severity_weighted_prevalence=0.0,
                impact_score=0.0,
                max_severities=[max_severities[index] for index in indices],
                run_ids=[runs[index].run_id for index in indices],
                representative_run_ids=representative_run_ids,
                dominant_case_type=_most_common_or_none(case_types),
                dominant_finding_type=_most_common_or_none(finding_types),
            )
        )

    return patterns


def _representative_run_ids(cluster_embeddings: np.ndarray, run_ids: list[str]) -> list[str]:
    """Return up to five run identifiers closest to a cluster centroid."""

    if len(run_ids) <= 5:
        return run_ids

    centroid = np.mean(cluster_embeddings, axis=0)
    distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
    ranked_indices = np.argsort(distances)
    return [run_ids[int(index)] for index in ranked_indices[:5]]


def _most_common_or_none(values: Sequence[str]) -> str | None:
    """Return the most common string with deterministic tie-breaking."""

    if not values:
        return None
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _tokenize(text: str) -> list[str]:
    """Tokenize a document into lowercase keyword candidates."""

    tokens = [
        token
        for token in _TOKEN_PATTERN.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS and not token.isdigit()
    ]
    return tokens


def _build_pattern_id(
    *,
    experiment_id: str,
    cluster_id: int,
    existing_pattern_ids: set[str],
) -> str:
    """Build a pattern identifier that does not collide with existing records."""

    base_pattern_id = f"{experiment_id}-pattern-{cluster_id}"
    if base_pattern_id not in existing_pattern_ids:
        return base_pattern_id

    suffix = 2
    while f"{base_pattern_id}-{suffix}" in existing_pattern_ids:
        suffix += 1
    return f"{base_pattern_id}-{suffix}"
