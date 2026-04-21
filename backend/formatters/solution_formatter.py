from __future__ import annotations

from ..explanation_utils import (
    format_equation_solution,
    format_fraction_solution,
    format_generic_solution,
    to_equation_source,
    to_fraction_source,
)
from ..formatters.expression_formatter import format_expression_solution
from ..expression_parser import normalize_expression_source


def format_solution(raw_text: str, text: str, kind: str) -> str:
    expression_source = normalize_expression_source(raw_text)
    if kind == 'expression' and expression_source and any(op in expression_source for op in '+-*/'):
        return format_expression_solution(raw_text, text)
    if kind == 'equation' and to_equation_source(raw_text):
        return format_equation_solution(raw_text, text)
    if kind == 'fraction' and to_fraction_source(raw_text) and not any('а' <= ch.lower() <= 'я' for ch in raw_text):
        return format_fraction_solution(raw_text, text)
    return format_generic_solution(raw_text, text, kind)
