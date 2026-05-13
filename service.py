from __future__ import annotations

from backend.expression_engine import build_explanation
from backend.postprocess import clean_result_payload
from backend.text_utils import NON_MATH_REPLY, looks_like_math_input
from backend.platform.request_shape_guards import build_multi_task_payload, canonicalize_system_submission, is_multi_task_submission


def validate_user_text(user_text: str):
    user_text = (user_text or '').strip()
    if not user_text:
        return False, {"error": "Пустой текст задачи"}
    if len(user_text) > 2000:
        return False, {"error": "Текст задачи слишком длинный"}
    return True, user_text


def get_non_math_response() -> dict:
    return {"result": NON_MATH_REPLY, "source": "guard", "validated": True}


def prevalidate_explanation_request(user_text: str) -> dict | None:
    ok, payload = validate_user_text(user_text)
    if not ok:
        return payload
    if not looks_like_math_input(payload):
        return clean_result_payload(get_non_math_response())
    # Multiple standalone examples/equations in one request are not solved as a batch.
    # They are guarded before the general solver so newline loss can never glue
    # digits into a false single expression (for example, 2+2 + 32-8).
    # True systems of equations are excluded inside is_multi_task_submission().
    if is_multi_task_submission(payload):
        return clean_result_payload(build_multi_task_payload(payload))
    return None


async def generate_explanation_response(user_text: str) -> dict:
    prevalidated = prevalidate_explanation_request(user_text)
    if prevalidated is not None:
        return prevalidated
    _, payload = validate_user_text(user_text)
    # Several equations with shared variables are one system, not several separate examples.
    # Canonicalize them before the general solver so they are not mistaken for a batch.
    system_payload = canonicalize_system_submission(payload)
    if system_payload is not None:
        payload = 'Система уравнений:\n' + system_payload
    result = await build_explanation(payload)
    return clean_result_payload(result)
