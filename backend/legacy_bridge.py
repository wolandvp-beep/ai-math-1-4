from __future__ import annotations

from . import legacy_core as core
from .formatters import format_solution
from .legacy_runtime import run_legacy_with_runtime_guards
from .text_utils import infer_task_kind


def format_local_solution(user_text: str, local_explanation: str, *, preformatted: bool = False) -> str:
    if preformatted:
        return local_explanation
    kind = infer_task_kind(user_text)
    return format_solution(user_text, local_explanation, kind)


async def build_legacy_explanation(user_text: str) -> dict:
    return await run_legacy_with_runtime_guards(user_text, core.build_explanation)


def expose_core():
    return core
