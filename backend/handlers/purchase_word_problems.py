from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

PURCHASE_HANDLER_NAMES = (
    '_try_reverse_money_purchase_problem',
    '_try_money_purchase_flow_problem',
    '_try_unit_price_purchase_problem',
    '_try_direct_price_problem',
)

PURCHASE_HANDLERS = available_group_handlers(PURCHASE_HANDLER_NAMES)


def resolve_purchase_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, PURCHASE_HANDLERS)


def build_purchase_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, PURCHASE_HANDLERS, 'legacy-purchase')


__all__ = [
    'PURCHASE_HANDLER_NAMES',
    'PURCHASE_HANDLERS',
    'resolve_purchase_word_problem',
    'build_purchase_word_problem_payload',
]
