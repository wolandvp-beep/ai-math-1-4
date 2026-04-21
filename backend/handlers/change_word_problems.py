from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

CHANGE_HANDLER_NAMES = (
    '_try_difference_after_change_problem',
    '_try_ratio_after_change_problem',
    '_try_reverse_transfer_problem',
    '_try_reverse_transfer_relation_problem',
    '_try_reverse_transfer_total_problem',
    '_try_reverse_transfer_mixed_total_problem',
    '_try_reverse_sequential_change_problem',
    '_try_sequential_change_word_problem',
    '_try_find_initial_number_after_change',
    '_try_find_initial_number_after_two_changes',
)

CHANGE_HANDLERS = available_group_handlers(CHANGE_HANDLER_NAMES)


def resolve_change_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, CHANGE_HANDLERS)


def build_change_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, CHANGE_HANDLERS, 'legacy-change')


__all__ = [
    'CHANGE_HANDLER_NAMES',
    'CHANGE_HANDLERS',
    'resolve_change_word_problem',
    'build_change_word_problem_payload',
]
