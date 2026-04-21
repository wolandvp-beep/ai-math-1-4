from __future__ import annotations

import ast
from typing import List, Optional

from .math_primitives import NEXT_PLACE_NAMES, PLACE_NAMES, digits_by_place, get_digits, split_tens_units
from .text_utils import join_explanation_lines


def build_long_division_steps(dividend: int, divisor: int):
    digits = list(str(dividend))
    steps = []
    current = ""
    quotient_digits = []
    started = False
    for index, digit in enumerate(digits):
        current += digit
        current_number = int(current)
        if current_number < divisor:
            if started:
                quotient_digits.append(("zero", current_number, index))
            continue
        started = True
        q_digit = current_number // divisor
        product = q_digit * divisor
        remainder = current_number - product
        next_digit = int(digits[index + 1]) if index + 1 < len(digits) else None
        steps.append({"current": current_number, "q_digit": q_digit, "product": product, "remainder": remainder, "next_digit": next_digit, "index": index})
        quotient_digits.append(("digit", q_digit, index))
        current = str(remainder)
    if not started:
        quotient_digits = [("digit", 0, 0)]
    remainder = int(current or "0")
    return {"steps": steps, "quotient": dividend // divisor if divisor != 0 else None, "remainder": remainder, "quotient_digits": quotient_digits}


def explain_addition_via_ten(left: int, right: int) -> str:
    to_ten = 10 - left
    rest = right - to_ten
    total = left + right
    return join_explanation_lines(
        "Ищем сумму",
        f"Чтобы получить 10, к {left} нужно прибавить {to_ten}",
        f"Разложим {right} на {to_ten} и {rest}",
        f"{left} + {to_ten} = 10, потом 10 + {rest} = {total}",
        f"Ответ: {total}",
        "Совет: если удобно, сначала доводи число до 10",
    )


def explain_subtraction_via_ten(left: int, right: int) -> str:
    first_part = left % 10
    second_part = right - first_part
    result = left - right
    return join_explanation_lines(
        "Ищем разность",
        f"Разложим {right} на {first_part} и {second_part}",
        f"Сначала {left} - {first_part} = 10",
        f"Потом 10 - {second_part} = {result}",
        f"Ответ: {result}",
        "Совет: при вычитании через десяток удобно сначала дойти до 10",
    )


def explain_subtraction_two_digit_with_borrow(minuend: int, subtrahend: int) -> Optional[str]:
    if minuend < 20 or subtrahend < 10:
        return None
    if minuend % 10 >= subtrahend % 10:
        return None
    tens = (minuend // 10 - 1) * 10
    units = 10 + (minuend % 10)
    subtrahend_tens = (subtrahend // 10) * 10
    subtrahend_units = subtrahend % 10
    result = minuend - subtrahend
    return join_explanation_lines(
        "Ищем разность",
        f"Представим {minuend} как {tens} + {units}",
        f"Представим {subtrahend} как {subtrahend_tens} + {subtrahend_units}",
        f"Вычитаем десятки: {tens} - {subtrahend_tens} = {tens - subtrahend_tens}",
        f"Вычитаем единицы: {units} - {subtrahend_units} = {units - subtrahend_units}",
        f"Складываем полученные разности: {tens - subtrahend_tens} + {units - subtrahend_units} = {result}",
        f"Ответ: {result}",
        "Совет: при вычитании с переходом через десяток удобно разложить уменьшаемое",
    )


def explain_column_addition(numbers: List[int]) -> str:
    ordered = sorted(numbers, key=lambda x: (len(str(abs(x))), abs(x)), reverse=True)
    width = max(len(str(abs(n))) for n in ordered)
    columns = [digits_by_place(n, width) for n in ordered]
    carry = 0
    lines = [
        "Пишем числа в столбик: единицы под единицами, десятки под десятками и так далее",
        "Начинаем сложение с единиц",
    ]
    for pos_from_right in range(width):
        idx = width - 1 - pos_from_right
        digits = [col[idx] for col in columns]
        total = sum(digits) + carry
        digit = total % 10
        new_carry = total // 10
        place_name = PLACE_NAMES[pos_from_right] if pos_from_right < len(PLACE_NAMES) else "разряд"
        expr = " + ".join(str(d) for d in digits)
        if carry:
            if new_carry:
                next_place = NEXT_PLACE_NAMES[pos_from_right] if pos_from_right < len(NEXT_PLACE_NAMES) else "следующий разряд"
                lines.append(f"{place_name.capitalize()}: {expr} и ещё {carry} = {total}. Пишем {digit}, {new_carry} {next_place} запоминаем")
            else:
                lines.append(f"{place_name.capitalize()}: {expr} и ещё {carry} = {total}. Пишем {digit}")
        else:
            if new_carry:
                next_place = NEXT_PLACE_NAMES[pos_from_right] if pos_from_right < len(NEXT_PLACE_NAMES) else "следующий разряд"
                lines.append(f"{place_name.capitalize()}: {expr} = {total}. Пишем {digit}, {new_carry} {next_place} запоминаем")
            else:
                lines.append(f"{place_name.capitalize()}: {expr} = {total}. Пишем {digit}")
        carry = new_carry
    if carry:
        lines.append(f"В следующем разряде записываем {carry}")
    total = sum(ordered)
    lines.append(f"Читаем ответ: сумма равна {total}")
    return join_explanation_lines(*lines, f"Ответ: {total}", "Совет: в столбике всегда начинай с младшего разряда")


def explain_column_subtraction(minuend: int, subtrahend: int) -> str:
    if subtrahend > minuend:
        return join_explanation_lines(
            "Первое число меньше второго",
            f"Считаем: {minuend} - {subtrahend} = {minuend - subtrahend}",
            f"Ответ: {minuend - subtrahend}",
            "Совет: перед вычитанием сравни числа",
        )
    work = get_digits(minuend)
    sub = get_digits(subtrahend)
    width = max(len(work), len(sub))
    work = [0] * (width - len(work)) + work
    sub = [0] * (width - len(sub)) + sub
    lines = [
        "Пишем числа в столбик: единицы под единицами, десятки под десятками и так далее",
        "Начинаем вычитание с единиц",
    ]
    result = [0] * width

    for pos_from_right in range(width):
        idx = width - 1 - pos_from_right
        top = work[idx]
        bottom = sub[idx]
        place_name = PLACE_NAMES[pos_from_right] if pos_from_right < len(PLACE_NAMES) else "разряд"
        if top >= bottom:
            result[idx] = top - bottom
            lines.append(f"{place_name.capitalize()}: {top} - {bottom} = {result[idx]}")
            continue

        j = idx - 1
        while j >= 0 and work[j] == 0:
            j -= 1
        if j < 0:
            return join_explanation_lines(
                "В этом примере не получается выполнить вычитание обычным способом",
                "Ответ: проверь запись примера",
                "Совет: уменьшаемое должно быть не меньше вычитаемого",
            )

        work[j] -= 1
        for k in range(j + 1, idx):
            work[k] = 9
        work[idx] += 10
        borrowed_value = work[idx]
        if idx - j == 1:
            higher_place = NEXT_PLACE_NAMES[pos_from_right] if pos_from_right < len(NEXT_PLACE_NAMES) else "следующий разряд"
            lines.append(
                f"Из {top} нельзя вычесть {bottom}. Занимаем 1 {higher_place}. Получаем {borrowed_value}. {borrowed_value} - {bottom} = {borrowed_value - bottom}"
            )
        else:
            lines.append(
                f"Из {top} нельзя вычесть {bottom}. Слева есть нули, поэтому занимаем в более старшем разряде. Получаем {borrowed_value}. {borrowed_value} - {bottom} = {borrowed_value - bottom}"
            )
        result[idx] = borrowed_value - bottom
        work[idx] = result[idx]

    answer = int("".join(str(d) for d in result))
    lines.append(f"Читаем ответ: разность равна {answer}")
    return join_explanation_lines(*lines, f"Ответ: {answer}", "Совет: если разряда не хватает, занимаем 1 из соседнего старшего разряда")


def explain_long_multiplication(left: int, right: int) -> str:
    a, b = left, right
    if len(str(abs(a))) < len(str(abs(b))):
        a, b = b, a
    result = a * b
    lines = ["Пишем множители столбиком: единицы под единицами, десятки под десятками и так далее"]
    if abs(b) < 10:
        carry = 0
        digits = get_digits(a)
        for pos_from_right, digit in enumerate(reversed(digits)):
            place_name = PLACE_NAMES[pos_from_right] if pos_from_right < len(PLACE_NAMES) else "разряд"
            total = digit * b + carry
            write_digit = total % 10
            new_carry = total // 10
            if carry:
                if new_carry:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} и ещё {carry} = {total}. Пишем {write_digit}, {new_carry} запоминаем")
                else:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} и ещё {carry} = {total}. Пишем {write_digit}")
            else:
                if new_carry:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} = {total}. Пишем {write_digit}, {new_carry} запоминаем")
                else:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} = {total}. Пишем {write_digit}")
            carry = new_carry
        if carry:
            lines.append(f"В старшем разряде записываем {carry}")
        lines.append(f"Читаем ответ: произведение равно {result}")
        return join_explanation_lines(*lines, f"Ответ: {result}", "Совет: в столбике умножай по разрядам справа налево")

    digits_b = list(reversed(get_digits(b)))
    partials = []
    for idx, digit in enumerate(digits_b):
        place_value = digit * (10 ** idx)
        if digit == 0:
            lines.append(f"В разряде {PLACE_NAMES[idx] if idx < len(PLACE_NAMES) else 'разряда'} второго множителя стоит 0, это неполное произведение пропускаем")
            continue
        partial = a * place_value
        partials.append(partial)
        lines.append(f"Находим неполное произведение: {a} × {place_value} = {partial}")
    if len(partials) > 1:
        lines.append(f"Складываем неполные произведения: {' + '.join(str(p) for p in partials)} = {result}")
    lines.append(f"Читаем ответ: произведение равно {result}")
    return join_explanation_lines(*lines, f"Ответ: {result}", "Совет: в умножении столбиком сначала находят неполные произведения, потом их складывают")


