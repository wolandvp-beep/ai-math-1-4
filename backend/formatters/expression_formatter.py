from __future__ import annotations
import re
from typing import Iterable, List
from ..advice import default_advice
from ..expression_parser import BinaryOperation, normalize_expression_source
from ..explanation_utils import (
    build_generic_steps_from_expression,
    build_order_block,
    expression_answer,
    finalize_text,
    number_lines,
    pretty_or_rendered_expression,
    split_sections,
)
def _expression_body_lines(parts: dict) -> List[str]:
    lines = [str(line or '').strip() for line in parts.get('body', [])]
    cleaned: List[str] = []
    for line in lines:
        if not line:
            continue
        if line == 'Пример в одно действие.':
            continue
        cleaned.append(re.sub(r'^\d+\)\s*', '', line))
    return cleaned
def _finalize_expression_lines(lines: Iterable[str]) -> str:
    finalized: List[str] = []
    for raw in lines:
        value = str(raw or '').strip()
        if not value:
            continue
        if value.endswith((':', '.', '!', '?')):
            finalized.append(value)
            continue
        if re.fullmatch(r'[0-9() +\-×:=/]+', value):
            finalized.append(value)
            continue
        finalized.append(value + '.')
    return '\n'.join(finalized).strip()
def format_simple_expression_solution(operation: BinaryOperation, base_text: str) -> str:
    parts = split_sections(base_text)
    answer = parts.get('answer') or 'проверь запись'
    advice = parts.get('advice') or default_advice('expression')
    body_lines = _expression_body_lines(parts)
    pretty_operator = ':' if operation.operator == '÷' else operation.operator
    pretty_expression = f'{operation.left} {pretty_operator} {operation.right}'
    lines: List[str] = [f'Пример: {pretty_expression} = {answer}.']
    lines.append('Решение:')
    lines.append(f'1) {pretty_expression} = {answer}.')
    lines.extend(body_lines)
    lines.append(f'Ответ: {answer}.')
    lines.append(f'Совет: {advice}.')
    return _finalize_expression_lines(lines)
def format_expression_solution(raw_text: str, base_text: str) -> str:
    source = normalize_expression_source(raw_text)
    if not source or not re.search(r'[+\-*/]', source):
        from ..explanation_utils import format_generic_solution
        return format_generic_solution(raw_text, base_text, 'expression')
    parts = split_sections(base_text)
    pretty_expression = pretty_or_rendered_expression(source)
    answer = parts.get('answer') or expression_answer(source) or 'проверь запись'
    body_lines = _expression_body_lines(parts)
    if not body_lines:
        body_lines = [re.sub(r'^\d+\)\s*', '', line) for line in build_generic_steps_from_expression(source)]
    lines: List[str] = [f'Пример: {pretty_expression} = {answer}.']
    order_block = build_order_block(source)
    if order_block:
        lines.extend(order_block)
        lines.append('Решение по действиям:')
    else:
        lines.append('Решение.')
    if body_lines:
        lines.extend(number_lines(body_lines))
    lines.append(f'Ответ: {answer}.')
    advice = parts.get('advice') or default_advice('expression')
    lines.append(f'Совет: {advice}.')
    return finalize_text(lines)
