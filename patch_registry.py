from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from backend.handlers import build_fraction_time_total_explanation, build_letter_problem_explanation, build_named_quantity_arithmetic_explanation
from backend.platform.features.handlers.direct_math.elementary_curriculum.primary_textbook_handlers import build_primary_textbook_explanation
from backend.platform.open_source_local_handlers import build_open_source_curriculum_explanation


@dataclass(frozen=True)
class LocalExplanationHandler:
    name: str
    func: Callable[[str], Optional[str]]
    preformatted: bool = False


# v253 release hardening: prioritize the targeted open-source curriculum layer.
# It contains the blind/generalization rules added in v245-v250 and avoids
# broad legacy handlers stealing these inputs before the targeted solver runs.
# No exact task lookup is added here.
LOCAL_EXPLANATION_HANDLERS = (
    LocalExplanationHandler('open_source_curriculum', build_open_source_curriculum_explanation, preformatted=True),
    LocalExplanationHandler('letter_word_problem', build_letter_problem_explanation),
    LocalExplanationHandler('fraction_time_total', build_fraction_time_total_explanation, preformatted=True),
    LocalExplanationHandler('named_quantity_arithmetic', build_named_quantity_arithmetic_explanation, preformatted=True),
    LocalExplanationHandler('primary_textbook', build_primary_textbook_explanation, preformatted=True),
)


def resolve_local_explanation(user_text: str) -> tuple[Optional[str], Optional[str], bool]:
    for handler in LOCAL_EXPLANATION_HANDLERS:
        result = handler.func(user_text)
        if result:
            return result, handler.name, handler.preformatted
    return None, None, False