def explain_long_division(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: сначала смотри на делитель")
    quotient, remainder = divmod(dividend, divisor)
    model = build_long_division_steps(dividend, divisor)
    steps = model["steps"]
    lines = ["Пишем деление столбиком", "Сначала находим первое неполное делимое"]
    if not steps:
        lines.append(f"{dividend} меньше {divisor}, значит в частном будет 0")
        if remainder:
            lines.append(f"Остаток равен {remainder}")
        answer_text = "0" if remainder == 0 else f"0, остаток {remainder}"
        return join_explanation_lines(*lines, f"Ответ: {answer_text}", "Совет: если делимое меньше делителя, частное начинается с нуля")

    lines.append(f"Первое неполное делимое — {steps[0]['current']}")
    step_idx = 0
    quotient_started = False
    current = ""
    digits = list(str(dividend))
    for digit_char in digits:
        current += digit_char
        current_number = int(current)
        if current_number < divisor and quotient_started:
            lines.append(f"Число {current_number} меньше {divisor}, поэтому в частном пишем 0 и сносим следующую цифру")
            continue
        if current_number < divisor:
            continue
        quotient_started = True
        step = steps[step_idx]
        q_digit = step["q_digit"]
        product = step["product"]
        remainder_here = step["remainder"]
        next_try = (q_digit + 1) * divisor
        if next_try > current_number:
            choose_line = f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше"
        else:
            choose_line = f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}"
        if step["next_digit"] is not None:
            next_number = int(str(remainder_here) + str(step["next_digit"]))
            lines.append(f"{choose_line}. Вычитаем: {step['current']} - {product} = {remainder_here}. Сносим следующую цифру и получаем {next_number}")
        elif remainder_here == 0:
            lines.append(f"{choose_line}. Вычитаем: {step['current']} - {product} = 0. Деление закончено")
        else:
            lines.append(f"{choose_line}. Вычитаем: {step['current']} - {product} = {remainder_here}. Это остаток")
        current = str(remainder_here)
        step_idx += 1

    if remainder == 0:
        lines.append(f"Читаем ответ: частное равно {quotient}")
        return join_explanation_lines(*lines, f"Ответ: {quotient}", "Совет: в столбике повторяй шаги: взял, подобрал, умножил, вычел, снес цифру")
    lines.append(f"Читаем ответ: частное равно {quotient}, остаток {remainder}")
    return join_explanation_lines(*lines, f"Ответ: {quotient}, остаток {remainder}", "Совет: остаток всегда должен быть меньше делителя")


