from __future__ import annotations

from typing import Iterable

from .explanation_utils import finalize_text
from .text_utils import normalize_word_problem_text


def audit_task_line(text: str) -> str:
    prepared = normalize_word_problem_text(text)
    if prepared and prepared[-1] not in '.!?':
        prepared += '.'
    return prepared


def finalize_legacy_lines(lines: Iterable[str]) -> str:
    return finalize_text([str(x) for x in lines if str(x or '').strip()])


__all__ = [
    'audit_task_line',
    'finalize_legacy_lines',
]
