from __future__ import annotations

import re
from typing import Optional

from ..text_utils import join_explanation_lines, normalize_word_problem_text


def _normalize(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text)


def _join(*lines: str) -> str:
    return join_explanation_lines(*lines)


def _task_shelf_more(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    match = re.search(
        r'на\s+одной\s+полке\s+([a-z])\s+книг[^.?!]*на\s+другой\s+на\s+([a-z])\s+книг\s+больше',
        lower,
    )
    if not match:
        return None
    first_symbol, delta_symbol = match.groups()
    return _join(
        f'1) Если на одной полке {first_symbol} книг, а на другой на {delta_symbol} книг больше, то на другой полке {first_symbol} + {delta_symbol} книг.',
        f'Ответ: на другой полке {first_symbol} + {delta_symbol} книг.',
        'Совет: если сказано «на несколько больше», к известному числу прибавляют разность.',
    )


def _task_tourist_remaining(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    match = re.search(
        r'турист должен пройти\s+([a-z])\s+км[\s\S]*?в первый день[\s\S]*?прош[её]л\s+([a-z])\s+км[\s\S]*?во второй[\s\S]*?([a-z])\s+км',
        lower,
    )
    if not match:
        return None
    total_symbol, first_symbol, second_symbol = match.groups()
    return _join(
        f'1) Если в первый день турист прошёл {first_symbol} км, а во второй {second_symbol} км, то за два дня он прошёл {first_symbol} + {second_symbol} км.',
        f'2) Если турист должен пройти {total_symbol} км, а уже прошёл {first_symbol} + {second_symbol} км, то ему осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.',
        f'Ответ: туристу осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.',
        'Совет: в буквенной задаче сначала находят уже пройденный путь, потом вычитают его из всего пути.',
    )


def _task_trains_passengers(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    match = re.search(
        r'на вокзал прибыл[ао]?\s+([a-z])\s+поезд[ао]в?\s+по\s+([a-z])\s+пассажир',
        lower,
    )
    if not match:
        return None
    trains_symbol, passengers_symbol = match.groups()
    return _join(
        f'1) Если на вокзал прибыло {trains_symbol} поездов по {passengers_symbol} пассажиров в каждом, то всего прибыло {trains_symbol} × {passengers_symbol} пассажиров.',
        f'Ответ: прибыло {trains_symbol} × {passengers_symbol} пассажиров.',
        'Совет: если одно и то же количество повторяется несколько раз, используют умножение.',
    )


def _task_garland_ratio(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    match = re.search(
        r'гирлянде\s+([a-z])\s+красных лампочек\s+и\s+([a-z])\s+зеленых|гирлянде\s+([a-z])\s+красных лампочек\s+и\s+([a-z])\s+зелёных',
        lower,
    )
    if not match:
        return None
    groups = [g for g in match.groups() if g]
    if len(groups) != 2:
        return None
    red_symbol, green_symbol = groups
    return _join(
        '1) Чтобы узнать, во сколько раз зелёных лампочек больше, чем красных, нужно количество зелёных разделить на количество красных.',
        f'2) Значит, нужно вычислить {green_symbol} : {red_symbol}.',
        f'Ответ: в {green_symbol} : {red_symbol} раза.',
        'Совет: вопрос «во сколько раз» решают делением большего количества на меньшее.',
    )


def _task_factories_total(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    match = re.search(
        r'один завод выпустил\s+([a-z])\s+станков[^.?!]*в\s+([a-z])\s+раз\s+меньше',
        lower,
    )
    if not match:
        return None
    first_symbol, factor_symbol = match.groups()
    return _join(
        f'1) Если один завод выпустил {first_symbol} станков, а второй в {factor_symbol} раз меньше, то второй завод выпустил {first_symbol} : {factor_symbol} станков.',
        f'2) Если первый завод выпустил {first_symbol} станков, а второй {first_symbol} : {factor_symbol} станков, то вместе они выпустили {first_symbol} + {first_symbol} : {factor_symbol} станков.',
        f'Ответ: вместе заводы выпустили {first_symbol} + {first_symbol} : {factor_symbol} станков.',
        'Совет: если число дано через «в несколько раз меньше», сначала делят, а потом находят сумму.',
    )


def build_letter_problem_explanation(raw_text: str) -> Optional[str]:
    return (
        _task_shelf_more(raw_text)
        or _task_tourist_remaining(raw_text)
        or _task_trains_passengers(raw_text)
        or _task_garland_ratio(raw_text)
        or _task_factories_total(raw_text)
    )
