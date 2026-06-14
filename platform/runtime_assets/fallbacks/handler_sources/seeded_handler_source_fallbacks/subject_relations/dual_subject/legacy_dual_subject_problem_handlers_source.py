from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_dual_subject_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_dual_subject_problem_handlers_source import (
    _try_dual_subject_money_after_changes_problem,
    _try_dual_subject_measured_after_changes_problem,
    _try_related_quantity_then_change_total_problem,
    _try_dual_subject_total_after_changes_problem,
    _try_dual_subject_comparison_after_changes_problem,
)


__all__ = ['_try_dual_subject_money_after_changes_problem', '_try_dual_subject_measured_after_changes_problem', '_try_related_quantity_then_change_total_problem', '_try_dual_subject_total_after_changes_problem', '_try_dual_subject_comparison_after_changes_problem']
