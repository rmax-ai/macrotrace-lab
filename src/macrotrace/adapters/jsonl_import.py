"""JSONL trace import adapter."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from macrotrace.exceptions import AdapterError
from macrotrace.schemas.trace import RawTrace, TraceEvent


class JsonlImportAdapter:
    """Normalize traces that were previously exported as JSONL."""

    def load_raw_traces(self, path: Path) -> list[RawTrace]:
        """Load raw traces from a JSONL file."""

        raw_traces: list[RawTrace] = []
        line_number = 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                for current_line_number, line in enumerate(handle, start=1):
                    line_number = current_line_number
                    stripped = line.strip()
                    if not stripped:
                        continue
                    payload = json.loads(stripped)
                    raw_traces.append(RawTrace.model_validate(payload))
        except FileNotFoundError as exc:
            raise AdapterError(f"JSONL trace file was not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise AdapterError(
                f"Malformed JSON on line {exc.lineno} of JSONL trace file: {path}"
            ) from exc
        except ValidationError as exc:
            raise AdapterError(
                f"Invalid raw trace payload on line {line_number} of JSONL trace file: {path}"
            ) from exc

        return raw_traces

    def normalize(self, raw_trace: RawTrace) -> list[TraceEvent]:
        """Normalize a JSONL-import raw trace into trace events."""

        events = raw_trace.payload.get("events")
        if not isinstance(events, list):
            raise AdapterError("JSONL raw trace payload must include an 'events' list.")

        normalized_events: list[TraceEvent] = []
        for event in events:
            if not isinstance(event, dict):
                raise AdapterError("JSONL event payloads must be JSON objects.")
            try:
                normalized_events.append(TraceEvent.model_validate(event))
            except ValidationError as exc:
                raise AdapterError("JSONL event payload failed TraceEvent validation.") from exc
        return normalized_events
