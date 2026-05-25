"""Trace document construction for pattern discovery."""

from __future__ import annotations

from collections.abc import Sequence

from macrotrace.schemas.eval import EvalFinding, FindingType
from macrotrace.schemas.scenario import Scenario
from macrotrace.schemas.trace import EventType, Run, TraceEvent

DOCUMENT_SCHEMA_VERSION = "1.0.0"
_UNSAFE_FALLBACK_FINDING_TYPES = {
    FindingType.POLICY_VIOLATION,
    FindingType.RUNTIME_FAILURE,
    FindingType.TOOL_USE_ERROR,
}


class TraceDocumentBuilder:
    """Build deterministic trace documents from normalized workflow artifacts."""

    def __init__(self, document_schema_version: str = DOCUMENT_SCHEMA_VERSION) -> None:
        """Initialize the builder with a fixed schema version."""

        self.document_schema_version = document_schema_version
        self.last_section_event_ids: dict[str, list[str]] = {}

    def build(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
        findings: Sequence[EvalFinding],
    ) -> str:
        """Render a versioned trace document from a run and its supporting evidence."""

        ordered_events = sorted(events, key=lambda event: (event.sequence_no, event.event_id))
        ordered_findings = sorted(
            findings,
            key=lambda finding: (
                finding.passed,
                -finding.severity,
                finding.finding_type.value,
                finding.finding_id,
            ),
        )
        request_text = _normalize_text(scenario.request_text)
        environment_lines = _build_environment_lines(scenario)
        route_lines, route_event_ids = _build_route(ordered_events)
        missing_route_lines = _build_missing_expected_route(scenario, ordered_events)
        tool_lines, tool_event_ids = _build_tool_lines(ordered_events, ordered_findings)
        decision_text, decision_event_ids = _build_decision(run, ordered_events)
        finding_lines, finding_event_ids = _build_finding_lines(ordered_findings)
        transition_text = _build_state_transitions(ordered_events)
        summary_text, summary_event_ids = _build_summary(
            run=run,
            scenario=scenario,
            events=ordered_events,
            findings=ordered_findings,
        )

        self.last_section_event_ids = {
            "REQUEST": _event_ids_for_text_match(ordered_events, request_text),
            "ENVIRONMENT": [],
            "ROUTE": route_event_ids,
            "MISSING_EXPECTED_ROUTE": [],
            "TOOLS": tool_event_ids,
            "DECISION": decision_event_ids,
            "EVAL_FINDINGS": finding_event_ids,
            "STATE_TRANSITIONS": [event.event_id for event in ordered_events],
            "SUMMARY": summary_event_ids,
        }

        return "\n".join(
            [
                f"RUN_ID: {run.run_id}",
                f"EXPERIMENT: {run.experiment_id}",
                f"CASE_TYPE: {scenario.case_type}",
                f"RUN_OUTCOME: {run.run_outcome.value}",
                f"EXPECTED_OUTCOME: {scenario.expected_outcome or 'N/A'}",
                f"SEVERITY_IF_MISHANDLED: {scenario.severity_if_mishandled}",
                "",
                "REQUEST:",
                request_text,
                "",
                "ENVIRONMENT:",
                "\n".join(environment_lines),
                "",
                "ROUTE:",
                "\n".join(route_lines),
                "",
                "MISSING_EXPECTED_ROUTE:",
                "\n".join(missing_route_lines),
                "",
                "TOOLS:",
                "\n".join(tool_lines),
                "",
                "DECISION:",
                decision_text,
                "",
                "EVAL_FINDINGS:",
                "\n".join(finding_lines),
                "",
                "STATE_TRANSITIONS:",
                transition_text,
                "",
                "SUMMARY:",
                summary_text,
            ]
        )


def _build_environment_lines(scenario: Scenario) -> list[str]:
    """Render policy-relevant environment signals in deterministic order."""

    if not scenario.environmental_signals:
        return ["N/A"]
    return [
        f"{key}={_format_scalar(scenario.environmental_signals[key])}"
        for key in sorted(scenario.environmental_signals)
        if scenario.environmental_signals[key] is not None
    ] or ["N/A"]


def _build_route(events: Sequence[TraceEvent]) -> tuple[list[str], list[str]]:
    """Render the observed agent route using first-seen agent activations."""

    route: list[str] = []
    route_event_ids: list[str] = []
    seen_agents: set[str] = set()
    for event in events:
        if event.event_type is not EventType.AGENT_STARTED or event.agent_name is None:
            continue
        if event.agent_name in seen_agents:
            continue
        seen_agents.add(event.agent_name)
        route.append(event.agent_name)
        route_event_ids.append(event.event_id)
    if not route:
        return ["N/A"], []
    return [" -> ".join(route)], route_event_ids


def _build_missing_expected_route(
    scenario: Scenario,
    events: Sequence[TraceEvent],
) -> list[str]:
    """Render agents that ground truth expected but the run never activated."""

    raw_required_agents = scenario.ground_truth.get("must_activate_agents", [])
    required_agents = (
        sorted(str(agent_name) for agent_name in raw_required_agents)
        if isinstance(raw_required_agents, list)
        else []
    )
    activated_agents = {
        event.agent_name
        for event in events
        if event.event_type is EventType.AGENT_STARTED and event.agent_name is not None
    }
    missing_agents = [
        agent_name for agent_name in required_agents if agent_name not in activated_agents
    ]
    return missing_agents or ["N/A"]


