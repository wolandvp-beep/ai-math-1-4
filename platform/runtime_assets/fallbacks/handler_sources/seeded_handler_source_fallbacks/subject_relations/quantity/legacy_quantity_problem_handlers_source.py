from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_quantity_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_quantity_problem_handlers_source import (
    _try_age_difference_problem,
    _try_mass_problem,
    _try_reverse_measured_change_problem,
    _try_measured_change_problem,
    _try_temperature_change_problem,
    _try_measure_difference_problem,
)


__all__ = ['_try_age_difference_problem', '_try_mass_problem', '_try_reverse_measured_change_problem', '_try_measured_change_problem', '_try_temperature_change_problem', '_try_measure_difference_problem']
