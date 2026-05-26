from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
from sqlmodel import Session

import macrotrace.db as db_module
from macrotrace.db import (
    create_db_engine,
    create_eval_finding,
    create_experiment,
    create_run,
    create_scenario,
    create_trace_event,
    get_session,
    init_db,
    list_behavior_patterns,
)
from macrotrace.discovery.pipeline import (
    ClusterEngine,
    DimensionalityReducer,
    DocumentStore,
    ImpactRanker,
    KeywordExtractor,
    PatternResult,
    TextEmbedder,
    discover_patterns,
)
from macrotrace.schemas import (
    EvalFinding,
    EventType,
    Experiment,
    FindingType,
    Run,
    RunOutcome,
    Scenario,
    TraceEvent,
)


def test_document_store_loads_experiment_traces(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "macrotrace.db")
    init_db(engine)

    with get_session(engine) as session:
        run = _seed_run_bundle(session, experiment_id="experiment-1", run_id="run-1")
        rows = DocumentStore(include_all=True).get_experiment_traces(session, "experiment-1")

    assert len(rows) == 1
    loaded_run, scenario, events, findings = rows[0]
    assert loaded_run.run_id == run.run_id
    assert scenario.scenario_id == run.scenario_id
    assert [event.event_id for event in events] == ["run-1-event-1", "run-1-event-2"]
    assert [finding.finding_id for finding in findings] == ["run-1-finding-1"]


def test_document_store_filters_include_all_false(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "macrotrace.db")
    init_db(engine)

    with get_session(engine) as session:
        _seed_run_bundle(session, experiment_id="experiment-1", run_id="run-failing", passed=False)
        _seed_run_bundle(session, experiment_id="experiment-1", run_id="run-passing", passed=True)
        rows = DocumentStore(include_all=False).get_experiment_traces(session, "experiment-1")

    assert [run.run_id for run, _scenario, _events, _findings in rows] == ["run-failing"]


def test_text_embedder_returns_correct_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(
            self,
            texts: list[str],
            *,
            convert_to_numpy: bool,
            show_progress_bar: bool,
        ) -> np.ndarray:
            assert convert_to_numpy is True
            assert show_progress_bar is False
            return np.ones((len(texts), 384), dtype=np.float64)

    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    TextEmbedder._MODEL_CACHE.clear()

    embeddings = TextEmbedder().embed(["one", "two", "three"])

    assert embeddings.shape == (3, 384)
    assert embeddings.dtype == np.float32


def test_dimensionality_reducer_returns_correct_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = ModuleType("umap")

    class FakeUMAP:
        def __init__(self, **_: object) -> None:
            pass

        def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:
            assert embeddings.shape == (3, 384)
            return np.asarray([[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]], dtype=np.float64)

    fake_module.UMAP = FakeUMAP
    monkeypatch.setitem(sys.modules, "umap", fake_module)

    reduced = DimensionalityReducer().reduce(np.ones((3, 384), dtype=np.float32))

    assert reduced.shape == (3, 2)
    assert reduced.dtype == np.float32


def test_cluster_engine_separates_distinct_clusters() -> None:
    pytest.importorskip("hdbscan")
    embeddings = np.asarray([[0.0, 0.0], [0.0, 1.0], [10.0, 0.0], [10.0, 1.0]], dtype=np.float32)

    labels = ClusterEngine().cluster(embeddings, min_cluster_size=2)

    non_noise_labels = sorted(set(labels.tolist()) - {-1})
    assert len(non_noise_labels) == 2
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]


def test_keyword_extractor_produces_labels() -> None:
    documents = [
        "routing failure budget threshold budget failure",
        "routing failure vendor risk failure",
        "review missing escalation review path",
    ]
    labels = np.asarray([0, 0, 1], dtype=np.int64)

    extracted = KeywordExtractor().extract_labels(documents, labels)

    assert [label.cluster_id for label in extracted] == [0, 1]
    assert all(label.keywords for label in extracted)
    assert all(label.label for label in extracted)
    assert all(label.label_quality > 0 for label in extracted)


