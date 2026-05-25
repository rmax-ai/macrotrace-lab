"""Trace import and validation command hooks."""

from __future__ import annotations

from pathlib import Path


def import_traces(adapter: str, path: Path) -> None:
    """Import traces from an external source."""

    raise NotImplementedError(
        f"Trace import is not implemented yet for adapter='{adapter}' and path='{path}'."
    )


def validate_traces(experiment: str) -> None:
    """Validate traces for an experiment."""

    raise NotImplementedError(f"Trace validation is not implemented yet for '{experiment}'.")
