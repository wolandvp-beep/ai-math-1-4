from __future__ import annotations

import re
from typing import Optional

from backend.legacy_text_helpers import audit_task_line, finalize_legacy_lines
from backend.text_utils import normalize_word_problem_text


GROUP_TARGET_MARKERS = (
    'на тарел',
    'в тарел',
    'на конверт',
    'на пакет',
    'в пакет',
    'на короб',
    'в короб',
    'на блюд',
    'на полк',
    'на открыт',
    'на кажд',
    'в кажд',
)

PART_WHOLE_MARKERS = (
    'из них',
    'красн',
    'син',
    'зелен',
    'мальчик',
    'девоч',
    'яблок',
    'груш',
    'шарик',
    'вороб',
    'синиц',
    'орех',
    'корзин',
    'коробк',
    'книг',
    'птиц',
    'конфет',
    'марок',
    'кубик',
    'фрукт',
    'пакет',
    'во втором',
    'во второй',
    'в одном',
)


def _normalize(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text)


def _finalize(lines: list[str]) -> str:
    return finalize_legacy_lines(lines)


def _make_payload(raw_text: str, lines: list[str]) -> str:
    return _finalize(['Задача.', audit_task_line(raw_text), *lines])


def _parse_clock_start(text: str) -> Optional[tuple[int, int]]:
    match = re.search(r'(?:в|во)\s*(\d{1,2})[:.]([0-5]\d)', text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_duration(text: str) -> Optional[tuple[int, int]]:
    lower = text.lower().replace('ё', 'е')
    hours_match = re.search(r'(\d+)\s*(?:ч\.?|час(?:а|ов)?)', lower)
    minutes_match = re.search(r'(\d+)\s*(?:мин\.?|минут(?:ы|)?)', lower)
    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    if hours == 0 and minutes == 0:
        return None
    return hours, minutes


def _format_clock(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    hours, minutes = divmod(total_minutes, 60)
    return f'{hours:02d}:{minutes:02d}'


def _build_clock_arrival_time(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    if not any(phrase in lower for phrase in ('когда', 'во сколько', 'к какому времени')):
        return None
    if not any(phrase in lower for phrase in ('отправ', 'выш', 'начал', 'отплыл', 'выех', 'поезд', 'самолет', 'самолёт', 'автобус', 'урок')):
        return None
    start = _parse_clock_start(text)
    duration = _parse_duration(text)
    if not start or not duration:
        return None
    start_hours, start_minutes = start
    dur_hours, dur_minutes = duration
    start_total = start_hours * 60 + start_minutes
    duration_total = dur_hours * 60 + dur_minutes
    finish_total = start_total + duration_total
    finish_clock = _format_clock(finish_total)
    finish_hours, finish_minutes = divmod(finish_total % (24 * 60), 60)
    duration_pretty_parts = []
    if dur_hours:
        duration_pretty_parts.append(f'{dur_hours} ч')
    if dur_minutes:
        duration_pretty_parts.append(f'{dur_minutes} мин')
    duration_pretty = ' '.join(duration_pretty_parts) or '0 мин'
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: начало было в {start_hours:02d}:{start_minutes:02d}, продолжительность {duration_pretty}.',
        f'Что нужно найти: {("когда закончится событие" if "когда" in lower else "время окончания")}.',
        f'1) Переводим время начала в минуты: {start_hours} ч {start_minutes} мин = {start_total} мин.',
        f'2) Переводим продолжительность в минуты: {dur_hours} ч {dur_minutes} мин = {duration_total} мин.',
        f'3) Находим время окончания в минутах: {start_total} + {duration_total} = {finish_total} мин.',
        f'4) Переводим обратно в часы и минуты: {finish_total % (24 * 60)} мин = {finish_hours} ч {finish_minutes} мин = {finish_clock}.',
        f'Ответ: {finish_clock}.',
        'Совет: чтобы найти время окончания, удобно перевести начало и продолжительность в минуты, выполнить действие, а потом вернуться к часам и минутам.',
    ])


def _build_table_sum_or_difference(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'таблиц' not in lower:
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) != 2:
        return None
    first, second = numbers
    if 'сколько всего' in lower or 'всего' in lower:
        answer = first + second
        return _make_payload(raw_text, [
            'Решение.',
            f'По таблице видим два значения: {first} и {second}.',
            'Что нужно найти: сколько всего.',
            f'1) Складываем данные из таблицы: {first} + {second} = {answer}.',
            f'Ответ: {answer}.',
            'Совет: если по таблице нужно узнать, сколько всего, значения складывают.',
        ])
    if 'на сколько' in lower and any(token in lower for token in ('больше', 'меньше')):
        bigger = max(first, second)
        smaller = min(first, second)
        answer = bigger - smaller
        return _make_payload(raw_text, [
            'Решение.',
            f'По таблице видим два значения: {first} и {second}.',
            'Что нужно найти: на сколько одно значение больше или меньше другого.',
            f'1) Вычитаем меньшее значение из большего: {bigger} - {smaller} = {answer}.',
            f'Ответ: {answer}.',
            'Совет: чтобы узнать, на сколько одно число больше или меньше другого, находят разность.',
        ])
    return None


def _build_total_minus_known_parts(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'таблиц' in lower:
        return None
    if not re.search(r'(?:в|на)\s+перв(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:во|в|на)\s+втор(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:в|на)\s+треть(?:ей|ем)', lower):
        return None
    if not any(token in lower for token in ('в трех', 'в трёх', 'всего', 'вместе')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) < 3:
        return None
    total, first, second = numbers[0], numbers[1], numbers[2]
    answer = total - first - second
    if answer < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: всего {total}, в первой части {first}, во второй части {second}.',
        'Что нужно найти: сколько было в третьей части.',
        f'1) Сначала найдём, сколько уже учтено в первой и второй частях: {first} + {second} = {first + second}.',
        f'2) Теперь найдём третью часть: {total} - {first + second} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если известно общее количество и две части, сначала сложи известные части, а потом вычти их из общего количества.',
    ])


