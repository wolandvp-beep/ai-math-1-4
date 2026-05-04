from __future__ import annotations

"""Statically materialized runtime module for final_textbook_runtime_module.py.

This preserves shard execution order while making this runtime layer a
normal importable Python module.
"""

# --- merged segment 001: backend.legacy_runtime_module_shards.final_textbook_runtime_module.segment_001 ---
def _final_20260416_prepare(raw_text: str):
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    return text, lower, nums


def _final_20260416_result_dict(text: str, source: str = 'local-final-20260416') -> dict:
    return {'result': text, 'source': source, 'validated': True}


def _final_20260416_fraction_word_to_pair(word: str):
    word = (word or '').lower()
    mapping = {
        'половина': (1, 2),
        'треть': (1, 3),
        'четверть': (1, 4),
        'четвёртая часть': (1, 4),
    }
    return mapping.get(word)


def _final_20260416_normalize_fraction_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(normalize_cyrillic_x(text))
    text = text.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    text = re.sub(r'\s+', '', text)
    if not text or re.search(r'[A-Za-zА-Яа-яЁё]', text):
        return None
    if re.search(r'[^0-9+\-*/()]', text):
        return None
    if not re.search(r'\d+/\d+', text):
        return None
    if re.fullmatch(r'\d+/\d+', text):
        return None

    all_numbers = [int(value) for value in re.findall(r'\d+', text)]
    if not all_numbers:
        return None
    if max(abs(value) for value in all_numbers) > 1000:
        return None

    fraction_matches = list(re.finditer(r'(\d+)/(\d+)', text))
    if not fraction_matches:
        return None

    placeholder = re.sub(r'\d+/\d+', 'F', text)
    if not re.fullmatch(r'[F0-9+\-*/()]+', placeholder):
        return None
    if placeholder == 'F':
        return None

    pairs = [(int(match.group(1)), int(match.group(2))) for match in fraction_matches]
    if any(den == 0 for _, den in pairs):
        return None

    # Одно обычное деление вроде 24/4 в длинном выражении не должно уходить в блок дробей.
    # Для дробных выражений начальной школы оставляем:
    # - хотя бы две дроби;
    # - или одну правильную дробь вроде 1/2 + 3.
    if len(pairs) == 1:
        numerator, denominator = pairs[0]
        if not (0 < numerator < denominator <= 20):
            return None
        start, end = fraction_matches[0].span()
        if '+' not in placeholder and '-' not in placeholder and '*' not in placeholder:
            return None
        if start > 0 and text[start - 1].isdigit():
            return None
        if end < len(text) and text[end:end + 1].isdigit():
            return None
    else:
        if not all(0 < num <= 50 and 0 < den <= 50 for num, den in pairs):
            return None
        if not any(num < den for num, den in pairs):
            return None

    return text


# Переопределяем нормализатор, чтобы обычные выражения с делением не шли в блок дробей.
_final_20260415_normalize_fraction_expression_source = _final_20260416_normalize_fraction_expression_source


def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    unit = geometry_unit(lower)

    square_side_match = re.search(
        r'(?:квадрат[^.?!]{0,60}?со\s+сторон(?:ой|ою|ой\s+)?[^\d]{0,20}(\d+))|(?:сторона\s+квадрата[^\d]{0,20}(\d+))',
        lower,
    )
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None

    question_parts = [part.strip() for part in re.split(r'[?.!]', lower) if part.strip()]
    question = question_parts[-1] if question_parts else lower
    asks_perimeter = 'периметр' in question or 'найди его периметр' in lower or 'найдите его периметр' in lower
    asks_width = 'найдите ширину' in lower or 'найди ширину' in lower or 'какова ширина' in lower
    asks_length = ('найдите длину' in lower or 'найди длину' in lower or 'какова длина' in lower) and not asks_width

    if 'квадрат' in lower and square_side_val is not None and asks_perimeter:
        result = square_side_val * 4
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: сторона квадрата равна {square_side_val} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата все четыре стороны равны.',
            f'2) Периметр квадрата — это сумма четырёх равных сторон: {square_side_val} × 4 = {result}.',
            f'Ответ: {with_unit(result, unit)}.'
        )

    # Формулировки вида «прямоугольной формы» тоже считаем задачами про прямоугольник.
    if 'прямоугольн' in lower and 'площад' in lower and ('длина' in lower or 'ширина' in lower):
        area_val = extract_keyword_number(lower, 'площад')
        length_val = extract_keyword_number(lower, 'длина')
        width_val = extract_keyword_number(lower, 'ширина')
        if asks_width and area_val is not None and length_val is not None and length_val != 0 and area_val % length_val == 0:
            width = area_val // length_val
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, длина {with_unit(length_val, unit)}.',
                'Что нужно найти: ширину прямоугольника.',
                '1) Площадь прямоугольника равна длине, умноженной на ширину.',
                f'2) Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}.',
                f'Ответ: {with_unit(width, unit)}.'
            )
        if asks_length and area_val is not None and width_val is not None and width_val != 0 and area_val % width_val == 0:
            length = area_val // width_val
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, ширина {with_unit(width_val, unit)}.',
                'Что нужно найти: длину прямоугольника.',
                '1) Площадь прямоугольника равна длине, умноженной на ширину.',
                f'2) Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}.',
                f'Ответ: {with_unit(length, unit)}.'
            )

    return _FINAL_20260416_PREV_GEOMETRY(raw_text)