def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if 0 <= left < 10 and 0 <= right < 10 and total > 10:
        return explain_addition_via_ten(left, right)
    if 10 <= left <= 99 and 10 <= right <= 99:
        lt, lu = split_tens_units(left)
        rt, ru = split_tens_units(right)
        return join_explanation_lines(
            "Ищем сумму",
            f"Разложим числа на десятки и единицы: {left} = {lt} + {lu}, {right} = {rt} + {ru}",
            f"Складываем десятки: {lt} + {rt} = {lt + rt}",
            f"Складываем единицы: {lu} + {ru} = {lu + ru}",
            f"Теперь складываем результаты: {lt + rt} + {lu + ru} = {total}",
            f"Ответ: {total}",
            "Совет: двузначные числа удобно раскладывать на десятки и единицы",
        )
    if left >= 100 or right >= 100:
        return explain_column_addition([left, right])
    return join_explanation_lines("Ищем сумму", f"Считаем: {left} + {right} = {total}", f"Ответ: {total}", "Совет: называй числа по порядку")


def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if 10 < left < 20 and 0 < right < 10 and left % 10 < right:
        return explain_subtraction_via_ten(left, right)
    if 10 <= left <= 99 and 10 <= right <= 99 and result >= 0 and left < 100:
        if left % 10 < right % 10:
            explanation = explain_subtraction_two_digit_with_borrow(left, right)
            if explanation:
                return explanation
        lt, lu = split_tens_units(left)
        rt, ru = split_tens_units(right)
        if lu >= ru:
            return join_explanation_lines(
                "Ищем разность",
                f"Разложим числа на десятки и единицы: {left} = {lt} + {lu}, {right} = {rt} + {ru}",
                f"Вычитаем десятки: {lt} - {rt} = {lt - rt}",
                f"Вычитаем единицы: {lu} - {ru} = {lu - ru}",
                f"Теперь складываем результаты: {lt - rt} + {lu - ru} = {result}",
                f"Ответ: {result}",
                "Совет: двузначные числа удобно раскладывать на десятки и единицы",
            )
    if left >= 100 and right >= 0 and result >= 0:
        return explain_column_subtraction(left, right)
    if result < 0:
        return join_explanation_lines(
            "Сначала сравниваем числа",
            f"{left} меньше {right}, поэтому ответ будет отрицательным",
            f"Считаем: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: перед вычитанием полезно сравнить числа",
        )
    return join_explanation_lines("Ищем разность", f"Считаем: {left} - {right} = {result}", f"Ответ: {result}", "Совет: вычитай спокойно и следи за знаком минус")


