from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from ..expression_parser import BinaryOperation, extract_simple_binary_operation
from ..column_engine import build_direct_column_payload
from ..legacy_bridge import build_legacy_explanation


def _digit_length(value: int) -> int:
    return len(str(abs(int(value))))


def should_use_column(operation: BinaryOperation) -> bool:
    a_length = _digit_length(operation.left)
    b_length = _digit_length(operation.right)
    if operation.operator == '×':
        return a_length >= 2 or b_length >= 2
    if operation.operator == '÷':
        return a_length >= 3 or b_length >= 2
    return a_length >= 3 or b_length >= 3 or (a_length >= 2 and b_length >= 2)


def get_column_operation(raw_text: str) -> Optional[BinaryOperation]:
    operation = extract_simple_binary_operation(raw_text)
    if not operation:
        return None
    if operation.operator == '÷' and operation.right == 0:
        return operation
    return operation if should_use_column(operation) else None


async def build_column_math_explanation(raw_text: str) -> Optional[dict]:
    operation = get_column_operation(raw_text)
    if not operation:
        return None

    direct_payload = build_direct_column_payload(operation)
    if direct_payload:
        return direct_payload

    result = await build_legacy_explanation(raw_text)
    if not isinstance(result, dict):
        return None
    enriched = dict(result)
    source = str(enriched.get('source') or 'legacy')
    if not source.startswith('legacy:column_math'):
        enriched['source'] = 'legacy:column_math'
    enriched['column_operation'] = asdict(operation)
    return enriched