def test_impact_ranker_sorts_by_score() -> None:
    patterns = [
        PatternResult(
            cluster_id=1,
            label="lower",
            keywords=["lower"],
            label_quality=1.0,
            trace_count=1,
            prevalence_share=0.0,
            severity_weighted_prevalence=0.0,
            impact_score=0.0,
            max_severities=[2.0],
            run_ids=["run-1"],
            representative_run_ids=["run-1"],
            dominant_case_type="clean_purchase",
            dominant_finding_type="routing_error",
        ),
        PatternResult(
            cluster_id=0,
            label="higher",
            keywords=["higher"],
            label_quality=1.0,
            trace_count=3,
            prevalence_share=0.0,
            severity_weighted_prevalence=0.0,
            impact_score=0.0,
            max_severities=[4.0, 4.0, 5.0],
            run_ids=["run-2", "run-3", "run-4"],
            representative_run_ids=["run-2", "run-3", "run-4"],
            dominant_case_type="vendor_risk_flag",
            dominant_finding_type="missing_review",
        ),
    ]

    ranked = ImpactRanker().rank(patterns)

    assert [pattern.cluster_id for pattern in ranked] == [0, 1]
    assert ranked[0].impact_score > ranked[1].impact_score


def test_discover_patterns_full_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_db_engine(tmp_path / "macrotrace.db")
    init_db(engine)
    monkeypatch.setattr(db_module, "ENGINE", engine)

    with get_session(engine) as session:
        _seed_run_bundle(
            session,
            experiment_id="experiment-1",
            run_id="run-1",
            case_type="budget_threshold",
            finding_type=FindingType.ROUTING_ERROR,
            severity=4,
            request_text="Budget approval failed due to threshold routing.",
        )
        _seed_run_bundle(
            session,
            experiment_id="experiment-1",
            run_id="run-2",
            case_type="budget_threshold",
            finding_type=FindingType.ROUTING_ERROR,
            severity=5,
            request_text="Budget escalation followed the same routing failure path.",
        )
        _seed_run_bundle(
            session,
            experiment_id="experiment-1",
            run_id="run-3",
            case_type="vendor_risk_flag",
            finding_type=FindingType.MISSING_REVIEW,
            severity=2,
            request_text="Vendor review was skipped despite a risk flag.",
        )

    monkeypatch.setattr(
        TextEmbedder,
        "embed",
        lambda _self, _texts: np.asarray(
            [[0.0, 0.1, 0.2], [0.0, 0.2, 0.1], [5.0, 5.1, 5.2]],
            dtype=np.float32,
        ),
    )
    monkeypatch.setattr(
        DimensionalityReducer,
        "reduce",
        lambda _self, _embeddings, **_: np.asarray(
            [[0.0, 0.0], [0.1, 0.1], [5.0, 5.0]],
            dtype=np.float32,
        ),
    )
    monkeypatch.setattr(
        ClusterEngine,
        "cluster",
        lambda _self, _embeddings_2d, **_: np.asarray([0, 0, 1], dtype=np.int64),
    )

    results = discover_patterns(experiment_id="experiment-1")

    with get_session(engine) as session:
        stored_patterns = list_behavior_patterns(session, experiment_id="experiment-1")

    assert len(results) == 2
    assert len(stored_patterns) == 2

    patterns_by_cluster = {pattern.cluster_id: pattern for pattern in stored_patterns}
    assert patterns_by_cluster[0].trace_count == 2
    assert patterns_by_cluster[0].dominant_case_type == "budget_threshold"
    assert patterns_by_cluster[0].dominant_finding_type == "routing_error"
    assert len(patterns_by_cluster[0].representative_run_ids) == 2
    assert patterns_by_cluster[1].trace_count == 1
    assert patterns_by_cluster[1].representative_run_ids == ["run-3"]
    assert all(pattern.keywords for pattern in stored_patterns)


def test_umap_reproducibility_with_seed() -> None:
    pytest.importorskip("umap")
    rng = np.random.default_rng(42)
    embeddings = rng.random((12, 8), dtype=np.float32)
    reducer = DimensionalityReducer()

    first = reducer.reduce(embeddings, random_state=42)
    second = reducer.reduce(embeddings, random_state=42)

    assert np.allclose(first, second)


