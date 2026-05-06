from __future__ import annotations

"""Statically materialized handler source for legacy_purchase_problem_handlers_source.py."""

from backend.static_module_bootstrap import seed_static_module_globals

__STATIC_BOOTSTRAP_SEEDED_SNAPSHOT__ = seed_static_module_globals(globals())

def _try_reverse_money_purchase_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    parsing_lower = _replace_small_number_words(lower)
    if not _looks_like_reverse_money_purchase_problem(text):
        return None

    purchases = _extract_purchase_entries_for_local_solver(parsing_lower)
    if not purchases:
        return None
    final_balance = _extract_final_money_balance_for_local_solver(parsing_lower)
    if final_balance is None:
        return None

    extra_expenses = _extract_extra_expenses_for_local_solver(parsing_lower, None)
    extra_incomes = _extract_extra_incomes_for_local_solver(parsing_lower, None)

    purchase_line_items = [
        {
            'kind': 'purchase',
            'label': item['item_label'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
            'cost': item['quantity'] * item['unit_price'],
        }
        for item in purchases
    ]
    extra_line_items = [
        {
            'kind': 'expense',
            'label': expense['label'],
            'cost': expense['cost'],
        }
        for expense in extra_expenses
    ]
    all_expense_items = purchase_line_items + extra_line_items
    total_cost = sum((item['cost'] for item in all_expense_items), Fraction(0))
    total_income = sum((item['amount'] for item in extra_incomes), Fraction(0))

    balance_after_expenses = final_balance
    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
    ]
    known_parts: list[str] = [f'после всех действий осталось {_format_number(final_balance)} руб']
    for item in purchases:
        if item['quantity'] == 1:
            known_parts.append(f'{item["item_label"]} за {_format_number(item["unit_price"])} руб')
        else:
            known_parts.append(f'{_format_number(item["quantity"])} {item["item_label"]} по {_format_number(item["unit_price"])} руб')
    for expense in extra_expenses:
        known_parts.append(f'ещё потратили {_format_number(expense["cost"])} руб на {expense["label"]}')
    for income in extra_incomes:
        known_parts.append(f'потом получили {_format_number(income["amount"])} руб')
    lines.append(_ensure_sentence('Что известно: ' + ', '.join(known_parts)))
    lines.append('Что нужно найти: сколько рублей было сначала.')

    step_number = 1
    for item in purchase_line_items:
        item_phrase = item['label'] if item['quantity'] == 1 else f'{_format_number(item["quantity"])} {item["label"]}'
        lines.append(
            _ensure_sentence(
                f'{step_number}) Находим стоимость покупки {item_phrase}: {_format_number(item["quantity"])} × {_format_number(item["unit_price"])} = {_format_number(item["cost"])} руб'
            )
        )
        step_number += 1
    for item in extra_line_items:
        lines.append(
            _ensure_sentence(
                f'{step_number}) Учитываем дополнительную трату на {item["label"]}: {_format_number(item["cost"])} руб'
            )
        )
        step_number += 1

    if len(all_expense_items) > 1:
        addition = ' + '.join(_format_number(item['cost']) for item in all_expense_items)
        lines.append(_ensure_sentence(f'{step_number}) Складываем все траты: {addition} = {_format_number(total_cost)} руб'))
        step_number += 1

    if extra_incomes:
        if len(extra_incomes) > 1:
            income_addition = ' + '.join(_format_number(item['amount']) for item in extra_incomes)
            lines.append(_ensure_sentence(f'{step_number}) Складываем все добавленные деньги: {income_addition} = {_format_number(total_income)} руб'))
            step_number += 1
        balance_after_expenses = final_balance - total_income
        if balance_after_expenses < 0:
            return None
        lines.append(
            _ensure_sentence(
                f'{step_number}) Отменяем добавление денег: {_format_number(final_balance)} - {_format_number(total_income)} = {_format_number(balance_after_expenses)} руб'
            )
        )
        step_number += 1

    initial_money = balance_after_expenses + total_cost
    lines.append(
        _ensure_sentence(
            f'{step_number}) Чтобы найти сумму в начале, прибавляем все траты к остатку после трат: {_format_number(balance_after_expenses)} + {_format_number(total_cost)} = {_format_number(initial_money)} руб'
        )
    )
    lines.append(f'Ответ: {_format_number(initial_money)} руб')
    lines.append('Совет: если известно, сколько осталось после покупок, то для поиска суммы в начале нужно идти назад: отменить добавленные деньги и прибавить все траты.')
    return _join_lines(lines)


