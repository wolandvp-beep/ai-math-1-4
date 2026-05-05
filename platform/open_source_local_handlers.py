from __future__ import annotations

import re
from typing import Optional

from backend.legacy_text_helpers import audit_task_line, finalize_legacy_lines
from backend.text_utils import normalize_word_problem_text


GROUP_TARGET_MARKERS = (
    'на тарел',
    'в тарел',
    'на конверт',
    'на пакет',
    'в пакет',
    'на короб',
    'в короб',
    'на блюд',
    'на полк',
    'на открыт',
    'на кажд',
    'в кажд',
)

PART_WHOLE_MARKERS = (
    'из них',
    'красн',
    'син',
    'зелен',
    'мальчик',
    'девоч',
    'яблок',
    'груш',
    'шарик',
    'вороб',
    'синиц',
    'орех',
    'корзин',
    'коробк',
    'книг',
    'птиц',
    'конфет',
    'марок',
    'кубик',
    'фрукт',
    'пакет',
    'во втором',
    'во второй',
    'в одном',
)


def _normalize(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text)




def _extract_last_question(raw_text: str) -> str:
    text = re.sub(r'\s+', ' ', str(raw_text or '')).strip()
    questions = re.findall(r'[^.!?]*\?+', text)
    if not questions:
        return ''
    return questions[-1].rstrip(' ?').strip().lower().replace('ё', 'е')


def _counted_unit_form(unit: str, value: str | int) -> str:
    raw = str(unit or '').strip().lower()
    if not raw:
        return ''
    try:
        n = abs(int(re.sub(r'[^\d-]', '', str(value)) or '0'))
    except ValueError:
        n = 0
    forms = {
        'арбузов': ('арбуз', 'арбуза', 'арбузов'),
        'арбуз': ('арбуз', 'арбуза', 'арбузов'),
        'яблок': ('яблоко', 'яблока', 'яблок'),
        'рублей': ('рубль', 'рубля', 'рублей'),
        'страниц': ('страница', 'страницы', 'страниц'),
        'деревьев': ('дерево', 'дерева', 'деревьев'),
        'тетрадей': ('тетрадь', 'тетради', 'тетрадей'),
        'карандашей': ('карандаш', 'карандаша', 'карандашей'),
        'см': ('см', 'см', 'см'),
        'км': ('км', 'км', 'км'),
        'м': ('м', 'м', 'м'),
    }
    item = forms.get(raw)
    if not item:
        return raw
    last_two = n % 100
    last = n % 10
    if 11 <= last_two <= 14:
        return item[2]
    if last == 1:
        return item[0]
    if 2 <= last <= 4:
        return item[1]
    return item[2]


def _build_full_answer_line(raw_text: str, answer_line: str) -> str:
    line = str(answer_line or '').strip()
    match = re.fullmatch(r'Ответ:\s*(-?\d+(?:[,.]\d+)?)(?:\s+([а-яa-z]+))?\.?', line, flags=re.IGNORECASE)
    if not match:
        return line
    value = match.group(1)
    explicit_unit = match.group(2) or ''
    question = _extract_last_question(raw_text)
    if not question:
        return line

    if 'арбуз' in question and ('трех' in question or 'трёх' in question) and 'машин' in question:
        return f'Ответ: всего на трех машинах вместе {value} {_counted_unit_form("арбузов", value)}.'
    if 'сколько осталось' in question:
        unit = _counted_unit_form(explicit_unit, value) if explicit_unit else ''
        return f'Ответ: осталось {value}{(" " + unit) if unit else ""}.'
    if 'сколько стало' in question:
        unit = _counted_unit_form(explicit_unit, value) if explicit_unit else ''
        return f'Ответ: стало {value}{(" " + unit) if unit else ""}.'
    m = re.search(r'сколько\s+всего\s+([а-яa-z]+)', question)
    if m:
        return f'Ответ: всего {value} {_counted_unit_form(m.group(1), value)}.'
    m = re.search(r'сколько\s+([а-яa-z]+)\s+всего\s+(.+)$', question)
    if m:
        rest = re.sub(r'\s+', ' ', m.group(2)).strip()
        return f'Ответ: {rest} {value} {_counted_unit_form(m.group(1), value)}.'
    if 'периметр' in question:
        return f'Ответ: периметр равен {value}{(" " + explicit_unit) if explicit_unit else ""}.'
    if 'площад' in question:
        return f'Ответ: площадь равна {value}{(" " + explicit_unit) if explicit_unit else ""}.'
    return line


def _enrich_answer_lines(raw_text: str, lines: list[str]) -> list[str]:
    return [_build_full_answer_line(raw_text, line) if str(line or '').strip().lower().startswith('ответ:') else line for line in lines]


def _finalize(lines: list[str]) -> str:
    return finalize_legacy_lines(lines)


def _make_payload(raw_text: str, lines: list[str]) -> str:
    return _finalize(['Задача.', audit_task_line(raw_text), *_enrich_answer_lines(raw_text, lines)])


def _format_signed(value: int) -> str:
    return f'({value})' if value < 0 else str(value)


