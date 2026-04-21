from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

DUAL_SUBJECT_HANDLER_NAMES = (
    '_try_reverse_dual_subject_measured_equality_after_changes_problem',
    '_try_reverse_dual_subject_equality_after_changes_problem',
    '_try_dual_subject_measured_after_changes_problem',
    '_try_dual_subject_money_after_changes_problem',
    '_try_dual_subject_total_after_changes_problem',
    '_try_dual_subject_comparison_after_changes_problem',
    '_try_reverse_dual_subject_measured_total_relation_after_changes_problem',
    '_try_reverse_dual_subject_measured_total_problem',
    '_try_related_quantity_then_change_total_problem',
    '_try_reverse_dual_subject_total_relation_after_changes_problem',
    '_try_reverse_dual_subject_total_after_changes_problem',
)

DUAL_SUBJECT_HANDLERS = available_group_handlers(DUAL_SUBJECT_HANDLER_NAMES)


def resolve_dual_subject_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, DUAL_SUBJECT_HANDLERS)


def build_dual_subject_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, DUAL_SUBJECT_HANDLERS, 'legacy-dual-subject')


__all__ = [
    'DUAL_SUBJECT_HANDLER_NAMES',
    'DUAL_SUBJECT_HANDLERS',
    'resolve_dual_subject_word_problem',
    'build_dual_subject_word_problem_payload',
]