def _try_money_purchase_flow_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _looks_like_dual_subject_money_after_changes_problem(text):
        return None
    lower = text.lower().replace('ё', 'е')
    parsing_lower = _replace_small_number_words(lower)
    if not _looks_like_money_purchase_flow_problem(text):
        return None

    purchases = _extract_purchase_entries_for_local_solver(parsing_lower)
    if not purchases:
        return None

    question = _question_text(text).lower().replace('ё', 'е')
    ask_change = 'сдач' in question or 'сдач' in lower
    ask_shortage = 'не хватает' in question or ('не хват' in question and 'сколько' in question)
    ask_enough = 'хватит ли' in question or 'достаточно ли' in question
    ask_difference_to_initial = (
        'на сколько рублей стало меньше' in question
        or 'на сколько денег стало меньше' in question
        or re.search(r'на\s+сколько[^?.!]*меньше[^?.!]*(?:было|сначала)', question) is not None
    )
    ask_remaining = ask_change or ask_shortage or ask_enough or 'остал' in question or 'остан' in question or ('денег' in lower and ('остал' in lower or 'остан' in lower))

    initial_money, initial_money_span, money_source = _extract_initial_money_for_local_solver(parsing_lower, ask_remaining or ask_difference_to_initial)
    if initial_money is None:
        return None

    extra_expenses = _extract_extra_expenses_for_local_solver(parsing_lower, initial_money_span)
    extra_incomes = _extract_extra_incomes_for_local_solver(parsing_lower, initial_money_span)
    if not extra_incomes and not ask_difference_to_initial:
        return None

    purchase_line_items = [
        {
            'kind': 'purchase',
            'label': item['item_label'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
            'cost': item['quantity'] * item['unit_price'],
        }
        for item in purchases
    ]
    extra_line_items = [
        {
            'kind': 'expense',
            'label': expense['label'],
            'cost': expense['cost'],
        }
        for expense in extra_expenses
    ]
    all_expense_items = purchase_line_items + extra_line_items
    total_cost = sum((item['cost'] for item in all_expense_items), Fraction(0))
    total_income = sum((item['amount'] for item in extra_incomes), Fraction(0))
    balance_after_expenses = initial_money - total_cost
    final_balance = balance_after_expenses + total_income

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
    ]
    known_parts: list[str] = []
    for item in purchases:
        if item['quantity'] == 1:
            known_parts.append(f'{item["item_label"]} за {_format_number(item["unit_price"])} руб')
        else:
            known_parts.append(f'{_format_number(item["quantity"])} {item["item_label"]} по {_format_number(item["unit_price"])} руб')
    for expense in extra_expenses:
        known_parts.append(f'ещё потратили {_format_number(expense["cost"])} руб на {expense["label"]}')
    for income in extra_incomes:
        known_parts.append(f'потом получили {_format_number(income["amount"])} руб')
    money_intro = 'сначала было' if money_source == 'initial' else 'на покупку дали'
    lines.append(_ensure_sentence(f'Что известно: {money_intro} {_format_number(initial_money)} руб, ' + ', '.join(known_parts)))

    if ask_difference_to_initial:
        lines.append('Что нужно найти: на сколько рублей денег стало меньше по сравнению с началом.')
    elif ask_change:
        lines.append('Что нужно найти: сколько сдачи получили.')
    elif ask_shortage:
        lines.append('Что нужно найти: сколько рублей не хватает.')
    elif ask_enough:
        lines.append('Что нужно найти: хватит ли денег на все траты.')
    else:
        lines.append('Что нужно найти: сколько денег осталось после всех действий.')

    step_number = 1
    for item in purchase_line_items:
        item_phrase = item['label'] if item['quantity'] == 1 else f'{_format_number(item["quantity"])} {item["label"]}'
        lines.append(
            _ensure_sentence(
                f'{step_number}) Находим стоимость покупки {item_phrase}: {_format_number(item["quantity"])} × {_format_number(item["unit_price"])} = {_format_number(item["cost"])} руб'
            )
        )
        step_number += 1
    for item in extra_line_items:
        lines.append(
            _ensure_sentence(
                f'{step_number}) Учитываем дополнительную трату на {item["label"]}: {_format_number(item["cost"])} руб'
            )
        )
        step_number += 1

    if len(all_expense_items) > 1:
        addition = ' + '.join(_format_number(item['cost']) for item in all_expense_items)
        lines.append(_ensure_sentence(f'{step_number}) Складываем все траты: {addition} = {_format_number(total_cost)} руб'))
        step_number += 1

    lines.append(
        _ensure_sentence(
            f'{step_number}) Находим, сколько денег осталось после покупок: {_format_number(initial_money)} - {_format_number(total_cost)} = {_format_number(balance_after_expenses)} руб'
        )
    )
    step_number += 1

    if extra_incomes:
        for income in extra_incomes:
            lines.append(
                _ensure_sentence(
                    f'{step_number}) Учитываем, что потом добавили деньги: {_format_number(income["amount"])} руб'
                )
            )
            step_number += 1
        if len(extra_incomes) > 1:
            income_addition = ' + '.join(_format_number(item['amount']) for item in extra_incomes)
            lines.append(_ensure_sentence(f'{step_number}) Складываем все дополнительные деньги: {income_addition} = {_format_number(total_income)} руб'))
            step_number += 1
        lines.append(
            _ensure_sentence(
                f'{step_number}) Прибавляем полученные деньги к остатку: {_format_number(balance_after_expenses)} + {_format_number(total_income)} = {_format_number(final_balance)} руб'
            )
        )
        step_number += 1

    if ask_difference_to_initial:
        difference = initial_money - final_balance
        if difference >= 0:
            lines.append(
                _ensure_sentence(
                    f'{step_number}) Сравниваем с началом: {_format_number(initial_money)} - {_format_number(final_balance)} = {_format_number(difference)} руб'
                )
            )
            lines.append(f'Ответ: на {_format_number(difference)} руб')
        else:
            difference = -difference
            lines.append(
                _ensure_sentence(
                    f'{step_number}) Сравниваем с началом: {_format_number(final_balance)} - {_format_number(initial_money)} = {_format_number(difference)} руб'
                )
            )
            lines.append(f'Ответ: денег стало больше на {_format_number(difference)} руб')
        lines.append('Совет: чтобы узнать, на сколько денег стало меньше, сравни сумму в начале и сумму после всех покупок и добавлений.')
        return _join_lines(lines)

    if final_balance >= 0:
        if ask_enough:
            lines.append(f'Ответ: да, хватит. Останется {_format_number(final_balance)} руб')
        elif ask_shortage:
            lines.append('Ответ: 0 руб, денег хватает')
        else:
            lines.append(f'Ответ: {_format_number(final_balance)} руб')
        lines.append('Совет: сначала находят все траты, потом остаток после покупок, а если деньги ещё добавили, этот остаток увеличивают.')
        return _join_lines(lines)

    shortage = -final_balance
    lines.append(
        _ensure_sentence(
            f'{step_number}) Денег всё равно не хватает: {_format_number(total_cost)} - {_format_number(initial_money + total_income)} = {_format_number(shortage)} руб'
        )
    )
    if ask_enough:
        lines.append(f'Ответ: нет, не хватит. Не хватает {_format_number(shortage)} руб')
    else:
        lines.append(f'Ответ: не хватает {_format_number(shortage)} руб')
    lines.append('Совет: если после всех добавлений денег всё равно меньше, чем нужно на покупку, находят, сколько рублей не хватает.')
    return _join_lines(lines)