def _build_three_part_relative_chain(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if not re.search(r'(?:на|в)\s+перв(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:на|во|в)\s+втор(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:на|в)\s+треть(?:ей|ем)', lower):
        return None

    first_match = re.search(r'(?:на|в)\s+перв(?:ой|ом)\b[^.?!]*?(\d+)', lower)
    second_match = re.search(r'(?:на|во|в)\s+втор(?:ой|ом)\b[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b[^.?!]*?чем\s+(?:на|в)\s+перв', lower)
    third_match = re.search(r'(?:на|в)\s+треть(?:ей|ем)\b[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b[^.?!]*?чем\s+(?:на|во|в)\s+втор', lower)
    if not first_match or not second_match or not third_match:
        return None
    first_value = int(first_match.group(1))
    second_delta = int(second_match.group(1))
    second_rel = second_match.group(2)
    third_delta = int(third_match.group(1))
    third_rel = third_match.group(2)
    second_value = first_value + second_delta if second_rel == 'больше' else first_value - second_delta
    third_value = second_value + third_delta if third_rel == 'больше' else second_value - third_delta
    if second_value < 0 or third_value < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: в первой части {first_value}. Во второй количество связано с первой, а в третьей — со второй.',
        'Что нужно найти: количество в третьей части.',
        f'1) Находим вторую часть: {first_value} {"+" if second_rel == "больше" else "-"} {second_delta} = {second_value}.',
        f'2) Находим третью часть: {second_value} {"+" if third_rel == "больше" else "-"} {third_delta} = {third_value}.',
        f'Ответ: {third_value}.',
        'Совет: в цепочке из трёх частей сначала найди вторую часть по первой, а потом третью по второй.',
    ])


def _build_part_whole_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower:
        return None
    if 'таблиц' in lower or 'по таблице' in lower or 'на сколько' in lower:
        return None
    if 'поровну' in lower or (re.search(r'по\s+\d+', lower) and any(marker in lower for marker in GROUP_TARGET_MARKERS)):
        return None
    explicit_part_markers = ('из них', 'красн', 'син', 'вороб', 'синиц', 'в одном', 'во втором', 'в первой', 'во второй')
    if ('всего' in lower or 'вместе' in lower) and not any(marker in lower for marker in explicit_part_markers):
        return None
    if any(verb in lower for verb in ('дал', 'отдал', 'съел', 'потрат', 'добав', 'купил', 'принес', 'принёс')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) != 2:
        return None
    if not any(marker in lower for marker in PART_WHOLE_MARKERS):
        return None
    total, known_part = numbers
    answer = total - known_part
    if answer < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: всего {total}, одна часть равна {known_part}.',
        'Что нужно найти: другую часть.',
        f'1) Из общего количества вычитаем известную часть: {total} - {known_part} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если известно целое и одна часть, вторую часть находят вычитанием.',
    ])



