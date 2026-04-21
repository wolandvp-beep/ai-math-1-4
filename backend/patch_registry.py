from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .handlers import (
    build_fraction_time_total_explanation,
    build_letter_problem_explanation,
    build_named_quantity_arithmetic_explanation,
)


@dataclass(frozen=True)
class LocalExplanationHandler:
    name: str
    func: Callable[[str], Optional[str]]
    preformatted: bool = False


LOCAL_EXPLANATION_HANDLERS = (
    LocalExplanationHandler('letter_word_problem', build_letter_problem_explanation),
    LocalExplanationHandler('fraction_time_total', build_fraction_time_total_explanation, preformatted=True),
    LocalExplanationHandler('named_quantity_arithmetic', build_named_quantity_arithmetic_explanation, preformatted=True),
)


def resolve_local_explanation(user_text: str) -> tuple[Optional[str], Optional[str], bool]:
    for handler in LOCAL_EXPLANATION_HANDLERS:
        result = handler.func(user_text)
        if result:
            return result, handler.name, handler.preformatted
    return None, None, False
