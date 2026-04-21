from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..input_normalization import normalize_solver_input
from ..legacy_bridge import expose_core
from .change_word_problems import CHANGE_HANDLER_NAMES
from .fraction_word_problems import FRACTION_HANDLER_NAMES
from .geometry_word_problems import GEOMETRY_HANDLER_NAMES
from .motion_word_problems import MOTION_HANDLER_NAMES
from .purchase_word_problems import PURCHASE_HANDLER_NAMES
from .quantity_word_problems import QUANTITY_HANDLER_NAMES
from .relation_word_problems import RELATION_HANDLER_NAMES
from .dual_subject_word_problems import DUAL_SUBJECT_HANDLER_NAMES
from .verbal_arithmetic_word_problems import VERBAL_ARITHMETIC_HANDLER_NAMES


@dataclass(frozen=True)
class LegacyWordProblemHandler:
    name: str
    func: Callable[[str], Optional[str]]


LEGACY_WORD_PROBLEM_HANDLER_NAMES = (
    '_try_rectangle_geometry',
    '_try_square_geometry',
    '_try_triangle_perimeter',
    '_try_sum_unknown_part_problem',
    '_try_difference_unknown_component_problem',
    '_try_post_change_equal_parts_problem',
    '_try_distribution_subset_problem',
    '_try_times_related_subject_problem',
    '_try_fraction_related_subject_problem',
    '_try_fraction_comparison_problem',
    '_try_fraction_of_remainder_problem',
    '_try_fraction_remainder_of_whole_problem',
    '_try_fraction_relative_change_problem',
    '_try_fraction_then_change_problem',
    '_try_fraction_change_problem',
    '_try_equal_parts_problem',
    '_try_temperature_change_problem',
    '_try_reverse_dual_subject_measured_equality_after_changes_problem',
    '_try_reverse_dual_subject_equality_after_changes_problem',
    '_try_dual_subject_measured_after_changes_problem',
    '_try_dual_subject_money_after_changes_problem',
    '_try_measure_difference_problem',
    '_try_dual_subject_total_after_changes_problem',
    '_try_dual_subject_comparison_after_changes_problem',
    '_try_mass_problem',
    '_try_reverse_dual_subject_measured_total_relation_after_changes_problem',
    '_try_reverse_dual_subject_measured_total_problem',
    '_try_reverse_measured_change_problem',
    '_try_measured_change_problem',
    '_try_age_difference_problem',
    '_try_related_quantity_then_change_total_problem',
    '_try_reverse_dual_subject_total_relation_after_changes_problem',
    '_try_reverse_dual_subject_total_after_changes_problem',
    '_try_simple_verbal_arithmetic',
    '_try_number_by_fraction',
)

_GROUPED_HANDLER_NAMES = frozenset(
    MOTION_HANDLER_NAMES
    + PURCHASE_HANDLER_NAMES
    + CHANGE_HANDLER_NAMES
    + GEOMETRY_HANDLER_NAMES
    + FRACTION_HANDLER_NAMES
    + QUANTITY_HANDLER_NAMES
    + RELATION_HANDLER_NAMES
    + DUAL_SUBJECT_HANDLER_NAMES
    + VERBAL_ARITHMETIC_HANDLER_NAMES
)

LEGACY_WORD_PROBLEM_HANDLER_NAMES = tuple(
    name for name in LEGACY_WORD_PROBLEM_HANDLER_NAMES if name not in _GROUPED_HANDLER_NAMES
)


def _available_handlers() -> tuple[LegacyWordProblemHandler, ...]:
    core = expose_core()
    handlers: list[LegacyWordProblemHandler] = []
    for name in LEGACY_WORD_PROBLEM_HANDLER_NAMES:
        func = getattr(core, name, None)
        if callable(func):
            handlers.append(LegacyWordProblemHandler(name=name.removeprefix('_try_'), func=func))
    return tuple(handlers)


LEGACY_WORD_PROBLEM_HANDLERS = _available_handlers()



def resolve_legacy_word_problem(raw_text: str) -> tuple[Optional[str], Optional[str], str]:
    normalized = normalize_solver_input(raw_text)
    for handler in LEGACY_WORD_PROBLEM_HANDLERS:
        try:
            result = handler.func(normalized)
        except Exception:
            continue
        if result:
            return result, handler.name, normalized
    return None, None, normalized



def build_legacy_word_problem_payload(raw_text: str) -> Optional[dict]:
    explanation, handler_name, normalized = resolve_legacy_word_problem(raw_text)
    if not explanation:
        return None
    return {
        'result': explanation,
        'source': f'legacy-local:{handler_name}',
        'validated': True,
        'normalized_input': normalized,
    }


__all__ = [
    'LEGACY_WORD_PROBLEM_HANDLER_NAMES',
    'LEGACY_WORD_PROBLEM_HANDLERS',
    'build_legacy_word_problem_payload',
    'resolve_legacy_word_problem',
]