def _final_20260416_try_pickles_two_days(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 3:
        return None
    if 'в первый день' not in lower or 'во второй день' not in lower:
        return None
    if 'по' not in lower or 'в каждом' not in lower:
        return None
    if 'на' not in lower or 'больше, чем в первый день' not in lower:
        return None
    if not contains_any_fragment(lower, ('сколько кг', 'сколько килограмм', 'сколько огурцов засолили за два дня', 'сколько засолили за два дня')):
        return None
    if not contains_any_fragment(lower, ('огурц', 'бочон', 'ящик', 'банк')):
        return None

    groups, per_group, diff = nums[:3]
    first_day = groups * per_group
    second_day = first_day + diff
    total = first_day + second_day
    if min(groups, per_group, diff, first_day, second_day, total) < 0:
        return None

    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в первый день засолили {groups} бочонков по {per_group} кг в каждом. Во второй день засолили на {diff} кг больше, чем в первый день.',
        'Что нужно найти: сколько килограммов огурцов засолили за два дня.',
        f'1) Сначала найдём, сколько килограммов засолили в первый день: {groups} × {per_group} = {first_day} кг.',
        f'2) Потом найдём, сколько килограммов засолили во второй день: {first_day} + {diff} = {second_day} кг.',
        f'3) Теперь найдём, сколько килограммов засолили за два дня: {first_day} + {second_day} = {total} кг.',
        f'Ответ: за два дня засолили {total} кг огурцов.'
    )


def _final_20260416_try_motion_compare_two_distances(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if 'на сколько больше' not in lower and 'на сколько меньше' not in lower:
        return None
    if not ('автобус' in lower and 'пеш' in lower):
        return None
    times = [int(v) for v in re.findall(r'(\d+)\s*(?:ч|час)', lower)]
    speeds = [int(v) for v in re.findall(r'(\d+)\s*км/ч', lower)]
    if len(times) < 2 or len(speeds) < 2:
        return None
    bus_time, walk_time = times[0], times[1]
    bus_speed, walk_speed = speeds[0], speeds[1]
    bus_distance = bus_speed * bus_time
    walk_distance = walk_speed * walk_time
    difference = bus_distance - walk_distance
    if difference < 0:
        return None
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: на автобусе ехали {bus_time} ч со скоростью {bus_speed} км/ч, пешком шли {walk_time} ч со скоростью {walk_speed} км/ч.',
        'Что нужно найти: на сколько больше путь на автобусе, чем пешком.',
        f'1) Сначала найдём путь на автобусе: {bus_speed} × {bus_time} = {bus_distance} км.',
        f'2) Потом найдём путь пешком: {walk_speed} × {walk_time} = {walk_distance} км.',
        f'3) Теперь сравним пути: {bus_distance} - {walk_distance} = {difference} км.',
        f'Ответ: путь на автобусе больше на {difference} км.'
    )


def _final_20260416_try_same_price_two_days(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 3:
        return None
    if 'в первый день' not in lower or 'во второй' not in lower:
        return None
    if 'по той же цене' not in lower and 'по одинаковой цене' not in lower:
        return None
    if 'за все' not in lower and 'за все полки' not in lower:
        return None
    if not contains_any_fragment(lower, ('сколько денег истратили', 'сколько денег потратили', 'сколько заплатили в первый день')):
        return None

    first_qty, second_qty, total_cost = nums[:3]
    total_qty = first_qty + second_qty
    if total_qty <= 0 or total_cost % total_qty != 0:
        return None
    price = total_cost // total_qty
    first_cost = first_qty * price
    second_cost = second_qty * price

    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в первый день купили {first_qty} полок, во второй — {second_qty} таких же полок по той же цене. За все полки заплатили {total_cost} р.',
        'Что нужно найти: сколько денег истратили в первый день и сколько — во второй день.',
        f'1) Сначала найдём, сколько полок купили всего: {first_qty} + {second_qty} = {total_qty}.',
        f'2) Теперь найдём цену одной полки: {total_cost} : {total_qty} = {price} р.',
        f'3) Узнаем, сколько заплатили в первый день: {first_qty} × {price} = {first_cost} р.',
        f'4) Узнаем, сколько заплатили во второй день: {second_qty} × {price} = {second_cost} р.',
        f'Ответ: в первый день — {first_cost} р, во второй день — {second_cost} р.'
    )


def _final_20260416_try_red_green_apples_half_taken(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None
    if 'красн' not in lower or 'зелен' not in lower or 'яблок' not in lower:
        return None
    if 'половину всех яблок' not in lower or 'осталось' not in lower:
        return None
    if 'сначала' not in lower:
        return None

    green_added, remained_after_taking = nums[:2]
    total_before_taking = remained_after_taking * 2
    red_initial = total_before_taking - green_added
    if min(green_added, remained_after_taking, total_before_taking, red_initial) < 0:
        return None

    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в корзину положили ещё {green_added} зелёных яблок. После того как взяли половину всех яблок, осталось {remained_after_taking} яблок.',
        'Что нужно найти: сколько красных яблок было в корзине сначала.',
        f'1) Если после того как взяли половину, осталось {remained_after_taking} яблок, значит это вторая половина всех яблок.',
        f'2) Тогда до того как взяли половину, в корзине было {remained_after_taking} × 2 = {total_before_taking} яблок.',
        f'3) Из этих яблок {green_added} были зелёные, значит красных было {total_before_taking} - {green_added} = {red_initial}.',
        f'Ответ: сначала в корзине было {red_initial} красных яблок.'
    )


