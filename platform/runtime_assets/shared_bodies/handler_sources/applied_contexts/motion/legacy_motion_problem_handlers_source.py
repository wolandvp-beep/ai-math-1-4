from __future__ import annotations

"""Statically materialized handler source for legacy_motion_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_clock_duration_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if len(_extract_compound_quantities(text)) < 2:
        return None
    if not any(keyword in lower for keyword in ('начал', 'начала', 'началось', 'начался', 'конец', 'законч', 'длил', 'продолж', 'до ')):
        return None
    if not any(keyword in lower for keyword in ('сколько длил', 'сколько продолж', 'сколько времени', 'какое время', 'длился', 'длилась', 'длилось', 'продолжался', 'продолжалась', 'продолжалось')):
        return None

    clock_times = _extract_clock_times(text)
    if len(clock_times) < 2:
        return None
    start = clock_times[0]
    end = clock_times[1]
    duration_minutes = Fraction(end['total_minutes'] - start['total_minutes'], 1)
    if duration_minutes < 0:
        return None
    formatted_duration = _format_clock_duration(duration_minutes)
    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: начало было в {start["pretty"]}, конец был в {end["pretty"]}.',
        _ensure_sentence(f'Что нужно найти: {(_question_text(text) or "сколько длилось событие").rstrip("?.!").lower()}'),
        f'1) Переводим время начала в минуты: {start["hour"]} ч {start["minute"]} мин = {start["total_minutes"]} мин.',
        f'2) Переводим время конца в минуты: {end["hour"]} ч {end["minute"]} мин = {end["total_minutes"]} мин.',
        f'3) Находим длительность: {end["total_minutes"]} - {start["total_minutes"]} = {_format_number(duration_minutes)} мин.',
        f'Ответ: {formatted_duration}',
        'Совет: чтобы узнать, сколько длилось событие, удобно перевести оба момента времени в минуты и найти разность.',
    ])


def _try_relative_motion_distance(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    asks_distance, _, _ = _ask_kind(lower)
    if not asks_distance:
        return None

    is_meeting = 'навстречу' in lower
    is_away = ('в противоположных направлениях' in lower) or ('в разные стороны' in lower)
    if not (is_meeting or is_away):
        return None

    speeds = _extract_speeds(lower)
    if len(speeds) < 2:
        return None
    time_values = _extract_time_values(lower)
    if not time_values:
        return None

    first_speed, speed_unit = speeds[0]
    second_speed, second_speed_unit = speeds[1]
    if speed_unit != second_speed_unit:
        return None
    speed_distance_unit, speed_time_unit = _SPEED_UNIT_PARTS[speed_unit]

    time_value, raw_time_unit, raw_time_text = time_values[-1]
    time_in_speed_unit = _convert_time(time_value, raw_time_unit, speed_time_unit)
    relative_speed = first_speed + second_speed
    distance = relative_speed * time_in_speed_unit
    known, question = _split_known_and_question(text)
    concept = 'скорость сближения' if is_meeting else 'скорость удаления'
    concept_rule = 'навстречу' if is_meeting else 'в противоположных направлениях'

    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: первая скорость {_format_number(first_speed)} {speed_unit}, вторая скорость {_format_number(second_speed)} {speed_unit}, время {raw_time_text}.',
        f'Что нужно найти: {question[:-1].lower() if question else "расстояние"}.',
        f'1) При движении {concept_rule} находим {concept}: {_format_number(first_speed)} + {_format_number(second_speed)} = {_format_number(relative_speed)} {speed_unit}.',
        f'2) Находим расстояние: {_format_number(relative_speed)} × {_format_number(time_in_speed_unit)} = {_format_number(distance)} {speed_distance_unit}.',
        f'Ответ: {_format_number(distance)} {speed_distance_unit}',
        f'Совет: при движении {concept_rule} сначала находят {concept}.',
    ])


def _try_simple_motion(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    if 'навстречу' in lower or 'в противоположных направлениях' in lower or 'в разные стороны' in lower:
        return None

    asks_distance, asks_speed, asks_time = _ask_kind(lower)
    speeds = _extract_speeds(lower)
    time_values = _extract_time_values(lower)
    distance_values = _extract_distance_values(lower)

    if asks_distance and len(speeds) == 1 and time_values:
        speed_value, speed_unit = speeds[0]
        speed_distance_unit, speed_time_unit = _SPEED_UNIT_PARTS[speed_unit]
        time_value, raw_time_unit, raw_time_text = time_values[0]
        time_in_speed_unit = _convert_time(time_value, raw_time_unit, speed_time_unit)
        distance = speed_value * time_in_speed_unit
        _, question = _split_known_and_question(text)
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: скорость {_format_number(speed_value)} {speed_unit}, время {raw_time_text}.',
            f'Что нужно найти: {question[:-1].lower() if question else "расстояние"}.',
            '1) Чтобы найти расстояние, нужно скорость умножить на время.',
            f'2) {_format_number(speed_value)} × {_format_number(time_in_speed_unit)} = {_format_number(distance)} {speed_distance_unit}.',
            f'Ответ: {_format_number(distance)} {speed_distance_unit}',
            'Совет: расстояние находят умножением скорости на время.',
        ])

    if asks_speed and distance_values and time_values:
        distance_value, distance_unit, raw_distance_text = distance_values[0]
        time_value, raw_time_unit, raw_time_text = time_values[0]
        if time_value <= 0:
            return None
        speed_value = distance_value / time_value
        answer_unit = f'{distance_unit}/{raw_time_unit}'
        known, question = _split_known_and_question(text)
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: путь {raw_distance_text}, время {raw_time_text}.',
            f'Что нужно найти: {question[:-1].lower() if question else "скорость"}.',
            '1) Чтобы найти скорость, нужно расстояние разделить на время.',
            f'2) {_format_number(distance_value)} : {_format_number(time_value)} = {_format_number(speed_value)} {answer_unit}.',
            f'Ответ: {_format_number(speed_value)} {answer_unit}',
            'Совет: скорость находят делением расстояния на время.',
        ])

    if asks_time and distance_values and len(speeds) == 1:
        distance_value, distance_unit, raw_distance_text = distance_values[0]
        speed_value, speed_unit = speeds[0]
        speed_distance_unit, speed_time_unit = _SPEED_UNIT_PARTS[speed_unit]
        distance_in_speed_unit = _convert_length(distance_value, distance_unit, speed_distance_unit)
        if speed_value <= 0:
            return None
        time_value = distance_in_speed_unit / speed_value
        time_text, time_unit = _format_time_result(time_value, speed_time_unit)
        known, question = _split_known_and_question(text)
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: путь {raw_distance_text}, скорость {_format_number(speed_value)} {speed_unit}.',
            f'Что нужно найти: {question[:-1].lower() if question else "время"}.',
            '1) Чтобы найти время, нужно расстояние разделить на скорость.',
            f'2) {_format_number(distance_in_speed_unit)} : {_format_number(speed_value)} = {time_text} {time_unit}.',
            f'Ответ: {time_text} {time_unit}',
            'Совет: время находят делением расстояния на скорость.',
        ])

    return None
