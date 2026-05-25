"""OpenAI Agents SDK trace normalization adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from macrotrace.exceptions import AdapterError
from macrotrace.schemas.trace import EventType, RawTrace, TraceEvent

_OPENAI_EVENT_TYPE_MAP: dict[str, EventType] = {
    "trace.start": EventType.WORKFLOW_STARTED,
    "run.start": EventType.WORKFLOW_STARTED,
    "agent.start": EventType.AGENT_STARTED,
    "agent.response": EventType.AGENT_RESPONSE,
    "tool.start": EventType.TOOL_CALLED,
    "tool.end": EventType.TOOL_RESULT,
    "handoff": EventType.HANDOFF,
    "guardrail.triggered": EventType.GUARDRAIL_TRIGGERED,
    "review.requested": EventType.REVIEW_REQUESTED,
    "decision": EventType.DECISION,
    "error": EventType.ERROR,
    "trace.end": EventType.WORKFLOW_COMPLETED,
    "run.end": EventType.WORKFLOW_COMPLETED,
}


class OpenAIAgentsAdapter:
    """Normalize OpenAI Agents SDK run/span events into MacroTrace events."""

    def build_trace_processor(self, raw_trace: RawTrace) -> Callable[[dict[str, object]], None]:
        """Build a callback compatible with the SDK custom trace processor pattern."""

        raw_events = raw_trace.payload.setdefault("events", [])
        if not isinstance(raw_events, list):
            raise AdapterError("OpenAI Agents raw trace payload must include an 'events' list.")

        def process(event: dict[str, object]) -> None:
            raw_events.append(event)

        return process

    def normalize(self, raw_trace: RawTrace) -> list[TraceEvent]:
        """Normalize an OpenAI Agents raw trace payload into trace events."""

        raw_events = raw_trace.payload.get("events")
        if raw_events is None:
            return []
        if not isinstance(raw_events, list):
            raise AdapterError("OpenAI Agents raw trace payload must include an 'events' list.")

        normalized_events: list[TraceEvent] = []
        for index, raw_event in enumerate(raw_events, start=1):
            if not isinstance(raw_event, dict):
                raise AdapterError("OpenAI Agents event payloads must be JSON objects.")
            normalized_events.append(
                self._normalize_event(raw_trace=raw_trace, raw_event=raw_event, index=index)
            )
        return normalized_events

    def _normalize_event(
        self,
        raw_trace: RawTrace,
        raw_event: dict[str, object],
        index: int,
    ) -> TraceEvent:
        """Normalize a single OpenAI Agents SDK event."""

        event_type_name = self._as_str(raw_event.get("type")) or self._as_str(
            raw_event.get("event_type")
        )
        normalized_type = _OPENAI_EVENT_TYPE_MAP.get(event_type_name or "", EventType.DECISION)
        agent_name = self._first_string(raw_event, "agent_name", "agent", "span_name")
        tool_name = self._first_string(raw_event, "tool_name", "tool")
        from_agent = self._first_string(raw_event, "from_agent", "source_agent")
        to_agent = self._first_string(raw_event, "to_agent", "target_agent")
        input_summary = self._summarize(raw_event.get("input"))
        output_summary = self._summarize(raw_event.get("output"))
        policy_reference = self._first_string(raw_event, "policy_reference", "guardrail")
        severity = self._severity_for_event(normalized_type)
        structured_payload = dict(raw_event)

        if agent_name is None:
            agent_name = self._nested_name(raw_event.get("agent"))
        if tool_name is None:
            tool_name = self._nested_name(raw_event.get("tool"))

        event_data = {
            "event_id": self._first_string(raw_event, "event_id", "id")
            or f"{raw_trace.trace_id}:{index}",
            "trace_id": raw_trace.trace_id,
            "run_id": raw_trace.run_id,
            "sequence_no": self._coerce_sequence(raw_event.get("sequence_no"), fallback=index),
            "timestamp": self._parse_timestamp(raw_event.get("timestamp")),
            "event_type": normalized_type,
            "agent_name": agent_name,
            "tool_name": tool_name,
            "parent_event_id": self._first_string(raw_event, "parent_event_id", "parent_id"),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "structured_payload": structured_payload,
            "policy_reference": policy_reference,
            "severity": severity,
            "redacted": False,
        }
        try:
            return TraceEvent.model_validate(event_data)
        except ValidationError as exc:
            raise AdapterError("OpenAI Agents event payload failed TraceEvent validation.") from exc

    def _nested_name(self, value: object) -> str | None:
        """Extract a nested name field from a mapping-like payload."""

        if not isinstance(value, dict):
            return None
        return self._as_str(value.get("name"))

    def _coerce_sequence(self, value: object, fallback: int) -> int:
        """Coerce an event sequence number."""

        if isinstance(value, int):
            return value
        return fallback

    def _parse_timestamp(self, value: object) -> datetime:
        """Parse a timestamp from the OpenAI Agents event payload."""

        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                normalized = value.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except ValueError:
                return datetime.now(tz=UTC)
        return datetime.now(tz=UTC)

    def _severity_for_event(self, event_type: EventType) -> int:
        """Assign a default severity for a normalized event type."""

        if event_type in {EventType.ERROR, EventType.GUARDRAIL_TRIGGERED}:
            return 4
        if event_type is EventType.REVIEW_REQUESTED:
            return 3
        return 1

    def _summarize(self, value: object) -> str | None:
        """Convert an event field into a short stored summary."""

        text = self._as_str(value)
        if text is not None:
            return text
        if isinstance(value, dict):
            for key in ("summary", "content", "text", "name"):
                nested = self._as_str(value.get(key))
                if nested is not None:
                    return nested
        return None

    def _first_string(self, payload: dict[str, object], *keys: str) -> str | None:
        """Return the first string-like value for a list of candidate keys."""

        for key in keys:
            value = self._as_str(payload.get(key))
            if value is not None:
                return value
        return None

    def _as_str(self, value: object) -> str | None:
        """Convert a primitive value into a string."""

        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return None
