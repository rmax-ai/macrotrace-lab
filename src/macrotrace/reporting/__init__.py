"""MacroTrace Lab — report generation and visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias

ReportFormat: TypeAlias = Literal["markdown", "html"]  # noqa: UP040


def export_report(experiment: str, output_format: ReportFormat, output: Path | None) -> None:
    """Export an experiment report."""

    raise NotImplementedError(
        "Report export is not implemented yet. "
        f"experiment={experiment}, format={output_format}, output={output}."
    )
