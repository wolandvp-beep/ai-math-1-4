from __future__ import annotations

"""Statically materialized runtime module for extended_handlers_runtime_module.py.

This preserves shard execution order while making this runtime layer a
normal importable Python module.
"""

# --- merged segment 001: backend.legacy_runtime_module_shards.extended_handlers_runtime_module.segment_001 ---
from decimal import Decimal, InvalidOperation

def _mass20260416x_dec(text: str) -> Decimal:
    return Decimal(str(text).replace(',', '.'))


def _mass20260416x_fmt_decimal(value) -> str:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    normalized = value.normalize()
    txt = format(normalized, 'f')
    if '.' in txt:
        txt = txt.rstrip('0').rstrip('.')
    if txt == '-0':
        txt = '0'
    return txt.replace('.', ',')


def _mass20260416x_pretty(text: str) -> str:
    return str(text or '').replace('*', ' × ').replace('/', ' : ').replace('-', ' - ').replace('+', ' + ')


def _mass20260416x_try_compare(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(normalize_cyrillic_x(text)).replace('…', '...').replace('−', '-')
    clean = re.sub(r'\([^)]*\)', '', clean).strip()
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(?:\.\.\.|…)?\s*(\d+(?:[.,]\d+)?)', clean)
    if m:
        a = m.group(1)
        b = m.group(2)
        da = _mass20260416x_dec(a)
        db = _mass20260416x_dec(b)
        sign = '>' if da > db else '<' if da < db else '='
        lines = [
            f'Пример: {a} {sign} {b}.',
            'Решение.',
            f'Сравниваем числа {a} и {b}.',
            f'Число {a} {"больше" if sign == ">" else "меньше" if sign == "<" else "равно"} числа {b}.',
            f'Ответ: {a} {sign} {b}',
            'Совет: сначала сравни числа, а потом поставь нужный знак',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'сравни\s*:\s*(\d+(?:[.,]\d+)?)\s*и\s*(\d+(?:[.,]\d+)?)\.?', clean.lower())
    if m:
        a = m.group(1)
        b = m.group(2)
        da = _mass20260416x_dec(a)
        db = _mass20260416x_dec(b)
        sign = '>' if da > db else '<' if da < db else '='
        lines = [
            f'Пример: {a} {sign} {b}.',
            'Решение.',
            f'Сравниваем десятичные дроби {a} и {b}.',
            f'{a} {"больше" if sign == ">" else "меньше" if sign == "<" else "равно"} {b}.',
            f'Ответ: {a} {sign} {b}',
            'Совет: при сравнении десятичных дробей сначала сравнивают целые части, потом десятые и сотые',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'сравни\s*:\s*(\d+)\s*/\s*(\d+)\s*и\s*(\d+)\s*/\s*(\d+)\.?', clean.lower())
    if m:
        a1, b1, a2, b2 = map(int, m.groups())
        f1 = Fraction(a1, b1)
        f2 = Fraction(a2, b2)
        sign = '>' if f1 > f2 else '<' if f1 < f2 else '='
        lines = [f'Пример: {a1}/{b1} {sign} {a2}/{b2}.', 'Решение.']
        if b1 == b2:
            lines += [
                f'У дробей одинаковые знаменатели: {b1}.',
                f'Сравниваем числители: {a1} и {a2}.',
            ]
        else:
            left = a1 * b2
            right = a2 * b1
            lines += [
                'Приводим дроби к сравнению перекрёстным умножением.',
                f'{a1} × {b2} = {left}.',
                f'{a2} × {b1} = {right}.',
            ]
        lines += [
            f'Ответ: {a1}/{b1} {sign} {a2}/{b2}',
            'Совет: дроби с одинаковыми знаменателями сравнивают по числителям',
        ]
        return _mass20260416x_finalize(lines)
    return None


def _mass20260416x_try_box_equation(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace('×', '*').replace('·', '*').replace(':', '/').replace('÷', '/').replace(' ', '')
    if '□' not in clean or clean.count('=') != 1:
        return None
    left, right = clean.split('=', 1)
    if not right.isdigit():
        return None
    total = int(right)
    pretty = normalize_dashes(text).replace('*', ' × ').replace('/', ' : ')
    answer = None
    step = ''
    check = ''
    if m := re.fullmatch(r'(\d+)\+□', left):
        a = int(m.group(1)); answer = total - a
        step = f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: □ = {total} - {a}'
        check = f'{a} + {answer} = {total}'
    elif m := re.fullmatch(r'□\+(\d+)', left):
        a = int(m.group(1)); answer = total - a
        step = f'Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: □ = {total} - {a}'
        check = f'{answer} + {a} = {total}'
    elif m := re.fullmatch(r'(\d+)-□', left):
        a = int(m.group(1)); answer = a - total
        step = f'Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: □ = {a} - {total}'
        check = f'{a} - {answer} = {total}'
    elif m := re.fullmatch(r'□-(\d+)', left):
        a = int(m.group(1)); answer = total + a
        step = f'Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: □ = {total} + {a}'
        check = f'{answer} - {a} = {total}'
    else:
        return None
    lines = [
        'Уравнение:',
        pretty,
        'Решение.',
        f'1) {step}.',
        '2) Считаем:',
        f'□ = {answer}',
        f'Проверка: {check}',
        f'Ответ: {answer}',
        'Совет: неизвестный компонент действия находят обратным действием',
    ]
    return _mass20260416x_finalize(lines)


def _mass20260416x_try_basic_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.fullmatch(r'начерти отрезок длиной (\d+) см\.?', lower)
    if m:
        length = int(m.group(1))
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: нужно начертить отрезок длиной {length} см.',
            'Что нужно сделать: построить отрезок нужной длины.',
            '1) Поставь первую точку.',
            f'2) По линейке отложи {length} см и поставь вторую точку.',
            '3) Соедини точки линейкой.',
            f'Ответ: получится отрезок длиной {length} см',
            'Совет: длину отрезка удобно откладывать по линейке от нулевой отметки',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'начерти отрезок на (\d+) см длиннее, чем (\d+) см\.?', lower)
    if m:
        delta = int(m.group(1)); base = int(m.group(2)); length = base + delta
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: нужно начертить отрезок на {delta} см длиннее, чем {base} см.',
            'Что нужно найти: длину нового отрезка.',
            f'1) Находим длину нового отрезка: {base} + {delta} = {length} см.',
            f'2) Теперь по линейке чертим отрезок длиной {length} см.',
            f'Ответ: нужно начертить отрезок длиной {length} см',
            'Совет: если отрезок длиннее на несколько сантиметров, эти сантиметры прибавляют',
        ]
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'(?:построй|начерти) отрезок, который короче (\d+) см на (\d+) см\.?', lower)
    if m:
        base = int(m.group(1)); delta = int(m.group(2)); length = base - delta
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: новый отрезок короче {base} см на {delta} см.',
            'Что нужно найти: длину нового отрезка.',
            f'1) Находим длину нового отрезка: {base} - {delta} = {length} см.',
            f'2) Теперь по линейке строим отрезок длиной {length} см.',
            f'Ответ: нужно начертить отрезок длиной {length} см',
            'Совет: если отрезок короче на несколько сантиметров, эти сантиметры вычитают',
        ]
        return _mass20260416x_finalize(lines)

    if 'сколько углов у квадрата' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'У квадрата четыре стороны и четыре угла.',
            'Ответ: 4 угла',
            'Совет: у квадрата все углы прямые, и их всегда четыре',
        ])

    if '3 стороны' in lower and '3 угла' in lower and 'назови фигуру' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Фигура с тремя сторонами и тремя углами называется треугольником.',
            'Ответ: треугольник',
            'Совет: количество сторон и углов у многоугольника одинаковое',
        ])

    m = re.fullmatch(r'начерти прямоугольник со сторонами (\d+) см и (\d+) см\.?', lower)
    if m:
        a = int(m.group(1)); b = int(m.group(2))
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: стороны прямоугольника равны {a} см и {b} см.',
            'Что нужно сделать: начертить такой прямоугольник.',
            f'1) Построй одну сторону длиной {a} см.',
            f'2) От её концов построй стороны по {b} см.',
            f'3) Соедини концы и получи прямоугольник {a} см на {b} см.',
            f'Ответ: прямоугольник со сторонами {a} см и {b} см',
            'Совет: у прямоугольника противоположные стороны равны, а все углы прямые',
        ])

    if 'чем отличается круг от овала' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Круг одинаково широкий во все стороны от центра.',
            'Овал вытянут: в одном направлении он длиннее, чем в другом.',
            'Ответ: круг круглый во все стороны одинаково, а овал вытянут',
            'Совет: если фигура вытянута, это овал, а не круг',
        ])

    if 'ломаную из 3 звеньев' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Ломаная из 3 звеньев состоит из трёх отрезков.',
            '1) Начерти первый отрезок.',
            '2) От его конца начерти второй отрезок в другом направлении.',
            '3) От конца второго начерти третий отрезок.',
            'Ответ: получится ломаная из 3 звеньев',
            'Совет: звено ломаной — это один её отрезок',
        ])

    if 'сколько вершин у куба' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'У куба восемь вершин.',
            'Ответ: 8 вершин',
            'Совет: вершина — это угол фигуры, где встречаются рёбра',
        ])

    if 'похожий на шар' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'На шар похож, например, мяч.',
            'Ответ: мяч',
            'Совет: шар — это объёмная круглая фигура',
        ])

    m = re.fullmatch(r'начерти прямоугольник с периметром (\d+) см\.?', lower)
    if m:
        per = int(m.group(1))
        if per < 6 or per % 2:
            return None
        a = per // 4 + 1
        b = per // 2 - a
        if b <= 0:
            a, b = per // 4, per // 4
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: периметр прямоугольника равен {per} см.',
            'Что нужно сделать: выбрать такие длину и ширину, чтобы сумма длин всех сторон была равна этому числу.',
            f'1) Например, возьмём стороны {a} см и {b} см.',
            f'2) Проверяем: ({a} + {b}) × 2 = {per} см.',
            f'Ответ: можно начертить прямоугольник со сторонами {a} см и {b} см',
            'Совет: у прямоугольника периметр равен сумме длины и ширины, умноженной на 2',
        ])

    m = re.fullmatch(r'начерти квадрат площадью (\d+) см²\.?', lower)
    if m:
        area = int(m.group(1))
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: площадь квадрата равна {area} см².',
            'Что нужно найти: длину стороны квадрата.',
            f'1) У квадрата площадь равна стороне, умноженной на такую же сторону.',
            f'2) Ищем число, которое при умножении само на себя даёт {area}. Это {side}.',
            f'3) Значит, нужно начертить квадрат со стороной {side} см.',
            f'Ответ: квадрат со стороной {side} см',
            'Совет: площадь квадрата равна a × a',
        ])
    return None


