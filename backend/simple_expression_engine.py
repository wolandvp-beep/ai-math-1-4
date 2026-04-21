from __future__ import annotations

from typing import Optional

from .expression_parser import BinaryOperation
from .formatters import format_simple_expression_solution
from .math_explainers import (
    explain_simple_addition,
    explain_simple_division,
    explain_simple_multiplication,
    explain_simple_subtraction,
)


def get_simple_expression_text(operation: BinaryOperation) -> Optional[str]:
    if operation.operator == '+':
        return explain_simple_addition(operation.left, operation.right)
    if operation.operator == '-':
        return explain_simple_subtraction(operation.left, operation.right)
    if operation.operator == '×':
        return explain_simple_multiplication(operation.left, operation.right)
    if operation.operator == '÷':
        if operation.right == 0:
            return None
        return explain_simple_division(operation.left, operation.right)
    return None


def build_direct_simple_expression_payload(operation: BinaryOperation) -> Optional[dict]:
    explanation_text = get_simple_expression_text(operation)
    if not explanation_text:
        return None
    formatted = format_simple_expression_solution(operation, explanation_text)
    return {
        'result': formatted,
        'source': f'expression_simple:direct:{operation.operator}',
        'validated': True,
        'simple_operation': {
            'left': operation.left,
            'operator': operation.operator,
            'right': operation.right,
        },
    }


__all__ = ['build_direct_simple_expression_payload', 'get_simple_expression_text']