def _final_20260416_try_fraction_whole_comparison(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None
    fraction_hits = list(re.finditer(r'(половина|треть|четверть)[^0-9]{0,60}?это\s*(\d+)', lower))
    if len(fraction_hits) != 2:
        return None

    parts = []
    for match in fraction_hits:
        frac_word = match.group(1)
        value = int(match.group(2))
        pair = _final_20260416_fraction_word_to_pair(frac_word)
        if not pair:
            return None
        num, den = pair
        whole = value * den // num
        if value * den % num != 0:
            return None
        parts.append({'word': frac_word, 'value': value, 'num': num, 'den': den, 'whole': whole})

    first_whole = parts[0]['whole']
    second_whole = parts[1]['whole']

    if 'во сколько раз' in lower and ('больше' in lower or 'меньше' in lower):
        bigger = max(first_whole, second_whole)
        smaller = min(first_whole, second_whole)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        unit = 'кг' if 'кг' in lower else ''
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {parts[0]["word"]} первого количества — это {parts[0]["value"]} {unit}. {parts[1]["word"]} второго количества — это {parts[1]["value"]} {unit}.',
            'Что нужно найти: во сколько раз одно количество больше другого.',
            f'1) Найдём всё первое количество: {parts[0]["value"]} × {parts[0]["den"]} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {parts[1]["value"]} × {parts[1]["den"]} = {second_whole} {unit}.',
            f'3) Сравним количества: {bigger} : {smaller} = {ratio}.',
            f'Ответ: в {ratio} раза.'
        )

    if 'на сколько' in lower and ('больше' in lower or 'меньше' in lower):
        difference = abs(second_whole - first_whole)
        unit = ''
        if 'см2' in lower or 'см²' in lower:
            unit = 'см²'
        elif 'кг' in lower:
            unit = 'кг'
        elif 'м2' in lower or 'м²' in lower:
            unit = 'м²'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {parts[0]["word"]} первого количества — это {parts[0]["value"]} {unit}. {parts[1]["word"]} второго количества — это {parts[1]["value"]} {unit}.',
            'Что нужно найти: на сколько одно количество отличается от другого.',
            f'1) Найдём всё первое количество: {parts[0]["value"]} × {parts[0]["den"]} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {parts[1]["value"]} × {parts[1]["den"]} = {second_whole} {unit}.',
            f'3) Найдём разность: {max(first_whole, second_whole)} - {min(first_whole, second_whole)} = {difference} {unit}.',
            f'Ответ: на {difference} {unit}.'.replace('  ', ' ')
        )

    return None


def _final_20260416_try_ratio_difference_full_answer(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) != 2:
        return None
    if 'в 3 раза больше' not in lower and not re.search(r'в\s+\d+\s+раз(?:а)?\s+больше', lower):
        return None
    if 'на сколько' not in lower:
        return None
    if 'рек' not in lower or 'город' not in lower:
        return None
    first, factor = nums
    second = first * factor
    diff = second - first
    if diff < 0:
        return None
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: названий рек {first}, названий городов в {factor} раза больше.',
        'Что нужно найти: на сколько названий рек меньше, чем названий городов.',
        f'1) Сначала найдём, сколько названий городов: {first} × {factor} = {second}.',
        f'2) Теперь найдём, на сколько названий рек меньше: {second} - {first} = {diff}.',
        f'Ответ: названий рек на {diff} меньше, чем названий городов.'
    )






# --- FINAL PATCH 2026-04-16B: direct geometry/textbook handlers and cleaner fraction-word parsing ---







def _final_20260416b_try_red_green_apples_half_taken(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None
    if 'красн' not in lower or 'зелен' not in lower or 'яблок' not in lower:
        return None
    if 'половину всех яблок' not in lower or 'осталось' not in lower or 'сначала' not in lower:
        return None
    green_added, remained_after_taking = nums[:2]
    total_before_taking = remained_after_taking * 2
    red_initial = total_before_taking - green_added
    if min(green_added, remained_after_taking, total_before_taking, red_initial) < 0:
        return None
    apple_word = _final_20260415ae_plural(red_initial, 'красное яблоко', 'красных яблока', 'красных яблок')
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: в корзину положили ещё {green_added} зелёных яблок. После того как взяли половину всех яблок, осталось {remained_after_taking} яблок.',
        'Что нужно найти: сколько красных яблок было в корзине сначала.',
        f'1) Если после того как взяли половину, осталось {remained_after_taking} яблок, значит это половина всех яблок.',
        f'2) Тогда до того как взяли половину, в корзине было {remained_after_taking} × 2 = {total_before_taking} яблок.',
        f'3) Из этих яблок {green_added} были зелёные, значит красных было {total_before_taking} - {green_added} = {red_initial}.',
        f'Ответ: сначала в корзине было {red_initial} {apple_word}.'
    )


def _final_20260416_try_all_remaining_fixes(raw_text: str) -> Optional[str]:
    return (
        _final_20260416b_try_geometry_direct(raw_text)
        or _final_20260416_try_pickles_two_days(raw_text)
        or _final_20260416_try_motion_compare_two_distances(raw_text)
        or _final_20260416_try_same_price_two_days(raw_text)
        or _final_20260416b_try_red_green_apples_half_taken(raw_text)
        or _final_20260416b_try_fraction_whole_comparison(raw_text)
        or _final_20260416_try_ratio_difference_full_answer(raw_text)
    )




# --- FINAL PATCH 2026-04-16C: robust numeric extraction for geometry wording ---



