from __future__ import annotations

from .explanation_dispatcher import dispatch_explanation
from .guards import division_by_zero_payload, is_direct_division_by_zero, looks_like_math_input


async def build_explanation(user_text: str) -> dict:
    return await dispatch_explanation(user_text)


__all__ = [
    'build_explanation',
    'division_by_zero_payload',
    'is_direct_division_by_zero',
    'looks_like_math_input',
]
