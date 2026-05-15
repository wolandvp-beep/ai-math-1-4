from __future__ import annotations

import json
import os
import re
from typing import Any

from backend.expression_engine import build_explanation
from backend.postprocess import clean_result_payload
from backend.text_utils import NON_MATH_REPLY, looks_like_math_input
from backend.platform.request_shape_guards import build_multi_task_payload, canonicalize_system_submission, is_multi_task_submission
from backend.live_math_solver import solve_live_math_first

APP_RELEASE = 'v289_g1_numbers_values_live_deepseek_audit'
SOLVER_VERSION = 'v289-g1-numbers-values-deepseek-primary-verifier'

_BAD_INTERNAL_MARKERS = (
    'Zad3',
    'deterministic regression',
    'answer map',
    'lookup',
    'Применяем правило:',
    'generic fallback',
)


SOLVER_MODE_DEEPSEEK_PRIMARY = 'deepseek_primary'
SOLVER_MODE_LOCAL_PRIMARY = 'local_primary'
_SOLVER_MODE_OVERRIDE: str | None = None


def set_solver_mode_override(mode: str | None) -> None:
    global _SOLVER_MODE_OVERRIDE
    _SOLVER_MODE_OVERRIDE = str(mode).strip() if mode else None


def resolve_solver_mode(mode: str | None = None) -> str:
    value = str(mode or _SOLVER_MODE_OVERRIDE or os.environ.get('SOLVER_MODE') or SOLVER_MODE_DEEPSEEK_PRIMARY).strip().lower()
    value = value.replace('-', '_')
    if value in {'local', 'local_first', 'local_primary', 'legacy_local'}:
        return SOLVER_MODE_LOCAL_PRIMARY
    return SOLVER_MODE_DEEPSEEK_PRIMARY


