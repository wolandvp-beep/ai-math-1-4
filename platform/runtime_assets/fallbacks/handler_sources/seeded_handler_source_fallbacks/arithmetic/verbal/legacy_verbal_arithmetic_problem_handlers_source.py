from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_verbal_arithmetic_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_verbal_arithmetic_problem_handlers_source import (
    _try_simple_verbal_arithmetic,
)


__all__ = ['_try_simple_verbal_arithmetic']