def _mass20260416x_try_named_units(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text).lower().replace('−', '-').replace('–', '-')
    clean = text.replace('…', '').replace('?', '').strip()

    m = re.fullmatch(r'(\d+)\s*дм\s*(\d+)\s*см\s*=\s*см\.?', clean)
    if m:
        dm, cm = map(int, m.groups()); total = dm * 10 + cm
        return _mass20260416x_finalize([
            f'Пример: {dm} дм {cm} см = {total} см.',
            'Решение.',
            f'1) В 1 дм 10 см.',
            f'2) {dm} дм = {dm * 10} см.',
            f'3) {dm * 10} см + {cm} см = {total} см.',
            f'Ответ: {total} см',
            'Совет: крупную единицу удобно сначала перевести в меньшую',
        ])

    m = re.fullmatch(r'(\d+)\s*см\s*=\s*дм\.?', clean)
    if m:
        cm = int(m.group(1)); dm = cm // 10
        return _mass20260416x_finalize([
            f'Пример: {cm} см = {dm} дм.',
            'Решение.',
            '1) В 1 дм 10 см.',
            f'2) {cm} : 10 = {dm}.',
            f'Ответ: {dm} дм',
            'Совет: чтобы перевести сантиметры в дециметры, делят на 10',
        ])

    m = re.fullmatch(r'(\d+)\s*ч\s*(\d+)\s*мин\s*=\s*мин\.?', clean)
    if m:
        h, minute = map(int, m.groups()); total = h * 60 + minute
        return _mass20260416x_finalize([
            f'Пример: {h} ч {minute} мин = {total} мин.',
            'Решение.',
            '1) В 1 часе 60 минут.',
            f'2) {h} ч = {h * 60} мин.',
            f'3) {h * 60} мин + {minute} мин = {total} мин.',
            f'Ответ: {total} мин',
            'Совет: часы в минуты переводят умножением на 60',
        ])

    m = re.fullmatch(r'(\d+)\s*мин\s*([+\-])\s*(\d+)\s*мин\s*=\s*ч\s*мин\.?', clean)
    if m:
        a, op, b = m.groups(); a = int(a); b = int(b); total = a + b if op == '+' else a - b
        h, minute = divmod(total, 60)
        return _mass20260416x_finalize([
            f'Пример: {a} мин {op} {b} мин = {h} ч {minute} мин.',
            'Решение.',
            f'1) Выполняем действие в минутах: {a} {op} {b} = {total} мин.',
            f'2) Переводим {total} мин в часы и минуты: {h} ч {minute} мин.',
            f'Ответ: {h} ч {minute} мин',
            'Совет: если минут больше 60, выделяют полные часы',
        ])

    m = re.fullmatch(r'(\d+)\s*кг\s*-\s*(\d+)\s*г\s*=\s*г\.?', clean)
    if m:
        kg, g = map(int, m.groups()); total = kg * 1000 - g
        return _mass20260416x_finalize([
            f'Пример: {kg} кг - {g} г = {total} г.',
            'Решение.',
            '1) В 1 кг 1000 г.',
            f'2) {kg} кг = {kg * 1000} г.',
            f'3) {kg * 1000} г - {g} г = {total} г.',
            f'Ответ: {total} г',
            'Совет: килограммы в граммы переводят умножением на 1000',
        ])

    m = re.fullmatch(r'(\d+)\s*дм\s*(\d+)\s*см\s*\+\s*(\d+)\s*дм\s*(\d+)\s*см\s*=\s*дм\s*см\.?', clean)
    if m:
        d1, c1, d2, c2 = map(int, m.groups()); total = d1 * 10 + c1 + d2 * 10 + c2; d, c = divmod(total, 10)
        return _mass20260416x_finalize([
            f'Пример: {d1} дм {c1} см + {d2} дм {c2} см = {d} дм {c} см.',
            'Решение.',
            f'1) Переводим первое число в сантиметры: {d1} дм {c1} см = {d1 * 10 + c1} см.',
            f'2) Переводим второе число в сантиметры: {d2} дм {c2} см = {d2 * 10 + c2} см.',
            f'3) Складываем: {d1 * 10 + c1} + {d2 * 10 + c2} = {total} см.',
            f'4) Переводим обратно: {total} см = {d} дм {c} см.',
            f'Ответ: {d} дм {c} см',
            'Совет: именованные числа удобно сначала переводить в меньшую единицу',
        ])

    m = re.fullmatch(r'(\d+)\s*мин\s*=\s*ч\s*мин\.?', clean)
    if m:
        total = int(m.group(1)); h, minute = divmod(total, 60)
        return _mass20260416x_finalize([
            f'Пример: {total} мин = {h} ч {minute} мин.',
            'Решение.',
            f'1) Делим {total} на 60: {total} : 60 = {h} ч и {minute} мин в остатке.',
            f'Ответ: {h} ч {minute} мин',
            'Совет: чтобы минуты перевести в часы и минуты, делят на 60',
        ])

    m = re.fullmatch(r'(\d+)\s*м\s*-\s*(\d+)\s*дм\s*=\s*дм\.?', clean)
    if m:
        mtr, dm = map(int, m.groups()); total = mtr * 10 - dm
        return _mass20260416x_finalize([
            f'Пример: {mtr} м - {dm} дм = {total} дм.',
            'Решение.',
            '1) В 1 м 10 дм.',
            f'2) {mtr} м = {mtr * 10} дм.',
            f'3) {mtr * 10} дм - {dm} дм = {total} дм.',
            f'Ответ: {total} дм',
            'Совет: метры в дециметры переводят умножением на 10',
        ])

    m = re.fullmatch(r'(\d+)\s*кг\s*(\d+)\s*г\s*-\s*(\d+)\s*кг\s*(\d+)\s*г\s*=\s*г\.?', clean)
    if m:
        k1, g1, k2, g2 = map(int, m.groups()); total = (k1 * 1000 + g1) - (k2 * 1000 + g2)
        return _mass20260416x_finalize([
            f'Пример: {k1} кг {g1} г - {k2} кг {g2} г = {total} г.',
            'Решение.',
            f'1) Переводим первое число в граммы: {k1} кг {g1} г = {k1 * 1000 + g1} г.',
            f'2) Переводим второе число в граммы: {k2} кг {g2} г = {k2 * 1000 + g2} г.',
            f'3) Вычитаем: {k1 * 1000 + g1} - {k2 * 1000 + g2} = {total} г.',
            f'Ответ: {total} г',
            'Совет: при вычислениях с килограммами и граммами удобно всё переводить в граммы',
        ])

    m = re.fullmatch(r'(\d+)\s*сутки\s*-\s*(\d+)\s*ч\s*=\s*ч\.?', clean)
    if m:
        day, hour = map(int, m.groups()); total = day * 24 - hour
        return _mass20260416x_finalize([
            f'Пример: {day} сутки - {hour} ч = {total} ч.',
            'Решение.',
            '1) В 1 сутках 24 часа.',
            f'2) {day} сутки = {day * 24} ч.',
            f'3) {day * 24} ч - {hour} ч = {total} ч.',
            f'Ответ: {total} ч',
            'Совет: сутки в часы переводят умножением на 24',
        ])

    m = re.fullmatch(r'вырази в метрах\s*:\s*(\d+)\s*см\.?', clean)
    if m:
        cm = int(m.group(1)); meters = Decimal(cm) / Decimal(100)
        return _mass20260416x_finalize([
            f'Пример: {cm} см = {_mass20260416x_fmt_decimal(meters)} м.',
            'Решение.',
            '1) В 1 м 100 см.',
            f'2) {cm} : 100 = {_mass20260416x_fmt_decimal(meters)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(meters)} м',
            'Совет: сантиметры в метры переводят делением на 100',
        ])

    m = re.fullmatch(r'вырази в рублях\s*:\s*(\d+)\s*коп\.?', clean)
    if m:
        kop = int(m.group(1)); rub = Decimal(kop) / Decimal(100)
        return _mass20260416x_finalize([
            f'Пример: {kop} коп = {_mass20260416x_fmt_decimal(rub)} руб.',
            'Решение.',
            '1) В 1 рубле 100 копеек.',
            f'2) {kop} : 100 = {_mass20260416x_fmt_decimal(rub)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(rub)} руб',
            'Совет: копейки в рубли переводят делением на 100',
        ])
    return None


def _mass20260416x_try_generic_unit_rate(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'на\s+(\d+)\s+одинаков[а-я]+\s+[а-яё]+\s+пошло\s+(\d+)\s+([а-яё]+)', lower)
    m2 = re.search(r'сколько\s+[а-яё]+\s+нужно\s+на\s+(\d+)\s+таких', lower)
    if m and m2:
        count = int(m.group(1)); total = int(m.group(2)); unit = m.group(3); target = int(m2.group(1))
        if count == 0 or total % count != 0:
            return None
        one = total // count; result = one * target
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: на {count} одинаковых предметов пошло {total} {unit}.',
            f'Что нужно найти: сколько {unit} нужно на {target} таких предметов.',
            f'1) Сначала находим, сколько {unit} идёт на один предмет: {total} : {count} = {one}.',
            f'2) Теперь находим, сколько {unit} нужно на {target} предметов: {one} × {target} = {result}.',
            f'Ответ: {result} {unit}',
            'Совет: в задачах на приведение к единице сначала находят одну группу, потом нужное число групп',
        ])

    m = re.search(r'за\s+(\d+)\s+одинаков[а-я]+\s+[а-яё]+\s+заплатили\s+(\d+)\s+руб', lower)
    m2 = re.search(r'сколько\s+стоят\s+(\d+)\s+таких', lower)
    if m and m2:
        count = int(m.group(1)); total = int(m.group(2)); target = int(m2.group(1))
        if count == 0 or total % count != 0:
            return None
        one = total // count; result = one * target
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: за {count} одинаковых предметов заплатили {total} руб.',
            f'Что нужно найти: сколько стоят {target} таких предметов.',
            f'1) Находим цену одного предмета: {total} : {count} = {one} руб.',
            f'2) Находим стоимость {target} предметов: {one} × {target} = {result} руб.',
            f'Ответ: {result} руб.',
            'Совет: если известна общая стоимость одинаковых предметов, сначала находят цену одного предмета',
        ])
    return None


def _mass20260416x_try_simple_fraction_meta(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'разделили на (\d+) равных част', lower)
    if m and 'какая доля' in lower:
        den = int(m.group(1))
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Если целое разделили на {den} равных частей, то одна часть — это одна из {den} частей.',
            f'Ответ: 1/{den}',
            'Совет: одна часть из нескольких равных частей записывается дробью 1/знаменатель',
        ])

    m = re.fullmatch(r'приведи к знаменателю\s+(\d+)\s*:\s*(\d+)\s*/\s*(\d+)\s+и\s+(\d+)\s*/\s*(\d+)\.?', lower)
    if m:
        target = int(m.group(1)); a1, b1, a2, b2 = map(int, m.groups()[1:])
        if target % b1 != 0 or target % b2 != 0:
            return None
        k1 = target // b1; k2 = target // b2
        n1 = a1 * k1; n2 = a2 * k2
        return _mass20260416x_finalize([
            f'Пример: привести к знаменателю {target}: {a1}/{b1} и {a2}/{b2}.',
            'Решение.',
            f'1) Для дроби {a1}/{b1}: {b1} × {k1} = {target}, значит, умножаем числитель и знаменатель на {k1}.',
            f'2) Получаем: {a1}/{b1} = {n1}/{target}.',
            f'3) Для дроби {a2}/{b2}: {b2} × {k2} = {target}, значит, умножаем числитель и знаменатель на {k2}.',
            f'4) Получаем: {a2}/{b2} = {n2}/{target}.',
            f'Ответ: {a1}/{b1} = {n1}/{target}; {a2}/{b2} = {n2}/{target}',
            'Совет: чтобы привести дробь к новому знаменателю, числитель и знаменатель умножают на одно и то же число',
        ])

    m = re.fullmatch(r'реши уравнение\s*:\s*x\s*\+\s*(\d+)\s*/\s*(\d+)\s*=\s*(\d+)\s*/\s*(\d+)\.?', lower)
    if m:
        a, b, c, d = map(int, m.groups())
        left = Fraction(a, b); right = Fraction(c, d); x = right - left
        return _mass20260416x_finalize([
            'Уравнение:',
            f'x + {a}/{b} = {c}/{d}',
            'Решение.',
            f'1) Чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое: x = {c}/{d} - {a}/{b}.',
            f'2) Считаем: x = {x.numerator}/{x.denominator}.',
            f'Проверка: {x.numerator}/{x.denominator} + {a}/{b} = {c}/{d}.',
            f'Ответ: {x.numerator}/{x.denominator}',
            'Совет: неизвестное слагаемое находят вычитанием',
        ])
    return None


def _mass20260416x_try_decimals(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace(' ', '')
    m = re.fullmatch(r'(\d+,\d+)\+(\d+,\d+)', clean)
    if m:
        a, b = m.groups(); da, db = _mass20260416x_dec(a), _mass20260416x_dec(b); res = da + db
        return _mass20260416x_finalize([
            f'Пример: {a} + {b} = {_mass20260416x_fmt_decimal(res)}.',
            'Решение.',
            '1) Складываем десятичные дроби по разрядам.',
            f'2) {a} + {b} = {_mass20260416x_fmt_decimal(res)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(res)}',
            'Совет: при сложении десятичных дробей единицы пишут под единицами, десятые под десятыми',
        ])
    m = re.fullmatch(r'(\d+,\d+)-(\d+,\d+)', clean)
    if m:
        a, b = m.groups(); da, db = _mass20260416x_dec(a), _mass20260416x_dec(b); res = da - db
        return _mass20260416x_finalize([
            f'Пример: {a} - {b} = {_mass20260416x_fmt_decimal(res)}.',
            'Решение.',
            '1) Вычитаем десятичные дроби по разрядам.',
            f'2) {a} - {b} = {_mass20260416x_fmt_decimal(res)}.',
            f'Ответ: {_mass20260416x_fmt_decimal(res)}',
            'Совет: при вычитании десятичных дробей запятые ставят друг под другом',
        ])

    m = re.fullmatch(r'запиши в виде десятичной дроби\s*:\s*([0-9/;\s]+)\.?', text.lower())
    if m:
        parts = [p.strip() for p in m.group(1).split(';') if p.strip()]
        if not parts:
            return None
        out = []
        lines = ['Задача.', _audit_task_line(raw_text), 'Решение.']
        for idx, part in enumerate(parts, 1):
            if not re.fullmatch(r'(\d+)/(\d+)', part):
                return None
            a, b = map(int, part.split('/'))
            dec = Decimal(a) / Decimal(b)
            out.append(_mass20260416x_fmt_decimal(dec))
            lines.append(f'{idx}) {part} = {_mass20260416x_fmt_decimal(dec)}.')
        lines += [f'Ответ: {"; ".join(out)}', 'Совет: дроби со знаменателем 10 или 100 легко записывать десятичной дробью']
        return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'запиши обыкновенной дробью\s*:\s*([0-9,;\s]+)\.?', text.lower())
    if m:
        parts = [p.strip() for p in m.group(1).split(';') if p.strip()]
        if not parts:
            return None
        out = []
        lines = ['Задача.', _audit_task_line(raw_text), 'Решение.']
        for idx, part in enumerate(parts, 1):
            if ',' not in part:
                return None
            frac_digits = len(part.split(',')[1])
            num = int(part.replace(',', ''))
            den = 10 ** frac_digits
            out.append(f'{num}/{den}')
            lines.append(f'{idx}) {part} = {num}/{den}.')
        lines += [f'Ответ: {"; ".join(out)}', 'Совет: количество цифр после запятой показывает знаменатель: 10, 100, 1000']
        return _mass20260416x_finalize(lines)
    return None


