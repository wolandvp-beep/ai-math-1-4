from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from .text_utils import looks_like_math_input as _shared_looks_like_math_input

_EXPLANATORY_MATH_MARKERS = (
    'что такое', 'почему', 'зачем', 'объясни', 'объяснение', 'поясни',
    'как понять', 'как решать', 'как решить', 'как находить', 'как найти',
    'когда используют', 'чем отличается', 'в чем разница', 'в чём разница',
    'почему больше', 'почему меньше', 'как сравнить',
)

LegacyMathInputFn = Callable[[str], bool]
LegacyAsyncCallFn = Callable[..., Awaitable[dict[str, Any] | None]]
LegacyApiKeyFn = Callable[[dict[str, Any]], str]


def _normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '').replace('−', '-').replace('–', '-')).strip()


def _strip_label(text: str) -> str:
    return re.sub(
        r'^(?:задача|пример|уравнение|дроби|геометрия|выражение|математика)\s*:\s*',
        '',
        str(text or '').strip(),
        flags=re.IGNORECASE,
    )


def _clean_text(text: str) -> str:
    return _normalize_space(_strip_label(text))


def _ensure_sentence(text: str) -> str:
    cleaned = _normalize_space(text)
    if not cleaned:
        return ''
    if cleaned[-1] not in '.!?':
        return cleaned + '.'
    return cleaned


def _join_lines(lines: list[str]) -> str:
    return '\n'.join(line.rstrip() for line in lines if str(line or '').strip())


def _parse_json_object(text: str) -> Optional[dict[str, Any]]:
    raw = str(text or '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find('{')
        end = raw.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _resolve_looks_like_math_input(looks_like_math_input_fn: Optional[LegacyMathInputFn]) -> LegacyMathInputFn:
    if callable(looks_like_math_input_fn):
        return looks_like_math_input_fn
    return _shared_looks_like_math_input


def _looks_like_explanatory_math_question(
    text: str,
    looks_like_math_input_fn: Optional[LegacyMathInputFn] = None,
) -> bool:
    lower = _clean_text(text).lower().replace('ё', 'е')
    looks_like_math_input = _resolve_looks_like_math_input(looks_like_math_input_fn)
    if not lower or not looks_like_math_input(lower):
        return False
    return any(marker in lower for marker in _EXPLANATORY_MATH_MARKERS)


def _build_structured_deepseek_explanation(
    parsed: dict[str, Any],
    user_text: str,
    looks_like_math_input_fn: Optional[LegacyMathInputFn] = None,
) -> Optional[dict[str, Any]]:
    if parsed.get('cannot_safely_explain') or parsed.get('cannot_safely_solve'):
        return None
    topic = _normalize_space(str(parsed.get('topic') or ''))
    short_answer = _normalize_space(str(parsed.get('short_answer') or parsed.get('answer') or ''))
    steps = parsed.get('steps')
    example = _normalize_space(str(parsed.get('example') or ''))
    tip = _normalize_space(str(parsed.get('tip') or '')) or 'сначала проговори правило своими словами, а потом проверь его на простом примере.'
    if not topic or not short_answer:
        return None
    if not isinstance(steps, list):
        return None
    normalized_steps = [_normalize_space(str(step)) for step in steps if _normalize_space(str(step))]
    if len(normalized_steps) < 2 or len(normalized_steps) > 6:
        return None
    if len(topic) > 90 or len(short_answer) > 260 or len(tip) > 180:
        return None
    if example and len(example) > 260:
        return None
    looks_like_math_input = _resolve_looks_like_math_input(looks_like_math_input_fn)
    if not looks_like_math_input(user_text):
        return None
    lines = [
        'Вопрос.',
        _ensure_sentence(_clean_text(user_text)),
        'Объяснение.',
        _ensure_sentence(f'Тема: {topic.rstrip(".")}'),
        _ensure_sentence(short_answer),
    ]
    for index, step in enumerate(normalized_steps, start=1):
        if re.match(r'^\d+\)', step):
            lines.append(_ensure_sentence(step))
        else:
            lines.append(_ensure_sentence(f'{index}) {step}'))
    if example:
        lines.append(_ensure_sentence(f'Пример: {example.rstrip(".")}'))
    lines.append(_ensure_sentence(f'Совет: {tip.rstrip(".")}'))
    return {
        'result': _join_lines(lines),
        'source': 'deepseek-structured-explanation',
        'validated': False,
        'structured_explanation': {
            'topic': topic,
            'short_answer': short_answer,
            'steps': normalized_steps,
            'example': example,
            'tip': tip,
        },
    }


def _deepseek_explanation_payload(user_text: str) -> dict[str, Any]:
    system_prompt = """Ты резервный математический объяснитель для детей 7–10 лет.
Верни только один JSON object без markdown и без текста вне JSON.
Объясняй коротко, дружелюбно и по-школьному.
Не решай нерелевантные вопросы и не выходи за рамки математики начальной школы.
Если вопрос не удаётся надёжно объяснить, верни {"cannot_safely_explain": true, "reason": "..."}.
Нужный JSON:
{
  "topic": "...",
  "short_answer": "...",
  "steps": ["...", "...", "..."],
  "example": "...",
  "tip": "..."
}"""
    return {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'Объясни математический вопрос и верни только JSON. Вопрос: {user_text}'},
        ],
        'response_format': {'type': 'json_object'},
        'max_tokens': 700,
        'temperature': 0.0,
    }


async def _try_structured_deepseek_explanation(
    ns: dict[str, Any],
    user_text: str,
    looks_like_math_input_fn: Optional[LegacyMathInputFn] = None,
) -> Optional[dict[str, Any]]:
    get_api_key: Optional[LegacyApiKeyFn] = ns.get('_get_deepseek_api_key')
    call_deepseek: Optional[LegacyAsyncCallFn] = ns.get('call_deepseek')
    if not callable(get_api_key) or not callable(call_deepseek):
        return None
    api_key = get_api_key(ns)
    if not api_key:
        return None
    previous_key = ns.get('DEEPSEEK_API_KEY', '')
    ns['DEEPSEEK_API_KEY'] = api_key
    try:
        llm_result = await call_deepseek(_deepseek_explanation_payload(user_text), timeout_seconds=20.0)
    finally:
        ns['DEEPSEEK_API_KEY'] = previous_key
    if not isinstance(llm_result, dict) or llm_result.get('error'):
        return None
    parsed = _parse_json_object(llm_result.get('result'))
    if not parsed:
        return None
    return _build_structured_deepseek_explanation(
        parsed,
        user_text,
        looks_like_math_input_fn=looks_like_math_input_fn,
    )


__all__ = [
    '_EXPLANATORY_MATH_MARKERS',
    '_build_structured_deepseek_explanation',
    '_deepseek_explanation_payload',
    '_looks_like_explanatory_math_question',
    '_try_structured_deepseek_explanation',
]