def _final_20260416c_find_geometry_number(lower: str, keyword: str) -> Optional[int]:
    patterns = {
        'площадь': [
            r'площад[а-яё ]{0,20}(?:равна|=|составляет|имеет)?[^\d]{0,12}(\d+)\s*(?:мм2|см2|дм2|м2|км2|мм²|см²|дм²|м²|км²)?',
            r'(\d+)\s*(?:мм2|см2|дм2|м2|км2|мм²|см²|дм²|м²|км²)[^.?!]{0,30}площад',
        ],
        'длина': [
            r'длин[а-яё ]{0,20}(?:равна|=|имеет)?[^\d]{0,12}(\d+)\s*(?:мм|см|дм|м|км)\b',
            r'(\d+)\s*(?:мм|см|дм|м|км)\b[^.?!]{0,30}длин',
        ],
        'ширина': [
            r'ширин[а-яё ]{0,20}(?:равна|=|имеет)?[^\d]{0,12}(\d+)\s*(?:мм|см|дм|м|км)\b',
            r'(\d+)\s*(?:мм|см|дм|м|км)\b[^.?!]{0,30}ширин',
        ],
    }
    key = 'площадь' if keyword.startswith('площад') else 'длина' if keyword.startswith('длина') else 'ширина'
    for pattern in patterns[key]:
        match = re.search(pattern, lower)
        if match:
            return int(match.group(1))
    return None






# --- FINAL PATCH 2026-04-16D: fuller textbook-style answers in new direct handlers ---



def _final_20260416b_try_geometry_direct(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    unit = geometry_unit(lower)

    square_side_match = re.search(
        r'(?:квадрат[^.?!]{0,80}?со\s+сторон(?:ой|ою)?[^\d]{0,20}(\d+))|(?:сторона\s+квадрата[^\d]{0,20}(\d+))',
        lower,
    )
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None

    if 'квадрат' in lower and 'периметр' in lower and square_side_val is not None:
        result = square_side_val * 4
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: сторона квадрата равна {square_side_val} {unit}.',
            'Что нужно найти: периметр квадрата.',
            '1) У квадрата все четыре стороны равны.',
            f'2) Периметр квадрата — это сумма четырёх равных сторон: {square_side_val} × 4 = {result}.',
            f'Ответ: периметр квадрата равен {with_unit(result, unit)}.'
        )

    area_val = _final_20260416c_find_geometry_number(lower, 'площадь')
    length_val = _final_20260416c_find_geometry_number(lower, 'длина')
    width_val = _final_20260416c_find_geometry_number(lower, 'ширина')
    asks_width = 'найдите ширину' in lower or 'найди ширину' in lower or 'какова ширина' in lower
    asks_length = ('найдите длину' in lower or 'найди длину' in lower or 'какова длина' in lower) and not asks_width

    if 'прямоугольн' in lower and area_val is not None and length_val is not None and asks_width and length_val != 0 and area_val % length_val == 0:
        width = area_val // length_val
        object_name = 'прямоугольника'
        if 'пруд' in lower:
            object_name = 'пруда'
        elif 'площадк' in lower:
            object_name = 'площадки'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, длина {with_unit(length_val, unit)}.',
            f'Что нужно найти: ширину {object_name}.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}.',
            f'Ответ: ширина {object_name} равна {with_unit(width, unit)}.'
        )

    if 'прямоугольн' in lower and area_val is not None and width_val is not None and asks_length and width_val != 0 and area_val % width_val == 0:
        length = area_val // width_val
        object_name = 'прямоугольника'
        if 'площадк' in lower:
            object_name = 'площадки'
        elif 'пруд' in lower:
            object_name = 'пруда'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь прямоугольника {with_unit(area_val, unit, square=True)}, ширина {with_unit(width_val, unit)}.',
            f'Что нужно найти: длину {object_name}.',
            '1) Площадь прямоугольника равна длине, умноженной на ширину.',
            f'2) Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}.',
            f'Ответ: длина {object_name} равна {with_unit(length, unit)}.'
        )

    return None


def _final_20260416b_try_fraction_whole_comparison(raw_text: str) -> Optional[str]:
    text, lower, nums = _final_20260416_prepare(raw_text)
    if len(nums) < 2:
        return None

    fraction_hits = []
    for match in re.finditer(r'(половина|треть|четверть)([^0-9]{0,80}?)(?:это\s*)?(\d+)', lower):
        frac_word = match.group(1)
        object_fragment = (match.group(2) or '').strip(' ,-–—')
        value = int(match.group(3))
        pair = _final_20260416_fraction_word_to_pair(frac_word)
        if not pair:
            continue
        fraction_hits.append((frac_word, object_fragment, value, pair[0], pair[1]))
    if len(fraction_hits) < 2:
        return None
    fraction_hits = fraction_hits[:2]

    first_word, first_object, first_value, first_num, first_den = fraction_hits[0]
    second_word, second_object, second_value, second_num, second_den = fraction_hits[1]
    if first_value * first_den % first_num != 0 or second_value * second_den % second_num != 0:
        return None
    first_whole = first_value * first_den // first_num
    second_whole = second_value * second_den // second_num

    unit = ''
    if 'см2' in lower or 'см²' in lower:
        unit = 'см²'
    elif 'м2' in lower or 'м²' in lower:
        unit = 'м²'
    elif 'кг' in lower:
        unit = 'кг'

    first_label = first_object or 'первого количества'
    second_label = second_object or 'второго количества'
    first_label = re.sub(r'\s+', ' ', first_label).strip()
    second_label = re.sub(r'\s+', ' ', second_label).strip()

    if 'во сколько раз' in lower and ('больше' in lower or 'меньше' in lower):
        bigger = max(first_whole, second_whole)
        smaller = min(first_whole, second_whole)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        answer = f'Ответ: первое количество больше второго в {ratio} раза.'
        if 'картошк' in lower and 'морков' in lower:
            answer = f'Ответ: масса картошки больше массы моркови в {ratio} раза.'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {first_word} {first_label} — это {first_value} {unit}. {second_word} {second_label} — это {second_value} {unit}.',
            'Что нужно найти: во сколько раз одно количество больше другого.',
            f'1) Найдём всё первое количество: {first_value} × {first_den} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {second_value} × {second_den} = {second_whole} {unit}.',
            f'3) Сравним количества: {bigger} : {smaller} = {ratio}.',
            answer
        )

    if 'на сколько' in lower and ('больше' in lower or 'меньше' in lower):
        difference = abs(second_whole - first_whole)
        big = max(first_whole, second_whole)
        small = min(first_whole, second_whole)
        answer = f'Ответ: одно количество отличается от другого на {difference} {unit}.'.replace('  ', ' ')
        if 'салфет' in lower and 'скатерт' in lower:
            answer = f'Ответ: площадь салфетки меньше площади скатерти на {difference} {unit}.'
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {first_word} {first_label} — это {first_value} {unit}. {second_word} {second_label} — это {second_value} {unit}.',
            'Что нужно найти: на сколько одно количество отличается от другого.',
            f'1) Найдём всё первое количество: {first_value} × {first_den} = {first_whole} {unit}.',
            f'2) Найдём всё второе количество: {second_value} × {second_den} = {second_whole} {unit}.',
            f'3) Найдём разность: {big} - {small} = {difference} {unit}.',
            answer
        )

    return None



