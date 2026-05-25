"""Base protocols and enums for trace adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from macrotrace.schemas.trace import RawTrace, TraceEvent


class RawTraceSource(StrEnum):
    """Supported sources for raw trace ingestion."""

    JSONL = "jsonl"
    JSONL_IMPORT = "jsonl_import"
    OPENAI_AGENTS = "openai_agents"


class TraceAdapter(Protocol):
    """Protocol implemented by all trace normalization adapters."""

    def normalize(self, raw_trace: RawTrace) -> list[TraceEvent]:
        """Normalize a raw trace payload into schema-validated trace events."""
