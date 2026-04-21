from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

VERBAL_ARITHMETIC_HANDLER_NAMES = (
    '_try_simple_verbal_arithmetic',
)

VERBAL_ARITHMETIC_HANDLERS = available_group_handlers(VERBAL_ARITHMETIC_HANDLER_NAMES)


def resolve_verbal_arithmetic_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, VERBAL_ARITHMETIC_HANDLERS)


def build_verbal_arithmetic_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, VERBAL_ARITHMETIC_HANDLERS, 'legacy-verbal-arithmetic')


__all__ = [
    'VERBAL_ARITHMETIC_HANDLER_NAMES',
    'VERBAL_ARITHMETIC_HANDLERS',
    'resolve_verbal_arithmetic_word_problem',
    'build_verbal_arithmetic_word_problem_payload',
]
