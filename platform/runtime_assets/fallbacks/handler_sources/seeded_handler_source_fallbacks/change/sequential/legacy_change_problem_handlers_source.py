from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_change_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_change_problem_handlers_source import (
    _try_reverse_sequential_change_problem,
    _try_sequential_change_word_problem,
    _try_find_initial_number_after_two_changes,
    _try_find_initial_number_after_change,
    _try_ratio_after_change_problem,
    _try_difference_after_change_problem,
)


__all__ = ['_try_reverse_sequential_change_problem', '_try_sequential_change_word_problem', '_try_find_initial_number_after_two_changes', '_try_find_initial_number_after_change', '_try_ratio_after_change_problem', '_try_difference_after_change_problem']
