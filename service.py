from __future__ import annotations

from backend.expression_engine import build_explanation
from backend.postprocess import clean_result_payload
from backend.text_utils import NON_MATH_REPLY, looks_like_math_input
from backend.platform.request_shape_guards import build_multi_task_payload, canonicalize_system_submission, is_multi_task_submission
from backend.live_math_solver import solve_live_math_first

APP_RELEASE = 'v280_external_blackbox_audit_wave1_grade1_2_basics'
SOLVER_VERSION = 'v280-external-blackbox-wave1-grade1-2-structural-solvers'

_BAD_INTERNAL_MARKERS = (
    'Zad3',
    'deterministic regression',
    'answer map',
    'lookup',
    'Применяем правило:',
    'generic fallback',
)


def attach_release(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out.setdefault('release', APP_RELEASE)
    out.setdefault('solverVersion', SOLVER_VERSION)
    return out


def _looks_like_complex_word_problem(text: str) -> bool:
    src = str(text or '').lower()
    return ('?' in src and len(src) > 45 and any(word in src for word in (
        'сколько', 'за сколько', 'на сколько', 'во сколько', 'остал', 'вместе', 'скорост',
        'поле', 'работая', 'по ', 'руб', 'коп', 'км', 'час', 'дн', 'ар', 'тонн',
    )))


def _is_unsafe_generic_payload(payload: dict, text: str) -> bool:
    result = str(payload.get('result') or '')
    source = str(payload.get('source') or '')
    if any(marker.lower() in result.lower() for marker in _BAD_INTERNAL_MARKERS):
        return True
    if source.startswith(('fallback', 'legacy-ai')) and _looks_like_complex_word_problem(text):
        return True
    return False


def _low_confidence_payload(text: str) -> dict:
    return {
        'result': (
            'Задача.\n'
            + str(text or '').strip()
            + '\nРешение.\n'
            + 'Я не уверен, что правильно распознал тип этой задачи, поэтому не буду давать предположительный ответ. '
              'Лучше переформулируйте условие или отправьте задачу одним полным предложением без лишних заданий.\n'
            + 'Ответ: нужно уточнить условие задачи.'
        ),
        'source': 'guard-low-confidence',
        'validated': True,
        'code': 'low_confidence_solver',
    }


def validate_user_text(user_text: str):
    user_text = (user_text or '').strip()
    if not user_text:
        return False, {"error": "Пустой текст задачи"}
    if len(user_text) > 2000:
        return False, {"error": "Текст задачи слишком длинный"}
    return True, user_text


def get_non_math_response() -> dict:
    return attach_release({"result": NON_MATH_REPLY, "source": "guard", "validated": True})


def prevalidate_explanation_request(user_text: str) -> dict | None:
    ok, payload = validate_user_text(user_text)
    if not ok:
        return payload
    if not looks_like_math_input(payload):
        return attach_release(clean_result_payload(get_non_math_response()))
    # Multiple standalone examples/equations in one request are not solved as a batch.
    # They are guarded before the general solver so newline loss can never glue
    # digits into a false single expression (for example, 2+2 + 32-8).
    # True systems of equations are excluded inside is_multi_task_submission().
    if is_multi_task_submission(payload):
        return attach_release(clean_result_payload(build_multi_task_payload(payload)))
    return None


async def generate_explanation_response(user_text: str) -> dict:
    prevalidated = prevalidate_explanation_request(user_text)
    if prevalidated is not None:
        return prevalidated
    _, payload = validate_user_text(user_text)
    # High-priority structural live-user solvers run before the broad legacy
    # dispatcher.  This prevents generic fallback rules from producing confident
    # but wrong answers for common grade 2-4 tasks and true 2-variable systems.
    live_payload = solve_live_math_first(payload)
    if live_payload is not None:
        return attach_release(clean_result_payload(live_payload))
    # Several equations with shared variables are one system, not several separate examples.
    # Canonicalize them before the general solver so they are not mistaken for a batch.
    system_payload = canonicalize_system_submission(payload)
    if system_payload is not None:
        payload = 'Система уравнений:\n' + system_payload
        live_payload = solve_live_math_first(payload)
        if live_payload is not None:
            return attach_release(clean_result_payload(live_payload))
    result = await build_explanation(payload)
    result = clean_result_payload(result)
    if _is_unsafe_generic_payload(result, payload):
        return attach_release(clean_result_payload(_low_confidence_payload(payload)))
    return attach_release(result)
