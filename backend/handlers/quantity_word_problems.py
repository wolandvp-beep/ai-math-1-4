from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

QUANTITY_HANDLER_NAMES = (
    '_try_temperature_change_problem',
    '_try_measure_difference_problem',
    '_try_mass_problem',
    '_try_reverse_measured_change_problem',
    '_try_measured_change_problem',
    '_try_age_difference_problem',
)

QUANTITY_HANDLERS = available_group_handlers(QUANTITY_HANDLER_NAMES)


def resolve_quantity_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, QUANTITY_HANDLERS)


def build_quantity_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, QUANTITY_HANDLERS, 'legacy-quantity')


__all__ = [
    'QUANTITY_HANDLER_NAMES',
    'QUANTITY_HANDLERS',
    'resolve_quantity_word_problem',
    'build_quantity_word_problem_payload',
]
