from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import List, Optional

from .column_engine import get_column_explanation_text
from .expression_parser import BinaryOperation, normalize_expression_source, parse_expression_ast
from .formatters.column_formatter import normalize_column_body_lines
from .explanation_utils import split_sections
from .math_explainers import (
    explain_simple_addition,
    explain_simple_division,
    explain_simple_multiplication,
    explain_simple_subtraction,
)

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_OPERATOR_SYMBOLS = {ast.Add: '+', ast.Sub: '-', ast.Mult: '×', ast.Div: ':'}
_OPERATOR_PRETTY = {'+': '+', '-': '-', '×': '×', ':': ':'}
_OPERATOR_NAMES = {'+': 'сложение', '-': 'вычитание', '×': 'умножение', ':': 'деление'}
_ORDINAL_WORDS = {1: 'Первое', 2: 'Второе', 3: 'Третье', 4: 'Четвёртое', 5: 'Пятое', 6: 'Шестое', 7: 'Седьмое', 8: 'Восьмое'}


@dataclass(frozen=True)
class MixedExpressionStep:
    left: Fraction
    operator: str
    right: Fraction
    result: Fraction
    operator_pos: int


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _to_fraction(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return Fraction(int(node.value), 1)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_to_fraction(node.operand)
    raise ValueError('Unsupported literal')


def _apply_operator(operator: ast.operator, left: Fraction, right: Fraction) -> Fraction:
    if isinstance(operator, ast.Add):
        return left + right
    if isinstance(operator, ast.Sub):
        return left - right
    if isinstance(operator, ast.Mult):
        return left * right
    if isinstance(operator, ast.Div):
        if right == 0:
            raise ZeroDivisionError('division by zero')
        return left / right
    raise ValueError('Unsupported operator')


def _find_operator_position(source: str, node: ast.BinOp) -> int:
    start = getattr(node.left, 'end_col_offset', None)
    end = getattr(node.right, 'col_offset', None)
    if start is not None and end is not None and 0 <= start <= end <= len(source):
        fragment = source[start:end]
        for index, ch in enumerate(fragment):
            if ch in '+-*/':
                return start + index
    for index, ch in enumerate(source):
        if ch in '+-*/':
            return index
    return 0


def _collect_steps(node: ast.AST, source: str) -> tuple[Fraction, List[MixedExpressionStep]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left_value, left_steps = _collect_steps(node.left, source)
        right_value, right_steps = _collect_steps(node.right, source)
        result = _apply_operator(node.op, left_value, right_value)
        step = MixedExpressionStep(
            left=left_value,
            operator=_OPERATOR_SYMBOLS[type(node.op)],
            right=right_value,
            result=result,
            operator_pos=_find_operator_position(source, node),
        )
        return result, [*left_steps, *right_steps, step]
    return _to_fraction(node), []


def _pretty_expression_with_map(source: str) -> tuple[str, dict[int, int]]:
    out: List[str] = []
    mapping: dict[int, int] = {}
    for index, ch in enumerate(source):
        prev = source[index - 1] if index > 0 else ''
        is_unary_minus = ch == '-' and (index == 0 or prev in '+-*/(')
        if ch in '+-*/' and not is_unary_minus:
            if out and out[-1] != ' ':
                out.append(' ')
            mapping[index] = len(out)
            out.append('×' if ch == '*' else ':' if ch == '/' else ch)
            out.append(' ')
        else:
            mapping[index] = len(out)
            out.append(ch)
    return ''.join(out).strip(), mapping


def _build_order_block(source: str, steps: List[MixedExpressionStep]) -> List[str]:
    if len(steps) <= 1:
        return []
    pretty, mapping = _pretty_expression_with_map(source)
    marks = [' '] * len(pretty)
    for index, step in enumerate(steps, start=1):
        pretty_pos = mapping.get(step.operator_pos)
        if pretty_pos is None:
            continue
        label = str(index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, ch in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = ch
    return ['Порядок действий:', ''.join(marks).rstrip(), pretty]


def _binary_operation_from_step(step: MixedExpressionStep) -> Optional[BinaryOperation]:
    if step.left.denominator != 1 or step.right.denominator != 1 or step.result.denominator != 1:
        return None
    left = int(step.left.numerator)
    right = int(step.right.numerator)
    operator = '÷' if step.operator == ':' else step.operator
    return BinaryOperation(left=left, operator=operator, right=right)


def _digit_length(value: int) -> int:
    return len(str(abs(int(value))))


def _should_use_column(operation: BinaryOperation) -> bool:
    a_length = _digit_length(operation.left)
    b_length = _digit_length(operation.right)
    if operation.operator == '×':
        return a_length >= 2 or b_length >= 2
    if operation.operator == '÷':
        return a_length >= 3 or b_length >= 2
    return a_length >= 3 or b_length >= 3 or (a_length >= 2 and b_length >= 2)


def _simple_operation_detail(step: MixedExpressionStep) -> Optional[List[str]]:
    operation = _binary_operation_from_step(step)
    if not operation:
        return None
    detail_text = None
    if operation.operator == '+':
        detail_text = explain_simple_addition(operation.left, operation.right)
    elif operation.operator == '-':
        if operation.left < operation.right:
            return None
        detail_text = explain_simple_subtraction(operation.left, operation.right)
    elif operation.operator == '×':
        detail_text = explain_simple_multiplication(operation.left, operation.right)
    elif operation.operator == '÷':
        if operation.right == 0:
            return None
        detail_text = explain_simple_division(operation.left, operation.right)
    if not detail_text:
        return None
    parts = split_sections(detail_text)
    body = []
    for raw in parts.get('body', []):
        line = str(raw or '').strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith('пример') or lower in {'решение', 'решение.'}:
            continue
        line = re.sub(r'^\d+\)\s*', '', line)
        body.append(line)
    return body or None


def _column_operation_detail(step: MixedExpressionStep) -> Optional[List[str]]:
    operation = _binary_operation_from_step(step)
    if not operation:
        return None
    detail_text = get_column_explanation_text(operation)
    if not detail_text:
        return None
    parts = split_sections(detail_text)
    lines = normalize_column_body_lines(parts.get('body', []))
    return lines or None


def build_direct_mixed_expression_payload(raw_text: str) -> Optional[dict]:
    source = normalize_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    try:
        value, steps = _collect_steps(node, source)
    except ZeroDivisionError:
        return None
    except Exception:
        return None
    if len(steps) <= 1:
        return None

    pretty_expression, _ = _pretty_expression_with_map(source)
    answer = _format_fraction(value)
    lines: List[str] = [f'Пример: {pretty_expression} = {answer}.']
    lines.extend(_build_order_block(source, steps))
    lines.append('Решение по действиям:')

    for index, step in enumerate(steps, start=1):
        left = _format_fraction(step.left)
        right = _format_fraction(step.right)
        result = _format_fraction(step.result)
        operation = _binary_operation_from_step(step)
        use_column = bool(operation and _should_use_column(operation))
        action_name = _OPERATOR_NAMES.get(step.operator, 'действие')
        ordinal = _ORDINAL_WORDS.get(index, f'{index}-е')
        if use_column:
            lines.append(f'{index}) {ordinal} действие — {action_name}: {left} {step.operator} {right}. Выполним это действие в столбик.')
            body_lines = _column_operation_detail(step)
            if body_lines:
                lines.extend(body_lines)
            lines.append(f'Значит, {left} {step.operator} {right} = {result}.')
        else:
            lines.append(f'{index}) {ordinal} действие — {action_name}: {left} {step.operator} {right} = {result}.')
            body_lines = _simple_operation_detail(step)
            if body_lines:
                lines.extend(body_lines)

    advice = 'сначала выполняй действия в скобках, потом умножение и деление, потом сложение и вычитание'
    lines.append(f'Ответ: {answer}.')
    lines.append(f'Совет: {advice}.')
    return {
        'result': '\n'.join(str(line).rstrip() for line in lines if str(line).strip()).strip(),
        'source': 'expression_mixed:direct',
        'validated': True,
        'expression_source': source,
        'step_count': len(steps),
    }


__all__ = ['build_direct_mixed_expression_payload', 'MixedExpressionStep']
