from __future__ import annotations

from .guards import division_by_zero_payload, is_direct_division_by_zero
from .handlers.change_word_problems import build_change_word_problem_payload
from .handlers.fraction_word_problems import build_fraction_word_problem_payload
from .handlers.geometry_word_problems import build_geometry_word_problem_payload
from .handlers.motion_word_problems import build_motion_word_problem_payload
from .handlers.purchase_word_problems import build_purchase_word_problem_payload
from .handlers.quantity_word_problems import build_quantity_word_problem_payload
from .handlers.relation_word_problems import build_relation_word_problem_payload
from .handlers.dual_subject_word_problems import build_dual_subject_word_problem_payload
from .handlers.verbal_arithmetic_word_problems import build_verbal_arithmetic_word_problem_payload
from .legacy_bridge import build_legacy_explanation, format_local_solution
from .legacy_ai_handlers import build_legacy_explanatory_math_payload
from .legacy_fallback_handlers import build_legacy_external_fallback_payload
from .math_expression_engine import build_direct_math_expression_payload
from .patch_registry import resolve_local_explanation


async def dispatch_explanation(user_text: str) -> dict:
    if is_direct_division_by_zero(user_text):
        return division_by_zero_payload()

    local_explanation, handler_name, preformatted = resolve_local_explanation(user_text)
    if local_explanation:
        formatted = format_local_solution(user_text, local_explanation, preformatted=preformatted)
        return {
            'result': formatted,
            'source': f'local:{handler_name}',
            'validated': True,
        }

    motion_word_problem = build_motion_word_problem_payload(user_text)
    if motion_word_problem:
        return motion_word_problem

    purchase_word_problem = build_purchase_word_problem_payload(user_text)
    if purchase_word_problem:
        return purchase_word_problem

    change_word_problem = build_change_word_problem_payload(user_text)
    if change_word_problem:
        return change_word_problem

    geometry_word_problem = build_geometry_word_problem_payload(user_text)
    if geometry_word_problem:
        return geometry_word_problem

    fraction_word_problem = build_fraction_word_problem_payload(user_text)
    if fraction_word_problem:
        return fraction_word_problem

    quantity_word_problem = build_quantity_word_problem_payload(user_text)
    if quantity_word_problem:
        return quantity_word_problem

    relation_word_problem = build_relation_word_problem_payload(user_text)
    if relation_word_problem:
        return relation_word_problem

    dual_subject_word_problem = build_dual_subject_word_problem_payload(user_text)
    if dual_subject_word_problem:
        return dual_subject_word_problem

    verbal_arithmetic_word_problem = build_verbal_arithmetic_word_problem_payload(user_text)
    if verbal_arithmetic_word_problem:
        return verbal_arithmetic_word_problem

    direct_math_expression = build_direct_math_expression_payload(user_text)
    if direct_math_expression:
        return direct_math_expression

    legacy_external_fallback = await build_legacy_external_fallback_payload(user_text)
    if legacy_external_fallback:
        return legacy_external_fallback

    legacy_explanatory_math = await build_legacy_explanatory_math_payload(user_text)
    if legacy_explanatory_math:
        return legacy_explanatory_math

    return await build_legacy_explanation(user_text)
