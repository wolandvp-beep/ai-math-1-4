from __future__ import annotations

"""Statically materialized handler source for legacy_verbal_arithmetic_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_simple_verbal_arithmetic(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()

    plus_match = re.search(r'к\s*(\d+(?:[.,]\d+)?)\s*(?:прибавили|добавили)\s*(\d+(?:[.,]\d+)?)', lower)
    if plus_match:
        first = _to_fraction(plus_match.group(1))
        second = _to_fraction(plus_match.group(2))
        result = first + second
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: к {_format_number(first)} прибавили {_format_number(second)}.',
            'Что нужно найти: сколько получилось.',
            f'1) Выполняем сложение: {_format_number(first)} + {_format_number(second)} = {_format_number(result)}.',
            f'Ответ: {_format_number(result)}',
            'Совет: при сложении к первому числу прибавляют второе число.',
        ])

    minus_match = re.search(r'от\s*(\d+(?:[.,]\d+)?)\s*(?:отняли|вычли)\s*(\d+(?:[.,]\d+)?)', lower)
    if minus_match:
        first = _to_fraction(minus_match.group(1))
        second = _to_fraction(minus_match.group(2))
        result = first - second
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: от {_format_number(first)} отняли {_format_number(second)}.',
            'Что нужно найти: сколько получилось.',
            f'1) Выполняем вычитание: {_format_number(first)} - {_format_number(second)} = {_format_number(result)}.',
            f'Ответ: {_format_number(result)}',
            'Совет: при вычитании из первого числа убирают второе число.',
        ])

    multiply_match = re.search(r'(\d+(?:[.,]\d+)?)\s*умножили\s+на\s*(\d+(?:[.,]\d+)?)', lower)
    if multiply_match:
        first = _to_fraction(multiply_match.group(1))
        second = _to_fraction(multiply_match.group(2))
        result = first * second
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: {_format_number(first)} умножили на {_format_number(second)}.',
            'Что нужно найти: сколько получилось.',
            f'1) Выполняем умножение: {_format_number(first)} × {_format_number(second)} = {_format_number(result)}.',
            f'Ответ: {_format_number(result)}',
            'Совет: умножение показывает, сколько получится одинаковых групп.',
        ])

    divide_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:разделили|поделили)\s+на\s*(\d+(?:[.,]\d+)?)', lower)
    if divide_match:
        first = _to_fraction(divide_match.group(1))
        second = _to_fraction(divide_match.group(2))
        if second == 0:
            return None
        result = first / second
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: {_format_number(first)} разделили на {_format_number(second)}.',
            'Что нужно найти: сколько получилось.',
            f'1) Выполняем деление: {_format_number(first)} : {_format_number(second)} = {_format_number(result)}.',
            f'Ответ: {_format_number(result)}',
            'Совет: деление показывает, на сколько равных частей разбили число или сколько раз одно число содержится в другом.',
        ])

    return None