def _build_tool_lines(
    events: Sequence[TraceEvent],
    findings: Sequence[EvalFinding],
) -> tuple[list[str], list[str]]:
    """Render tool outcomes, failed calls, and unsafe fallbacks."""

    tool_lines: list[str] = []
    tool_event_ids: list[str] = []
    pending_calls: dict[str, TraceEvent] = {}

    for event in events:
        if event.event_type is EventType.TOOL_CALLED and event.tool_name is not None:
            pending_calls[event.event_id] = event
            continue
        if event.event_type is not EventType.TOOL_RESULT or event.tool_name is None:
            continue
        result_text = _first_non_empty(
            event.output_summary,
            event.input_summary,
            "result_unavailable",
        )
        tool_lines.append(f"{event.tool_name} returned {_normalize_text(result_text)}")
        tool_event_ids.append(event.event_id)
        if event.parent_event_id is not None:
            pending_calls.pop(event.parent_event_id, None)

    for event in sorted(
        pending_calls.values(),
        key=lambda item: (item.sequence_no, item.event_id),
    ):
        tool_lines.append(f"{event.tool_name} returned no_result")
        tool_event_ids.append(event.event_id)

    unsafe_fallback_evidence = sorted(
        {
            event_id
            for finding in findings
            if not finding.passed and finding.finding_type in _UNSAFE_FALLBACK_FINDING_TYPES
            for event_id in finding.evidence_event_ids
            if event_id in {event.event_id for event in events}
        }
    )
    for event_id in unsafe_fallback_evidence:
        event = next(item for item in events if item.event_id == event_id)
        if event.event_type not in {
            EventType.DECISION,
            EventType.REVIEW_REQUESTED,
            EventType.ERROR,
        }:
            continue
        actor = event.agent_name or "workflow"
        fallback_text = _first_non_empty(
            event.output_summary,
            event.input_summary,
            "unsafe fallback detected",
        )
        tool_lines.append(f"{actor} returned {_normalize_text(fallback_text)}")
        tool_event_ids.append(event.event_id)

    return tool_lines or ["N/A"], tool_event_ids


def _build_decision(run: Run, events: Sequence[TraceEvent]) -> tuple[str, list[str]]:
    """Render the final decision line with evidence links."""

    decision_events = [
        event
        for event in events
        if event.event_type
        in {
            EventType.DECISION,
            EventType.REVIEW_REQUESTED,
            EventType.WORKFLOW_COMPLETED,
        }
    ]
    decision_text = _first_non_empty(
        run.final_decision,
        run.final_output,
        next(
            (
                _first_non_empty(event.output_summary, event.input_summary)
                for event in reversed(decision_events)
                if _first_non_empty(event.output_summary, event.input_summary) is not None
            ),
            None,
        ),
        "N/A",
    )
    return _normalize_text(decision_text), [event.event_id for event in decision_events]


def _build_finding_lines(findings: Sequence[EvalFinding]) -> tuple[list[str], list[str]]:
    """Render failed evaluation findings only."""

    failing_findings = [finding for finding in findings if not finding.passed]
    if not failing_findings:
        return ["N/A"], []

    lines = [
        f"{finding.finding_type.value} severity={finding.severity}" for finding in failing_findings
    ]
    event_ids = sorted(
        {event_id for finding in failing_findings for event_id in finding.evidence_event_ids}
    )
    return lines, event_ids


def _build_state_transitions(events: Sequence[TraceEvent]) -> str:
    """Render event types in sequence order using controlled vocabulary."""

    if not events:
        return "N/A"
    return " -> ".join(event.event_type.value for event in events)


def _build_summary(
    *,
    run: Run,
    scenario: Scenario,
    events: Sequence[TraceEvent],
    findings: Sequence[EvalFinding],
) -> tuple[str, list[str]]:
    """Render a one-sentence run summary."""

    route_lines, route_event_ids = _build_route(events)
    failing_findings = [finding.finding_type.value for finding in findings if not finding.passed]
    route_text = route_lines[0] if route_lines[0] != "N/A" else "no agent route"
    findings_text = ", ".join(failing_findings) if failing_findings else "no failing eval findings"
    summary = (
        f"Scenario {scenario.case_type} ended with {run.run_outcome.value} via {route_text}, "
        f"with {findings_text}."
    )
    return summary, route_event_ids


def _event_ids_for_text_match(events: Sequence[TraceEvent], text: str) -> list[str]:
    """Return event identifiers whose summaries include the given text."""

    if text == "N/A":
        return []
    matched_event_ids = [
        event.event_id
        for event in events
        if text
        in {
            _normalize_text(event.input_summary),
            _normalize_text(event.output_summary),
        }
    ]
    return matched_event_ids


def _first_non_empty(*values: str | None) -> str | None:
    """Return the first non-empty string-like value."""

    for value in values:
        if value is not None and value.strip():
            return value
    return None


def _normalize_text(value: str | None) -> str:
    """Collapse whitespace and return a safe placeholder when text is missing."""

    if value is None or not value.strip():
        return "N/A"
    return " ".join(value.split())


def _format_scalar(value: int | str | float | bool | None) -> str:
    """Format scalar environment values deterministically."""

    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