# --- FINAL PATCH 2026-04-16E: new-source audit fixes without touching stable UI logic ---


_FINAL_20260416E_LINEAR_UNITS = {
    'мм': 1,
    'см': 10,
    'дм': 100,
    'м': 1000,
    'км': 1000000,
}


def _final_20260416e_norm_math_text(raw_text: str) -> str:
    return strip_known_prefix(str(raw_text or '')).strip()


def _final_20260416e_pretty_ops(text: str) -> str:
    return (
        str(text or '')
        .replace('**', '^')
        .replace('*', ' × ')
        .replace('/', ' : ')
        .replace('+', ' + ')
        .replace('-', ' - ')
    )


def _final_20260416e_eval_integer_expression(expr: str) -> Optional[int]:
    source = to_expression_source(expr) or str(expr or '').strip()
    node = parse_expression_ast(source)
    if node is None:
        return None
    try:
        value = eval_fraction_node(node)
    except Exception:
        return None
    if isinstance(value, Fraction):
        if value.denominator != 1:
            return None
        return int(value.numerator)
    try:
        value = Fraction(value)
    except Exception:
        return None
    if value.denominator != 1:
        return None
    return int(value.numerator)


def _final_20260416e_try_force_detailed_expression(raw_text: str) -> Optional[str]:
    text = _final_20260416e_norm_math_text(raw_text)
    if not text or '=' in text or re.search(r'[A-Za-zА-Яа-я]', text):
        return None
    source = to_expression_source(text)
    if not source:
        return None
    if _final_20260416_normalize_fraction_expression_source(text):
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return None
    rendered = _patch_20260412c_render_mixed_expression_solution(source)
    return rendered if rendered else None


def _final_20260416e_try_motion_per_hour_speed(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if not contains_any_fragment(lower, ('с какой скоростью', 'какова скорость')):
        return None
    match = re.search(r'кажд(?:ый|ую|ое)\s+час[^\d]{0,20}(\d+)\s*км', lower)
    if not match:
        match = re.search(r'(\d+)\s*км[^.?!]{0,30}кажд(?:ый|ую|ое)\s+час', lower)
    if not match:
        return None
    speed = int(match.group(1))
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: за 1 час проходят {speed} км.',
        'Что нужно найти: скорость.',
        '1) Скорость показывает, какое расстояние проходят за один час.',
        f'2) За один час проходят {speed} км, значит скорость равна {speed} км/ч.',
        f'Ответ: скорость равна {speed} км/ч.'
    )