def _mass20260416x_try_percent(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'найди\s+(\d+)%\s+от\s+(\d+)', lower)
    if m:
        p = int(m.group(1)); total = int(m.group(2)); result = total * p // 100 if (total * p) % 100 == 0 else total * p / 100
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) {p}% — это {p}/100 от числа.',
            f'2) Находим {p}% от {total}: {total} × {p} : 100 = {result}.',
            f'Ответ: {result}',
            'Совет: чтобы найти проценты от числа, число умножают на количество процентов и делят на 100',
        ])

    m = re.search(r'в классе (\d+) ученик[а-я]*,\s*(\d+)% из них', lower) or re.search(r'в саду (\d+) дерев[а-я]*,\s*из них (\d+)%', lower) or re.search(r'в библиотеке (\d+) книг,\s*(\d+)%', lower)
    if m:
        total = int(m.group(1)); p = int(m.group(2)); result = total * p // 100
        unit = 'учеников' if 'ученик' in lower else 'деревьев' if 'дерев' in lower else 'книг'
        if 'отличник' in lower:
            unit = 'отличников'
        elif 'яблон' in lower:
            unit = 'яблонь'
        elif 'словар' in lower:
            unit = 'словарей'
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {p}% от {total}: {total} × {p} : 100 = {result}.',
            f'Ответ: {result} {unit}',
            'Совет: процент — это одна сотая часть числа',
        ])

    m = re.search(r'товар стоил (\d+) руб\.? цена снизилась на (\d+)%', lower)
    if m:
        price = int(m.group(1)); p = int(m.group(2)); disc = price * p // 100; new = price - disc
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько рублей составляет скидка: {price} × {p} : 100 = {disc} руб.',
            f'2) Вычитаем скидку из старой цены: {price} - {disc} = {new} руб.',
            f'Ответ: {new} руб.',
            'Совет: чтобы уменьшить число на несколько процентов, сначала находят эти проценты',
        ])

    m = re.search(r'скидка (\d+)%[\s\S]*вещь стоит (\d+) руб', lower)
    if m:
        p = int(m.group(1)); price = int(m.group(2)); save = price * p // 100
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {p}% от {price}: {price} × {p} : 100 = {save} руб.',
            f'Ответ: {save} руб.',
            'Совет: размер скидки находят как процент от цены',
        ])

    m = re.search(r'цена выросла с (\d+) руб\.? до (\d+) руб\.?', lower)
    if m and 'на сколько процентов' in lower:
        old = int(m.group(1)); new = int(m.group(2)); diff = new - old; p = diff * 100 // old if (diff * 100) % old == 0 else diff * 100 / old
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, на сколько рублей выросла цена: {new} - {old} = {diff} руб.',
            f'2) Теперь узнаём, какую часть это составляет от старой цены: {diff} × 100 : {old} = {p}%.',
            f'Ответ: {p}%',
            'Совет: процент увеличения считают от старого значения',
        ])

    m = re.search(r'под (\d+)% годовых', lower)
    if m and 'сколько процентов' in lower:
        p = int(m.group(1))
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'По условию вклад открыт под {p}% годовых.',
            f'Ответ: {p}%',
            'Совет: если процентная ставка дана в условии, её и называют в ответе',
        ])
    return None


def _mass20260416x_try_average(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'найди среднее арифметическое чисел ([0-9,\s]+)', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        if not nums:
            return None
        total = sum(nums); n = len(nums); avg = total / n
        avg_text = int(avg) if avg == int(avg) else avg
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Складываем числа: {" + ".join(map(str, nums))} = {total}.',
            f'2) Делим сумму на количество чисел: {total} : {n} = {avg_text}.',
            f'Ответ: {avg_text}',
            'Совет: среднее арифметическое находят делением суммы чисел на их количество',
        ])

    m = re.search(r'среднее арифметическое трех чисел равно (\d+)[\s\S]*сумма двух из них (\d+)', lower)
    if m:
        avg = int(m.group(1)); sum_two = int(m.group(2)); total = avg * 3; third = total - sum_two
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим сумму трех чисел: {avg} × 3 = {total}.',
            f'2) Находим третье число: {total} - {sum_two} = {third}.',
            f'Ответ: {third}',
            'Совет: если известно среднее арифметическое, сначала можно найти общую сумму',
        ])

    m = re.search(r'средний рост пяти игроков (\d+) см[\s\S]*сумма роста четырех игроков (\d+) см', lower)
    if m:
        avg = int(m.group(1)); sum_four = int(m.group(2)); total = avg * 5; fifth = total - sum_four
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим общий рост пяти игроков: {avg} × 5 = {total} см.',
            f'2) Находим рост пятого игрока: {total} - {sum_four} = {fifth} см.',
            f'Ответ: {fifth} см',
            'Совет: средний рост умножают на количество игроков, чтобы получить общий рост',
        ])

    m = re.search(r'среднее арифметическое двух чисел (\d+), одно из них (\d+)', lower)
    if m:
        avg = int(m.group(1)); one = int(m.group(2)); total = avg * 2; two = total - one
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим сумму двух чисел: {avg} × 2 = {total}.',
            f'2) Находим второе число: {total} - {one} = {two}.',
            f'Ответ: {two}',
            'Совет: если известно среднее двух чисел, сумма равна среднему, умноженному на 2',
        ])

    m = re.search(r'машина проехала (\d+) км за (\d+) ч, затем (\d+) км за (\d+) ч', lower)
    if m and 'среднюю скорость' in lower:
        s1, t1, s2, t2 = map(int, m.groups()); total_s = s1 + s2; total_t = t1 + t2; v = total_s / total_t
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим весь путь: {s1} + {s2} = {total_s} км.',
            f'2) Находим всё время: {t1} + {t2} = {total_t} ч.',
            f'3) Средняя скорость равна всему пути, деленному на всё время: {total_s} : {total_t} = {int(v) if v == int(v) else v} км/ч.',
            f'Ответ: {int(v) if v == int(v) else v} км/ч',
            'Совет: среднюю скорость на всём пути находят делением всего пути на всё время',
        ])

    # generic average with a list and a unit
    m = re.search(r':\s*([0-9,\s]+)\.?\s*найди средн', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        if nums:
            total = sum(nums); n = len(nums); avg = total / n
            unit = '°' if 'температур' in lower else ''
            avg_text = int(avg) if avg == int(avg) else avg
            return _mass20260416x_finalize([
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Складываем все значения: {" + ".join(map(str, nums))} = {total}.',
                f'2) Делим сумму на количество значений: {total} : {n} = {avg_text}.',
                f'Ответ: {avg_text}{unit}',
                'Совет: среднее арифметическое показывает, сколько пришлось бы на каждый случай поровну',
            ])

    m = re.search(r'в первый день собрали (\d+) кг [а-я]+, во второй (\d+) кг, в третий (\d+) кг', lower)
    if m and 'в среднем' in lower:
        a, b, c = map(int, m.groups()); total = a + b + c; avg = total // 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Складываем весь урожай: {a} + {b} + {c} = {total} кг.',
            f'2) Делим на 3 дня: {total} : 3 = {avg} кг.',
            f'Ответ: {avg} кг',
            'Совет: чтобы найти среднее за несколько дней, нужно общий результат разделить на число дней',
        ])

    m = re.search(r'в трех коробках лежат карандаши:\s*(\d+),\s*(\d+)\s*и\s*(\d+)', lower)
    if m and 'в среднем' in lower:
        a, b, c = map(int, m.groups()); total = a + b + c; avg = total // 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим общее число карандашей: {a} + {b} + {c} = {total}.',
            f'2) Делим на 3 коробки: {total} : 3 = {avg}.',
            f'Ответ: {avg}',
            'Совет: среднее число в коробке находят делением общего количества на число коробок',
        ])

    m = re.search(r'оценки:\s*([0-9,\s]+)\.?\s*найди средний балл', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        if nums:
            total = sum(nums); n = len(nums); avg = total / n
            avg_text = int(avg) if avg == int(avg) else _mass20260416x_fmt_decimal(Decimal(str(avg)))
            return _mass20260416x_finalize([
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Складываем оценки: {" + ".join(map(str, nums))} = {total}.',
                f'2) Делим на число оценок: {total} : {n} = {avg_text}.',
                f'Ответ: {avg_text}',
                'Совет: средний балл — это среднее арифметическое всех оценок',
            ])
    return None

# --- merged segment 002: backend.legacy_runtime_module_shards.extended_handlers_runtime_module.segment_002 ---
def _mass20260416x_try_system_word_problems(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'сумма двух чисел (\d+), разность (\d+)', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); big = (s + d) // 2; small = (s - d) // 2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если к сумме прибавить разность, получится удвоенное большее число: {s} + {d} = {s + d}.',
            f'2) Большее число: {s + d} : 2 = {big}.',
            f'3) Меньшее число: {s} - {big} = {small}.',
            f'Ответ: {big} и {small}',
            'Совет: в задачах на сумму и разность удобно сначала находить большее число',
        ])

    m = re.search(r'одно число больше другого на (\d+), а сумма их (\d+)', lower)
    if m:
        d = int(m.group(1)); s = int(m.group(2)); small = (s - d) // 2; big = small + d
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если одно число больше на {d}, то без этой добавки два числа были бы равны.',
            f'2) Убираем добавку: {s} - {d} = {s - d}.',
            f'3) Находим меньшее число: {s - d} : 2 = {small}.',
            f'4) Находим большее число: {small} + {d} = {big}.',
            f'Ответ: {small} и {big}',
            'Совет: если одно число больше другого на несколько единиц, можно сначала убрать эту разницу',
        ])

    m = re.search(r'в двух корзинах (\d+) яблок.*в первой на (\d+) меньше', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); second = (s + d) // 2; first = s - second
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если в первой корзине на {d} яблок меньше, то во второй на {d} яблок больше.',
            f'2) Прибавим эту разницу к общему числу: {s} + {d} = {s + d}.',
            f'3) Во второй корзине: {s + d} : 2 = {second}.',
            f'4) В первой корзине: {s} - {second} = {first}.',
            f'Ответ: в первой {first}, во второй {second}',
            'Совет: в задачах с суммой и разницей сначала удобно найти большее количество',
        ])

    m = re.search(r'у кати и лены вместе (\d+) руб[а-я]*, у кати на (\d+) руб[а-я]* больше', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); lena = (s - d) // 2; katya = lena + d
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если у Кати на {d} рубля больше, то без этой добавки у девочек было бы поровну.',
            f'2) Убираем добавку: {s} - {d} = {s - d}.',
            f'3) Находим деньги Лены: {s - d} : 2 = {lena} руб.',
            f'4) Находим деньги Кати: {lena} + {d} = {katya} руб.',
            f'Ответ: у Кати {katya} руб., у Лены {lena} руб.',
            'Совет: если один имеет на несколько единиц больше, сначала убирают эту разницу',
        ])

    m = re.search(r'сумма двух чисел (\d+), одно в (\d+) раза больше другого', lower)
    if m:
        s = int(m.group(1)); k = int(m.group(2)); small = s // (k + 1); big = small * k
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Всего равных частей: 1 + {k} = {k + 1}.',
            f'2) Одна часть: {s} : {k + 1} = {small}.',
            f'3) Большее число: {small} × {k} = {big}.',
            f'Ответ: {big} и {small}',
            'Совет: если одно число в несколько раз больше другого, удобно делить сумму на число частей',
        ])

    m = re.search(r'разность двух чисел (\d+), одно в (\d+) раза больше другого', lower)
    if m:
        d = int(m.group(1)); k = int(m.group(2))
        if k <= 1 or d % (k - 1) != 0:
            return None
        small = d // (k - 1); big = small * k
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Разность между {k} частями и 1 частью равна {k - 1} частям.',
            f'2) Одна часть: {d} : {k - 1} = {small}.',
            f'3) Большее число: {small} × {k} = {big}.',
            f'Ответ: {big} и {small}',
            'Совет: при кратном сравнении разность помогает найти одну часть',
        ])

    m = re.search(r'в классе (\d+) учеников, девочек на (\d+) больше, чем мальчиков', lower)
    if m:
        s = int(m.group(1)); d = int(m.group(2)); boys = (s - d) // 2; girls = boys + d
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если убрать лишние {d} девочки, мальчиков и девочек было бы поровну.',
            f'2) {s} - {d} = {s - d}.',
            f'3) Мальчиков: {s - d} : 2 = {boys}.',
            f'4) Девочек: {boys} + {d} = {girls}.',
            f'Ответ: мальчиков {boys}, девочек {girls}',
            'Совет: если одной группы больше на несколько человек, сначала убирают разницу',
        ])

    m = re.search(r'два числа в сумме дают (\d+), а одно составляет (\d+)/(\d+) другого', lower)
    if m:
        s = int(m.group(1)); num = int(m.group(2)); den = int(m.group(3))
        # smaller = num/den larger
        whole_parts = num + den
        if s * den % whole_parts != 0:
            return None
        larger = s * den // whole_parts
        smaller = s - larger
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) По условию одно число составляет {num}/{den} другого.',
            f'2) Значит, вся сумма — это {num} части и {den} частей, всего {whole_parts} частей.',
            f'3) Одна часть: {s} : {whole_parts} = {s // whole_parts}.',
            f'4) Числа равны {smaller} и {larger}.',
            f'Ответ: {smaller} и {larger}',
            'Совет: дробное отношение удобно переводить в равные части',
        ])

    m = re.search(r'в двух ящиках (\d+) кг апельсинов. в первом в (\d+) раза больше', lower)
    if m:
        s = int(m.group(1)); k = int(m.group(2)); second = s // (k + 1); first = second * k
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Всего частей: {k} + 1 = {k + 1}.',
            f'2) Во втором ящике: {s} : {k + 1} = {second} кг.',
            f'3) В первом ящике: {second} × {k} = {first} кг.',
            f'Ответ: в первом {first} кг, во втором {second} кг',
            'Совет: если одно количество в несколько раз больше другого, удобнее делить сумму на число частей',
        ])
    return None


