from __future__ import annotations
import re
from typing import Iterable, List
from ..advice import default_advice
from ..expression_parser import BinaryOperation
from ..explanation_utils import split_sections
_VISUAL_NUMBER_RE = re.compile(r'^\d[\d\s]*\.?$')
_VISUAL_OPERATOR_RE = re.compile(r'^[+\-–×÷:]\s*\d[\d\s]*\.?$')
_VISUAL_RULE_RE = re.compile(r'^-{3,}$')
def _pretty_operator(symbol: str) -> str:
    return {'+': '+', '-': '-', '×': '×', '÷': ':'}.get(symbol, symbol)
def _normalize_visual_line(line: str) -> str:
    value = str(line or '').rstrip()
    stripped = value.strip()
    if _VISUAL_NUMBER_RE.fullmatch(stripped):
        return stripped.rstrip('.')
    if _VISUAL_OPERATOR_RE.fullmatch(stripped):
        return stripped.rstrip('.')
    if _VISUAL_RULE_RE.fullmatch(stripped):
        return stripped
    return stripped
def normalize_column_body_lines(lines: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    for raw in lines:
        line = _normalize_visual_line(str(raw or ''))
        lower = line.lower()
        if not line:
            continue
        if line == 'Пример в одно действие.':
            continue
        if lower.startswith('читаем ответ:'):
            continue
        cleaned.append(line)
    return cleaned
def _finalize_column_lines(lines: Iterable[str]) -> str:
    finalized: List[str] = []
    for raw in lines:
        value = str(raw or '').rstrip()
        if not value:
            continue
        stripped = value.strip()
        if stripped.endswith(':'):
            finalized.append(stripped)
            continue
        if _VISUAL_NUMBER_RE.fullmatch(stripped) or _VISUAL_OPERATOR_RE.fullmatch(stripped) or _VISUAL_RULE_RE.fullmatch(stripped):
            finalized.append(stripped)
            continue
        if re.fullmatch(r'[ A-Za-zА-Яа-я0-9()+\-×:=/]+', value) and (('=' in value) or bool(re.search(r'[+\-×:/]', value))):
            finalized.append(value)
            continue
        if stripped[-1] not in '.!?:':
            stripped += '.'
        finalized.append(stripped)
    return '\n'.join(finalized).strip()
def format_column_operation_solution(operation: BinaryOperation, explanation_text: str) -> str:
    parts = split_sections(explanation_text)
    answer = parts.get('answer') or 'проверь запись'
    advice = parts.get('advice') or default_advice('expression')
    body_lines = normalize_column_body_lines(parts.get('body', []))
    pretty_expression = f'{operation.left} {_pretty_operator(operation.operator)} {operation.right}'
    lines: List[str] = [f'Пример: {pretty_expression} = {answer}.']
    lines.append('Порядок действий:')
    lines.append(pretty_expression)
    lines.append('Решение по действиям:')
    lines.append(f'1) {pretty_expression} = {answer}.')
    lines.extend(body_lines)
    lines.append(f'Ответ: {answer}.')
    lines.append(f'Совет: {advice}.')
    return _finalize_column_lines(lines)
