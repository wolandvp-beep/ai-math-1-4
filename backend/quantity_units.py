from __future__ import annotations

import re
from typing import Optional

from .legacy_text_helpers import audit_task_line, finalize_legacy_lines
from .text_utils import normalize_dashes, normalize_word_problem_text

_FRAC20260416_CONT_WORDS = {
    'половин': (1, 2),
    'втор': (1, 2),
    'треть': (1, 3),
    'четверт': (1, 4),
    'пят': (1, 5),
    'шест': (1, 6),
    'седьм': (1, 7),
    'восьм': (1, 8),
    'девят': (1, 9),
    'десят': (1, 10),
}


def _frac20260416_cont_norm(text: str) -> str:
    text = normalize_word_problem_text(text)
    text = normalize_dashes(text)
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _frac20260416_cont_parse_fraction(fragment: str) -> Optional[tuple[int, int]]:
    frag = _frac20260416_cont_norm(fragment).lower()
    m = re.search(r'(\d+)\s*/\s*(\d+)', frag)
    if m:
        return int(m.group(1)), int(m.group(2))
    for key, value in _FRAC20260416_CONT_WORDS.items():
        if key in frag:
            return value
    return None


_UNIT20260416_CONT_GROUPS = {
    'length': {'км': 1000, 'м': 1, 'дм': 0.1, 'см': 0.01, 'мм': 0.001},
    'mass': {'т': 1000, 'ц': 100, 'кг': 1, 'г': 0.001},
    'time': {'сут': 86400, 'ч': 3600, 'мин': 60, 'с': 1},
}

_UNIT20260416_CONT_ALIASES = {
    'суток': 'сут', 'сутки': 'сут', 'сут': 'сут',
    'час': 'ч', 'часа': 'ч', 'часов': 'ч', 'ч': 'ч',
    'минута': 'мин', 'минуты': 'мин', 'минут': 'мин', 'мин': 'мин',
    'секунда': 'с', 'секунды': 'с', 'секунд': 'с', 'сек': 'с', 'с': 'с',
    'км': 'км', 'метр': 'м', 'метра': 'м', 'метров': 'м', 'м': 'м',
    'дециметр': 'дм', 'дециметра': 'дм', 'дециметров': 'дм', 'дм': 'дм',
    'сантиметр': 'см', 'сантиметра': 'см', 'сантиметров': 'см', 'см': 'см',
    'миллиметр': 'мм', 'миллиметра': 'мм', 'миллиметров': 'мм', 'мм': 'мм',
    'тонна': 'т', 'тонны': 'т', 'тонн': 'т', 'т': 'т',
    'центнер': 'ц', 'центнера': 'ц', 'центнеров': 'ц', 'ц': 'ц',
    'килограмм': 'кг', 'килограмма': 'кг', 'килограммов': 'кг', 'кг': 'кг',
    'грамм': 'г', 'грамма': 'г', 'граммов': 'г', 'г': 'г',
}

_UNIT20260416_CONT_TOKEN_RE = re.compile(
    r'(\d+)\s*(суток|сутки|сут|часа|часов|час|ч|минуты|минут|минута|мин|секунды|секунд|секунда|сек|с|км|метров|метра|метр|м|дециметров|дециметра|дециметр|дм|сантиметров|сантиметра|сантиметр|см|миллиметров|миллиметра|миллиметр|мм|тонн|тонны|тонна|т|центнеров|центнера|центнер|ц|килограммов|килограмма|килограмм|кг|граммов|грамма|грамм|г)',
    re.IGNORECASE,
)


def _unit20260416_cont_parse_quantity(expr: str) -> Optional[dict]:
    matches = list(_UNIT20260416_CONT_TOKEN_RE.finditer(expr))
    if not matches:
        return None
    tokens = []
    normalized_units = []
    groups = set()
    for m in matches:
        value = int(m.group(1))
        raw_unit = m.group(2).lower()
        unit = _UNIT20260416_CONT_ALIASES.get(raw_unit)
        if not unit:
            return None
        group = next((g for g, mp in _UNIT20260416_CONT_GROUPS.items() if unit in mp), None)
        if not group:
            return None
        tokens.append((value, unit))
        normalized_units.append(unit)
        groups.add(group)
    if len(groups) != 1:
        return None
    covered = ''.join(m.group(0) for m in matches)
    cleaned = re.sub(r'[^\dа-яa-z]+', '', expr.lower())
    if covered and re.sub(r'[^\dа-яa-z]+', '', covered.lower()) != cleaned:
        return None
    group = groups.pop()
    total = 0.0
    for value, unit in tokens:
        total += value * _UNIT20260416_CONT_GROUPS[group][unit]
    pretty = ' '.join(f'{value} {unit}' for value, unit in tokens)
    return {
        'group': group,
        'tokens': tokens,
        'units': normalized_units,
        'pretty': pretty,
        'total': total,
    }


def _unit20260416_cont_base_unit(group: str, units: list[str]) -> str:
    unit_map = _UNIT20260416_CONT_GROUPS[group]
    return min(set(units), key=lambda u: unit_map[u])


def _unit20260416_cont_total_in_unit(quantity: dict, unit: str) -> int:
    scale = _UNIT20260416_CONT_GROUPS[quantity['group']][unit]
    return int(round(quantity['total'] / scale))