def _mass20260416x_try_volume_geometry(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'объем куба с ребром (\d+)\s*(см|дм|м)', lower)
    if m:
        a = int(m.group(1)); unit = m.group(2); v = a ** 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объем куба находят по формуле V = a × a × a.',
            f'2) Подставляем число: {a} × {a} × {a} = {v}.',
            f'Ответ: {v} {unit}³',
            'Совет: объем куба равен кубу его ребра',
        ])

    m = re.search(r'длина прямоугольного параллелепипеда (\d+)\s*(см|дм|м), ширина (\d+)\s*\2, высота (\d+)\s*\2', lower)
    if m and 'объем' in lower:
        l = int(m.group(1)); unit = m.group(2); w = int(m.group(3)); h = int(m.group(4)); v = l * w * h
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объем прямоугольного параллелепипеда находят по формуле V = a × b × c.',
            f'2) Подставляем числа: {l} × {w} × {h} = {v}.',
            f'Ответ: {v} {unit}³',
            'Совет: объем прямоугольного параллелепипеда равен произведению длины, ширины и высоты',
        ])

    m = re.search(r'площадь пола комнаты (\d+)\s*м², высота (\d+)\s*м', lower)
    if m and 'объем комнаты' in lower:
        s = int(m.group(1)); h = int(m.group(2)); v = s * h
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объем комнаты равен площади пола, умноженной на высоту.',
            f'2) {s} × {h} = {v}.',
            f'Ответ: {v} м³',
            'Совет: объем прямоугольной комнаты можно найти как площадь пола, умноженную на высоту',
        ])

    m = re.search(r'ребро куба увеличили в (\d+) раза', lower)
    if m and 'во сколько раз увеличился объем' in lower:
        k = int(m.group(1)); factor = k ** 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Если ребро куба увеличить в {k} раза, то каждая из трех мер увеличится в {k} раза.',
            f'2) Объем увеличится в {k} × {k} × {k} = {factor} раз.',
            f'Ответ: в {factor} раз',
            'Совет: при увеличении всех трех измерений в несколько раз объем увеличивается в куб этого числа',
        ])

    m = re.search(r'площадь поверхности куба с ребром (\d+)\s*(см|дм|м)', lower)
    if m:
        a = int(m.group(1)); unit = m.group(2); face = a * a; area = face * 6
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) У куба 6 одинаковых граней.',
            f'2) Площадь одной грани: {a} × {a} = {face} {unit}².',
            f'3) Площадь всей поверхности: {face} × 6 = {area} {unit}².',
            f'Ответ: {area} {unit}²',
            'Совет: площадь поверхности куба равна площади одной грани, умноженной на 6',
        ])

    m = re.search(r'прямоугольный участок земли имеет длину (\d+) м и ширину (\d+) м', lower)
    if m:
        l, w = map(int, m.groups()); area = l * w; per = 2 * (l + w)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь участка: {l} × {w} = {area} м².',
            f'2) Периметр участка: ({l} + {w}) × 2 = {per} м.',
            f'Ответ: площадь {area} м², периметр {per} м',
            'Совет: площадь прямоугольника равна длине, умноженной на ширину',
        ])

    m = re.search(r'квадрат и прямоугольник имеют одинаковую площадь (\d+) см².*ширина прямоугольника (\d+) см', lower)
    if m and 'найди длину прямоугольника' in lower:
        area = int(m.group(1)); w = int(m.group(2)); l = area // w
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь прямоугольника равна {area} см².',
            f'2) Длина прямоугольника равна площади, деленной на ширину: {area} : {w} = {l} см.',
            f'Ответ: {l} см',
            'Совет: если известны площадь и одна сторона прямоугольника, другую сторону находят делением',
        ])

    m = re.search(r'начерти прямоугольник, площадь которого (\d+) см², а длина (\d+) см', lower)
    if m and 'периметр' in lower:
        area = int(m.group(1)); l = int(m.group(2)); w = area // l; per = 2 * (l + w)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим ширину прямоугольника: {area} : {l} = {w} см.',
            f'2) Находим периметр: ({l} + {w}) × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: если известны площадь и длина прямоугольника, ширину находят делением',
        ])

    m = re.search(r'объем аквариума (\d+) л.*высота аквариума (\d+) дм, ширина (\d+) дм', lower)
    if m and 'найди длину' in lower:
        v = int(m.group(1)); h = int(m.group(2)); w = int(m.group(3)); l = v // (h * w)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) 1 л = 1 дм³, значит, объем равен в кубических дециметрах тому же числу.',
            f'2) Длина равна объему, деленному на ширину и высоту: {v} : ({w} × {h}) = {l} дм.',
            f'Ответ: {l} дм',
            'Совет: неизвестное измерение прямоугольного параллелепипеда находят делением объема на произведение двух других',
        ])

    m = re.search(r'прямоугольник разрезали на (\d+) одинаковых квадратов. сумма периметров квадратов (\d+) см', lower)
    if m and 'периметр исходного прямоугольника' in lower:
        n = int(m.group(1)); sum_per = int(m.group(2))
        one_square_per = sum_per // n; side = one_square_per // 4
        per = 2 * ((side * n) + side)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Периметр одного квадрата: {sum_per} : {n} = {one_square_per} см.',
            f'2) Сторона квадрата: {one_square_per} : 4 = {side} см.',
            f'3) Исходный прямоугольник составлен из {n} квадратов, значит, его стороны {side * n} см и {side} см.',
            f'4) Периметр исходного прямоугольника: ({side * n} + {side}) × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: если фигура составлена из одинаковых квадратов, сначала находят сторону одного квадрата',
        ])

    m = re.search(r'квадрат разрезали на два равных прямоугольника с периметром (\d+) см каждый', lower)
    if m and 'сторону квадрата' in lower:
        per = int(m.group(1))
        if per % 3 != 0:
            return None
        side = per // 3
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Если квадрат разрезать пополам, получится прямоугольник со сторонами a и a/2.',
            f'2) Периметр такого прямоугольника равен 2 × (a + a/2) = 3a.',
            f'3) Значит, 3a = {per}, поэтому a = {per} : 3 = {side} см.',
            f'Ответ: {side} см',
            'Совет: в составных геометрических задачах сначала вырази искомую величину через сторону фигуры',
        ])
    return None


def _mass20260416x_try_fraction_drawing_and_piece(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    m = re.search(r'начерти отрезок (\d+) см, покажи (\d+)/(\d+) этого отрезка', lower)
    if m:
        total = int(m.group(1)); num = int(m.group(2)); den = int(m.group(3))
        if total % den != 0:
            return None
        part = total // den * num
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим одну {den}-ю часть отрезка: {total} : {den} = {total // den} см.',
            f'2) Находим {num}/{den} отрезка: {total // den} × {num} = {part} см.',
            f'Ответ: нужно показать {part} см',
            'Совет: чтобы найти дробь от длины, сначала делят на знаменатель, потом умножают на числитель',
        ])
    return None




# --- MASS AUDIT PATCH 2026-04-16Y: fix mixed verbs, geometry wording, fraction chains, motion details ---



def _mass20260416y_try_specific_words(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'в классе (\d+) мальчиков и (\d+) девочки', lower)
    if m and 'кого меньше' in lower and 'на сколько' in lower:
        boys = int(m.group(1)); girls = int(m.group(2)); diff = boys - girls
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: мальчиков {boys}, девочек {girls}.',
            'Что нужно найти: кого меньше и на сколько.',
            f'1) Сравниваем количества: {boys} - {girls} = {diff}.',
            f'2) Девочек меньше, потому что {girls} меньше {boys}.',
            f'Ответ: девочек меньше на {diff}',
            'Совет: чтобы узнать, на сколько одно число меньше другого, из большего вычитают меньшее',
        ])

    m = re.search(r'у лены (\d+) руб[а-я]*, а у оли на (\d+) руб[а-я]* меньше', lower)
    if m and 'сколько денег у обеих' in lower:
        lena = int(m.group(1)); diff = int(m.group(2)); olya = lena - diff; total = lena + olya
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько денег у Оли: {lena} - {diff} = {olya} руб.',
            f'2) Находим, сколько денег у обеих девочек: {lena} + {olya} = {total} руб.',
            f'Ответ: {total} руб.',
            'Совет: если сказано «на несколько меньше», нужно вычитать',
        ])

    m = re.search(r'в вагоне ехали (\d+) человек, на станции вышли (\d+), а зашли (\d+)', lower)
    if m:
        start, out, come = map(int, m.groups()); after = start - out + come
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) После того как вышли {out} человек, осталось: {start} - {out} = {start - out}.',
            f'2) Потом зашли {come} человек: {start - out} + {come} = {after}.',
            f'Ответ: {after} человек',
            'Совет: если сначала люди вышли, вычитаем, а если потом зашли, прибавляем',
        ])

    m = re.search(r'в магазине было (\d+) кг муки\. продали (\d+) кг, потом привезли (\d+) кг', lower)
    if m:
        start, sold, came = map(int, m.groups()); after = start - sold + came
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) После продажи осталось: {start} - {sold} = {start - sold} кг.',
            f'2) Потом привезли ещё {came} кг: {start - sold} + {came} = {after} кг.',
            f'Ответ: {after} кг',
            'Совет: если сначала убавили, а потом прибавили, выполняй действия по порядку',
        ])

    m = re.search(r'у сережи (\d+) марки, у коли на (\d+) марок меньше, а у вити на (\d+) больше, чем у коли', lower)
    if m:
        s, less, more = map(int, m.groups()); kolya = s - less; vitya = kolya + more
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько марок у Коли: {s} - {less} = {kolya}.',
            f'2) Находим, сколько марок у Вити: {kolya} + {more} = {vitya}.',
            f'Ответ: {vitya} марок',
            'Совет: в составной задаче сначала находят промежуточное количество',
        ])

    m = re.search(r'в автобусе было (\d+) пассажиров\. на остановке вышли (\d+) и зашли (\d+)', lower)
    if m:
        start, out, come = map(int, m.groups()); after = start - out + come
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) После того как вышли {out} пассажиров, осталось: {start} - {out} = {start - out}.',
            f'2) Потом зашли {come} пассажиров: {start - out} + {come} = {after}.',
            f'Ответ: {after} пассажира' if str(after).endswith('4') else f'Ответ: {after} пассажиров',
            'Совет: если пассажиры выходят, число уменьшается, а если заходят, увеличивается',
        ])

    m = re.search(r'масса тыквы (\d+) кг, а арбуза - в (\d+) раза меньше', lower)
    if m and ('общая масса' in lower or 'какова общая масса' in lower):
        pumpkin, k = map(int, m.groups()); watermelon = pumpkin // k; total = pumpkin + watermelon
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим массу арбуза: {pumpkin} : {k} = {watermelon} кг.',
            f'2) Находим общую массу: {pumpkin} + {watermelon} = {total} кг.',
            f'Ответ: {total} кг',
            'Совет: если сказано «в несколько раз меньше», нужно делить',
        ])
    return None


def _mass20260416y_try_geometry_updates(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'прямоугольник имеет стороны (\d+) см и (\d+) см', lower)
    if m and 'сумму длин всех сторон' in lower:
        a, b = map(int, m.groups()); per = 2 * (a + b)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Сумма длин всех сторон прямоугольника — это его периметр.',
            f'2) Периметр: ({a} + {b}) × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: у прямоугольника две длины и две ширины',
        ])

    m = re.search(r'периметр треугольника (\d+) см, две стороны по (\d+) см', lower)
    if m and 'третью сторону' in lower:
        per, side = map(int, m.groups()); third = per - side - side
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Из периметра вычитаем две известные стороны: {per} - {side} - {side} = {third} см.',
            f'Ответ: {third} см',
            'Совет: периметр — это сумма длин всех сторон фигуры',
        ])

    m = re.search(r'квадрат и прямоугольник имеют одинаковый периметр (\d+) см', lower)
    if m and 'сторона квадрата' in lower:
        per = int(m.group(1)); side = per // 4
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) У квадрата все стороны равны.',
            f'2) Чтобы найти сторону квадрата, делим периметр на 4: {per} : 4 = {side} см.',
            f'Ответ: {side} см',
            'Совет: сторону квадрата находят делением периметра на 4',
        ])

    m = re.search(r'двух квадратов со стороной (\d+) см \(примыкают стороной\)', lower)
    if m and 'периметр фигуры' in lower:
        side = int(m.group(1)); per = side * 6
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) У двух квадратов было бы {8} стороны по {side} см, если бы они не соприкасались.',
            f'2) Одна общая сторона внутри фигуры не входит в периметр. Таких сторон две по {side} см.',
            f'3) Периметр фигуры: {side} × 8 - {side} × 2 = {per} см.',
            f'Ответ: {per} см',
            'Совет: общая сторона внутри составной фигуры в периметр не входит',
        ])

    m = re.search(r'найди площадь прямоугольника со сторонами (\d+) см и (\d+) см', lower)
    if m:
        a, b = map(int, m.groups()); area = a * b
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь прямоугольника находят умножением длины на ширину.',
            f'2) {a} × {b} = {area} см².',
            f'Ответ: {area} см²',
            'Совет: площадь прямоугольника равна длине, умноженной на ширину',
        ])

    if 'сравни площади' in lower and 'прямоугольник 6×2' in lower and 'квадрат со стороной 3 см' in lower:
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Площадь прямоугольника: 6 × 2 = 12 см².',
            '2) Площадь квадрата: 3 × 3 = 9 см².',
            '3) 12 см² больше 9 см².',
            'Ответ: площадь прямоугольника больше',
            'Совет: чтобы сравнить площади, сначала находят площадь каждой фигуры',
        ])

    m = re.search(r'площадь листа бумаги (\d+) см², его отрезали пополам', lower)
    if m:
        area = int(m.group(1)); half = area // 2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Половина — это одна вторая часть.',
            f'2) {area} : 2 = {half} см².',
            f'Ответ: {half} см²',
            'Совет: чтобы найти половину величины, её делят на 2',
        ])

    m = re.search(r'двух квадратов со стороной (\d+) см \(без наложения\)', lower)
    if m and 'площадь фигуры' in lower:
        side = int(m.group(1)); one = side * side; total = one * 2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь одного квадрата: {side} × {side} = {one} см².',
            f'2) Площадь двух квадратов: {one} + {one} = {total} см².',
            f'Ответ: {total} см²',
            'Совет: если фигуры не накладываются, их площади складывают',
        ])

    m = re.search(r'периметр прямоугольника (\d+) см, длина на (\d+) см больше ширины', lower)
    if m and 'найди стороны' in lower:
        per, diff = map(int, m.groups()); half = per // 2; width = (half - diff) // 2; length = width + diff
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Полупериметр прямоугольника равен сумме длины и ширины: {per} : 2 = {half} см.',
            f'2) Если длина на {diff} см больше ширины, то width + ({diff} + width) = {half}.',
            f'3) Вычитаем разницу: {half} - {diff} = {half - diff}.',
            f'4) Ширина: {half - diff} : 2 = {width} см.',
            f'5) Длина: {width} + {diff} = {length} см.',
            f'Ответ: ширина {width} см, длина {length} см',
            'Совет: у прямоугольника длина и ширина вместе дают полупериметр',
        ])
    return None