def explain_two_digit_by_two_digit_multiplication(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    tens, units = split_tens_units(small)
    first = big * tens
    second = big * units
    result = left * right
    return join_explanation_lines(
        "Ищем произведение",
        f"Разложим {small} на {tens} и {units}",
        f"{big} × {tens} = {first}",
        f"{big} × {units} = {second}",
        f"Складываем частичные результаты: {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: при умножении удобно разложить одно число на десятки и единицы",
    )


def explain_multiply_divide_by_power_of_10(left: int, right: int, op) -> Optional[str]:
    if op is ast.Mult:
        if right in (10, 100, 1000):
            result = left * right
            zeros = len(str(right)) - 1
            return join_explanation_lines(
                f"Умножение на {right}",
                f"При умножении на {right} к числу справа дописываем {zeros} нул{'ь' if zeros == 1 else 'я' if 2 <= zeros <= 4 else 'ей'}",
                f"{left} × {right} = {result}",
                f"Ответ: {result}",
                "Совет: запомни правило умножения на 10, 100, 1000",
            )
        if left in (10, 100, 1000):
            return explain_multiply_divide_by_power_of_10(right, left, op)
    elif op is ast.Div:
        if right in (10, 100, 1000):
            if left % right != 0:
                return None
            result = left // right
            zeros = len(str(right)) - 1
            return join_explanation_lines(
                f"Деление на {right}",
                f"При делении на {right} у числа справа отбрасываем {zeros} нул{'ь' if zeros == 1 else 'я' if 2 <= zeros <= 4 else 'ей'}",
                f"{left} : {right} = {result}",
                f"Ответ: {result}",
                "Совет: запомни правило деления на 10, 100, 1000",
            )
    return None


def explain_two_digit_division(dividend: int, divisor: int) -> Optional[str]:
    if divisor < 10 or dividend < 10 or dividend >= 100 or divisor >= 100:
        return None
    if dividend % divisor != 0:
        return None
    quotient = dividend // divisor
    if quotient >= 10:
        return None
    return join_explanation_lines(
        f"Нужно разделить {dividend} на {divisor}",
        f"Подбираем число, которое при умножении на {divisor} даст {dividend}",
        f"Пробуем: {divisor} × {quotient} = {dividend}",
        f"Значит, {dividend} : {divisor} = {quotient}",
        f"Ответ: {quotient}",
        "Совет: при делении двузначного на двузначное подбирай частное умножением",
    )


def explain_simple_multiplication(left: int, right: int) -> str:
    power10 = explain_multiply_divide_by_power_of_10(left, right, ast.Mult)
    if power10:
        return power10
    result = left * right
    big = max(left, right)
    small = min(left, right)
    if big >= 100:
        return explain_long_multiplication(left, right)
    if 10 <= left <= 99 and 10 <= right <= 99:
        return explain_two_digit_by_two_digit_multiplication(left, right)
    if big >= 10 and small <= 10:
        tens = big - big % 10
        units = big % 10
        return join_explanation_lines(
            "Ищем произведение",
            f"Разбиваем {big} на {tens} и {units}",
            f"{tens} × {small} = {tens * small}",
            f"{units} × {small} = {units * small}",
            f"Теперь складываем части: {tens * small} + {units * small} = {result}",
            f"Ответ: {result}",
            "Совет: умножение удобно разбирать на части",
        )
    return join_explanation_lines("Ищем произведение", f"Считаем: {left} × {right} = {result}", f"Ответ: {result}", "Совет: умножение показывает одинаковые группы")


def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: сначала смотри на делитель")
    power10 = explain_multiply_divide_by_power_of_10(left, right, ast.Div)
    if power10:
        return power10
    quotient, remainder = divmod(left, right)
    if left < 100 and right < 100 and 10 <= right <= 99 and remainder == 0 and quotient < 10:
        two_digit_div = explain_two_digit_division(left, right)
        if two_digit_div:
            return two_digit_div
    if left < 100 and right < 10:
        if remainder == 0:
            return join_explanation_lines(
                "Ищем, на какое число нужно умножить делитель, чтобы получить делимое",
                f"{quotient} × {right} = {left}, значит {left} : {right} = {quotient}",
                f"Ответ: {quotient}",
                "Совет: в простом делении полезно проверять умножением",
            )
        return join_explanation_lines(
            "Ищем, сколько полных раз делитель помещается в делимом",
            f"{quotient} × {right} = {quotient * right}",
            f"Остаток: {left} - {quotient * right} = {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше делителя",
        )
    if left < 100 and right < 100 and remainder == 0:
        return join_explanation_lines(
            "Ищем, на какое число нужно умножить делитель, чтобы получить делимое",
            f"{right} × {quotient} = {left}",
            f"Значит, {left} : {right} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: при делении двузначных чисел помогает подбор и проверка умножением",
        )
    return explain_long_division(left, right)


__all__ = [
    'build_long_division_steps',
    'explain_addition_via_ten',
    'explain_subtraction_via_ten',
    'explain_subtraction_two_digit_with_borrow',
    'explain_column_addition',
    'explain_column_subtraction',
    'explain_long_multiplication',
    'explain_long_division',
    'explain_simple_addition',
    'explain_simple_subtraction',
    'explain_two_digit_by_two_digit_multiplication',
    'explain_multiply_divide_by_power_of_10',
    'explain_two_digit_division',
    'explain_simple_multiplication',
    'explain_simple_division',
]
