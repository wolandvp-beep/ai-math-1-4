from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..input_normalization import normalize_solver_input
from ..legacy_bridge import expose_core


@dataclass(frozen=True)
class LegacyGroupedHandler:
    name: str
    func: Callable[[str], Optional[str]]


def available_group_handlers(handler_names: tuple[str, ...]) -> tuple[LegacyGroupedHandler, ...]:
    core = expose_core()
    handlers: list[LegacyGroupedHandler] = []
    for name in handler_names:
        func = getattr(core, name, None)
        if callable(func):
            handlers.append(LegacyGroupedHandler(name=name.removeprefix('_try_'), func=func))
    return tuple(handlers)


def _normalize_group_input(raw_text: str) -> str:
    return normalize_solver_input(raw_text)


def resolve_grouped_legacy_problem(raw_text: str, handlers: tuple[LegacyGroupedHandler, ...]) -> tuple[Optional[str], Optional[str]]:
    normalized = _normalize_group_input(raw_text)
    for handler in handlers:
        try:
            result = handler.func(normalized)
        except Exception:
            continue
        if result:
            return result, handler.name
    return None, None


def build_grouped_legacy_payload(raw_text: str, handlers: tuple[LegacyGroupedHandler, ...], source_prefix: str) -> Optional[dict]:
    normalized = _normalize_group_input(raw_text)
    explanation, handler_name = resolve_grouped_legacy_problem(normalized, handlers)
    if not explanation:
        return None
    return {
        'result': explanation,
        'source': f'{source_prefix}:{handler_name}',
        'validated': True,
        'normalized_input': normalized,
    }


__all__ = [
    'LegacyGroupedHandler',
    'available_group_handlers',
    'build_grouped_legacy_payload',
    'resolve_grouped_legacy_problem',
]
