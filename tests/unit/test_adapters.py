from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from macrotrace.adapters.jsonl_import import JsonlImportAdapter
from macrotrace.adapters.openai_agents import OpenAIAgentsAdapter
from macrotrace.exceptions import AdapterError
from macrotrace.schemas import EventType, RawTrace, TraceEvent
from macrotrace.tracing.normalizer import TraceNormalizer
from macrotrace.tracing.redaction import TraceRedactor


def test_jsonl_import_adapter_normalizes_valid_jsonl_input(tmp_path: Path) -> None:
    adapter = JsonlImportAdapter()
    jsonl_path = tmp_path / "trace.jsonl"
    raw_trace_payload = {
        "trace_id": "trace-1",
        "run_id": "run-1",
        "source_adapter": "jsonl_import",
        "payload": {
            "events": [
                {
                    "event_id": "event-1",
                    "trace_id": "trace-1",
                    "run_id": "run-1",
                    "sequence_no": 1,
                    "timestamp": "2026-05-25T12:00:00+00:00",
                    "event_type": "workflow_started",
                    "agent_name": "coordinator",
                    "tool_name": None,
                    "parent_event_id": None,
                    "from_agent": None,
                    "to_agent": None,
                    "input_summary": "start",
                    "output_summary": None,
                    "structured_payload": {"step": "begin"},
                    "policy_reference": None,
                    "severity": 1,
                    "redacted": False,
                }
            ]
        },
    }
    jsonl_path.write_text(
        f"{json.dumps(raw_trace_payload)}\n",
        encoding="utf-8",
    )

    raw_traces = adapter.load_raw_traces(jsonl_path)

    assert len(raw_traces) == 1
    events = adapter.normalize(raw_traces[0])
    assert events == [
        TraceEvent(
            event_id="event-1",
            trace_id="trace-1",
            run_id="run-1",
            sequence_no=1,
            timestamp=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            event_type=EventType.WORKFLOW_STARTED,
            agent_name="coordinator",
            tool_name=None,
            parent_event_id=None,
            from_agent=None,
            to_agent=None,
            input_summary="start",
            output_summary=None,
            structured_payload={"step": "begin"},
            policy_reference=None,
            severity=1,
            redacted=False,
        )
    ]


def test_jsonl_import_adapter_rejects_malformed_input(tmp_path: Path) -> None:
    adapter = JsonlImportAdapter()
    jsonl_path = tmp_path / "trace.jsonl"
    jsonl_path.write_text('{"trace_id": "trace-1"', encoding="utf-8")

    with pytest.raises(AdapterError):
        adapter.load_raw_traces(jsonl_path)


def test_openai_agents_adapter_handles_empty_event_list() -> None:
    adapter = OpenAIAgentsAdapter()
    raw_trace = RawTrace(
        trace_id="trace-1",
        run_id="run-1",
        source_adapter="openai_agents",
        payload={"events": []},
    )

    assert adapter.normalize(raw_trace) == []


def test_trace_normalizer_dispatches_to_correct_adapter() -> None:
    normalizer = TraceNormalizer()
    raw_trace = RawTrace(
        trace_id="trace-1",
        run_id="run-1",
        source_adapter="openai_agents",
        payload={
            "events": [
                {
                    "id": "event-1",
                    "type": "tool.start",
                    "sequence_no": 1,
                    "timestamp": "2026-05-25T12:00:00+00:00",
                    "agent_name": "coordinator",
                    "tool_name": "lookup_budget",
                    "input": "fetch budget",
                }
            ]
        },
    )

    events = normalizer.normalize_trace(raw_trace, "openai_agents")

    assert len(events) == 1
    assert events[0].event_type is EventType.TOOL_CALLED
    assert events[0].tool_name == "lookup_budget"


def test_redaction_removes_configured_sensitive_fields() -> None:
    redactor = TraceRedactor()
    event = TraceEvent(
        event_id="event-1",
        trace_id="trace-1",
        run_id="run-1",
        sequence_no=1,
        timestamp=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        event_type=EventType.AGENT_RESPONSE,
        agent_name="coordinator",
        tool_name=None,
        parent_event_id=None,
        from_agent=None,
        to_agent=None,
        input_summary="contact analyst@example.com",
        output_summary="done",
        structured_payload={
            "password": "super-secret",
            "nested": {"token": "abc123"},
            "safe_field": "safe-value",
        },
        policy_reference=None,
        severity=1,
        redacted=False,
    )

    redacted_events = redactor.redact_trace([event], sensitive_fields=["password", "token"])

    assert redacted_events[0].structured_payload["password"] == "[REDACTED]"
    assert redacted_events[0].structured_payload["nested"] == {"token": "[REDACTED]"}
    assert redacted_events[0].input_summary == "contact [REDACTED]"
    assert redacted_events[0].structured_payload["safe_field"] == "safe-value"


def test_redacted_events_have_redacted_true() -> None:
    redactor = TraceRedactor()
    event = TraceEvent(
        event_id="event-2",
        trace_id="trace-2",
        run_id="run-2",
        sequence_no=1,
        timestamp=datetime(2026, 5, 25, 12, 5, tzinfo=UTC),
        event_type=EventType.TOOL_RESULT,
        agent_name=None,
        tool_name="lookup_user",
        parent_event_id=None,
        from_agent=None,
        to_agent=None,
        input_summary=None,
        output_summary="user jane@example.com",
        structured_payload={"email": "jane@example.com"},
        policy_reference=None,
        severity=1,
        redacted=False,
    )

    [redacted_event] = redactor.redact_trace([event], sensitive_fields=["email"])

    assert redacted_event.redacted is True
    assert redacted_event.structured_payload["email"] == "[REDACTED]"
    assert redacted_event.output_summary == "user [REDACTED]"
