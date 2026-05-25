"""Trace normalization service."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from macrotrace.adapters.base import TraceAdapter
from macrotrace.adapters.jsonl_import import JsonlImportAdapter
from macrotrace.adapters.openai_agents import OpenAIAgentsAdapter
from macrotrace.exceptions import AdapterError
from macrotrace.schemas.trace import RawTrace, TraceEvent


class TraceNormalizer:
    """Dispatch raw traces to the correct adapter and validate normalized output."""

    def __init__(self, adapters: Mapping[str, TraceAdapter] | None = None) -> None:
        """Initialize a normalizer with an optional adapter registry override."""

        self._adapters: dict[str, TraceAdapter] = dict(adapters or self._default_adapters())

    def normalize_trace(self, raw_trace: RawTrace, adapter_name: str) -> list[TraceEvent]:
        """Normalize a raw trace with the named adapter."""

        adapter = self._adapters.get(adapter_name)
        if adapter is None:
            raise AdapterError(f"Unsupported trace adapter: {adapter_name}")

        try:
            normalized_events = adapter.normalize(raw_trace)
            return [TraceEvent.model_validate(event.model_dump()) for event in normalized_events]
        except AdapterError:
            raise
        except ValidationError as exc:
            raise AdapterError("Normalized trace events failed schema validation.") from exc
        except Exception as exc:
            raise AdapterError(f"Failed to normalize trace with adapter '{adapter_name}'.") from exc

    def _default_adapters(self) -> dict[str, TraceAdapter]:
        """Build the default adapter registry."""

        return {
            "jsonl": JsonlImportAdapter(),
            "jsonl_import": JsonlImportAdapter(),
            "openai_agents": OpenAIAgentsAdapter(),
        }
