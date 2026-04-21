from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Optional

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


@dataclass(frozen=True)
class BinaryOperation:
    left: int
    operator: str
    right: int


def normalize_expression_source(raw_text: str) -> str:
    text = str(raw_text or '').strip()
    if not text:
        return ''
    text = re.sub(r'^(?:пример|реши|вычисли|найди)\b\s*[:\-]?\s*', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'[=?]+$', '', text).strip()
    text = text.replace('×', '*').replace('x', '*').replace('X', '*').replace('х', '*').replace('Х', '*')
    text = text.replace('÷', '/').replace(':', '/')
    text = text.replace('−', '-').replace('–', '-').replace('—', '-')
    return text


def validate_expression_ast(node: ast.AST) -> bool:
    if isinstance(node, ast.Expression):
        return validate_expression_ast(node.body)
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, _ALLOWED_BINOPS) and validate_expression_ast(node.left) and validate_expression_ast(node.right)
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.USub) and validate_expression_ast(node.operand)
    return isinstance(node, ast.Constant) and type(node.value) is int


def parse_expression_ast(source: str) -> Optional[ast.AST]:
    try:
        parsed = ast.parse(source, mode='eval')
    except SyntaxError:
        return None
    if not validate_expression_ast(parsed):
        return None
    return parsed.body


def _as_int_literal(node: ast.AST) -> Optional[int]:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return int(node.value)
    return None


def extract_simple_binary_operation(raw_text: str) -> Optional[BinaryOperation]:
    source = normalize_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if not isinstance(node, ast.BinOp):
        return None
    left = _as_int_literal(node.left)
    right = _as_int_literal(node.right)
    if left is None or right is None:
        return None
    operator = '+' if isinstance(node.op, ast.Add) else '-' if isinstance(node.op, ast.Sub) else '×' if isinstance(node.op, ast.Mult) else '÷' if isinstance(node.op, ast.Div) else ''
    if not operator:
        return None
    return BinaryOperation(left=left, operator=operator, right=right)
