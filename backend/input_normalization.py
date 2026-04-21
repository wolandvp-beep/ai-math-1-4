from __future__ import annotations

import re
from typing import Optional

_COMMAND_PREFIX_PATTERNS = (
    re.compile(r'^\s*(?:реши|вычисли|посчитай)\s+(?:пример|выражение)\s*:?\s*', re.IGNORECASE),
    re.compile(r'^\s*(?:найди\s+значение\s+выражения|вычисли\s+значение\s+выражения)\s*:?\s*', re.IGNORECASE),
    re.compile(r'^\s*(?:реши|найди(?:\s+корень)?)\s+уравнение\s*:?\s*', re.IGNORECASE),
    re.compile(
        r'^\s*найди\s+неизвестн(?:ое|ый)\s+(?:слагаемое|уменьшаемое|вычитаемое|множитель|делитель|делимое)\s*:?\s*',
        re.IGNORECASE,
    ),
    re.compile(r'^\s*(?:сколько\s+будет|чему\s+равно)\s+', re.IGNORECASE),
    re.compile(r'^\s*(?:реши|вычисли|посчитай)\s*:?\s*', re.IGNORECASE),
)


def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '').replace('−', '-').replace('–', '-')).strip()



def strip_solver_command_prefix(raw_text: str) -> Optional[str]:
    text = normalize_space(raw_text)
    if not text:
        return None
    for pattern in _COMMAND_PREFIX_PATTERNS:
        stripped = pattern.sub('', text, count=1).strip()
        if stripped and stripped != text:
            stripped = re.sub(r'[?!.]+$', '', stripped).strip()
            return stripped
    return None



def normalize_solver_input(raw_text: str) -> str:
    stripped = strip_solver_command_prefix(raw_text)
    if stripped:
        return stripped
    return normalize_space(raw_text)


__all__ = [
    'normalize_solver_input',
    'normalize_space',
    'strip_solver_command_prefix',
]
