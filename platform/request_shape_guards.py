from __future__ import annotations

import ast
import re
from fractions import Fraction
from typing import Optional

from backend.legacy_text_helpers import audit_task_line, finalize_legacy_lines

MULTI_TASK_MESSAGE = (
    'Я решаю только одно задание за раз. Похоже, вы отправили несколько заданий. '
    'Разделите их и отправьте отдельно.'
)

_PREFIX_RE = re.compile(
    r'^(?:задача|пример|уравнение|дроби|геометрия|выражение|математика)\s*:\s*',
    re.IGNORECASE,
)
_COMPARE_PREFIX_RE = re.compile(
    r'^(?:сравни(?:те)?|поставь(?:те)?\s+знак(?:[^\dа-яёa-z]+)?(?:\s+между)?|какой\s+знак\s+поставить(?:\s+между)?|определи(?:те)?\s+знак)\s*:?',
    re.IGNORECASE,
)
_SYSTEM_PREFIX_RE = re.compile(
    r'^(?:реши(?:те)?\s+)?систем[ауые]\s*:?',
    re.IGNORECASE,
)
_NUMBERED_TASK_RE = re.compile(r'(?:^|\n)\s*(?:№\s*\d+|\d+[.)]|[а-яa-z][)])\s*', re.IGNORECASE)
_SOLVER_VERB_RE = re.compile(r'\b(?:реши(?:те)?|вычисли(?:те)?|найди(?:те)?|сравни(?:те)?|поставь(?:те)?|определи(?:те)?|запиши(?:те)?|укажи(?:те)?)\b', re.IGNORECASE)
_ALLOWED_EXPR_CHARS_RE = re.compile(r'^[0-9xyххуу+\-*/().,:÷×·\s]+$', re.IGNORECASE)
_ALLOWED_EQ_CHARS_RE = re.compile(r'^[0-9xy+\-*/().\s=]+$', re.IGNORECASE)


def _normalize_text(text: str) -> str:
    cleaned = str(text or '').strip()
    cleaned = _PREFIX_RE.sub('', cleaned)
    cleaned = cleaned.replace('−', '-').replace('–', '-').replace('—', '-')
    cleaned = cleaned.replace('Х', 'x').replace('х', 'x')
    cleaned = cleaned.replace('Ё', 'Е').replace('ё', 'е')
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    cleaned = re.sub(r'\t+', ' ', cleaned)
    return cleaned.strip()


def _strip_compare_prefix(text: str) -> str:
    return _COMPARE_PREFIX_RE.sub('', text).strip(' :')


def _strip_system_prefix(text: str) -> str:
    return _SYSTEM_PREFIX_RE.sub('', text).strip(' :')


def _normalize_expression_fragment(fragment: str) -> str:
    text = str(fragment or '').strip()
    text = text.strip('[]{}')
    text = text.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    text = re.sub(r'\s+', '', text)
    return text


def _looks_like_expression_fragment(fragment: str) -> bool:
    raw = str(fragment or '').strip()
    if not raw or '=' in raw:
        return False
    if not _ALLOWED_EXPR_CHARS_RE.fullmatch(raw):
        return False
    if not re.search(r'\d|[xyххуy]', raw, flags=re.IGNORECASE):
        return False
    try:
        _eval_fraction_expression(raw)
        return True
    except Exception:
        return False


def _fraction_to_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f'{value.numerator}/{value.denominator}'