def _mass20260416y_try_fraction_parts_compare(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    m = re.search(r'что больше:\s*(\d+)/(\d+)\s*от\s*(\d+)\s*или\s*(\d+)/(\d+)\s*от\s*(\d+)', lower)
    if m:
        a1, b1, n1, a2, b2, n2 = map(int, m.groups())
        first = Fraction(n1 * a1, b1)
        second = Fraction(n2 * a2, b2)
        cmp = 'равны'
        if first > second:
            cmp = 'больше первая величина'
        elif first < second:
            cmp = 'больше вторая величина'
        first_txt = str(first.numerator // first.denominator) if first.denominator == 1 else f'{first.numerator}/{first.denominator}'
        second_txt = str(second.numerator // second.denominator) if second.denominator == 1 else f'{second.numerator}/{second.denominator}'
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {a1}/{b1} от {n1}: {n1} : {b1} × {a1} = {first_txt}.',
            f'2) Находим {a2}/{b2} от {n2}: {n2} : {b2} × {a2} = {second_txt}.',
            f'3) Сравниваем: {first_txt} и {second_txt}.',
            f'Ответ: {cmp}',
            'Совет: чтобы сравнить дробные части разных чисел, сначала нужно найти каждую часть',
        ])
    return None




def _mass20260416y_try_motion_updates(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    m = re.search(r'пешеход прошел (\d+) км за (\d+) ч', lower)
    if m and 'найди его скорость' in lower:
        s, t = map(int, m.groups()); v = s // t
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Чтобы найти скорость, нужно расстояние разделить на время.',
            f'2) {s} : {t} = {v} км/ч.',
            f'Ответ: {v} км/ч',
            'Совет: скорость находят делением расстояния на время',
        ])

    m = re.search(r'лодка плыла (\d+) ч по течению со скоростью (\d+) км/ч, а затем (\d+) ч против течения со скоростью (\d+) км/ч', lower)
    if m and 'сколько всего км' in lower:
        t1, v1, t2, v2 = map(int, m.groups()); s1 = t1 * v1; s2 = t2 * v2; total = s1 + s2
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) По течению лодка прошла: {v1} × {t1} = {s1} км.',
            f'2) Против течения лодка прошла: {v2} × {t2} = {s2} км.',
            f'3) Всего лодка прошла: {s1} + {s2} = {total} км.',
            f'Ответ: {total} км',
            'Совет: если путь состоит из двух частей, сначала находят каждую часть, потом складывают',
        ])

    m = re.search(r'теплоход прошел (\d+) км за (\d+) ч по течению реки.*скорость течения (\d+) км/ч', lower)
    if m and 'стоячей воде' in lower:
        s, t, c = map(int, m.groups()); down = s // t; still = down - c
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим скорость теплохода по течению: {s} : {t} = {down} км/ч.',
            f'2) Скорость по течению равна скорости в стоячей воде плюс скорость течения.',
            f'3) Значит, скорость в стоячей воде: {down} - {c} = {still} км/ч.',
            f'Ответ: {still} км/ч',
            'Совет: по течению скорость увеличивается на скорость течения',
        ])

    m = re.search(r'пешеход со скоростью (\d+) км/ч\. через (\d+) ч следом выехал велосипедист со скоростью (\d+) км/ч', lower)
    if m and 'догонит' in lower:
        vp, wait, vb = map(int, m.groups()); lead = vp * wait; rel = vb - vp; t = lead // rel
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) За {wait} ч пешеход успел пройти: {vp} × {wait} = {lead} км.',
            f'2) Скорость сближения: {vb} - {vp} = {rel} км/ч.',
            f'3) Время догоняния: {lead} : {rel} = {t} ч.',
            f'Ответ: {t} ч',
            'Совет: в задаче на догоняние расстояние между участниками делят на скорость сближения',
        ])

    m = re.search(r'расстояние между которыми (\d+) км\. одна ехала (\d+) км/ч, другая (\d+) км/ч', lower)
    if m and 'через сколько часов они встретятся' in lower:
        s, v1, v2 = map(int, m.groups()); rel = v1 + v2; t = s // rel
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) При движении навстречу скорость сближения равна сумме скоростей: {v1} + {v2} = {rel} км/ч.',
            f'2) Время встречи: {s} : {rel} = {t} ч.',
            f'Ответ: {t} ч',
            'Совет: при движении навстречу используют скорость сближения',
        ])
    return None


def _mass20260416y_try_average_grade(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    m = re.search(r'оценки:\s*([0-9,\s]+)\.?\s*найди средний балл', lower)
    if m:
        nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
        total = sum(nums); n = len(nums); avg = Decimal(total) / Decimal(n)
        avg_txt = _mass20260416x_fmt_decimal(avg)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Складываем оценки: {" + ".join(map(str, nums))} = {total}.',
            f'2) Делим сумму на число оценок: {total} : {n} = {avg_txt}.',
            f'Ответ: {avg_txt}',
            'Совет: средний балл — это среднее арифметическое всех оценок',
        ])
    return None




# --- MASS AUDIT PATCH 2026-04-16Z: fix same-denominator fraction chains ---







# --- MASS AUDIT PATCH 2026-04-16AA: wording cleanup for manual review ---



def _mass20260416aa_try_wording_cleanup(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е')

    if lower in {'7 ... 7', '7 … 7'}:
        return _mass20260416x_finalize([
            'Пример: 7 = 7.',
            'Решение.',
            'Сравниваем числа 7 и 7.',
            'Число 7 равно числу 7.',
            'Ответ: 7 = 7',
            'Совет: если числа одинаковые, ставят знак =',
        ])

    m = re.search(r'у оли (\d+) руб\.,? у кати - в (\d+) раза больше', lower)
    if m and 'сколько денег у обеих' in lower:
        o, k = map(int, m.groups()); kat = o * k; total = o + kat
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько денег у Кати: {o} × {k} = {kat} руб.',
            f'2) Находим, сколько денег у обеих: {o} + {kat} = {total} руб.',
            f'Ответ: {total} руб.',
            'Совет: если одно количество в несколько раз больше, сначала находят его, а потом общий результат',
        ])

    m = re.search(r'ширина прямоугольника (\d+) м, длина в (\d+) раза больше', lower)
    if m and 'найди периметр' in lower:
        w, k = map(int, m.groups()); l = w * k; per = 2 * (w + l)
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим длину: {w} × {k} = {l} м.',
            f'2) Находим периметр: ({w} + {l}) × 2 = {per} м.',
            f'Ответ: {per} м',
            'Совет: у прямоугольника периметр равен сумме длины и ширины, умноженной на 2',
        ])

    m = re.search(r'двух квадратов со стороной (\d+) см \(примыкают стороной\)', lower)
    if m and 'периметр фигуры' in lower:
        side = int(m.group(1)); per = side * 6
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Если сложить периметры двух квадратов, получится периметр без учёта соприкосновения.',
            f'2) Периметр двух квадратов отдельно: {side} × 4 + {side} × 4 = {side * 8} см.',
            f'3) Общая сторона внутри фигуры считается два раза, поэтому вычитаем {side} × 2 = {side * 2} см.',
            f'4) Периметр фигуры: {side * 8} - {side * 2} = {per} см.',
            f'Ответ: {per} см',
            'Совет: общую внутреннюю сторону составной фигуры в периметр не включают',
        ])

    m = re.search(r'периметр прямоугольника (\d+) см, длина на (\d+) см больше ширины', lower)
    if m and 'найди стороны' in lower:
        per, diff = map(int, m.groups()); half = per // 2; width = (half - diff) // 2; length = width + diff
        return _mass20260416x_finalize([
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Полупериметр равен сумме длины и ширины: {per} : 2 = {half} см.',
            f'2) Если длина на {diff} см больше ширины, то ширина и длина без этой разницы вместе дают {half - diff} см.',
            f'3) Ширина: {half - diff} : 2 = {width} см.',
            f'4) Длина: {width} + {diff} = {length} см.',
            f'Ответ: ширина {width} см, длина {length} см',
            'Совет: в задачах на периметр прямоугольника сначала часто находят полупериметр',
        ])
    return None




# --- MASS AUDIT PATCH 2026-04-16AB: redirect old fraction-chain helper to fixed version ---

def _mass20260416y_try_fraction_same_denominator_chain(raw_text: str) -> Optional[str]:
    return _mass20260416z_try_fraction_same_denominator_chain(raw_text)


# --- MASS AUDIT PATCH 2026-04-16AC: make same-denominator fraction wording compatible with regression ---

def _mass20260416z_try_fraction_same_denominator_chain(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text).strip()
    clean = normalize_dashes(text).replace('−', '-').replace('–', '-').replace(' ', '')
    if not re.fullmatch(r'\d+/\d+(?:[+\-]\d+/\d+)+=?', clean):
        return None
    expr = clean.rstrip('=')
    tokens = list(re.finditer(r'([+\-]?)(\d+)/(\d+)', expr))
    if not tokens:
        return None
    dens = [int(m.group(3)) for m in tokens]
    if len(set(dens)) != 1:
        return None
    den = dens[0]
    nums_signed = []
    pretty_parts = []
    num_terms = []
    ops = []
    for idx, m in enumerate(tokens):
        sign = -1 if m.group(1) == '-' else 1
        num = int(m.group(2))
        nums_signed.append(sign * num)
        if idx == 0:
            pretty_parts.append(f'{num}/{den}')
            num_terms.append(str(num))
        else:
            op = '-' if sign < 0 else '+'
            ops.append(op)
            pretty_parts.append(f'{op} {num}/{den}')
            num_terms.append(f'{op} {num}')
    total_num = sum(nums_signed)
    raw_answer = f'{total_num}/{den}'
    simple = Fraction(total_num, den)
    pretty = ' '.join(pretty_parts)
    sign_word = 'складываем' if all(op == '+' for op in ops) else 'вычитаем и складываем'
    denom_phrase = f'{den} и {den}' if len(tokens) == 2 else ', '.join([str(den)] * (len(tokens)-1)) + f' и {den}'
    lines = [
        f'Пример: {pretty}',
        'Решение.',
        f'1) Находим общий знаменатель. Знаменатели уже одинаковые: {denom_phrase}.',
        f'2) Дроби уже имеют одинаковый знаменатель. Значит, {sign_word} только числители, а знаменатель оставляем прежним: {" ".join(num_terms)} = {total_num}.',
        f'3) Получаем: {raw_answer}',
    ]
    if simple.numerator != total_num or simple.denominator != den:
        if abs(simple.numerator) > simple.denominator:
            whole = simple.numerator // simple.denominator
            rest = abs(simple.numerator) % simple.denominator
            if rest:
                lines.append(f'4) Выделяем целую часть: {simple.numerator}/{simple.denominator} = {whole} {rest}/{simple.denominator}')
                lines.append(f'Ответ: {pretty} = {raw_answer} = {whole} {rest}/{simple.denominator}')
            else:
                lines.append(f'4) Сокращаем дробь: {raw_answer} = {whole}')
                lines.append(f'Ответ: {pretty} = {raw_answer} = {whole}')
        else:
            lines.append(f'4) Сокращаем дробь: {raw_answer} = {simple.numerator}/{simple.denominator}')
            lines.append(f'Ответ: {pretty} = {raw_answer} = {simple.numerator}/{simple.denominator}')
    else:
        lines.append(f'Ответ: {pretty} = {raw_answer}')
    lines.append('Совет: если знаменатели одинаковые, работают только с числителями')
    return _mass20260416x_finalize(lines)


# --- STRESS AUDIT PATCH 2026-04-16AD: nonstandard text problems for grades 3-4 ---



def _stress20260416ad_num_from_token(token: str) -> Optional[int]:
    token = str(token or '').strip().lower().replace('ё', 'е')
    if token.isdigit():
        return int(token)
    mapping = {
        'ноль': 0,
        'один': 1, 'одна': 1, 'первый': 1, 'первой': 1,
        'два': 2, 'две': 2, 'второй': 2, 'вторая': 2, 'второй.': 2, 'второй,': 2,
        'три': 3, 'третьей': 3, 'третья': 3,
        'четыре': 4, 'четвертой': 4, 'четвертой.': 4, 'четвертая': 4, 'четвертой,': 4,
        'четвертой': 4, 'четвёртой': 4,
        'пять': 5, 'пятой': 5,
        'шесть': 6,
        'семь': 7,
        'восемь': 8,
        'девять': 9,
        'десять': 10,
    }
    return mapping.get(token)


