from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

RELATION_HANDLER_NAMES = (
    '_try_sum_unknown_part_problem',
    '_try_difference_unknown_component_problem',
    '_try_post_change_equal_parts_problem',
    '_try_distribution_subset_problem',
    '_try_times_related_subject_problem',
    '_try_equal_parts_problem',
)

RELATION_HANDLERS = available_group_handlers(RELATION_HANDLER_NAMES)


def resolve_relation_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, RELATION_HANDLERS)


def build_relation_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, RELATION_HANDLERS, 'legacy-relation')


__all__ = [
    'RELATION_HANDLER_NAMES',
    'RELATION_HANDLERS',
    'resolve_relation_word_problem',
    'build_relation_word_problem_payload',
]
