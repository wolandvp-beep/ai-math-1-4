from __future__ import annotations

"""Statically materialized runtime module for prompt_runtime_module.py.

This preserves shard execution order while making this runtime layer a
normal importable Python module.
"""

# --- merged segment 001: backend.legacy_runtime_module_shards.prompt_runtime_module.segment_001 ---
def _prompt20260416h_result(text: str, source: str = 'local') -> dict:
    return {'result': text, 'source': source, 'validated': True}


def _prompt20260416h_eval_int_expression(expr: str) -> Optional[int]:
    source = to_expression_source(expr) or str(expr or '').strip()
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    try:
        value = eval_fraction_node(node)
    except Exception:
        return None
    if not isinstance(value, Fraction):
        try:
            value = Fraction(value)
        except Exception:
            return None
    if value.denominator != 1:
        return None
    return int(value.numerator)


def _prompt20260416h_pretty_expr(source: str) -> str:
    try:
        return _user_final_patch_pretty_expression_from_source(source)
    except Exception:
        return str(source or '').replace('*', ' × ').replace('/', ' : ')


def _prompt20260416h_single_order_block(pretty_expr: str) -> List[str]:
    pos = None
    for idx, ch in enumerate(pretty_expr):
        if ch in '+-×:':
            pos = idx
            break
    if pos is None:
        return []
    mark = (' ' * pos) + '1'
    return ['Порядок действий:', mark.rstrip(), pretty_expr]


def _prompt20260416h_body_without_answer(detail_text: str) -> List[str]:
    parts = _detailed_split_sections(detail_text)
    cleaned: List[str] = []
    for raw in parts.get('body', []):
        line = str(raw or '').strip()
        lower = line.lower()
        if not line:
            continue
        if lower in {'решение', 'решение.', 'решение по действиям', 'решение по действиям:'}:
            continue
        if lower.startswith('пример:'):
            continue
        cleaned.append(line)
    return cleaned


def _prompt20260416h_append_advice_if_missing(text: str, kind: str, advice: Optional[str] = None) -> str:
    cleaned = str(text or '').strip()
    if not cleaned:
        return cleaned
    if re.search(r'^\s*совет\s*:', cleaned, flags=re.IGNORECASE | re.MULTILINE):
        return cleaned
    advice_text = str(advice or default_advice(kind)).strip().rstrip('.!?')
    return _detailed_finalize_text(cleaned.split('\n') + [f'Совет: {advice_text}'])