def _unit20260416_cont_format_number(value: int) -> str:
    return str(int(value))


def _unit20260416_cont_format_compound(total_value: int, group: str, units_present: list[str], base_unit: str | None = None) -> str:
    ordered = {
        'time': ['сут', 'ч', 'мин', 'с'],
        'mass': ['т', 'ц', 'кг', 'г'],
        'length': ['км', 'м', 'дм', 'см', 'мм'],
    }[group]
    present = set(units_present)
    active = [u for u in ordered if u in present]
    if not active:
        active = [base_unit or ordered[0]]
    if base_unit is None:
        base_unit = active[-1]
    start = ordered.index(active[0])
    end = max(ordered.index(active[-1]), ordered.index(base_unit))
    use_units = ordered[start:end + 1]
    return _unit20260416_cont_format_compound_from_base(total_value, group, base_unit, use_units)


_UNIT20260416_CONT_SMALLEST_SCALES = {
    'time': {'сут': 86400, 'ч': 3600, 'мин': 60, 'с': 1},
    'mass': {'т': 1000000, 'ц': 100000, 'кг': 1000, 'г': 1},
    'length': {'км': 1000000, 'м': 1000, 'дм': 100, 'см': 10, 'мм': 1},
}


def _unit20260416_cont_format_compound_from_base(total_value: int, group: str, base_unit: str, units_present: list[str]) -> str:
    ordered = {
        'time': ['сут', 'ч', 'мин', 'с'],
        'mass': ['т', 'ц', 'кг', 'г'],
        'length': ['км', 'м', 'дм', 'см', 'мм'],
    }[group]
    scales = _UNIT20260416_CONT_SMALLEST_SCALES[group]
    present = set(units_present)
    active = [u for u in ordered if u in present]
    if not active:
        active = [base_unit]
    start = ordered.index(active[0])
    end = max(ordered.index(active[-1]), ordered.index(base_unit))
    use_units = ordered[start:end + 1]
    smallest_unit = use_units[-1]
    total_smallest = int(round(total_value * scales[base_unit] / scales[smallest_unit]))
    remainder = total_smallest
    smallest_scale = scales[smallest_unit]
    parts = []
    for unit in use_units:
        unit_scale = scales[unit]
        factor = unit_scale // smallest_scale
        if unit == smallest_unit:
            amount = remainder
        else:
            amount, remainder = divmod(remainder, factor)
        if amount:
            parts.append(f'{amount} {unit}')
    if not parts:
        parts.append(f'0 {smallest_unit}')
    return ' '.join(parts)


def _unit20260416_cont_try_arithmetic(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    m = re.fullmatch(r'(.+?)\s*([+\-])\s*(.+?)\s*=?', text)
    if not m:
        return None
    left_text, op, right_text = m.group(1).strip(), m.group(2), m.group(3).strip()
    left = _unit20260416_cont_parse_quantity(left_text)
    right = _unit20260416_cont_parse_quantity(right_text)
    if not left or not right or left['group'] != right['group']:
        return None

    all_units = left['units'] + right['units']
    group = left['group']
    base_unit = _unit20260416_cont_base_unit(group, all_units)
    left_base = _unit20260416_cont_total_in_unit(left, base_unit)
    right_base = _unit20260416_cont_total_in_unit(right, base_unit)
    result_base = left_base + right_base if op == '+' else left_base - right_base
    if result_base < 0:
        return None

    answer_text = _unit20260416_cont_format_compound(result_base, group, all_units, base_unit)
    sign_text = '+' if op == '+' else '-'
    action_text = 'Складываем' if op == '+' else 'Вычитаем'
    lines = [
        'Пример: ' + raw_text.strip(),
        'Решение.',
        f'1) Переводим первое именованное число в {base_unit}: {left["pretty"]} = {left_base} {base_unit}.',
        f'2) Переводим второе именованное число в {base_unit}: {right["pretty"]} = {right_base} {base_unit}.',
        f'3) {action_text}: {left_base} {sign_text} {right_base} = {result_base} {base_unit}.',
        f'4) Переводим ответ обратно: {result_base} {base_unit} = {answer_text}.',
        f'Ответ: {answer_text}',
        'Совет: при действиях с именованными величинами сначала переводят их в одинаковые единицы',
    ]
    return finalize_legacy_lines(lines)


__all__ = [
    '_FRAC20260416_CONT_WORDS',
    '_UNIT20260416_CONT_ALIASES',
    '_UNIT20260416_CONT_GROUPS',
    '_UNIT20260416_CONT_SMALLEST_SCALES',
    '_UNIT20260416_CONT_TOKEN_RE',
    '_frac20260416_cont_norm',
    '_frac20260416_cont_parse_fraction',
    '_unit20260416_cont_base_unit',
    '_unit20260416_cont_format_compound',
    '_unit20260416_cont_format_compound_from_base',
    '_unit20260416_cont_format_number',
    '_unit20260416_cont_parse_quantity',
    '_unit20260416_cont_total_in_unit',
    '_unit20260416_cont_try_arithmetic',
    'audit_task_line',
    'finalize_legacy_lines',
]
