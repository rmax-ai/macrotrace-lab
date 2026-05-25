"""MacroTrace Lab — graph-based diagnosis and suspect ranking."""

from __future__ import annotations


def diagnose_pattern(experiment: str, pattern: str) -> None:
    """Diagnose a discovered pattern."""

    raise NotImplementedError(
        f"Diagnosis is not implemented yet for experiment='{experiment}', pattern='{pattern}'."
    )


def compare_experiments(baseline: str, candidate: str) -> None:
    """Compare two experiments."""

    raise NotImplementedError(
        f"Experiment comparison is not implemented yet for '{baseline}' vs '{candidate}'."
    )
