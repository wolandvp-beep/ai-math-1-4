from __future__ import annotations

from .legacy_runtime import division_by_zero_payload, is_direct_division_by_zero
from .text_utils import looks_like_math_input

__all__ = [
    'division_by_zero_payload',
    'is_direct_division_by_zero',
    'looks_like_math_input',
]
