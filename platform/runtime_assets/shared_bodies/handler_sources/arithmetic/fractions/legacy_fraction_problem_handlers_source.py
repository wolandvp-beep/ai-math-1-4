from __future__ import annotations

"""Statically materialized handler source for legacy_fraction_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_fraction_related_subject_problem(raw_text: str) -> Optional[str]:
    parsed = _parse_fraction_related_subject_problem(raw_text)
    if not parsed:
        return None

    text = parsed['text']
    lower = parsed['lower']
    question = parsed['question']
    fraction_value = parsed['fraction']
    fraction_display = parsed['fraction_display']
    answer_label = parsed['answer_label']
    base_name = parsed['base_name']
    relation_name = parsed['relation_name']
    current_values = [parsed['base_value'], parsed['relation_value']]
    subject_entries = [
        {'keys': {parsed['base_key']}, 'label': base_name},
        {'keys': {parsed['relation_key']}, 'label': relation_name},
    ]

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(
            f'Что известно: у {base_name} было {_format_number(current_values[0])} {answer_label}, '
            f'а у {relation_name} — {fraction_display} от количества {base_name}'
        ),
        _ensure_sentence(f'Что нужно найти: {(question or "нужное количество").rstrip("?.!")}'),
    ]

    step_number = 1
    numerator = fraction_value.numerator
    denominator = fraction_value.denominator

    if parsed['mode'] == 'forward':
        one_share = current_values[0] / denominator
        lines.append(
            f'{step_number}) Находим одну долю количества у {base_name}: '
            f'{_format_number(current_values[0])} : {_format_number(denominator)} = {_format_number(one_share)} {answer_label}.'
        )
        step_number += 1
        if numerator == 1:
            lines.append(
                f'{step_number}) Значит, у {relation_name} {_format_number(one_share)} {answer_label}.'
            )
        else:
            relation_value = one_share * numerator
            lines.append(
                f'{step_number}) Находим {fraction_display} от количества у {base_name}: '
                f'{_format_number(one_share)} × {_format_number(numerator)} = {_format_number(relation_value)} {answer_label}.'
            )
            current_values[1] = relation_value
        step_number += 1
    else:
        if numerator == 1:
            lines.append(
                f'{step_number}) Так как {_format_number(current_values[1])} {answer_label} — это {fraction_display} от количества у {base_name}, '
                f'находим всё количество: {_format_number(current_values[1])} × {_format_number(denominator)} = {_format_number(current_values[0])} {answer_label}.'
            )
            step_number += 1
        else:
            one_share = current_values[1] / numerator
            lines.append(
                f'{step_number}) Находим одну долю количества у {base_name}: '
                f'{_format_number(current_values[1])} : {_format_number(numerator)} = {_format_number(one_share)} {answer_label}.'
            )
            step_number += 1
            lines.append(
                f'{step_number}) Находим всё количество у {base_name}: '
                f'{_format_number(one_share)} × {_format_number(denominator)} = {_format_number(current_values[0])} {answer_label}.'
            )
            step_number += 1

    actions, matches = _extract_sequential_actions(lower)
    filtered_actions = [
        (action, match)
        for action, match in zip(actions, matches)
        if match.start() > parsed['fraction_end']
    ]
    for action, match in filtered_actions:
        transfer = _extract_dual_subject_transfer_action(lower, match, subject_entries, action['value'])
        if transfer:
            step_number = _apply_dual_subject_transfer_step(lines, step_number, current_values, transfer, subject_entries, answer_label)
            if step_number is None:
                return None
            continue
        target_index = _detect_dual_subject_action_index(lower, match, subject_entries)
        if target_index is None:
            return None
        old_value = current_values[target_index]
        change_value = action['value']
        new_value = old_value + action['sign'] * change_value
        if new_value < 0:
            return None
        operation = '+' if action['sign'] > 0 else '-'
        lines.append(
            f'{step_number}) Изменяем количество у {subject_entries[target_index]["label"]}: '
            f'{_format_number(old_value)} {operation} {_format_number(change_value)} = {_format_number(new_value)} {answer_label}.'
        )
        current_values[target_index] = new_value
        step_number += 1

    order = _question_subject_order(question, subject_entries)
    relation_word = 'меньше' if 'меньше' in question else 'больше' if 'больше' in question else ''

    if 'вместе' in question or 'всего' in question:
        total_value = current_values[0] + current_values[1]
        lines.append(
            f'{step_number}) Находим, сколько стало вместе: '
            f'{_format_number(current_values[0])} + {_format_number(current_values[1])} = {_format_number(total_value)} {answer_label}.'
        )
        lines.append(f'Ответ: {_format_number(total_value)} {answer_label}')
        lines.append('Совет: если одно количество выражено дробью от другого, сначала находят оба количества, а потом складывают или сравнивают их.')
        return _join_lines(lines)

    if len(order) >= 2:
        first_index, second_index = order[0], order[1]
    elif len(order) == 1:
        first_index, second_index = order[0], 1 - order[0]
    else:
        first_index, second_index = 0, 1

    first_value = current_values[first_index]
    second_value = current_values[second_index]

    if 'во сколько раз' in question:
        if relation_word == 'меньше':
            if first_value <= 0 or second_value < first_value:
                return None
            numerator_value, denominator_value = second_value, first_value
        else:
            if second_value <= 0:
                return None
            if relation_word == 'больше' and first_value < second_value:
                return None
            numerator_value, denominator_value = first_value, second_value
        ratio_value = numerator_value / denominator_value
        lines.append(
            f'{step_number}) Для кратного сравнения делим одно количество на другое: '
            f'{_format_number(numerator_value)} : {_format_number(denominator_value)} = {_format_number(ratio_value)}.'
        )
        lines.append(f'Ответ: в {_format_number(ratio_value)} раза')
        lines.append('Совет: чтобы узнать, во сколько раз одно количество больше или меньше другого, нужно разделить большее количество на меньшее.')
        return _join_lines(lines)

    if 'на сколько' in question:
        if relation_word == 'меньше':
            if second_value < first_value:
                return None
            bigger_value, smaller_value = second_value, first_value
        elif relation_word == 'больше':
            if first_value < second_value:
                return None
            bigger_value, smaller_value = first_value, second_value
        else:
            bigger_value, smaller_value = max(first_value, second_value), min(first_value, second_value)
        difference_value = bigger_value - smaller_value
        lines.append(
            f'{step_number}) Сравниваем количества: '
            f'{_format_number(bigger_value)} - {_format_number(smaller_value)} = {_format_number(difference_value)} {answer_label}.'
        )
        lines.append(f'Ответ: на {_format_number(difference_value)} {answer_label}')
        lines.append('Совет: сначала найди каждое количество, а потом вычти меньшее из большего.')
        return _join_lines(lines)

    target_index = order[0] if order else 1
    lines.append(
        f'{step_number}) Мы уже нашли количество у {subject_entries[target_index]["label"]}: '
        f'{_format_number(current_values[target_index])} {answer_label}.'
    )
    lines.append(f'Ответ: {_format_number(current_values[target_index])} {answer_label}')
    lines.append('Совет: если одно количество составляет дробь от другого, сначала находят одну долю или всё количество, а потом отвечают на вопрос задачи.')
    return _join_lines(lines)


def _try_fraction_comparison_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _parse_fraction_related_subject_problem(raw_text):
        return None
    lower = text.lower().replace('ё', 'е')
    fractions = _extract_text_fractions(text)
    if len(fractions) < 2:
        return None

    question = _question_text(text).lower().replace('ё', 'е')
    if not any(marker in lower or marker in question for marker in (
        'сравни дроб', 'что больше', 'что меньше', 'какая дробь больше', 'какая дробь меньше', 'на сколько'
    )):
        return None

    first = fractions[0]['value']
    second = fractions[1]['value']
    if first <= 0 or second <= 0:
        return None

    common_denominator = math.lcm(first.denominator, second.denominator)
    first_common = first.numerator * (common_denominator // first.denominator)
    second_common = second.numerator * (common_denominator // second.denominator)
    first_text = _format_fraction_value(first)
    second_text = _format_fraction_value(second)

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: нужно сравнить дроби {first_text} и {second_text}.',
    ]

    if 'на сколько' in question:
        difference = abs(first - second)
        difference_common = abs(first_common - second_common)
        answer_label = _fraction_answer_label(text, _extract_word_after(text, fractions[0]['end']))
        lines.append(f'Что нужно найти: {question.rstrip("?.!") or "на сколько одна дробь больше или меньше другой"}.')
        lines.append(
            f'1) Приводим дроби к общему знаменателю {common_denominator}: '
            f'{first_text} = {first_common}/{common_denominator}, {second_text} = {second_common}/{common_denominator}.'
        )
        lines.append(
            f'2) Находим разность: {max(first_common, second_common)}/{common_denominator} - '
            f'{min(first_common, second_common)}/{common_denominator} = '
            f'{difference_common}/{common_denominator} = {_format_fraction_value(difference)}.'
        )
        lines.append(f'Ответ: на {_format_fraction_value(difference)} {answer_label}'.strip())
        lines.append('Совет: чтобы узнать, на сколько одна дробь больше другой, удобно привести дроби к общему знаменателю и вычесть их.')
        return _join_lines(lines)

    relation = '='
    relation_words = 'дроби равны'
    answer_text = f'{first_text} = {second_text}'
    if first > second:
        relation = '>'
        relation_words = f'{first_common} > {second_common}'
        answer_text = f'{first_text} > {second_text}'
    elif first < second:
        relation = '<'
        relation_words = f'{first_common} < {second_common}'
        answer_text = f'{first_text} < {second_text}'

    lines.append(f'Что нужно найти: {question.rstrip("?.!") or "какая дробь больше"}.')
    lines.append(
        f'1) Приводим дроби к общему знаменателю {common_denominator}: '
        f'{first_text} = {first_common}/{common_denominator}, {second_text} = {second_common}/{common_denominator}.'
    )
    lines.append(
        f'2) При одинаковом знаменателе сравниваем числители: {relation_words}. Значит, {answer_text}.'
    )
    if 'что больше' in question or 'какая дробь больше' in question:
        bigger = first_text if first >= second else second_text
        lines.append(f'Ответ: больше {bigger}')
    elif 'что меньше' in question or 'какая дробь меньше' in question:
        smaller = first_text if first <= second else second_text
        lines.append(f'Ответ: меньше {smaller}')
    else:
        lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: чтобы сравнить дроби, можно привести их к общему знаменателю и сравнить числители.')
    return _join_lines(lines)


def _try_fraction_remainder_of_whole_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _parse_fraction_related_subject_problem(raw_text):
        return None
    lower = text.lower().replace('ё', 'е')
    fractions = _extract_text_fractions(text)
    if not fractions:
        return None
    if any('оставш' in lower[max(0, item['start'] - 12): item['end'] + 18] for item in fractions[1:]):
        return None
    if any(marker in lower for marker in _FRACTION_CHANGE_ACTION_HINTS):
        return None
    question = _question_text(text).lower().replace('ё', 'е')
    if len(fractions) == 1:
        if 'остальн' not in lower:
            return None
        if not any(marker in question for marker in ('мальчик', 'остальн', 'осталось', 'другого')):
            return None
    else:
        if not any(marker in question for marker in ('остальн', 'осталось', 'другого')):
            return None

    plain_matches = _plain_number_matches(lower)
    if not plain_matches:
        return None
    first_fraction_start = fractions[0]['start']
    total_match = next((match for match in plain_matches if match.start() < first_fraction_start), None)
    if total_match is None:
        return None
    total_value = _to_fraction(total_match.group(1))
    if total_value <= 0:
        return None

    initial_label = _extract_word_after(text, total_match.end()) or _fraction_answer_label(text, 'предметов')
    parts: list[Fraction] = []
    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: всего было {_format_number(total_value)} {initial_label}.',
        f'Что нужно найти: {question.rstrip("?.!") or "сколько осталось после известных долей"}.',
    ]
    step_number = 1
    for item in fractions:
        share_value = total_value / item['value'].denominator
        part_value = share_value * item['value'].numerator
        part_text = _format_fraction_value(item['value'])
        lines.append(
            f'{step_number}) Находим одну долю: {_format_number(total_value)} : {_format_number(item["value"].denominator)} = {_format_number(share_value)}.'
        )
        step_number += 1
        if item['value'].numerator == 1:
            lines.append(
                f'{step_number}) Находим {part_text} от всего количества: {_format_number(share_value)} × 1 = {_format_number(part_value)}.'
            )
        else:
            lines.append(
                f'{step_number}) Находим {part_text} от всего количества: '
                f'{_format_number(share_value)} × {_format_number(item["value"].numerator)} = {_format_number(part_value)}.'
            )
        step_number += 1
        parts.append(part_value)

    distributed_total = sum(parts, Fraction(0))
    if distributed_total > total_value:
        return None
    if len(parts) > 1:
        distribution_sum = ' + '.join(_format_number(value) for value in parts)
        lines.append(
            f'{step_number}) Находим, сколько уже распределили: {distribution_sum} = {_format_number(distributed_total)}.'
        )
        step_number += 1
    remainder_value = total_value - distributed_total
    answer_label = _fraction_answer_label(text, initial_label)
    lines.append(
        f'{step_number}) Находим остаток: {_format_number(total_value)} - {_format_number(distributed_total)} = {_format_number(remainder_value)}.'
    )
    lines.append(f'Ответ: {_format_number(remainder_value)} {answer_label}'.strip())
    lines.append('Совет: если известны части от всего количества, сначала находят каждую часть, потом складывают их и вычитают из целого.')
    return _join_lines(lines)


def _try_fraction_of_remainder_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _parse_fraction_related_subject_problem(raw_text):
        return None
    lower = text.lower().replace('ё', 'е')
    fractions = _extract_text_fractions(text)
    if len(fractions) < 2:
        return None

    second_context = lower[max(0, fractions[1]['start'] - 18): fractions[1]['end'] + 18]
    if 'оставш' not in second_context:
        return None

    plain_matches = _plain_number_matches(lower)
    if not plain_matches:
        return None
    total_match = next((match for match in plain_matches if match.start() < fractions[0]['start']), None)
    if total_match is None:
        return None
    total_value = _to_fraction(total_match.group(1))
    if total_value <= 0:
        return None

    first_fraction = fractions[0]['value']
    second_fraction = fractions[1]['value']
    first_share = total_value / first_fraction.denominator
    first_part = first_share * first_fraction.numerator
    first_remainder = total_value - first_part
    if first_remainder < 0:
        return None
    second_share = first_remainder / second_fraction.denominator
    second_part = second_share * second_fraction.numerator
    final_remainder = first_remainder - second_part
    if final_remainder < 0:
        return None

    question = _question_text(text).lower().replace('ё', 'е')
    answer_value = final_remainder
    if any(marker in question for marker in ('сколько съел', 'сколько съела', 'сколько съели', 'сколько откусил', 'сколько откусила')):
        answer_value = second_part
    answer_label = _fraction_answer_label(text, _extract_word_after(text, total_match.end()) or 'предметов')

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: сначала было {_format_number(total_value)} {answer_label}, сначала убрали {_format_fraction_value(first_fraction)} от всего количества, а потом убрали {_format_fraction_value(second_fraction)} от оставшегося.',
        f'Что нужно найти: {question.rstrip("?.!") or "сколько осталось после двух изменений"}.',
        f'1) Находим {_format_fraction_value(first_fraction)} от всего количества: {_format_number(total_value)} : {_format_number(first_fraction.denominator)} = {_format_number(first_share)}, затем {_format_number(first_share)} × {_format_number(first_fraction.numerator)} = {_format_number(first_part)}.',
        f'2) После первого изменения осталось: {_format_number(total_value)} - {_format_number(first_part)} = {_format_number(first_remainder)}.',
        f'3) Находим {_format_fraction_value(second_fraction)} от оставшегося количества: {_format_number(first_remainder)} : {_format_number(second_fraction.denominator)} = {_format_number(second_share)}, затем {_format_number(second_share)} × {_format_number(second_fraction.numerator)} = {_format_number(second_part)}.',
        f'4) После второго изменения осталось: {_format_number(first_remainder)} - {_format_number(second_part)} = {_format_number(final_remainder)}.',
        f'Ответ: {_format_number(answer_value)} {answer_label}'.strip(),
        'Совет: если вторая дробь относится к оставшейся части, сначала находят остаток после первого действия, а уже потом берут дробь от остатка.',
    ]
    return _join_lines(lines)


def _try_fraction_relative_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _parse_fraction_related_subject_problem(raw_text):
        return None
    lower = text.lower().replace('ё', 'е')
    if ' на ' not in lower or not any(word in lower for word in ('меньше', 'больше')):
        return None
    fractions = _extract_text_fractions(text)
    if not fractions:
        return None

    relation_fraction: Optional[dict[str, Any]] = None
    relation_kind = ''
    for item in fractions:
        before = lower[max(0, item['start'] - 6):item['start']]
        after = lower[item['end']:item['end'] + 12]
        if 'на' in before and 'меньше' in after:
            relation_fraction = item
            relation_kind = 'меньше'
            break
        if 'на' in before and 'больше' in after:
            relation_fraction = item
            relation_kind = 'больше'
            break
    if relation_fraction is None:
        return None

    plain_matches = _plain_number_matches(lower)
    base_match = next((match for match in plain_matches if match.start() < relation_fraction['start']), None)
    if base_match is None:
        return None
    base_value = _to_fraction(base_match.group(1))
    if base_value <= 0:
        return None

    fraction_value = relation_fraction['value']
    fraction_part = base_value / fraction_value.denominator * fraction_value.numerator
    if relation_kind == 'меньше':
        answer_value = base_value - fraction_part
        operation = '-'
    else:
        answer_value = base_value + fraction_part
        operation = '+'
    if answer_value < 0:
        return None

    question = _question_text(text).lower().replace('ё', 'е')
    answer_label = _fraction_answer_label(text, _extract_word_after(text, base_match.end()) or 'единиц')
    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: одно количество равно {_format_number(base_value)} {answer_label}, другое количество на {_format_fraction_value(fraction_value)} {relation_kind}.',
        f'Что нужно найти: {question.rstrip("?.!") or "второе количество"}.',
        f'1) Находим {_format_fraction_value(fraction_value)} от {_format_number(base_value)}: {_format_number(base_value)} : {_format_number(fraction_value.denominator)} = {_format_number(base_value / fraction_value.denominator)}, затем {_format_number(base_value / fraction_value.denominator)} × {_format_number(fraction_value.numerator)} = {_format_number(fraction_part)}.',
        f'2) Так как второе количество на {_format_fraction_value(fraction_value)} {relation_kind}, получаем: {_format_number(base_value)} {operation} {_format_number(fraction_part)} = {_format_number(answer_value)}.',
        f'Ответ: {_format_number(answer_value)} {answer_label}'.strip(),
        'Совет: если сказано “на дробь меньше или больше”, сначала находят эту дробь от известного количества, а потом вычитают или прибавляют её.',
    ]
    return _join_lines(lines)


def _try_fraction_then_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _parse_fraction_related_subject_problem(raw_text):
        return None
    lower = text.lower().replace('ё', 'е')
    fraction_match = _FRACTION_RE.search(lower)
    if not fraction_match:
        return None
    if not any(marker in lower[fraction_match.end():] for marker in ('потом', 'затем', 'после этого', 'ещё', 'еще')):
        return None

    numerator = _to_fraction(fraction_match.group(1))
    denominator = _to_fraction(fraction_match.group(2))
    if numerator <= 0 or denominator <= 0 or numerator >= denominator:
        return None

    plain_matches = _plain_number_matches(lower)
    total_match = next((match for match in plain_matches if match.start() < fraction_match.start()), None)
    if total_match is None:
        return None
    total_value = _to_fraction(total_match.group(1))
    one_share = total_value / denominator
    fraction_value = one_share * numerator

    punctuation_match = re.search(r'[,.!?;]', lower[fraction_match.end():])
    tail_start = fraction_match.end() + (punctuation_match.start() if punctuation_match else 0)
    tail = lower[tail_start:]
    actions, _ = _extract_sequential_actions(tail)
    if not actions:
        return None

    current_value = total_value - fraction_value
    if current_value < 0:
        return None

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: сначала было {_format_number(total_value)} {(_question_count_label(text) or _extract_word_after(text, total_match.end())).strip()}, потом убрали {fraction_match.group(1)}/{fraction_match.group(2)} этого количества'),
        _ensure_sentence(f'Что нужно найти: {(_question_text(text) or "итог после всех изменений").rstrip("?.!").lower()}'),
        _ensure_sentence(f'1) Находим одну долю: {_format_number(total_value)} : {_format_number(denominator)} = {_format_number(one_share)}'),
        _ensure_sentence(f'2) Находим {_format_number(numerator)}/{_format_number(denominator)} от всего количества: {_format_number(one_share)} × {_format_number(numerator)} = {_format_number(fraction_value)}'),
        _ensure_sentence(f'3) После этого изменения осталось: {_format_number(total_value)} - {_format_number(fraction_value)} = {_format_number(current_value)}'),
    ]
    step_number = 4
    for action in actions:
        new_value = current_value + action['sign'] * action['value']
        if new_value < 0:
            return None
        op = '+' if action['sign'] > 0 else '-'
        lines.append(_ensure_sentence(f'{step_number}) Выполняем следующее изменение: {_format_number(current_value)} {op} {_format_number(action["value"])} = {_format_number(new_value)}'))
        current_value = new_value
        step_number += 1
    answer_label = _question_count_label(text) or _extract_word_after(text, total_match.end())
    lines.append(f'Ответ: {_format_number(current_value)} {answer_label}'.strip())
    lines.append('Совет: в комбинированной задаче сначала находят долю, потом выполняют остальные изменения по порядку.')
    return _join_lines(lines)


def _try_number_by_fraction(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    match = re.search(
        r'(\d+)\s*/\s*(\d+)\s*(?:этого\s+|данного\s+)?числа\s*(?:равн(?:а|ы)|составля(?:ет|ют)|=|это)\s*(\d+(?:[.,]\d+)?)',
        lower,
    )
    if not match:
        match = re.search(
            r'(\d+)\s*/\s*(\d+)\s*от\s*числа\s*(?:равн(?:а|ы)|составля(?:ет|ют)|=|это)\s*(\d+(?:[.,]\d+)?)',
            lower,
        )
    if not match:
        return None

    numerator = _to_fraction(match.group(1))
    denominator = _to_fraction(match.group(2))
    part_value = _to_fraction(match.group(3))
    if numerator <= 0 or denominator <= 0:
        return None

    if numerator == 1:
        whole = part_value * denominator
        lines = [
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: 1/{_format_number(denominator)} числа равна {_format_number(part_value)}.',
            'Что нужно найти: всё число.',
            f'1) 1/{_format_number(denominator)} числа — это одна из {_format_number(denominator)} равных частей целого.',
            f'2) Чтобы найти всё число, умножаем значение одной части на {_format_number(denominator)}: {_format_number(part_value)} × {_format_number(denominator)} = {_format_number(whole)}.',
            f'Ответ: {_format_number(whole)}',
            'Совет: если известна одна доля числа, всё число находят умножением на количество таких долей.',
        ]
        return _join_lines(lines)

    one_share = part_value / numerator
    whole = one_share * denominator
    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: {_format_number(numerator)}/{_format_number(denominator)} числа равны {_format_number(part_value)}.',
        'Что нужно найти: всё число.',
        f'1) Сначала находим одну долю: {_format_number(part_value)} : {_format_number(numerator)} = {_format_number(one_share)}.',
        f'2) Теперь находим всё число: {_format_number(one_share)} × {_format_number(denominator)} = {_format_number(whole)}.',
        f'Ответ: {_format_number(whole)}',
        'Совет: если известны несколько одинаковых долей числа, сначала находят одну долю, а потом всё число.',
    ]
    return _join_lines(lines)


def _try_fraction_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _parse_fraction_related_subject_problem(raw_text):
        return None
    lower = text.lower().replace('ё', 'е')
    fraction_match = _FRACTION_RE.search(lower)
    if not fraction_match:
        return None
    if any(marker in lower[fraction_match.end():] for marker in ('потом', 'затем', 'после этого', 'ещё', 'еще')):
        return None

    numerator = _to_fraction(fraction_match.group(1))
    denominator = _to_fraction(fraction_match.group(2))
    if numerator <= 0 or denominator <= 0 or numerator >= denominator:
        return None

    question = _question_text(text).lower()
    plain_matches = _plain_number_matches(lower)
    if not plain_matches:
        return None

    total_match = next((match for match in plain_matches if match.start() < fraction_match.start()), None)
    if total_match:
        total_value = _to_fraction(total_match.group(1))
        initial_label = _extract_word_after(text, total_match.end())
        fraction_label = _extract_word_after(text, fraction_match.end())
        total_label = initial_label or _question_count_label(text) or fraction_label
        one_share = total_value / denominator
        part_value = one_share * numerator
        remainder_value = total_value - part_value
        ask_remainder = 'остал' in question or 'стало' in question

        steps = [
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            _ensure_sentence(
                f'Что известно: всего было {_format_number(total_value)} {initial_label or total_label}, взяли {fraction_match.group(1)}/{fraction_match.group(2)} этого количества'
            ),
            _ensure_sentence(
                f'Что нужно найти: {question.rstrip("?.!") or "нужную часть"}'
            ),
            _ensure_sentence(
                f'1) Находим одну долю: {_format_number(total_value)} : {_format_number(denominator)} = {_format_number(one_share)}'
            ),
        ]
        if numerator == 1:
            steps.append(_ensure_sentence(f'2) Одна такая доля равна {_format_number(part_value)}'))
        else:
            steps.append(
                _ensure_sentence(
                    f'2) Находим {_format_number(numerator)} такие доли: {_format_number(one_share)} × {_format_number(numerator)} = {_format_number(part_value)}'
                )
            )
        if ask_remainder:
            steps.append(
                _ensure_sentence(
                    f'3) Находим остаток: {_format_number(total_value)} - {_format_number(part_value)} = {_format_number(remainder_value)}'
                )
            )
            answer_value = remainder_value
            answer_label = initial_label or total_label or fraction_label
        else:
            answer_value = part_value
            answer_label = _question_count_label(text) or fraction_label or initial_label or total_label
        steps.append(f'Ответ: {_format_number(answer_value)} {answer_label}'.strip())
        steps.append('Совет: если известна доля от целого, сначала находят одну долю, а потом нужное количество долей или остаток.')
        return _join_lines(steps)

    remaining_match = next((match for match in plain_matches if match.start() > fraction_match.end()), None)
    if remaining_match and 'остал' in lower:
        remaining_value = _to_fraction(remaining_match.group(1))
        remaining_label = _question_count_label(text) or _extract_word_after(text, remaining_match.end())
        remaining_shares = denominator - numerator
        if remaining_shares <= 0:
            return None
        one_share = remaining_value / remaining_shares
        whole_value = one_share * denominator
        removed_value = one_share * numerator
        ask_removed = any(fragment in question for fragment in ('сколько съели', 'сколько отдали', 'сколько раздали', 'сколько продали', 'сколько использовали'))
        answer_value = removed_value if ask_removed else whole_value
        steps = [
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            _ensure_sentence(
                f'Что известно: после того как убрали {fraction_match.group(1)}/{fraction_match.group(2)} целого, осталось {_format_number(remaining_value)} {remaining_label}'
            ),
            _ensure_sentence(
                f'Что нужно найти: {question.rstrip("?.!") or "целое количество"}'
            ),
            _ensure_sentence(
                f'1) Если убрали {_format_number(numerator)}/{_format_number(denominator)}, то осталось {_format_number(remaining_shares)}/{_format_number(denominator)} целого'
            ),
            _ensure_sentence(
                f'2) Находим одну долю: {_format_number(remaining_value)} : {_format_number(remaining_shares)} = {_format_number(one_share)}'
            ),
        ]
        if ask_removed:
            steps.append(
                _ensure_sentence(
                    f'3) Находим убранную часть: {_format_number(one_share)} × {_format_number(numerator)} = {_format_number(removed_value)}'
                )
            )
        else:
            steps.append(
                _ensure_sentence(
                    f'3) Находим всё целое: {_format_number(one_share)} × {_format_number(denominator)} = {_format_number(whole_value)}'
                )
            )
        answer_label = _question_count_label(text) or remaining_label
        steps.append(f'Ответ: {_format_number(answer_value)} {answer_label}'.strip())
        steps.append('Совет: если известен остаток после удаления доли, сначала находят, какая доля осталась, потом одну долю и всё целое.')
        return _join_lines(steps)

    return None
