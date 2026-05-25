"""structlog configuration for MacroTrace Lab."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(verbose: bool) -> None:
    """Configure JSON logging to stdout with context variable support."""

    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        experiment_id=None,
        run_id=None,
        trace_id=None,
    )