def _build_simple_system_two_unknowns(raw_text: str) -> Optional[str]:
    """Solve primary-school two-variable systems such as x+y=15; x=y+3.

    The legacy system solver was intentionally conservative and missed cases
    where the difference is negative. This local handler keeps only the
    standard 4th-grade forms and explains them by addition/substitution.
    """
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('−', '-').replace('—', '-')
    if not any(token in lower for token in ('систем', 'x', 'х', 'y', 'у')):
        return None
    compact = re.sub(r'\s+', '', lower)
    compact = compact.replace('х', 'x').replace('у', 'y')
    compact = compact.replace('×', '*').replace('·', '*').replace(':', '/')

    total: Optional[int] = None
    diff: Optional[int] = None

    # x + y = S and x - y = D. Order can be either way.
    total_match = re.search(r'x\+y=(-?\d+)', compact) or re.search(r'y\+x=(-?\d+)', compact)
    diff_match = re.search(r'x-y=(-?\d+)', compact)
    reverse_diff_match = re.search(r'y-x=(-?\d+)', compact)
    relation_match = re.search(r'x=y([+-])(\d+)', compact)
    reverse_relation_match = re.search(r'y=x([+-])(\d+)', compact)

    if total_match:
        total = int(total_match.group(1))
    if diff_match:
        diff = int(diff_match.group(1))
    elif reverse_diff_match:
        diff = -int(reverse_diff_match.group(1))
    elif relation_match:
        sign, value = relation_match.groups()
        diff = int(value) if sign == '+' else -int(value)
    elif reverse_relation_match:
        sign, value = reverse_relation_match.groups()
        # y = x + d -> x - y = -d; y = x - d -> x - y = d
        diff = -int(value) if sign == '+' else int(value)

    if total is None or diff is None:
        return None
    two_x = total + diff
    two_y = total - diff
    if two_x % 2 != 0 or two_y % 2 != 0:
        return None
    x_value = two_x // 2
    y_value = two_y // 2
    if x_value + y_value != total or x_value - y_value != diff:
        return None

    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: сумма чисел x и y равна {total}, а разность x - y равна {diff}.',
        'Что нужно найти: оба неизвестных числа x и y.',
        f'1) Складываем два равенства: (x + y) + (x - y) = {total} + {_format_signed(diff)}.',
        f'2) Слева y и -y уничтожаются, остаётся 2 × x. Получаем: 2 × x = {two_x}.',
        f'3) Находим x: {two_x} : 2 = {x_value}.',
        f'4) Находим y из суммы: {total} - {x_value} = {y_value}.',
        f'5) Проверка: {x_value} + {y_value} = {total}, {x_value} - {y_value} = {diff}.',
        f'Ответ: x = {x_value}, y = {y_value}.',
        'Совет: если известны сумма и разность двух чисел, удобно сложить равенства и сначала найти одно число.',
    ])