def _build_equal_groups_division(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'сколько' not in lower or 'по ' not in lower:
        return None
    if not ('поровну' in lower or any(marker in lower for marker in GROUP_TARGET_MARKERS)):
        return None
    match = re.search(r'(\d+)[^.?!]*?по\s+(\d+)', lower)
    if not match:
        return None
    total = int(match.group(1))
    per_group = int(match.group(2))
    if per_group == 0 or total % per_group != 0:
        return None
    groups = total // per_group
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: всего {total}, в каждой группе по {per_group}.',
        'Что нужно найти: сколько получилось одинаковых групп.',
        f'1) Чтобы найти число групп, делим общее количество на количество в одной группе: {total} : {per_group} = {groups}.',
        f'Ответ: {groups}.',
        'Совет: когда известно, сколько всего и по сколько в каждой группе, число групп находят делением.',
    ])



def _build_compose_number(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')

    match = re.search(
        r'запиши\s+число,?\s+в\s+котором\s+(\d+)\s+тысяч(?:а|и|)?\s+(\d+)\s+сот(?:ня|ни|ен)\s+(\d+)\s+десят(?:ок|ка|ков)\s+(\d+)\s+единиц(?:а|ы|)?',
        lower,
    )
    if match:
        thousands, hundreds, tens, ones = map(int, match.groups())
        value = thousands * 1000 + hundreds * 100 + tens * 10 + ones
        return _make_payload(raw_text, [
            'Решение.',
            f'Собираем число из разрядов: {thousands} тысяч, {hundreds} сотен, {tens} десятков и {ones} единиц.',
            f'1) {thousands} тысяч = {thousands * 1000}.',
            f'2) {hundreds} сотен = {hundreds * 100}.',
            f'3) {tens} десятков = {tens * 10}.',
            f'4) {thousands * 1000} + {hundreds * 100} + {tens * 10} + {ones} = {value}.',
            f'Ответ: {value}.',
            'Совет: чтобы составить число по разрядам, складывают тысячи, сотни, десятки и единицы.',
        ])

    match = re.search(r'запиши\s+число,?\s+в\s+котором\s+(\d+)\s+сот(?:ня|ни|ен)\s+(\d+)\s+десят(?:ок|ка|ков)\s+(\d+)\s+единиц(?:а|ы|)?', lower)
    if match:
        hundreds, tens, ones = map(int, match.groups())
        value = hundreds * 100 + tens * 10 + ones
        return _make_payload(raw_text, [
            'Решение.',
            f'Собираем число из разрядов: {hundreds} сотен, {tens} десятков и {ones} единиц.',
            f'1) {hundreds} сотен = {hundreds * 100}.',
            f'2) {tens} десятков = {tens * 10}.',
            f'3) {hundreds * 100} + {tens * 10} + {ones} = {value}.',
            f'Ответ: {value}.',
            'Совет: чтобы составить число по разрядам, складывают сотни, десятки и единицы.',
        ])

    match = re.search(r'запиши\s+число,?\s+в\s+котором\s+(\d+)\s+десят(?:ок|ка|ков)\s+и\s+(\d+)\s+единиц(?:а|ы|)?', lower)
    if match:
        tens, ones = map(int, match.groups())
        value = tens * 10 + ones
        return _make_payload(raw_text, [
            'Решение.',
            f'Собираем число из разрядов: {tens} десятков и {ones} единиц.',
            f'1) {tens} десятков = {tens * 10}.',
            f'2) {tens * 10} + {ones} = {value}.',
            f'Ответ: {value}.',
            'Совет: двузначное число можно составить из десятков и единиц.',
        ])
    return None



def build_open_source_curriculum_explanation(raw_text: str) -> Optional[str]:
    return (
        _build_table_sum_or_difference(raw_text)
        or _build_equal_groups_division(raw_text)
        or _build_part_whole_problem(raw_text)
        or _build_compose_number(raw_text)
        or _build_clock_arrival_time(raw_text)
        or _build_total_minus_known_parts(raw_text)
        or _build_three_part_relative_chain(raw_text)
    )


__all__ = ['build_open_source_curriculum_explanation']
