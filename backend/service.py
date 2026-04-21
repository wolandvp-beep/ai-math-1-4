from __future__ import annotations

from .expression_engine import build_explanation
from .postprocess import clean_result_payload
from .text_utils import NON_MATH_REPLY, looks_like_math_input


def validate_user_text(user_text: str):
    user_text = (user_text or '').strip()
    if not user_text:
        return False, {"error": "Пустой текст задачи"}
    if len(user_text) > 2000:
        return False, {"error": "Текст задачи слишком длинный"}
    return True, user_text


def get_non_math_response() -> dict:
    return {"result": NON_MATH_REPLY, "source": "guard", "validated": True}


async def generate_explanation_response(user_text: str) -> dict:
    ok, payload = validate_user_text(user_text)
    if not ok:
        return payload
    if not looks_like_math_input(payload):
        return clean_result_payload(get_non_math_response())
    result = await build_explanation(payload)
    return clean_result_payload(result)
