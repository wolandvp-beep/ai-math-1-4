from __future__ import annotations

import re
from typing import Optional

from ..legacy_text_helpers import audit_task_line, finalize_legacy_lines
from ..quantity_units import (
    _frac20260416_cont_norm,
    _unit20260416_cont_base_unit,
    _unit20260416_cont_format_compound_from_base,
    _unit20260416_cont_parse_quantity,
    _unit20260416_cont_total_in_unit,
)


def build_fraction_time_total_explanation(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    lower = text.lower()
    match = re.search(r'(?:проехал|проехала|прошел|прошла|прошёл)\s+(?:четвертую|шестую)\s+часть пути(?:\s+за)?\s*(\d+)\s*минут', lower)
    if not match:
        return None
    part_time = int(match.group(1))
    denominator = 4 if 'четверт' in lower else 6
    whole_time = part_time * denominator
    lines = [
        'Задача.',
        audit_task_line(raw_text),
        'Решение.',
        f'Что известно: 1/{denominator} пути пройдена за {part_time} минут.',
        'Что нужно найти: время на весь путь.',
        f'1) Весь путь состоит из {denominator} таких частей.',
        f'2) Находим всё время: {part_time} × {denominator} = {whole_time} минут.',
        f'Ответ: {whole_time} минут',
        'Совет: если одна доля пути занимает известное время, всё время находят умножением на число долей',
    ]
    return finalize_legacy_lines(lines)


def build_named_quantity_arithmetic_explanation(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    match = re.fullmatch(r'(.+?)\s*([+\-])\s*(.+?)\s*=?', text)
    if not match:
        return None
    left_text, operator, right_text = match.group(1).strip(), match.group(2), match.group(3).strip()
    left = _unit20260416_cont_parse_quantity(left_text)
    right = _unit20260416_cont_parse_quantity(right_text)
    if not left or not right or left['group'] != right['group']:
        return None

    all_units = left['units'] + right['units']
    group = left['group']
    base_unit = _unit20260416_cont_base_unit(group, all_units)
    left_base = _unit20260416_cont_total_in_unit(left, base_unit)
    right_base = _unit20260416_cont_total_in_unit(right, base_unit)
    result_base = left_base + right_base if operator == '+' else left_base - right_base
    if result_base < 0:
        return None

    answer_text = _unit20260416_cont_format_compound_from_base(result_base, group, base_unit, all_units)
    action_text = 'Складываем' if operator == '+' else 'Вычитаем'
    lines = [
        'Пример: ' + raw_text.strip(),
        'Порядок действий:',
        '1',
        raw_text.strip(),
        'Решение по действиям:',
        f'1) Переводим первое именованное число в {base_unit}: {left["pretty"]} = {left_base} {base_unit}.',
        f'2) Переводим второе именованное число в {base_unit}: {right["pretty"]} = {right_base} {base_unit}.',
        f'3) {action_text}: {left_base} {operator} {right_base} = {result_base} {base_unit}.',
        f'4) Переводим ответ обратно: {result_base} {base_unit} = {answer_text}.',
        f'Ответ: {answer_text}',
        'Совет: при действиях с именованными величинами сначала переводят их в одинаковые единицы',
    ]
    return finalize_legacy_lines(lines)
