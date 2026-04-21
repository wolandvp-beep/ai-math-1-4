from __future__ import annotations

import re

NON_MATH_REPLY = (
    'Я помогаю только с математикой. Пришлите пример, уравнение или задачу с числами.'
)

MATH_INPUT_HINTS = (
    'сколько', 'сколько всего', 'сколько стало', 'сколько осталось', 'на сколько', 'во сколько',
    'больше', 'меньше', 'поровну', 'по ', 'стоимость', 'цена', 'количество', 'купили',
    'скорость', 'расстояние', 'время', 'площадь', 'периметр', 'доля', 'часть',
    'уравнение', 'пример', 'выражение', 'реши', 'найди', 'найдите',
)


def strip_known_prefix(text: str) -> str:
    cleaned = str(text or '').strip()
    cleaned = re.sub(
        r'^(?:задача|пример|уравнение|дроби|геометрия|выражение|математика)\s*:\s*',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()



def normalize_dashes(text: str) -> str:
    return str(text or '').replace('−', '-').replace('–', '-').replace('—', '-')



def normalize_cyrillic_x(text: str) -> str:
    return str(text or '').replace('Х', 'x').replace('х', 'x')



def normalize_word_problem_text(text: str) -> str:
    cleaned = strip_known_prefix(text)
    cleaned = normalize_dashes(cleaned)
    cleaned = cleaned.replace('ё', 'е').replace('Ё', 'Е')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()



def normalize_sentence(text: str) -> str:
    line = str(text or '').strip()
    if not line:
        return ''
    if re.fullmatch(r'[+\-×:=/() 0-9]+', line):
        return line
    if line[-1] not in '.!?':
        line += '.'
    return line



def join_explanation_lines(*lines: str) -> str:
    parts = [normalize_sentence(line) for line in lines if str(line or '').strip()]
    return '\n'.join(parts)



def infer_task_kind(text: str) -> str:
    from .input_normalization import strip_solver_command_prefix

    base = strip_solver_command_prefix(text) or strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()
    if re.search(r'\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+', lowered):
        return 'fraction'
    if 'x' in lowered and '=' in lowered:
        return 'equation'
    if re.search(r'периметр|площадь|прямоугольник|квадрат|треугольник|сторон|длина|ширина', lowered):
        return 'geometry'
    if re.search(r'[а-я]', lowered):
        return 'word'
    if re.search(r'[+\-*/()×÷:]', lowered):
        return 'expression'
    return 'other'



def looks_like_math_input(text: str) -> bool:
    base = normalize_word_problem_text(text).lower()
    if re.search(r'\d|x|х|[+\-*/=×÷:]', base):
        return True
    if re.search(r'\b[a-z]\b', base) and any(hint in base for hint in MATH_INPUT_HINTS):
        return True
    if any(hint in base for hint in MATH_INPUT_HINTS):
        return True
    return False


__all__ = [
    'NON_MATH_REPLY',
    'MATH_INPUT_HINTS',
    'infer_task_kind',
    'join_explanation_lines',
    'looks_like_math_input',
    'normalize_cyrillic_x',
    'normalize_dashes',
    'normalize_sentence',
    'normalize_word_problem_text',
    'strip_known_prefix',
]
