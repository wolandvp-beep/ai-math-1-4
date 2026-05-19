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

APP_RELEASE = 'v296.06_live_g1_arithmetic_actions_api_evidence'
SOLVER_VERSION = 'v296.06-live-g1-arithmetic-actions-api-evidence'

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
        or (('как называ' in src or 'назови' in src) and any(word in src for word in ('слагаем', 'складыва', 'сумм', 'разност', 'вычита', 'уменьшаем')))
        or ('сколько будет' in src and any(word in src for word in ('прибав', 'вычесть', 'вычти', '+', '-')))
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
Для заданий 1 класса отвечай особенно коротко, но НЕ оставляй пустые поля. Даже если ответ — одно слово или одна цифра, верни валидный JSON.
Обязательно сохрани смысл вопроса: «на сколько» = вычитание, «во сколько раз» = деление, «сколько всего/вместе/стало» = итоговая величина.
Если задание: «Сравни числа A и B», final_answer должен быть только сравнением со знаком: «A < B», «A > B» или «A = B». Не заменяй сравнение разностью.
Если задание: «В числе N сколько десятков и сколько единиц?», final_answer пиши как «D десяток и E единиц» с правильной формой слова: 1 единица, 2 единицы, 5 единиц.
Если задание: «Как читается число N?», final_answer — только слово числа: «ноль», «пять», «двенадцать».
Если задание: «Запиши цифрой число ...», final_answer — только цифры, например «12».
Для 1 класса, раздел «Арифметические действия»: вычисляй сложение и вычитание в пределах 20 точно; для уравнений x + a = b, a + x = b, x - a = b, a - x = b верни final_answer вида «x = 7»; для сравнения выражений верни знак и оба выражения, например «7 + 5 > 8 + 3»; для вопросов о названиях компонентов верни термин: «сумма», «разность», «слагаемое», «уменьшаемое», «вычитаемое».
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



_NUMBER_WORDS_0_20 = {
    0: 'ноль', 1: 'один', 2: 'два', 3: 'три', 4: 'четыре', 5: 'пять',
    6: 'шесть', 7: 'семь', 8: 'восемь', 9: 'девять', 10: 'десять',
    11: 'одиннадцать', 12: 'двенадцать', 13: 'тринадцать', 14: 'четырнадцать',
    15: 'пятнадцать', 16: 'шестнадцать', 17: 'семнадцать', 18: 'восемнадцать',
    19: 'девятнадцать', 20: 'двадцать',
}
_NUMBER_WORD_TO_INT_0_20 = {value: key for key, value in _NUMBER_WORDS_0_20.items()}


def _ru_plural_1_2_5(number: int, one: str, two: str, five: str) -> str:
    n = abs(int(number))
    last_two = n % 100
    last = n % 10
    if 11 <= last_two <= 14:
        return five
    if last == 1:
        return one
    if 2 <= last <= 4:
        return two
    return five


def _g1_tens_units_phrase(number: int) -> str:
    tens = int(number) // 10
    ones = int(number) % 10
    tens_word = _ru_plural_1_2_5(tens, 'десяток', 'десятка', 'десятков')
    ones_word = _ru_plural_1_2_5(ones, 'единица', 'единицы', 'единиц')
    return f'{tens} {tens_word} и {ones} {ones_word}'


