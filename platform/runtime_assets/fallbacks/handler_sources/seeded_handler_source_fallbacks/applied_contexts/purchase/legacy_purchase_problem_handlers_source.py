from __future__ import annotations

"""Seeded-exec compatibility fallback for legacy_purchase_problem_handlers_source.py.

This module intentionally re-exports the materialized handler-source fallback
functions, so the final seeded-exec branch stays importable and does not depend
on incomplete raw snippets.
"""

from backend.materialized_handler_source_fallbacks.legacy_purchase_problem_handlers_source import (
    _try_reverse_money_purchase_problem,
    _try_money_purchase_flow_problem,
    _try_unit_price_purchase_problem,
    _try_direct_price_problem,
)


__all__ = ['_try_reverse_money_purchase_problem', '_try_money_purchase_flow_problem', '_try_unit_price_purchase_problem', '_try_direct_price_problem']
