from __future__ import annotations

"""Statically materialized handler source for legacy_quantity_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_age_difference_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'лет' not in lower and 'год' not in lower:
        return None
    if 'старше' not in lower and 'младше' not in lower:
        return None

    direct_relation_match = re.search(
        r'([а-яёa-z-]+)\s+(старше|младше)\s+([а-яёa-z-]+)\s+на\s*(\d+(?:[.,]\d+)?)\s+год',
        lower,
    )
    inverse_relation_match = re.search(
        r'([а-яёa-z-]+)\s+на\s*(\d+(?:[.,]\d+)?)\s+год\w*\s+(старше|младше)\s+([а-яёa-z-]+)',
        lower,
    )
    if direct_relation_match:
        first_person = direct_relation_match.group(1)
        relation = direct_relation_match.group(2)
        second_person = direct_relation_match.group(3)
        diff_value = _to_fraction(direct_relation_match.group(4))
    elif inverse_relation_match:
        first_person = inverse_relation_match.group(1)
        diff_value = _to_fraction(inverse_relation_match.group(2))
        relation = inverse_relation_match.group(3)
        second_person = inverse_relation_match.group(4)
    else:
        return None
    if diff_value < 0:
        return None

    age_matches = list(re.finditer(r'([а-яёa-z-]+)\s*(\d+(?:[.,]\d+)?)\s*(?:лет|год(?:а)?)', lower))
    known_person = None
    known_age = None
    first_key = _soft_person_key(first_person)
    second_key = _soft_person_key(second_person)
    for age_match in age_matches:
        candidate_key = _soft_person_key(age_match.group(1))
        if candidate_key in {first_key, second_key}:
            known_person = age_match.group(1)
            known_age = _to_fraction(age_match.group(2))
            break
    if known_person is None or known_age is None:
        return None

    question_match = re.search(r'сколько\s+(?:лет|год(?:а)?)\s+([а-яёa-z-]+)', lower)
    target_person = question_match.group(1) if question_match else ''
    target_key = _soft_person_key(target_person)
    known_key = _soft_person_key(known_person)

    first_age = second_age = None
    if known_key == first_key:
        first_age = known_age
    elif known_key == second_key:
        second_age = known_age
    else:
        return None

    if relation == 'старше':
        if first_age is not None:
            second_age = first_age - diff_value
        else:
            first_age = second_age + diff_value
    else:
        if first_age is not None:
            second_age = first_age + diff_value
        else:
            first_age = second_age - diff_value

    if first_age is None or second_age is None or first_age < 0 or second_age < 0:
        return None

    if target_key == first_key:
        answer_person = target_person or first_person
        answer_age = first_age
    elif target_key == second_key:
        answer_person = target_person or second_person
        answer_age = second_age
    elif known_key == first_key:
        answer_person = second_person
        answer_age = second_age
    else:
        answer_person = first_person
        answer_age = first_age

    operation = '+' if (answer_age >= known_age and _soft_person_key(answer_person) != known_key) else '-'
    if _soft_person_key(answer_person) == first_key and known_key == second_key:
        operation = '+' if relation == 'старше' else '-'
    elif _soft_person_key(answer_person) == second_key and known_key == first_key:
        operation = '-' if relation == 'старше' else '+'

    first_display = first_person.capitalize()
    second_display = second_person.capitalize()
    known_display = known_person.capitalize()
    answer_display = answer_person.capitalize()

    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: {first_display} {relation} {second_display} на {_format_number(diff_value)} года, {known_display} {_format_number(known_age)} лет'),
        _ensure_sentence(f'Что нужно найти: сколько лет {answer_display}'),
        _ensure_sentence(
            f'1) Слово "{relation}" подсказывает действие {operation}: {_format_number(known_age)} {operation} {_format_number(diff_value)} = {_format_number(answer_age)}'
        ),
        f'Ответ: {answer_display} {_format_number(answer_age)} лет',
        'Совет: если кто-то старше, его возраст больше; если младше, его возраст меньше.',
    ])


def _try_mass_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    if not any(word in lower for word in ('масса', 'вес', 'весит', 'весят')):
        return None

    known_total_match = (
        re.search(
            r'(?:масса|вес)\s*(\d+)\s+одинаковых?\s+([а-яё\- ]+?)\s*(?:равна|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(кг|г)\b',
            lower,
        )
        or re.search(
            r'(\d+)\s+одинаковых?\s+([а-яё\- ]+?)\s+весят\s*(\d+(?:[.,]\d+)?)\s*(кг|г)\b',
            lower,
        )
    )
    known_one_match = (
        re.search(
            r'(?:масса|вес)\s*(?:1|одного|одной)\s+([а-яё\- ]+?)\s*(?:равна|составляет|=)?\s*(\d+(?:[.,]\d+)?)\s*(кг|г)\b',
            lower,
        )
        or re.search(
            r'(?:один|одна)\s+([а-яё\- ]+?)\s+весит\s*(\d+(?:[.,]\d+)?)\s*(кг|г)\b',
            lower,
        )
    )
    target_one = (
        re.search(r'(?:найди|определи)\s+(?:массу|вес)\s*(?:1|одного|одной)\b', lower) is not None
        or re.search(r'сколько\s+весит\s*(?:1|один|одна)\b', lower) is not None
    )
    target_count_match = (
        re.search(r'(?:какова\s+(?:масса|вес)|найди\s+(?:массу|вес)|сколько\s+весят?)\s*(\d+)\s+(?:таких\s+)?([а-яё\- ]+)?', lower)
        or re.search(r'сколько\s+весят\s*(\d+)\s+(?:таких\s+)?([а-яё\- ]+)?', lower)
    )

    if known_total_match:
        known_count = _to_fraction(known_total_match.group(1))
        item_phrase = _normalize_space(known_total_match.group(2)).strip(' .,!?:;') or 'предметов'
        total_mass = _to_fraction(known_total_match.group(3))
        unit = known_total_match.group(4).lower()
        if unit not in _MASS_UNITS or known_count <= 0:
            return None
        one_mass = total_mass / known_count

        if target_one:
            return _join_lines([
                'Задача.',
                _ensure_sentence(text),
                'Решение.',
                f'Что известно: {_format_number(known_count)} {item_phrase} весят {_format_number(total_mass)} {unit}.',
                'Что нужно найти: массу одного предмета.',
                f'1) Делим общую массу на количество предметов: {_format_number(total_mass)} : {_format_number(known_count)} = {_format_number(one_mass)} {unit}.',
                f'Ответ: {_format_number(one_mass)} {unit}',
                'Совет: чтобы найти массу одного одинакового предмета, общую массу делят на количество предметов.',
            ])

        if target_count_match:
            target_count = _to_fraction(target_count_match.group(1))
            target_mass = one_mass * target_count
            return _join_lines([
                'Задача.',
                _ensure_sentence(text),
                'Решение.',
                f'Что известно: {_format_number(known_count)} {item_phrase} весят {_format_number(total_mass)} {unit}.',
                f'Что нужно найти: массу {_format_number(target_count)} таких предметов.',
                f'1) Находим массу одного предмета: {_format_number(total_mass)} : {_format_number(known_count)} = {_format_number(one_mass)} {unit}.',
                f'2) Находим массу {_format_number(target_count)} предметов: {_format_number(one_mass)} × {_format_number(target_count)} = {_format_number(target_mass)} {unit}.',
                f'Ответ: {_format_number(target_mass)} {unit}',
                'Совет: сначала находят массу одного предмета, а потом умножают на нужное количество.',
            ])

    if known_one_match and target_count_match:
        item_phrase = _normalize_space(known_one_match.group(1)).strip(' .,!?:;') or 'предмета'
        one_mass = _to_fraction(known_one_match.group(2))
        unit = known_one_match.group(3).lower()
        if unit not in _MASS_UNITS:
            return None
        target_count = _to_fraction(target_count_match.group(1))
        target_mass = one_mass * target_count
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: масса одного такого предмета равна {_format_number(one_mass)} {unit}.',
            f'Что нужно найти: массу {_format_number(target_count)} таких предметов.',
            f'1) Умножаем массу одного предмета на количество: {_format_number(one_mass)} × {_format_number(target_count)} = {_format_number(target_mass)} {unit}.',
            f'Ответ: {_format_number(target_mass)} {unit}',
            'Совет: если известна масса одного одинакового предмета, для нескольких предметов её умножают на количество.',
        ])

    return None


def _try_reverse_measured_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if not _looks_like_reverse_measured_change_problem(text):
        return None

    quantities = _extract_compound_quantities(text)
    if len(quantities) < 2:
        return None
    group = quantities[0]['group']
    if len({quantity['group'] for quantity in quantities}) != 1:
        return None

    final_quantity = quantities[-1]
    if not _measure_quantity_has_final_state_marker(lower, final_quantity):
        return None

    changes: list[tuple[int, dict]] = []
    previous_end = 0
    for quantity in quantities[:-1]:
        sign = _infer_measure_change_sign(lower, quantity, previous_end)
        if sign is None:
            return None
        changes.append((sign, quantity))
        previous_end = quantity['end']
    if not changes:
        return None

    base_unit = _choose_measure_base_unit(group, quantities)
    visible_units: list[str] = []
    for quantity in quantities:
        visible_units.extend(quantity['units'])

    current_value = _quantity_value_in_unit(final_quantity, base_unit)
    known, question = _split_known_and_question(text)
    if question:
        question_line = question.rstrip('.!?').lower()
    else:
        question_line = 'какой была величина сначала'

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: после всех изменений стало {final_quantity["pretty"]}.',
        f'Что нужно найти: {question_line}.',
        f'1) Переводим конечную величину в {base_unit}: {final_quantity["pretty"]} = {_format_number(current_value)} {base_unit}.',
    ]
    step_number = 2

    for sign, quantity in reversed(changes):
        change_value = _quantity_value_in_unit(quantity, base_unit)
        lines.append(f'{step_number}) Переводим изменение в {base_unit}: {quantity["pretty"]} = {_format_number(change_value)} {base_unit}.')
        step_number += 1
        if sign > 0:
            previous_value = current_value - change_value
            operation = '-'
        else:
            previous_value = current_value + change_value
            operation = '+'
        if previous_value < 0:
            return None
        lines.append(
            f'{step_number}) Идём от ответа назад: '
            f'{_format_number(current_value)} {operation} {_format_number(change_value)} = {_format_number(previous_value)} {base_unit}.'
        )
        step_number += 1
        current_value = previous_value

    total_smallest = current_value * _MEASURE_GROUP_SCALES[group][base_unit]
    answer_text = _format_measure_total(total_smallest, group, visible_units)
    lines.append(f'{step_number}) Записываем ответ в удобных единицах: {_format_number(current_value)} {base_unit} = {answer_text}.')
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: если нужно узнать, сколько было сначала, начинай с конечного результата и отменяй изменения в обратном порядке.')
    return _join_lines(lines)


def _try_measured_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _looks_like_dual_subject_measured_after_changes_problem(text):
        return None
    lower = text.lower().replace('ё', 'е')
    quantities = _extract_compound_quantities(text)
    if len(quantities) < 2:
        return None
    if len({quantity['group'] for quantity in quantities}) != 1:
        return None

    group = quantities[0]['group']
    if group == 'length' and '/ч' in lower:
        return None

    changes: list[tuple[int, dict]] = []
    previous_end = quantities[0]['end']
    for quantity in quantities[1:]:
        sign = _infer_measure_change_sign(lower, quantity, previous_end)
        if sign is None:
            return None
        changes.append((sign, quantity))
        previous_end = quantity['end']
    if not changes:
        return None

    base_unit = _choose_measure_base_unit(group, quantities)
    visible_units: list[str] = []
    for quantity in quantities:
        visible_units.extend(quantity['units'])

    initial = quantities[0]
    current_value = _quantity_value_in_unit(initial, base_unit)
    step_number = 1
    known, question = _split_known_and_question(text)
    if question:
        question_line = question.rstrip('.!?').lower()
    else:
        question_line = 'итоговую величину'

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: сначала величина равна {initial["pretty"]}.',
        f'Что нужно найти: {question_line}.',
        f'{step_number}) Переводим начальную величину в {base_unit}: {initial["pretty"]} = {_format_number(current_value)} {base_unit}.',
    ]
    step_number += 1

    for sign, quantity in changes:
        change_value = _quantity_value_in_unit(quantity, base_unit)
        lines.append(f'{step_number}) Переводим изменение в {base_unit}: {quantity["pretty"]} = {_format_number(change_value)} {base_unit}.')
        step_number += 1
        new_value = current_value + sign * change_value
        if new_value < 0:
            return None
        reason = 'величину увеличили, поэтому прибавляем' if sign > 0 else 'часть величины убрали, поэтому вычитаем'
        op = '+' if sign > 0 else '-'
        lines.append(
            f'{step_number}) Так как {reason}: '
            f'{_format_number(current_value)} {op} {_format_number(change_value)} = {_format_number(new_value)} {base_unit}.'
        )
        step_number += 1
        current_value = new_value

    total_smallest = current_value * _MEASURE_GROUP_SCALES[group][base_unit]
    answer_text = _format_measure_total(total_smallest, group, visible_units)
    lines.append(f'{step_number}) Записываем ответ в удобных единицах: {_format_number(current_value)} {base_unit} = {answer_text}.')
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: в задачах с разными единицами сначала переводят величины в одинаковую единицу, а потом выполняют действия по порядку.')
    return _join_lines(lines)


def _try_temperature_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    if 'градус' not in lower:
        return None
    first_plain = next(iter(_plain_number_matches(lower)), None)
    change_match = re.search(r'на\s*(\d+(?:[.,]\d+)?)\s*градус\w*\s*(холоднее|теплее|выше|ниже)', lower)
    if not first_plain or not change_match:
        return None
    start_value = _to_fraction(first_plain.group(1))
    change_value = _to_fraction(change_match.group(1))
    keyword = change_match.group(2)
    is_increase = keyword in _TEMPERATURE_UP_HINTS
    result_value = start_value + change_value if is_increase else start_value - change_value
    sign = '+' if is_increase else '-'
    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: сначала было {_format_number(start_value)} градусов, потом стало на {_format_number(change_value)} градусов {keyword}'),
        _ensure_sentence(f'Что нужно найти: {(_question_text(text) or "какая стала температура").rstrip("?.!")}'),
        _ensure_sentence(f'1) {"При потеплении прибавляем" if is_increase else "При похолодании вычитаем"}: {_format_number(start_value)} {sign} {_format_number(change_value)} = {_format_number(result_value)}'),
        f'Ответ: {_format_number(result_value)} градусов',
        'Совет: слова "теплее" и "выше" означают прибавить, а слова "холоднее" и "ниже" — вычесть.',
    ]
    return _join_lines(lines)


def _try_measure_difference_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if 'на сколько' not in question and not any(word in question for word in ('длиннее', 'короче', 'выше', 'ниже', 'больше', 'меньше')):
        return None
    if _ACTION_VERB_RE.search(lower):
        return None

    quantities = _extract_compound_quantities(text)
    if len(quantities) < 2:
        return None
    first, second = quantities[0], quantities[1]
    if first['group'] != second['group']:
        return None

    group = first['group']
    base_unit = _choose_measure_base_unit(group, [first, second])
    first_value = _quantity_value_in_unit(first, base_unit)
    second_value = _quantity_value_in_unit(second, base_unit)
    bigger = max(first_value, second_value)
    smaller = min(first_value, second_value)
    diff_value = bigger - smaller
    total_smallest = diff_value * _MEASURE_GROUP_SCALES[group][base_unit]
    answer_text = _format_measure_total(total_smallest, group, first['units'] + second['units'])

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: первая величина равна {first["pretty"]}, вторая величина равна {second["pretty"]}'),
        _ensure_sentence(f'Что нужно найти: {(question or "на сколько одна величина больше или меньше другой").rstrip("?.!")}'),
        f'1) Переводим первую величину в {base_unit}: {first["pretty"]} = {_format_number(first_value)} {base_unit}.',
        f'2) Переводим вторую величину в {base_unit}: {second["pretty"]} = {_format_number(second_value)} {base_unit}.',
        f'3) Находим разность: {_format_number(bigger)} - {_format_number(smaller)} = {_format_number(diff_value)} {base_unit}.',
        f'4) Записываем ответ в удобных единицах: {_format_number(diff_value)} {base_unit} = {answer_text}.',
        f'Ответ: {answer_text}',
        'Совет: чтобы узнать, на сколько одна величина больше или меньше другой, нужно из большей величины вычесть меньшую.',
    ]
    return _join_lines(lines)
