from __future__ import annotations

"""Statically materialized handler source for legacy_geometry_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_rectangle_geometry(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    if 'прямоугольник' not in lower:
        return None

    asks_perimeter = 'периметр' in lower
    asks_area = 'площад' in lower
    asks_unknown_side = any(fragment in lower for fragment in ('другую сторону', 'вторую сторону', 'найди ширину', 'найди длину'))

    perimeter_match = re.search(
        r'периметр(?:\s+прямоугольника)?\s*(?:равен|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)',
        lower,
    )
    known_side_match = re.search(
        r'(?:одна\s+сторона|первая\s+сторона|длина|ширина)\s*(?:прямоугольника\s*)?(?:равна|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)',
        lower,
    )
    if asks_unknown_side and perimeter_match and known_side_match:
        perimeter = _to_fraction(perimeter_match.group(1))
        perimeter_unit = perimeter_match.group(2).lower()
        known_side = _to_fraction(known_side_match.group(1))
        side_unit = known_side_match.group(2).lower()

        if perimeter_unit != side_unit:
            target_unit = perimeter_unit if _LENGTH_UNITS[perimeter_unit] < _LENGTH_UNITS[side_unit] else side_unit
            perimeter_value = _convert_length(perimeter, perimeter_unit, target_unit)
            known_side_value = _convert_length(known_side, side_unit, target_unit)
            unit = target_unit
        else:
            perimeter_value = perimeter
            known_side_value = known_side
            unit = perimeter_unit

        half_perimeter = perimeter_value / 2
        other_side = half_perimeter - known_side_value
        if other_side <= 0:
            return None

        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: периметр прямоугольника {_format_number(perimeter_value)} {unit}, одна известная сторона {_format_number(known_side_value)} {unit}.',
            'Что нужно найти: другую сторону прямоугольника.',
            '1) У прямоугольника длина и ширина повторяются по два раза, поэтому сначала находим сумму длины и ширины.',
            f'2) {_format_number(perimeter_value)} : 2 = {_format_number(half_perimeter)} {unit}.',
            '3) Теперь из суммы длины и ширины вычитаем известную сторону.',
            f'4) {_format_number(half_perimeter)} - {_format_number(known_side_value)} = {_format_number(other_side)} {unit}.',
            f'Ответ: {_format_number(other_side)} {unit}',
            'Совет: если известен периметр прямоугольника и одна сторона, сначала делят периметр на 2, а потом вычитают известную сторону.',
        ])

    if not (asks_perimeter or asks_area):
        return None

    side_match = re.search(
        r'со\s+сторонами\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)\s*и\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)?',
        lower,
    )
    if side_match:
        a = _to_fraction(side_match.group(1))
        unit_a = side_match.group(2)
        b = _to_fraction(side_match.group(3))
        unit_b = (side_match.group(4) or unit_a).lower()
    else:
        pair_match = re.search(
            r'длин(?:а|ой)\s*(?:прямоугольника\s*)?(?:равна\s*)?(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)[^\d]{0,40}ширин(?:а|ой)\s*(?:прямоугольника\s*)?(?:равна\s*)?(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)',
            lower,
        )
        if not pair_match:
            pair_match = re.search(
                r'ширин(?:а|ой)\s*(?:прямоугольника\s*)?(?:равна\s*)?(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)[^\d]{0,40}длин(?:а|ой)\s*(?:прямоугольника\s*)?(?:равна\s*)?(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)',
                lower,
            )
            if not pair_match:
                return None
            b = _to_fraction(pair_match.group(1))
            unit_b = pair_match.group(2)
            a = _to_fraction(pair_match.group(3))
            unit_a = pair_match.group(4)
        else:
            a = _to_fraction(pair_match.group(1))
            unit_a = pair_match.group(2)
            b = _to_fraction(pair_match.group(3))
            unit_b = pair_match.group(4)

    if unit_a != unit_b:
        target_unit = unit_a if _LENGTH_UNITS[unit_a] < _LENGTH_UNITS[unit_b] else unit_b
        a_value = _convert_length(a, unit_a, target_unit)
        b_value = _convert_length(b, unit_b, target_unit)
        unit = target_unit
    else:
        a_value = a
        b_value = b
        unit = unit_a

    if asks_perimeter:
        half_perimeter = a_value + b_value
        perimeter = half_perimeter * 2
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: одна сторона прямоугольника {_format_number(a_value)} {unit}, другая сторона {_format_number(b_value)} {unit}.',
            'Что нужно найти: периметр прямоугольника.',
            f'1) Складываем длину и ширину: {_format_number(a_value)} + {_format_number(b_value)} = {_format_number(half_perimeter)} {unit}.',
            f'2) У прямоугольника две такие суммы, поэтому умножаем на 2: {_format_number(half_perimeter)} × 2 = {_format_number(perimeter)} {unit}.',
            f'Ответ: {_format_number(perimeter)} {unit}',
            'Совет: чтобы найти периметр прямоугольника, складывают длину и ширину и умножают сумму на 2.',
        ])

    area = a_value * b_value
    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: одна сторона прямоугольника {_format_number(a_value)} {unit}, другая сторона {_format_number(b_value)} {unit}.',
        'Что нужно найти: площадь прямоугольника.',
        '1) Площадь прямоугольника находят умножением длины на ширину.',
        f'2) {_format_number(a_value)} × {_format_number(b_value)} = {_format_number(area)} {unit}².',
        f'Ответ: {_format_number(area)} {unit}²',
        'Совет: площадь прямоугольника равна длине, умноженной на ширину.',
    ])


def _try_square_geometry(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    if 'квадрат' not in lower:
        return None

    asks_perimeter = 'периметр' in lower
    asks_area = 'площад' in lower
    asks_side = any(fragment in lower for fragment in ('сторону квадрата', 'сторона квадрата', 'найди сторону', 'какова сторона'))

    side_match = (
        re.search(r'сторон(?:а|ой)(?:\s+квадрата)?\s*(?:равна|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)\b', lower)
        or re.search(r'квадрат\s+со\s+стороной\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)\b', lower)
    )
    perimeter_match = re.search(
        r'периметр(?:\s+квадрата)?\s*(?:равен|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)\b',
        lower,
    )
    area_match = re.search(
        r'площад(?:ь|и)(?:\s+квадрата)?\s*(?:равна|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)\s*(?:\^?2|²)',
        lower,
    )

    if asks_side and area_match:
        area_value = _to_fraction(area_match.group(1))
        unit = area_match.group(2).lower()
        side_value = _perfect_square_root(area_value)
        if side_value is None or side_value <= 0:
            return None
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: площадь квадрата равна {_format_number(area_value)} {unit}².',
            'Что нужно найти: сторону квадрата.',
            '1) У квадрата площадь равна стороне, умноженной на сторону.',
            f'2) Подбираем число, которое при умножении само на себя даёт {_format_number(area_value)}: {_format_number(side_value)} × {_format_number(side_value)} = {_format_number(area_value)}.',
            f'Ответ: {_format_number(side_value)} {unit}',
            'Совет: чтобы найти сторону квадрата по площади, нужно вспомнить, какое число в квадрате даёт эту площадь.',
        ])

    if asks_side and perimeter_match:
        perimeter_value = _to_fraction(perimeter_match.group(1))
        unit = perimeter_match.group(2).lower()
        side_value = perimeter_value / 4
        if side_value <= 0:
            return None
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: периметр квадрата равен {_format_number(perimeter_value)} {unit}.',
            'Что нужно найти: сторону квадрата.',
            '1) У квадрата 4 равные стороны, поэтому делим периметр на 4.',
            f'2) {_format_number(perimeter_value)} : 4 = {_format_number(side_value)} {unit}.',
            f'Ответ: {_format_number(side_value)} {unit}',
            'Совет: сторону квадрата находят делением периметра на 4.',
        ])

    if not side_match:
        return None
    side_value = _to_fraction(side_match.group(1))
    unit = side_match.group(2).lower()
    if side_value <= 0:
        return None

    if asks_perimeter:
        perimeter_value = side_value * 4
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: сторона квадрата равна {_format_number(side_value)} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата 4 равные стороны, значит сторону умножаем на 4.',
            f'2) {_format_number(side_value)} × 4 = {_format_number(perimeter_value)} {unit}.',
            f'Ответ: {_format_number(perimeter_value)} {unit}',
            'Совет: периметр квадрата равен четырём его сторонам.',
        ])

    if asks_area:
        area_value = side_value * side_value
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: сторона квадрата равна {_format_number(side_value)} {unit}.',
            'Что нужно найти: площадь квадрата.',
            '1) Площадь квадрата находят умножением стороны на сторону.',
            f'2) {_format_number(side_value)} × {_format_number(side_value)} = {_format_number(area_value)} {unit}².',
            f'Ответ: {_format_number(area_value)} {unit}²',
            'Совет: площадь квадрата равна стороне, умноженной на такую же сторону.',
        ])

    return None


def _try_triangle_perimeter(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    if 'треуголь' not in lower or 'периметр' not in lower:
        return None

    side_measurements = _extract_distance_values(lower)
    if len(side_measurements) < 3:
        return None

    asks_third_side = any(fragment in lower for fragment in ('третью сторону', 'третья сторона', 'третьей стороны', 'другую сторону'))
    if asks_third_side:
        perimeter_value_raw, perimeter_unit, _ = side_measurements[0]
        first_side_raw, first_side_unit, _ = side_measurements[1]
        second_side_raw, second_side_unit, _ = side_measurements[2]
        unit = min((perimeter_unit, first_side_unit, second_side_unit), key=lambda current: _LENGTH_UNITS[current])
        perimeter_value = _convert_length(perimeter_value_raw, perimeter_unit, unit)
        first_side = _convert_length(first_side_raw, first_side_unit, unit)
        second_side = _convert_length(second_side_raw, second_side_unit, unit)
        known_sum = first_side + second_side
        third_side = perimeter_value - known_sum
        if third_side <= 0:
            return None
        if first_side + second_side <= third_side or first_side + third_side <= second_side or second_side + third_side <= first_side:
            return None
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: периметр треугольника {_format_number(perimeter_value)} {unit}, две стороны {_format_number(first_side)} {unit} и {_format_number(second_side)} {unit}.',
            'Что нужно найти: третью сторону треугольника.',
            '1) Сначала складываем две известные стороны.',
            f'2) {_format_number(first_side)} + {_format_number(second_side)} = {_format_number(known_sum)} {unit}.',
            '3) Из периметра вычитаем сумму двух известных сторон.',
            f'4) {_format_number(perimeter_value)} - {_format_number(known_sum)} = {_format_number(third_side)} {unit}.',
            f'Ответ: {_format_number(third_side)} {unit}',
            'Совет: если известны периметр треугольника и две стороны, третью сторону находят вычитанием.',
        ])

    values = [side[0] for side in side_measurements[:3]]
    units = [side[1] for side in side_measurements[:3]]
    unit = min(units, key=lambda current: _LENGTH_UNITS[current])
    converted_values = [_convert_length(value, original_unit, unit) for value, original_unit, _ in side_measurements[:3]]
    perimeter_value = sum(converted_values, Fraction(0))
    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: стороны треугольника равны {_format_number(converted_values[0])} {unit}, {_format_number(converted_values[1])} {unit} и {_format_number(converted_values[2])} {unit}.',
        'Что нужно найти: периметр треугольника.',
        '1) Периметр треугольника находят сложением длин всех сторон.',
        f'2) {_format_number(converted_values[0])} + {_format_number(converted_values[1])} + {_format_number(converted_values[2])} = {_format_number(perimeter_value)} {unit}.',
        f'Ответ: {_format_number(perimeter_value)} {unit}',
        'Совет: чтобы найти периметр треугольника, нужно сложить длины трёх его сторон.',
    ])