def _try_unit_price_purchase_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    if _looks_like_dual_subject_money_after_changes_problem(text):
        return None
    lower = text.lower().replace('ё', 'е')
    parsing_lower = _replace_small_number_words(lower)
    purchase_pattern = re.compile(
        r'(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+(?:\s+[а-яёa-z-]+){0,2})\s+по\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        re.IGNORECASE,
    )
    single_price_pattern = re.compile(
        r'(?:(\d+(?:[.,]\d+)?)\s+)?([а-яёa-z-]+(?:\s+[а-яёa-z-]+){0,2})\s+за\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE + r'\s*$',
        re.IGNORECASE,
    )
    purchases = []

    for match in purchase_pattern.finditer(parsing_lower):
        quantity = _to_fraction(match.group(1))
        item_label = _normalize_space(match.group(2)).strip(' .,!?:;')
        unit_price = _to_fraction(match.group(3))
        if quantity <= 0 or unit_price < 0:
            return None
        purchases.append({'quantity': quantity, 'item_label': item_label, 'unit_price': unit_price})

    for fragment in re.split(r'[,.!?;]|\sи\s', parsing_lower):
        fragment = _normalize_space(fragment)
        if not fragment or ' по ' in fragment:
            continue
        previous_fragment = None
        while fragment != previous_fragment:
            previous_fragment = fragment
            fragment = re.sub(r'^(?:она|он|они|мама|папа|купил(?:а|и)?|купили|взял(?:а|и)?|взяли|заплатил(?:а|и)?|заплатили|потом|затем|ещё|еще|за)\s+', '', fragment).strip()
        fragment = re.sub(
            r'\s*(?:заплатил(?:а|и)?|заплатили|отдал(?:а|и)?|дала|дали|дал)\s*\d+(?:[.,]\d+)?\s*' + _RUBLE_RE + r'.*$',
            '',
            fragment,
        ).strip()
        match = single_price_pattern.search(fragment)
        if not match:
            continue
        quantity_text = match.group(1)
        item_label = _normalize_space(match.group(2)).strip(' .,!?:;')
        unit_price = _to_fraction(match.group(3))
        quantity = _to_fraction(quantity_text) if quantity_text else Fraction(1)
        if not item_label or quantity <= 0 or unit_price < 0:
            continue
        candidate = {'quantity': quantity, 'item_label': item_label, 'unit_price': unit_price}
        if candidate not in purchases:
            purchases.append(candidate)
    if not purchases:
        return None

    question = _question_text(text).lower().replace('ё', 'е')
    if 'сколько' in question and ('сначала' in question or 'было' in question):
        return None
    ask_change = 'сдач' in question or 'сдач' in lower
    ask_shortage = 'не хватает' in question or ('не хват' in question and 'сколько' in question)
    ask_enough = 'хватит ли' in question or 'достаточно ли' in question
    ask_remaining = ask_change or ask_shortage or ask_enough or 'остал' in question or 'остан' in question or ('денег' in lower and ('остал' in lower or 'остан' in lower))

    money_source = 'initial'
    initial_money = None
    initial_money_span = None
    initial_patterns = (
        r'(?:^|[.?!]\s*|,\s*)было\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        r'(?:^|[.?!]\s*|,\s*)имелось\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        r'(?:^|[.?!]\s*|,\s*)лежало\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        r'(?:^|[.?!]\s*|,\s*)у\s+[а-яёa-z-]+\s*(?:было\s*)?(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        r'(?:^|[.?!]\s*|,\s*)в\s+кошельке\s*(?:было\s*)?(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
    )
    for pattern in initial_patterns:
        initial_money_match = re.search(pattern, parsing_lower)
        if initial_money_match:
            initial_money = _to_fraction(initial_money_match.group(1))
            initial_money_span = initial_money_match.span(1)
            break
    if initial_money is None and ask_remaining:
        payment_patterns = (
            r'с\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
            r'(?:заплатил(?:а|и)?|отдал(?:а|и)?|дали|дала|дал)\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
            r'заплатили\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        )
        for pattern in payment_patterns:
            payment_match = re.search(pattern, parsing_lower)
            if payment_match:
                initial_money = _to_fraction(payment_match.group(1))
                initial_money_span = payment_match.span(1)
                money_source = 'payment'
                break

    extra_expenses: list[dict[str, Any]] = []
    seen_expense_spans: set[tuple[int, int]] = set()

    def _add_extra_expense(amount_text: str, label: str, span: tuple[int, int]) -> None:
        if span in seen_expense_spans:
            return
        if initial_money_span and not (span[1] <= initial_money_span[0] or span[0] >= initial_money_span[1]):
            return
        amount = _to_fraction(amount_text)
        if amount < 0:
            return
        seen_expense_spans.add(span)
        cleaned_label = _normalize_space(label).strip(' .,!?:;') or 'дополнительная трата'
        normalized_label = cleaned_label
        if cleaned_label.startswith('проезд'):
            normalized_label = 'проезд'
        elif cleaned_label.startswith('билет'):
            normalized_label = 'билет'
        elif cleaned_label.startswith('доставк'):
            normalized_label = 'доставку'
        elif cleaned_label.startswith('поездк'):
            normalized_label = 'поездку'
        elif cleaned_label.startswith('дорог'):
            normalized_label = 'дорогу'
        extra_expenses.append({'cost': amount, 'label': normalized_label})

    payment_expense_pattern = re.compile(
        r'(?:^|[,.!?;]\s*|\s+)(?:потом|затем|ещё|еще)?\s*(?:заплатил(?:а|и)?|отдал(?:а|и)?|потратил(?:а|и)?|потратила|потратили|оплатил(?:а|и)?|уплатил(?:а|и)?|внес(?:ла|ли)?|израсходовал(?:а|и)?)\s*(\d+(?:[.,]\d+)?)\s*'
        + _RUBLE_RE
        + r'(?:\s*за\s*([а-яёa-z-]+(?:\s+[а-яёa-z-]+){0,3}))?',
        re.IGNORECASE,
    )
    for match in payment_expense_pattern.finditer(parsing_lower):
        label = match.group(2) or 'дополнительную покупку'
        _add_extra_expense(match.group(1), label, match.span(1))

    named_expense_pattern = re.compile(
        r'(?:оплат[а-я]*\s+)?(проезд(?:а)?|билет(?:а)?|доставк[а-я]*|поездк[а-я]*|дорог[а-я]*)\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        re.IGNORECASE,
    )
    for match in named_expense_pattern.finditer(parsing_lower):
        _add_extra_expense(match.group(2), match.group(1), match.span(2))

    purchase_line_items = [
        {
            'kind': 'purchase',
            'label': item['item_label'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
            'cost': item['quantity'] * item['unit_price'],
        }
        for item in purchases
    ]
    extra_line_items = [
        {
            'kind': 'expense',
            'label': expense['label'],
            'cost': expense['cost'],
        }
        for expense in extra_expenses
    ]
    all_line_items = purchase_line_items + extra_line_items
    total_cost = sum((item['cost'] for item in all_line_items), Fraction(0))
    if ask_remaining and initial_money is None:
        return None

    lines = [
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
    ]
    known_parts = []
    for item in purchases:
        if item['quantity'] == 1:
            known_parts.append(f'{item["item_label"]} за {_format_number(item["unit_price"])} руб')
        else:
            known_parts.append(f'{_format_number(item["quantity"])} {item["item_label"]} по {_format_number(item["unit_price"])} руб')
    for expense in extra_expenses:
        known_parts.append(f'ещё потратили {_format_number(expense["cost"])} руб на {expense["label"]}')
    if initial_money is not None:
        money_intro = 'сначала было' if money_source == 'initial' else 'на покупку дали'
        lines.append(_ensure_sentence(f'Что известно: {money_intro} {_format_number(initial_money)} руб, ' + ', '.join(known_parts)))
    else:
        lines.append(_ensure_sentence('Что известно: ' + ', '.join(known_parts)))
    if ask_change:
        lines.append('Что нужно найти: сколько сдачи получили.')
    elif ask_shortage:
        lines.append('Что нужно найти: сколько рублей не хватает.')
    elif ask_enough:
        lines.append('Что нужно найти: хватит ли денег на все траты.')
    elif ask_remaining:
        lines.append('Что нужно найти: сколько денег осталось.')
    else:
        lines.append(_ensure_sentence(f'Что нужно найти: {(_question_text(text) or "стоимость покупки").rstrip("?.!").lower()}'))

    step_number = 1
    for item in purchase_line_items:
        item_phrase = item['label'] if item['quantity'] == 1 else f'{_format_number(item["quantity"])} {item["label"]}'
        lines.append(
            _ensure_sentence(
                f'{step_number}) Находим стоимость покупки {item_phrase}: {_format_number(item["quantity"])} × {_format_number(item["unit_price"])} = {_format_number(item["cost"])} руб'
            )
        )
        step_number += 1
    for item in extra_line_items:
        lines.append(
            _ensure_sentence(
                f'{step_number}) Учитываем дополнительную трату на {item["label"]}: {_format_number(item["cost"])} руб'
            )
        )
        step_number += 1

    if len(all_line_items) > 1:
        addition = ' + '.join(_format_number(item['cost']) for item in all_line_items)
        lines.append(_ensure_sentence(f'{step_number}) Складываем все траты: {addition} = {_format_number(total_cost)} руб'))
        step_number += 1

    if ask_remaining:
        balance = initial_money - total_cost
        if balance >= 0:
            lines.append(_ensure_sentence(f'{step_number}) Вычитаем все траты из всех денег: {_format_number(initial_money)} - {_format_number(total_cost)} = {_format_number(balance)} руб'))
            step_number += 1
            if len(all_line_items) > 1:
                current_money = initial_money
                for index, item in enumerate(all_line_items, start=1):
                    next_money = current_money - item['cost']
                    lines.append(_ensure_sentence(f'{step_number}) После {index}-й траты денег осталось: {_format_number(current_money)} - {_format_number(item["cost"])} = {_format_number(next_money)} руб'))
                    step_number += 1
                    current_money = next_money
            if ask_enough:
                lines.append(f'Ответ: да, хватит. Останется {_format_number(balance)} руб')
            elif ask_shortage:
                lines.append('Ответ: 0 руб, денег хватает')
            else:
                lines.append(f'Ответ: {_format_number(balance)} руб')
            lines.append('Совет: сначала находят стоимость каждой покупки и каждой дополнительной траты, затем все расходы вместе и только потом сравнивают их с имеющимися деньгами.')
            return _join_lines(lines)

        shortage = total_cost - initial_money
        lines.append(_ensure_sentence(f'{step_number}) Находим, сколько денег не хватает: {_format_number(total_cost)} - {_format_number(initial_money)} = {_format_number(shortage)} руб'))
        if ask_enough:
            lines.append(f'Ответ: нет, не хватит. Не хватает {_format_number(shortage)} руб')
        else:
            lines.append(f'Ответ: не хватает {_format_number(shortage)} руб')
        lines.append('Совет: если расходов получилось больше, чем денег было сначала, нужно найти разность: сколько надо добавить до полной суммы.')
        return _join_lines(lines)

    lines.append(f'Ответ: {_format_number(total_cost)} руб')
    lines.append('Совет: стоимость одинаковых товаров находят умножением количества на цену одной штуки.')
    return _join_lines(lines)


def _try_direct_price_problem(raw_text: str) -> Optional[str]:
    text = _clean_text(raw_text)
    lower = text.lower()
    target_match = (
        re.search(r'сколько\s+стоят?\s*(\d+)', lower)
        or re.search(r'какова\s+стоимость\s*(\d+)', lower)
        or re.search(r'сколько\s+заплат(?:ят|ить)\s+за\s*(\d+)', lower)
    )
    if not target_match:
        return None
    target_count = _to_fraction(target_match.group(1))

    known_match = (
        re.search(rf'цена\s*(\d+)\s+([а-яё\- ]+?)\s*(?:составляет|равна)?\s*(\d+)\s*{_RUBLE_RE}', lower)
        or re.search(rf'стоимость\s*(\d+)\s+([а-яё\- ]+?)\s*(?:составляет|равна)?\s*(\d+)\s*{_RUBLE_RE}', lower)
        or re.search(rf'за\s*(\d+)\s+([а-яё\- ]+?)\s*(?:заплатили|отдали)\s*(\d+)\s*{_RUBLE_RE}', lower)
        or re.search(rf'(\d+)\s+([а-яё\- ]+?)\s+стоят\s*(\d+)\s*{_RUBLE_RE}', lower)
    )
    if not known_match:
        return None

    known_count = _to_fraction(known_match.group(1))
    item_phrase = _normalize_space(known_match.group(2)).strip(' .,!?:;')
    total_price = _to_fraction(known_match.group(3))
    if known_count <= 0:
        return None

    unit_price = total_price / known_count
    target_price = unit_price * target_count
    known, question = _split_known_and_question(text)
    if not question:
        question = _ensure_sentence(f'Сколько стоят {_format_number(target_count)} таких предметов')

    item_label = item_phrase or 'предметов'
    return _join_lines([
        'Задача.',
        _ensure_sentence(text),
        'Решение.',
        f'Что известно: {_format_number(known_count)} {item_label} стоят {_format_number(total_price)} руб.',
        f'Что нужно найти: {question[:-1].lower() if question.endswith(("?", ".", "!")) else question.lower()}.',
        f'1) Находим цену одной штуки: {_format_number(total_price)} : {_format_number(known_count)} = {_format_number(unit_price)} руб.',
        f'2) Находим цену {_format_number(target_count)} штук: {_format_number(unit_price)} × {_format_number(target_count)} = {_format_number(target_price)} руб.',
        f'Ответ: {_format_number(target_price)} руб',
        'Совет: сначала находят цену одной вещи, а потом умножают на нужное количество.',
    ])
