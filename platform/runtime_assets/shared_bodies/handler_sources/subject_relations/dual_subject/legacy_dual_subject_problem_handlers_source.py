from __future__ import annotations

"""Statically materialized handler source for legacy_dual_subject_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_dual_subject_money_after_changes_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if not _looks_like_dual_subject_money_after_changes_problem(text):
        return None

    lower = text.lower().replace('ё', 'е')
    parsing_lower = _replace_small_number_words(lower)
    question = _question_text(text).lower().replace('ё', 'е')
    matches = list(_ACTION_VERB_RE.finditer(parsing_lower))
    if not matches:
        return None
    prefix = parsing_lower[:matches[0].start()]
    number_matches = list(re.finditer(r'(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE, prefix, re.IGNORECASE))
    if len(number_matches) < 2:
        return None
    subject_entries = _extract_dual_subject_entries(prefix, number_matches)
    if len(subject_entries) < 2:
        return None
    subject_entries = subject_entries[:2]
    initial_values = [_to_fraction(number_matches[0].group(1)), _to_fraction(number_matches[1].group(1))]

    current_values = initial_values[:]
    fragments = _split_money_action_fragments(text[matches[0].start():])
    if not fragments:
        return None
    prefix_context_indexes = _subject_indexes_in_segment(prefix[-50:], subject_entries)
    current_subject_index: Optional[int] = prefix_context_indexes[-1] if prefix_context_indexes else None

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(
            f'Что известно: сначала у {subject_entries[0]["label"]} было {_format_number(initial_values[0])} руб, '
            f'а у {subject_entries[1]["label"]} — {_format_number(initial_values[1])} руб'
        ),
        _ensure_sentence(f'Что нужно найти: {(question or "что стало после изменений").rstrip("?.!")}'),
    ]
    step_number = 1

    for fragment in fragments:
        clause_text = _normalize_space(fragment)
        if not clause_text:
            continue
        clause_lower = clause_text.lower().replace('ё', 'е')
        parsing_clause = _replace_small_number_words(clause_lower)
        if '?' in fragment and ('сколько' in clause_lower or 'на сколько' in clause_lower or 'во сколько' in clause_lower):
            continue

        clause_indexes: list[int] = []
        for index in _subject_indexes_in_segment(parsing_clause, subject_entries):
            if index not in clause_indexes:
                clause_indexes.append(index)
        previous_context_index = current_subject_index
        explicit_subject = clause_indexes[0] if len(clause_indexes) == 1 else None
        if explicit_subject is not None:
            current_subject_index = explicit_subject

        purchases = _extract_purchase_entries_for_local_solver(parsing_clause)
        if purchases:
            target_index = explicit_subject if explicit_subject is not None else current_subject_index
            if target_index is None:
                return None
            item_costs: list[Fraction] = []
            for item in purchases:
                cost = item['quantity'] * item['unit_price']
                item_costs.append(cost)
                item_phrase = item['item_label'] if item['quantity'] == 1 else f'{_format_number(item["quantity"])} {item["item_label"]}'
                lines.append(
                    f'{step_number}) Находим стоимость покупки у {subject_entries[target_index]["label"]}: '
                    f'{item_phrase} = {_format_number(item["quantity"])} × {_format_number(item["unit_price"])} = {_format_number(cost)} руб.'
                )
                step_number += 1
            total_cost = sum(item_costs, Fraction(0))
            if len(item_costs) > 1:
                lines.append(
                    f'{step_number}) Складываем все покупки у {subject_entries[target_index]["label"]}: '
                    f'{" + ".join(_format_number(cost) for cost in item_costs)} = {_format_number(total_cost)} руб.'
                )
                step_number += 1
            previous_value = current_values[target_index]
            new_value = previous_value - total_cost
            if new_value < 0:
                return None
            lines.append(
                f'{step_number}) Вычитаем стоимость покупок из денег у {subject_entries[target_index]["label"]}: '
                f'{_format_number(previous_value)} - {_format_number(total_cost)} = {_format_number(new_value)} руб.'
            )
            current_values[target_index] = new_value
            step_number += 1
            continue

        clause_actions, clause_matches = _extract_sequential_actions(parsing_clause)
        if not clause_actions or not clause_matches:
            continue
        for action, match in zip(clause_actions, clause_matches):
            normalized_verb = action['verb'].lower().replace('ё', 'е')
            if normalized_verb in _AMBIGUOUS_ACTION_VERBS:
                continue
            transfer = _extract_dual_subject_transfer_action(parsing_clause, match, subject_entries, action['value'])
            explicit_after_verb = explicit_subject is not None and explicit_subject in _subject_indexes_in_segment(parsing_clause[match.end():], subject_entries)
            if transfer is None and explicit_after_verb and normalized_verb in {item.replace('ё', 'е') for item in _TRANSFER_ACTION_VERBS} and previous_context_index is not None and explicit_subject is not None and explicit_subject != previous_context_index:
                transfer = {
                    'source_index': previous_context_index,
                    'target_index': explicit_subject,
                    'value': action['value'],
                    'verb': normalized_verb,
                }
            if transfer:
                step_number = _apply_dual_subject_transfer_step(lines, step_number, current_values, transfer, subject_entries, 'руб')
                if step_number is None:
                    return None
                current_subject_index = transfer['source_index']
                continue
            target_index = _detect_dual_subject_action_index(parsing_clause, match, subject_entries)
            if target_index is None:
                target_index = explicit_subject if explicit_subject is not None else current_subject_index
            if target_index is None:
                return None
            previous_value = current_values[target_index]
            new_value = previous_value + action['sign'] * action['value']
            if new_value < 0:
                return None
            operation = '+' if action['sign'] > 0 else '-'
            lines.append(
                f'{step_number}) Изменяем деньги у {subject_entries[target_index]["label"]}: '
                f'{_format_number(previous_value)} {operation} {_format_number(action["value"])} = {_format_number(new_value)} руб.'
            )
            current_values[target_index] = new_value
            step_number += 1

    mode = _direct_dual_subject_question_mode(question, subject_entries)
    order = _question_subject_order(question, subject_entries)
    relation_word = 'меньше' if 'меньше' in question else 'больше' if 'больше' in question else ''

    if mode == 'both':
        if len(order) >= 2:
            first_index, second_index = order[:2]
        else:
            first_index, second_index = 0, 1
        lines.append(
            f'{step_number}) Теперь знаем новые суммы денег: '
            f'у {subject_entries[first_index]["label"]} — {_format_number(current_values[first_index])} руб, '
            f'у {subject_entries[second_index]["label"]} — {_format_number(current_values[second_index])} руб.'
        )
        lines.append(
            f'Ответ: у {subject_entries[first_index]["label"]} — {_format_number(current_values[first_index])} руб, '
            f'у {subject_entries[second_index]["label"]} — {_format_number(current_values[second_index])} руб'
        )
        lines.append('Совет: если деньги изменялись у двух людей, сначала найди новую сумму денег у каждого, а потом отвечай на вопрос.')
        return _join_lines(lines)

    if mode == 'total':
        total_value = current_values[0] + current_values[1]
        lines.append(
            f'{step_number}) Находим, сколько стало вместе: '
            f'{_format_number(current_values[0])} + {_format_number(current_values[1])} = {_format_number(total_value)} руб.'
        )
        lines.append(f'Ответ: {_format_number(total_value)} руб')
        lines.append('Совет: если деньги изменялись у двух людей, сначала найди новую сумму у каждого, а потом сложи результаты.')
        return _join_lines(lines)

    if 'во сколько раз' in question:
        if len(order) >= 2:
            first_index, second_index = order[:2]
        else:
            first_index, second_index = 0, 1
        first_value = current_values[first_index]
        second_value = current_values[second_index]
        if relation_word == 'меньше':
            if first_value <= 0 or second_value < first_value:
                return None
            numerator, denominator = second_value, first_value
        else:
            if second_value <= 0:
                return None
            if relation_word == 'больше' and first_value < second_value:
                return None
            numerator, denominator = first_value, second_value
        ratio = numerator / denominator
        lines.append(
            f'{step_number}) Для кратного сравнения делим одно новое количество денег на другое: '
            f'{_format_number(numerator)} : {_format_number(denominator)} = {_format_number(ratio)}.'
        )
        lines.append(f'Ответ: в {_format_number(ratio)} раза')
        lines.append('Совет: чтобы узнать, во сколько раз денег стало больше или меньше, раздели большую сумму на меньшую.')
        return _join_lines(lines)

    if 'на сколько' in question:
        if len(order) >= 2:
            first_index, second_index = order[:2]
        else:
            first_index, second_index = 0, 1
        first_value = current_values[first_index]
        second_value = current_values[second_index]
        if relation_word == 'меньше':
            if second_value < first_value:
                return None
            bigger, smaller = second_value, first_value
        elif relation_word == 'больше':
            if first_value < second_value:
                return None
            bigger, smaller = first_value, second_value
        else:
            bigger, smaller = max(current_values), min(current_values)
        difference = bigger - smaller
        lines.append(
            f'{step_number}) Сравниваем новые суммы денег: '
            f'{_format_number(bigger)} - {_format_number(smaller)} = {_format_number(difference)} руб.'
        )
        lines.append(f'Ответ: на {_format_number(difference)} руб')
        lines.append('Совет: если нужно узнать, на сколько одна сумма больше другой, вычти меньшую сумму из большей.')
        return _join_lines(lines)

    if order:
        target_index = order[0]
    else:
        return None
    lines.append(
        f'{step_number}) Смотрим новую сумму денег у {subject_entries[target_index]["label"]}: '
        f'{_format_number(current_values[target_index])} руб.'
    )
    lines.append(f'Ответ: {_format_number(current_values[target_index])} руб')
    lines.append('Совет: если деньги изменялись у двух людей, сначала найди новую сумму у каждого, а потом выбери нужную сумму.')
    return _join_lines(lines)


def _try_dual_subject_measured_after_changes_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if not _looks_like_dual_subject_measured_after_changes_problem(text):
        return None

    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    matches = list(_ACTION_VERB_RE.finditer(lower))
    if not matches:
        return None
    prefix_text = text[:matches[0].start()]
    infos = _extract_dual_measure_subject_infos(prefix_text)
    if len(infos) < 2:
        return None
    infos = infos[:2]
    subject_entries = [info['entry'] for info in infos]
    if any(info.get('quantity') is None for info in infos):
        return None

    group = infos[0]['quantity']['group']
    if any(info['quantity']['group'] != group for info in infos):
        return None

    question_mode = _direct_dual_subject_question_mode(question, subject_entries)
    all_group_quantities = [quantity for quantity in _extract_compound_quantities(text) if quantity['group'] == group]
    visible_units: list[str] = []
    for quantity in all_group_quantities:
        visible_units.extend(quantity['units'])
    base_unit = _choose_measure_base_unit(group, all_group_quantities)
    classified = _classify_measured_mixed_actions(text, subject_entries, group, base_unit, {'start': len(text)})
    if not classified:
        return None

    initial_values = [_quantity_value_in_unit(info['quantity'], base_unit) for info in infos]
    current_values = initial_values[:]
    current_total = sum(current_values, Fraction(0))
    total_distribution_unknown = False

    known_parts = []
    for info in infos:
        known_parts.append(f'{info["entry"]["label"]} — {info["quantity"]["pretty"]}')

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence('Что известно: сначала ' + ', '.join(known_parts)),
        _ensure_sentence(f'Что нужно найти: {(question or "что стало после изменений").rstrip("?.!")}'),
        f'1) Переводим начальные величины в {base_unit}: '
        + ', '.join(
            f'{info["quantity"]["pretty"]} = {_format_number(initial_values[index])} {base_unit}'
            for index, info in enumerate(infos)
        )
        + '.',
    ]
    step_number = 2

    for action in classified:
        kind = action['kind']
        if kind == 'total':
            if question_mode != 'total' or total_distribution_unknown:
                return None
            new_total = current_total + action['sign'] * action['value']
            if new_total < 0:
                return None
            operation = '+' if action['sign'] > 0 else '-'
            lines.append(
                f'{step_number}) Изменяется только общая величина: '
                f'{_format_number(current_total)} {operation} {_format_number(action["value"])} = {_format_number(new_total)} {base_unit}.'
            )
            current_total = new_total
            total_distribution_unknown = True
            step_number += 1
            continue

        if total_distribution_unknown:
            return None

        if kind == 'transfer':
            source_index = action['source_index']
            target_index = action['target_index']
            previous_source = current_values[source_index]
            previous_target = current_values[target_index]
            new_source = previous_source - action['value']
            new_target = previous_target + action['value']
            if new_source < 0 or new_target < 0:
                return None
            lines.append(
                f'{step_number}) Это передача между двумя величинами: '
                f'{subject_entries[source_index]["label"]}: {_format_number(previous_source)} - {_format_number(action["value"])} = {_format_number(new_source)} {base_unit}, '
                f'{subject_entries[target_index]["label"]}: {_format_number(previous_target)} + {_format_number(action["value"])} = {_format_number(new_target)} {base_unit}.'
            )
            current_values[source_index] = new_source
            current_values[target_index] = new_target
            current_total = sum(current_values, Fraction(0))
            step_number += 1
            continue

        if kind != 'subject':
            return None
        target_index = action['target_index']
        previous_value = current_values[target_index]
        new_value = previous_value + action['sign'] * action['value']
        if new_value < 0:
            return None
        operation = '+' if action['sign'] > 0 else '-'
        lines.append(
            f'{step_number}) Изменяем {subject_entries[target_index]["label"]}: '
            f'{_format_number(previous_value)} {operation} {_format_number(action["value"])} = {_format_number(new_value)} {base_unit}.'
        )
        current_values[target_index] = new_value
        current_total = sum(current_values, Fraction(0))
        step_number += 1

    if question_mode == 'both':
        order = _question_subject_order(question, subject_entries)
        if len(order) >= 2:
            first_index, second_index = order[:2]
        else:
            first_index, second_index = 0, 1
        first_text = _format_measure_value_text(current_values[first_index], group, base_unit, visible_units)
        second_text = _format_measure_value_text(current_values[second_index], group, base_unit, visible_units)
        lines.append(
            f'{step_number}) Теперь знаем обе новые величины: '
            f'{subject_entries[first_index]["label"]} — {first_text}, '
            f'{subject_entries[second_index]["label"]} — {second_text}.'
        )
        lines.append(
            f'Ответ: {subject_entries[first_index]["label"]} — {first_text}, '
            f'{subject_entries[second_index]["label"]} — {second_text}'
        )
        lines.append('Совет: если изменились две величины, сначала переведи их в одинаковые единицы, а потом измени каждую величину по порядку.')
        return _join_lines(lines)

    if question_mode == 'total':
        total_text = _format_measure_value_text(current_total, group, base_unit, visible_units)
        if not total_distribution_unknown:
            lines.append(
                f'{step_number}) Находим, сколько стало вместе: '
                f'{_format_number(current_values[0])} + {_format_number(current_values[1])} = {_format_number(current_total)} {base_unit}.'
            )
        else:
            lines.append(
                f'{step_number}) Записываем общую величину после всех изменений: {_format_number(current_total)} {base_unit} = {total_text}.'
            )
        lines.append(f'Ответ: {total_text}')
        lines.append('Совет: если изменились две величины, сначала переведи их в одинаковые единицы, а потом выполни все изменения по порядку.')
        return _join_lines(lines)

    if total_distribution_unknown:
        return None

    order = _question_subject_order(question, subject_entries)
    relation_word = 'меньше' if 'меньше' in question else 'больше' if 'больше' in question else ''
    if 'во сколько раз' in question:
        if len(order) >= 2:
            first_index, second_index = order[:2]
        else:
            first_index, second_index = 0, 1
        first_value = current_values[first_index]
        second_value = current_values[second_index]
        if relation_word == 'меньше':
            if first_value <= 0 or second_value < first_value:
                return None
            numerator, denominator = second_value, first_value
        else:
            if second_value <= 0:
                return None
            if relation_word == 'больше' and first_value < second_value:
                return None
            numerator, denominator = first_value, second_value
        ratio = numerator / denominator
        lines.append(
            f'{step_number}) Для кратного сравнения делим большую величину на меньшую: '
            f'{_format_number(numerator)} : {_format_number(denominator)} = {_format_number(ratio)}.'
        )
        lines.append(f'Ответ: в {_format_number(ratio)} раза')
        lines.append('Совет: чтобы узнать, во сколько раз одна величина больше другой, раздели большую величину на меньшую.')
        return _join_lines(lines)

    if 'на сколько' in question:
        if len(order) >= 2:
            first_index, second_index = order[:2]
        else:
            first_index, second_index = 0, 1
        first_value = current_values[first_index]
        second_value = current_values[second_index]
        if relation_word == 'меньше':
            if second_value < first_value:
                return None
            bigger, smaller = second_value, first_value
        elif relation_word == 'больше':
            if first_value < second_value:
                return None
            bigger, smaller = first_value, second_value
        else:
            bigger, smaller = max(current_values), min(current_values)
        difference = bigger - smaller
        diff_text = _format_measure_value_text(difference, group, base_unit, visible_units)
        lines.append(
            f'{step_number}) Сравниваем новые величины: '
            f'{_format_number(bigger)} - {_format_number(smaller)} = {_format_number(difference)} {base_unit}.'
        )
        lines.append(f'Ответ: на {diff_text}')
        lines.append('Совет: если нужно узнать, на сколько одна величина больше другой, вычти меньшую величину из большей.')
        return _join_lines(lines)

    if order:
        target_index = order[0]
    else:
        return None
    answer_text = _format_measure_value_text(current_values[target_index], group, base_unit, visible_units)
    lines.append(
        f'{step_number}) Записываем новую величину {_subject_location_phrase(subject_entries[target_index])}: '
        f'{_format_number(current_values[target_index])} {base_unit} = {answer_text}.'
    )
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: если изменились две величины, сначала переведи их в одинаковые единицы, а потом выполни все изменения по порядку.')
    return _join_lines(lines)


def _try_related_quantity_then_change_total_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if 'вместе' not in question and 'всего' not in question:
        return None
    if _extract_compound_quantities(text):
        return None

    relation_match = re.search(
        r'у\s+([а-яёa-z-]+)\s+(?:было\s*)?(\d+(?:[.,]\d+)?)\s+([а-яёa-z/-]+)[^?.!]*?у\s+([а-яёa-z-]+)\s+в\s*(\d+(?:[.,]\d+)?)\s+раз[а]?\s+(больше|меньше)',
        lower,
    )
    if not relation_match:
        return None

    first_name = relation_match.group(1)
    first_value = _to_fraction(relation_match.group(2))
    answer_label = relation_match.group(3).strip('.,!?')
    second_name = relation_match.group(4)
    factor = _to_fraction(relation_match.group(5))
    relation = relation_match.group(6)
    if factor <= 0:
        return None

    if relation == 'больше':
        second_value = first_value * factor
        relation_step = f'{_format_number(first_value)} × {_format_number(factor)} = {_format_number(second_value)}'
    else:
        second_value = first_value / factor
        relation_step = f'{_format_number(first_value)} : {_format_number(factor)} = {_format_number(second_value)}'

    actions, matches = _extract_sequential_actions(lower)
    filtered: list[tuple[dict[str, Any], re.Match[str]]] = [
        (action, match) for action, match in zip(actions, matches) if match.start() > relation_match.end()
    ]
    if not filtered:
        return None

    subject_entries = [
        {'keys': {_soft_person_key(first_name)}, 'label': first_name.capitalize()},
        {'keys': {_soft_person_key(second_name)}, 'label': second_name.capitalize()},
    ]
    current_values = [first_value, second_value]

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: у {first_name.capitalize()} было {_format_number(first_value)} {answer_label}, а у {second_name.capitalize()} — в {_format_number(factor)} раза {relation}'),
        _ensure_sentence(f'Что нужно найти: {(question or "сколько стало вместе").rstrip("?.!")}'),
        f'1) Находим, сколько было у {second_name.capitalize()}: {relation_step}.',
    ]

    step_number = 2
    for action, match in filtered:
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
            f'{step_number}) Изменяем количество у {subject_entries[target_index]["label"]}: {_format_number(old_value)} {operation} {_format_number(change_value)} = {_format_number(new_value)}.'
        )
        current_values[target_index] = new_value
        step_number += 1

    total_value = current_values[0] + current_values[1]
    lines.append(
        f'{step_number}) Находим, сколько стало вместе: {_format_number(current_values[0])} + {_format_number(current_values[1])} = {_format_number(total_value)}.'
    )
    lines.append(f'Ответ: {_format_number(total_value)} {answer_label}')
    lines.append('Совет: сначала найди количество по сравнению “в несколько раз”, потом выполни изменения и только после этого складывай оба результата.')
    return _join_lines(lines)


def _try_dual_subject_total_after_changes_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if _extract_compound_quantities(text):
        return None

    if re.search(r'в\s*\d+(?:[.,]\d+)?\s+раз[а]?\s+(?:больше|меньше)', lower):
        return None
    if re.search(r'на\s*\d+(?:[.,]\d+)?\s+(?:[а-яёa-z-]+\s+)?(?:больше|меньше)', lower):
        return None

    actions, matches = _extract_sequential_actions(lower)
    if not actions or not matches:
        return None

    prefix = lower[:matches[0].start()]
    prefix_number_matches = _plain_number_matches(prefix)
    if len(prefix_number_matches) < 2:
        return None

    subject_entries = _extract_dual_subject_entries(prefix, prefix_number_matches)
    if len(subject_entries) < 2:
        return None

    order = _question_subject_order(question, subject_entries)
    wants_total = 'вместе' in question or 'всего' in question
    if not wants_total and not order:
        return None
    if 'на сколько' in question or 'во сколько раз' in question:
        return None

    current_values = [
        _to_fraction(prefix_number_matches[0].group(1)),
        _to_fraction(prefix_number_matches[1].group(1)),
    ]
    initial_values = list(current_values)
    known_label_match = re.search(r'\d+\s+([а-яёa-z/-]+)', lower)
    known_label = known_label_match.group(1).strip('.,!?') if known_label_match else ''
    label_suffix = f' {known_label}' if known_label else ''

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(
            f'Что известно: сначала {subject_entries[0]["label"]} — {_format_number(initial_values[0])}{label_suffix}, '
            f'а {subject_entries[1]["label"]} — {_format_number(initial_values[1])}{label_suffix}'
        ),
        _ensure_sentence(f'Что нужно найти: {(question or "нужное количество после изменений").rstrip("?.!")}'),
    ]

    step_number = 1
    for action, match in zip(actions, matches):
        transfer = _extract_dual_subject_transfer_action(lower, match, subject_entries, action['value'])
        if transfer:
            step_number = _apply_dual_subject_transfer_step(lines, step_number, current_values, transfer, subject_entries, known_label)
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
            f'{step_number}) Изменяем {subject_entries[target_index]["label"]}: '
            f'{_format_number(old_value)} {operation} {_format_number(change_value)} = {_format_number(new_value)}{label_suffix}.'
        )
        current_values[target_index] = new_value
        step_number += 1

    if wants_total:
        total_value = current_values[0] + current_values[1]
        lines.append(
            f'{step_number}) Находим, сколько стало вместе: '
            f'{_format_number(current_values[0])} + {_format_number(current_values[1])} = {_format_number(total_value)}{label_suffix}.'
        )
        answer_text = _format_number(total_value)
        if known_label:
            answer_text += f' {known_label}'
        lines.append(f'Ответ: {answer_text}')
        lines.append('Совет: если в задаче два количества, сначала выполни все изменения у каждого из них, а потом складывай результат.')
        return _join_lines(lines)

    target_index = order[0]
    answer_text = _format_number(current_values[target_index])
    if known_label:
        answer_text += f' {known_label}'
    lines.append(
        f'{step_number}) Смотрим новое количество у {subject_entries[target_index]["label"]}: '
        f'{answer_text}.'
    )
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: если в задаче два количества, сначала выполни все изменения, а потом выбери то количество, про которое спрашивают.')
    return _join_lines(lines)


def _try_dual_subject_comparison_after_changes_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if 'на сколько' not in question and 'во сколько раз' not in question:
        return None
    if _extract_compound_quantities(text):
        return None

    actions, matches = _extract_sequential_actions(lower)
    if len(actions) < 2 or len(matches) < 2:
        return None

    prefix = lower[:matches[0].start()]
    prefix_number_matches = _plain_number_matches(prefix)
    if len(prefix_number_matches) < 2:
        return None

    subject_entries = _extract_dual_subject_entries(prefix, prefix_number_matches)
    if len(subject_entries) < 2:
        return None

    current_values = [
        _to_fraction(prefix_number_matches[0].group(1)),
        _to_fraction(prefix_number_matches[1].group(1)),
    ]
    initial_values = list(current_values)
    known_label_match = re.search(r'\d+\s+([а-яёa-z/-]+)', lower)
    known_label = known_label_match.group(1) if known_label_match else ''
    answer_label = ''
    if 'на сколько' in question:
        question_label_match = re.search(r'на\s+сколько\s+(?:(?:больше|меньше)\s+)?([а-яёa-z/-]+)', question)
        if question_label_match:
            candidate_label = question_label_match.group(1).strip('.,!?')
            if candidate_label not in {'больше', 'меньше', 'раз'}:
                answer_label = candidate_label
    if not answer_label:
        answer_label = known_label

    known_line = f'Что известно: сначала первое количество было {_format_number(initial_values[0])}'
    if known_label:
        known_line += f' {known_label}'
    known_line += f', а второе количество было {_format_number(initial_values[1])}'
    if known_label:
        known_line += f' {known_label}'
    known_line += '.'

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        known_line,
        _ensure_sentence(f'Что нужно найти: {(question or "сравнение после изменений").rstrip("?.!")}'),
    ]

    step_number = 1
    for action, match in zip(actions, matches):
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
            f'{step_number}) Изменяем {subject_entries[target_index]["label"]}: '
            f'{_format_number(old_value)} {operation} {_format_number(change_value)} = {_format_number(new_value)}.'
        )
        current_values[target_index] = new_value
        step_number += 1

    order = _question_subject_order(question, subject_entries)
    if len(order) >= 2:
        first_index, second_index = order[0], order[1]
    else:
        first_index, second_index = 0, 1

    first_value = current_values[first_index]
    second_value = current_values[second_index]
    relation_word = 'меньше' if 'меньше' in question else 'больше' if 'больше' in question else ''

    if 'во сколько раз' in question:
        if relation_word == 'меньше':
            if first_value == 0 or second_value < first_value:
                return None
            numerator, denominator = second_value, first_value
        else:
            if second_value == 0:
                return None
            if relation_word == 'больше' and first_value < second_value:
                return None
            numerator, denominator = first_value, second_value
        ratio = numerator / denominator
        lines.append(
            f'{step_number}) Для кратного сравнения делим одно новое количество на другое: '
            f'{_format_number(numerator)} : {_format_number(denominator)} = {_format_number(ratio)}.'
        )
        lines.append(f'Ответ: в {_format_number(ratio)} раза')
        lines.append('Совет: если изменились два количества, сначала найди каждое новое количество отдельно, а потом сравни их.')
        return _join_lines(lines)

    if relation_word == 'меньше':
        if second_value < first_value:
            return None
        bigger, smaller = second_value, first_value
    elif relation_word == 'больше':
        if first_value < second_value:
            return None
        bigger, smaller = first_value, second_value
    else:
        bigger, smaller = max(first_value, second_value), min(first_value, second_value)
    difference = bigger - smaller
    lines.append(
        f'{step_number}) Сравниваем новые количества: '
        f'{_format_number(bigger)} - {_format_number(smaller)} = {_format_number(difference)}.'
    )
    answer_text = f'на {_format_number(difference)}'
    if answer_label:
        answer_text += f' {answer_label}'
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: если изменились два количества, сначала найди каждое новое количество отдельно, а потом сравни их.')
    return _join_lines(lines)