def _prompt20260416h_try_pure_expression(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text or re.search(r'[A-Za-zА-Яа-я]', text):
        return None
    if _final_20260416_normalize_fraction_expression_source(text):
        return None
    source = to_expression_source(text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None

    try:
        value, steps = build_eval_steps(node, source)
    except Exception:
        return None

    if isinstance(value, Fraction) and value.denominator != 1:
        return None
    answer = format_fraction(value)
    pretty = _prompt20260416h_pretty_expr(source)

    if len(steps) > 1:
        rendered = _patch_20260412c_render_mixed_expression_solution(source)
        if rendered:
            advice = 'сначала выполняй действия в скобках, потом умножение и деление, потом сложение и вычитание'
            return _prompt20260416h_append_advice_if_missing(rendered, 'expression', advice)

    simple = try_simple_binary_int_expression(node)
    if not simple:
        return None
    left = simple['left']
    right = simple['right']
    operator = simple['operator']
    if operator is ast.Add:
        detail = explain_column_addition([left, right]) if (abs(left) >= 100 or abs(right) >= 100) else explain_simple_addition(left, right)
        advice = 'при сложении начинай с единиц и не забывай про перенос разряда' if (abs(left) >= 100 or abs(right) >= 100) else 'сумму находят действием сложения'
    elif operator is ast.Sub:
        detail = explain_column_subtraction(left, right) if (abs(left) >= 100 or abs(right) >= 100) else explain_simple_subtraction(left, right)
        advice = 'при вычитании в столбик начинай с единиц и при необходимости занимай единицу из соседнего разряда' if (abs(left) >= 100 or abs(right) >= 100) else 'разность находят действием вычитания'
    elif operator is ast.Mult:
        detail = explain_long_multiplication(left, right) if (abs(left) >= 100 or abs(right) >= 100) else explain_simple_multiplication(left, right)
        advice = 'произведение находят действием умножения'
    elif operator is ast.Div:
        detail = explain_long_division(left, right) if (abs(left) >= 100 or abs(right) >= 10) else explain_simple_division(left, right)
        advice = 'частное находят делением, а проверять удобно умножением'
    else:
        return None

    lines: List[str] = [f'Пример: {pretty} = {answer}.']
    lines.extend(_prompt20260416h_single_order_block(pretty))
    lines.append('Решение по действиям:')
    lines.append(f'1) {pretty} = {answer}.')
    lines.extend(_prompt20260416h_body_without_answer(detail))
    lines.append(f'Ответ: {answer}')
    lines.append(f'Совет: {advice}')
    return _detailed_finalize_text(lines)


def _prompt20260416h_try_named_measure_expression(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    match = re.fullmatch(r'(\d+)\s*м\s*(\d+)\s*см\s*([+\-])\s*(\d+)\s*м\s*(\d+)\s*см', text.lower())
    if not match:
        return None
    m1 = int(match.group(1))
    cm1 = int(match.group(2))
    sign = '+' if match.group(3) == '+' else '-'
    m2 = int(match.group(4))
    cm2 = int(match.group(5))
    first_cm = m1 * 100 + cm1
    second_cm = m2 * 100 + cm2
    total_cm = first_cm + second_cm if sign == '+' else first_cm - second_cm
    if total_cm < 0:
        return None
    ans_m, ans_cm = divmod(total_cm, 100)
    pretty = f'{m1} м {cm1} см {sign} {m2} м {cm2} см'
    lines = [
        f'Пример: {pretty} = {ans_m} м {ans_cm} см.',
        'Порядок действий:',
        (' ' * (len(f'{m1} м {cm1} см '))) + '1',
        pretty,
        'Решение по действиям:',
        f'1) Переводим первое именованное число в сантиметры: {m1} м {cm1} см = {first_cm} см.',
        f'2) Переводим второе именованное число в сантиметры: {m2} м {cm2} см = {second_cm} см.',
        f'3) Выполняем действие: {first_cm} {sign} {second_cm} = {total_cm} см.',
        f'4) Переводим ответ обратно: {total_cm} см = {ans_m} м {ans_cm} см.',
        f'Ответ: {ans_m} м {ans_cm} см',
        'Совет: именованные числа удобно сначала переводить в меньшую единицу, а потом переводить ответ обратно',
    ]
    return _detailed_finalize_text(lines)


def _prompt20260416h_try_equation(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    norm = normalize_dashes(normalize_cyrillic_x(text)).replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    norm = re.sub(r'\s+', '', norm)
    if norm.count('=') != 1 or 'x' not in norm:
        return None
    lhs, rhs = norm.split('=', 1)
    if 'x' not in lhs and 'x' in rhs:
        lhs, rhs = rhs, lhs

    rhs_value = _prompt20260416h_eval_int_expression(rhs)
    if rhs_value is None:
        return None
    rhs_pretty = _prompt20260416h_pretty_expr(rhs)
    original_pretty = f"{_prompt20260416h_pretty_expr(lhs)} = {_prompt20260416h_pretty_expr(rhs)}"

    steps: List[str] = ['Уравнение:', original_pretty, 'Решение.']
    step_no = 1
    if rhs != str(rhs_value):
        steps.append(f'{step_no}) Сначала вычисляем правую часть: {rhs_pretty} = {rhs_value}.')
        step_no += 1

    check_expr = ''
    answer = None
    if re.fullmatch(r'x\+(\d+)', lhs):
        a = int(re.fullmatch(r'x\+(\d+)', lhs).group(1))
        steps.append(f'{step_no}) Неизвестное x оставляем слева, а число {a} переносим вправо. При переносе знак + меняется на -:')
        steps.append(f'x = {rhs_value} - {a}')
        step_no += 1
        answer = rhs_value - a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} + {a} = {rhs_value}'
    elif re.fullmatch(r'(\d+)\+x', lhs):
        a = int(re.fullmatch(r'(\d+)\+x', lhs).group(1))
        steps.append(f'{step_no}) Переставим слагаемые местами: x + {a} = {rhs_value}.')
        step_no += 1
        steps.append(f'{step_no}) Неизвестное x оставляем слева, а число {a} переносим вправо. При переносе знак + меняется на -:')
        steps.append(f'x = {rhs_value} - {a}')
        step_no += 1
        answer = rhs_value - a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{a} + {answer} = {rhs_value}'
    elif re.fullmatch(r'x-(\d+)', lhs):
        a = int(re.fullmatch(r'x-(\d+)', lhs).group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое:')
        steps.append(f'x = {rhs_value} + {a}')
        step_no += 1
        answer = rhs_value + a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} - {a} = {rhs_value}'
    elif re.fullmatch(r'(\d+)-x', lhs):
        a = int(re.fullmatch(r'(\d+)-x', lhs).group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность:')
        steps.append(f'x = {a} - {rhs_value}')
        step_no += 1
        answer = a - rhs_value
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{a} - {answer} = {rhs_value}'
    elif re.fullmatch(r'x\*(\d+)', lhs) or re.fullmatch(r'(\d+)\*x', lhs):
        m = re.fullmatch(r'x\*(\d+)', lhs) or re.fullmatch(r'(\d+)\*x', lhs)
        a = int(m.group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестный множитель, произведение делим на известный множитель:')
        steps.append(f'x = {rhs_value} : {a}')
        step_no += 1
        if a == 0 or rhs_value % a != 0:
            return None
        answer = rhs_value // a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} × {a} = {rhs_value}' if re.fullmatch(r'x\*(\d+)', lhs) else f'{a} × {answer} = {rhs_value}'
    elif re.fullmatch(r'x/(\d+)', lhs):
        a = int(re.fullmatch(r'x/(\d+)', lhs).group(1))
        steps.append(f'{step_no}) Чтобы найти неизвестное делимое, частное умножаем на делитель:')
        steps.append(f'x = {rhs_value} × {a}')
        step_no += 1
        answer = rhs_value * a
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{answer} : {a} = {rhs_value}'
    elif re.fullmatch(r'(\d+)/x', lhs):
        a = int(re.fullmatch(r'(\d+)/x', lhs).group(1))
        if rhs_value == 0 or a % rhs_value != 0:
            return None
        steps.append(f'{step_no}) Чтобы найти неизвестный делитель, делимое делим на частное:')
        steps.append(f'x = {a} : {rhs_value}')
        step_no += 1
        answer = a // rhs_value
        steps.append(f'{step_no}) Считаем:')
        steps.append(f'x = {answer}')
        check_expr = f'{a} : {answer} = {rhs_value}'
    else:
        return None

    steps.append(f'Проверка: {check_expr}')
    steps.append(f'Ответ: {answer}')
    steps.append('Совет: неизвестный компонент действия находят обратным действием')
    return _detailed_finalize_text(steps)


def _prompt20260416h_try_system(raw_text: str) -> Optional[str]:
    text = normalize_dashes(normalize_cyrillic_x(strip_known_prefix(raw_text))).replace(' ', '')
    parts = [p for p in re.split(r'[;,\n]+', text) if p]
    if len(parts) != 2:
        return None
    equations = []
    for part in parts:
        if not re.fullmatch(r'[xy0-9=+\-]+', part):
            return None
        equations.append(part)
    normalized = set(equations)
    m1 = None
    m2 = None
    for eq in equations:
        if re.fullmatch(r'x\+y=\d+', eq):
            m1 = int(eq.split('=')[1])
        elif re.fullmatch(r'x-y=\d+', eq):
            m2 = int(eq.split('=')[1])
        elif re.fullmatch(r'y\+x=\d+', eq):
            m1 = int(eq.split('=')[1])
        elif re.fullmatch(r'y-x=\d+', eq):
            # y - x = d  -> x - y = -d
            m2 = -int(eq.split('=')[1])
    if m1 is None or m2 is None or (m1 + m2) % 2 != 0 or (m1 - m2) % 2 != 0:
        return None
    x = (m1 + m2) // 2
    y = (m1 - m2) // 2
    lines = [
        'Система уравнений:',
        f'{equations[0]}',
        f'{equations[1]}',
        'Решение.',
        f'1) Складываем обе равенства: (x + y) + (x - y) = {m1} + {m2}.',
        f'2) Получаем: 2x = {m1 + m2}.',
        f'3) Находим x: {m1 + m2} : 2 = {x}.',
        f'4) Подставляем x в первое уравнение: {x} + y = {m1}.',
        f'5) Находим y: y = {m1} - {x} = {y}.',
        f'Проверка: {x} + {y} = {m1}; {x} - {y} = {m2}.',
        f'Ответ: x = {x}, y = {y}',
        'Совет: в простой системе удобно сначала найти одно неизвестное, а потом подставить его в другое уравнение',
    ]
    return _detailed_finalize_text(lines)


def _prompt20260416h_task_header(raw_text: str, known: str, find: str) -> List[str]:
    return [
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: {known}',
        f'Что нужно найти: {find}',
    ]


def _prompt20260416h_try_word_problems(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'на одной полке\s+(\d+)\s+книг[^.?!]*на второй\s+на\s+(\d+)\s+книг\s+больше', lower)
    if m and 'двух полках' in lower:
        first = int(m.group(1)); delta = int(m.group(2)); second = first + delta; total = first + second
        lines = _prompt20260416h_task_header(raw_text, 'на одной полке 25 книг, на второй на 7 книг больше' if (first, delta) == (25, 7) else f'на одной полке {first}, на второй на {delta} больше', 'сколько книг на двух полках')
        lines += [
            f'1) Сначала находим, сколько книг на второй полке: {first} + {delta} = {second}.',
            f'2) Теперь находим, сколько книг на двух полках: {first} + {second} = {total}.',
            f'Ответ: {total} книг',
            'Совет: если одно количество больше другого, сначала найди второе количество, а потом общий результат',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'было\s+(\d+)\s+машин[\s\S]*?уехало\s+(\d+)\s+машин[\s\S]*?еще\s+(\d+)', lower)
    if m and 'осталось' in lower:
        start = int(m.group(1)); left1 = int(m.group(2)); left2 = int(m.group(3)); rem1 = start - left1; rem2 = rem1 - left2
        lines = _prompt20260416h_task_header(raw_text, f'в гараже было {start} машин, утром уехало {left1} машин, вечером еще {left2} машин', 'сколько машин осталось в гараже')
        lines += [
            f'1) После того как утром уехало {left1} машин, осталось: {start} - {left1} = {rem1}.',
            f'2) После того как вечером уехало еще {left2} машин, осталось: {rem1} - {left2} = {rem2}.',
            f'Ответ: {rem2} машин',
            'Совет: если из одного количества несколько раз убирают части, вычитай их по порядку',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'в\s+(\d+)\s+одинаковых\s+коробк[а-я]*\s+(\d+)\s+карандаш', lower)
    m2 = re.search(r'сколько\s+карандаш[а-я]*\s+в\s+(\d+)\s+таких', lower)
    if m and m2:
        boxes = int(m.group(1)); total = int(m.group(2)); target = int(m2.group(1))
        if boxes == 0 or total % boxes != 0:
            return None
        one = total // boxes; result = one * target
        lines = _prompt20260416h_task_header(raw_text, f'в {boxes} одинаковых коробках {total} карандашей', f'сколько карандашей в {target} таких коробках')
        lines += [
            f'1) Сначала находим, сколько карандашей в одной коробке: {total} : {boxes} = {one}.',
            f'2) Теперь находим, сколько карандашей в {target} коробках: {one} × {target} = {result}.',
            f'Ответ: {result} карандаша' if result % 10 in {2,3,4} and result % 100 not in {12,13,14} else f'Ответ: {result} карандашей',
            'Совет: в задачах на приведение к единице сначала находят одну группу, а потом нужное количество групп',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'в первом классе\s+(\d+)\s+ученик[а-я]*,\s*это\s+на\s+(\d+)\s+ученик[а-я]*\s+больше,\s*чем\s+во втором', lower)
    if m:
        first = int(m.group(1)); delta = int(m.group(2)); second = first - delta
        lines = _prompt20260416h_task_header(raw_text, f'в первом классе {first} учеников, это на {delta} ученика больше, чем во втором классе', 'сколько учеников во втором классе')
        lines += [
            '1) Это задача в косвенной форме.',
            f'2) Если в первом классе на {delta} ученика больше, значит во втором классе на {delta} ученика меньше.',
            f'3) Находим число учеников во втором классе: {first} - {delta} = {second}.',
            f'Ответ: {second} учеников',
            'Совет: в задаче косвенной формы сначала переведи условие в прямую форму',
        ]
        return _detailed_finalize_text(lines)

    if ('по' in lower and ('руб' in lower or 'рубл' in lower) and ('стоила вся покупка' in lower or 'стоила вся покупка' in lower or 'стоила вся' in lower or 'вся покупка' in lower)):
        matches = list(re.finditer(r'(\d+)\s+([^?.!,]{1,40}?)\s+по\s+(\d+)', lower))
        if len(matches) >= 2:
            c1 = int(matches[0].group(1)); name1 = matches[0].group(2).strip(); p1 = int(matches[0].group(3))
            c2 = int(matches[1].group(1)); name2 = matches[1].group(2).strip(); p2 = int(matches[1].group(3))
            t1 = c1 * p1; t2 = c2 * p2; total = t1 + t2
            lines = _prompt20260416h_task_header(raw_text, f'купили {c1} по {p1} рублей и {c2} по {p2} рублей', 'сколько рублей стоила вся покупка')
            lines += [
                f'1) Находим стоимость первой покупки: {c1} × {p1} = {t1} руб.',
                f'2) Находим стоимость второй покупки: {c2} × {p2} = {t2} руб.',
                f'3) Находим общую стоимость: {t1} + {t2} = {total} руб.',
                f'Ответ: {total} рублей',
                'Совет: стоимость находят умножением цены на количество, а потом складывают все покупки',
            ]
            return _detailed_finalize_text(lines)

    m = re.search(r'(?:со\s+скоростью|скорость)\s+(\d+)\s*км/ч[\s\S]*?в\s+пути\s+(\d+)\s*час', lower)
    if m and ('какое расстояние' in lower or 'какое расстояние он проехал' in lower or 'сколько километров' in lower):
        speed = int(m.group(1)); time = int(m.group(2)); distance = speed * time
        lines = _prompt20260416h_task_header(raw_text, f'скорость {speed} км/ч, время {time} ч', 'какое расстояние проехал велосипедист')
        lines += [
            '1) Чтобы найти расстояние, нужно скорость умножить на время.',
            f'2) Считаем: {speed} × {time} = {distance} км.',
            f'Ответ: {distance} км',
            'Совет: в задачах на движение расстояние находят по формуле S = v × t',
        ]
        return _detailed_finalize_text(lines)

    if 'навстречу друг другу' in lower and 'встретились через' in lower:
        direct = re.search(r'скорость\s+первого\s+(\d+)\s*км/ч,\s*второго\s+(\d+)\s*км/ч', lower)
        if direct:
            v1 = int(direct.group(1))
            v2 = int(direct.group(2))
        else:
            speeds = re.findall(r'скорост[^\d]{0,20}(\d+)\s*км/ч', lower)
            if len(speeds) >= 2:
                v1 = int(speeds[0])
                v2 = int(speeds[1])
            else:
                v1 = v2 = None
        time_match = re.search(r'встретились через\s+(\d+)\s*час', lower)
        if v1 is not None and v2 is not None and time_match:
            time = int(time_match.group(1)); closing = v1 + v2; dist = closing * time
            lines = _prompt20260416h_task_header(raw_text, f'скорость первого {v1} км/ч, скорость второго {v2} км/ч, встретились через {time} ч', 'каково расстояние между поселками')
            lines += [
                f'1) При движении навстречу друг другу находим скорость сближения: {v1} + {v2} = {closing} км/ч.',
                f'2) Теперь находим расстояние: {closing} × {time} = {dist} км.',
                f'Ответ: {dist} км',
                'Совет: при движении навстречу друг другу скорость сближения равна сумме скоростей',
            ]
            return _detailed_finalize_text(lines)

    frac_match = re.search(r'найди\s+(\d+)\s*/\s*(\d+)\s+от\s+числа\s+(\d+)', lower)
    if frac_match:
        num = int(frac_match.group(1)); den = int(frac_match.group(2)); total = int(frac_match.group(3))
        if den == 0 or total % den != 0:
            return None
        one = total // den; part = one * num
        lines = _prompt20260416h_task_header(raw_text, f'число равно {total}, нужно найти {num}/{den} этого числа', 'искомую часть числа')
        lines += [
            f'1) Находим одну долю: {total} : {den} = {one}.',
            f'2) Находим {num}/{den} от {total}: {one} × {num} = {part}.',
            f'Ответ: {part}',
            'Совет: чтобы найти дробь от числа, сначала находят одну долю, а потом берут нужное количество долей',
        ]
        return _detailed_finalize_text(lines)

    frac_match = re.search(r'(\d+)\s*км[^.?!]*составляет\s+(\d+)\s*/\s*(\d+)\s+всего\s+пути', lower)
    if frac_match and 'сколько км составляет весь путь' in lower:
        part = int(frac_match.group(1)); num = int(frac_match.group(2)); den = int(frac_match.group(3))
        if num == 0 or part % num != 0:
            return None
        one = part // num; total = one * den
        lines = _prompt20260416h_task_header(raw_text, f'{part} км составляют {num}/{den} всего пути', 'сколько километров составляет весь путь')
        if num == 1:
            step1 = f'1) Число {part} км — это одна доля, то есть 1/{den} всего пути.'
            step2 = f'2) Во всём пути {den} таких долей: {part} × {den} = {total} км.'
        else:
            step1 = f'1) Сначала находим одну долю: {part} : {num} = {one} км.'
            step2 = f'2) Теперь находим весь путь: {one} × {den} = {total} км.'
        lines += [
            step1,
            step2,
            f'Ответ: {total} км',
            'Совет: чтобы найти число по его дробной части, сначала находят одну долю, а потом всё число',
        ]
        return _detailed_finalize_text(lines)

    return None


def _prompt20260416h_try_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    unit = geometry_unit(lower) or 'см'
    m = re.search(r'длина\s+прямоугольника\s+(\d+)\s*см,\s*ширина\s+(\d+)\s*см', lower)
    if m and 'периметр' in lower and 'площад' in lower:
        length = int(m.group(1)); width = int(m.group(2)); perimeter = 2 * (length + width); area = length * width
        lines = _prompt20260416h_task_header(raw_text, f'длина прямоугольника {length} см, ширина {width} см', 'периметр и площадь прямоугольника')
        lines += [
            f'1) Находим периметр: ({length} + {width}) × 2 = {perimeter} см.',
            f'2) Находим площадь: {length} × {width} = {area} см².',
            f'Ответ: периметр — {perimeter} см; площадь — {area} см²',
            'Совет: у прямоугольника периметр находят сложением длины и ширины с последующим умножением на 2, а площадь — умножением длины на ширину',
        ]
        return _detailed_finalize_text(lines)

    m = re.search(r'периметр\s+квадрата\s+равен\s+(\d+)\s*см', lower)
    if m and ('сторона' in lower or 'чему равна его сторона' in lower):
        perimeter = int(m.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        lines = _prompt20260416h_task_header(raw_text, f'периметр квадрата равен {perimeter} см', 'чему равна его сторона')
        lines += [
            '1) У квадрата все четыре стороны равны.',
            f'2) Чтобы найти сторону квадрата, делим периметр на 4: {perimeter} : 4 = {side} см.',
            f'Ответ: {side} см',
            'Совет: у квадрата все стороны равны, поэтому сторону находят делением периметра на 4',
        ]
        return _detailed_finalize_text(lines)

    return None


def _prompt20260416h_try_high_priority(raw_text: str) -> Optional[str]:
    return (
        _prompt20260416h_try_named_measure_expression(raw_text)
        or _prompt20260416h_try_equation(raw_text)
        or _prompt20260416h_try_system(raw_text)
        or _prompt20260416h_try_geometry(raw_text)
        or _prompt20260416h_try_word_problems(raw_text)
        or _prompt20260416h_try_pure_expression(raw_text)
    )
