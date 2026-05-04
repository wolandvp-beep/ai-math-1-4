from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_fraction_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_fraction_problem_handlers_source import (
    _try_fraction_related_subject_problem,
    _try_fraction_comparison_problem,
    _try_fraction_remainder_of_whole_problem,
    _try_fraction_of_remainder_problem,
    _try_fraction_relative_change_problem,
    _try_fraction_then_change_problem,
    _try_number_by_fraction,
    _try_fraction_change_problem,
)


__all__ = ['_try_fraction_related_subject_problem', '_try_fraction_comparison_problem', '_try_fraction_remainder_of_whole_problem', '_try_fraction_of_remainder_problem', '_try_fraction_relative_change_problem', '_try_fraction_then_change_problem', '_try_number_by_fraction', '_try_fraction_change_problem']
