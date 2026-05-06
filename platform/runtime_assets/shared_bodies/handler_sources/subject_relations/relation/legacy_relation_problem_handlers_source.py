from __future__ import annotations

"""Statically materialized handler source for legacy_relation_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_sum_unknown_part_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    asks_other = any(fragment in lower for fragment in ('другое число', 'другого числа', 'другой отрезок', 'длину другого', 'третью сторону', 'неизвестную часть'))
    if 'сумм' not in lower or not asks_other:
        return None

    measured_values = _extract_distance_values(lower)
    if measured_values:
        if len(measured_values) < 2:
            return None
        total_raw, total_unit, _ = measured_values[0]
        known_raw, known_unit, _ = measured_values[1]
        unit = min((total_unit, known_unit), key=lambda current: _LENGTH_UNITS[current])
        total_value = _convert_length(total_raw, total_unit, unit)
        known_value = _convert_length(known_raw, known_unit, unit)
        other_value = total_value - known_value
        if other_value < 0:
            return None
        question = _question_text(text) or 'длину другой части'
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: сумма равна {_format_number(total_value)} {unit}, одна часть равна {_format_number(known_value)} {unit}.',
            _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
            '1) Чтобы найти неизвестную часть, из всей суммы вычитаем известную часть.',
            f'2) {_format_number(total_value)} - {_format_number(known_value)} = {_format_number(other_value)} {unit}.',
            f'Ответ: {_format_number(other_value)} {unit}',
            'Совет: если известны целое и одна часть, другую часть находят вычитанием.',
        ])

    number_matches = _plain_number_matches(lower)
    if len(number_matches) < 2:
        return None
    total_value = _to_fraction(number_matches[0].group(1))
    known_value = _to_fraction(number_matches[1].group(1))
    other_value = total_value - known_value
    if other_value < 0:
        return None
    question = _question_text(text) or 'другое число'
    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: сумма двух чисел равна {_format_number(total_value)}, одно число равно {_format_number(known_value)}.',
        _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
        '1) Чтобы найти другое число, из суммы вычитаем известное число.',
        f'2) {_format_number(total_value)} - {_format_number(known_value)} = {_format_number(other_value)}.',
        f'Ответ: {_format_number(other_value)}',
        'Совет: если известны сумма и одно слагаемое, другое слагаемое находят вычитанием.',
    ])


def _try_difference_unknown_component_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    difference_match = re.search(r'разност(?:ь|и)\s*(?:двух\s+чисел\s*)?(?:равна|составляет|=)?\s*(\d+(?:[.,]\d+)?)', lower)
    if not difference_match:
        difference_match = re.search(r'разность\s*(\d+(?:[.,]\d+)?)', lower)
    difference_value = _to_fraction(difference_match.group(1)) if difference_match else None

    bigger_match = re.search(r'больш(?:ее|ое)\s+число\s*(?:равно|=)?\s*(\d+(?:[.,]\d+)?)', lower)
    smaller_match = re.search(r'меньш(?:ее|ое)\s+число\s*(?:равно|=)?\s*(\d+(?:[.,]\d+)?)', lower)
    minuend_match = re.search(r'уменьшаем(?:ое|ого)\s*(?:равно|=)?\s*(\d+(?:[.,]\d+)?)', lower)
    subtrahend_match = re.search(r'вычитаем(?:ое|ого)\s*(?:равно|=)?\s*(\d+(?:[.,]\d+)?)', lower)

    question = _question_text(text) or 'неизвестное число'

    if difference_value is not None and bigger_match and any(fragment in lower for fragment in ('меньшее число', 'найди меньшее')):
        bigger_value = _to_fraction(bigger_match.group(1))
        answer = bigger_value - difference_value
        if answer < 0:
            return None
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: большее число {_format_number(bigger_value)}, разность {_format_number(difference_value)}.',
            _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
            '1) Чтобы найти меньшее число, из большего числа вычитаем разность.',
            f'2) {_format_number(bigger_value)} - {_format_number(difference_value)} = {_format_number(answer)}.',
            f'Ответ: {_format_number(answer)}',
            'Совет: если известны большее число и разность, меньшее число находят вычитанием.',
        ])

    if difference_value is not None and smaller_match and any(fragment in lower for fragment in ('большее число', 'найди большее')):
        smaller_value = _to_fraction(smaller_match.group(1))
        answer = smaller_value + difference_value
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: меньшее число {_format_number(smaller_value)}, разность {_format_number(difference_value)}.',
            _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
            '1) Чтобы найти большее число, к меньшему числу прибавляем разность.',
            f'2) {_format_number(smaller_value)} + {_format_number(difference_value)} = {_format_number(answer)}.',
            f'Ответ: {_format_number(answer)}',
            'Совет: если известны меньшее число и разность, большее число находят сложением.',
        ])

    if difference_value is not None and minuend_match and 'вычитаем' in lower:
        minuend_value = _to_fraction(minuend_match.group(1))
        answer = minuend_value - difference_value
        if answer < 0:
            return None
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: уменьшаемое {_format_number(minuend_value)}, разность {_format_number(difference_value)}.',
            _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
            '1) Чтобы найти вычитаемое, из уменьшаемого вычитаем разность.',
            f'2) {_format_number(minuend_value)} - {_format_number(difference_value)} = {_format_number(answer)}.',
            f'Ответ: {_format_number(answer)}',
            'Совет: вычитаемое находят вычитанием разности из уменьшаемого.',
        ])

    if difference_value is not None and subtrahend_match and 'уменьшаем' in lower:
        subtrahend_value = _to_fraction(subtrahend_match.group(1))
        answer = subtrahend_value + difference_value
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: вычитаемое {_format_number(subtrahend_value)}, разность {_format_number(difference_value)}.',
            _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
            '1) Чтобы найти уменьшаемое, к вычитаемому прибавляем разность.',
            f'2) {_format_number(subtrahend_value)} + {_format_number(difference_value)} = {_format_number(answer)}.',
            f'Ответ: {_format_number(answer)}',
            'Совет: уменьшаемое находят сложением вычитаемого и разности.',
        ])

    return None


def _try_distribution_subset_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    match = re.search(
        r'(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+)\s+(?:раздали|разложили|распределили|поделили)\s+поровну\s+(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+)',
        lower,
    )
    if not match:
        return None
    total_value = _to_fraction(match.group(1))
    item_label = match.group(2)
    groups = _to_fraction(match.group(3))
    group_label = match.group(4)
    if groups == 0:
        return None
    each_group = total_value / groups
    question = _question_text(text) or 'сколько получил каждый'
    answer_label = _question_count_label(text) or item_label
    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: {_format_number(total_value)} {item_label} раздали поровну {_format_number(groups)} {group_label}.',
        _ensure_sentence(f'Что нужно найти: {question.rstrip("?.!")}'),
        '1) Чтобы узнать, сколько получил каждый, делим общее количество на число получателей.',
        f'2) {_format_number(total_value)} : {_format_number(groups)} = {_format_number(each_group)}.',
        f'Ответ: {_format_number(each_group)} {answer_label}'.strip(),
        'Совет: если предметы раздали поровну, дели общее количество на число одинаковых получателей.',
    ])


def _try_post_change_equal_parts_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    distribution_match = _find_post_change_distribution_anchor(lower)
    if distribution_match is None or 'поровну' not in lower[distribution_match.start():]:
        return None

    groups, group_label = _extract_distribution_group(lower, distribution_match.start())
    if groups is None or groups <= 0:
        return None

    question = (_question_text(text) or 'сколько получится в каждой части').rstrip('?.!').lower()
    answer_label = _guess_count_answer_label(text) or _question_count_label(text)

    quantities = [quantity for quantity in _extract_compound_quantities(text) if quantity['end'] <= distribution_match.start()]
    if len(quantities) >= 2 and len({quantity['group'] for quantity in quantities}) == 1:
        group = quantities[0]['group']
        base_unit = _choose_measure_base_unit(group, quantities)
        visible_units: list[str] = []
        for quantity in quantities:
            visible_units.extend(quantity['units'])

        initial = quantities[0]
        current_value = _quantity_value_in_unit(initial, base_unit)
        previous_end = initial['end']
        lines = [
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            _ensure_sentence(
                f'Что известно: сначала было {initial["pretty"]}, потом величину изменяли, а оставшееся количество разделили поровну на {_format_number(groups)} {group_label}'.rstrip()
            ),
            f'Что нужно найти: {question}.',
            f'1) Переводим начальную величину в {base_unit}: {initial["pretty"]} = {_format_number(current_value)} {base_unit}.',
        ]
        step_number = 2
        for quantity in quantities[1:]:
            sign = _infer_measure_change_sign(lower[:distribution_match.start()], quantity, previous_end)
            if sign is None:
                return None
            change_value = _quantity_value_in_unit(quantity, base_unit)
            lines.append(f'{step_number}) Переводим изменение в {base_unit}: {quantity["pretty"]} = {_format_number(change_value)} {base_unit}.')
            step_number += 1
            new_value = current_value + sign * change_value
            if new_value < 0:
                return None
            operation = '+' if sign > 0 else '-'
            reason = 'прибавляем изменение' if sign > 0 else 'находим остаток после изменения'
            lines.append(
                f'{step_number}) {reason}: {_format_number(current_value)} {operation} {_format_number(change_value)} = {_format_number(new_value)} {base_unit}.'
            )
            step_number += 1
            current_value = new_value
            previous_end = quantity['end']
        each_value = current_value / groups
        total_smallest_each = each_value * _MEASURE_GROUP_SCALES[group][base_unit]
        answer_text = _format_measure_total(total_smallest_each, group, visible_units)
        lines.append(
            f'{step_number}) Делим оставшееся количество поровну: {_format_number(current_value)} : {_format_number(groups)} = {_format_number(each_value)} {base_unit}.'
        )
        step_number += 1
        lines.append(f'{step_number}) Записываем ответ в удобных единицах: {_format_number(each_value)} {base_unit} = {answer_text}.')
        lines.append(f'Ответ: {answer_text}')
        lines.append('Совет: сначала найди, сколько осталось после изменений, а потом раздели остаток поровну.')
        return _join_lines(lines)

    prefix = lower[:distribution_match.start()]
    actions, matches = _extract_sequential_actions(prefix)
    if not actions or not matches:
        return None
    initial_prefix = prefix[:matches[0].start()]
    prefix_numbers = _plain_number_matches(initial_prefix)
    if not prefix_numbers:
        return None
    initial_value = _to_fraction(prefix_numbers[0].group(1))

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(
            f'Что известно: сначала было {_format_number(initial_value)}{(" " + answer_label) if answer_label else ""}, потом количество изменяли, а остаток разделили поровну на {_format_number(groups)} {group_label}'.rstrip()
        ),
        f'Что нужно найти: {question}.',
    ]

    current_value = initial_value
    step_number = 1
    for action in actions:
        new_value = current_value + action['sign'] * action['value']
        if new_value < 0:
            return None
        operation = '+' if action['sign'] > 0 else '-'
        reason = 'Прибавляем следующее изменение' if action['sign'] > 0 else 'Находим остаток после изменения'
        lines.append(
            f'{step_number}) {reason}: {_format_number(current_value)} {operation} {_format_number(action["value"])} = {_format_number(new_value)}.'
        )
        step_number += 1
        current_value = new_value

    each_value = current_value / groups
    lines.append(
        f'{step_number}) Делим оставшееся количество поровну: {_format_number(current_value)} : {_format_number(groups)} = {_format_number(each_value)}.'
    )
    answer_text = _format_number(each_value)
    if answer_label:
        answer_text += f' {answer_label}'
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: сначала найди, сколько осталось после изменений, а потом раздели остаток поровну.')
    return _join_lines(lines)


def _try_equal_parts_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()

    segment_match = re.search(
        r'(?:отрезок|лента|веревка|верёвка|доска|проволока|шнур)\w*(?:\s+длиной)?\s*(\d+(?:[.,]\d+)?)\s*(км|м|дм|см|мм)\b[^.!?]{0,120}?(?:разделили|разрезали|распилили|поделили)\s+на\s*(\d+(?:[.,]\d+)?)\s+равн\w+\s+част',
        lower,
    )
    if segment_match:
        total_value = _to_fraction(segment_match.group(1))
        unit = segment_match.group(2)
        parts_count = _to_fraction(segment_match.group(3))
        if parts_count == 0:
            return None
        part_value = total_value / parts_count
        lines = [
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            _ensure_sentence(f'Что известно: длина предмета {_format_number(total_value)} {unit}, его разделили на {_format_number(parts_count)} равные части'),
            _ensure_sentence(f'Что нужно найти: {(_question_text(text) or "длину одной части").rstrip("?.!")}'),
            _ensure_sentence(f'1) Чтобы найти длину одной равной части, делим всю длину на число частей: {_format_number(total_value)} : {_format_number(parts_count)} = {_format_number(part_value)} {unit}'),
            f'Ответ: {_format_number(part_value)} {unit}',
            'Совет: если предмет разделили на равные части, длину одной части находят делением.',
        ]
        return _join_lines(lines)

    grouped_match = re.search(
        r'(?:на|в)\s*(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+)[^.!?]{0,120}?(?:поровну\s+)?(?:расставили|разложили|раздали|распределили|разместили|развесили|разделили)\s*(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+)',
        lower,
    )
    if grouped_match:
        groups = _to_fraction(grouped_match.group(1))
        group_label = grouped_match.group(2)
        total_value = _to_fraction(grouped_match.group(3))
        item_label = _question_count_label(text) or grouped_match.group(4)
        if groups == 0:
            return None
        each_group = total_value / groups
        lines = [
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            _ensure_sentence(f'Что известно: {_format_number(total_value)} {item_label} распределили поровну на {_format_number(groups)} {group_label}'),
            _ensure_sentence(f'Что нужно найти: {(_question_text(text) or "сколько будет в каждой группе").rstrip("?.!")}'),
            _ensure_sentence(f'1) Чтобы узнать, сколько будет в одной группе, делим общее количество на число групп: {_format_number(total_value)} : {_format_number(groups)} = {_format_number(each_group)}'),
            f'Ответ: {_format_number(each_group)} {item_label}'.strip(),
            'Совет: когда предметы распределяют поровну, общее количество делят на число одинаковых групп.',
        ]
        return _join_lines(lines)

    return None
