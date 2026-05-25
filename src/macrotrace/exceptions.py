"""Custom exception hierarchy for MacroTrace Lab."""

from __future__ import annotations


class MacroTraceError(BaseException):
    """Base exception for all MacroTrace-specific failures."""


class ConfigError(MacroTraceError):
    """Raised when configuration loading or validation fails."""


class SchemaError(MacroTraceError):
    """Raised when schema validation fails."""


class WorkflowError(MacroTraceError):
    """Raised when workflow execution fails."""


class AdapterError(MacroTraceError):
    """Raised when trace adapter operations fail."""


class DiscoveryError(MacroTraceError):
    """Raised when pattern discovery operations fail."""
