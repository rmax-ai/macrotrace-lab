"""Trace collection and persistence service."""

from __future__ import annotations

from sqlmodel import Session

from macrotrace.db import create_raw_trace, create_trace_event
from macrotrace.exceptions import AdapterError
from macrotrace.schemas.trace import RawTrace, TraceEvent
from macrotrace.tracing.normalizer import TraceNormalizer


class TraceCollector:
    """Collect raw traces, normalize them, and persist both representations."""

    def __init__(self, normalizer: TraceNormalizer | None = None) -> None:
        """Initialize the collector with a normalizer dependency."""

        self._normalizer = normalizer or TraceNormalizer()

    def collect_and_store(
        self,
        raw_trace: RawTrace,
        adapter_name: str,
        session: Session,
    ) -> list[TraceEvent]:
        """Normalize a raw trace, persist it, and persist the resulting events."""

        try:
            normalized_events = self._normalizer.normalize_trace(raw_trace, adapter_name)
            create_raw_trace(session, raw_trace)
            for event in normalized_events:
                create_trace_event(session, event)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(
                "Failed to collect and store trace "
                f"'{raw_trace.trace_id}' with adapter '{adapter_name}'."
            ) from exc
        return normalized_events
