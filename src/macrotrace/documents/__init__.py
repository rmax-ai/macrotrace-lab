"""MacroTrace Lab — compact trace document construction."""

from __future__ import annotations

from macrotrace.documents.trace_document_builder import (
    DOCUMENT_SCHEMA_VERSION,
    TraceDocumentBuilder,
)

__all__ = ["DOCUMENT_SCHEMA_VERSION", "TraceDocumentBuilder", "build_documents"]


def build_documents(experiment: str, schema_version: str | None) -> None:
    """Build trace documents for an experiment."""

    raise NotImplementedError(
        "Document building is not implemented yet. "
        f"experiment={experiment}, schema_version={schema_version}."
    )
