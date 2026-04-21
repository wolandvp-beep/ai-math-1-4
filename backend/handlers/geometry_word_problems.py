from __future__ import annotations

from .legacy_groups import available_group_handlers, build_grouped_legacy_payload, resolve_grouped_legacy_problem

GEOMETRY_HANDLER_NAMES = (
    '_try_rectangle_geometry',
    '_try_square_geometry',
    '_try_triangle_perimeter',
)

GEOMETRY_HANDLERS = available_group_handlers(GEOMETRY_HANDLER_NAMES)


def resolve_geometry_word_problem(raw_text: str):
    return resolve_grouped_legacy_problem(raw_text, GEOMETRY_HANDLERS)


def build_geometry_word_problem_payload(raw_text: str):
    return build_grouped_legacy_payload(raw_text, GEOMETRY_HANDLERS, 'legacy-geometry')


__all__ = [
    'GEOMETRY_HANDLER_NAMES',
    'GEOMETRY_HANDLERS',
    'resolve_geometry_word_problem',
    'build_geometry_word_problem_payload',
]
