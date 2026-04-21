from __future__ import annotations

import ast
import re
from fractions import Fraction
from typing import List

from .expression_parser import parse_expression_ast

_OPERATOR_SYMBOLS = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '×',
    ast.Div: ':',
}
_PRECEDENCE = {
    ast.Add: 1,
    ast.Sub: 1,
    ast.Mult: 2,
    ast.Div: 2,
}


def _is_int_literal_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int


def _int_from_literal_node(node: ast.AST) -> int:
    if not _is_int_literal_node(node):
        raise ValueError('Expected integer literal node')
    return int(node.value)


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f'{value.numerator}/{value.denominator}'


def eval_fraction_node(node: ast.AST) -> Fraction:
    if _is_int_literal_node(node):
        return Fraction(_int_from_literal_node(node), 1)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -eval_fraction_node(node.operand)
    if isinstance(node, ast.BinOp):
        left = eval_fraction_node(node.left)
        right = eval_fraction_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError('division by zero')
            return left / right
    raise ValueError('Unsupported expression')


def render_node(node: ast.AST, parent_precedence: int = 0, is_right_child: bool = False) -> str:
    if _is_int_literal_node(node):
        return str(_int_from_literal_node(node))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = render_node(node.operand, 3)
        return f'-{inner}'
    if isinstance(node, ast.BinOp):
        current_precedence = _PRECEDENCE[type(node.op)]
        left_text = render_node(node.left, current_precedence, False)
        right_text = render_node(node.right, current_precedence, True)
        text = f"{left_text} {_OPERATOR_SYMBOLS[type(node.op)]} {right_text}"
        needs_brackets = current_precedence < parent_precedence or (
            is_right_child and isinstance(node.op, (ast.Add, ast.Sub)) and parent_precedence == current_precedence
        )
        return f'({text})' if needs_brackets else text
    raise ValueError('Unsupported node')


def pretty_expression_with_map(source: str) -> tuple[str, dict[int, int]]:
    pretty_parts: List[str] = []
    op_map = {}
    current_len = 0
    for index, ch in enumerate(source):
        if ch in '+-*/':
            symbol = '×' if ch == '*' else ':' if ch == '/' else ch
            token = f' {symbol} '
            pretty_parts.append(token)
            op_map[index] = current_len + 1
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    return ''.join(pretty_parts), op_map


def _find_operator_position(source: str, node: ast.AST) -> int | None:
    if not isinstance(node, ast.BinOp):
        return None
    try:
        left_end = node.left.end_col_offset
        right_start = node.right.col_offset
        segment = source[left_end:right_start]
        for offset, char in enumerate(segment):
            if char in '+-*/':
                return left_end + offset
        for index in range(node.col_offset, node.end_col_offset):
            if 0 <= index < len(source) and source[index] in '+-*/':
                return index
    except Exception:
        return None
    return None


def _collect_expression_steps(node: ast.AST, source: str) -> List[dict]:
    if _is_int_literal_node(node):
        return []
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return []
    if not isinstance(node, ast.BinOp):
        return []
    left_steps = _collect_expression_steps(node.left, source)
    right_steps = _collect_expression_steps(node.right, source)
    try:
        left_value = format_fraction(eval_fraction_node(node.left))
        right_value = format_fraction(eval_fraction_node(node.right))
        result_value = format_fraction(eval_fraction_node(node))
    except Exception:
        return left_steps + right_steps
    position = _find_operator_position(source, node)
    return left_steps + right_steps + [{
        'left': left_value,
        'right': right_value,
        'operator': _OPERATOR_SYMBOLS[type(node.op)],
        'result': result_value,
        'pos': position,
    }]


def build_order_block(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _collect_expression_steps(node, source)
    if len(steps) <= 1:
        return []
    pretty_expr, op_map = pretty_expression_with_map(source)
    marks = [' '] * len(pretty_expr)
    for step_index, step in enumerate(steps, start=1):
        raw_pos = step.get('pos')
        if raw_pos is None or raw_pos not in op_map:
            continue
        pretty_pos = op_map[raw_pos]
        label = str(step_index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, char in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = char
    mark_line = ''.join(marks).rstrip()
    return ['Порядок действий:', mark_line, pretty_expr]


def expression_answer(source: str) -> str:
    node = parse_expression_ast(source)
    if node is None:
        return ''
    try:
        return format_fraction(eval_fraction_node(node))
    except Exception:
        return ''


def build_generic_steps_from_expression(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _collect_expression_steps(node, source)
    return [f"{index}) {step['left']} {step['operator']} {step['right']} = {step['result']}" for index, step in enumerate(steps, start=1)]


def pretty_or_rendered_expression(source: str) -> str:
    node = parse_expression_ast(source)
    if node is not None:
        return render_node(node)
    pretty, _ = pretty_expression_with_map(source)
    return pretty


def pretty_equation(source: str) -> str:
    text = re.sub(r'([+\-*/=])', r' \1 ', source)
    text = text.replace('*', '×').replace('/', ':')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def pretty_fraction_expression(source: str) -> str:
    text = re.sub(r'\s+', '', source)
    text = text.replace('+', ' + ').replace('-', ' - ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


__all__ = [
    'build_generic_steps_from_expression',
    'build_order_block',
    'eval_fraction_node',
    'expression_answer',
    'format_fraction',
    'pretty_equation',
    'pretty_expression_with_map',
    'pretty_fraction_expression',
    'pretty_or_rendered_expression',
    'render_node',
]