def _eval_fraction_expression(fragment: str) -> Fraction:
    source = _normalize_expression_fragment(fragment)
    tree = ast.parse(source, mode='eval')

    def _eval(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return Fraction(int(node.value), 1)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return _eval(node.operand)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
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
        raise ValueError('unsupported expression fragment')

    return _eval(tree)


def _display_fragment(fragment: str) -> str:
    text = str(fragment or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_compare_expressions(raw_text: str) -> Optional[tuple[str, str]]:
    text = _normalize_text(raw_text)
    if not text:
        return None
    lower = text.lower()
    has_compare_cue = bool(
        re.search(r'\b(?:сравни(?:те)?|поставь(?:те)?\s+знак|какой\s+знак\s+поставить|определи(?:те)?\s+знак)\b', lower)
        or '...' in text
        or '…' in text
    )
    body = _strip_compare_prefix(text) if has_compare_cue else text
    if has_compare_cue and ':' in body:
        body = body.split(':', 1)[1].strip()
    body = re.sub(r'^между\s+', '', body, flags=re.IGNORECASE).strip()

    placeholder_match = re.split(r'\s*(?:\.\.\.|…|_{2,}|□|◻)\s*', body, maxsplit=1)
    if len(placeholder_match) == 2 and all(_looks_like_expression_fragment(part) for part in placeholder_match):
        return placeholder_match[0].strip(), placeholder_match[1].strip()

    between_match = re.search(r'между\s+(.+?)\s+и\s+(.+)$', body, flags=re.IGNORECASE)
    if between_match:
        left, right = between_match.group(1).strip(), between_match.group(2).strip()
        if _looks_like_expression_fragment(left) and _looks_like_expression_fragment(right):
            return left, right

    if has_compare_cue:
        split_parts = re.split(r'\s+и\s+', body, maxsplit=1, flags=re.IGNORECASE)
        if len(split_parts) == 2 and all(_looks_like_expression_fragment(part) for part in split_parts):
            return split_parts[0].strip(), split_parts[1].strip()

    return None


def build_compare_expression_payload(raw_text: str) -> Optional[dict]:
    parts = extract_compare_expressions(raw_text)
    if not parts:
        return None
    left_raw, right_raw = parts
    try:
        left_value = _eval_fraction_expression(left_raw)
        right_value = _eval_fraction_expression(right_raw)
    except Exception:
        return None
    sign = '>' if left_value > right_value else '<' if left_value < right_value else '='
    left_text = _display_fragment(left_raw)
    right_text = _display_fragment(right_raw)
    left_value_text = _fraction_to_text(left_value)
    right_value_text = _fraction_to_text(right_value)
    result_text = finalize_legacy_lines([
        'Задача.',
        audit_task_line(raw_text),
        'Решение.',
        f'1) Вычисляем первое выражение: {left_text} = {left_value_text}.',
        f'2) Вычисляем второе выражение: {right_text} = {right_value_text}.',
        f'3) Сравниваем полученные значения: {left_value_text} {sign} {right_value_text}.',
        f'Ответ: {left_text} {sign} {right_text}.',
        'Совет: в задании на сравнение сначала вычисли оба выражения, а потом поставь знак между их значениями.',
    ])
    return {
        'result': result_text,
        'source': 'local-compare-expression',
        'validated': True,
    }


def canonicalize_system_submission(raw_text: str) -> Optional[str]:
    text = _normalize_text(raw_text)
    if not text or text.count('=') < 2:
        return None
    lower = text.lower()
    system_cue = bool(re.search(r'\bсистем[ауые]\b', lower))
    body = _strip_system_prefix(text)
    body = body.strip(' {}[]')
    if system_cue and body.count('=') >= 2 and ';' not in body and ',' not in body and '\n' not in body:
        body = re.sub(r'\s+и\s+', '\n', body, flags=re.IGNORECASE)
    body = re.sub(r'\s*[;]\s*', '\n', body)
    body = re.sub(r'\s*,\s*', '\n', body)
    lines = []
    for raw_line in body.split('\n'):
        line = raw_line.strip()
        line = re.sub(r'^(?:№\s*\d+|\d+[.)])\s*', '', line, flags=re.IGNORECASE)
        if not line:
            continue
        if line.count('=') != 1:
            continue
        compact = re.sub(r'\s+', '', line)
        if not _ALLOWED_EQ_CHARS_RE.fullmatch(compact):
            return None
        if not re.search(r'[xy]', compact, flags=re.IGNORECASE):
            return None
        lines.append(compact)
    if len(lines) < 2 or len(lines) > 3:
        return None
    var_sets = [set(re.findall(r'[xy]', line.lower())) for line in lines]
    if any(not var_set for var_set in var_sets):
        return None
    all_vars = set().union(*var_sets)
    if len(all_vars) == 1 and not system_cue:
        return None
    shared_vars = set.intersection(*var_sets) if len(var_sets) > 1 else set()
    if not system_cue and not shared_vars:
        return None
    return '\n'.join(lines)


def build_multi_task_payload(raw_text: str) -> dict:
    result_text = finalize_legacy_lines([
        'Задача.',
        audit_task_line(raw_text),
        'Решение.',
        MULTI_TASK_MESSAGE,
        'Ответ: разделите задания и отправьте их по отдельности.',
        'Совет: систему уравнений и сравнение двух выражений можно отправлять одним запросом только как одно общее задание.',
    ])
    return {
        'result': result_text,
        'source': 'guard-multi-task',
        'validated': True,
        'code': 'multi_task_not_allowed',
    }


def _segments_with_math(parts: list[str]) -> int:
    count = 0
    for part in parts:
        lowered = part.lower()
        if re.search(r'\d', part) and (_SOLVER_VERB_RE.search(lowered) or re.search(r'[+\-*/=×÷:]', part) or '?' in part):
            count += 1
    return count


def is_multi_task_submission(raw_text: str) -> bool:
    text = _normalize_text(raw_text)
    if not text:
        return False
    if extract_compare_expressions(text) or canonicalize_system_submission(text):
        return False

    lowered = text.lower()
    if re.search(r'\b(?:продолжи(?:те)?|закономерност|ряд)\b', lowered):
        return False

    numbered_matches = _NUMBERED_TASK_RE.findall(text)
    if len(numbered_matches) >= 2 or ('№1' in text and '№2' in text):
        return True

    if ';' in text:
        parts = [part.strip() for part in text.split(';') if part.strip()]
        if _segments_with_math(parts) >= 2:
            return True

    if ',' in text:
        comma_parts = [part.strip() for part in re.split(r'\s*,\s*', text) if part.strip()]
        if len(comma_parts) >= 2:
            mathy_parts = 0
            for part in comma_parts:
                if _looks_like_expression_fragment(part):
                    mathy_parts += 1
                    continue
                compact = re.sub(r'\s+', '', part)
                if compact.count('=') == 1 and re.search(r'[xy]', compact, flags=re.IGNORECASE):
                    mathy_parts += 1
            if mathy_parts >= 2:
                return True

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) >= 2 and _segments_with_math(lines) >= 2:
        return True

    expr_and_expr_match = re.match(
        r'^\s*(?:реши(?:те)?|вычисли(?:те)?|найди(?:те)?|пример|выражение)?\s*:?' \
        r'\s*([^;\n]+?)\s+и\s+([^;\n]+?)\s*$',
        text,
        flags=re.IGNORECASE,
    )
    if expr_and_expr_match:
        left, right = expr_and_expr_match.group(1), expr_and_expr_match.group(2)
        if _looks_like_expression_fragment(left) and _looks_like_expression_fragment(right):
            return True

    equation_and_equation_match = re.match(
        r'^\s*(?:реши(?:те)?|найди(?:те)?|вычисли(?:те)?)?\s*:?\s*([^;\n]+?=[^;\n]+?)\s+и\s+([^;\n]+?=[^;\n]+?)\s*$',
        text,
        flags=re.IGNORECASE,
    )
    if equation_and_equation_match:
        return True

    sentences = [segment.strip() for segment in re.split(r'(?<=[.!?])\s+', text) if segment.strip()]
    if len(sentences) >= 2:
        mathy_sentence_count = 0
        for sentence in sentences:
            lower = sentence.lower()
            if re.search(r'\d', sentence) and (_SOLVER_VERB_RE.search(lower) or '?' in sentence):
                mathy_sentence_count += 1
        if mathy_sentence_count >= 2:
            return True

    return False


__all__ = [
    'MULTI_TASK_MESSAGE',
    'build_compare_expression_payload',
    'build_multi_task_payload',
    'canonicalize_system_submission',
    'extract_compare_expressions',
    'is_multi_task_submission',
]
