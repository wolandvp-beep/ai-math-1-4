from __future__ import annotations

"""Statically materialized handler source for legacy_change_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_reverse_sequential_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if _extract_compound_quantities(text):
        return None
    if not _looks_like_reverse_sequential_change_problem(text):
        return None

    actions, matches = _extract_sequential_actions(lower)
    if not actions:
        return None
    if len(_extract_named_subject_entries_from_text(lower)) >= 2 and any(match.group(1).lower().replace('ё', 'е') in _TRANSFER_ACTION_VERBS for match in matches):
        return None
    final_value = _extract_final_change_result_value(text)
    if final_value is None:
        return None

    question = _question_text(text).lower().replace('ё', 'е') or 'сколько было сначала'
    answer_label = _question_count_label(text) or _guess_count_answer_label(text)

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: после всех изменений стало {_format_number(final_value)}{(" " + answer_label) if answer_label else ""}.',
        f'Что нужно найти: {question.rstrip("?.!")}.',
    ]

    current_value = final_value
    for index, action in enumerate(reversed(actions), start=1):
        if action['sign'] > 0:
            previous_value = current_value - action['value']
            if previous_value < 0:
                return None
            lines.append(
                f'{index}) Отменяем прибавление: {_format_number(current_value)} - {_format_number(action["value"])} = {_format_number(previous_value)}.'
            )
        else:
            previous_value = current_value + action['value']
            lines.append(
                f'{index}) Отменяем вычитание: {_format_number(current_value)} + {_format_number(action["value"])} = {_format_number(previous_value)}.'
            )
        current_value = previous_value

    answer_text = _format_number(current_value)
    if answer_label:
        answer_text += f' {answer_label}'
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: если нужно узнать, сколько было сначала, начинай с конечного результата и отменяй действия в обратном порядке.')
    return _join_lines(lines)


def _try_sequential_change_word_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if _extract_compound_quantities(text):
        return None

    actions, matches = _extract_sequential_actions(lower)
    if len(actions) < 2 or not matches:
        return None

    prefix = lower[:matches[0].start()]
    question = _question_text(text).lower().replace('ё', 'е')
    if re.search(r'у\s+[а-яёa-z-]+\s+(?:было\s*)?\d+(?:[.,]\d+)?\s+[а-яёa-z/-]+[^?.!]*?у\s+[а-яёa-z-]+\s+в\s*\d+(?:[.,]\d+)?\s+раз[а]?\s+(?:больше|меньше)', lower):
        return None
    if re.search(r'это\s+в\s*\d+(?:[.,]\d+)?\s+раз[а]?\s+(?:больше|меньше)[^?.!]*?чем\s+у\s+[а-яёa-z-]+', lower):
        return None
    if 'сколько' in question and ('сначала' in question or 'было' in question):
        return None
    if len(_plain_number_matches(prefix)) >= 2 and ('на сколько' in question or 'во сколько раз' in question):
        return None

    prefix_numbers = re.findall(r'\d+(?:[.,]\d+)?', prefix)
    if not prefix_numbers:
        return None
    initial_value = _to_fraction(prefix_numbers[0])
    answer_label = _guess_count_answer_label(text)
    known, question = _split_known_and_question(text)
    if question:
        question_line = question.rstrip('.!?').lower()
    else:
        question_line = 'итог после всех изменений'

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: сначала было {_format_number(initial_value)}{(" " + answer_label) if answer_label else ""}.',
        f'Что нужно найти: {question_line}.',
    ]

    current_value = initial_value
    for index, action in enumerate(actions, start=1):
        change_value = action['value']
        sign = action['sign']
        new_value = current_value + sign * change_value
        if new_value < 0:
            return None
        op = '+' if sign > 0 else '-'
        action_text = 'Прибавляем следующее изменение' if sign > 0 else 'Вычитаем следующее изменение'
        lines.append(
            f'{index}) {action_text}: '
            f'{_format_number(current_value)} {op} {_format_number(change_value)} = {_format_number(new_value)}.'
        )
        current_value = new_value

    answer_text = _format_number(current_value)
    if answer_label:
        answer_text += f' {answer_label}'
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: если в задаче несколько изменений подряд, выполняй их по порядку и каждый раз записывай новый результат.')
    return _join_lines(lines)


def _try_find_initial_number_after_two_changes(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if _extract_compound_quantities(text):
        return None
    question = _question_text(text).lower().replace('ё', 'е')
    if 'число' not in lower and 'число' not in question:
        return None

    patterns = (
        (
            re.compile(
                r'(?:к\s+числу\s+прибавили|к\s+числу\s+добавили|число\s+увеличили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,40}?(?:а\s+потом|потом|затем)\D{0,20}?(?:вычли|отняли|число\s+уменьшили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,80}?(?:получилось|получили|стало|вышло|равно)\s*(\d+(?:[.,]\d+)?)',
                re.IGNORECASE,
            ),
            (1, -1),
        ),
        (
            re.compile(
                r'(?:из\s+числа\s+вычли|от\s+числа\s+отняли|число\s+уменьшили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,40}?(?:а\s+потом|потом|затем)\D{0,20}?(?:прибавили|добавили|число\s+увеличили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,80}?(?:получилось|получили|стало|вышло|равно)\s*(\d+(?:[.,]\d+)?)',
                re.IGNORECASE,
            ),
            (-1, 1),
        ),
        (
            re.compile(
                r'(?:к\s+числу\s+прибавили|к\s+числу\s+добавили|число\s+увеличили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,40}?(?:а\s+потом|потом|затем)\D{0,20}?(?:прибавили|добавили|число\s+увеличили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,80}?(?:получилось|получили|стало|вышло|равно)\s*(\d+(?:[.,]\d+)?)',
                re.IGNORECASE,
            ),
            (1, 1),
        ),
        (
            re.compile(
                r'(?:из\s+числа\s+вычли|от\s+числа\s+отняли|число\s+уменьшили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,40}?(?:а\s+потом|потом|затем)\D{0,20}?(?:вычли|отняли|число\s+уменьшили\s+на)\s*(\d+(?:[.,]\d+)?)\D{0,80}?(?:получилось|получили|стало|вышло|равно)\s*(\d+(?:[.,]\d+)?)',
                re.IGNORECASE,
            ),
            (-1, -1),
        ),
    )

    first_value = second_value = result_value = None
    signs: tuple[int, int] | None = None
    for pattern, candidate_signs in patterns:
        match = pattern.search(lower)
        if match:
            first_value = _to_fraction(match.group(1))
            second_value = _to_fraction(match.group(2))
            result_value = _to_fraction(match.group(3))
            signs = candidate_signs
            break
    if first_value is None or second_value is None or result_value is None or signs is None:
        return None

    actions = [
        {'sign': signs[0], 'value': first_value},
        {'sign': signs[1], 'value': second_value},
    ]

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: после двух действий получилось {_format_number(result_value)}.',
        'Что нужно найти: какое число было сначала.',
    ]

    current_value = result_value
    step_number = 1
    for action in reversed(actions):
        if action['sign'] > 0:
            inverse_value = current_value - action['value']
            lines.append(
                f'{step_number}) Отменяем действие прибавления: {_format_number(current_value)} - {_format_number(action["value"])} = {_format_number(inverse_value)}.'
            )
        else:
            inverse_value = current_value + action['value']
            lines.append(
                f'{step_number}) Отменяем действие вычитания: {_format_number(current_value)} + {_format_number(action["value"])} = {_format_number(inverse_value)}.'
            )
        current_value = inverse_value
        step_number += 1

    lines.append(f'Ответ: {_format_number(current_value)}')
    lines.append('Совет: если число изменяли несколько раз, то для поиска исходного числа нужно идти от ответа назад и отменять действия в обратном порядке.')
    return _join_lines(lines)


def _try_find_initial_number_after_change(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()

    subtract_match = re.search(
        r'(?:из\s+числа\s+вычли|от\s+числа\s+отняли|от\s+числа\s+вычли|число\s+уменьшили\s+на|после\s+(?:вычитания|уменьшения)\s*(?:числа\s+)?(?:на\s*)?)\s*(\d+(?:[.,]\d+)?)\D{0,80}?(?:получилось|получили|осталось|стало|вышло)\s*(\d+(?:[.,]\d+)?)',
        lower,
    )
    if subtract_match:
        removed_value = _to_fraction(subtract_match.group(1))
        result_value = _to_fraction(subtract_match.group(2))
        initial_value = result_value + removed_value
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: из неизвестного числа вычли {_format_number(removed_value)} и получили {_format_number(result_value)}.',
            'Что нужно найти: какое число было сначала.',
            '1) Чтобы найти исходное число, к результату прибавляем то, что вычли.',
            f'2) {_format_number(result_value)} + {_format_number(removed_value)} = {_format_number(initial_value)}.',
            f'Ответ: {_format_number(initial_value)}',
            'Совет: если после вычитания известно, что получилось, то исходное число находят сложением.',
        ])

    add_match = re.search(
        r'(?:к\s+числу\s+прибавили|к\s+числу\s+добавили|число\s+увеличили\s+на|после\s+(?:прибавления|добавления|увеличения)\s*(?:числа\s+)?(?:на\s*)?)\s*(\d+(?:[.,]\d+)?)\D{0,80}?(?:получилось|получили|стало|вышло)\s*(\d+(?:[.,]\d+)?)',
        lower,
    )
    if add_match:
        added_value = _to_fraction(add_match.group(1))
        result_value = _to_fraction(add_match.group(2))
        initial_value = result_value - added_value
        return _join_lines([
            'Задача.',
            _ensure_sentence(text),
            'Решение.',
            f'Что известно: к неизвестному числу прибавили {_format_number(added_value)} и получили {_format_number(result_value)}.',
            'Что нужно найти: какое число было сначала.',
            '1) Чтобы найти исходное число, из результата вычитаем то, что прибавили.',
            f'2) {_format_number(result_value)} - {_format_number(added_value)} = {_format_number(initial_value)}.',
            f'Ответ: {_format_number(initial_value)}',
            'Совет: если после сложения известно, что получилось, то исходное число находят вычитанием.',
        ])

    return None


def _try_ratio_after_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if 'во сколько раз' not in question:
        return None
    if _extract_compound_quantities(text):
        return None

    actions, matches = _extract_sequential_actions(lower)
    if len(actions) != 1 or not matches:
        return None

    prefix = lower[:matches[0].start()]
    prefix_number_matches = _plain_number_matches(prefix)
    if len(prefix_number_matches) < 2:
        return None

    first_value = _to_fraction(prefix_number_matches[0].group(1))
    second_value = _to_fraction(prefix_number_matches[1].group(1))
    subject_entries = _extract_dual_subject_entries(prefix, prefix_number_matches)
    if len(subject_entries) < 2:
        return None

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: сначала было {_format_number(first_value)} и {_format_number(second_value)}.'),
        _ensure_sentence(f'Что нужно найти: {(question or "во сколько раз одно количество стало больше или меньше другого").rstrip("?.!")}'),
    ]

    change = actions[0]
    updated_values = [first_value, second_value]
    transfer = _extract_dual_subject_transfer_action(lower, matches[0], subject_entries, change['value'])
    step_number = 1
    if transfer:
        step_number = _apply_dual_subject_transfer_step(lines, step_number, updated_values, transfer, subject_entries, '')
        if step_number is None:
            return None
    else:
        subject_words = _subject_words_before_numbers(prefix, prefix_number_matches)
        target_index = _detect_changed_subject_index(lower, matches[0], subject_words)
        old_target_value = updated_values[target_index]
        updated_values[target_index] = updated_values[target_index] + change['sign'] * change['value']
        if updated_values[target_index] < 0:
            return None
        operation = '+' if change['sign'] > 0 else '-'
        lines.append(
            f'{step_number}) Сначала изменяем одно количество: {_format_number(old_target_value)} {operation} {_format_number(change["value"])} = {_format_number(updated_values[target_index])}.'
        )
        step_number += 1

    relation_word = 'меньше' if 'меньше' in question else 'больше' if 'больше' in question else ''
    order = _question_subject_order(question, subject_entries)
    if len(order) >= 2:
        first_index, second_index = order[0], order[1]
    else:
        first_index, second_index = 0, 1

    first_current = updated_values[first_index]
    second_current = updated_values[second_index]
    if relation_word == 'меньше':
        if first_current <= 0 or second_current < first_current:
            return None
        numerator_value, denominator_value = second_current, first_current
    else:
        if second_current <= 0:
            return None
        if relation_word == 'больше' and first_current < second_current:
            return None
        numerator_value, denominator_value = first_current, second_current

    ratio = numerator_value / denominator_value
    lines.append(
        f'{step_number}) Для кратного сравнения делим одно новое количество на другое: {_format_number(numerator_value)} : {_format_number(denominator_value)} = {_format_number(ratio)}.'
    )
    lines.append(f'Ответ: в {_format_number(ratio)} раза')
    lines.append('Совет: сначала найди новые количества после изменения, а потом раздели большее количество на меньшее.')
    return _join_lines(lines)


def _try_difference_after_change_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if 'на сколько' not in question:
        return None
    if _extract_compound_quantities(text):
        return None

    actions, matches = _extract_sequential_actions(lower)
    if len(actions) != 1 or not matches:
        return None

    prefix = lower[:matches[0].start()]
    prefix_number_matches = _plain_number_matches(prefix)
    if len(prefix_number_matches) < 2:
        return None
    first_value = _to_fraction(prefix_number_matches[0].group(1))
    second_value = _to_fraction(prefix_number_matches[1].group(1))
    subject_entries = _extract_dual_subject_entries(prefix, prefix_number_matches)
    if len(subject_entries) < 2:
        return None

    label = _question_count_label(text) or _guess_count_answer_label(text)
    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        _ensure_sentence(f'Что известно: сначала было {_format_number(first_value)} и {_format_number(second_value)}.'),
        _ensure_sentence(f'Что нужно найти: {(question or "на сколько одна величина стала больше или меньше другой").rstrip("?.!")}'),
    ]

    change = actions[0]
    updated_values = [first_value, second_value]
    step_number = 1
    transfer = _extract_dual_subject_transfer_action(lower, matches[0], subject_entries, change['value'])
    if transfer:
        step_number = _apply_dual_subject_transfer_step(lines, step_number, updated_values, transfer, subject_entries, label)
        if step_number is None:
            return None
    else:
        subject_words = _subject_words_before_numbers(prefix, prefix_number_matches)
        target_index = _detect_changed_subject_index(lower, matches[0], subject_words)
        old_target_value = updated_values[target_index]
        updated_values[target_index] = updated_values[target_index] + change['sign'] * change['value']
        if updated_values[target_index] < 0:
            return None
        operation = '+' if change['sign'] > 0 else '-'
        lines.append(
            f'{step_number}) Сначала изменяем одно количество: {_format_number(old_target_value)} {operation} {_format_number(change["value"])} = {_format_number(updated_values[target_index])}.'
        )
        step_number += 1

    order = _question_subject_order(question, subject_entries)
    relation_word = 'меньше' if 'меньше' in question else 'больше' if 'больше' in question else ''
    if len(order) >= 2:
        first_index, second_index = order[0], order[1]
    else:
        first_index, second_index = 0, 1

    first_current = updated_values[first_index]
    second_current = updated_values[second_index]
    if relation_word == 'меньше':
        if second_current < first_current:
            return None
        bigger, smaller = second_current, first_current
    elif relation_word == 'больше':
        if first_current < second_current:
            return None
        bigger, smaller = first_current, second_current
    else:
        bigger, smaller = max(updated_values), min(updated_values)

    difference = bigger - smaller
    answer_text = f'на {_format_number(difference)}' + (f' {label}' if label else '')
    lines.append(f'{step_number}) Сравниваем новые количества: {_format_number(bigger)} - {_format_number(smaller)} = {_format_number(difference)}.')
    lines.append(f'Ответ: {answer_text}')
    lines.append('Совет: сначала найди новые количества после изменения, а потом вычти меньшее из большего.')
    return _join_lines(lines)
