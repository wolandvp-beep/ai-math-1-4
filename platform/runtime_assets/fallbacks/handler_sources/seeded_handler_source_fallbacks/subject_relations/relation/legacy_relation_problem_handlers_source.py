from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_relation_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_relation_problem_handlers_source import (
    _try_sum_unknown_part_problem,
    _try_difference_unknown_component_problem,
    _try_distribution_subset_problem,
    _try_post_change_equal_parts_problem,
    _try_equal_parts_problem,
)


__all__ = ['_try_sum_unknown_part_problem', '_try_difference_unknown_component_problem', '_try_distribution_subset_problem', '_try_post_change_equal_parts_problem', '_try_equal_parts_problem']