def _safe_eval_primary_arithmetic(source: str) -> Optional[int | Fraction]:
    expr = source.strip()
    if not expr:
        return None
    expr = expr.replace('×', '*').replace('·', '*').replace(':', '/').replace('÷', '/')
    expr = re.sub(r'(?<=\d)[xхXХ](?=\d)', '*', expr)
    expr = re.sub(r'\s+', '', expr)
    if not re.fullmatch(r'[0-9+\-*/().]+', expr):
        return None
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError:
        return None

    def ev(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return Fraction(int(node.value), 1)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return ev(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError
                return left / right
        raise ValueError('unsupported expression')

    try:
        value = ev(tree)
    except Exception:
        return None
    return value.numerator if value.denominator == 1 else value


def _format_fraction_or_int(value: int | Fraction) -> str:
    if isinstance(value, Fraction):
        return str(value.numerator) if value.denominator == 1 else f'{value.numerator}/{value.denominator}'
    return str(value)


def _build_comparison_question_mark(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if '?' not in text:
        return None
    if not any(token in lower for token in ('поставь знак', 'сравни', 'какой знак')):
        return None
    # We need the literal question mark between two expressions, not only at
    # the end of a sentence. Keep the original text so signs and numbers stay.
    match = re.search(r'(?:поставь\s+знак|сравни|какой\s+знак)\s*:?\s*(.+?)\?\s*(.+?)(?:[.!?]|$)', text, re.IGNORECASE)
    if not match:
        return None
    left_expr = match.group(1).strip(' .,:;')
    right_expr = match.group(2).strip(' .,:;')
    if not left_expr or not right_expr:
        return None
    left_value = _safe_eval_primary_arithmetic(left_expr)
    right_value = _safe_eval_primary_arithmetic(right_expr)
    if left_value is None or right_value is None:
        return None
    if left_value > right_value:
        sign = '>'
    elif left_value < right_value:
        sign = '<'
    else:
        sign = '='
    left_text = _format_fraction_or_int(left_value)
    right_text = _format_fraction_or_int(right_value)
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: нужно сравнить два выражения: {left_expr} и {right_expr}.',
        'Что нужно найти: какой знак поставить между выражениями.',
        f'1) Вычисляем левую часть: {left_expr} = {left_text}.',
        f'2) Вычисляем правую часть: {right_expr} = {right_text}.',
        f'3) Сравниваем полученные числа: {left_text} {sign} {right_text}.',
        f'Ответ: {left_expr} {sign} {right_expr}.',
        'Совет: чтобы сравнить выражения, сначала вычисли каждое, а потом сравни результаты.',
    ])


def _parse_clock_start(text: str) -> Optional[tuple[int, int]]:
    match = re.search(r'(?:в|во)\s*(\d{1,2})[:.]([0-5]\d)', text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _parse_duration(text: str) -> Optional[tuple[int, int]]:
    lower = text.lower().replace('ё', 'е')
    hours_match = re.search(r'(\d+)\s*(?:ч\.?|час(?:а|ов)?)', lower)
    minutes_match = re.search(r'(\d+)\s*(?:мин\.?|минут(?:ы|)?)', lower)
    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    if hours == 0 and minutes == 0:
        return None
    return hours, minutes


def _format_clock(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    hours, minutes = divmod(total_minutes, 60)
    return f'{hours:02d}:{minutes:02d}'


def _build_clock_arrival_time(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    if not any(phrase in lower for phrase in ('когда', 'во сколько', 'к какому времени')):
        return None
    if not any(phrase in lower for phrase in ('отправ', 'выш', 'начал', 'отплыл', 'выех', 'поезд', 'самолет', 'самолёт', 'автобус', 'урок')):
        return None
    start = _parse_clock_start(text)
    duration = _parse_duration(text)
    if not start or not duration:
        return None
    start_hours, start_minutes = start
    dur_hours, dur_minutes = duration
    start_total = start_hours * 60 + start_minutes
    duration_total = dur_hours * 60 + dur_minutes
    finish_total = start_total + duration_total
    finish_clock = _format_clock(finish_total)
    finish_hours, finish_minutes = divmod(finish_total % (24 * 60), 60)
    duration_pretty_parts = []
    if dur_hours:
        duration_pretty_parts.append(f'{dur_hours} ч')
    if dur_minutes:
        duration_pretty_parts.append(f'{dur_minutes} мин')
    duration_pretty = ' '.join(duration_pretty_parts) or '0 мин'
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: начало было в {start_hours:02d}:{start_minutes:02d}, продолжительность {duration_pretty}.',
        f'Что нужно найти: {("когда закончится событие" if "когда" in lower else "время окончания")}.',
        f'1) Переводим время начала в минуты: {start_hours} ч {start_minutes} мин = {start_total} мин.',
        f'2) Переводим продолжительность в минуты: {dur_hours} ч {dur_minutes} мин = {duration_total} мин.',
        f'3) Находим время окончания в минутах: {start_total} + {duration_total} = {finish_total} мин.',
        f'4) Переводим обратно в часы и минуты: {finish_total % (24 * 60)} мин = {finish_hours} ч {finish_minutes} мин = {finish_clock}.',
        f'Ответ: {finish_clock}.',
        'Совет: чтобы найти время окончания, удобно перевести начало и продолжительность в минуты, выполнить действие, а потом вернуться к часам и минутам.',
    ])


def _build_table_sum_or_difference(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'таблиц' not in lower:
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) != 2:
        return None
    first, second = numbers
    if 'сколько всего' in lower or 'всего' in lower:
        answer = first + second
        return _make_payload(raw_text, [
            'Решение.',
            f'По таблице видим два значения: {first} и {second}.',
            'Что нужно найти: сколько всего.',
            f'1) Складываем данные из таблицы: {first} + {second} = {answer}.',
            f'Ответ: {answer}.',
            'Совет: если по таблице нужно узнать, сколько всего, значения складывают.',
        ])
    if 'на сколько' in lower and any(token in lower for token in ('больше', 'меньше')):
        bigger = max(first, second)
        smaller = min(first, second)
        answer = bigger - smaller
        return _make_payload(raw_text, [
            'Решение.',
            f'По таблице видим два значения: {first} и {second}.',
            'Что нужно найти: на сколько одно значение больше или меньше другого.',
            f'1) Вычитаем меньшее значение из большего: {bigger} - {smaller} = {answer}.',
            f'Ответ: {answer}.',
            'Совет: чтобы узнать, на сколько одно число больше или меньше другого, находят разность.',
        ])
    return None


def _build_total_minus_known_parts(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'таблиц' in lower:
        return None
    if not re.search(r'(?:в|на)\s+перв(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:во|в|на)\s+втор(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:в|на)\s+треть(?:ей|ем)', lower):
        return None
    if not any(token in lower for token in ('в трех', 'в трёх', 'всего', 'вместе')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) < 3:
        return None
    total, first, second = numbers[0], numbers[1], numbers[2]
    answer = total - first - second
    if answer < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: всего {total}, в первой части {first}, во второй части {second}.',
        'Что нужно найти: сколько было в третьей части.',
        f'1) Сначала найдём, сколько уже учтено в первой и второй частях: {first} + {second} = {first + second}.',
        f'2) Теперь найдём третью часть: {total} - {first + second} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если известно общее количество и две части, сначала сложи известные части, а потом вычти их из общего количества.',
    ])


def _build_three_part_relative_chain(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if not re.search(r'(?:на|в)\s+перв(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:на|во|в)\s+втор(?:ой|ом)', lower):
        return None
    if not re.search(r'(?:на|в)\s+треть(?:ей|ем)', lower):
        return None

    first_match = re.search(r'(?:на|в)\s+перв(?:ой|ом)\b[^.?!]*?(\d+)', lower)
    second_match = re.search(r'(?:на|во|в)\s+втор(?:ой|ом)\b[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b[^.?!]*?чем\s+(?:на|в)\s+перв', lower)
    third_match = re.search(r'(?:на|в)\s+треть(?:ей|ем)\b[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b[^.?!]*?чем\s+(?:на|во|в)\s+втор', lower)
    if not first_match or not second_match or not third_match:
        return None
    first_value = int(first_match.group(1))
    second_delta = int(second_match.group(1))
    second_rel = second_match.group(2)
    third_delta = int(third_match.group(1))
    third_rel = third_match.group(2)
    second_value = first_value + second_delta if second_rel == 'больше' else first_value - second_delta
    third_value = second_value + third_delta if third_rel == 'больше' else second_value - third_delta
    if second_value < 0 or third_value < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: в первой части {first_value}. Во второй количество связано с первой, а в третьей — со второй.',
        'Что нужно найти: количество в третьей части.',
        f'1) Находим вторую часть: {first_value} {"+" if second_rel == "больше" else "-"} {second_delta} = {second_value}.',
        f'2) Находим третью часть: {second_value} {"+" if third_rel == "больше" else "-"} {third_delta} = {third_value}.',
        f'Ответ: {third_value}.',
        'Совет: в цепочке из трёх частей сначала найди вторую часть по первой, а потом третью по второй.',
    ])


