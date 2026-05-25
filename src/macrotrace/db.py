"""SQLite persistence layer for MacroTrace Lab."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Column, ForeignKey, String, event, text
from sqlalchemy.engine import Engine
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

from macrotrace.schemas.eval import EvalFinding, FindingType
from macrotrace.schemas.experiment import Experiment
from macrotrace.schemas.pattern import BehaviorPattern, DiagnosisSuspect
from macrotrace.schemas.scenario import Scenario
from macrotrace.schemas.trace import EventType, RawTrace, Run, RunOutcome, TraceEvent

DEFAULT_DB_PATH = Path("data/macrotrace.db")


def _json_column() -> Column[Any]:
    """Build a SQLite JSON column."""

    return Column(JSON, nullable=False)


class ScenarioTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for scenarios."""

    __tablename__ = "scenarios"

    scenario_id: str = SQLField(primary_key=True)
    dataset_id: str
    case_type: str
    request_text: str
    expected_outcome: str | None = None
    ground_truth: dict[str, bool | list[str]] = SQLField(sa_column=_json_column())
    environmental_signals: dict[str, int | str | float | bool | None] = SQLField(
        sa_column=_json_column()
    )
    severity_if_mishandled: int
    tags: list[str] = SQLField(sa_column=_json_column())


class ExperimentTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for experiments."""

    __tablename__ = "experiments"

    experiment_id: str = SQLField(primary_key=True)
    name: str
    created_at: datetime
    workflow_name: str
    workflow_version: str
    config_hash: str
    baseline_experiment_id: str | None = SQLField(
        default=None, foreign_key="experiments.experiment_id"
    )
    scenario_dataset_id: str
    model_settings: dict[str, object] = SQLField(sa_column=_json_column())
    agent_config: dict[str, object] = SQLField(sa_column=_json_column())
    fault_injections: list[str] = SQLField(sa_column=_json_column())
    notes: str | None = None


class RunTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for workflow runs."""

    __tablename__ = "runs"

    run_id: str = SQLField(primary_key=True)
    trace_id: str = SQLField(index=True, unique=True)
    experiment_id: str = SQLField(foreign_key="experiments.experiment_id", index=True)
    scenario_id: str = SQLField(foreign_key="scenarios.scenario_id", index=True)
    started_at: datetime
    ended_at: datetime | None = None
    run_outcome: str
    final_output: str | None = None
    final_decision: str | None = None
    human_review_requested: bool
    cost_estimate_usd: float | None = None
    latency_ms: int | None = None
    error_type: str | None = None


class TraceEventTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for normalized trace events."""

    __tablename__ = "trace_events"

    event_id: str = SQLField(primary_key=True)
    trace_id: str = SQLField(index=True)
    run_id: str = SQLField(foreign_key="runs.run_id", index=True)
    sequence_no: int = SQLField(index=True)
    timestamp: datetime
    event_type: str = SQLField(index=True)
    agent_name: str | None = None
    tool_name: str | None = None
    parent_event_id: str | None = SQLField(
        default=None, sa_column=Column(String, ForeignKey("trace_events.event_id"), nullable=True)
    )
    from_agent: str | None = None
    to_agent: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    structured_payload: dict[str, object] = SQLField(sa_column=_json_column())
    policy_reference: str | None = None
    severity: int
    redacted: bool


class RawTraceTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for raw adapter payloads."""

    __tablename__ = "raw_traces"

    trace_id: str = SQLField(primary_key=True)
    run_id: str = SQLField(foreign_key="runs.run_id", index=True)
    source_adapter: str
    payload: dict[str, object] = SQLField(sa_column=_json_column())


class EvalFindingTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for evaluator findings."""

    __tablename__ = "eval_findings"

    finding_id: str = SQLField(primary_key=True)
    run_id: str = SQLField(foreign_key="runs.run_id", index=True)
    evaluator_name: str
    evaluator_version: str
    finding_type: str = SQLField(index=True)
    passed: bool
    severity: int
    confidence: float
    evidence_event_ids: list[str] = SQLField(sa_column=_json_column())
    explanation: str
    expected_behavior: str
    observed_behavior: str


class BehaviorPatternTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for discovered behavior patterns."""

    __tablename__ = "behavior_patterns"

    pattern_id: str = SQLField(primary_key=True)
    experiment_id: str = SQLField(foreign_key="experiments.experiment_id", index=True)
    cluster_id: int = SQLField(index=True)
    label: str
    keywords: list[str] = SQLField(sa_column=_json_column())
    trace_count: int
    prevalence_share: float
    severity_weighted_prevalence: float
    impact_score: float
    dominant_case_type: str | None = None
    dominant_finding_type: str | None = None
    dominant_owner: str | None = None
    representative_run_ids: list[str] = SQLField(sa_column=_json_column())


class DiagnosisSuspectTable(SQLModel, table=True):  # type: ignore[misc,call-arg]
    """SQLModel table for diagnosis suspects."""

    __tablename__ = "diagnosis_suspects"

    suspect_id: str = SQLField(primary_key=True)
    pattern_id: str = SQLField(foreign_key="behavior_patterns.pattern_id", index=True)
    node_signature: str
    node_kind: str
    agent_name: str | None = None
    tool_name: str | None = None
    proximity_score: float
    frequency_score: float
    bridge_score: float
    role_score: float
    suspect_score: float
    trace_coverage_share: float
    explanation: str


def _apply_sqlite_pragmas(dbapi_connection: Any, _: Any) -> None:
    """Apply SQLite tuning pragmas when a connection is opened."""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA cache_size=-64000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


def create_db_engine(db_path: str | Path = DEFAULT_DB_PATH) -> Engine:
    """Create a SQLite engine configured for local batch workloads."""

    resolved_path = Path(db_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{resolved_path}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _apply_sqlite_pragmas)
    return engine


ENGINE = create_db_engine()


@contextmanager
def get_session(engine: Engine = ENGINE) -> Any:
    """Yield a database session."""

    with Session(engine) as session:
        yield session


def init_db(engine: Engine = ENGINE) -> None:
    """Create all configured database tables."""

    SQLModel.metadata.create_all(engine)


