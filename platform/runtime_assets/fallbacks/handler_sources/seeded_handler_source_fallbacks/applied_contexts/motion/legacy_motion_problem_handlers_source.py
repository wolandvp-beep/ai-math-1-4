from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_motion_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_motion_problem_handlers_source import (
    _try_clock_duration_problem,
    _try_relative_motion_distance,
    _try_simple_motion,
)


__all__ = ['_try_clock_duration_problem', '_try_relative_motion_distance', '_try_simple_motion']