def _build_three_container_relative_total(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')

    if 'сколько' not in lower or not any(token in lower for token in ('всего', 'вместе')):
        return None
    if not re.search(r'(?:на|в)\s+(?:одной|одном|первой|первом)\b', lower):
        return None
    if not re.search(r'(?:на|во|в)\s+(?:другой|другом|второй|втором)\b', lower):
        return None
    if not re.search(r'(?:на|в)\s+треть(?:ей|ем)\b', lower):
        return None

    first_match = re.search(
        r'(?:на|в)\s+(?:одной|одном|первой|первом)\b[^.?!]*?(\d+)',
        lower,
    )
    second_match = re.search(
        r'(?:на|во|в)\s+(?:другой|другом|второй|втором)\b[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b[^.?!]*?чем\s+(?:на|в)\s+(?:первой|первом|одной|одном)',
        lower,
    )
    third_sum_match = re.search(
        r'(?:на|в)\s+треть(?:ей|ем)\b[^.?!]*?столько[^.?!]*?сколько[^.?!]*?(?:перв(?:ой|ом)|одн(?:ой|ом))[^.?!]*?(?:втор(?:ой|ом)|друг(?:ой|ом))',
        lower,
    )

    if not first_match or not second_match or not third_sum_match:
        return None

    first_value = int(first_match.group(1))
    second_delta = int(second_match.group(1))
    second_rel = second_match.group(2)
    second_value = first_value + second_delta if second_rel == 'больше' else first_value - second_delta
    if second_value < 0:
        return None
    third_value = first_value + second_value
    answer = first_value + second_value + third_value

    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: на первой машине {first_value}; на второй на {second_delta} {second_rel}, чем на первой; на третьей столько, сколько на первой и второй вместе.',
        'Что нужно найти: сколько всего на трёх машинах вместе.',
        f'1) Находим, сколько на второй машине: {first_value} {"+" if second_rel == "больше" else "-"} {second_delta} = {second_value}.',
        f'2) Находим, сколько на третьей машине: {first_value} + {second_value} = {third_value}.',
        f'3) Складываем арбузы на трёх машинах: {first_value} + {second_value} + {third_value} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: сначала найди неизвестные части по условию, и только потом складывай все части вместе.',
    ])


def _build_two_part_relative_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower:
        return None
    if 'на сколько' in lower:
        return None
    # Типичная задача 1–2 класса: в первой части известно число,
    # во второй на N больше/меньше. Нужно найти вторую часть.
    patterns = [
        re.search(r'(?:в|на)\s+перв(?:ой|ом)\b[^.?!]*?(\d+)[^.?!]*?(?:во|в|на)\s+втор(?:ой|ом)\b[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b', lower),
        re.search(r'у\s+[^.?!,]+?\s+(\d+)[^.?!]*?у\s+[^.?!,]+?\s+на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b', lower),
        re.search(r'([а-яa-z]+)\s+[^.?!]*?(\d+)[^.?!]*?(?:втор[а-я]*|друг[а-я]*|ещ[её]\s+одн[а-я]*)[^.?!]*?на\s+(\d+)\s+[^.?!]*?\b(больше|меньше)\b', lower),
    ]
    match = next((item for item in patterns if item), None)
    if not match:
        return None

    groups = match.groups()
    if len(groups) == 3:
        base, delta, relation = int(groups[0]), int(groups[1]), groups[2]
    elif len(groups) == 4:
        base, delta, relation = int(groups[1]), int(groups[2]), groups[3]
    else:
        return None

    answer = base + delta if relation == 'больше' else base - delta
    if answer < 0:
        return None
    sign = '+' if relation == 'больше' else '-'
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: первая величина равна {base}, вторая на {delta} {relation}.',
        'Что нужно найти: вторую величину.',
        f'1) Если во второй части на {delta} {relation}, выполняем действие: {base} {sign} {delta} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: слова «на больше» ведут к сложению, а слова «на меньше» — к вычитанию.',
    ])