def deepseek_api_key_configured() -> bool:
    try:
        import backend.legacy_core as legacy_core
        getter = getattr(legacy_core, '_get_deepseek_api_key', None) or getattr(legacy_core, 'get_deepseek_api_key', None)
        if callable(getter):
            try:
                key = getter(legacy_core.__dict__)
            except TypeError:
                key = getter()
            return bool(str(key or '').strip())
    except Exception:
        pass
    return bool(str(os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip())



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


def _looks_like_programmatic_math_text(text: str) -> bool:
    """Allow official-program prompts that use number words before digits appear."""
    src = str(text or '').lower().replace('ё', 'е')
    return bool(
        ('запиши' in src and 'число' in src and ('цифр' in src or 'цифрами' in src))
        or re.search(r'как\s+читается\s+число\s+\d+', src)
        or re.search(r'сколько\s+чисел', src)
        or ('вычитание' in src and 'провер' in src)
        or ('результат' in src and ('сложен' in src or 'вычитан' in src or '+' in src or '-' in src))
    )


def prevalidate_explanation_request(user_text: str) -> dict | None:
    ok, payload = validate_user_text(user_text)
    if not ok:
        return payload
    if not looks_like_math_input(payload) and not _looks_like_programmatic_math_text(payload):
        return attach_release(clean_result_payload(get_non_math_response()))
    # Multiple standalone examples/equations in one request are not solved as a batch.
    # They are guarded before the general solver so newline loss can never glue
    # digits into a false single expression (for example, 2+2 + 32-8).
    # True systems of equations are excluded inside is_multi_task_submission().
    if is_multi_task_submission(payload):
        return attach_release(clean_result_payload(build_multi_task_payload(payload)))
    return None



def _tag_payload(payload: dict, **extra: Any) -> dict:
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out.update(extra)
    return out


async def _generate_local_primary_response(payload: str) -> dict:
    # Structural local/verifier path kept for guards, math-audit regression and
    # no-key fallback. It is no longer the default user-facing solver in v288.
    live_payload = solve_live_math_first(payload)
    if live_payload is not None:
        return attach_release(clean_result_payload(_tag_payload(live_payload, solverMode=SOLVER_MODE_LOCAL_PRIMARY)))
    system_payload = canonicalize_system_submission(payload)
    if system_payload is not None:
        system_text = 'Система уравнений:\n' + system_payload
        live_payload = solve_live_math_first(system_text)
        if live_payload is not None:
            return attach_release(clean_result_payload(_tag_payload(live_payload, solverMode=SOLVER_MODE_LOCAL_PRIMARY)))
        payload = system_text
    result = await build_explanation(payload)
    result = clean_result_payload(result)
    if _is_unsafe_generic_payload(result, payload):
        return attach_release(clean_result_payload(_low_confidence_payload(payload)))
    return attach_release(_tag_payload(result, solverMode=SOLVER_MODE_LOCAL_PRIMARY))


def _normalize_deepseek_result_text(result: str) -> str:
    lines: list[str] = []
    for raw_line in str(result or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith(('совет:', 'подсказка:', 'конечно', 'давайте')):
            continue
        if low.startswith('ответ:') and line[-1:] not in '.!?':
            line += '.'
        lines.append(line)
    # Keep the stable product template and avoid trailing technical/extra prose.
    return '\n'.join(lines).strip()


def _postprocess_deepseek_primary_payload(payload: dict, original_text: str) -> dict:
    cleaned = clean_result_payload(payload)
    result = _normalize_deepseek_result_text(str(cleaned.get('result') or '').strip())
    cleaned['result'] = result
    source = str(cleaned.get('source') or '')
    if not result or 'Ответ:' not in result:
        return attach_release(_tag_payload(_low_confidence_payload(original_text), source='deepseek-primary-invalid-format', solverMode=SOLVER_MODE_DEEPSEEK_PRIMARY))
    if any(marker.lower() in result.lower() for marker in _BAD_INTERNAL_MARKERS):
        return attach_release(_tag_payload(_low_confidence_payload(original_text), source='deepseek-primary-forbidden-marker', solverMode=SOLVER_MODE_DEEPSEEK_PRIMARY))
    return attach_release(_tag_payload(cleaned, source=source or 'deepseek-primary', solverMode=SOLVER_MODE_DEEPSEEK_PRIMARY, verifier='local-postprocess'))


def _parse_json_object(text: Any) -> dict[str, Any] | None:
    raw = str(text or '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        start = raw.find('{')
        end = raw.rfind('}')
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start:end + 1])
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _deepseek_primary_payload(user_text: str) -> dict[str, Any]:
    system_prompt = """Ты решаешь задания по математике для российской начальной школы 1–4 класса.
Верни только JSON object, без markdown и без текста вне JSON.
Стиль: короткое школьное решение для ребёнка. Не добавляй приветствия, советы, рассуждения о себе.
Решай ровно одно задание. Если в сообщении несколько отдельных заданий, верни cannot_safely_solve=true.
Обязательно сохрани смысл вопроса: «на сколько» = вычитание, «во сколько раз» = деление, «сколько всего/вместе/стало» = итоговая величина.
Формат JSON:
{
  "known": "что известно, коротко",
  "find": "что надо найти, коротко",
  "steps": ["9 + 4 = 13"],
  "answer_number": "13",
  "answer_unit": "шаров",
  "final_answer": "13 шаров",
  "cannot_safely_solve": false,
  "reason": ""
}
Если единицы нет, answer_unit может быть пустой строкой. Шаги должны содержать арифметические равенства."""
    return {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': 'Реши задачу и верни только JSON. Задача: ' + str(user_text or '').strip()},
        ],
        'response_format': {'type': 'json_object'},
        'max_tokens': 900,
        'temperature': 0.0,
    }


def _format_deepseek_primary_solution(parsed: dict[str, Any], original_text: str) -> dict | None:
    if parsed.get('cannot_safely_solve'):
        return None
    steps_raw = parsed.get('steps')
    if not isinstance(steps_raw, list):
        return None
    steps: list[str] = []
    for raw in steps_raw:
        step = str(raw or '').strip()
        if step:
            steps.append(step)
    if not steps:
        return None
    answer_number = str(parsed.get('answer_number') or '').strip()
    answer_unit = str(parsed.get('answer_unit') or '').strip()
    final_answer = str(parsed.get('final_answer') or '').strip()
    if not final_answer:
        final_answer = (answer_number + (' ' + answer_unit if answer_unit else '')).strip()
    if not final_answer:
        return None
    lines = ['Задача.', str(original_text or '').strip(), 'Решение.']
    for idx, step in enumerate(steps, start=1):
        step = re.sub(r'^\s*\d+[\).]\s*', '', step).strip()
        if step and step[-1:] not in '.!?':
            step += '.'
        lines.append(f'{idx}) {step}')
    if final_answer[-1:] not in '.!?':
        final_answer += '.'
    lines.append('Ответ: ' + final_answer)
    return {
        'result': '\n'.join(lines),
        'source': 'deepseek-primary',
        'validated': True,
        'structured_solution': {
            'known': str(parsed.get('known') or '').strip(),
            'find': str(parsed.get('find') or '').strip(),
            'steps': steps,
            'answer_number': answer_number,
            'answer_unit': answer_unit,
            'final_answer': final_answer.rstrip('.'),
        },
    }


async def _call_deepseek_primary(payload: str) -> dict | None:
    import backend.legacy_core as legacy_core
    call_deepseek = getattr(legacy_core, 'call_deepseek', None)
    if not callable(call_deepseek) or not deepseek_api_key_configured():
        return None
    getter = getattr(legacy_core, '_get_deepseek_api_key', None) or getattr(legacy_core, 'get_deepseek_api_key', None)
    try:
        api_key = getter(legacy_core.__dict__) if callable(getter) else ''
    except TypeError:
        api_key = getter() if callable(getter) else ''
    api_key = str(api_key or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('myapp_ai_math_1_4_API_key') or '').strip()
    previous_key = getattr(legacy_core, 'DEEPSEEK_API_KEY', '')
    setattr(legacy_core, 'DEEPSEEK_API_KEY', api_key)
    try:
        llm_result = await call_deepseek(_deepseek_primary_payload(payload), timeout_seconds=25.0)
    finally:
        setattr(legacy_core, 'DEEPSEEK_API_KEY', previous_key)
    if not isinstance(llm_result, dict) or llm_result.get('error'):
        return None
    parsed = _parse_json_object(llm_result.get('result'))
    if not parsed:
        return None
    return _format_deepseek_primary_solution(parsed, payload)


async def _generate_deepseek_primary_response(payload: str, *, allow_external: bool = True) -> dict:
    if not allow_external:
        return attach_release({
            'result': (
                'Задача.\n' + str(payload or '').strip() + '\nРешение.\n'
                'Для этой проверки внешний DeepSeek API запрещён, поэтому задача не решалась.\n'
                'Ответ: внешний API заблокирован.'
            ),
            'source': 'deepseek-primary-external-blocked',
            'validated': True,
            'solverMode': SOLVER_MODE_DEEPSEEK_PRIMARY,
            'externalApiBlocked': True,
        })
    try:
        ai_payload = await _call_deepseek_primary(payload)
    except Exception as exc:
        local_payload = await _generate_local_primary_response(payload)
        return attach_release(_tag_payload(local_payload, solverMode=SOLVER_MODE_DEEPSEEK_PRIMARY, deepseekPrimaryFallback='deepseek_exception', deepseekError=str(exc)[:300]))
    if isinstance(ai_payload, dict) and ai_payload.get('result'):
        return _postprocess_deepseek_primary_payload(ai_payload, payload)
    local_payload = await _generate_local_primary_response(payload)
    fallback_reason = 'deepseek_invalid_or_empty' if deepseek_api_key_configured() else 'no_api_key_or_no_helper'
    return attach_release(_tag_payload(local_payload, solverMode=SOLVER_MODE_DEEPSEEK_PRIMARY, deepseekPrimaryFallback=fallback_reason))


async def generate_explanation_response(user_text: str, *, solver_mode: str | None = None, allow_external: bool = True) -> dict:
    prevalidated = prevalidate_explanation_request(user_text)
    if prevalidated is not None:
        return prevalidated
    _, payload = validate_user_text(user_text)
    mode = resolve_solver_mode(solver_mode)
    if mode == SOLVER_MODE_LOCAL_PRIMARY:
        return await _generate_local_primary_response(payload)
    return await _generate_deepseek_primary_response(payload, allow_external=allow_external)
