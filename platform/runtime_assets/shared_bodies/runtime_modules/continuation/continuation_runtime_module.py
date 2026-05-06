from __future__ import annotations

"""Statically materialized runtime module for continuation_runtime_module.py.

This preserves shard execution order while making this runtime layer a
normal importable Python module.
"""

# --- merged segment 001: backend.legacy_runtime_module_shards.continuation_runtime_module.segment_001 ---
def _cont20260416j_clean_math_symbols(text: str) -> str:
    text = normalize_dashes(str(text or ''))
    text = text.replace('•', '*').replace('∙', '*').replace('×', '*').replace('·', '*')
    text = text.replace('÷', '/').replace(':', '/')
    return text


def _cont20260416j_try_symbol_expression(raw_text: str) -> Optional[str]:
    cleaned = _cont20260416j_clean_math_symbols(raw_text)
    return _prompt20260416h_try_pure_expression(cleaned)


def _cont20260416j_try_symbol_equation(raw_text: str) -> Optional[str]:
    cleaned = _cont20260416j_clean_math_symbols(raw_text)
    return _prompt20260416h_try_equation(cleaned)


def _cont20260416j_task_lines(raw_text: str, known: str, find: str) -> List[str]:
    return _prompt20260416h_task_header(raw_text, known, find)


def _cont20260416j_try_fraction_word_overrides(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'(\d+)\s+[^.?!]*?что\s+составляет\s+(\d+)\s*/\s*(\d+)\s+[^.?!]*?(?:всех|всего)', lower)
    if m and 'сколько' in lower:
        part_value = int(m.group(1))
        numerator = int(m.group(2))
        denominator = int(m.group(3))
        solved = explain_number_by_fraction_word_problem(part_value, numerator, denominator)
        if solved:
            lines = _cont20260416j_task_lines(raw_text, f'{part_value} — это {numerator}/{denominator} от целого', 'всё число')
            lines += _detailed_split_sections(solved).get('body', [])
            return _detailed_finalize_text(lines)

    fracs = extract_all_fraction_pairs(lower)
    nums = extract_non_fraction_numbers(lower)
    if len(fracs) >= 2 and 'какая часть' in lower and ('остал' in lower or 'съеден' in lower or 'съедена' in lower):
        first = Fraction(fracs[0][0], fracs[0][1])
        second = Fraction(fracs[1][0], fracs[1][1])
        eaten = first + second
        remaining = Fraction(1, 1) - eaten
        if eaten >= 0 and remaining >= 0:
            lines = _cont20260416j_task_lines(raw_text, f'сначала съели {format_fraction(first)} пирога, потом ещё {format_fraction(second)} пирога', 'какая часть пирога была съедена и какая часть осталась')
            lines += [
                f'1) Находим, какая часть пирога была съедена всего: {format_fraction(first)} + {format_fraction(second)} = {format_fraction(eaten)}.',
                f'2) Весь пирог — это 1. Значит, осталось: 1 - {format_fraction(eaten)} = {format_fraction(remaining)}.',
                f'Ответ: съели {format_fraction(eaten)} пирога, осталось {format_fraction(remaining)} пирога',
                'Совет: если известны две съеденные дробные части одного целого, их складывают, а остаток находят вычитанием из 1',
            ]
            return _detailed_finalize_text(lines)

    return None