def test_hdbscan_noise_label_is_minus_one() -> None:
    pytest.importorskip("hdbscan")
    embeddings = np.asarray([[0.0, 0.0], [100.0, 100.0], [200.0, 200.0]], dtype=np.float32)

    labels = ClusterEngine().cluster(embeddings, min_cluster_size=2)

    assert set(labels.tolist()) == {-1}


def _seed_run_bundle(
    session: Session,
    *,
    experiment_id: str,
    run_id: str,
    passed: bool = False,
    case_type: str = "clean_purchase",
    finding_type: FindingType = FindingType.ROUTING_ERROR,
    severity: int = 4,
    request_text: str = "Approve the purchase request.",
) -> Run:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    scenario = Scenario(
        scenario_id=f"{run_id}-scenario",
        dataset_id="dataset-1",
        case_type=case_type,
        request_text=request_text,
        expected_outcome="approved" if passed else "review_required",
        ground_truth={"must_trigger_review": not passed},
        environmental_signals={"vendor_risk": "high" if not passed else "low"},
        severity_if_mishandled=severity,
        tags=["test"],
    )
    experiment = Experiment(
        experiment_id=experiment_id,
        name="Discovery Test",
        created_at=now,
        workflow_name="reference_workflow",
        workflow_version="1.0.0",
        config_hash=f"hash-{experiment_id}",
        baseline_experiment_id=None,
        scenario_dataset_id="dataset-1",
        model_settings={"coordinator": "gpt-5.5"},
        agent_config={"specialists": ["policy"]},
        fault_injections=[],
        notes=None,
    )
    run = Run(
        run_id=run_id,
        trace_id=f"{run_id}-trace",
        experiment_id=experiment_id,
        scenario_id=scenario.scenario_id,
        started_at=now,
        ended_at=now,
        run_outcome=RunOutcome.APPROVED if passed else RunOutcome.REVIEW_REQUIRED,
        final_output="Approved." if passed else "Escalated for review.",
        final_decision="approved" if passed else "review_required",
        human_review_requested=not passed,
        cost_estimate_usd=0.1,
        latency_ms=100,
        error_type=None,
    )
    events = [
        TraceEvent(
            event_id=f"{run_id}-event-1",
            trace_id=run.trace_id,
            run_id=run.run_id,
            sequence_no=1,
            timestamp=now,
            event_type=EventType.AGENT_STARTED,
            agent_name="coordinator",
            tool_name=None,
            parent_event_id=None,
            from_agent=None,
            to_agent=None,
            input_summary=request_text,
            output_summary=None,
            structured_payload={},
            policy_reference=None,
            severity=1,
            redacted=False,
        ),
        TraceEvent(
            event_id=f"{run_id}-event-2",
            trace_id=run.trace_id,
            run_id=run.run_id,
            sequence_no=2,
            timestamp=now,
            event_type=EventType.DECISION if passed else EventType.REVIEW_REQUESTED,
            agent_name="coordinator",
            tool_name=None,
            parent_event_id=None,
            from_agent="coordinator",
            to_agent="reviewer" if not passed else None,
            input_summary=None,
            output_summary="Approved." if passed else "Review requested.",
            structured_payload={},
            policy_reference=None,
            severity=severity,
            redacted=False,
        ),
    ]
    finding = EvalFinding(
        finding_id=f"{run_id}-finding-1",
        run_id=run.run_id,
        evaluator_name="DiscoveryEval",
        evaluator_version="1.0.0",
        finding_type=FindingType.NONE if passed else finding_type,
        passed=passed,
        severity=0 if passed else severity,
        confidence=0.95,
        evidence_event_ids=[events[-1].event_id],
        explanation="Passed." if passed else "Detected failure.",
        expected_behavior="Expected behavior.",
        observed_behavior="Observed behavior.",
    )

    create_scenario(session, scenario)
    if run.experiment_id not in {
        existing_experiment.experiment_id
        for existing_experiment in db_module.list_experiments(session)
    }:
        create_experiment(session, experiment)
    create_run(session, run)
    for event in events:
        create_trace_event(session, event)
    create_eval_finding(session, finding)
    return run
