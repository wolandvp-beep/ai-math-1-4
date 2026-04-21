from __future__ import annotations

from typing import Optional

from .column_engine import build_direct_column_payload
from .expression_parser import extract_simple_binary_operation, normalize_expression_source, parse_expression_ast
from .handlers.column_math import should_use_column
from .mixed_expression_engine import build_direct_mixed_expression_payload
from .simple_expression_engine import build_direct_simple_expression_payload


def build_direct_math_expression_payload(raw_text: str) -> Optional[dict]:
    source = normalize_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None

    operation = extract_simple_binary_operation(raw_text)
    if operation:
        if operation.operator == '÷' and operation.right == 0:
            return None
        if should_use_column(operation):
            return build_direct_column_payload(operation)
        return build_direct_simple_expression_payload(operation)

    return build_direct_mixed_expression_payload(raw_text)


__all__ = ['build_direct_math_expression_payload']