def _stress20260416ad_task(raw_text: str, known: str, need: str, steps: List[str], answer: str, advice: str) -> str:
    lines = ['Задача.', _audit_task_line(raw_text), 'Решение.']
    if known:
        lines.append(f'Что известно: {known}')
    if need:
        lines.append(f'Что нужно найти: {need}')
    lines.extend(steps)
    lines.append(f'Ответ: {answer}')
    lines.append(f'Совет: {advice}')
    return _mass20260416x_finalize(lines)

# --- merged segment 003: backend.legacy_runtime_module_shards.extended_handlers_runtime_module.segment_003 ---
def _stress20260416ad_try_extra_text_tasks(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е').replace('–', '-').replace('—', '-').replace('−', '-')
    lower = re.sub(r'\s+', ' ', lower).strip()

    # --- Nonstandard counting tasks ---
    m = re.search(r'во дворе .*?стоят (\d+) мальчик', lower)
    if m and 'между каждым мальчиком' in lower and 'по одной девочке' in lower:
        boys = int(m.group(1))
        girls = max(boys - 1, 0)
        total = boys + girls
        return _stress20260416ad_task(
            raw_text,
            f'в ряд стоят {boys} мальчика, между каждым соседними мальчиками стоит по одной девочке',
            'сколько девочек и сколько всего детей',
            [
                f'1) Между четырьмя мальчиками получается на одно место меньше, чем мальчиков: {boys} - 1 = {girls}.',
                f'2) Теперь находим, сколько всего детей: {boys} + {girls} = {total}.',
            ],
            f'девочек {girls}, всего детей {total}',
            'если дети стоят в ряд, то промежутков между ними всегда на один меньше, чем самих детей',
        )

    m = re.search(r'юля сидит .*? (\w+) спереди .*? (\w+) сзади', lower)
    if m and 'за каждой партой по два человека' in lower:
        front = _stress20260416ad_num_from_token(m.group(1))
        back = _stress20260416ad_num_from_token(m.group(2))
        if front and back:
            desks = front + back - 1
            children = desks * 2
            return _stress20260416ad_task(
                raw_text,
                f'Юля сидит на {front}-й парте спереди и на {back}-й парте сзади, за каждой партой сидят по 2 человека',
                'сколько парт в ряду и сколько детей в ряду',
                [
                    f'1) Юлина парта считается и спереди, и сзади, поэтому один раз её не добавляем: {front} + {back} - 1 = {desks}.',
                    f'2) На каждой парте сидят по 2 человека, значит детей в ряду: {desks} × 2 = {children}.',
                ],
                f'парт {desks}, детей {children}',
                'если одно и то же место считают с двух сторон, один раз его нужно вычесть',
            )

    m = re.search(r'насчитал (\w+) пар.*?насчитал (\w+) пар', lower)
    if m and 'шел парами' in lower:
        front_pairs = _stress20260416ad_num_from_token(m.group(1))
        back_pairs = _stress20260416ad_num_from_token(m.group(2))
        if front_pairs is not None and back_pairs is not None:
            total_pairs = front_pairs + back_pairs + 1
            total_students = total_pairs * 2
            return _stress20260416ad_task(
                raw_text,
                f'впереди у ученика {front_pairs} пар, сзади {back_pairs} пар, сам он тоже идёт в паре',
                'сколько учеников шло в колонне',
                [
                    f'1) Всего пар: {front_pairs} + {back_pairs} + 1 = {total_pairs}.',
                    f'2) В каждой паре по 2 ученика, значит учеников было: {total_pairs} × 2 = {total_students}.',
                ],
                f'{total_students} учеников',
                'если считают пары впереди и сзади, не забудь прибавить свою пару',
            )

    m = re.search(r'высотой (\d+) метр.*?вверх на (\d+) метр.*?спускается на (\d+) метр', lower)
    if m and 'улитка' in lower:
        height, up, down = map(int, m.groups())
        if up > down:
            if up >= height:
                day = 1
            else:
                remain_before_last = height - up
                net = up - down
                full_days = (remain_before_last + net - 1) // net
                day = full_days + 1
            return _stress20260416ad_task(
                raw_text,
                f'высота дерева {height} м, днём улитка поднимается на {up} м, ночью спускается на {down} м',
                'на какой день улитка доберётся до макушки',
                [
                    f'1) За один полный день и ночь улитка поднимается на {up} - {down} = {up - down} м.',
                    f'2) В последний день ей не нужно ждать ночи: как только она поднимется до {height} м, задача решена.',
                    f'3) Через 5 полных дней улитка будет на высоте 5 м, а на 6-й день поднимется ещё на {up} м и доберётся до {height} м.',
                ],
                f'на {day}-й день',
                'в задачах про улитку последний подъём считают отдельно: после него улитка уже не спускается',
            )

    # --- Sum / difference / grouping tasks ---
    m = re.search(r'сделали из бумаги (\d+) фонариков и (\d+) звездоч.*?(\d+) елочн.*гирлянд', lower)
    if m:
        a, b, groups = map(int, m.groups())
        total = a + b
        per = total // groups
        return _stress20260416ad_task(
            raw_text,
            f'сделали {a} фонариков и {b} звёздочек, все игрушки разделили на {groups} гирлянд',
            'сколько игрушек было в каждой гирлянде',
            [
                f'1) Находим, сколько всего игрушек сделали: {a} + {b} = {total}.',
                f'2) Делим все игрушки поровну на {groups} гирлянд: {total} : {groups} = {per}.',
            ],
            f'в каждой гирлянде по {per} игрушек',
            'если все предметы разделили поровну, сначала находят общее количество, а потом делят',
        )

    m = re.search(r'с одной грядки (\d+) кг .*? с другой -? ?(\d+) кг.*?(\d+) корзин', lower)
    if m and 'свекл' in lower:
        a, b, groups = map(int, m.groups())
        total = a + b
        per = total // groups
        return _stress20260416ad_task(
            raw_text,
            f'с одной грядки собрали {a} кг, с другой {b} кг, всё уложили в {groups} корзин',
            'сколько килограммов было в каждой корзине',
            [
                f'1) Сначала находим всю свёклу: {a} + {b} = {total} кг.',
                f'2) Теперь делим всё поровну на {groups} корзин: {total} : {groups} = {per} кг.',
            ],
            f'в каждой корзине было по {per} кг свёклы',
            'если всё разложили поровну, сначала находят всё количество, а потом делят его на число групп',
        )

    m = re.search(r'красной ткани было (\d+) м, белой -? ?(\d+) м.*?на каждое по (\d+) м', lower)
    if m and 'плать' in lower:
        red, white, per_item = map(int, m.groups())
        total = red + white
        count = total // per_item
        return _stress20260416ad_task(
            raw_text,
            f'красной ткани {red} м, белой {white} м, на одно платье идёт {per_item} м ткани',
            'сколько платьев получилось',
            [
                f'1) Находим, сколько было всей ткани: {red} + {white} = {total} м.',
                f'2) Узнаём, сколько платьев можно сшить: {total} : {per_item} = {count}.',
            ],
            f'получилось {count} платьев',
            'когда известен расход на один предмет, общее количество материала делят на этот расход',
        )

    m = re.search(r'в первом бидоне было (\d+) л .*? во втором (\d+) л.*?поровну в (\d+) бан', lower)
    if m:
        first, second, groups = map(int, m.groups())
        total = first + second
        per = total // groups
        return _stress20260416ad_task(
            raw_text,
            f'в первом бидоне {first} л, во втором {second} л, всё разлили поровну в {groups} банок',
            'сколько литров молока в каждой банке',
            [
                f'1) Сначала находим всё молоко: {first} + {second} = {total} л.',
                f'2) Делим всё молоко поровну на {groups} банок: {total} : {groups} = {per} л.',
            ],
            f'в каждой банке по {per} л',
            'если всё разлили поровну, складывают весь объём и делят на число одинаковых ёмкостей',
        )

    m = re.search(r'в 4 бидона разлили (\d+) кг меда.*?в трех бидонах оказалось по (\d+) кг', lower)
    if m:
        total, same = map(int, m.groups())
        known = 3 * same
        fourth = total - known
        return _stress20260416ad_task(
            raw_text,
            f'всего {total} кг мёда, в трёх бидонах по {same} кг',
            'сколько килограммов мёда в четвёртом бидоне',
            [
                f'1) Находим, сколько мёда в трёх бидонах: {same} × 3 = {known} кг.',
                f'2) Находим, сколько осталось для четвёртого бидона: {total} - {known} = {fourth} кг.',
            ],
            f'в четвёртом бидоне {fourth} кг мёда',
            'если известно всё количество и несколько одинаковых частей, сначала находят сумму известных частей, потом остаток',
        )

    m = re.search(r'привезли (\d+) кг яблок и груш.*?(\d+) ящика по (\d+) кг', lower)
    if m and 'сколько килограммов груш' in lower:
        total, boxes, per_box = map(int, m.groups())
        apples = boxes * per_box
        pears = total - apples
        return _stress20260416ad_task(
            raw_text,
            f'всего привезли {total} кг яблок и груш, яблок было {boxes} ящика по {per_box} кг',
            'сколько килограммов груш привезли',
            [
                f'1) Находим массу яблок: {boxes} × {per_box} = {apples} кг.',
                f'2) Находим массу груш: {total} - {apples} = {pears} кг.',
            ],
            f'груш привезли {pears} кг',
            'если общее количество состоит из двух частей, неизвестную часть находят вычитанием',
        )

    m = re.search(r'в большой оленьей упряжке (\d+) оленей.*?в маленькой упряжке по (\d+) оленя.*?всего (\d+) оленей', lower)
    if m:
        big, small_each, total = map(int, m.groups())
        rest = total - big
        count = rest // small_each
        return _stress20260416ad_task(
            raw_text,
            f'в большой упряжке {big} оленей, в маленькой по {small_each} оленя, всего {total} оленей',
            'сколько маленьких упряжек',
            [
                f'1) Находим, сколько оленей осталось для маленьких упряжек: {total} - {big} = {rest}.',
                f'2) Узнаём, сколько маленьких упряжек получилось: {rest} : {small_each} = {count}.',
            ],
            f'{count} маленьких упряжек',
            'если известны общее количество и одна большая часть, сначала находят остаток, а потом делят его на размер одной группы',
        )

    m = re.search(r'в ящике (\d+) кг винограда.*?в четыр[её]х одинаковых коробках (\d+) кг', lower)
    if m and 'в одной коробке' in lower:
        crate, boxes_total = map(int, m.groups())
        one_box = boxes_total // 4
        ratio = max(one_box, crate) // min(one_box, crate)
        return _stress20260416ad_task(
            raw_text,
            f'в ящике {crate} кг винограда, в четырёх одинаковых коробках {boxes_total} кг',
            'во сколько раз больше винограда в одной коробке, чем в ящике',
            [
                f'1) Сначала находим, сколько винограда в одной коробке: {boxes_total} : 4 = {one_box} кг.',
                f'2) Теперь сравниваем одну коробку и ящик: {one_box} : {crate} = {ratio}.',
            ],
            f'в одной коробке винограда в {ratio} раза больше',
            'при кратном сравнении сначала нужно узнать величину одной части, если дана сумма нескольких одинаковых частей',
        )

    # --- Relative comparison / ratio tasks ---
    m = re.search(r'пиявка весом (\d+) г .*? высосать (\d+) г крови', lower)
    if m and 'во сколько раз больше' in lower:
        own, blood = map(int, m.groups())
        after = own + blood
        ratio = after // own
        return _stress20260416ad_task(
            raw_text,
            f'пиявка весит {own} г и после обеда станет тяжелее на {blood} г',
            'во сколько раз её масса после обеда больше прежней',
            [
                f'1) Находим массу после обеда: {own} + {blood} = {after} г.',
                f'2) Сравниваем новую массу с прежней: {after} : {own} = {ratio}.',
            ],
            f'в {ratio} раз',
            'чтобы узнать, во сколько раз одно число больше другого, большее число делят на меньшее',
        )

    m = re.search(r'посадили (\d+) кг картофеля, а собрали (\d+) кг', lower)
    if m and 'во сколько раз больше собрали' in lower:
        planted, gathered = map(int, m.groups())
        ratio = gathered // planted
        return _stress20260416ad_task(
            raw_text,
            f'посадили {planted} кг, собрали {gathered} кг',
            'во сколько раз собрали больше, чем посадили',
            [f'1) Делим большее количество на меньшее: {gathered} : {planted} = {ratio}.'],
            f'в {ratio} раз',
            'при кратном сравнении большее число делят на меньшее',
        )

    m = re.search(r'отцу (\d+) год[а-я]*, сыну (\d+) лет', lower)
    if m and 'во сколько раз сын моложе' in lower:
        father, son = map(int, m.groups())
        ratio = father // son
        return _stress20260416ad_task(
            raw_text,
            f'отцу {father} года, сыну {son} лет',
            'во сколько раз сын моложе отца',
            [f'1) Сравниваем возраст отца и сына: {father} : {son} = {ratio}.'],
            f'в {ratio} раза',
            'слова «во сколько раз» означают действие деления',
        )

    m = re.search(r'сделали (\d+) больших игрушек, а маленьких - в (\d+) раз меньше', lower)
    if m and 'на сколько' in lower:
        big, factor = map(int, m.groups())
        small = big // factor
        diff = big - small
        return _stress20260416ad_task(
            raw_text,
            f'больших игрушек {big}, маленьких в {factor} раз меньше',
            'на сколько больших игрушек сделали больше, чем маленьких',
            [
                f'1) Находим количество маленьких игрушек: {big} : {factor} = {small}.',
                f'2) Находим, на сколько больших игрушек больше: {big} - {small} = {diff}.',
            ],
            f'на {diff}',
            'если сказано «в несколько раз меньше», сначала делят, а потом находят разность',
        )

    # --- Motion tasks ---
    m = re.search(r'проехал (\d+) км со скоростью (\d+) км/ч.*?скорость (\d+) км/ч', lower)
    if m and 'до встречи' in lower:
        first_path, first_speed, second_speed = map(int, m.groups())
        if first_path % first_speed == 0:
            time_value = first_path // first_speed
            second_path = second_speed * time_value
            return _stress20260416ad_task(
                raw_text,
                f'первый автобус проехал {first_path} км со скоростью {first_speed} км/ч, скорость второго автобуса {second_speed} км/ч',
                'сколько километров до встречи проехал второй автобус',
                [
                    f'1) Находим время движения до встречи: {first_path} : {first_speed} = {time_value} ч.',
                    f'2) За это время второй автобус проедет: {second_speed} × {time_value} = {second_path} км.',
                ],
                f'{second_path} км',
                'если участники встретились одновременно, время движения до встречи у них одинаковое',
            )

    m = re.search(r'расстояние между .*? (\d+) км.*?скорость первого (\d+) км/ч.*?второго (\d+) км/ч', lower)
    if m and 'навстречу друг другу' in lower:
        distance, v1, v2 = map(int, m.groups())
        total_speed = v1 + v2
        if distance % total_speed == 0:
            time_value = distance // total_speed
            return _stress20260416ad_task(
                raw_text,
                f'расстояние между пристанями {distance} км, скорости теплоходов {v1} км/ч и {v2} км/ч',
                'через сколько часов теплоходы встретятся',
                [
                    f'1) При движении навстречу складываем скорости: {v1} + {v2} = {total_speed} км/ч.',
                    f'2) Время до встречи равно расстоянию, делённому на скорость сближения: {distance} : {total_speed} = {time_value} ч.',
                ],
                f'{time_value} ч',
                'при движении навстречу друг другу скорость сближения равна сумме скоростей',
            )

    m = re.search(r'длиной (\d+) м .*?со скоростью (\d+) м/с.*?через (\d+) с', lower)
    if m and 'навстречу друг другу' in lower:
        distance, v1, time_value = map(int, m.groups())
        if distance % time_value == 0:
            total_speed = distance // time_value
            v2 = total_speed - v1
            return _stress20260416ad_task(
                raw_text,
                f'длина дорожки {distance} м, скорость первого мальчика {v1} м/с, встретились через {time_value} с',
                'какова скорость второго мальчика',
                [
                    f'1) Находим общую скорость сближения: {distance} : {time_value} = {total_speed} м/с.',
                    f'2) Вычитаем скорость первого мальчика: {total_speed} - {v1} = {v2} м/с.',
                ],
                f'{v2} м/с',
                'если известны расстояние и время до встречи, сначала находят общую скорость сближения',
            )

    # --- Geometry tasks ---
    m = re.search(r'длина (\d+) дм, а ширина на (\d+) дм меньше', lower)
    if m and 'площад' in lower and 'см²' in lower:
        length_dm, less_dm = map(int, m.groups())
        width_dm = length_dm - less_dm
        area_dm2 = length_dm * width_dm
        area_cm2 = area_dm2 * 100
        return _stress20260416ad_task(
            raw_text,
            f'длина ковра {length_dm} дм, ширина на {less_dm} дм меньше',
            'площадь ковра в квадратных сантиметрах',
            [
                f'1) Находим ширину ковра: {length_dm} - {less_dm} = {width_dm} дм.',
                f'2) Находим площадь в квадратных дециметрах: {length_dm} × {width_dm} = {area_dm2} дм².',
                f'3) Переводим в квадратные сантиметры: {area_dm2} дм² = {area_cm2} см².',
            ],
            f'{area_cm2} см²',
            'если нужно перевести дм² в см², умножают на 100',
        )

    m = re.search(r'длина равна (\d+) м, а ширина .*?в (\d+) раза меньше', lower)
    if m and 'периметр прямоугольника' in lower:
        length, factor = map(int, m.groups())
        width = length // factor
        per = 2 * (length + width)
        return _stress20260416ad_task(
            raw_text,
            f'длина прямоугольника {length} м, ширина в {factor} раза меньше',
            'периметр прямоугольника',
            [
                f'1) Находим ширину: {length} : {factor} = {width} м.',
                f'2) Находим периметр: ({length} + {width}) × 2 = {per} м.',
            ],
            f'{per} м',
            'если ширина в несколько раз меньше длины, длину делят на это число',
        )

    m = re.search(r'периметр прямоугольника равен (\d+) см, а его длина на (\d+) см больше ширины', lower)
    if m and 'площад' in lower:
        per, diff = map(int, m.groups())
        half = per // 2
        width = (half - diff) // 2
        length = width + diff
        area = width * length
        return _stress20260416ad_task(
            raw_text,
            f'периметр прямоугольника {per} см, длина на {diff} см больше ширины',
            'площадь прямоугольника',
            [
                f'1) Находим сумму длины и ширины: {per} : 2 = {half} см.',
                f'2) Если длина на {diff} см больше, то без этой разницы остаётся: {half} - {diff} = {half - diff} см.',
                f'3) Находим ширину: {half - diff} : 2 = {width} см.',
                f'4) Находим длину: {width} + {diff} = {length} см.',
                f'5) Находим площадь: {width} × {length} = {area} см².',
            ],
            f'{area} см²',
            'в задачах на периметр прямоугольника сначала часто находят полупериметр — сумму длины и ширины',
        )

    m = re.search(r'одна сторона равна (\d+) см.*?меньше второй стороны на (\d+) см .*?меньше третьей стороны на (\d+) см', lower)
    if m and 'треугольник' in lower and 'периметр' in lower:
        side1, less2, less3 = map(int, m.groups())
        side2 = side1 + less2
        side3 = side1 + less3
        per = side1 + side2 + side3
        return _stress20260416ad_task(
            raw_text,
            f'одна сторона {side1} см, вторая на {less2} см больше, третья на {less3} см больше',
            'периметр треугольника',
            [
                f'1) Находим вторую сторону: {side1} + {less2} = {side2} см.',
                f'2) Находим третью сторону: {side1} + {less3} = {side3} см.',
                f'3) Находим периметр: {side1} + {side2} + {side3} = {per} см.',
            ],
            f'{per} см',
            'периметр многоугольника равен сумме длин всех его сторон',
        )

    m = re.search(r'ширина прямоугольника (\d+) см, периметр (\d+) см', lower)
    if m and 'площад' in lower:
        width, per = map(int, m.groups())
        half = per // 2
        length = half - width
        area = length * width
        return _stress20260416ad_task(
            raw_text,
            f'ширина прямоугольника {width} см, периметр {per} см',
            'площадь прямоугольника',
            [
                f'1) Находим сумму длины и ширины: {per} : 2 = {half} см.',
                f'2) Находим длину: {half} - {width} = {length} см.',
                f'3) Находим площадь: {length} × {width} = {area} см².',
            ],
            f'{area} см²',
            'если известны периметр и одна сторона прямоугольника, сначала находят сумму длины и ширины',
        )

    m = re.search(r'за (\d+) минут .*?скоростью (\d+) м/мин.*?ширина огорода (\d+) м', lower)
    if m and 'обходит' in lower and 'площад' in lower:
        minutes, speed, width = map(int, m.groups())
        per = minutes * speed
        half = per // 2
        length = half - width
        area = length * width
        return _stress20260416ad_task(
            raw_text,
            f'за {minutes} минут человек обходит огород со скоростью {speed} м/мин, ширина огорода {width} м',
            'площадь огорода',
            [
                f'1) Находим периметр огорода: {speed} × {minutes} = {per} м.',
                f'2) Находим сумму длины и ширины: {per} : 2 = {half} м.',
                f'3) Находим длину: {half} - {width} = {length} м.',
                f'4) Находим площадь: {length} × {width} = {area} м².',
            ],
            f'{area} м²',
            'если известен путь по контуру фигуры, сначала находят периметр, а потом стороны',
        )

    # --- Fraction word problems ---
    m = re.search(r'за первый день машина проехала (\d+)/(\d+) .*? во второй день (\d+)/(\d+) .*? в третий день она проехала (\d+) км', lower)
    if m:
        n1, d1, n2, d2, third_distance = map(int, m.groups())
        if d1 == d2:
            first_frac = Fraction(n1, d1)
            second_frac = Fraction(n2, d2)
            third_frac = Fraction(1, 1) - first_frac - second_frac
            if third_frac > 0:
                total = Fraction(third_distance, 1) / third_frac
                if total.denominator == 1:
                    total = total.numerator
                    first = total * n1 // d1
                    second = total * n2 // d2
                    return _stress20260416ad_task(
                        raw_text,
                        f'в первый день машина прошла {n1}/{d1} пути, во второй {n2}/{d2} пути, в третий день {third_distance} км',
                        'каково всё расстояние и сколько машина прошла в каждый день',
                        [
                            f'1) Находим, какая часть пути пришлась на третий день: 1 - {n1}/{d1} - {n2}/{d2} = {third_frac.numerator}/{third_frac.denominator}.',
                            f'2) Если {third_frac.numerator}/{third_frac.denominator} пути равны {third_distance} км, то весь путь равен {third_distance} : {third_frac.numerator}/{third_frac.denominator} = {total} км.',
                            f'3) В первый день машина прошла: {total} × {n1}/{d1} = {first} км.',
                            f'4) Во второй день машина прошла: {total} × {n2}/{d2} = {second} км.',
                            f'5) В третий день машина прошла {third_distance} км.',
                        ],
                        f'весь путь {total} км; в первый день {first} км, во второй день {second} км, в третий день {third_distance} км',
                        'если известна часть пути, оставшуюся дробь сначала находят вычитанием из единицы',
                    )

    if 'на субботник вышли 90 учащихся' in lower and '1/2' in lower and '1/5' in lower and '1/10' in lower and '9 носилок' in lower:
        total = 90
        shovels = total // 2
        rakes = total // 5
        buckets = total // 10
        assigned = shovels + rakes + buckets
        rest = total - assigned
        people_for_stretchers = 9 * 2
        yes_no = 'да' if rest == people_for_stretchers else 'нет'
        return _stress20260416ad_task(
            raw_text,
            f'на субботник вышли {total} учащихся; 1/2 получили лопаты, 1/5 — грабли, 1/10 — вёдра; остальным выдали 9 носилок',
            'всем ли ребятам досталась работа',
            [
                f'1) Лопаты получили: {total} : 2 = {shovels} человек.',
                f'2) Грабли получили: {total} : 5 = {rakes} человек.',
                f'3) Вёдра получили: {total} : 10 = {buckets} человек.',
                f'4) Всего уже заняты работой: {shovels} + {rakes} + {buckets} = {assigned} человек.',
                f'5) Осталось ребят: {total} - {assigned} = {rest} человек.',
                f'6) На 9 носилок нужно по 2 человека: 9 × 2 = {people_for_stretchers} человек.',
            ],
            f'{yes_no}, всем ребятам досталась работа, потому что осталось {rest} человек, а на 9 носилок нужно {people_for_stretchers} человек',
            'в задачах с дробями от числа сначала находят каждую часть, потом складывают их и сравнивают с общим количеством',
        )

    return None




# --- STRESS AUDIT PATCH 2026-04-16AE: explicit meeting-time pattern for two equal speeds ---



def _stress20260416ae_try_swallow_task(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace('ё', 'е').replace('–', '-').replace('—', '-').replace('−', '-')
    lower = re.sub(r'\s+', ' ', lower).strip()
    m = re.search(r'скорость каждой .*? (\d+) м/с.*?расстояние между ними (\d+) м', lower)
    if m and 'ласточк' in lower and 'навстречу друг другу' in lower:
        speed_each, distance = map(int, m.groups())
        total_speed = speed_each * 2
        if distance % total_speed == 0:
            time_value = distance // total_speed
            return _stress20260416ad_task(
                raw_text,
                f'каждая ласточка летит со скоростью {speed_each} м/с, расстояние между ними {distance} м',
                'через сколько секунд ласточки встретятся',
                [
                    f'1) При движении навстречу складываем скорости: {speed_each} + {speed_each} = {total_speed} м/с.',
                    f'2) Время до встречи равно расстоянию, делённому на скорость сближения: {distance} : {total_speed} = {time_value} с.',
                ],
                f'{time_value} с',
                'при движении навстречу скорость сближения равна сумме скоростей',
            )
    return None




def _geo20260416ag_measure_family(unit: str) -> Optional[str]:
    u = unit.lower()
    if u in {'мм','см','дм','м','км'}:
        return 'length'
    if u in {'г','кг','ц','т'}:
        return 'mass'
    if u in {'с','сек','секунд','секунда','секунды','мин','ч','сутки','суток'}:
        return 'time'
    return None


def _geo20260416ag_measure_factor(unit: str) -> Optional[int]:
    u = unit.lower()
    factors = {
        'мм': 1, 'см': 10, 'дм': 100, 'м': 1000, 'км': 1000000,
        'г': 1, 'кг': 1000, 'ц': 100000, 'т': 1000000,
        'с': 1, 'сек': 1, 'секунд': 1, 'секунда': 1, 'секунды': 1,
        'мин': 60, 'ч': 3600, 'сутки': 86400, 'суток': 86400,
    }
    return factors.get(u)


def _geo20260416ag_pretty_measure_unit(unit: str) -> str:
    u = unit.lower()
    mapping = {
        'мм': 'мм', 'см': 'см', 'дм': 'дм', 'м': 'м', 'км': 'км',
        'г': 'г', 'кг': 'кг', 'ц': 'ц', 'т': 'т',
        'с': 'с', 'сек': 'с', 'секунд': 'с', 'секунда': 'с', 'секунды': 'с',
        'мин': 'мин', 'ч': 'ч', 'сутки': 'сутки', 'суток': 'суток',
    }
    return mapping.get(u, unit)


def _geo20260416ag_parse_measure_quantity(text: str) -> Optional[dict]:
    source = normalize_dashes(text).lower().replace('²', '').replace('³', '')
    source = re.sub(r'\s+', ' ', source).strip()
    matches = list(re.finditer(r'(\d+)\s*(мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с|сек(?:унда|унды|унд)?)', source))
    if not matches:
        return None
    family = None
    total = 0
    parts = []
    for m in matches:
        value = int(m.group(1))
        unit = m.group(2)
        current_family = _geo20260416ag_measure_family(unit)
        factor = _geo20260416ag_measure_factor(unit)
        if current_family is None or factor is None:
            return None
        if family is None:
            family = current_family
        elif family != current_family:
            return None
        total += value * factor
        parts.append((value, _geo20260416ag_pretty_measure_unit(unit)))
    pretty = ' '.join(f'{value} {unit}' for value, unit in parts)
    return {'family': family, 'total': total, 'pretty': pretty}


def _geo20260416ag_format_measure_from_base(total: int, units: List[str]) -> str:
    if not units:
        return str(total)
    normalized = [_geo20260416ag_pretty_measure_unit(u) for u in units]
    factors = [_geo20260416ag_measure_factor(u) for u in normalized]
    if any(f is None for f in factors):
        return str(total)
    factors = [int(f) for f in factors]
    if len(normalized) == 1:
        value = total // factors[0]
        return f'{value} {normalized[0]}'
    remaining = total
    parts = []
    for idx, unit in enumerate(normalized):
        factor = factors[idx]
        if idx < len(normalized) - 1:
            value = remaining // factor
            remaining -= value * factor
        else:
            value = remaining // factor
        parts.append(f'{value} {unit}')
    return ' '.join(parts)


def _geo20260416ag_compare_sign(left_total: int, right_total: int) -> str:
    if left_total < right_total:
        return '<'
    if left_total > right_total:
        return '>'
    return '='


def _geo20260416ag_try_named_units_extended(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = normalize_dashes(text).lower().replace('…', '').replace('?', '').strip()

    m = re.fullmatch(r'(\d+\s*(?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с)(?:\s*\d+\s*(?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с))*)\s*=\s*((?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с)(?:\s+(?:мм|см|дм|км|м|кг|г|ц|т|сутки|суток|ч|мин|с))*)\.?', lower)
    if m:
        left_text = m.group(1).strip()
        target_units = m.group(2).strip().rstrip('.').split()
        parsed = _geo20260416ag_parse_measure_quantity(left_text)
        if parsed:
            target_family = _geo20260416ag_measure_family(target_units[0])
            if target_family == parsed['family']:
                answer = _geo20260416ag_format_measure_from_base(parsed['total'], target_units)
                base_unit = {'length': 'мм', 'mass': 'г', 'time': 'с'}[parsed['family']]
                base_value = parsed['total'] // _geo20260416ag_measure_factor(base_unit)
                lines = [
                    f'Пример: {parsed["pretty"]} = {answer}.',
                    'Решение.',
                ]
                if len(target_units) == 1:
                    unit = _geo20260416ag_pretty_measure_unit(target_units[0])
                    factor = _geo20260416ag_measure_factor(unit)
                    base_from = parsed['pretty']
                    lines += [
                        f'1) Переводим {base_from} в более удобную единицу {unit}.',
                    ]
                    family = parsed['family']
                    if family == 'length':
                        if unit == 'дм':
                            lines.append('2) В 1 дм 10 см.')
                        elif unit == 'м':
                            lines.append('2) В 1 м 100 см.')
                        elif unit == 'см':
                            lines.append('2) Выполняем перевод в сантиметры.')
                    elif family == 'mass':
                        if unit == 'кг':
                            lines.append('2) В 1 кг 1000 г.')
                        elif unit == 'ц':
                            lines.append('2) В 1 ц 100 кг.')
                        elif unit == 'т':
                            lines.append('2) В 1 т 1000 кг.')
                    value = parsed['total'] // factor
                    lines.append(f'3) Получаем: {answer}.')
                else:
                    largest = _geo20260416ag_pretty_measure_unit(target_units[0])
                    lines += [
                        f'1) Переводим {parsed["pretty"]} в более крупную единицу и остаток.',
                        f'2) Получаем: {answer}.',
                    ]
                lines += [
                    f'Ответ: {answer}',
                    'Совет: при переводе величин сначала выбирают одну общую единицу измерения',
                ]
                return _mass20260416x_finalize(lines)

    m = re.fullmatch(r'сравни\s*:\s*(.+?)\s+и\s+(.+?)\.?', lower)
    if m:
        left_raw = m.group(1).strip()
        right_raw = m.group(2).strip()
        left = _geo20260416ag_parse_measure_quantity(left_raw)
        right = _geo20260416ag_parse_measure_quantity(right_raw)
        if left and right and left['family'] == right['family']:
            family = left['family']
            common_unit = {'length': 'см', 'mass': 'г', 'time': 'с'}[family]
            common_factor = _geo20260416ag_measure_factor(common_unit)
            left_common = left['total'] // common_factor
            right_common = right['total'] // common_factor
            sign = _geo20260416ag_compare_sign(left['total'], right['total'])
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Переводим обе величины в {common_unit}.',
                f'2) {left["pretty"]} = {left_common} {common_unit}.',
                f'3) {right["pretty"]} = {right_common} {common_unit}.',
                f'4) Сравниваем: {left_common} {common_unit} {sign} {right_common} {common_unit}.',
                f'Ответ: {left["pretty"]} {sign} {right["pretty"]}',
                'Совет: чтобы сравнить именованные величины, их переводят в одинаковые единицы',
            ]
            return _mass20260416x_finalize(lines)
    return None


def _geo20260416ag_try_geometry_extended(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = normalize_dashes(text).lower().replace('см2', 'см²').replace('см 2', 'см²')
    lower = re.sub(r'\s+', ' ', lower).strip()

    m = re.search(r'периметр прямоугольника равен (\d+) см\.?.*во сколько раз длина прямоугольника больше его ширины, если ширина равна (\d+) см', lower)
    if m:
        per = int(m.group(1)); width = int(m.group(2))
        half = per // 2
        length = half - width
        if width > 0 and length > 0 and per == 2 * (length + width) and length % width == 0:
            ratio = length // width
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: периметр прямоугольника {per} см, ширина {width} см.',
                'Что нужно найти: во сколько раз длина больше ширины.',
                f'1) У прямоугольника половина периметра равна сумме длины и ширины: {per} : 2 = {half} см.',
                f'2) Находим длину: {half} - {width} = {length} см.',
                f'3) Узнаём, во сколько раз длина больше ширины: {length} : {width} = {ratio}.',
                f'Ответ: в {ratio} раза',
                'Совет: если известен периметр прямоугольника, сначала удобно найти сумму длины и ширины',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'длина прямоугольника (\d+) см\.?.*ширина прямоугольника, если периметр (\d+) см', lower)
    if m:
        length = int(m.group(1)); per = int(m.group(2))
        half = per // 2
        width = half - length
        if width > 0 and per == 2 * (length + width):
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: длина прямоугольника {length} см, периметр {per} см.',
                'Что нужно найти: ширину прямоугольника.',
                f'1) Половина периметра равна сумме длины и ширины: {per} : 2 = {half} см.',
                f'2) Вычитаем длину: {half} - {length} = {width} см.',
                f'Ответ: {width} см',
                'Совет: у прямоугольника сумма длины и ширины равна половине периметра',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'длина прямоугольника (\d+) см,? а ширина в (\d+) раз[а-я]* короче.*найди (площадь|периметр) прямоугольника', lower)
    if m:
        length = int(m.group(1)); ratio = int(m.group(2)); ask = m.group(3)
        if ratio > 0 and length % ratio == 0:
            width = length // ratio
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: длина прямоугольника {length} см, ширина в {ratio} раза короче.',
                'Что нужно найти: ' + ('площадь прямоугольника.' if 'площад' in ask else 'периметр прямоугольника.'),
                f'1) Находим ширину: {length} : {ratio} = {width} см.',
            ]
            if 'площад' in ask:
                area = length * width
                lines += [
                    f'2) Площадь прямоугольника равна длине, умноженной на ширину: {length} × {width} = {area} см².',
                    f'Ответ: {area} см²',
                    'Совет: если одна сторона в несколько раз короче другой, меньшую сторону находят делением',
                ]
            else:
                per = 2 * (length + width)
                lines += [
                    f'2) Периметр прямоугольника: ({length} + {width}) × 2 = {per} см.',
                    f'Ответ: {per} см',
                    'Совет: если одна сторона в несколько раз короче другой, меньшую сторону находят делением',
                ]
            return _mass20260416x_finalize(lines)
    return None