def _build_part_whole_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower:
        return None
    if 'таблиц' in lower or 'по таблице' in lower or 'на сколько' in lower:
        return None
    if 'поровну' in lower or (re.search(r'по\s+\d+', lower) and any(marker in lower for marker in GROUP_TARGET_MARKERS)):
        return None
    if any(token in lower for token in ('таких ', 'кажд', ' раза ', ' раз ', 'прилет', 'прибеж', 'приш', 'появил', 'стало', 'стал', 'посад', 'ряд', 'маршрут')):
        return None
    explicit_part_markers = ('из них', 'красн', 'син', 'вороб', 'синиц', 'в одном', 'во втором', 'в первой', 'во второй')
    if ('всего' in lower or 'вместе' in lower) and not any(marker in lower for marker in explicit_part_markers):
        return None
    if any(verb in lower for verb in ('дал', 'отдал', 'съел', 'потрат', 'добав', 'купил', 'принес', 'принёс')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) != 2:
        return None
    if not any(marker in lower for marker in PART_WHOLE_MARKERS):
        return None
    total, known_part = numbers
    answer = total - known_part
    if answer < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: всего {total}, одна часть равна {known_part}.',
        'Что нужно найти: другую часть.',
        f'1) Из общего количества вычитаем известную часть: {total} - {known_part} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если известно целое и одна часть, вторую часть находят вычитанием.',
    ])



def _build_equal_groups_division(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')
    if 'сколько' not in lower or 'по ' not in lower:
        return None
    if not ('поровну' in lower or any(marker in lower for marker in GROUP_TARGET_MARKERS)):
        return None
    match = re.search(r'(\d+)[^.?!]*?по\s+(\d+)', lower)
    if not match:
        return None
    total = int(match.group(1))
    per_group = int(match.group(2))
    if per_group == 0 or total % per_group != 0:
        return None
    groups = total // per_group
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: всего {total}, в каждой группе по {per_group}.',
        'Что нужно найти: сколько получилось одинаковых групп.',
        f'1) Чтобы найти число групп, делим общее количество на количество в одной группе: {total} : {per_group} = {groups}.',
        f'Ответ: {groups}.',
        'Совет: когда известно, сколько всего и по сколько в каждой группе, число групп находят делением.',
    ])



def _build_compose_number(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е')

    match = re.search(
        r'(?:запиши|составь)\s+число,?\s+в\s+котором\s+(\d+)\s+тысяч(?:а|и|)?\s+(\d+)\s+сот(?:ня|ни|ен)\s+(\d+)\s+десят(?:ок|ка|ков)\s+(\d+)\s+единиц(?:а|ы|)?',
        lower,
    )
    if match:
        thousands, hundreds, tens, ones = map(int, match.groups())
        value = thousands * 1000 + hundreds * 100 + tens * 10 + ones
        return _make_payload(raw_text, [
            'Решение.',
            f'Собираем число из разрядов: {thousands} тысяч, {hundreds} сотен, {tens} десятков и {ones} единиц.',
            f'1) {thousands} тысяч = {thousands * 1000}.',
            f'2) {hundreds} сотен = {hundreds * 100}.',
            f'3) {tens} десятков = {tens * 10}.',
            f'4) {thousands * 1000} + {hundreds * 100} + {tens * 10} + {ones} = {value}.',
            f'Ответ: {value}.',
            'Совет: чтобы составить число по разрядам, складывают тысячи, сотни, десятки и единицы.',
        ])

    match = re.search(r'(?:запиши|составь)\s+число,?\s+в\s+котором\s+(\d+)\s+сот(?:ня|ни|ен)\s+(\d+)\s+десят(?:ок|ка|ков)\s+(\d+)\s+единиц(?:а|ы|)?', lower)
    if match:
        hundreds, tens, ones = map(int, match.groups())
        value = hundreds * 100 + tens * 10 + ones
        return _make_payload(raw_text, [
            'Решение.',
            f'Собираем число из разрядов: {hundreds} сотен, {tens} десятков и {ones} единиц.',
            f'1) {hundreds} сотен = {hundreds * 100}.',
            f'2) {tens} десятков = {tens * 10}.',
            f'3) {hundreds * 100} + {tens * 10} + {ones} = {value}.',
            f'Ответ: {value}.',
            'Совет: чтобы составить число по разрядам, складывают сотни, десятки и единицы.',
        ])

    match = re.search(r'(?:запиши|составь)\s+число,?\s+в\s+котором\s+(\d+)\s+десят(?:ок|ка|ков)\s+и\s+(\d+)\s+единиц(?:а|ы|)?', lower)
    if not match:
        match = re.search(r'(?:запиши|составь)\s+число,?\s+из\s+(\d+)\s+десят(?:ок|ка|ков)\s+и\s+(\d+)\s+единиц(?:а|ы|)?', lower)
    if match:
        tens, ones = map(int, match.groups())
        value = tens * 10 + ones
        return _make_payload(raw_text, [
            'Решение.',
            f'Собираем число из разрядов: {tens} десятков и {ones} единиц.',
            f'1) {tens} десятков = {tens * 10}.',
            f'2) {tens * 10} + {ones} = {value}.',
            f'Ответ: {value}.',
            'Совет: двузначное число можно составить из десятков и единиц.',
        ])
    return None



def _build_simple_change_total_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower:
        return None
    if 'остал' in lower:
        return None
    if not any(token in lower for token in ('стало', 'станет', 'всего стало')):
        return None
    if not any(token in lower for token in ('прилет', 'приш', 'прибеж', 'добав', 'полож', 'купил', 'принес', 'принёс')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) < 2:
        return None
    first, added = numbers[0], numbers[1]
    answer = first + added
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: сначала было {first}, потом добавилось ещё {added}.',
        'Что нужно найти: сколько стало всего.',
        f'1) Когда добавляют, выполняем сложение: {first} + {added} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если к количеству что-то добавили или кто-то прилетел, число увеличивается, значит складываем.',
    ])