def create_scenario(session: Session, scenario: Scenario) -> Scenario:
    """Persist a scenario."""

    record = ScenarioTable(**scenario.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return Scenario.model_validate(record.model_dump())


def list_scenarios(session: Session) -> list[Scenario]:
    """List all persisted scenarios."""

    records = session.exec(select(ScenarioTable).order_by(ScenarioTable.scenario_id)).all()
    return [Scenario.model_validate(record.model_dump()) for record in records]


def create_experiment(session: Session, experiment: Experiment) -> Experiment:
    """Persist experiment metadata."""

    payload = experiment.model_dump(by_alias=True)
    record = ExperimentTable(**payload)
    session.add(record)
    session.commit()
    session.refresh(record)
    return Experiment.model_validate(record.model_dump())


def list_experiments(session: Session) -> list[Experiment]:
    """List persisted experiments."""

    records = session.exec(select(ExperimentTable).order_by(ExperimentTable.experiment_id)).all()
    return [Experiment.model_validate(record.model_dump()) for record in records]


def create_run(session: Session, run: Run) -> Run:
    """Persist a workflow run."""

    data = run.model_dump(exclude={"run_outcome"})
    record = RunTable(
        **data,
        run_outcome=run.run_outcome.value,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return Run.model_validate(
        {
            **record.model_dump(),
            "run_outcome": RunOutcome(record.run_outcome),
        }
    )


def list_runs(session: Session, experiment_id: str | None = None) -> list[Run]:
    """List persisted workflow runs, optionally filtered by experiment."""

    statement = select(RunTable)
    if experiment_id is not None:
        statement = statement.where(RunTable.experiment_id == experiment_id)
    records = session.exec(statement.order_by(RunTable.run_id)).all()
    return [
        Run.model_validate({**record.model_dump(), "run_outcome": RunOutcome(record.run_outcome)})
        for record in records
    ]


def create_trace_event(session: Session, trace_event: TraceEvent) -> TraceEvent:
    """Persist a normalized trace event."""

    data = trace_event.model_dump(exclude={"event_type"})
    record = TraceEventTable(
        **data,
        event_type=trace_event.event_type.value,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return TraceEvent.model_validate(
        {
            **record.model_dump(),
            "event_type": EventType(record.event_type),
        }
    )


def list_trace_events(session: Session, run_id: str | None = None) -> list[TraceEvent]:
    """List normalized trace events, optionally filtered by run."""

    statement = select(TraceEventTable)
    if run_id is not None:
        statement = statement.where(TraceEventTable.run_id == run_id)
    records = session.exec(statement.order_by(TraceEventTable.sequence_no)).all()
    return [
        TraceEvent.model_validate(
            {**record.model_dump(), "event_type": EventType(record.event_type)}
        )
        for record in records
    ]


def create_raw_trace(session: Session, raw_trace: RawTrace) -> RawTrace:
    """Persist a raw trace payload."""

    record = RawTraceTable(**raw_trace.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return RawTrace.model_validate(record.model_dump())


def list_raw_traces(session: Session, run_id: str | None = None) -> list[RawTrace]:
    """List raw traces, optionally filtered by run."""

    statement = select(RawTraceTable)
    if run_id is not None:
        statement = statement.where(RawTraceTable.run_id == run_id)
    records = session.exec(statement.order_by(RawTraceTable.trace_id)).all()
    return [RawTrace.model_validate(record.model_dump()) for record in records]


def create_eval_finding(session: Session, finding: EvalFinding) -> EvalFinding:
    """Persist an evaluator finding."""

    data = finding.model_dump(exclude={"finding_type"})
    record = EvalFindingTable(
        **data,
        finding_type=finding.finding_type.value,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return EvalFinding.model_validate(
        {
            **record.model_dump(),
            "finding_type": FindingType(record.finding_type),
        }
    )


def list_eval_findings(session: Session, run_id: str | None = None) -> list[EvalFinding]:
    """List evaluator findings, optionally filtered by run."""

    statement = select(EvalFindingTable)
    if run_id is not None:
        statement = statement.where(EvalFindingTable.run_id == run_id)
    records = session.exec(statement.order_by(EvalFindingTable.finding_id)).all()
    return [
        EvalFinding.model_validate(
            {**record.model_dump(), "finding_type": FindingType(record.finding_type)}
        )
        for record in records
    ]


def create_behavior_pattern(session: Session, pattern: BehaviorPattern) -> BehaviorPattern:
    """Persist a discovered behavior pattern."""

    record = BehaviorPatternTable(**pattern.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return BehaviorPattern.model_validate(record.model_dump())


def list_behavior_patterns(
    session: Session,
    experiment_id: str | None = None,
) -> list[BehaviorPattern]:
    """List behavior patterns, optionally filtered by experiment."""

    statement = select(BehaviorPatternTable)
    if experiment_id is not None:
        statement = statement.where(BehaviorPatternTable.experiment_id == experiment_id)
    records = session.exec(statement.order_by(BehaviorPatternTable.pattern_id)).all()
    return [BehaviorPattern.model_validate(record.model_dump()) for record in records]


def create_diagnosis_suspect(
    session: Session,
    suspect: DiagnosisSuspect,
) -> DiagnosisSuspect:
    """Persist a diagnosis suspect."""

    record = DiagnosisSuspectTable(**suspect.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return DiagnosisSuspect.model_validate(record.model_dump())


def list_diagnosis_suspects(
    session: Session,
    pattern_id: str | None = None,
) -> list[DiagnosisSuspect]:
    """List diagnosis suspects, optionally filtered by pattern."""

    statement = select(DiagnosisSuspectTable)
    if pattern_id is not None:
        statement = statement.where(DiagnosisSuspectTable.pattern_id == pattern_id)
    records = session.exec(statement.order_by(DiagnosisSuspectTable.suspect_id)).all()
    return [DiagnosisSuspect.model_validate(record.model_dump()) for record in records]


def get_sqlite_pragma(session: Session, pragma_name: str) -> Any:
    """Fetch a SQLite pragma value for tests or diagnostics."""

    result = session.exec(text(f"PRAGMA {pragma_name};")).one()
    return result
