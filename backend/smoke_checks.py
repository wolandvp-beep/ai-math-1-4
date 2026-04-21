from __future__ import annotations

from .explanation_dispatcher import dispatch_explanation
from .expression_parser import extract_simple_binary_operation
from .guards import division_by_zero_payload, is_direct_division_by_zero, looks_like_math_input
from .handlers.change_word_problems import resolve_change_word_problem
from .handlers.column_math import get_column_operation
from .math_expression_engine import build_direct_math_expression_payload
from .math_explainers import explain_simple_addition, explain_column_addition
from .handlers.fraction_word_problems import resolve_fraction_word_problem
from .handlers.geometry_word_problems import resolve_geometry_word_problem
from .handlers.legacy_word_problems import resolve_legacy_word_problem
from .handlers.motion_word_problems import resolve_motion_word_problem
from .handlers.purchase_word_problems import resolve_purchase_word_problem
from .handlers.quantity_word_problems import resolve_quantity_word_problem
from .handlers.relation_word_problems import resolve_relation_word_problem
from .handlers.dual_subject_word_problems import resolve_dual_subject_word_problem
from .handlers.verbal_arithmetic_word_problems import resolve_verbal_arithmetic_word_problem
from .input_normalization import normalize_solver_input, strip_solver_command_prefix
from .legacy_ai_handlers import build_legacy_explanatory_math_payload, build_legacy_generic_math_payload
from .legacy_explanatory_ai import _looks_like_explanatory_math_question
from .legacy_fallback_handlers import build_legacy_external_fallback_payload
from .legacy_safe_responses import safe_cannot_reliably_solve_math
from .patch_registry import resolve_local_explanation
from .text_utils import infer_task_kind, normalize_word_problem_text


def _serialize_binary_operation(operation):
    if not operation:
        return None
    return {
        'left': operation.left,
        'operator': operation.operator,
        'right': operation.right,
    }


def smoke_probe(text: str) -> dict:
    local_explanation, handler_name, preformatted = resolve_local_explanation(text)
    motion_explanation, motion_handler_name = resolve_motion_word_problem(text)
    purchase_explanation, purchase_handler_name = resolve_purchase_word_problem(text)
    change_explanation, change_handler_name = resolve_change_word_problem(text)
    geometry_explanation, geometry_handler_name = resolve_geometry_word_problem(text)
    fraction_explanation, fraction_handler_name = resolve_fraction_word_problem(text)
    quantity_explanation, quantity_handler_name = resolve_quantity_word_problem(text)
    relation_explanation, relation_handler_name = resolve_relation_word_problem(text)
    dual_subject_explanation, dual_subject_handler_name = resolve_dual_subject_word_problem(text)
    verbal_arithmetic_explanation, verbal_arithmetic_handler_name = resolve_verbal_arithmetic_word_problem(text)
    legacy_local_explanation, legacy_handler_name, normalized = resolve_legacy_word_problem(text)
    binary_operation = extract_simple_binary_operation(text)
    column_operation = get_column_operation(text)
    direct_math_expression = build_direct_math_expression_payload(text)
    legacy_external_fallback = None
    return {
        'looks_like_math_input': looks_like_math_input(text),
        'task_kind': infer_task_kind(text),
        'normalized_word_problem_text': normalize_word_problem_text(text),
        'strip_solver_command_prefix': strip_solver_command_prefix(text),
        'normalize_solver_input': normalize_solver_input(text),
        'is_direct_division_by_zero': is_direct_division_by_zero(text),
        'binary_operation': _serialize_binary_operation(binary_operation),
        'column_operation': _serialize_binary_operation(column_operation),
        'direct_math_expression': direct_math_expression.get('source') if direct_math_expression else None,
        'math_explainers_sample': {
            'simple_addition': explain_simple_addition(2, 3),
            'column_addition': explain_column_addition([405, 70]),
        },
        'mixed_expression_steps': direct_math_expression.get('step_count') if direct_math_expression else None,
        'legacy_safe_response_sample': safe_cannot_reliably_solve_math('Сколько стоят 3 тетради по 7 руб?'),
        'legacy_explanatory_probe': _looks_like_explanatory_math_question(text),
        'local_handler': handler_name if local_explanation else None,
        'motion_handler': motion_handler_name if motion_explanation else None,
        'purchase_handler': purchase_handler_name if purchase_explanation else None,
        'change_handler': change_handler_name if change_explanation else None,
        'geometry_handler': geometry_handler_name if geometry_explanation else None,
        'fraction_handler': fraction_handler_name if fraction_explanation else None,
        'quantity_handler': quantity_handler_name if quantity_explanation else None,
        'relation_handler': relation_handler_name if relation_explanation else None,
        'dual_subject_handler': dual_subject_handler_name if dual_subject_explanation else None,
        'verbal_arithmetic_handler': verbal_arithmetic_handler_name if verbal_arithmetic_explanation else None,
        'legacy_local_handler': legacy_handler_name if legacy_local_explanation else None,
        'legacy_local_normalized_input': normalized if legacy_local_explanation else None,
        'preformatted': preformatted,
    }


async def smoke_external_fallback(text: str) -> dict | None:
    return await build_legacy_external_fallback_payload(text)


async def smoke_explanatory_math(text: str) -> dict | None:
    return await build_legacy_explanatory_math_payload(text)


async def smoke_generic_math(text: str) -> dict | None:
    return await build_legacy_generic_math_payload(text)


async def smoke_dispatch(text: str) -> dict:
    return await dispatch_explanation(text)


__all__ = [
    'dispatch_explanation',
    'division_by_zero_payload',
    'extract_simple_binary_operation',
    'is_direct_division_by_zero',
    'looks_like_math_input',
    'get_column_operation',
    'resolve_change_word_problem',
    'resolve_fraction_word_problem',
    'resolve_geometry_word_problem',
    'resolve_legacy_word_problem',
    'resolve_motion_word_problem',
    'resolve_purchase_word_problem',
    'resolve_quantity_word_problem',
    'resolve_relation_word_problem',
    'resolve_dual_subject_word_problem',
    'resolve_verbal_arithmetic_word_problem',
    'build_direct_math_expression_payload',
    'resolve_local_explanation',
    'build_legacy_external_fallback_payload',
    'build_legacy_explanatory_math_payload',
    'build_legacy_generic_math_payload',
    'safe_cannot_reliably_solve_math',
    'smoke_probe',
    'smoke_external_fallback',
    'smoke_explanatory_math',
    'smoke_generic_math',
    'smoke_dispatch',
]


if __name__ == '__main__':
    pass
