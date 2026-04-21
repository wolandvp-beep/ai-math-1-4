from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from .text_utils import join_explanation_lines, looks_like_math_input


def division_by_zero_payload() -> dict[str, Any]:
    return {
        'result': join_explanation_lines(
            'На ноль делить нельзя.',
            'Ответ: деление на ноль невозможно',
            'Совет: сначала проверь делитель.',
        ),
        'source': 'guard-runtime',
        'validated': True,
    }


def is_direct_division_by_zero(text: str) -> bool:
    normalized = (text or '').strip().lower()
    if not normalized or not looks_like_math_input(normalized):
        return False
    compact = normalized.replace(' ', '')
    compact = compact.replace('×', '*').replace('x', '*').replace('х', '*')
    compact = compact.replace('÷', '/').replace(':', '/')
    compact = compact.replace('−', '-').replace('–', '-').replace('—', '-')
    pattern = r'(?:^|[+\-*/(])(?:\d+|\([^()]*\))*/0+(?=$|[+\-*/)])'
    return bool(re.search(pattern, compact))


async def run_legacy_with_runtime_guards(
    user_text: str,
    core_builder: Callable[[str], Awaitable[dict]],
) -> dict:
    if is_direct_division_by_zero(user_text):
        return division_by_zero_payload()
    try:
        return await core_builder(user_text)
    except ZeroDivisionError:
        return division_by_zero_payload()
    except Exception as exc:  # pragma: no cover - defensive bridge
        if 'division by zero' in str(exc).lower():
            return division_by_zero_payload()
        raise


__all__ = [
    'division_by_zero_payload',
    'is_direct_division_by_zero',
    'run_legacy_with_runtime_guards',
]
