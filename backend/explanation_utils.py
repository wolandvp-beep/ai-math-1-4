from __future__ import annotations

import re
from fractions import Fraction
from typing import Iterable, List

from .advice import default_advice
from .expression_parser import normalize_expression_source, parse_expression_ast
from .text_utils import normalize_cyrillic_x, strip_known_prefix
from .expression_rendering import (
    build_generic_steps_from_expression,
    build_order_block,
    expression_answer,
    pretty_equation,
    pretty_fraction_expression,
    pretty_or_rendered_expression,
)

BANNED_OPENERS = re.compile(
    r'^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\b',
    re.IGNORECASE,
)
LEADING_FILLER_SENTENCE = re.compile(
    r'^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\b[^.!?\n]*[.!?]\s*',
    re.IGNORECASE,
)
SECTION_PREFIX_RE = re.compile(r'^(ответ|совет|проверка)\s*:\s*', re.IGNORECASE)
LOW_VALUE_BODY_PATTERNS = [
    re.compile(r'^решаем по шагам$', re.IGNORECASE),
    re.compile(r'^это задача(?:[^.!?]*)$', re.IGNORECASE),
    re.compile(r'^известны числа$', re.IGNORECASE),
]


def sanitize_model_text(text: str) -> str:
    cleaned = str(text or '').replace('\r', '')
    while True:
        updated = LEADING_FILLER_SENTENCE.sub('', cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    cleaned = cleaned.replace('**', '').replace('__', '').replace('`', '')
    cleaned = re.sub(r'^\s*#{1,6}\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
    cleaned = cleaned.replace('\\', '')
    cleaned = re.sub(r'^\s*[-*•]\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    raw_lines = [line.strip() for line in cleaned.split('\n')]
    lines = []
    seen = set()
    for raw in raw_lines:
        if not raw:
            continue
        if BANNED_OPENERS.match(raw):
            continue
        raw = SECTION_PREFIX_RE.sub(lambda m: f"{m.group(1).capitalize()}: ", raw)
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(raw)
    return '\n'.join(lines).strip()


def split_sections(text: str) -> dict:
    cleaned = sanitize_model_text(text)
    body: List[str] = []
    answer = ''
    advice = ''
    check = ''
    for raw in cleaned.split('\n'):
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith('ответ:'):
            value = line.split(':', 1)[1].strip().rstrip('.!?').strip()
            if value and not answer:
                answer = value
            continue
        if lower.startswith('совет:'):
            value = line.split(':', 1)[1].strip().rstrip('.!?').strip()
            if value and not advice:
                advice = value
            continue
        if lower.startswith('проверка:'):
            value = line.split(':', 1)[1].strip()
            if value and not check:
                check = f'Проверка: {value}'
            continue
        body.append(line)
    return {'body': body, 'answer': answer, 'advice': advice, 'check': check}


def finalize_line(line: str) -> str:
    raw = str(line or '').rstrip()
    if not raw:
        return ''
    stripped = raw.strip()
    if re.fullmatch(r'[ 0-9()+\-×:=/]+', raw):
        return raw
    if re.match(r'^(?:Пример|Порядок действий|Решение по действиям|Решение|Задача|Уравнение)\b', stripped, flags=re.IGNORECASE):
        return stripped
    if stripped[-1] not in '.!?':
        stripped += '.'
    return stripped


def finalize_text(lines: Iterable[str]) -> str:
    finalized = []
    for line in lines:
        fixed = finalize_line(line)
        if fixed:
            finalized.append(fixed)
    return '\n'.join(finalized).strip()


def strip_sequence_prefix(line: str) -> str:
    text = str(line or '').strip()
    text = re.sub(r'^\d+[.)]\s*', '', text)
    text = re.sub(r'^(?:сначала|потом|дальше)\s+', '', text, flags=re.IGNORECASE)
    if text:
        text = text[0].upper() + text[1:]
    return text


def number_lines(lines: Iterable[str]) -> List[str]:
    result: List[str] = []
    counter = 1
    for raw in lines:
        line = str(raw or '').strip()
        if not line:
            continue
        if re.match(r'^\d+\)', line):
            result.append(line)
            counter += 1
            continue
        line = strip_sequence_prefix(line)
        result.append(f'{counter}) {line}')
        counter += 1
    return result


def statement_text(raw_text: str) -> str:
    text = strip_known_prefix(str(raw_text or '').replace('\r', ' ').replace('\n', ' '))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or '').strip()
    if not value:
        return value
    if re.search(r'[А-Яа-я]', value):
        return value
    lower = str(raw_text or '').lower().replace('ё', 'е')
    if 'руб' in lower or 'денег' in lower:
        return f'{value} руб.'
    return value


def to_equation_source(raw_text: str) -> str | None:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = re.sub(r'[−–—]', '-', text)
    text = normalize_cyrillic_x(text)
    text = text.replace('X', 'x').replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    text = re.sub(r'\s+', '', text)
    if text.count('=') != 1 or text.count('x') != 1:
        return None
    if not re.fullmatch(r'[\dx=+\-*/]+', text):
        return None
    return text


def to_fraction_source(raw_text: str) -> str | None:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = re.sub(r'[−–—]', '-', text)
    text = re.sub(r'[=?]+$', '', text).strip()
    if not re.fullmatch(r'\s*\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+\s*', text):
        return None
    return text


def format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = split_sections(base_text)
    lines: List[str] = []
    statement = statement_text(raw_text)
    if statement and kind in {'word', 'geometry'}:
        lines.append('Задача.')
        lines.append(statement)
        lines.append('Решение.')
    else:
        lines.append('Решение.')
    lines.extend(number_lines(parts['body']))
    if parts['check']:
        lines.append(parts['check'])
    answer = maybe_enrich_answer(parts['answer'], raw_text, kind) or 'проверь запись'
    lines.append(f'Ответ: {answer}')
    advice = parts['advice'] or default_advice(kind)
    lines.append(f'Совет: {advice}')
    return finalize_text(lines)


def format_equation_solution(raw_text: str, base_text: str) -> str:
    parts = split_sections(base_text)
    source = to_equation_source(raw_text) or normalize_cyrillic_x(strip_known_prefix(raw_text))
    pretty = pretty_equation(source)
    answer = parts['answer'] or 'проверь запись'
    if re.fullmatch(r'-?\d+(?:/\d+)?', answer):
        answer = f'x = {answer}'
    lines: List[str] = [f'Уравнение: {pretty}', 'Решение.']
    lines.extend(number_lines(parts['body']))
    if parts['check']:
        lines.append(parts['check'])
    lines.append(f'Ответ: {answer}')
    advice = parts['advice'] or default_advice('equation')
    lines.append(f'Совет: {advice}')
    return finalize_text(lines)


def format_fraction_solution(raw_text: str, base_text: str) -> str:
    parts = split_sections(base_text)
    source = to_fraction_source(raw_text) or strip_known_prefix(raw_text)
    pretty = pretty_fraction_expression(source)
    answer = parts['answer'] or 'проверь запись'
    lines: List[str] = [f'Пример: {pretty} = {answer}', 'Решение']
    lines.extend(number_lines(parts['body']))
    if parts['check']:
        lines.append(parts['check'])
    lines.append(f'Ответ: {answer}')
    advice = parts['advice'] or default_advice('fraction')
    lines.append(f'Совет: {advice}')
    return finalize_text(lines)


__all__ = [
    'expression_answer',
    'build_generic_steps_from_expression',
    'build_order_block',
    'default_advice',
    'finalize_line',
    'finalize_text',
    'format_equation_solution',
    'format_fraction_solution',
    'format_generic_solution',
    'maybe_enrich_answer',
    'number_lines',
    'pretty_or_rendered_expression',
    'split_sections',
    'statement_text',
    'to_equation_source',
    'to_fraction_source',
]