def _final_20260416e_try_equation_with_side_expression(raw_text: str) -> Optional[str]:
    text = _final_20260416e_norm_math_text(raw_text)
    compact = text.replace('×', '*').replace('÷', '/').replace(':', '/').replace('−', '-').replace('–', '-').replace('—', '-')
    if compact.count('=') != 1:
        return None
    if ',' in compact or ';' in compact or '\n' in compact:
        return None
    letters = re.findall(r'[A-Za-zА-Яа-я]', compact)
    if not letters:
        return None
    unique_letters = {ch.lower() for ch in letters}
    if len(unique_letters) != 1:
        return None
    variable = letters[0]
    left_raw, right_raw = [part.strip() for part in compact.split('=', 1)]
    left_has_var = bool(re.search(r'[A-Za-zА-Яа-я]', left_raw))
    right_has_var = bool(re.search(r'[A-Za-zА-Яа-я]', right_raw))
    if left_has_var == right_has_var:
        return None
    variable_side = left_raw if left_has_var else right_raw
    numeric_side = right_raw if left_has_var else left_raw
    if not re.search(r'[+\-*/]', numeric_side):
        return None
    numeric_value = _final_20260416e_eval_integer_expression(numeric_side)
    if numeric_value is None:
        return None

    compact_var = variable_side.replace(' ', '')
    pretty_numeric = _final_20260416e_pretty_ops(numeric_side).replace('  ', ' ').strip()
    pretty_variable_side = _final_20260416e_pretty_ops(variable_side).replace('  ', ' ').strip()

    def build_lines(new_equation: str, solve_line: str, final_value: int, component_text: str, operation_text: str) -> str:
        original_pretty = _final_20260416e_pretty_ops(compact.replace('=', ' = ')).replace('  ', ' ').strip()
        return join_explanation_lines(
            'Уравнение:',
            original_pretty,
            'Решение.',
            '1) Сначала вычисляем значение выражения в той части уравнения, где нет неизвестного:',
            f'{pretty_numeric} = {numeric_value}',
            '2) Получаем более простое уравнение:',
            new_equation,
            component_text,
            operation_text,
            f'3) Считаем: {solve_line}',
            f'Ответ: {final_value}'
        )

    m = re.fullmatch(rf'{re.escape(variable)}\+(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value - number
        return build_lines(
            f'{variable} + {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное слагаемое.',
            f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {variable} = {numeric_value} - {number}.'
        )
    m = re.fullmatch(rf'(\d+)\+{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value - number
        return build_lines(
            f'{number} + {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное слагаемое.',
            f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {variable} = {numeric_value} - {number}.'
        )
    m = re.fullmatch(rf'{re.escape(variable)}-(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value + number
        return build_lines(
            f'{variable} - {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное уменьшаемое.',
            f'Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: {variable} = {numeric_value} + {number}.'
        )
    m = re.fullmatch(rf'(\d+)-{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        answer = number - numeric_value
        return build_lines(
            f'{number} - {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное вычитаемое.',
            f'Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: {variable} = {number} - {numeric_value}.'
        )
    m = re.fullmatch(rf'{re.escape(variable)}\*(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        if number == 0 or numeric_value % number != 0:
            return None
        answer = numeric_value // number
        return build_lines(
            f'{variable} × {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестный множитель.',
            f'Чтобы найти неизвестный множитель, произведение делим на известный множитель: {variable} = {numeric_value} : {number}.'
        )
    m = re.fullmatch(rf'(\d+)\*{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        if number == 0 or numeric_value % number != 0:
            return None
        answer = numeric_value // number
        return build_lines(
            f'{number} × {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестный множитель.',
            f'Чтобы найти неизвестный множитель, произведение делим на известный множитель: {variable} = {numeric_value} : {number}.'
        )
    m = re.fullmatch(rf'{re.escape(variable)}/(\d+)', compact_var)
    if m:
        number = int(m.group(1))
        answer = numeric_value * number
        return build_lines(
            f'{variable} : {number} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестное делимое.',
            f'Чтобы найти неизвестное делимое, делитель умножаем на частное: {variable} = {numeric_value} × {number}.'
        )
    m = re.fullmatch(rf'(\d+)/{re.escape(variable)}', compact_var)
    if m:
        number = int(m.group(1))
        if numeric_value == 0 or number % numeric_value != 0:
            return None
        answer = number // numeric_value
        return build_lines(
            f'{number} : {variable} = {numeric_value}',
            f'{variable} = {answer}',
            answer,
            f'{variable} — неизвестный делитель.',
            f'Чтобы найти неизвестный делитель, делимое делим на частное: {variable} = {number} : {numeric_value}.'
        )
    return None


def _final_20260416e_extract_target_area_unit(lower: str) -> Optional[str]:
    if 'мм2' in lower or 'мм²' in lower:
        return 'мм'
    if 'см2' in lower or 'см²' in lower:
        return 'см'
    if 'дм2' in lower or 'дм²' in lower:
        return 'дм'
    if 'м2' in lower or 'м²' in lower:
        return 'м'
    if 'км2' in lower or 'км²' in lower:
        return 'км'
    return None


def _final_20260416e_convert_area_value(value: int, from_unit: str, to_unit: str) -> Optional[int]:
    if from_unit not in _FINAL_20260416E_LINEAR_UNITS or to_unit not in _FINAL_20260416E_LINEAR_UNITS:
        return None
    base_from = _FINAL_20260416E_LINEAR_UNITS[from_unit]
    base_to = _FINAL_20260416E_LINEAR_UNITS[to_unit]
    total_in_mm2 = value * (base_from ** 2)
    if total_in_mm2 % (base_to ** 2) != 0:
        return None
    return total_in_mm2 // (base_to ** 2)

# --- merged segment 002: backend.legacy_runtime_module_shards.final_textbook_runtime_module.segment_002 ---
def _final_20260416e_try_geometry_textbook_patterns(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    # 1) Прямоугольник: известны длина и ширина напрямую.
    rect_direct = re.search(
        r'длин[а-яё ]{0,20}(?:которого|прямоугольника)?[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширин[а-яё ]{0,20}[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)',
        lower,
    )
    if rect_direct:
        length = int(rect_direct.group(1))
        length_unit = rect_direct.group(2)
        width = int(rect_direct.group(3))
        width_unit = rect_direct.group(4)
        if length_unit == width_unit:
            unit = length_unit
            area = length * width
            perimeter = (length + width) * 2
            asks_area = 'площад' in lower
            asks_perimeter = 'периметр' in lower
            target_area_unit = _final_20260416e_extract_target_area_unit(lower)
            if asks_area and target_area_unit and target_area_unit != unit:
                converted = _final_20260416e_convert_area_value(area, unit, target_area_unit)
                if converted is not None:
                    return join_explanation_lines(
                        'Задача.',
                        _audit_task_line(raw_text),
                        'Решение.',
                        f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                        'Что нужно найти: площадь прямоугольника и перевести её в другую единицу площади.',
                        f'1) Находим площадь прямоугольника: {length} × {width} = {area} {unit}².',
                        f'2) Переводим {area} {unit}² в {target_area_unit}²: {area} {unit}² = {converted} {target_area_unit}².',
                        f'Ответ: площадь прямоугольника равна {with_unit(converted, target_area_unit, square=True)}.'
                    )
            if asks_area and not asks_perimeter:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                    'Что нужно найти: площадь прямоугольника.',
                    f'1) Площадь прямоугольника равна длине, умноженной на ширину: {length} × {width} = {area}.',
                    f'Ответ: площадь прямоугольника равна {with_unit(area, unit, square=True)}.'
                )
            if asks_perimeter and not asks_area:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                    'Что нужно найти: периметр прямоугольника.',
                    f'1) Периметр прямоугольника равен сумме длины и ширины, умноженной на 2: ({length} + {width}) × 2 = {perimeter}.',
                    f'Ответ: периметр прямоугольника равен {with_unit(perimeter, unit)}.'
                )
            if asks_area and asks_perimeter:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: длина прямоугольника {with_unit(length, unit)}, ширина {with_unit(width, unit)}.',
                    'Что нужно найти: площадь и периметр прямоугольника.',
                    f'1) Находим площадь: {length} × {width} = {area} {unit}².',
                    f'2) Находим периметр: ({length} + {width}) × 2 = {perimeter} {unit}.',
                    f'Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}.'
                )

    # 2) Квадрат: известна сторона (в разных формулировках).
    square_side = re.search(
        r'квадрат[^.?!]{0,80}?(?:со\s+сторон(?:ой|ою)?|длина\s+которого|длина\s+стороны)[^\d]{0,20}(\d+)\s*(мм|см|дм|м|км)',
        lower,
    )
    if square_side:
        side = int(square_side.group(1))
        unit = square_side.group(2)
        area = side * side
        perimeter = side * 4
        asks_area = 'площад' in lower
        asks_perimeter = 'периметр' in lower
        if asks_area and not asks_perimeter:
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: сторона квадрата равна {with_unit(side, unit)}.',
                'Что нужно найти: площадь квадрата.',
                f'1) Площадь квадрата равна стороне, умноженной на сторону: {side} × {side} = {area}.',
                f'Ответ: площадь квадрата равна {with_unit(area, unit, square=True)}.'
            )
        if asks_perimeter and not asks_area:
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: сторона квадрата равна {with_unit(side, unit)}.',
                'Что нужно найти: периметр квадрата.',
                f'1) Периметр квадрата равен четырём сторонам: {side} × 4 = {perimeter}.',
                f'Ответ: периметр квадрата равен {with_unit(perimeter, unit)}.'
            )

    # 3) Прямоугольник: одна сторона известна, другая задана через «на ... больше/меньше» или «в ... раз ...».
    patterns = [
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*меньше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+в\s+(\d+)\s+раза?\s+меньше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*больше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+в\s+(\d+)\s+раза?\s+больше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*короче', lower),
    ]
    for idx, match in enumerate(patterns):
        if not match:
            continue
        first = int(match.group(1))
        unit = match.group(2)
        second = int(match.group(3))
        if idx in {0, 4}:  # length known, width smaller by delta
            length = first
            width = first - second
            explanation_line = f'1) Сначала находим ширину: {length} - {second} = {width}.'
        elif idx == 1:  # length known, width less in ratio
            length = first
            if second == 0 or first % second != 0:
                return None
            width = first // second
            explanation_line = f'1) Сначала находим ширину: {length} : {second} = {width}.'
        elif idx == 2:  # width known, length greater by delta
            width = first
            length = first + second
            explanation_line = f'1) Сначала находим длину: {width} + {second} = {length}.'
        else:  # width known, length greater in ratio
            width = first
            length = first * second
            explanation_line = f'1) Сначала находим длину: {width} × {second} = {length}.'
        if width < 0:
            return None
        area = length * width
        perimeter = (length + width) * 2
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: длина и ширина прямоугольника связаны между собой.',
            'Что нужно найти: площадь и периметр прямоугольника.',
            explanation_line,
            f'2) Находим площадь: {length} × {width} = {area} {unit}².',
            f'3) Находим периметр: ({length} + {width}) × 2 = {perimeter} {unit}.',
            f'Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}.'
        )

    return None


def _final_20260416e_try_fraction_textbook_patterns(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    # Найти число по его дроби.
    match = re.search(r'найти\s+число[^.?!]*?(\d+)\s*/\s*(\d+)\s+его\s+(?:составляет|равна|равно|равны)\s*(\d+)', lower)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        part_value = int(match.group(3))
        if numerator == 0 or (part_value * denominator) % numerator != 0:
            return None
        whole = part_value * denominator // numerator
        one_part = part_value // numerator if numerator != 0 and part_value % numerator == 0 else None
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {numerator}/{denominator} числа равны {part_value}.',
            'Что нужно найти: всё число.',
        ]
        if one_part is not None:
            lines.append(f'1) Находим одну долю: {part_value} : {numerator} = {one_part}.')
            lines.append(f'2) Находим всё число: {one_part} × {denominator} = {whole}.')
        else:
            lines.append(f'1) Чтобы найти всё число, умножаем значение части на знаменатель и делим на числитель: {part_value} × {denominator} : {numerator} = {whole}.')
        lines.append(f'Ответ: {whole}.')
        return join_explanation_lines(*lines)

    # Известно целое и дробная часть; спрашивают часть или остаток.
    first_number_match = re.search(r'(\d+)', re.sub(r'\b\d+\s*/\s*\d+\b', ' ', lower))
    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    if first_number_match and fraction_match:
        total = int(first_number_match.group(1))
        numerator = int(fraction_match.group(1))
        denominator = int(fraction_match.group(2))
        if denominator == 0 or total * numerator % denominator != 0:
            return None
        one_part = total // denominator if total % denominator == 0 else None
        part_value = total * numerator // denominator

        if 'остальн' in lower:
            remaining = total - part_value
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: всего {total}, дробная часть {numerator}/{denominator}.',
                'Что нужно найти: сколько осталось после этой части.',
                f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
                f'2) Находим {numerator}/{denominator} от {total}: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {part_value}.',
                f'3) Находим остаток: {total} - {part_value} = {remaining}.',
                f'Ответ: {remaining}.'
            )

        if contains_any_fragment(lower, ('составляет', 'составля', 'часть комнаты', 'часть всех', 'от ')) or ('чему равна' in lower and '/' in lower):
            result_label = 'часть'
            if 'площад' in lower:
                return join_explanation_lines(
                    'Задача.',
                    _audit_task_line(raw_text),
                    'Решение.',
                    f'Что известно: всё равно {total}, нужно найти {numerator}/{denominator} этого числа.',
                    'Что нужно найти: искомую часть.',
                    f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
                    f'2) Находим {numerator}/{denominator} от {total}: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {part_value}.',
                    f'Ответ: {part_value}.'
                )
            return join_explanation_lines(
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: всё равно {total}, нужно найти {numerator}/{denominator} этого числа.',
                'Что нужно найти: искомую часть.',
                f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
                f'2) Находим {numerator}/{denominator} от {total}: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {part_value}.',
                f'Ответ: {part_value}.'
            )

    return None



