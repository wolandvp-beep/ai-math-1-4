from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from .legacy_bridge import expose_core
from .legacy_dangerous_topics import dangerous_topic_for_old_solver
from .legacy_safe_responses import guard_result, safe_cannot_reliably_solve_math


LegacyAsyncDictFn = Callable[[dict, str], Awaitable[Optional[dict[str, Any]]]]

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


async def build_legacy_external_fallback_payload(user_text: str) -> Optional[dict[str, Any]]:
    core = _get_core()

    try_validated_fn: Optional[LegacyAsyncDictFn] = getattr(core, '_try_validated_deepseek_fallback', None)
    dangerous_topic = dangerous_topic_for_old_solver(user_text, core.__dict__)
    if not dangerous_topic:
        return None

    ai_result = await _call_async_legacy(try_validated_fn, user_text)
    if ai_result:
        return _tag_result(ai_result, 'legacy-fallback:dangerous-topic-ai')

    safe_text = safe_cannot_reliably_solve_math(user_text)
    guarded = guard_result(safe_text, source='legacy-fallback:dangerous-topic-guard')
    return _tag_result(guarded, 'legacy-fallback:dangerous-topic-guard')


__all__ = [
    'build_legacy_external_fallback_payload',
]
