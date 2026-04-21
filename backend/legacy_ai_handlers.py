from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from .legacy_bridge import expose_core
from .legacy_explanatory_ai import (
    _looks_like_explanatory_math_question,
    _try_structured_deepseek_explanation,
)
from .legacy_safe_responses import (
    guard_result,
    safe_cannot_reliably_explain_math,
    safe_cannot_reliably_solve_math,
)

LegacyAsyncDictFn = Callable[[dict, str], Awaitable[Optional[dict[str, Any]]]]
LegacyBoolFn = Callable[[str], bool]


def _get_core():
    return expose_core()


def _tag_result(payload: Optional[dict[str, Any]], fallback_path: str) -> Optional[dict[str, Any]]:
    if payload is None:
        return None
    tagged = dict(payload)
    tagged.setdefault('source', fallback_path)
    tagged['fallback_path'] = fallback_path
    return tagged


async def _call_async_legacy(fn: Optional[LegacyAsyncDictFn], user_text: str) -> Optional[dict[str, Any]]:
    if not callable(fn):
        return None
    core = _get_core()
    return await fn(core.__dict__, user_text)



async def build_legacy_explanatory_math_payload(user_text: str) -> Optional[dict[str, Any]]:
    core = _get_core()
    if not _looks_like_explanatory_math_question(user_text, core.__dict__.get('_looks_like_math_input')):
        return None

    explained = await _try_structured_deepseek_explanation(core.__dict__, user_text, looks_like_math_input_fn=core.__dict__.get('_looks_like_math_input'))
    if explained:
        return _tag_result(explained, 'legacy-ai:structured-explanation')

    guarded = guard_result(
        safe_cannot_reliably_explain_math(user_text),
        source='legacy-ai:structured-explanation-guard',
    )
    return _tag_result(guarded, 'legacy-ai:structured-explanation-guard')


async def build_legacy_generic_math_payload(user_text: str) -> Optional[dict[str, Any]]:
    core = _get_core()
    looks_like_math_input = getattr(core, '_looks_like_math_input', None)
    try_validated = getattr(core, '_try_validated_deepseek_fallback', None)
    if not _call_bool_legacy(looks_like_math_input, user_text):
        return None

    ai_result = await _call_async_legacy(try_validated, user_text)
    if ai_result:
        return _tag_result(ai_result, 'legacy-ai:validated-math')

    guarded = guard_result(
        safe_cannot_reliably_solve_math(user_text),
        source='legacy-ai:validated-math-guard',
    )
    return _tag_result(guarded, 'legacy-ai:validated-math-guard')


__all__ = [
    'build_legacy_explanatory_math_payload',
    'build_legacy_generic_math_payload',
]