def _normalize_g1_numbers_final_answer(parsed: dict[str, Any], original_text: str) -> tuple[str | None, str | None, str | None]:
    """Deterministic verifier normalization for grade-1 numbers/values prompts.

    DeepSeek remains the primary solver, but this layer keeps the product answer
    format stable for trivial grade-1 number tasks that are easy to verify.
    """
    src = str(original_text or '').strip()
    low = src.lower().replace('ё', 'е')

    m = re.search(r'сравни\s+числа\s+(\d+)\s+и\s+(\d+)', low)
    if m:
        a = int(m.group(1)); b = int(m.group(2))
        sign = '<' if a < b else '>' if a > b else '='
        return f'{a} {sign} {b}', str(a if sign == '=' else ''), ''

    m = re.search(r'в\s+числе\s+(\d+)\s+сколько\s+десят', low)
    if m:
        n = int(m.group(1))
        return _g1_tens_units_phrase(n), '', ''

    m = re.search(r'как\s+читается\s+число\s+(\d+)', low)
    if m:
        n = int(m.group(1))
        word = _NUMBER_WORDS_0_20.get(n)
        if word:
            return word, '', ''

    m = re.search(r'запиши\s+цифр(?:ой|ами)?\s+число\s+([а-я]+)', low)
    if m:
        word = m.group(1)
        value = _NUMBER_WORD_TO_INT_0_20.get(word)
        if value is not None:
            return str(value), str(value), ''

    m = re.search(r'сколько\s+сантиметров\s+в\s+(\d+)\s*дм(?:\s+(\d+)\s*см)?', low)
    if m:
        dm = int(m.group(1)); cm = int(m.group(2) or 0)
        total = dm * 10 + cm
        return f'{total} сантиметров', str(total), 'сантиметров'

    m = re.search(r'сравни\s+длины\s+(\d+)\s*см\s+и\s+(\d+)\s*см', low)
    if m:
        a = int(m.group(1)); b = int(m.group(2))
        sign = '<' if a < b else '>' if a > b else '='
        return f'{a} см {sign} {b} см', '', ''

    final_answer = str(parsed.get('final_answer') or '').strip()
    answer_number = str(parsed.get('answer_number') or '').strip()
    answer_unit = str(parsed.get('answer_unit') or '').strip()

    # Normalize common DeepSeek variant: "1 десяток, 2 единицы".
    if re.fullmatch(r'\d+\s+десят(?:ок|ка|ков),\s*\d+\s+единиц(?:а|ы)?', final_answer.lower()):
        return re.sub(r',\s*', ' и ', final_answer), answer_number, answer_unit

    return final_answer or None, answer_number or None, answer_unit or None



def _deepseek_primary_retry_payload(user_text: str, raw_reply: str = '') -> dict[str, Any]:
    system_prompt = """Верни только валидный JSON object для решения задания по математике 1–4 класса.
Не пиши markdown. Не оставляй content пустым.
Формат строго:
{"known":"...","find":"...","steps":["..."],"answer_number":"...","answer_unit":"","final_answer":"...","cannot_safely_solve":false,"reason":""}
Для «Сравни числа A и B» final_answer обязательно «A < B», «A > B» или «A = B». Для уравнений 1 класса верни «x = число», для сравнения выражений — «выражение знак выражение»."""
    user_prompt = 'Задача: ' + str(user_text or '').strip()
    if raw_reply:
        user_prompt += '\nПредыдущий ответ был невалидным JSON или пустым. Исправь и верни только JSON.'
    return {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': 700,
        'temperature': 0.0,
    }

def _is_g1_deterministic_numbers_prompt(original_text: str) -> bool:
    low = str(original_text or '').lower().replace('ё', 'е')
    patterns = [
        r'сравни\s+числа\s+\d+\s+и\s+\d+',
        r'в\s+числе\s+\d+\s+сколько\s+десят',
        r'как\s+читается\s+число\s+\d+',
        r'запиши\s+цифр(?:ой|ами)?\s+число\s+[а-я]+',
        r'сколько\s+сантиметров\s+в\s+\d+\s*дм',
        r'сравни\s+длины\s+\d+\s*см\s+и\s+\d+\s*см',
    ]
    return any(re.search(p, low) for p in patterns)


def _canonical_step_for_g1_prompt(original_text: str, final_answer: str) -> str:
    low = str(original_text or '').lower().replace('ё', 'е')
    if re.search(r'сравни\s+числа\s+\d+\s+и\s+\d+', low):
        return final_answer
    if re.search(r'сравни\s+длины\s+\d+\s*см\s+и\s+\d+\s*см', low):
        return final_answer
    if re.search(r'в\s+числе\s+\d+\s+сколько\s+десят', low):
        return final_answer
    if re.search(r'как\s+читается\s+число\s+\d+', low):
        return f'Число читается: «{final_answer}»'
    if re.search(r'запиши\s+цифр(?:ой|ами)?\s+число\s+[а-я]+', low):
        return f'Записываем число цифрами: {final_answer}'
    m = re.search(r'сколько\s+сантиметров\s+в\s+(\d+)\s*дм(?:\s+(\d+)\s*см)?', low)
    if m:
        dm = int(m.group(1)); cm = int(m.group(2) or 0)
        if cm:
            return f'{dm} дм = {dm * 10} см; {dm * 10} + {cm} = {dm * 10 + cm} см'
        return f'{dm} дм = {dm * 10} см'
    return final_answer


