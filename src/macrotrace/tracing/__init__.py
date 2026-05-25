"""MacroTrace Lab trace service exports."""

from __future__ import annotations

__all__ = [
    "TraceCollector",
    "TraceNormalizer",
    "TraceRedactor",
]


def __getattr__(name: str) -> object:
    """Lazily resolve trace service exports."""

    if name == "TraceCollector":
        from macrotrace.tracing.collector import TraceCollector

        return TraceCollector
    if name == "TraceNormalizer":
        from macrotrace.tracing.normalizer import TraceNormalizer

        return TraceNormalizer
    if name == "TraceRedactor":
        from macrotrace.tracing.redaction import TraceRedactor

        return TraceRedactor
    raise AttributeError(name)