def _build_sequential_removed_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower or 'остал' not in lower:
        return None
    if not any(token in lower for token in ('продал', 'отдал', 'съел', 'потрат', 'израсход', 'ушл')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if len(numbers) < 3:
        return None
    start, first_removed, second_removed = numbers[0], numbers[1], numbers[2]
    removed_total = first_removed + second_removed
    answer = start - removed_total
    if answer < 0:
        return None
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: сначала было {start}, потом убрали {first_removed} и ещё {second_removed}.',
        'Что нужно найти: сколько осталось.',
        f'1) Сначала найдём, сколько всего убрали: {first_removed} + {second_removed} = {removed_total}.',
        f'2) Теперь вычтем это из начального количества: {start} - {removed_total} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если убирали несколько раз, сначала можно сложить всё, что убрали, а потом вычесть из начального количества.',
    ])


def _build_equal_groups_multiplication(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower:
        return None
    # Защита от задач вида: «на одной машине 176, на другой на 234 больше,
    # на третьей столько, сколько на первой и второй вместе». Там число 234 —
    # не количество одинаковых групп, а разница между частями.
    if re.search(r'(?:на|во|в)\s+(?:другой|другом|второй|втором)\b[^.?!]*?на\s+\d+\s+[^.?!]*?\b(?:больше|меньше)\b', lower):
        return None

    # Формы: «в одной коробке 6 ... в 5 таких коробках»,
    # «в каждом ряду 9 парт ... в 4 рядах».
    match = re.search(
        r'(?:в|на)\s+(?:одной|одном|одну|каждой|каждом|каждом\s+ряду|каждом\s+пакете|каждой\s+коробке)\b.*?(\d+).*?(?:в|на)\s+(\d+)\s+(?:таких\s+)?[а-яa-z]+',
        lower,
    )
    if not match:
        match = re.search(r'в\s+кажд(?:ом|ой)\s+[а-яa-z]+\s+(\d+).*?в\s+(\d+)\s+[а-яa-z]+', lower)
    if not match:
        if not re.search(r'\b(?:в|на)\s+(?:одной|одном|одну|каждой|каждом)\b', lower):
            return None
        if not re.search(r'\b(?:в|на)\s+\d+\s+таких\b', lower):
            return None
        numbers = [int(value) for value in re.findall(r'\d+', lower)]
        if len(numbers) < 2:
            return None
        per_group, groups = numbers[0], numbers[1]
    else:
        per_group, groups = int(match.group(1)), int(match.group(2))
    answer = per_group * groups
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: в одной группе {per_group}, таких групп {groups}.',
        'Что нужно найти: сколько всего.',
        f'1) Чтобы найти общее количество, умножаем количество в одной группе на число групп: {per_group} × {groups} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: если одинаковых групп несколько, общее количество находят умножением.',
    ])


def _build_multiplicative_comparison_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower:
        return None
    match = re.search(r'(\d+)[^.?!]*?в\s+(\d+)\s+раз(?:а)?\s+(меньше|больше)', lower)
    if not match:
        return None
    base = int(match.group(1))
    factor = int(match.group(2))
    relation = match.group(3)
    if factor == 0:
        return None
    answer = base // factor if relation == 'меньше' and base % factor == 0 else base / factor if relation == 'меньше' else base * factor
    if isinstance(answer, float) and answer.is_integer():
        answer = int(answer)
    op = ':' if relation == 'меньше' else '×'
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: первое количество {base}, второе в {factor} раза {relation}.',
        'Что нужно найти: второе количество.',
        f'1) Если в {factor} раза {relation}, выполняем {"деление" if relation == "меньше" else "умножение"}: {base} {op} {factor} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: «в несколько раз меньше» — делим, а «в несколько раз больше» — умножаем.',
    ])


def _build_named_sum_of_two_products(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    if 'сколько' not in lower or 'всего' not in lower:
        return None
    # Typical primary-school form: 4 ряда берёз по 9 деревьев и 3 ряда клёнов по 8 деревьев.
    matches = re.findall(r'(\d+)\s+[^.?!]*?\bпо\s+(\d+)', lower)
    if len(matches) < 2:
        return None
    a_groups, a_per = map(int, matches[0])
    b_groups, b_per = map(int, matches[1])
    first_total = a_groups * a_per
    second_total = b_groups * b_per
    answer = first_total + second_total
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: есть две группы: {a_groups} по {a_per} и {b_groups} по {b_per}.',
        'Что нужно найти: сколько всего.',
        f'1) Находим количество в первой группе: {a_groups} × {a_per} = {first_total}.',
        f'2) Находим количество во второй группе: {b_groups} × {b_per} = {second_total}.',
        f'3) Складываем результаты: {first_total} + {second_total} = {answer}.',
        f'Ответ: {answer}.',
        'Совет: в задаче с двумя одинаковыми группами сначала посчитай каждую группу, потом сложи результаты.',
    ])


