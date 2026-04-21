from __future__ import annotations

from typing import Optional

from .expression_parser import BinaryOperation
from .formatters import format_column_operation_solution
from .math_explainers import (
    explain_column_addition,
    explain_column_subtraction,
    explain_long_division,
    explain_long_multiplication,
)


def get_column_explanation_text(operation: BinaryOperation) -> Optional[str]:
    if operation.operator == '+':
        return explain_column_addition([operation.left, operation.right])
    if operation.operator == '-':
        if operation.left < operation.right:
            return None
        return explain_column_subtraction(operation.left, operation.right)
    if operation.operator == '×':
        return explain_long_multiplication(operation.left, operation.right)
    if operation.operator == '÷':
        return explain_long_division(operation.left, operation.right)
    return None


def build_direct_column_payload(operation: BinaryOperation) -> Optional[dict]:
    explanation_text = get_column_explanation_text(operation)
    if not explanation_text:
        return None
    formatted = format_column_operation_solution(operation, explanation_text)
    return {
        'result': formatted,
        'source': f'column_math:direct:{operation.operator}',
        'validated': True,
        'column_operation': {
            'left': operation.left,
            'operator': operation.operator,
            'right': operation.right,
        },
    }


__all__ = ['build_direct_column_payload', 'get_column_explanation_text']
