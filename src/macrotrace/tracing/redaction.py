"""Trace redaction service."""

from __future__ import annotations

import re
from collections.abc import Sequence

from macrotrace.schemas.trace import TraceEvent

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_DEFAULT_SENSITIVE_FIELDS: tuple[str, ...] = (
    "api_key",
    "api_keys",
    "authorization",
    "email",
    "email_address",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
)


class TraceRedactor:
    """Redact sensitive values from normalized trace events."""

    def redact_trace(
        self,
        events: list[TraceEvent],
        sensitive_fields: list[str] | None = None,
    ) -> list[TraceEvent]:
        """Redact configured sensitive fields from a trace event list."""

        configured_fields = {
            field.casefold() for field in (sensitive_fields or list(_DEFAULT_SENSITIVE_FIELDS))
        }
        redacted_events: list[TraceEvent] = []
        for event in events:
            payload, payload_redacted = self._redact_mapping(
                event.structured_payload,
                configured_fields=configured_fields,
            )
            input_summary, input_redacted = self._redact_text(event.input_summary)
            output_summary, output_redacted = self._redact_text(event.output_summary)
            was_redacted = payload_redacted or input_redacted or output_redacted
            redacted_events.append(
                event.model_copy(
                    update={
                        "structured_payload": payload,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "redacted": event.redacted or was_redacted,
                    }
                )
            )
        return redacted_events

    def _redact_mapping(
        self,
        value: dict[str, object],
        configured_fields: set[str],
    ) -> tuple[dict[str, object], bool]:
        """Redact sensitive content from a mapping."""

        updated: dict[str, object] = {}
        redacted = False
        for key, item in value.items():
            if key.casefold() in configured_fields:
                updated[key] = "[REDACTED]"
                redacted = True
                continue
            updated_item, item_redacted = self._redact_value(
                item, configured_fields=configured_fields
            )
            updated[key] = updated_item
            redacted = redacted or item_redacted
        return updated, redacted

    def _redact_sequence(
        self,
        value: Sequence[object],
        configured_fields: set[str],
    ) -> tuple[list[object], bool]:
        """Redact sensitive content from a sequence."""

        updated: list[object] = []
        redacted = False
        for item in value:
            updated_item, item_redacted = self._redact_value(
                item, configured_fields=configured_fields
            )
            updated.append(updated_item)
            redacted = redacted or item_redacted
        return updated, redacted

    def _redact_value(
        self,
        value: object,
        configured_fields: set[str],
    ) -> tuple[object, bool]:
        """Redact sensitive content from any supported value."""

        if isinstance(value, dict):
            return self._redact_mapping(value, configured_fields=configured_fields)
        if isinstance(value, list):
            return self._redact_sequence(value, configured_fields=configured_fields)
        if isinstance(value, tuple):
            redacted_list, redacted = self._redact_sequence(
                list(value),
                configured_fields=configured_fields,
            )
            return redacted_list, redacted
        if isinstance(value, str):
            return self._redact_text(value)
        return value, False

    def _redact_text(self, value: str | None) -> tuple[str | None, bool]:
        """Redact sensitive content embedded in a text field."""

        if value is None:
            return None, False
        redacted_value = _EMAIL_PATTERN.sub("[REDACTED]", value)
        return redacted_value, redacted_value != value