def _build_fraction_of_whole_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    # Не путать долю «треть» с порядковым словом «в третьей коробке».
    if re.search(r'\b(?:в|на|во)\s+треть(?:ей|ем|ю)\b', lower):
        return None
    if not any(token in lower for token in ('треть', 'половин', 'четверт', 'пят')):
        return None
    if any(token in lower for token in ('что составляет', 'это составляет', 'составляет')):
        return None
    if not any(token in lower for token in ('отрез', 'израсход', 'потрат', 'прочитал', 'закрас', 'съел', 'взял', 'нашли', 'найди', 'сколько')):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if not numbers:
        return None
    whole = numbers[0]
    denom = None
    part_name = ''
    if 'треть' in lower:
        denom, part_name = 3, 'треть'
    elif 'половин' in lower:
        denom, part_name = 2, 'половина'
    elif 'четверт' in lower:
        denom, part_name = 4, 'четверть'
    elif 'пят' in lower:
        denom, part_name = 5, 'пятая часть'
    if not denom or whole % denom != 0:
        return None
    answer = whole // denom
    unit_match = re.search(r'\d+\s*([а-яa-z/]+)', lower)
    unit = unit_match.group(1) if unit_match else ''
    answer_unit = f' {unit}' if unit else ''
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: целое равно {whole}{answer_unit}, нужно найти {part_name}.',
        'Что нужно найти: одну долю от целого.',
        f'1) {part_name.capitalize()} — это 1/{denom} целого, поэтому делим целое на {denom}: {whole} : {denom} = {answer}.',
        f'Ответ: {answer}{answer_unit}.',
        'Совет: чтобы найти долю от числа, раздели число на количество равных долей.',
    ])


def _build_fraction_inverse_whole_problem(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('—', '-')
    # Не путать долю «треть» с порядковым словом «в третьей коробке».
    if re.search(r'\b(?:в|на|во)\s+треть(?:ей|ем|ю)\b', lower):
        return None
    inverse_markers = ('что составляет', 'это составляет', 'составляет')
    if 'сколько' in lower and 'какова' not in lower and 'найди' not in lower and not any(token in lower for token in inverse_markers):
        return None
    if not any(token in lower for token in ('треть', 'половин', 'четверт', 'пят')):
        return None
    if not (any(token in lower for token in ('всего', 'весь', 'всего маршрута', 'маршрут', 'книга', 'книге')) or any(token in lower for token in inverse_markers)):
        return None
    numbers = [int(value) for value in re.findall(r'\d+', lower)]
    if not numbers:
        return None
    known = numbers[0]
    denom = None
    part_name = ''
    if 'треть' in lower:
        denom, part_name = 3, 'треть'
    elif 'половин' in lower:
        denom, part_name = 2, 'половина'
    elif 'четверт' in lower:
        denom, part_name = 4, 'четверть'
    elif 'пят' in lower:
        denom, part_name = 5, 'пятая часть'
    if not denom:
        return None
    answer = known * denom
    unit_match = re.search(r'\d+\s*([а-яa-z/]+)', lower)
    unit = unit_match.group(1) if unit_match else ''
    answer_unit = f' {unit}' if unit else ''
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: {known}{answer_unit} — это {part_name} всего.',
        'Что нужно найти: целое.',
        f'1) Если {known}{answer_unit} — это 1/{denom}, то целое в {denom} раза больше.',
        f'2) Находим целое: {known} × {denom} = {answer}.',
        f'Ответ: {answer}{answer_unit}.',
        'Совет: если дана одна доля и нужно найти всё целое, умножаем значение доли на число долей.',
    ])


from fractions import Fraction
import ast


def _extract_equation_expression(raw_text: str) -> Optional[str]:
    text = _normalize(raw_text)
    lower = text.lower().replace('ё', 'е').replace('×', '*').replace('·', '*').replace(':', '/')
    if '=' not in lower or 'x' not in lower:
        return None

    # Ребёнок часто пишет не только само уравнение, а фразу:
    # «Реши уравнение: 5x + 7 = 42». Для вычисления берём только
    # математическую часть вокруг знака равно.
    normalized = re.sub(r'\s+', '', lower)
    allowed = r'0-9x+\-*/().'
    match = re.search(rf'([{allowed}]*x[{allowed}]*)=([{allowed}]+)', normalized)
    if not match:
        return None
    expr = f'{match.group(1)}={match.group(2)}'
    # Если перед уравнением была фраза «Реши:», двоеточие уже
    # превратилось в символ деления. Убираем такой технический хвост
    # слева, но не трогаем минус у отрицательного числа.
    expr = re.sub(r'^[+*/]+', '', expr)
    if expr.count('=') != 1:
        return None

    # Поддерживаем школьную запись 5x вместо 5*x.
    expr = re.sub(r'(\d)(x)', r'\1*\2', expr)
    expr = re.sub(r'(x)(\d)', r'\1*\2', expr)
    expr = re.sub(r'(\))(x)', r'\1*\2', expr)
    expr = re.sub(r'(x)(\()', r'\1*\2', expr)
    if not re.fullmatch(r'[0-9x+\-*/().=]+', expr):
        return None
    return expr