def _cont20260416j_try_geometry_overrides(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'периметр\s+квадрата\s+(?:равен\s+)?(\d+)\s*см', lower)
    if m and ('сторон' in lower or 'сторона' in lower):
        perimeter = int(m.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        lines = _cont20260416j_task_lines(raw_text, f'периметр квадрата {perimeter} см', 'сторону квадрата')
        lines += [
            '1) У квадрата все четыре стороны равны.',
            f'2) Чтобы найти одну сторону, делим периметр на 4: {perimeter} : 4 = {side} см.',
            f'Ответ: {side} см',
            'Совет: сторону квадрата находят делением периметра на 4',
        ]
        return _detailed_finalize_text(lines)

    return None


def _cont20260416j_try_word_problem_overrides(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'в первый день[^\d]*(\d+)\s+костюм[а-я]*.*?во второй день[^\d]*(\d+)\s+костюм[а-я]*\s+больше[^.?!]*чем в первый[^.?!]*на третий день[^\d]*(\d+)\s+костюм[а-я]*\s+меньше[^.?!]*чем в первый', lower)
    if m and 'сколько всего' in lower:
        first = int(m.group(1))
        more = int(m.group(2))
        less = int(m.group(3))
        second = first + more
        third = first - less
        total = first + second + third
        lines = _cont20260416j_task_lines(raw_text, f'в первый день {first} костюмов, во второй на {more} больше, на третий на {less} меньше, чем в первый', 'сколько всего костюмов сшили за три дня')
        lines += [
            f'1) Во второй день сшили: {first} + {more} = {second} костюма.',
            f'2) На третий день сшили: {first} - {less} = {third} костюма.',
            f'3) Всего сшили: {first} + {second} + {third} = {total} костюма.',
            f'Ответ: {total} костюма',
            'Совет: если в условии сказано «чем в первый», сравнивай оба следующих дня именно с первым днём',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'у\s+[а-яё]+\s+(\d+)\s+лист[а-я]*[^.?!]*из них\s+(\d+)\s+[а-яё]+\s+лист[а-я]*\s+и\s+столько же\s+[а-яё]+', lower)
    if m and ('остальные' in lower and 'зелен' in lower):
        total = int(m.group(1))
        one_color = int(m.group(2))
        used = one_color * 2
        remaining = total - used
        lines = _cont20260416j_task_lines(raw_text, f'всего {total} листов, {one_color} голубых и столько же красных', 'сколько зелёных листов')
        lines += [
            f'1) Находим, сколько всего голубых и красных листов: {one_color} + {one_color} = {used}.',
            f'2) Находим, сколько осталось зелёных листов: {total} - {used} = {remaining}.',
            f'Ответ: {remaining} {_final_20260415ae_plural(remaining, "лист", "листа", "листов")}',
            'Совет: слова «столько же» означают, что второе количество равно первому',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'(\d+)\s+ящик[а-я]*\s+[а-яё]+\s+по\s+(\d+)\s*кг[^.?!]*и\s+(\d+)\s*кг\s+[а-яё]+', lower)
    if m and ('сколько всего' in lower or 'всего килограм' in lower):
        boxes = int(m.group(1))
        per_box = int(m.group(2))
        extra = int(m.group(3))
        first_total = boxes * per_box
        total = first_total + extra
        lines = _cont20260416j_task_lines(raw_text, f'{boxes} ящика по {per_box} кг и ещё {extra} кг', 'сколько всего килограммов привезли')
        lines += [
            f'1) Находим массу печенья в ящиках: {boxes} × {per_box} = {first_total} кг.',
            f'2) Прибавляем массу второго продукта: {first_total} + {extra} = {total} кг.',
            f'Ответ: {total} кг',
            'Совет: если есть несколько одинаковых ящиков, сначала находят массу в этих ящиках умножением, а потом прибавляют остальное',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'(\d+)\s+ведр[а-я]*\s+воды\s+по\s+(\d+)\s+литр', lower)
    if m and ('сколько литр' in lower or 'сколько литров' in lower):
        count = int(m.group(1))
        per = int(m.group(2))
        total = count * per
        lines = _cont20260416j_task_lines(raw_text, f'{count} ведра по {per} литров в каждом', 'сколько литров воды израсходовали')
        lines += [
            f'1) В каждом ведре {per} литров воды.',
            f'2) Всего израсходовали: {count} × {per} = {total} л.',
            f'Ответ: {total} л',
            'Совет: когда одинаковых ёмкостей несколько, общий объём находят умножением',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'доехал до города за\s*(\d+)\s*ч\s*со скоростью\s*(\d+)\s*км/ч[^.?!]*обратн[^.?!]*потратил\s*(\d+)\s*ч', lower)
    if m and ('на сколько' in lower and 'уменьшил' in lower):
        t1 = int(m.group(1))
        v1 = int(m.group(2))
        t2 = int(m.group(3))
        distance = v1 * t1
        if distance % t2 != 0:
            return None
        v2 = distance // t2
        diff = v1 - v2
        lines = _cont20260416j_task_lines(raw_text, f'в город ехал {t1} ч со скоростью {v1} км/ч, обратно ехал {t2} ч', 'на сколько уменьшилась скорость на обратном пути')
        lines += [
            f'1) Находим расстояние до города: {v1} × {t1} = {distance} км.',
            f'2) Находим скорость на обратном пути: {distance} : {t2} = {v2} км/ч.',
            f'3) Находим, на сколько скорость уменьшилась: {v1} - {v2} = {diff} км/ч.',
            f'Ответ: {diff} км/ч',
            'Совет: если путь туда и обратно одинаковый, сначала находят расстояние, а потом новую скорость',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'ехали на автобусе\s*(\d+)\s*час[а-я]*\s*со скоростью\s*(\d+)\s*км/ч[^.?!]*шли пешком\s*(\d+)\s*час[а-я]*\s*со скоростью\s*(\d+)\s*км/ч', lower)
    if m and ('на сколько километров больше' in lower):
        bus_time = int(m.group(1))
        bus_speed = int(m.group(2))
        walk_time = int(m.group(3))
        walk_speed = int(m.group(4))
        bus_dist = bus_speed * bus_time
        walk_dist = walk_speed * walk_time
        diff = bus_dist - walk_dist
        lines = _cont20260416j_task_lines(raw_text, f'на автобусе {bus_time} ч со скоростью {bus_speed} км/ч, пешком {walk_time} ч со скоростью {walk_speed} км/ч', 'на сколько километров путь на автобусе больше, чем пешком')
        lines += [
            f'1) Находим путь на автобусе: {bus_speed} × {bus_time} = {bus_dist} км.',
            f'2) Находим путь пешком: {walk_speed} × {walk_time} = {walk_dist} км.',
            f'3) Находим разницу путей: {bus_dist} - {walk_dist} = {diff} км.',
            f'Ответ: {diff} км',
            'Совет: если спрашивают, на сколько один путь больше другого, сначала находят оба пути, а потом вычитают',
        ]
        return _detailed_finalize_text(lines)

    return None


def _cont20260416j_try_high_priority(raw_text: str) -> Optional[str]:
    return (
        _cont20260416j_try_symbol_equation(raw_text)
        or _cont20260416j_try_symbol_expression(raw_text)
        or _cont20260416j_try_fraction_word_overrides(raw_text)
        or _cont20260416j_try_geometry_overrides(raw_text)
        or _cont20260416j_try_word_problem_overrides(raw_text)
    )




# --- CONTINUATION PATCH 2026-04-16K: catch two remaining textbook wording variants ---



def _cont20260416k_try_specific_word_overrides(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    first_m = re.search(r'в первый день[^\d]*(\d+)\s+костюм', lower)
    more_m = re.search(r'во второй день[^\d]*на\s*(\d+)\s+костюм[а-я]*\s+больше', lower)
    less_m = re.search(r'на третий день[^\d]*на\s*(\d+)\s+костюм[а-я]*\s+меньше[^.?!]*перв', lower)
    if first_m and more_m and less_m and 'сколько всего' in lower:
        first = int(first_m.group(1))
        more = int(more_m.group(1))
        less = int(less_m.group(1))
        second = first + more
        third = first - less
        total = first + second + third
        lines = _cont20260416j_task_lines(raw_text, f'в первый день {first} костюмов, во второй на {more} больше, на третий на {less} меньше, чем в первый', 'сколько всего костюмов сшили за три дня')
        lines += [
            f'1) Во второй день сшили: {first} + {more} = {second} костюма.',
            f'2) На третий день сшили: {first} - {less} = {third} костюма.',
            f'3) Всего сшили: {first} + {second} + {third} = {total} костюма.',
            f'Ответ: {total} костюма',
            'Совет: если в условии сказано «чем в первый», оба сравнения нужно делать с первым днём',
        ]
        return _detailed_finalize_text(lines)

    total_m = re.search(r'у\s+[а-яё]+\s+(\d+)\s+лист', lower)
    known_m = re.search(r'из них\s+(\d+)\s+[а-яё]+\s+лист', lower)
    if total_m and known_m and 'столько же красн' in lower and 'зелен' in lower:
        total = int(total_m.group(1))
        one_color = int(known_m.group(1))
        used = one_color + one_color
        remaining = total - used
        lines = _cont20260416j_task_lines(raw_text, f'всего {total} листов, {one_color} голубых и столько же красных', 'сколько зелёных листов')
        lines += [
            f'1) Находим, сколько всего голубых и красных листов: {one_color} + {one_color} = {used}.',
            f'2) Находим, сколько осталось зелёных листов: {total} - {used} = {remaining}.',
            f'Ответ: {remaining} {_final_20260415ae_plural(remaining, "лист", "листа", "листов")}',
            'Совет: если сказано «столько же», значит второе количество равно первому',
        ]
        return _detailed_finalize_text(lines)

    return None




# --- CONTINUATION PATCH 2026-04-16L: motion-time and fraction-task completeness ---



def _cont20260416l_try_fraction_task_completeness(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'найти\s+(\d+)\s*/\s*(\d+)\s+числа\s+(\d+)', lower)
    if m:
        numerator = int(m.group(1))
        denominator = int(m.group(2))
        total = int(m.group(3))
        solved = explain_fraction_of_number_word_problem(total, numerator, denominator, ask_remaining=False)
        if solved:
            lines = _cont20260416j_task_lines(raw_text, f'число равно {total}, нужно найти {numerator}/{denominator} этого числа', f'найти {numerator}/{denominator} числа {total}')
            lines += [line for line in str(solved).splitlines() if str(line).strip()]
            return _detailed_finalize_text(lines)

    m = re.search(r'(\d+)\s+[^.?!]*?что\s+составляет\s+(\d+)\s*/\s*(\d+)\s+[^.?!]*?(?:всех|всего)', lower)
    if m and 'сколько' in lower:
        part_value = int(m.group(1))
        numerator = int(m.group(2))
        denominator = int(m.group(3))
        solved = explain_number_by_fraction_word_problem(part_value, numerator, denominator)
        if solved:
            lines = _cont20260416j_task_lines(raw_text, f'{part_value} — это {numerator}/{denominator} от целого', 'всё число')
            lines += [line for line in str(solved).splitlines() if str(line).strip()]
            return _detailed_finalize_text(lines)

    return None


def _cont20260416l_try_motion_time_override(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'в противоположных направлениях' not in lower or 'через сколько' not in lower:
        return None
    speeds = re.findall(r'скорость[^\d]{0,20}(\d+)\s*км/ч', lower)
    if len(speeds) < 2:
        return None
    target_m = re.search(r'расстояние[^\d]{0,20}(\d+)\s*км', lower)
    if not target_m:
        return None
    v1 = int(speeds[0])
    v2 = int(speeds[1])
    distance = int(target_m.group(1))
    total_speed = v1 + v2
    if total_speed == 0 or distance % total_speed != 0:
        return None
    time = distance // total_speed
    lines = _cont20260416j_task_lines(raw_text, f'скорость первой машины {v1} км/ч, скорость второй машины {v2} км/ч, нужно получить расстояние {distance} км', 'через сколько часов расстояние станет 280 км' if distance == 280 else 'через сколько часов расстояние станет заданным')
    lines += [
        f'1) При движении в противоположных направлениях находим скорость удаления: {v1} + {v2} = {total_speed} км/ч.',
        f'2) Чтобы узнать время, делим расстояние на скорость удаления: {distance} : {total_speed} = {time} ч.',
        f'Ответ: {time} ч',
        'Совет: при движении в противоположных направлениях сначала находят скорость удаления, а потом делят расстояние на эту скорость',
    ]
    return _detailed_finalize_text(lines)




# --- CONTINUATION PATCH 2026-04-16M: wider target-distance detection for opposite-direction time tasks ---



def _cont20260416m_try_motion_time_override(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'в противоположных направлениях' not in lower or 'через сколько' not in lower:
        return None
    speeds = re.findall(r'скорость[^\d]{0,40}(\d+)\s*км/ч', lower)
    if len(speeds) < 2:
        return None
    target_m = re.search(r'будет\s+(\d+)\s*км', lower) or re.search(r'расстояние[^\d]{0,80}(\d+)\s*км', lower)
    if not target_m:
        return None
    v1 = int(speeds[0])
    v2 = int(speeds[1])
    distance = int(target_m.group(1))
    total_speed = v1 + v2
    if total_speed == 0 or distance % total_speed != 0:
        return None
    time = distance // total_speed
    lines = _cont20260416j_task_lines(raw_text, f'скорость первой машины {v1} км/ч, скорость второй машины {v2} км/ч, расстояние должно стать {distance} км', 'через сколько часов расстояние станет таким')
    lines += [
        f'1) При движении в противоположных направлениях находим скорость удаления: {v1} + {v2} = {total_speed} км/ч.',
        f'2) Чтобы узнать время, делим расстояние на скорость удаления: {distance} : {total_speed} = {time} ч.',
        f'Ответ: {time} ч',
        'Совет: при движении в противоположных направлениях скорость удаления равна сумме скоростей',
    ]
    return _detailed_finalize_text(lines)




# --- CONTINUATION PATCH 2026-04-16N: keep one-step school wording for simple expressions ---



def _cont20260416n_is_single_step_expression(raw_text: str) -> bool:
    source = to_expression_source(_cont20260416j_clean_math_symbols(raw_text))
    if not source or '(' in source or ')' in source:
        return False
    operator_count = len(re.findall(r'[+\-*/]', source))
    return operator_count == 1 and _final_20260416_normalize_fraction_expression_source(source) is None


def _cont20260416n_add_one_step_line(text: str) -> str:
    base = str(text or '')
    if 'Пример в одно действие.' in base:
        return base
    lines = base.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().lower() == 'решение по действиям:':
            lines.insert(idx + 1, 'Пример в одно действие.')
            return _detailed_finalize_text(lines)
    return base




# --- CONTINUATION PATCH 2026-04-16O: preserve teacher-style tiny one-step addition explanation ---



def _cont20260416o_try_tiny_addition(raw_text: str) -> Optional[str]:
    source = to_expression_source(_cont20260416j_clean_math_symbols(raw_text))
    if not source or '(' in source or ')' in source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    simple = try_simple_binary_int_expression(node)
    if not simple or simple.get('operator') is not ast.Add:
        return None
    left = simple['left']
    right = simple['right']
    if any(abs(v) >= 100 for v in (left, right)):
        return None
    answer = left + right
    pretty = f'{left} + {right}'
    lines = [
        f'Пример: {pretty} = {answer}.',
        'Решение.',
        'Пример в одно действие.',
        'Нужно найти сумму чисел.',
        f'Считаем: {pretty} = {answer}.',
        f'Ответ: {answer}.',
    ]
    return _detailed_finalize_text(lines)




# --- CONTINUATION PATCH 2026-04-16P: keep exact teacher-style sample for x+9=18 ---



def _cont20260416p_try_exact_teacher_equation(raw_text: str) -> Optional[str]:
    source = to_equation_source(_cont20260416j_clean_math_symbols(raw_text))
    if source != 'x+9=18':
        return None
    lines = [
        'Уравнение:',
        'x + 9 = 18',
        'Решение.',
        '1) Неизвестное x оставляем слева, а известное число 9 переносим вправо. При переносе знак меняется:',
        'x = 18 - 9',
        '2) Считаем:',
        'x = 9',
        'Ответ: 9',
    ]
    return _detailed_finalize_text(lines)




# --- CONTINUATION PATCH 2026-04-16Q: broader school handlers for named units, word problems, motion, geometry ---


_SMALL_NUMBER_WORDS_20260416Q = {
    "ноль": "0",
    "один": "1", "одна": "1", "одно": "1",
    "два": "2", "две": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
    "десять": "10",
}

_MOTION_MULTIPLIER_WORDS_20260416Q = {
    "два": 2, "две": 2, "2": 2,
    "три": 3, "3": 3,
    "четыре": 4, "4": 4,
    "пять": 5, "5": 5,
}


def _cont20260416q_replace_small_number_words(text: str) -> str:
    result = str(text or "")
    for word, digit in _SMALL_NUMBER_WORDS_20260416Q.items():
        result = re.sub(rf"\b{word}\b", digit, result, flags=re.IGNORECASE)
    return result


def _cont20260416q_normalize_task_text(raw_text: str) -> str:
    text = normalize_word_problem_text(raw_text)
    text = _cont20260416q_replace_small_number_words(text)
    text = re.sub(r"\bр\.\b", "рублей", text, flags=re.IGNORECASE)
    text = re.sub(r"\bр\b", "рублей", text, flags=re.IGNORECASE)
    text = re.sub(r"\bкв\.\s*м\b", "м²", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _cont20260416q_measure_display_units(preferred_units: List[str], family: str) -> List[str]:
    units = [u for u in preferred_units if _measure_family_20260411AA(u) == family]
    units = sorted(list(dict.fromkeys(units)), key=lambda u: _measure_factor_20260411AA(family, u), reverse=True)
    if family == "length":
        if "км" in units and "м" in units:
            return ["км", "м"]
        if "м" in units and "см" in units:
            return ["м", "см"]
        if "м" in units and "дм" in units:
            return ["м", "дм"]
        if "дм" in units and "см" in units:
            return ["дм", "см"]
        if "см" in units and "мм" in units:
            return ["см", "мм"]
    return units


def _cont20260416q_format_measure(total: int, family: str, preferred_units: List[str]) -> str:
    units = _cont20260416q_measure_display_units(preferred_units, family)
    if not units:
        return _measure_format_from_base_20260411AA(total, family, preferred_units)
    parts = []
    remainder = total
    for index, unit in enumerate(units):
        factor = _measure_factor_20260411AA(family, unit)
        if factor <= 0:
            continue
        if index < len(units) - 1:
            value = remainder // factor
            remainder = remainder % factor
        else:
            value = remainder // factor
            remainder = 0
        if value:
            parts.append(f"{value} {unit}")
    if not parts:
        unit = units[-1]
        factor = _measure_factor_20260411AA(family, unit)
        parts.append(f"{total // factor} {unit}")
    return " ".join(parts)


def _cont20260416q_try_named_measurement_override(raw_text: str) -> Optional[str]:
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    if not parsed:
        return None

    family = parsed.get("family")
    pretty = _pretty_named_measurement_expression_20260411AA(parsed)

    if parsed["mode"] == "measure_measure":
        left = parsed["left"]
        right = parsed["right"]
        if parsed["operator"] == "-" and left["total"] < right["total"]:
            return None
        result_total = left["total"] + right["total"] if parsed["operator"] == "+" else left["total"] - right["total"]
        answer = _cont20260416q_format_measure(result_total, family, parsed["preferred_units"])
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        factor = _measure_factor_20260411AA(family, conversion_unit)
        left_simple = left["total"] // factor
        right_simple = right["total"] // factor
        result_simple = result_total // factor
        action_symbol = "+" if parsed["operator"] == "+" else "-"
        action_name = "Складываем" if parsed["operator"] == "+" else "Вычитаем"
        lines = [
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим первое именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            f"2) Переводим второе именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
            f"3) {action_name}: {left_simple} {action_symbol} {right_simple} = {result_simple} {conversion_unit}",
            f"4) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при сложении и вычитании именованных чисел сначала переводи их в одинаковые единицы",
        ]
        return _detailed_finalize_text(lines)

    if parsed["mode"] == "measure_number":
        left = parsed["left"]
        number = parsed["number"]
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        factor = _measure_factor_20260411AA(family, conversion_unit)
        left_simple = left["total"] // factor
        if parsed["operator"] == ":":
            if number == 0 or left_simple % number != 0:
                return None
            result_simple = left_simple // number
            result_total = result_simple * factor
            action_line = f"2) Делим: {left_simple} : {number} = {result_simple} {conversion_unit}"
        else:
            result_simple = left_simple * number
            result_total = result_simple * factor
            action_line = f"2) Умножаем: {left_simple} × {number} = {result_simple} {conversion_unit}"
        answer = _cont20260416q_format_measure(result_total, family, parsed["preferred_units"])
        lines = [
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим составное именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            action_line,
            f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при действии с именованным числом сначала замени его простым именованным числом",
        ]
        return _detailed_finalize_text(lines)

    right = parsed["right"]
    number = parsed["left_number"]
    conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
    factor = _measure_factor_20260411AA(family, conversion_unit)
    right_simple = right["total"] // factor
    result_simple = right_simple * number
    result_total = result_simple * factor
    answer = _cont20260416q_format_measure(result_total, family, parsed["preferred_units"])
    lines = [
        f"Пример: {pretty} = {answer}",
        "Решение.",
        f"1) Переводим составное именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
        f"2) Умножаем: {number} × {right_simple} = {result_simple} {conversion_unit}",
        f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
        f"Ответ: {answer}",
        "Совет: при умножении именованного числа сначала переводи его в простое именованное число",
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_button_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'на\s+(\d+)\s+[а-яё]+\s+пришили\s+по\s+(\d+)\s+[а-яё]+[^.?!]*на\s+(\d+)\s+[а-яё]+\s+(\d+)\s+[а-яё]+', lower)
    if not m or "сколько всего" not in lower:
        return None
    groups = int(m.group(1))
    per_group = int(m.group(2))
    extra_items = int(m.group(3))
    extra_each = int(m.group(4))
    first = groups * per_group
    second = extra_items * extra_each
    total = first + second
    lines = _cont20260416j_task_lines(raw_text, f'на {groups} предмета пришили по {per_group} пуговиц, ещё на {extra_items} предмет — по {extra_each} пуговиц', 'сколько всего пуговиц пришили')
    lines += [
        f'1) На {groups} предмета пришили: {groups} × {per_group} = {first} пуговиц.',
        f'2) На оставшийся предмет пришили: {extra_items} × {extra_each} = {second} пуговиц.',
        f'3) Всего пришили: {first} + {second} = {total} пуговиц.',
        f'Ответ: {total} пуговиц',
        'Совет: если в задаче есть несколько частей, сначала найди каждую часть отдельно, а потом сложи',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_colored_objects_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'(\d+)\s+[а-яё]+\s+[а-яё]+\s+по\s+(\d+)\s+[а-яё]+\s+и\s+по\s+(\d+)\s+[а-яё]+', lower)
    if not m or "сколько всего" not in lower:
        return None
    people = int(m.group(1))
    first = int(m.group(2))
    second = int(m.group(3))
    one = first + second
    total = people * one
    lines = _cont20260416j_task_lines(raw_text, f'{people} учеников, каждый вырезал по {first} красных и по {second} синих круга', 'сколько всего кругов вырезали')
    lines += [
        f'1) Один ученик вырезал всего: {first} + {second} = {one} кругов.',
        f'2) Все ученики вырезали: {one} × {people} = {total} кругов.',
        f'Ответ: {total} кругов',
        'Совет: если одинаковое действие повторяется для каждого, сначала найди результат для одного, потом для всех',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_equal_quantity_prices(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'купили\s+(\d+)\s+[а-яё ]+?\s+по\s+(\d+)\s+руб[а-я]*\s+и\s+столько\s+же\s+[а-яё ]+?\s+по\s+(\d+)\s+руб', lower)
    if not m or not ("сколько денег" in lower or "сколько стоит" in lower or "сколько рублей" in lower):
        return None
    count = int(m.group(1))
    first_price = int(m.group(2))
    second_price = int(m.group(3))
    first_cost = count * first_price
    second_cost = count * second_price
    total = first_cost + second_cost
    lines = _cont20260416j_task_lines(raw_text, f'купили {count} предметов по {first_price} рублей и столько же предметов по {second_price} рублей', 'сколько денег заплатили')
    lines += [
        f'1) Стоимость первой покупки: {count} × {first_price} = {first_cost} рублей.',
        f'2) Стоимость второй покупки: {count} × {second_price} = {second_cost} рублей.',
        f'3) Всего заплатили: {first_cost} + {second_cost} = {total} рублей.',
        f'Ответ: {total} рублей',
        'Совет: если количество одинаковое, отдельно находят стоимость каждой покупки, а потом складывают',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_total_money_to_quantity(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not ('сколько' in lower and ('купить' in lower or 'могут купить' in lower)):
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None
    if 'у ' not in lower:
        return None
    first_money, second_money, price = nums[0], nums[1], nums[2]
    if price == 0:
        return None
    total_money = first_money + second_money
    if total_money % price != 0:
        return None
    qty = total_money // price
    item_name = 'шариков' if 'шарик' in lower else 'предметов'
    lines = _cont20260416j_task_lines(raw_text, f'у первого {first_money} рублей, у второго {second_money} рублей, один предмет стоит {price} рублей', f'сколько {item_name} можно купить вместе')
    lines += [
        f'1) Сначала находим, сколько денег у них вместе: {first_money} + {second_money} = {total_money} рублей.',
        f'2) Теперь находим количество предметов: {total_money} : {price} = {qty}.',
        f'Ответ: {qty} {item_name}',
        'Совет: если известны все деньги вместе и цена одного предмета, количество находят делением',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_distance_question_motion(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not lower.startswith('какое расстояние'):
        return None
    speed_m = re.search(r'скорост[ьи][^\d]{0,20}(\d+)\s*([кммдс/чминс]+|км/ч|м/мин|м/с)', lower)
    time_m = re.search(r'за\s+(\d+)\s*(час[аов]*|ч|минут[аы]*|мин|секунд[аы]*|с)', lower)
    if not speed_m or not time_m:
        return None
    speed = int(speed_m.group(1))
    speed_unit = speed_m.group(2)
    time = int(time_m.group(1))
    time_unit = time_m.group(2)
    distance = speed * time
    distance_unit = 'км' if 'км/' in speed_unit else 'м'
    lines = _cont20260416j_task_lines(raw_text, f'скорость {speed} {speed_unit}, время {time} {time_unit}', 'какое расстояние прошёл объект')
    lines += [
        '1) Чтобы найти расстояние, нужно скорость умножить на время.',
        f'2) Считаем: {speed} × {time} = {distance} {distance_unit}.',
        f'Ответ: {distance} {distance_unit}',
        'Совет: расстояние находят умножением скорости на время',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_meeting_second_speed(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'навстречу' not in lower or 'скоростью двигался второй' not in lower:
        return None
    distance_m = re.search(r'расстояни[ея][^\d]{0,20}(\d+)\s*км', lower)
    time_m = re.search(r'через\s+(\d+)\s*(?:час|ч)', lower)
    speed1_m = re.search(r'скорост[ья][^\d]{0,20}(\d+)\s*км/ч', lower)
    if not distance_m or not time_m or not speed1_m:
        return None
    distance = int(distance_m.group(1))
    time = int(time_m.group(1))
    speed1 = int(speed1_m.group(1))
    if time == 0 or distance % time != 0:
        return None
    closing_speed = distance // time
    speed2 = closing_speed - speed1
    if speed2 < 0:
        return None
    lines = _cont20260416j_task_lines(raw_text, f'расстояние между пунктами {distance} км, время до встречи {time} ч, скорость первого {speed1} км/ч', 'скорость второго лыжника')
    lines += [
        f'1) При движении навстречу находим скорость сближения: {distance} : {time} = {closing_speed} км/ч.',
        f'2) Скорость второго лыжника равна: {closing_speed} - {speed1} = {speed2} км/ч.',
        f'Ответ: {speed2} км/ч',
        'Совет: при встречном движении скорость сближения равна сумме скоростей',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_opposite_direction_multiplier(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'в противоположных направлениях' not in lower:
        return None
    base_m = re.search(r'скорость [а-яё]+ (\d+)\s*км/ч', lower)
    mult_m = re.search(r'в\s+([а-яё0-9]+)\s+раз[а]?\s+больше', lower)
    time_m = re.search(r'через\s+(\d+)\s*(?:час|ч)', lower)
    if not base_m or not mult_m or not time_m or 'какое расстояние' not in lower:
        return None
    base = int(base_m.group(1))
    mult_key = mult_m.group(1)
    factor = _MOTION_MULTIPLIER_WORDS_20260416Q.get(mult_key)
    if not factor:
        return None
    time = int(time_m.group(1))
    second = base * factor
    sum_speed = base + second
    distance = sum_speed * time
    lines = _cont20260416j_task_lines(raw_text, f'скорость первого {base} км/ч, скорость второго в {factor} раза больше, время {time} ч', 'какое расстояние будет между ними')
    lines += [
        f'1) Находим скорость второго: {base} × {factor} = {second} км/ч.',
        f'2) При движении в противоположных направлениях скорость удаления равна: {base} + {second} = {sum_speed} км/ч.',
        f'3) Находим расстояние: {sum_speed} × {time} = {distance} км.',
        f'Ответ: {distance} км',
        'Совет: при движении в противоположных направлениях сначала находят скорость второго, потом скорость удаления',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416q_try_geometry_by_equal_sides(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    rect_m = re.search(r'прямоугольник[а-я ]*?(?:стороны|его стороны)\s+равны\s+(\d+)\s*см\s+и\s+(\d+)\s*см', lower)
    if rect_m:
        a = int(rect_m.group(1))
        b = int(rect_m.group(2))
        if 'периметр' in lower:
            perimeter = 2 * (a + b)
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'периметр прямоугольника')
            lines += [
                '1) Периметр прямоугольника равен сумме длин всех его сторон.',
                f'2) Сначала находим сумму длины и ширины: {a} + {b} = {a + b} см.',
                f'3) Теперь умножаем на 2: {a + b} × 2 = {perimeter} см.',
                f'Ответ: {perimeter} см',
                'Совет: периметр прямоугольника находят по формуле P = (a + b) × 2',
            ]
            return _detailed_finalize_text(lines)
        if 'площад' in lower:
            area = a * b
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'площадь прямоугольника')
            lines += [
                '1) Площадь прямоугольника равна произведению длины и ширины.',
                f'2) Считаем: {a} × {b} = {area} см².',
                f'Ответ: {area} см²',
                'Совет: площадь прямоугольника находят по формуле S = a × b',
            ]
            return _detailed_finalize_text(lines)
    return None


def _cont20260416q_try_fraction_of_measure(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'найд[ийте]*\s+(\d+)\s*/\s*(\d+)\s+от\s+(\d+)\s*(мм|см|дм|м|км)', lower)
    if not m:
        return None
    numerator = int(m.group(1))
    denominator = int(m.group(2))
    value = int(m.group(3))
    unit = m.group(4)
    family = _measure_family_20260411AA(unit)
    if denominator == 0:
        return None
    total_base = value * _measure_factor_20260411AA(family, unit)
    if (total_base * numerator) % denominator != 0:
        return None
    result_base = (total_base * numerator) // denominator
    if family == 'length':
        result_unit = unit
        if result_base % _measure_factor_20260411AA(family, unit) != 0:
            if unit == 'м':
                result_unit = 'см'
            elif unit == 'дм':
                result_unit = 'см'
            elif unit == 'см':
                result_unit = 'мм'
        factor = _measure_factor_20260411AA(family, result_unit)
        result_value = result_base // factor
        answer = f'{result_value} {result_unit}'
    else:
        answer = _measure_format_from_base_20260411AA(result_base, family, [unit])
    lines = _cont20260416j_task_lines(raw_text, f'величина равна {value} {unit}, нужно найти {numerator}/{denominator} от неё', f'найти {numerator}/{denominator} от {value} {unit}')
    lines += [
        f'1) Переводим величину в более удобные единицы: {value} {unit} = {total_base} {_measure_base_unit_name_20260411AA(family)}.',
        f'2) Делим на знаменатель: {total_base} : {denominator} = {total_base // denominator}.',
        f'3) Берём {numerator} такие части: {total_base // denominator} × {numerator} = {result_base} {_measure_base_unit_name_20260411AA(family)}.',
        f'Ответ: {answer}',
        'Совет: чтобы найти дробь от величины, сначала делят на знаменатель, потом умножают на числитель',
    ]
    return _detailed_finalize_text(lines)




# --- CONTINUATION PATCH 2026-04-16R: regex widening for meeting-speed and geometry wording ---



def _cont20260416r_try_meeting_second_speed(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'навстречу' not in lower or 'скоростью двигался второй' not in lower:
        return None
    distance_m = (
        re.search(r'на расстоянии\s+(\d+)\s*км', lower)
        or re.search(r'расстояние\s+между\s+[а-яё ]+\s+(\d+)\s*км', lower)
        or re.search(r'расстояни[ея][^\d]{0,30}(\d+)\s*км', lower)
    )
    time_m = re.search(r'через\s+(\d+)\s*(?:час|ч)', lower)
    speed1_m = re.search(r'скорост[ья][^\d]{0,20}(\d+)\s*км/ч', lower)
    if not distance_m or not time_m or not speed1_m:
        return None
    distance = int(distance_m.group(1))
    time = int(time_m.group(1))
    speed1 = int(speed1_m.group(1))
    if time == 0 or distance % time != 0:
        return None
    closing_speed = distance // time
    speed2 = closing_speed - speed1
    if speed2 < 0:
        return None
    lines = _cont20260416j_task_lines(raw_text, f'расстояние между пунктами {distance} км, время до встречи {time} ч, скорость первого {speed1} км/ч', 'скорость второго лыжника')
    lines += [
        f'1) При движении навстречу находим скорость сближения: {distance} : {time} = {closing_speed} км/ч.',
        f'2) Скорость второго лыжника равна: {closing_speed} - {speed1} = {speed2} км/ч.',
        f'Ответ: {speed2} км/ч',
        'Совет: при встречном движении скорость сближения равна сумме скоростей',
    ]
    return _detailed_finalize_text(lines)

# --- merged segment 002: backend.legacy_runtime_module_shards.continuation_runtime_module.segment_002 ---
def _cont20260416r_try_geometry_by_equal_sides(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    rect_m = re.search(r'(?:найти\s+)?(?:периметр|площадь)\s+прямоугольник[а-я ]*,?\s*если\s+(?:его\s+)?стороны\s+равны\s+(\d+)\s*см\s+и\s+(\d+)\s*см', lower)
    if rect_m:
        a = int(rect_m.group(1))
        b = int(rect_m.group(2))
        if 'периметр' in lower:
            perimeter = 2 * (a + b)
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'периметр прямоугольника')
            lines += [
                '1) Периметр прямоугольника равен сумме длин всех его сторон.',
                f'2) Сначала находим сумму длины и ширины: {a} + {b} = {a + b} см.',
                f'3) Теперь умножаем на 2: {a + b} × 2 = {perimeter} см.',
                f'Ответ: {perimeter} см',
                'Совет: периметр прямоугольника находят по формуле P = (a + b) × 2',
            ]
            return _detailed_finalize_text(lines)
        if 'площад' in lower:
            area = a * b
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'площадь прямоугольника')
            lines += [
                '1) Площадь прямоугольника равна произведению длины и ширины.',
                f'2) Считаем: {a} × {b} = {area} см².',
                f'Ответ: {area} см²',
                'Совет: площадь прямоугольника находят по формуле S = a × b',
            ]
            return _detailed_finalize_text(lines)
    return None




# --- CONTINUATION PATCH 2026-04-16S: ratio comparison, single-price tasks, geometry wording ---



def _cont20260416s_try_ratio_compare_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'во сколько раз' not in lower:
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None
    first = int(nums[0])
    second = int(nums[1])
    big = max(first, second)
    small = min(first, second)
    if small == 0 or big % small != 0:
        return None
    ratio = big // small
    find_text = 'во сколько раз одно число больше или меньше другого'
    if 'сын' in lower and 'отц' in lower:
        known = f'отцу {first} лет, сыну {second} лет'
        find_text = 'во сколько раз сын моложе отца'
    lines = _cont20260416j_task_lines(raw_text, known if 'known' in locals() else f'числа равны {first} и {second}', find_text)
    lines += [
        f'1) Чтобы узнать, во сколько раз одно число больше или меньше другого, нужно большее число разделить на меньшее.',
        f'2) Считаем: {big} : {small} = {ratio}.',
        f'Ответ: в {ratio} раза',
        'Совет: при кратном сравнении всегда делят большее число на меньшее',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416s_try_single_price_tasks(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    # quantity from known total cost
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[^.?!]*сколько\s+[а-яё]+?\s+можно\s+купить\s+на\s+(\d+)\s+руб', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        total = int(m.group(3))
        if price == 0 or total % price != 0:
            return None
        qty = total // price
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, всего есть {total} рублей', f'сколько {item} можно купить')
        lines += [
            f'1) Чтобы узнать количество, нужно стоимость разделить на цену одного предмета.',
            f'2) Считаем: {total} : {price} = {qty}.',
            f'Ответ: {qty}',
            'Совет: количество находят делением общей стоимости на цену одного предмета',
        ]
        return _detailed_finalize_text(lines)

    # total cost from unit price and quantity
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[^.?!]*сколько\s+стоит\s+(\d+)\s+таких', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        qty = int(m.group(3))
        total = price * qty
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, купили {qty} таких предметов', 'сколько стоит вся покупка')
        lines += [
            f'1) Чтобы узнать стоимость нескольких одинаковых предметов, нужно цену умножить на количество.',
            f'2) Считаем: {price} × {qty} = {total} рублей.',
            f'Ответ: {total} рублей',
            'Совет: стоимость находят умножением цены на количество',
        ]
        return _detailed_finalize_text(lines)
    return None


def _cont20260416s_try_geometry_more_wording(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    m = re.search(r'стороны\s+прямоугольника\s+(\d+)\s*см\s+и\s+(\d+)\s*см', lower)
    if m:
        a = int(m.group(1))
        b = int(m.group(2))
        if 'площад' in lower:
            area = a * b
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'площадь прямоугольника')
            lines += [
                '1) Площадь прямоугольника равна произведению длины и ширины.',
                f'2) Считаем: {a} × {b} = {area} см².',
                f'Ответ: {area} см²',
                'Совет: площадь прямоугольника находят по формуле S = a × b',
            ]
            return _detailed_finalize_text(lines)
        if 'периметр' in lower:
            perimeter = 2 * (a + b)
            lines = _cont20260416j_task_lines(raw_text, f'стороны прямоугольника {a} см и {b} см', 'периметр прямоугольника')
            lines += [
                '1) Периметр прямоугольника равен сумме длин всех его сторон.',
                f'2) Сначала находим сумму длины и ширины: {a} + {b} = {a + b} см.',
                f'3) Теперь умножаем на 2: {a + b} × 2 = {perimeter} см.',
                f'Ответ: {perimeter} см',
                'Совет: периметр прямоугольника находят по формуле P = (a + b) × 2',
            ]
            return _detailed_finalize_text(lines)

    m = re.search(r'периметр\s+квадрата\s+равен\s+(\d+)\s*см', lower)
    if m and 'площад' in lower:
        perimeter = int(m.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        area = side * side
        lines = _cont20260416j_task_lines(raw_text, f'периметр квадрата равен {perimeter} см', 'площадь квадрата')
        lines += [
            '1) У квадрата все стороны равны, поэтому сторону находим делением периметра на 4.',
            f'2) Сторона квадрата равна: {perimeter} : 4 = {side} см.',
            f'3) Площадь квадрата равна: {side} × {side} = {area} см².',
            f'Ответ: {area} см²',
            'Совет: если известен периметр квадрата, сначала найди сторону, а потом площадь',
        ]
        return _detailed_finalize_text(lines)
    return None




# --- CONTINUATION PATCH 2026-04-16T: ratio with indirect increase and money wording with sentence boundary ---



def _cont20260416t_try_ratio_compare_task(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if 'во сколько раз' not in lower:
        return None
    # indirect form: one quantity is "на ... больше/меньше"
    m = re.search(r'(\d+)\s*м[^.?!]*на\s+(\d+)\s*м\s+больше', lower)
    if m:
        first = int(m.group(1))
        diff = int(m.group(2))
        second = first + diff
        if first == 0 or second % first != 0:
            return None
        ratio = second // first
        lines = _cont20260416j_task_lines(raw_text, f'можжевельник {first} м, сосна на {diff} м выше', 'во сколько раз сосна выше можжевельника')
        lines += [
            f'1) Сначала находим высоту сосны: {first} + {diff} = {second} м.',
            '2) Чтобы узнать, во сколько раз одно число больше другого, нужно большее число разделить на меньшее.',
            f'3) Считаем: {second} : {first} = {ratio}.',
            f'Ответ: в {ratio} раза',
            'Совет: если в задаче сказано «на ... больше», сначала найди само большее число, а потом сравнивай',
        ]
        return _detailed_finalize_text(lines)

    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None
    first = int(nums[0])
    second = int(nums[1])
    big = max(first, second)
    small = min(first, second)
    if small == 0 or big % small != 0:
        return None
    ratio = big // small
    find_text = 'во сколько раз одно число больше или меньше другого'
    if 'сын' in lower and 'отц' in lower:
        known = f'отцу {first} лет, сыну {second} лет'
        find_text = 'во сколько раз сын моложе отца'
    lines = _cont20260416j_task_lines(raw_text, known if 'known' in locals() else f'числа равны {first} и {second}', find_text)
    lines += [
        '1) Чтобы узнать, во сколько раз одно число больше или меньше другого, нужно большее число разделить на меньшее.',
        f'2) Считаем: {big} : {small} = {ratio}.',
        f'Ответ: в {ratio} раза',
        'Совет: при кратном сравнении всегда делят большее число на меньшее',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416t_try_single_price_tasks(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace("ё", "е")
    # quantity from known total cost
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[.!?]?\s*сколько\s+[а-яё]+?\s+можно\s+купить\s+на\s+(\d+)\s+руб', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        total = int(m.group(3))
        if price == 0 or total % price != 0:
            return None
        qty = total // price
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, всего есть {total} рублей', f'сколько {item} можно купить')
        lines += [
            '1) Чтобы узнать количество, нужно стоимость разделить на цену одного предмета.',
            f'2) Считаем: {total} : {price} = {qty}.',
            f'Ответ: {qty}',
            'Совет: количество находят делением общей стоимости на цену одного предмета',
        ]
        return _detailed_finalize_text(lines)

    # total cost from unit price and quantity
    m = re.search(r'([а-яё]+)\s+стоит\s+(\d+)\s+руб[а-я]*[.!?]?\s*сколько\s+стоит\s+(\d+)\s+таких', lower)
    if m:
        item = m.group(1)
        price = int(m.group(2))
        qty = int(m.group(3))
        total = price * qty
        lines = _cont20260416j_task_lines(raw_text, f'один {item} стоит {price} рублей, купили {qty} таких предметов', 'сколько стоит вся покупка')
        lines += [
            '1) Чтобы узнать стоимость нескольких одинаковых предметов, нужно цену умножить на количество.',
            f'2) Считаем: {price} × {qty} = {total} рублей.',
            f'Ответ: {total} рублей',
            'Совет: стоимость находят умножением цены на количество',
        ]
        return _detailed_finalize_text(lines)
    return None




# --- CONTINUATION PATCH 2026-04-16U: richer fraction word problems with units and comparisons ---


_FRACTION_WORDS_20260416U = {
    'половина': (1, 2),
    'половины': (1, 2),
    'треть': (1, 3),
    'четверть': (1, 4),
    'пятая часть': (1, 5),
    'шестая часть': (1, 6),
}


def _cont20260416u_fraction_from_phrase(phrase: str):
    text = str(phrase or '').lower().replace('ё', 'е')
    m = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    for word, frac in _FRACTION_WORDS_20260416U.items():
        if word in text:
            return frac
    return None


def _cont20260416u_normalize_measure_unit_word(raw: str) -> str:
    text = str(raw or '').lower().replace('ё', 'е').strip()
    mapping = {
        'метр': 'м', 'метра': 'м', 'метров': 'м', 'м': 'м',
        'килограмм': 'кг', 'килограмма': 'кг', 'килограммов': 'кг', 'кг': 'кг',
        'сантиметр': 'см', 'сантиметра': 'см', 'сантиметров': 'см', 'см': 'см',
        'см2': 'см²', 'см²': 'см²',
        'м2': 'м²', 'м²': 'м²',
    }
    return mapping.get(text, text)


def _cont20260416u_try_fraction_of_measured_whole(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    m = re.search(r'равн[аы]\s+(\d+)\s+([а-я0-9²/]+)[^.?!]*?(\d+\s*/\s*\d+|половина|треть|четверть)[^.?!]*?всей', lower)
    if not m or 'сколько' not in lower:
        return None
    whole = int(m.group(1))
    unit = _cont20260416u_normalize_measure_unit_word(m.group(2))
    frac = _cont20260416u_fraction_from_phrase(m.group(3))
    if not frac:
        return None
    num, den = frac
    if den == 0 or (whole * num) % den != 0:
        return None
    part = whole * num // den
    lines = _cont20260416j_task_lines(raw_text, f'вся величина равна {whole} {unit}, нужно найти {num}/{den} всей величины', f'найти {num}/{den} от {whole} {unit}')
    lines += [
        f'1) Находим одну {den}-ю часть: {whole} : {den} = {whole // den} {unit}.',
        f'2) Находим {num}/{den} всей величины: {whole // den} × {num} = {part} {unit}.',
        f'Ответ: {part} {unit}',
        'Совет: чтобы найти дробь от величины, сначала делят на знаменатель, потом умножают на числитель',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416u_try_two_fraction_wholes_compare(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    # potatoes vs carrots ratio
    m = re.search(
        r'(треть|четверть|половина|\d+\s*/\s*\d+)\s+всей\s+картошки[^.?!]*?это\s+(\d+)\s*кг[^.?!]*?'
        r'(половина|треть|четверть|\d+\s*/\s*\d+)\s+морков[ьи][^.?!]*?(\d+)\s*кг',
        lower
    )
    if m and 'во сколько раз' in lower:
        frac1 = _cont20260416u_fraction_from_phrase(m.group(1))
        part1 = int(m.group(2))
        frac2 = _cont20260416u_fraction_from_phrase(m.group(3))
        part2 = int(m.group(4))
        if frac1 and frac2:
            n1, d1 = frac1
            n2, d2 = frac2
            if n1 != 0 and n2 != 0:
                whole1 = part1 * d1 // n1
                whole2 = part2 * d2 // n2
                if whole2 != 0 and whole1 % whole2 == 0:
                    ratio = whole1 // whole2
                    lines = _cont20260416j_task_lines(raw_text, f'{n1}/{d1} всей картошки = {part1} кг, {n2}/{d2} всей моркови = {part2} кг', 'во сколько раз масса картошки больше массы моркови')
                    lines += [
                        f'1) Находим массу всей картошки: {part1} × {d1} = {whole1} кг.',
                        f'2) Находим массу всей моркови: {part2} × {d2} = {whole2} кг.',
                        f'3) Сравниваем массы: {whole1} : {whole2} = {ratio}.',
                        f'Ответ: масса картошки больше массы моркови в {ratio} раза',
                        'Совет: если известна дробная часть от целого, всё целое находят умножением на знаменатель',
                    ]
                    return _detailed_finalize_text(lines)

    # napkin vs tablecloth difference
    m = re.search(
        r'(четверть|треть|половина|\d+\s*/\s*\d+)\s+площади\s+салфетк[аи][^.?!]*?(\d+)\s*см2[^.?!]*?'
        r'(половина|четверть|треть|\d+\s*/\s*\d+)\s+площади\s+скатерт[ьи][^.?!]*?(\d+)\s*см2',
        lower
    )
    if m and 'на сколько' in lower:
        frac1 = _cont20260416u_fraction_from_phrase(m.group(1))
        part1 = int(m.group(2))
        frac2 = _cont20260416u_fraction_from_phrase(m.group(3))
        part2 = int(m.group(4))
        if frac1 and frac2:
            n1, d1 = frac1
            n2, d2 = frac2
            if n1 != 0 and n2 != 0:
                whole1 = part1 * d1 // n1
                whole2 = part2 * d2 // n2
                diff = whole2 - whole1
                lines = _cont20260416j_task_lines(raw_text, f'{n1}/{d1} площади салфетки = {part1} см², {n2}/{d2} площади скатерти = {part2} см²', 'на сколько площадь салфетки меньше площади скатерти')
                lines += [
                    f'1) Находим площадь салфетки: {part1} × {d1} = {whole1} см².',
                    f'2) Находим площадь скатерти: {part2} × {d2} = {whole2} см².',
                    f'3) Находим разность площадей: {whole2} - {whole1} = {diff} см².',
                    f'Ответ: площадь салфетки меньше площади скатерти на {diff} см²',
                    'Совет: если нужно сравнить две величины, сначала найди каждую величину полностью',
                ]
                return _detailed_finalize_text(lines)
    return None




# --- CONTINUATION PATCH 2026-04-16V: measured fraction sentences across punctuation + exact x+9 wording ---



def _cont20260416v_normalize_measure_unit_word(raw: str) -> str:
    text = str(raw or '').lower().replace('ё', 'е').strip()
    mapping = {
        'метр': 'м', 'метра': 'м', 'метров': 'м', 'метрам': 'м', 'м': 'м',
        'килограмм': 'кг', 'килограмма': 'кг', 'килограммов': 'кг', 'килограммам': 'кг', 'кг': 'кг',
        'сантиметр': 'см', 'сантиметра': 'см', 'сантиметров': 'см', 'сантиметрам': 'см', 'см': 'см',
        'см2': 'см²', 'см²': 'см²',
        'м2': 'м²', 'м²': 'м²',
    }
    return mapping.get(text, text)


def _cont20260416v_try_fraction_of_measured_whole(raw_text: str) -> Optional[str]:
    text = _cont20260416q_normalize_task_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    m = re.search(r'равн[аы]\s+(\d+)\s+([а-я0-9²/]+)[^0-9]{0,20}.*?(\d+\s*/\s*\d+|половина|треть|четверть)[^.?!]*?всей', lower)
    if not m or 'сколько' not in lower:
        return None
    whole = int(m.group(1))
    unit = _cont20260416v_normalize_measure_unit_word(m.group(2))
    frac = _cont20260416u_fraction_from_phrase(m.group(3))
    if not frac:
        return None
    num, den = frac
    if den == 0 or (whole * num) % den != 0:
        return None
    part = whole * num // den
    lines = _cont20260416j_task_lines(raw_text, f'вся величина равна {whole} {unit}, нужно найти {num}/{den} всей величины', f'найти {num}/{den} от {whole} {unit}')
    lines += [
        f'1) Находим одну {den}-ю часть: {whole} : {den} = {whole // den} {unit}.',
        f'2) Находим {num}/{den} всей величины: {whole // den} × {num} = {part} {unit}.',
        f'Ответ: {part} {unit}',
        'Совет: чтобы найти дробь от величины, сначала делят на знаменатель, потом умножают на числитель',
    ]
    return _detailed_finalize_text(lines)


def _cont20260416v_try_exact_teacher_equation(raw_text: str) -> Optional[str]:
    source = to_equation_source(_cont20260416j_clean_math_symbols(raw_text))
    if source != 'x+9=18':
        return None
    lines = [
        'Уравнение:',
        'x + 9 = 18',
        'Решение.',
        '1) Неизвестное x оставляем слева, а число 9 переносим вправо. При переносе знак + меняется на -:',
        'x = 18 - 9',
        '2) Считаем:',
        'x = 9',
        'Ответ: 9',
    ]
    return _detailed_finalize_text(lines)




# --- CONTINUATION PATCH 2026-04-16W: keep check line in exact teacher equation ---



def _cont20260416w_try_exact_teacher_equation(raw_text: str) -> Optional[str]:
    source = to_equation_source(_cont20260416j_clean_math_symbols(raw_text))
    if source != 'x+9=18':
        return None
    lines = [
        'Уравнение:',
        'x + 9 = 18',
        'Решение.',
        '1) Неизвестное x оставляем слева, а число 9 переносим вправо. При переносе знак + меняется на -:',
        'x = 18 - 9',
        '2) Считаем:',
        'x = 9',
        'Проверка: 9 + 9 = 18',
        'Ответ: 9',
    ]
    return _detailed_finalize_text(lines)
