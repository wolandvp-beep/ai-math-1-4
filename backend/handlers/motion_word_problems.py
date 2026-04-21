from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

MOTION_HANDLER_NAMES = (
    '_try_clock_duration_problem',
    '_try_relative_motion_distance',
    '_try_simple_motion',
)

MOTION_HANDLERS = available_group_handlers(MOTION_HANDLER_NAMES)


def resolve_motion_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, MOTION_HANDLERS)


def build_motion_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, MOTION_HANDLERS, 'legacy-motion')


__all__ = [
    'MOTION_HANDLER_NAMES',
    'MOTION_HANDLERS',
    'resolve_motion_word_problem',
    'build_motion_word_problem_payload',
]