def _build_linear_equation_problem(raw_text: str) -> Optional[str]:
    expr = _extract_equation_expression(raw_text)
    if not expr:
        return None
    left, right = expr.split('=', 1)

    def eval_expr(source: str, x_value: Fraction) -> Fraction:
        tree = ast.parse(source, mode='eval')
        def ev(node: ast.AST) -> Fraction:
            if isinstance(node, ast.Expression):
                return ev(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, int):
                return Fraction(int(node.value), 1)
            if isinstance(node, ast.Name) and node.id == 'x':
                return x_value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                return -ev(node.operand)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
                return ev(node.operand)
            if isinstance(node, ast.BinOp):
                a, b = ev(node.left), ev(node.right)
                if isinstance(node.op, ast.Add): return a + b
                if isinstance(node.op, ast.Sub): return a - b
                if isinstance(node.op, ast.Mult): return a * b
                if isinstance(node.op, ast.Div):
                    if b == 0: raise ZeroDivisionError
                    return a / b
            raise ValueError('unsupported equation')
        return ev(tree)

    try:
        f0 = eval_expr(left, Fraction(0)) - eval_expr(right, Fraction(0))
        f1 = eval_expr(left, Fraction(1)) - eval_expr(right, Fraction(1))
    except Exception:
        return None
    coef = f1 - f0
    if coef == 0:
        return None
    solution = -f0 / coef
    try:
        if eval_expr(left, solution) != eval_expr(right, solution):
            return None
    except Exception:
        return None
    answer = str(solution.numerator) if solution.denominator == 1 else f'{solution.numerator}/{solution.denominator}'
    pretty = raw_text.strip()

    # Friendlier explanations for the two most common 4-grade patterns.
    match = re.fullmatch(r'(\d+)\*x\+(\d+)=(\d+)', expr)
    if match:
        a, b, c = map(int, match.groups())
        after_sub = c - b
        return _make_payload(raw_text, [
            'Решение.',
            f'Что известно: {a} × x + {b} = {c}.',
            'Что нужно найти: значение x.',
            f'1) Сначала убираем прибавленное число {b}: {c} - {b} = {after_sub}.',
            f'2) Получаем {a} × x = {after_sub}. Чтобы найти x, делим: {after_sub} : {a} = {answer}.',
            f'3) Проверка: {a} × {answer} + {b} = {c}.',
            f'Ответ: {answer}.',
            'Совет: в сложном уравнении иди обратными действиями: сначала убери последнее действие, потом предыдущее.',
        ])
    match = re.fullmatch(r'(\d+)\*\(x\+(\d+)\)=(\d+)', expr)
    if match:
        a, b, c = map(int, match.groups())
        after_div = Fraction(c, a)
        after_div_text = str(after_div.numerator) if after_div.denominator == 1 else f'{after_div.numerator}/{after_div.denominator}'
        return _make_payload(raw_text, [
            'Решение.',
            f'Что известно: {a} × (x + {b}) = {c}.',
            'Что нужно найти: значение x.',
            f'1) Сначала убираем умножение на {a}: {c} : {a} = {after_div_text}.',
            f'2) Получаем x + {b} = {after_div_text}. Теперь вычитаем {b}: {after_div_text} - {b} = {answer}.',
            f'3) Проверка: {a} × ({answer} + {b}) = {c}.',
            f'Ответ: {answer}.',
            'Совет: если в уравнении есть скобки, сначала найди значение всей скобки, а потом неизвестное внутри неё.',
        ])
    return _make_payload(raw_text, [
        'Решение.',
        f'Что известно: уравнение {pretty}.',
        'Что нужно найти: значение x.',
        f'1) Рассматриваем левую и правую части как равные выражения.',
        f'2) По обратным действиям получаем x = {answer}.',
        f'3) Подставляем x = {answer} и проверяем равенство.',
        f'Ответ: {answer}.',
        'Совет: после решения уравнения всегда делай проверку подстановкой.',
    ])


def build_open_source_curriculum_explanation(raw_text: str) -> Optional[str]:
    return (
        _build_simple_system_two_unknowns(raw_text)
        or _build_comparison_question_mark(raw_text)
        or _build_linear_equation_problem(raw_text)
        or _build_table_sum_or_difference(raw_text)
        or _build_three_container_relative_total(raw_text)
        or _build_total_minus_known_parts(raw_text)
        or _build_simple_change_total_problem(raw_text)
        or _build_sequential_removed_problem(raw_text)
        or _build_equal_groups_multiplication(raw_text)
        or _build_multiplicative_comparison_problem(raw_text)
        or _build_named_sum_of_two_products(raw_text)
        or _build_fraction_of_whole_problem(raw_text)
        or _build_fraction_inverse_whole_problem(raw_text)
        or _build_equal_groups_division(raw_text)
        or _build_two_part_relative_problem(raw_text)
        or _build_part_whole_problem(raw_text)
        or _build_compose_number(raw_text)
        or _build_clock_arrival_time(raw_text)
        or _build_three_part_relative_chain(raw_text)
    )


__all__ = ['build_open_source_curriculum_explanation']