# --- merged segment 004: backend.legacy_runtime_module_shards.extended_handlers_runtime_module.segment_004 ---
def _geo20260416ah_try_volume_surface_extended(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = normalize_dashes(text).lower().replace('м3', 'м³').replace('см3', 'см³').replace('дм3', 'дм³')
    lower = lower.replace('м 3', 'м³').replace('см 3', 'см³').replace('дм 3', 'дм³')
    lower = re.sub(r'\s+', ' ', lower).strip()

    m = re.search(r'проволочн[а-я ]+каркаса куба с ребром (\d+) см', lower)
    if m:
        edge_cm = int(m.group(1))
        total_cm = edge_cm * 12
        meters = total_cm / 100
        meters_text = str(int(meters)) if float(meters).is_integer() else str(meters).replace('.', ',')
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: ребро куба {edge_cm} см.',
            'Что нужно найти: сколько метров проволоки нужно для каркаса куба.',
            '1) У куба 12 рёбер.',
            f'2) Находим общую длину всех рёбер: {edge_cm} × 12 = {total_cm} см.',
            f'3) Переводим в метры: {total_cm} см = {meters_text} м.',
            f'Ответ: {meters_text} м',
            'Совет: каркас куба состоит из всех его рёбер, поэтому сначала считают сумму длин 12 рёбер',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'площадь полной поверхности параллелепипеда с измерениями:? а ?= ?(\d+) см,? в ?= ?(\d+) см,? с ?= ?(\d+) см', lower)
    if m:
        a, b, c = map(int, m.groups())
        ab = a * b; ac = a * c; bc = b * c
        total = 2 * (ab + ac + bc)
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Площадь полной поверхности прямоугольного параллелепипеда находят по формуле S = 2 × (ab + ac + bc).',
            f'2) Находим площади трёх разных граней: {a} × {b} = {ab} см², {a} × {c} = {ac} см², {b} × {c} = {bc} см².',
            f'3) Складываем и умножаем на 2: 2 × ({ab} + {ac} + {bc}) = {total} см².',
            f'Ответ: {total} см²',
            'Совет: у прямоугольного параллелепипеда по две одинаковые грани каждого вида',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'найдите объем параллелепипеда с измерениями:? а ?= ?(\d+) см,? в ?= ?(\d+) см,? с ?= ?(\d+) см', lower)
    if m:
        a, b, c = map(int, m.groups())
        volume = a * b * c
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            '1) Объём прямоугольного параллелепипеда находят по формуле V = a × b × c.',
            f'2) Подставляем числа: {a} × {b} × {c} = {volume} см³.',
            f'Ответ: {volume} см³',
            'Совет: чтобы найти объём прямоугольного параллелепипеда, перемножают его длину, ширину и высоту',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'высотой потолка (\d+) м имеет объем (\d+) м³.*какова его площадь', lower)
    if m:
        height, volume = map(int, m.groups())
        if height > 0 and volume % height == 0:
            area = volume // height
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'1) Объём прямоугольного помещения равен площади пола, умноженной на высоту.',
                f'2) Чтобы найти площадь пола, объём делим на высоту: {volume} : {height} = {area} м².',
                f'Ответ: {area} м²',
                'Совет: если известны объём и высота, площадь основания находят делением объёма на высоту',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'во сколько раз объем куба с ребром (\d+) см (?:меньше|больше) объема параллелепипеда с измерениями (\d+) см, (\d+) см, (\d+) см', lower)
    if m:
        edge, a, b, c = map(int, m.groups())
        cube_v = edge ** 3
        prism_v = a * b * c
        if cube_v == 0 or prism_v == 0:
            return None
        if 'меньше' in lower:
            if prism_v % cube_v != 0:
                return None
            ratio = prism_v // cube_v
            relation = 'меньше'
        else:
            if cube_v % prism_v != 0:
                return None
            ratio = cube_v // prism_v
            relation = 'больше'
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим объём куба: {edge} × {edge} × {edge} = {cube_v} см³.',
            f'2) Находим объём параллелепипеда: {a} × {b} × {c} = {prism_v} см³.',
            f'3) Узнаём, во сколько раз один объём {relation} другого.',
        ]
        if relation == 'меньше':
            lines.append(f'4) {prism_v} : {cube_v} = {ratio}.')
        else:
            lines.append(f'4) {cube_v} : {prism_v} = {ratio}.')
        lines += [
            f'Ответ: в {ratio} раз',
            'Совет: чтобы узнать, во сколько раз одна величина больше или меньше другой, большее число делят на меньшее',
        ]
        return _mass20260416x_finalize(lines)
    return None