# --- FINAL PATCH 2026-04-16F: relation geometry before direct widths, and fraction area units ---



def _final_20260416f_detect_metric_unit(lower: str) -> str:
    if 'кв.м' in lower or 'м2' in lower or 'м²' in lower:
        return 'м'
    if 'кв.дм' in lower or 'дм2' in lower or 'дм²' in lower:
        return 'дм'
    if 'кв.см' in lower or 'см2' in lower or 'см²' in lower:
        return 'см'
    if 'кв.мм' in lower or 'мм2' in lower or 'мм²' in lower:
        return 'мм'
    return geometry_unit(lower)


def _final_20260416f_try_geometry_relations(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    relation_patterns = [
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*меньше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+в\s+(\d+)\s+раза?\s+меньше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*больше', lower),
        re.search(r'ширина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}длина\s+в\s+(\d+)\s+раза?\s+больше', lower),
        re.search(r'длина\s+прямоугольника[^\d]{0,12}(\d+)\s*(мм|см|дм|м|км)[^\d]{0,40}ширина\s+на\s+(\d+)\s*(?:мм|см|дм|м|км)?\s*короче', lower),
    ]
    for idx, match in enumerate(relation_patterns):
        if not match:
            continue
        first = int(match.group(1))
        unit = match.group(2)
        second = int(match.group(3))
        if idx in {0, 4}:
            length = first
            width = first - second
            first_step = f'1) Сначала находим ширину: {length} - {second} = {width}.'
        elif idx == 1:
            length = first
            if second == 0 or first % second != 0:
                return None
            width = first // second
            first_step = f'1) Сначала находим ширину: {length} : {second} = {width}.'
        elif idx == 2:
            width = first
            length = first + second
            first_step = f'1) Сначала находим длину: {width} + {second} = {length}.'
        else:
            width = first
            length = first * second
            first_step = f'1) Сначала находим длину: {width} × {second} = {length}.'
        if width < 0:
            return None
        area = length * width
        perimeter = (length + width) * 2
        return join_explanation_lines(
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Что известно: одна сторона прямоугольника дана, а другая выражена через неё.',
            'Что нужно найти: площадь и периметр прямоугольника.',
            first_step,
            f'2) Находим площадь: {length} × {width} = {area} {unit}².',
            f'3) Находим периметр: ({length} + {width}) × 2 = {perimeter} {unit}.',
            f'Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}.'
        )
    return None


def _final_20260416f_try_fraction_area_part(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')
    if 'площад' not in lower or 'остальн' in lower:
        return None
    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    total_match = re.search(r'(\d+)', re.sub(r'\b\d+\s*/\s*\d+\b', ' ', lower))
    if not fraction_match or not total_match:
        return None
    numerator = int(fraction_match.group(1))
    denominator = int(fraction_match.group(2))
    total = int(total_match.group(1))
    if denominator == 0 or total % denominator != 0:
        return None
    unit = _final_20260416f_detect_metric_unit(lower) or 'м'
    one_part = total // denominator
    result = one_part * numerator
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: всё равно {with_unit(total, unit, square=True)}, нужно найти {numerator}/{denominator} этого числа.',
        'Что нужно найти: площадь искомой части.',
        f'1) Находим одну долю: {total} : {denominator} = {one_part}.',
        f'2) Находим {numerator}/{denominator} от {total}: {one_part} × {numerator} = {result}.',
        f'Ответ: площадь равна {with_unit(result, unit, square=True)}.'
    )



# --- FINAL PATCH 2026-04-16G: fraction remainder wording like peel/pulp ---



def _final_20260416g_try_fraction_remainder_named_part(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')
    if 'мякот' not in lower:
        return None
    total_match = re.search(r'(\d+)\s*(?:г|кг)', lower)
    fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', lower)
    if not total_match or not fraction_match:
        return None
    total = int(total_match.group(1))
    numerator = int(fraction_match.group(1))
    denominator = int(fraction_match.group(2))
    if denominator == 0 or total * numerator % denominator != 0:
        return None
    peel = total * numerator // denominator
    pulp = total - peel
    unit = 'г' if ' г' in lower else 'кг' if 'кг' in lower else ''
    one_part = total // denominator if total % denominator == 0 else None
    return join_explanation_lines(
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: масса банана {with_unit(total, unit)}, кожура составляет {numerator}/{denominator} всей массы.',
        'Что нужно найти: массу мякоти.',
        f'1) Находим одну долю: {total} : {denominator} = {one_part if one_part is not None else total / denominator}.',
        f'2) Находим массу кожуры: {one_part if one_part is not None else f"{total} : {denominator}"} × {numerator} = {peel}.',
        f'3) Находим массу мякоти: {total} - {peel} = {pulp}.',
        f'Ответ: масса мякоти равна {with_unit(pulp, unit)}.'
    )