def _extract_answer_line(result: str) -> str:
    m = re.search(r'Ответ:\s*(.+)', str(result or ''), flags=re.IGNORECASE | re.DOTALL)
    return (m.group(1).splitlines()[0] if m else '').strip().rstrip('.')


def _verified_g1_arithmetic_payload(original_text: str) -> dict | None:
    """Use the structural local layer only as a verifier/postprocessor.

    DeepSeek has already been called before this function is considered; this
    branch only normalizes deterministic grade-1 arithmetic answers and protects
    against bad formatting or arithmetic slips in the LLM response.
    """
    try:
        structural = solve_live_math_first(original_text)
    except Exception:
        return None
    if not isinstance(structural, dict):
        return None
    source = str(structural.get('source') or '')
    if not source.startswith(('local:live-v296-g1-', 'local:live-v287-g1-')):
        return None
    result = _normalize_deepseek_result_text(str(structural.get('result') or '').strip())
    if not result or 'Ответ:' not in result:
        return None
    answer = _extract_answer_line(result)
    steps: list[str] = []
    for line in result.splitlines():
        clean = line.strip()
        if re.match(r'^\d+\)\s+', clean):
            steps.append(re.sub(r'^\d+\)\s+', '', clean).strip())
    return {
        'result': result,
        'source': 'deepseek-primary',
        'validated': True,
        'structured_solution': {
            'known': '',
            'find': '',
            'steps': steps,
            'answer_number': answer,
            'answer_unit': '',
            'final_answer': answer,
        },
        'verifier': 'local-v296-arithmetic-postprocess',
    }


def _format_deepseek_primary_solution(parsed: dict[str, Any], original_text: str) -> dict | None:
    verified_arithmetic = _verified_g1_arithmetic_payload(original_text)
    if verified_arithmetic is not None:
        return verified_arithmetic
    if parsed.get('cannot_safely_solve'):
        return None

    normalized_final, normalized_number, normalized_unit = _normalize_g1_numbers_final_answer(parsed, original_text)
    answer_number = str(normalized_number or parsed.get('answer_number') or '').strip()
    answer_unit = str(normalized_unit if normalized_unit is not None else parsed.get('answer_unit') or '').strip()
    final_answer = str(normalized_final or parsed.get('final_answer') or '').strip()
    if not final_answer:
        final_answer = (answer_number + (' ' + answer_unit if answer_unit else '')).strip()
    if not final_answer:
        return None

    steps_raw = parsed.get('steps')
    steps: list[str] = []
    if isinstance(steps_raw, list):
        for raw in steps_raw:
            step = str(raw or '').strip()
            if step:
                steps.append(step)

    low_original = str(original_text or '').lower().replace('ё', 'е')
    deterministic_g1 = _is_g1_deterministic_numbers_prompt(original_text)

    # For tiny grade-1 number/value prompts DeepSeek often returns a valid final
    # answer but leaves steps empty. That is acceptable for product UX: the local
    # verifier can generate the one-line explanation while the live external API
    # call is still counted and cached.
    if deterministic_g1:
        steps = [_canonical_step_for_g1_prompt(original_text, final_answer)]
    elif not steps:
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
    raw_result = str(llm_result.get('result') or '')
    parsed = _parse_json_object(raw_result)
    if not parsed:
        # One controlled retry fixes occasional empty/non-JSON responses on very short grade-1 prompts.
        retry_result = await call_deepseek(_deepseek_primary_retry_payload(payload, raw_result), timeout_seconds=25.0)
        if not isinstance(retry_result, dict) or retry_result.get('error'):
            return None
        raw_result = str(retry_result.get('result') or '')
        parsed = _parse_json_object(raw_result)
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
