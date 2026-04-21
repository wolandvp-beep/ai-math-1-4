from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

FRACTION_HANDLER_NAMES = (
    '_try_fraction_related_subject_problem',
    '_try_fraction_comparison_problem',
    '_try_fraction_of_remainder_problem',
    '_try_fraction_remainder_of_whole_problem',
    '_try_fraction_relative_change_problem',
    '_try_fraction_then_change_problem',
    '_try_fraction_change_problem',
    '_try_number_by_fraction',
)

FRACTION_HANDLERS = available_group_handlers(FRACTION_HANDLER_NAMES)


def resolve_fraction_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, FRACTION_HANDLERS)


def build_fraction_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, FRACTION_HANDLERS, 'legacy-fraction')


__all__ = [
    'FRACTION_HANDLER_NAMES',
    'FRACTION_HANDLERS',
    'resolve_fraction_word_problem',
    'build_fraction_word_problem_payload',
]
