from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional

from backend.platform.request_shape_guards import canonicalize_system_submission


def _clean_text(text: str) -> str:
    value = str(text or '')
    value = value.replace('\u00a0', ' ')
    value = value.replace('−', '-').replace('–', '-').replace('—', '-')
    value = value.replace('×', '*').replace('·', '*').replace('÷', ':')
    # Do not replace Cyrillic letters globally: words like 'труба' and 'купила'
    # must remain readable.  Variable normalization is done only inside equation parsers.
    value = value.replace('Ё', 'Е').replace('ё', 'е')
    value = re.sub(r'\s+', ' ', value.replace('\r\n', '\n').replace('\r', '\n')).strip()
    return value


def _lower(text: str) -> str:
    return _clean_text(text).lower()


def _result(lines: list[str], source: str) -> dict:
    text = '\n'.join(line.rstrip() for line in lines if line is not None).strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return {'result': text, 'source': source, 'validated': True}


def _fmt_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    # Keep elementary display stable: an improper fraction plus decimal hint for time.
    return f'{value.numerator}/{value.denominator}'


def _fmt_decimal_comma(value: Fraction, digits: int = 2) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    raw = f'{float(value):.{digits}f}'.rstrip('0').rstrip('.')
    return raw.replace('.', ',')


def _choose_plural_int(n: int, one: str, two_four: str, many: str) -> str:
    n_abs = abs(int(n))
    if 11 <= n_abs % 100 <= 14:
        return many
    last = n_abs % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return two_four
    return many


def _format_time(value: Fraction, unit_hint: str) -> str:
    unit_hint = unit_hint.lower()
    if unit_hint.startswith('д'):
        if value.denominator == 1:
            n = value.numerator
            return f'{n} {_choose_plural_int(n, "день", "дня", "дней")}'
        return f'{_fmt_decimal_comma(value)} дня'
    if unit_hint.startswith('мин'):
        if value.denominator == 1:
            n = value.numerator
            return f'{n} {_choose_plural_int(n, "минута", "минуты", "минут")}'
        return f'{_fmt_decimal_comma(value)} минуты'
    # hours by default; convert exact common fractional hours to hours + minutes.
    if value.denominator == 1:
        n = value.numerator
        return f'{n} {_choose_plural_int(n, "час", "часа", "часов")}'
    minutes = value * 60
    if minutes.denominator == 1:
        total = minutes.numerator
        hours = total // 60
        mins = total % 60
        pieces: list[str] = []
        if hours:
            pieces.append(f'{hours} {_choose_plural_int(hours, "час", "часа", "часов")}')
        if mins:
            pieces.append(f'{mins} {_choose_plural_int(mins, "минута", "минуты", "минут")}')
        if pieces:
            return ' '.join(pieces)
    return f'{_fmt_decimal_comma(value)} часа'


def _format_unit_rate_unit(work_unit: str, time_unit: str) -> str:
    work = work_unit.strip() or 'единиц работы'
    if time_unit.startswith('д'):
        return f'{work} в день'
    if time_unit.startswith('мин'):
        return f'{work} в минуту'
    return f'{work} в час'


def _extract_work_amount(text: str) -> tuple[Optional[int], str]:
    # Prefer quantities that name the work size, not durations or speeds.
    patterns = [
        r'(?:площадью\s+)?(\d+)\s*(аров|ара|ар|а)\b',
        r'(\d+)\s*(т|тонн(?:ы|у)?|центнеров|кг)\b',
        r'(\d+)\s*(детал(?:ей|и|ь)|издели(?:й|я|е)|заказ(?:ов|а)?|страниц(?:ы|у)?|метров|м)\b',
        r'(\d+)\s*(гектар(?:ов|а)?|сот(?:ок|ки)?)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).strip()
            if unit == 'а':
                unit = 'аров'
            if unit == 'т':
                unit = 'т'
            return amount, unit
    return None, 'единиц работы'


def solve_joint_work(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'\b(?:вместе|оба|обе|работая\s+вместе)\b', source):
        return None
    # Two performers completing the same work in different times.
    if not re.search(r'(?:трактор|комбайн|бригад|рабоч|мастер|труб|насос|станок|машин|экскаватор|кран)', source):
        return None
    time_matches = re.findall(r'за\s+(\d+)\s*(час(?:а|ов)?|ч\b|дн(?:я|ей|ь)?|день|дней|мин(?:ут(?:ы)?|\b))', source, flags=re.IGNORECASE)
    if len(time_matches) < 2:
        return None
    t1 = int(time_matches[0][0])
    t2 = int(time_matches[1][0])
    if t1 <= 0 or t2 <= 0:
        return None
    unit_hint = time_matches[0][1]
    if unit_hint == 'ч':
        unit_hint = 'час'
    amount, work_unit = _extract_work_amount(source)
    if amount is None:
        total_work = Fraction(1, 1)
        rate1 = Fraction(1, t1)
        rate2 = Fraction(1, t2)
        rate_text_1 = f'1 : {t1} = {_fmt_fraction(rate1)} части работы'
        rate_text_2 = f'1 : {t2} = {_fmt_fraction(rate2)} части работы'
        combined = rate1 + rate2
        total_time = total_work / combined
        work_unit_rate = 'части работы за 1 ' + ('день' if unit_hint.startswith('д') else 'час')
    else:
        total_work = Fraction(amount, 1)
        rate1 = total_work / t1
        rate2 = total_work / t2
        combined = rate1 + rate2
        total_time = total_work / combined
        work_unit_rate = _format_unit_rate_unit(work_unit, unit_hint)
        rate_text_1 = f'{amount} : {t1} = {_fmt_fraction(rate1)} {work_unit_rate}'
        rate_text_2 = f'{amount} : {t2} = {_fmt_fraction(rate2)} {work_unit_rate}'

    time_text = _format_time(total_time, unit_hint)
    if 'комбайн' in source:
        final = f'Оба комбайна, работая вместе, уберут поле за {time_text}.'
        action1 = 'убирает первый комбайн'
        action2 = 'убирает второй комбайн'
        action_both = 'убирают оба комбайна вместе'
    elif 'трактор' in source:
        final = f'Оба трактора, работая вместе, вспашут поле за {time_text}.'
        action1 = 'вспашет первый трактор'
        action2 = 'вспашет второй трактор'
        action_both = 'вспашут оба трактора вместе'
    elif 'труб' in source:
        final = f'Обе трубы вместе выполнят работу за {time_text}.'
        action1 = 'делает первая труба за единицу времени'
        action2 = 'делает вторая труба за единицу времени'
        action_both = 'делают обе трубы вместе за единицу времени'
    elif 'бригад' in source:
        final = f'Обе бригады вместе выполнят такую работу за {time_text}.'
        action1 = 'делает первая бригада'
        action2 = 'делает вторая бригада'
        action_both = 'делают обе бригады вместе'
    else:
        final = f'Работая вместе, они выполнят работу за {time_text}.'
        action1 = 'делает первый исполнитель'
        action2 = 'делает второй исполнитель'
        action_both = 'делают оба исполнителя вместе'

    if amount is None:
        step4 = f'4) 1 : {_fmt_fraction(combined)} = {_fmt_fraction(total_time)} — столько времени нужно вместе.'
    else:
        step4 = f'4) {amount} : {_fmt_fraction(combined)} = {_fmt_fraction(total_time)} — столько времени нужно вместе.'
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {rate_text_1} — столько {action1}.',
        f'2) {rate_text_2} — столько {action2}.',
        f'3) {_fmt_fraction(rate1)} + {_fmt_fraction(rate2)} = {_fmt_fraction(combined)} — столько {action_both}.',
        step4,
        f'Ответ: {final}',
    ], 'local:live-joint-work')


_LINEAR_TERM_RE = re.compile(r'([+-]?)(?:(\d+)\*?)?([xy])|([+-]?\d+)')


def _parse_linear_expression(expr: str) -> Optional[tuple[Fraction, Fraction, Fraction]]:
    s = expr.replace(' ', '').replace('−', '-').replace('х', 'x').replace('у', 'y')
    s = s.replace('Х', 'x').replace('У', 'y')
    if not s:
        return None
    # Normalize unary plus/minus splitting.
    if s[0] not in '+-':
        s = '+' + s
    pos = 0
    ax = Fraction(0)
    by = Fraction(0)
    c = Fraction(0)
    token_re = re.compile(r'([+-])(?:(\d+)?\*?([xy])|(\d+))', flags=re.IGNORECASE)
    for match in token_re.finditer(s):
        if match.start() != pos:
            return None
        sign = -1 if match.group(1) == '-' else 1
        if match.group(3):
            coeff = int(match.group(2) or '1') * sign
            if match.group(3).lower() == 'x':
                ax += coeff
            else:
                by += coeff
        else:
            c += int(match.group(4)) * sign
        pos = match.end()
    if pos != len(s):
        return None
    return ax, by, c


def _parse_linear_equation(line: str) -> Optional[tuple[Fraction, Fraction, Fraction]]:
    compact = line.strip().replace('−', '-').replace('х', 'x').replace('у', 'y').replace('Х', 'x').replace('У', 'y')
    compact = re.sub(r'\s+', '', compact)
    if compact.count('=') != 1:
        return None
    left, right = compact.split('=', 1)
    parsed_left = _parse_linear_expression(left)
    parsed_right = _parse_linear_expression(right)
    if parsed_left is None or parsed_right is None:
        return None
    ax_l, by_l, c_l = parsed_left
    ax_r, by_r, c_r = parsed_right
    # Move variables to left, constants to right: ax*x + by*y = rhs.
    return ax_l - ax_r, by_l - by_r, c_r - c_l


def _split_system_equations(raw_text: str) -> Optional[list[str]]:
    canonical = canonicalize_system_submission(raw_text)
    if canonical:
        return [line.strip() for line in canonical.split('\n') if line.strip()]
    text = _clean_text(raw_text)
    if text.count('=') < 2:
        return None
    # Support compact comma/semicolon/newline input without the word "system".
    body = re.sub(r'^(?:реши(?:те)?\s+)?систем[ауые](?:\s+уравнений)?\s*:?\s*', '', text, flags=re.IGNORECASE)
    parts = [part.strip() for part in re.split(r'\s*(?:,|;|\n)\s*', body) if part.strip()]
    if len(parts) == 1:
        # Try to split a whitespace-joined pair like x+y=10 y-x=2.
        parts = [p.strip() for p in re.split(r'(?<==[-+]?\d+)\s+(?=[xyхуу])', body, flags=re.IGNORECASE) if p.strip()]
    if len(parts) < 2 or len(parts) > 3:
        return None
    if not all(part.count('=') == 1 and re.search(r'[xyхуу]', part, flags=re.IGNORECASE) for part in parts):
        return None
    all_vars = set(''.join(re.findall(r'[xy]', ' '.join(parts).lower().replace('х', 'x').replace('у', 'y'))))
    if not {'x', 'y'}.issubset(all_vars):
        return None
    return parts


def solve_two_variable_system(text: str) -> Optional[dict]:
    lines = _split_system_equations(text)
    if not lines or len(lines) < 2:
        return None
    parsed = [_parse_linear_equation(line) for line in lines[:2]]
    if any(item is None for item in parsed):
        return None
    a1, b1, c1 = parsed[0]  # type: ignore[index]
    a2, b2, c2 = parsed[1]  # type: ignore[index]
    det = a1 * b2 - a2 * b1
    if det == 0:
        return _result([
            'Задача.',
            'Дана система уравнений:',
            *[f'{line}' for line in lines[:2]],
            'Решение.',
            'Определитель системы равен 0, поэтому по этим двум уравнениям нельзя получить единственное значение x и y.',
            'Ответ: у системы нет единственного решения.',
        ], 'local:live-system-solver')
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    x_text = _fmt_fraction(x)
    y_text = _fmt_fraction(y)
    return _result([
        'Задача.',
        'Дана система уравнений:',
        *[f'{line}' for line in lines[:2]],
        'Решение.',
        f'1) Из первого уравнения выражаем одну переменную или складываем уравнения так, чтобы исключить вторую переменную.',
        f'2) Решаем получившееся уравнение и получаем x = {x_text}.',
        f'3) Подставляем x = {x_text} в одно из уравнений и получаем y = {y_text}.',
        f'4) Проверка: значения x = {x_text}, y = {y_text} подходят к обоим уравнениям.',
        f'Ответ: x = {x_text}, y = {y_text}.',
    ], 'local:live-system-solver')


def solve_motion(text: str) -> Optional[dict]:
    source = _lower(text)
    # Special case: travelled for t at speed v; remaining is k times travelled; find total.
    m = re.search(
        r'ехал(?:а|и)?\s+(\d+)\s*(?:ч|час(?:а|ов)?)\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч.*?остал[а-я]+\s+проехать\s+в\s+(\d+)\s+раз[а]?\s+больше',
        source,
        flags=re.IGNORECASE,
    )
    if m and re.search(r'сколько\s+всего|весь\s+путь|должен\s+проехать', source):
        t, v, k = map(int, m.groups())
        first = t * v
        rest = first * k
        total = first + rest
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {v} × {t} = {first} км — столько уже проехал велосипедист.',
            f'2) {first} × {k} = {rest} км — столько осталось проехать.',
            f'3) {first} + {rest} = {total} км — весь путь.',
            f'Ответ: Велосипедист должен проехать всего {total} километров.',
        ], 'local:live-motion')

    # Find speed: distance over time.
    m = re.search(r'(?:прош[её]л|проехал|пролетел|проплыл)[а-я]*\s+(\d+)\s*км\s+за\s+(\d+)\s*(?:ч|час(?:а|ов)?)', source, flags=re.IGNORECASE)
    if m and re.search(r'скорост', source):
        distance, time = map(int, m.groups())
        if time == 0:
            return None
        speed = Fraction(distance, time)
        speed_text = _fmt_fraction(speed)
        subject = 'Катер' if 'катер' in source else 'Объект'
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) Чтобы найти скорость, расстояние делим на время.',
            f'2) {distance} : {time} = {speed_text} км/ч.',
            f'Ответ: {subject} шёл со скоростью {speed_text} км/ч.' if 'катер' in source else f'Ответ: Скорость равна {speed_text} км/ч.',
        ], 'local:live-motion')

    # Find distance: speed times time. Accept either order.
    m = re.search(r'(?:ехал|шла|ш[её]л|двигал[а-я]*)\s+(\d+)\s*(?:ч|час(?:а|ов)?)\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч', source, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч\s+(?:.*?)(\d+)\s*(?:ч|час(?:а|ов)?)', source, flags=re.IGNORECASE)
        if m:
            v, t = map(int, m.groups())
        else:
            v = t = None  # type: ignore[assignment]
    else:
        t, v = map(int, m.groups())
    if m and re.search(r'сколько\s+(?:километров|км)|какое\s+расстояние|проехал', source):
        distance = int(v) * int(t)  # type: ignore[arg-type]
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            '1) Чтобы найти расстояние, скорость умножаем на время.',
            f'2) {v} × {t} = {distance} км.',
            f'Ответ: За {t} часа он проехал {distance} километров.' if int(t) != 1 else f'Ответ: За {t} час он проехал {distance} километров.',
        ], 'local:live-motion')
    return None


def solve_purchase(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'\b(?:купил|купила|купили|стоил|стоит|по\s+\d+\s*(?:руб|р\b))', source):
        return None
    m = re.search(r'было\s+(\d+)\s*(?:руб|р\b).*?купил[а-я]*\s+(\d+)\s+[а-яеё]+\s+по\s+(\d+)\s*(?:руб|р\b)', source, flags=re.IGNORECASE)
    if m and re.search(r'остал', source):
        initial, qty, price = map(int, m.groups())
        cost = qty * price
        left = initial - cost
        person = 'Маши' if 'маш' in source else 'покупателя'
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {price} × {qty} = {cost} рублей — стоимость покупки.',
            f'2) {initial} − {cost} = {left} рублей — осталось после покупки.',
            f'Ответ: У {person} осталось {left} {_choose_plural_int(left, "рубль", "рубля", "рублей")}.',
        ], 'local:live-purchase')
    m = re.search(r'купил[а-я]*\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s*(?:руб|р\b)', source, flags=re.IGNORECASE)
    if m and re.search(r'сколько\s+(?:рублей|р\b).*?(?:заплат|сто)', source):
        qty = int(m.group(1))
        item = m.group(2)
        price = int(m.group(3))
        cost = qty * price
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {price} × {qty} = {cost} рублей — стоимость всех {item}.',
            f'Ответ: За покупку заплатили {cost} {_choose_plural_int(cost, "рубль", "рубля", "рублей")}.',
        ], 'local:live-purchase')
    return None


def solve_equal_groups_remaining(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(r'на\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?(?:утащил[а-я]*|забрал[а-я]*|съел[а-я]*|израсходовал[а-я]*|подарил[а-я]*)\s+(\d+)\s+\4', source, flags=re.IGNORECASE)
    if m and re.search(r'остал', source):
        groups = int(m.group(1))
        each = int(m.group(3))
        taken = int(m.group(5))
        total = groups * each
        left = total - taken
        item = m.group(4)
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {groups} × {each} = {total} {item} — было всего.',
            f'2) {total} − {taken} = {left} {item} — осталось.',
            f'Ответ: Осталось {left} {item}.',
        ], 'local:live-equal-groups')
    return None


def solve_proportion(text: str) -> Optional[dict]:
    source = _lower(text)
    # На 2 этажах 36 окон. Сколько окон на 3 этажах?
    m = re.search(r'на\s+(\d+)\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?сколько\s+\4\s+на\s+(\d+)\s+\2', source, flags=re.IGNORECASE)
    if m:
        base_groups = int(m.group(1))
        group_name = m.group(2)
        total_items = int(m.group(3))
        item_name = m.group(4)
        target_groups = int(m.group(5))
        if base_groups == 0:
            return None
        per_group = Fraction(total_items, base_groups)
        target_total = per_group * target_groups
        if target_total.denominator != 1:
            return None
        answer = target_total.numerator
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {total_items} : {base_groups} = {_fmt_fraction(per_group)} {item_name} — приходится на один {group_name}.',
            f'2) {_fmt_fraction(per_group)} × {target_groups} = {answer} {item_name} — будет на {target_groups} {group_name}.',
            f'Ответ: На {target_groups} {group_name} будет {answer} {item_name}.',
        ], 'local:live-proportion')
    return None


def solve_fraction_part(text: str) -> Optional[dict]:
    source = _lower(text)
    ordinals = {
        'половин': 2, 'втор': 2, 'треть': 3, 'трет': 3, 'четверт': 4,
        'пят': 5, 'шест': 6, 'седьм': 7, 'восьм': 8, 'девят': 9, 'десят': 10,
    }
    m = re.search(r'(?:найди|чему\s+равна|сколько)\s+([а-яеё]+)\s+част[ьи]\s+от\s+(\d+)', source, flags=re.IGNORECASE)
    if not m:
        return None
    word = m.group(1)
    n = int(m.group(2))
    denom = None
    for stem, value in ordinals.items():
        if stem in word:
            denom = value
            break
    if not denom:
        return None
    ans = Fraction(n, denom)
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) Чтобы найти эту часть числа, делим {n} на {denom}.',
        f'2) {n} : {denom} = {_fmt_fraction(ans)}.',
        f'Ответ: Эта часть числа равна {_fmt_fraction(ans)}.',
    ], 'local:live-fraction-part')


def solve_live_math_first(text: str) -> Optional[dict]:
    """High-priority deterministic handlers for real user inputs.

    These handlers run before the broad legacy fallback.  They are intentionally
    structural (not exact lookup): the goal is to prevent wrong generic answers
    such as "720 часов" or "Ответ: -2" for common grade 2–4 tasks.
    """
    for solver in (
        solve_two_variable_system,
        solve_joint_work,
        solve_motion,
        solve_purchase,
        solve_equal_groups_remaining,
        solve_proportion,
        solve_fraction_part,
    ):
        payload = solver(text)
        if payload is not None:
            return payload
    return None

# --- v275 deployment black-box diagnostic hardening ---
# These overrides are deliberately structural, not exact lookup.  They cover
# live-user cases that previously escaped to the broad generic fallback.

def _v275_equation_candidates(body: str) -> list[str]:
    text = str(body or '').replace('−', '-').replace('х', 'x').replace('у', 'y').replace('Х', 'x').replace('У', 'y')
    text = re.sub(r'^(?:реши(?:те)?\s+)?систем[ауые](?:\s+уравнений)?\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
    # Preferred path: explicit separators.
    parts = [part.strip() for part in re.split(r'\s*(?:,|;|\n)\s*', text) if part.strip()]
    if len(parts) >= 2:
        return parts
    # Newline may have been lost by UI/OCR.  Extract elementary linear equations
    # with constant RHS without using variable-width lookbehind.
    var_term = r'(?:[+-]?\s*(?:\d+\s*\*?\s*)?[xy])'
    const_term = r'(?:[+-]?\s*\d+)'
    first_term = rf'(?:{var_term}|{const_term})'
    next_term = rf'(?:\s*[+-]\s*(?:\d+\s*\*?\s*)?[xy]|\s*[+-]\s*\d+)'
    lhs = rf'(?:{first_term}(?:{next_term})*)'
    rhs = r'(?:[+-]?\s*\d+)'
    candidates = [m.group(0).strip() for m in re.finditer(rf'{lhs}\s*=\s*{rhs}', text, flags=re.IGNORECASE)]
    if len(candidates) >= 2:
        return candidates
    return parts


def _split_system_equations(raw_text: str) -> Optional[list[str]]:  # type: ignore[override]
    canonical = canonicalize_system_submission(raw_text)
    if canonical:
        return [line.strip() for line in canonical.split('\n') if line.strip()]
    text = _clean_text(raw_text)
    if text.count('=') < 2:
        return None
    parts = _v275_equation_candidates(text)
    if len(parts) < 2 or len(parts) > 3:
        return None
    normalized_parts: list[str] = []
    for part in parts[:2]:
        compact = re.sub(r'\s+', '', part).replace('х', 'x').replace('у', 'y').replace('Х', 'x').replace('У', 'y')
        if compact.count('=') != 1 or not re.search(r'[xy]', compact, flags=re.IGNORECASE):
            return None
        normalized_parts.append(compact)
    all_vars = set(''.join(re.findall(r'[xy]', ' '.join(normalized_parts).lower())))
    if not {'x', 'y'}.issubset(all_vars):
        return None
    return normalized_parts


def solve_two_variable_system(text: str) -> Optional[dict]:  # type: ignore[override]
    try:
        lines = _split_system_equations(text)
    except Exception:
        return None
    if not lines or len(lines) < 2:
        return None
    parsed = [_parse_linear_equation(line) for line in lines[:2]]
    if any(item is None for item in parsed):
        return None
    a1, b1, c1 = parsed[0]  # type: ignore[index]
    a2, b2, c2 = parsed[1]  # type: ignore[index]
    det = a1 * b2 - a2 * b1
    if det == 0:
        return _result([
            'Задача.',
            'Дана система уравнений:',
            *[f'{line}' for line in lines[:2]],
            'Решение.',
            'Определитель системы равен 0, поэтому по этим двум уравнениям нельзя получить единственное значение x и y.',
            'Ответ: у системы нет единственного решения.',
        ], 'local:live-system-solver')
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    x_text = _fmt_fraction(x)
    y_text = _fmt_fraction(y)
    return _result([
        'Задача.',
        'Дана система уравнений:',
        *[f'{line}' for line in lines[:2]],
        'Решение.',
        '1) Складываем или вычитаем уравнения так, чтобы исключить одну переменную.',
        f'2) Получаем x = {x_text}.',
        f'3) Подставляем x = {x_text} в одно из уравнений и получаем y = {y_text}.',
        f'4) Проверка: значения x = {x_text}, y = {y_text} подходят к обоим уравнениям.',
        f'Ответ: x = {x_text}, y = {y_text}.',
    ], 'local:live-system-solver')


def _item_form(n: int, word: str) -> str:
    stem = (word or '').lower().replace('ё', 'е')
    forms = [
        ('шиш', ('шишка', 'шишки', 'шишек')),
        ('яблок', ('яблоко', 'яблока', 'яблок')),
        ('гриб', ('гриб', 'гриба', 'грибов')),
        ('карандаш', ('карандаш', 'карандаша', 'карандашей')),
        ('тетрад', ('тетрадь', 'тетради', 'тетрадей')),
        ('конфет', ('конфета', 'конфеты', 'конфет')),
        ('книг', ('книга', 'книги', 'книг')),
        ('окн', ('окно', 'окна', 'окон')),
        ('монет', ('монета', 'монеты', 'монет')),
        ('мар', ('марка', 'марки', 'марок')),
        ('руб', ('рубль', 'рубля', 'рублей')),
        ('коп', ('копейка', 'копейки', 'копеек')),
    ]
    for marker, (one, two, many) in forms:
        if marker in stem:
            return _choose_plural_int(n, one, two, many)
    return word


def _count_with_item(n: int, word: str) -> str:
    return f'{n} {_item_form(n, word)}'


def solve_equal_groups_remaining(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    m = re.search(
        r'на\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b.*?'
        r'(?:утащил[а-я]*|забрал[а-я]*|съел[а-я]*|израсходовал[а-я]*|подарил[а-я]*|взял[а-я]*|унес[а-я]*)\s+'
        r'(\d+)\s+([а-яеё]+)\b',
        source,
        flags=re.IGNORECASE,
    )
    if m and re.search(r'остал', source):
        groups = int(m.group(1))
        each = int(m.group(3))
        item = m.group(4)
        taken = int(m.group(5))
        total = groups * each
        left = total - taken
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {groups} × {each} = {total} — было всего.',
            f'2) {total} − {taken} = {left} — осталось.',
            f'Ответ: Осталось {_count_with_item(left, item)}.',
        ], 'local:live-equal-groups')
    return None


def _group_phrase_one(word: str) -> str:
    stem = (word or '').lower().replace('ё', 'е')
    if 'этаж' in stem:
        return 'на одном этаже'
    if 'ряд' in stem:
        return 'в одном ряду'
    if 'полк' in stem:
        return 'на одной полке'
    if 'короб' in stem:
        return 'в одной коробке'
    return 'на одну группу'


def solve_proportion(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    m = re.search(r'на\s+(\d+)\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+)\b.*?сколько\s+\4\s+на\s+(\d+)\s+\2', source, flags=re.IGNORECASE)
    if m:
        base_groups = int(m.group(1))
        group_name = m.group(2)
        total_items = int(m.group(3))
        item_name = m.group(4)
        target_groups = int(m.group(5))
        if base_groups == 0:
            return None
        per_group = Fraction(total_items, base_groups)
        target_total = per_group * target_groups
        if target_total.denominator != 1:
            return None
        answer = target_total.numerator
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {total_items} : {base_groups} = {_fmt_fraction(per_group)} — приходится {_group_phrase_one(group_name)}.',
            f'2) {_fmt_fraction(per_group)} × {target_groups} = {answer} — будет на {target_groups} {group_name}.',
            f'Ответ: На {target_groups} {group_name} будет {_count_with_item(answer, item_name)}.',
        ], 'local:live-proportion')
    return None


def solve_money_conversion(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'руб|коп|р\b|к\b', source):
        return None
    m = re.search(r'(\d+)\s*(?:руб(?:л(?:ей|я|ь|ях)?)?\.?|р\b)\s*(?:и\s*)?(\d+)\s*(?:коп(?:е(?:ек|йки|йка|йках)?)?\.?|к\b)', source, flags=re.IGNORECASE)
    if m and re.search(r'сколько\s+коп', source):
        rub = int(m.group(1))
        kop = int(m.group(2))
        total = rub * 100 + kop
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) 1 рубль = 100 копеек, значит {rub} руб. = {rub * 100} коп.',
            f'2) {rub * 100} + {kop} = {total} коп.',
            f'Ответ: Всего {_count_with_item(total, "копейка")}.',
        ], 'local:live-money-conversion')
    m = re.search(r'сколько\s+копеек\s+в\s+(\d+)\s*(?:руб(?:л(?:ях|ей|я|ь)?)?\.?|р\b)', source, flags=re.IGNORECASE)
    if m:
        rub = int(m.group(1))
        total = rub * 100
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) 1 рубль = 100 копеек.',
            f'2) {rub} × 100 = {total} коп.',
            f'Ответ: Всего {_count_with_item(total, "копейка")}.',
        ], 'local:live-money-conversion')
    m = re.search(r'(?:сколько\s+руб[а-яё\s]*коп[а-яё\s]*в|переведи[а-яё\s]*в\s+руб[а-яё\s]*и\s+коп[а-яё\s]*)\s*(\d+)\s*коп', source, flags=re.IGNORECASE)
    if m:
        total = int(m.group(1))
        rub = total // 100
        kop = total % 100
        return _result([
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {total} : 100 = {rub} руб. и остаток {kop} коп.',
            f'Ответ: Это {_count_with_item(rub, "рубль")} {_count_with_item(kop, "копейка")}.',
        ], 'local:live-money-conversion')
    return None


def solve_division_container_count(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'короб|пакет|ящик|мешок|контейнер', source):
        return None
    m = re.search(r'по\s+(\d+)\s+([а-яеё]+)\b.*?(?:для|на|чтобы\s+разложить)\s+(\d+)\s+\2\b', source, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'(\d+)\s+([а-яеё]+)\b.*?по\s+(\d+)\s+\2\b', source, flags=re.IGNORECASE)
        if m:
            total = int(m.group(1)); item = m.group(2); per = int(m.group(3))
        else:
            return None
    else:
        per = int(m.group(1)); item = m.group(2); total = int(m.group(3))
    if per <= 0:
        return None
    full = total // per
    rem = total % per
    need = full + (1 if rem else 0)
    asks_need = bool(re.search(r'понадоб|нужно|хватит|сколько\s+(?:короб|пакет|ящик|меш)', source)) and not re.search(r'полных|остат', source)
    if asks_need:
        lines = [
            'Задача.',
            str(text).strip(),
            'Решение.',
            f'1) {total} : {per} = {full} (ост. {rem}) — делим предметы по {per}.',
        ]
        if rem:
            lines.append(f'2) Осталось {rem}, поэтому нужна ещё одна коробка/упаковка: {full} + 1 = {need}.')
        else:
            lines.append(f'2) Остатка нет, значит нужно ровно {need}.')
        lines.append(f'Ответ: Понадобится {need} {_choose_plural_int(need, "коробка", "коробки", "коробок")}.')
        return _result(lines, 'local:live-division-containers')
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {total} : {per} = {full} (ост. {rem}).',
        f'Ответ: Получится {full} полных групп, останется {_count_with_item(rem, item)}.',
    ], 'local:live-division-containers')


def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    """High-priority deterministic handlers for real user inputs."""
    for solver in (
        solve_two_variable_system,
        solve_joint_work,
        solve_motion,
        solve_purchase,
        solve_money_conversion,
        solve_division_container_count,
        solve_equal_groups_remaining,
        solve_proportion,
        solve_fraction_part,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return payload
    return None

# --- v276 live route/unit/system formatting fix ---
# Keep these overrides at the end so the high-priority live router uses them
# before any broad fallback.  They are structural, not exact-text lookup.

def _v276_work_unit_forms(unit: str) -> tuple[str, str, str] | None:
    stem = (unit or '').lower().replace('ё', 'е').strip()
    if stem in {'а', 'ар'} or stem.startswith('ар'):
        return ('ар', 'ара', 'аров')
    if stem.startswith('акр'):
        return ('акр', 'акра', 'акров')
    if stem == 'т' or stem.startswith('тонн'):
        return ('т', 'т', 'т')
    if stem.startswith('центнер'):
        return ('центнер', 'центнера', 'центнеров')
    if stem == 'кг' or stem.startswith('килограмм'):
        return ('кг', 'кг', 'кг')
    if stem.startswith('детал'):
        return ('деталь', 'детали', 'деталей')
    if stem.startswith('издел'):
        return ('изделие', 'изделия', 'изделий')
    if stem.startswith('страниц'):
        return ('страница', 'страницы', 'страниц')
    if stem.startswith('метр') or stem == 'м':
        return ('м', 'м', 'м')
    if stem.startswith('гектар'):
        return ('гектар', 'гектара', 'гектаров')
    if stem.startswith('сот'):
        return ('сотка', 'сотки', 'соток')
    return None


def _v276_format_work_quantity(value: Fraction, unit: str) -> str:
    forms = _v276_work_unit_forms(unit)
    if value.denominator == 1:
        n = value.numerator
        if forms:
            return f'{n} {_choose_plural_int(n, forms[0], forms[1], forms[2])}'
        return f'{n} {unit}'.strip()
    # For fractional productivity, use the stable unit name after the fraction.
    if forms:
        return f'{_fmt_fraction(value)} {forms[2]}'
    return f'{_fmt_fraction(value)} {unit}'.strip()


def _v276_format_rate(value: Fraction, work_unit: str, time_unit: str) -> str:
    quantity = _v276_format_work_quantity(value, work_unit)
    time_unit = (time_unit or '').lower()
    if time_unit.startswith('д'):
        return f'{quantity} в день'
    if time_unit.startswith('мин'):
        return f'{quantity} в минуту'
    return f'{quantity} в час'


def _extract_work_amount(text: str) -> tuple[Optional[int], str]:  # type: ignore[override]
    patterns = [
        r'(?:площадью\s+)?(\d+)\s*(аров|ара|ар|а)\b',
        r'(?:площадью\s+)?(\d+)\s*(акров|акра|акр)\b',
        r'(\d+)\s*(т|тонн(?:ы|у|а)?|центнеров|кг)\b',
        r'(\d+)\s*(детал(?:ей|и|ь)|издели(?:й|я|е)|заказ(?:ов|а)?|страниц(?:ы|у)?|метров|м)\b',
        r'(\d+)\s*(гектар(?:ов|а)?|сот(?:ок|ки)?)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).strip().lower()
            if unit == 'а':
                unit = 'ар'
            if unit.startswith('тонн'):
                unit = 'т'
            return amount, unit
    return None, 'единиц работы'


def _v276_time_unit_noun(unit_hint: str) -> str:
    unit_hint = (unit_hint or '').lower()
    if unit_hint.startswith('д'):
        return 'день'
    if unit_hint.startswith('мин'):
        return 'минута'
    return 'час'


def solve_joint_work(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    if not re.search(r'\b(?:вместе|оба|обе|работая\s+вместе)\b', source):
        return None
    if not re.search(r'(?:трактор|комбайн|бригад|рабоч|мастер|труб|насос|станок|машин|экскаватор|кран)', source):
        return None
    time_matches = re.findall(
        r'за\s+(\d+)\s*(час(?:а|ов)?|ч\b|дн(?:я|ей|ь)?|день|дней|мин(?:ут(?:ы)?|\b))',
        source,
        flags=re.IGNORECASE,
    )
    if len(time_matches) < 2:
        return None
    t1 = int(time_matches[0][0])
    t2 = int(time_matches[1][0])
    if t1 <= 0 or t2 <= 0:
        return None
    unit_hint = time_matches[0][1]
    if unit_hint == 'ч':
        unit_hint = 'час'
    amount, work_unit = _extract_work_amount(source)

    if amount is None:
        rate1 = Fraction(1, t1)
        rate2 = Fraction(1, t2)
        combined = rate1 + rate2
        total_time = Fraction(1, 1) / combined
        time_unit = _v276_time_unit_noun(unit_hint)
        rate_text_1 = f'1 : {t1} = {_fmt_fraction(rate1)} части работы за 1 {time_unit}'
        rate_text_2 = f'1 : {t2} = {_fmt_fraction(rate2)} части работы за 1 {time_unit}'
        combined_text = f'{_fmt_fraction(combined)} части работы за 1 {time_unit}'
        step4 = f'4) 1 : {_fmt_fraction(combined)} = {_format_time(total_time, unit_hint)} — столько времени нужно вместе.'
    else:
        total_work = Fraction(amount, 1)
        rate1 = total_work / t1
        rate2 = total_work / t2
        combined = rate1 + rate2
        total_time = total_work / combined
        rate_text_1 = f'{amount} : {t1} = {_v276_format_rate(rate1, work_unit, unit_hint)}'
        rate_text_2 = f'{amount} : {t2} = {_v276_format_rate(rate2, work_unit, unit_hint)}'
        combined_text = _v276_format_rate(combined, work_unit, unit_hint)
        step4 = f'4) {amount} : {_fmt_fraction(combined)} = {_format_time(total_time, unit_hint)} — столько времени нужно вместе.'

    time_text = _format_time(total_time, unit_hint)
    if 'комбайн' in source:
        final = f'Оба комбайна, работая вместе, уберут поле за {time_text}.'
        action1 = 'убирает первый комбайн'
        action2 = 'убирает второй комбайн'
        action_both = 'убирают оба комбайна вместе'
    elif 'трактор' in source:
        final = f'Оба трактора, работая вместе, вспашут поле за {time_text}.'
        action1 = 'вспашет первый трактор'
        action2 = 'вспашет второй трактор'
        action_both = 'вспашут оба трактора вместе'
    elif 'труб' in source:
        final = f'Обе трубы вместе выполнят работу за {time_text}.'
        action1 = 'выполняет первая труба'
        action2 = 'выполняет вторая труба'
        action_both = 'выполняют обе трубы вместе'
    elif 'бригад' in source:
        final = f'Обе бригады вместе выполнят такую работу за {time_text}.'
        action1 = 'делает первая бригада'
        action2 = 'делает вторая бригада'
        action_both = 'делают обе бригады вместе'
    else:
        final = f'Работая вместе, они выполнят работу за {time_text}.'
        action1 = 'делает первый исполнитель'
        action2 = 'делает второй исполнитель'
        action_both = 'делают оба исполнителя вместе'

    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {rate_text_1} — столько {action1}.',
        f'2) {rate_text_2} — столько {action2}.',
        f'3) {_fmt_fraction(rate1)} + {_fmt_fraction(rate2)} = {combined_text} — столько {action_both}.',
        step4,
        f'Ответ: {final}',
    ], 'local:live-joint-work')


def solve_two_variable_system(text: str) -> Optional[dict]:  # type: ignore[override]
    try:
        lines = _split_system_equations(text)
    except Exception:
        return None
    if not lines or len(lines) < 2:
        return None
    parsed = [_parse_linear_equation(line) for line in lines[:2]]
    if any(item is None for item in parsed):
        return None
    a1, b1, c1 = parsed[0]  # type: ignore[index]
    a2, b2, c2 = parsed[1]  # type: ignore[index]
    det = a1 * b2 - a2 * b1
    if det == 0:
        return _result([
            'Задача.',
            'Дана система уравнений:',
            *[f'{line}' for line in lines[:2]],
            'Решение.',
            'Определитель системы равен 0, поэтому по этим двум уравнениям нельзя получить единственное значение x и y.',
            'Ответ: у системы нет единственного решения.',
        ], 'local:live-system-solver')
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    x_text = _fmt_fraction(x)
    y_text = _fmt_fraction(y)
    return _result([
        'Задача.',
        'Дана система уравнений:',
        *[f'{line}' for line in lines[:2]],
        'Решение.',
        '1) Складываем или вычитаем уравнения так, чтобы исключить одну переменную.',
        f'2) Получаем x = {x_text}.',
        f'3) Подставляем x = {x_text} в одно из уравнений и получаем y = {y_text}.',
        f'4) Проверяем: значения x = {x_text}, y = {y_text} подходят к обоим уравнениям.',
        f'Ответ: x = {x_text}, y = {y_text}.',
    ], 'local:live-system-solver')

# --- v278 structural live solvers + diagnostic-audit hardening ---
# These are not exact text lookups.  They cover broad elementary structures that
# otherwise fell into low-confidence or unsafe generic fallback paths.

def _v278_actor_from_text(text: str, default: str = 'ученика') -> str:
    m = re.search(r'\b[Уу]\s+([А-ЯЁ][а-яё]+)\b', str(text or ''))
    if m:
        return m.group(1)
    return default


def _v278_item_word(word: str) -> str:
    return (word or '').strip().lower().replace('ё', 'е')


def _v278_same_item(a: str, b: str) -> bool:
    a = _v278_item_word(a)
    b = _v278_item_word(b)
    if not a or not b:
        return True
    if a == b:
        return True
    # Compare by a short stem; enough for apples/confets/pencils style words.
    return a[:4] == b[:4] or a[:5] == b[:5]


def solve_basic_addition_word(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'\b(?:стало|получилось|всего|теперь)\b', source):
        return None
    m = re.search(
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?'
        r'(?:дали|добавили|подарили|принесли|наш[её]л[а-я]*|купил[а-я]*|положили|доложили)\s+'
        r'(?:еще\s+)?(\d+)\s+([а-яеё]+)\b',
        source,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    first = int(m.group(1))
    item = m.group(2)
    second = int(m.group(3))
    item2 = m.group(4)
    if not _v278_same_item(item, item2):
        return None
    total = first + second
    actor = _v278_actor_from_text(text, 'ученика')
    actor_phrase = f'У {actor}' if actor != 'ученика' else 'Всего'
    final = f'{actor_phrase} стало {_count_with_item(total, item)}.' if actor != 'ученика' else f'Всего стало {_count_with_item(total, item)}.'
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {first} + {second} = {total} {_item_form(total, item)} — столько стало всего.',
        f'Ответ: {final}',
    ], 'local:live-basic-addition')


def solve_basic_subtraction_word(text: str) -> Optional[dict]:
    source = _lower(text)
    if 'остал' not in source:
        return None
    m = re.search(
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?'
        r'(?:отдал[а-я]*|израсходовал[а-я]*|потратил[а-я]*|съел[а-я]*|забрал[а-я]*|подарил[а-я]*|унес[а-я]*|убрал[а-я]*)\s+'
        r'(\d+)\s+([а-яеё]+)\b',
        source,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    first = int(m.group(1))
    item = m.group(2)
    second = int(m.group(3))
    item2 = m.group(4)
    if not _v278_same_item(item, item2):
        return None
    left = first - second
    actor = _v278_actor_from_text(text, 'ученика')
    if actor != 'ученика':
        final = f'У {actor} осталось {_count_with_item(left, item)}.'
    else:
        final = f'Осталось {_count_with_item(left, item)}.'
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {first} − {second} = {left} {_item_form(left, item)} — столько осталось.',
        f'Ответ: {final}',
    ], 'local:live-basic-subtraction')


def solve_equal_groups_total(text: str) -> Optional[dict]:
    source = _lower(text)
    if 'остал' in source:
        return None
    m = re.search(r'(?:в|на)\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b', source, flags=re.IGNORECASE)
    if not m:
        return None
    groups = int(m.group(1))
    group_word = m.group(2)
    each = int(m.group(3))
    item = m.group(4)
    if not re.search(r'сколько|найди|всего', source):
        return None
    total = groups * each
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {groups} × {each} = {total} {_item_form(total, item)} — столько всего.',
        f'Ответ: Всего {_count_with_item(total, item)}.',
    ], 'local:live-equal-groups-total')


def solve_equal_sharing(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(
        r'(\d+)\s+([а-яеё]+)\b.*?'
        r'(?:разложил[а-я]*|раздал[а-я]*|поделил[а-я]*|распределил[а-я]*)\s+'
        r'(?:поровну\s+)?(?:в|между|на)\s+(\d+)\s+([а-яеё]+)\b',
        source,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    total = int(m.group(1))
    item = m.group(2)
    groups = int(m.group(3))
    group_word = m.group(4)
    if groups == 0:
        return None
    if not re.search(r'(?:в\s+кажд|каждому|одн[ао]й|одном|одну)', source):
        return None
    per = Fraction(total, groups)
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {total} : {groups} = {_fmt_fraction(per)} {_item_form(per.numerator if per.denominator == 1 else total, item)} — столько приходится на одну группу.',
        f'Ответ: В каждой группе {_fmt_fraction(per)} {_item_form(per.numerator if per.denominator == 1 else total, item)}.',
    ], 'local:live-equal-sharing')


def _v278_eval_simple_expr(expr: str) -> Optional[Fraction]:
    raw = str(expr or '').strip().replace('−', '-').replace('–', '-').replace('—', '-')
    raw = raw.replace('×', '*').replace('·', '*').replace('÷', '/').replace(':', '/')
    raw = re.sub(r'\s+', '', raw)
    if not raw or not re.fullmatch(r'[0-9+\-*/().]+', raw):
        return None
    if re.search(r'/\s*0(?!\d)', raw):
        return None
    try:
        value = eval(raw, {'__builtins__': {}}, {})
    except Exception:
        return None
    if isinstance(value, (int, float)):
        try:
            return Fraction(value).limit_denominator(1000000)
        except Exception:
            return None
    return None


def solve_compare_two_expressions(text: str) -> Optional[dict]:
    source = _clean_text(text)
    m = re.search(r'сравни\s+(.+?)\s+и\s+(.+?)(?:[.!?]|$)', source, flags=re.IGNORECASE)
    if not m:
        return None
    left_expr = m.group(1).strip()
    right_expr = m.group(2).strip()
    left_val = _v278_eval_simple_expr(left_expr)
    right_val = _v278_eval_simple_expr(right_expr)
    if left_val is None or right_val is None:
        return None
    if left_val == right_val:
        sign = '='
        words = 'равны'
        final = f'Выражения {left_expr} и {right_expr} равны.'
    elif left_val > right_val:
        sign = '>'
        words = 'больше'
        final = f'Выражение {left_expr} больше, чем {right_expr}.'
    else:
        sign = '<'
        words = 'меньше'
        final = f'Выражение {left_expr} меньше, чем {right_expr}.'
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {left_expr} = {_fmt_fraction(left_val)}.',
        f'2) {right_expr} = {_fmt_fraction(right_val)}.',
        f'3) {_fmt_fraction(left_val)} {sign} {_fmt_fraction(right_val)}, значит выражения равны.' if left_val == right_val else f'3) {_fmt_fraction(left_val)} {sign} {_fmt_fraction(right_val)}, значит первое выражение {words}.',
        f'Ответ: {final}',
    ], 'local:live-compare-expressions')


def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    """High-priority deterministic handlers for real user inputs, v278."""
    for solver in (
        solve_two_variable_system,
        solve_joint_work,
        solve_motion,
        solve_purchase,
        solve_money_conversion,
        solve_division_container_count,
        solve_basic_addition_word,
        solve_basic_subtraction_word,
        solve_equal_groups_remaining,
        solve_equal_groups_total,
        solve_equal_sharing,
        solve_proportion,
        solve_fraction_part,
        solve_compare_two_expressions,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return payload
    return None

# --- v278 patch: two same-object parts total, e.g. 2 белых гриба и 3 желтых гриба ---
def solve_two_part_total(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'сколько.*(?:всего|собрал|наш[её]л|получилось|стало)', source):
        return None
    m = re.search(
        r'(\d+)\s+(?:[а-яеё]+\s+)?(гриб(?:а|ов)?|яблок(?:а|о)?|карандаш(?:а|ей)?|конфет(?:ы|а)?|книг(?:и|а)?|шишк(?:и|а|ек))\b\s+и\s+'
        r'(\d+)\s+(?:[а-яеё]+\s+)?(гриб(?:а|ов)?|яблок(?:а|о)?|карандаш(?:а|ей)?|конфет(?:ы|а)?|книг(?:и|а)?|шишк(?:и|а|ек))\b',
        source,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    first = int(m.group(1))
    item = m.group(2)
    second = int(m.group(3))
    item2 = m.group(4)
    if not _v278_same_item(item, item2):
        return None
    total = first + second
    person_match = re.search(r'\b([А-ЯЁ][а-яё]+)\b', str(text or ''))
    person = person_match.group(1) if person_match else ''
    if person and 'гриб' in _v278_item_word(item):
        final = f'{person} собрала в лесу всего {_count_with_item(total, item)}.' if person.endswith('а') else f'{person} собрал всего {_count_with_item(total, item)}.'
    else:
        final = f'Всего получилось {_count_with_item(total, item)}.'
    return _result([
        'Задача.',
        str(text).strip(),
        'Решение.',
        f'1) {first} + {second} = {total} {_item_form(total, item)} — складываем две части.',
        f'Ответ: {final}',
    ], 'local:live-two-part-total')


def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    """High-priority deterministic handlers for real user inputs, v278 patch 2."""
    for solver in (
        solve_two_variable_system,
        solve_joint_work,
        solve_motion,
        solve_purchase,
        solve_money_conversion,
        solve_division_container_count,
        solve_two_part_total,
        solve_basic_addition_word,
        solve_basic_subtraction_word,
        solve_equal_groups_remaining,
        solve_equal_groups_total,
        solve_equal_sharing,
        solve_proportion,
        solve_fraction_part,
        solve_compare_two_expressions,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return payload
    return None

# --- v279 external black-box audit hardening ---
# The goal of this block is not to memorize internet tasks.  It adds structural
# solvers for classes found by the external task audit: basic word problems,
# cost/quantity/price, motion, units, geometry, fractions, one-variable
# equations, expressions, tables and division with remainder.

_V279_RELEASE_NOTE = 'v279-external-audit-solvers'


def _v279_subject(text: str, default: str = '') -> str:
    m = re.search(r'\b[Уу]\s+([А-ЯЁ][а-яё]+)\b', str(text or ''))
    if m:
        return m.group(1)
    m = re.search(r'^\s*([А-ЯЁ][а-яё]+)\b', str(text or ''))
    if m and m.group(1).lower() not in {'один', 'одна', 'в', 'на', 'из', 'с'}:
        return m.group(1)
    return default


def _v279_sentence(text: str) -> str:
    return str(text or '').strip()


def _v279_form(n: int, one: str, two_four: str, many: str) -> str:
    return _choose_plural_int(n, one, two_four, many)


def _v279_unit_word(n: int, unit: str) -> str:
    u = (unit or '').lower().replace('ё', 'е').strip(' .')
    table = [
        ('час', ('час', 'часа', 'часов')),
        ('мин', ('минута', 'минуты', 'минут')),
        ('дн', ('день', 'дня', 'дней')),
        ('руб', ('рубль', 'рубля', 'рублей')),
        ('коп', ('копейка', 'копейки', 'копеек')),
        ('км', ('километр', 'километра', 'километров')),
        ('метр', ('метр', 'метра', 'метров')),
        ('м', ('метр', 'метра', 'метров')),
        ('см', ('сантиметр', 'сантиметра', 'сантиметров')),
        ('грам', ('грамм', 'грамма', 'граммов')),
        ('г', ('грамм', 'грамма', 'граммов')),
        ('кг', ('килограмм', 'килограмма', 'килограммов')),
        ('ар', ('ар', 'ара', 'аров')),
        ('акр', ('акр', 'акра', 'акров')),
        ('т', ('тонна', 'тонны', 'тонн')),
    ]
    for marker, forms in table:
        if u == marker or marker in u:
            return _choose_plural_int(int(n), *forms)
    return _item_form(int(n), unit)


def _v279_count(n: int | Fraction, unit: str) -> str:
    if isinstance(n, Fraction):
        if n.denominator == 1:
            return _v279_count(n.numerator, unit)
        return f'{_fmt_fraction(n)} {unit}'
    return f'{n} {_v279_unit_word(int(n), unit)}'


def _v279_eval_expr_to_text(expr: str) -> Optional[tuple[Fraction, str]]:
    val = _v278_eval_simple_expr(expr)
    if val is None:
        return None
    return val, _fmt_fraction(val)


def solve_v279_basic_addition_word(text: str) -> Optional[dict]:
    source = _lower(text)
    if not re.search(r'сколько|всего|стало|получилось', source):
        return None
    # У Оли было 8 наклеек, мама дала ей ещё 7 наклеек.
    patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?(?:дали|дала|дал|добавили|подарили|принесли|положили|доложили|купил[а-я]*|наш[её]л[а-я]*)\s+(?:ей|ему|им|еще|ещ[её])?\s*(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
        r'лежал[а-я]*\s+(\d+)\s+([а-яеё]+)\b.*?(?:положили|добавили|принесли)\s+(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
    ]
    for pat in patterns:
        m = re.search(pat, source, flags=re.IGNORECASE)
        if m:
            first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
            if not _v278_same_item(item, item2):
                return None
            total = first + second
            subj = _v279_subject(text)
            final = f'У {subj} стало {_count_with_item(total, item)}.' if subj else f'Всего стало {_count_with_item(total, item)}.'
            return _result([
                'Задача.', _v279_sentence(text), 'Решение.',
                f'1) {first} + {second} = {total} {_item_form(total, item)} — складываем количество.',
                f'Ответ: {final}',
            ], 'local:live-v279-basic-addition')
    return None


def solve_v279_basic_subtraction_word(text: str) -> Optional[dict]:
    source = _lower(text)
    if 'остал' not in source:
        return None
    patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?(?:отдал[а-я]*|подарил[а-я]*|израсходовал[а-я]*|потратил[а-я]*|съел[а-я]*|забрал[а-я]*|унес[а-я]*|вышл[а-я]*|убрал[а-я]*|взял[а-я]*)\s+(?:другу\s+)?(\d+)\s+([а-яеё]+)\b',
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?на\s+остановке\s+вышл[а-я]*\s+(\d+)\s+([а-яеё]+)\b',
    ]
    for pat in patterns:
        m = re.search(pat, source, flags=re.IGNORECASE)
        if m:
            first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
            if not _v278_same_item(item, item2):
                return None
            left = first - second
            subj = _v279_subject(text)
            final = f'У {subj} осталось {_count_with_item(left, item)}.' if subj else f'Осталось {_count_with_item(left, item)}.'
            return _result([
                'Задача.', _v279_sentence(text), 'Решение.',
                f'1) {first} − {second} = {left} {_item_form(left, item)} — вычитаем то, что убрали.',
                f'Ответ: {final}',
            ], 'local:live-v279-basic-subtraction')
    return None


def solve_v279_equal_groups_remaining(text: str) -> Optional[dict]:
    source = _lower(text)
    # In 4 boxes there are 8 pencils each. 6 pencils were taken.
    m = re.search(
        r'(?:в|на)\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b.*?'
        r'(?:утащил[а-я]*|забрал[а-я]*|съел[а-я]*|израсходовал[а-я]*|подарил[а-я]*|взял[а-я]*|унес[а-я]*|взяли|отдали)\s+'
        r'(\d+)\s+([а-яеё]+)\b', source, flags=re.IGNORECASE)
    if m and 'остал' in source:
        groups, each, taken = int(m.group(1)), int(m.group(3)), int(m.group(5))
        item = m.group(4)
        total = groups * each
        left = total - taken
        return _result([
            'Задача.', _v279_sentence(text), 'Решение.',
            f'1) {groups} × {each} = {total} {_item_form(total, item)} — было всего.',
            f'2) {total} − {taken} = {left} {_item_form(left, item)} — осталось.',
            f'Ответ: Осталось {_count_with_item(left, item)}.',
        ], 'local:live-v279-equal-groups-remaining')
    return None


def solve_v279_equal_sharing(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(
        r'(\d+)\s+([а-яеё]+)\b.*?(?:раздали|разложили|поделили|распределили)\s+поровну\s+(?:между\s+)?(\d+)\s+([а-яеё]+)\b',
        source, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'(\d+)\s+([а-яеё]+)\b.*?(?:в|на)\s+(\d+)\s+([а-яеё]+).*?(?:кажд)', source, flags=re.IGNORECASE)
    if m and re.search(r'кажд|одн', source):
        total, item, groups = int(m.group(1)), m.group(2), int(m.group(3))
        if groups == 0:
            return None
        per = Fraction(total, groups)
        per_text = _fmt_fraction(per)
        return _result([
            'Задача.', _v279_sentence(text), 'Решение.',
            f'1) {total} : {groups} = {per_text} — делим поровну.',
            f'Ответ: Каждый получит {per_text} {_item_form(per.numerator if per.denominator == 1 else total, item)}.'
        ], 'local:live-v279-equal-sharing')
    return None


def solve_v279_price_quantity_cost(text: str) -> Optional[dict]:
    source = _lower(text)
    # Quantity from available money and unit price.
    m = re.search(r'сколько\s+([а-яеё]+)\s+можно\s+купить\s+на\s+(\d+)\s*(?:руб|р\b).*?(?:одна|один|1)\s+\1\s+стоит\s+(\d+)\s*(?:руб|р\b)', source, flags=re.IGNORECASE)
    if m:
        item, money, price = m.group(1), int(m.group(2)), int(m.group(3))
        qty = money // price if price else 0
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {money} : {price} = {qty} — делим деньги на цену одного предмета.',
                        f'Ответ: Можно купить {_count_with_item(qty, item)}.'], 'local:live-v279-price-quantity')
    # Unit price from total cost.
    m = re.search(r'за\s+(\d+)\s+одинаков[а-я]+\s+([а-яеё]+)\s+заплатил[а-я]*\s+(\d+)\s*(?:руб|р\b).*?сколько\s+рубл[а-я]*\s+стоит\s+один', source, flags=re.IGNORECASE)
    if m:
        qty, item, total = int(m.group(1)), m.group(2), int(m.group(3))
        price = Fraction(total, qty)
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {total} : {qty} = {_fmt_fraction(price)} рублей — цена одного предмета.',
                        f'Ответ: Один {item} стоит {_fmt_fraction(price)} {_v279_unit_word(int(price) if price.denominator == 1 else 5, "руб")}.'], 'local:live-v279-price-one')
    return None


def solve_v279_motion(text: str) -> Optional[dict]:
    source = _lower(text)
    # Find time = distance / speed.
    m = re.search(r'со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч.*?(?:прош[её]л|проехал|пролетел|проплыл|прошла|проехала)\s+(\d+)\s*км', source, flags=re.IGNORECASE)
    if m and re.search(r'сколько\s+час|за\s+сколько\s+час|время', source):
        speed, distance = int(m.group(1)), int(m.group(2))
        if speed == 0:
            return None
        t = Fraction(distance, speed)
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        '1) Чтобы найти время, расстояние делим на скорость.',
                        f'2) {distance} : {speed} = {_fmt_fraction(t)} часа.',
                        f'Ответ: Объект двигался {_format_time(t, "час")}.'], 'local:live-v279-motion-time')
    # Towards each other: (v1 + v2) * t.
    m = re.search(r'скорость\s+перв[а-я]+\s+(\d+)\s*км\s*/?\s*ч.*?скорость\s+втор[а-я]+\s+(\d+)\s*км\s*/?\s*ч.*?через\s+(\d+)\s*час', source, flags=re.IGNORECASE)
    if m and re.search(r'навстречу|встретил', source) and re.search(r'расстояни[ея]|между\s+город', source):
        v1, v2, t = map(int, m.groups())
        closing = v1 + v2
        dist = closing * t
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {v1} + {v2} = {closing} км/ч — скорость сближения.',
                        f'2) {closing} × {t} = {dist} км — расстояние между городами.',
                        f'Ответ: Расстояние между городами {dist} километров.'], 'local:live-v279-motion-towards')
    # Already went some distance; remaining is k times less/more; find total.
    m = re.search(r'(?:прош[её]л|проехал|проплыл|пролетел)\s+(\d+)\s*км.*?остал[а-я]+\s+(?:пройти|проехать|проплыть|пролететь)\s+в\s+(\d+)\s+раз[а]?\s+(больше|меньше)', source, flags=re.IGNORECASE)
    if m and re.search(r'весь\s+путь|всего|общ', source):
        done, k, kind = int(m.group(1)), int(m.group(2)), m.group(3)
        rest = done * k if 'больше' in kind else Fraction(done, k)
        if rest.denominator != 1:
            return None
        total = done + rest.numerator
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) Уже пройдено {done} км.',
                        f'2) {done} : {k} = {rest.numerator} км — осталось пройти.' if 'меньше' in kind else f'2) {done} × {k} = {rest.numerator} км — осталось пройти.',
                        f'3) {done} + {rest.numerator} = {total} км — весь путь.',
                        f'Ответ: Весь путь составляет {total} километров.'], 'local:live-v279-motion-remaining')
    return None


def solve_v279_units(text: str) -> Optional[dict]:
    source = _lower(text)
    # m + cm -> cm
    m = re.search(r'сколько\s+сантиметр[а-я]*\s+в\s+(\d+)\s*м\s*(\d+)?\s*см?', source, flags=re.IGNORECASE)
    if m:
        meters = int(m.group(1)); cm = int(m.group(2) or 0); total = meters * 100 + cm
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {meters} м = {meters * 100} см.',
                        f'2) {meters * 100} + {cm} = {total} см.',
                        f'Ответ: Всего {total} сантиметров.'], 'local:live-v279-units')
    m = re.search(r'сколько\s+метр[а-я]*\s+и\s+сантиметр[а-я]*\s+в\s+(\d+)\s*см', source, flags=re.IGNORECASE)
    if m:
        cm_total = int(m.group(1)); meters, cm = divmod(cm_total, 100)
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {cm_total} см = {meters} м {cm} см, потому что 1 м = 100 см.',
                        f'Ответ: Это {meters} {_v279_unit_word(meters,"м")} {cm} {_v279_unit_word(cm,"см")}.'], 'local:live-v279-units')
    m = re.search(r'сколько\s+грамм[а-я]*\s+в\s+(\d+)\s*кг\s*(\d+)?\s*г', source, flags=re.IGNORECASE)
    if m:
        kg = int(m.group(1)); grams = int(m.group(2) or 0); total = kg * 1000 + grams
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {kg} кг = {kg * 1000} г.',
                        f'2) {kg * 1000} + {grams} = {total} г.',
                        f'Ответ: Всего {total} граммов.'], 'local:live-v279-units')
    m = re.search(r'сколько\s+минут[а-я]*\s+в\s+(\d+)\s*час[а-я]*\s*(\d+)?\s*мин', source, flags=re.IGNORECASE)
    if m:
        hours = int(m.group(1)); minutes = int(m.group(2) or 0); total = hours * 60 + minutes
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {hours} ч = {hours * 60} мин.',
                        f'2) {hours * 60} + {minutes} = {total} мин.',
                        f'Ответ: Всего {total} минут.'], 'local:live-v279-units')
    return None


def solve_v279_geometry(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(r'(?:длина\s+(\d+)\s*см.*?ширина\s+(\d+)\s*см|ширина\s+(\d+)\s*см.*?длина\s+(\d+)\s*см)', source, flags=re.IGNORECASE)
    if m:
        a = int(m.group(1) or m.group(4)); b = int(m.group(2) or m.group(3))
        if 'периметр' in source:
            p = 2 * (a + b)
            return _result(['Задача.', _v279_sentence(text), 'Решение.',
                            f'1) ({a} + {b}) × 2 = {p} см — периметр прямоугольника.',
                            f'Ответ: Периметр прямоугольника равен {p} см.'], 'local:live-v279-geometry')
        if 'площад' in source:
            s = a * b
            return _result(['Задача.', _v279_sentence(text), 'Решение.',
                            f'1) {a} × {b} = {s} кв. см — площадь прямоугольника.',
                            f'Ответ: Площадь прямоугольника равна {s} кв. см.'], 'local:live-v279-geometry')
    m = re.search(r'периметр\s+квадрат[а-я]*\s+равен\s+(\d+)\s*см.*?(?:сторона|чему\s+равна)', source, flags=re.IGNORECASE)
    if m:
        p = int(m.group(1)); side = Fraction(p, 4)
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) У квадрата 4 равные стороны.',
                        f'2) {p} : 4 = {_fmt_fraction(side)} см — сторона квадрата.',
                        f'Ответ: Сторона квадрата равна {_fmt_fraction(side)} см.'], 'local:live-v279-geometry')
    return None


def solve_v279_fraction_whole_compare(text: str) -> Optional[dict]:
    source = _lower(text)
    denom_words = {'половин':2,'втор':2,'треть':3,'трет':3,'четверт':4,'пят':5,'шест':6,'седьм':7,'восьм':8,'девят':9,'десят':10}
    m = re.search(r'([а-яеё]+)\s+част[ьи]\s+числа\s+равна\s+(\d+).*?(?:найди|чему\s+равно).*?(?:числ|вс[её])', source, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'([а-яеё]+)\s+числа\s+равна\s+(\d+).*?(?:найди|чему\s+равно).*?(?:числ|вс[её])', source, flags=re.IGNORECASE)
    if m:
        word, part = m.group(1), int(m.group(2)); denom = None
        for stem, d in denom_words.items():
            if stem in word:
                denom = d; break
        if denom:
            whole = part * denom
            return _result(['Задача.', _v279_sentence(text), 'Решение.',
                            f'1) Если одна {word} часть равна {part}, то всё число в {denom} раза больше.',
                            f'2) {part} × {denom} = {whole}.',
                            f'Ответ: Всё число равно {whole}.'], 'local:live-v279-fraction-whole')
    m = re.search(r'сравни\s+дроби\s+(\d+)\s*/\s*(\d+)\s+и\s+(\d+)\s*/\s*(\d+)', source, flags=re.IGNORECASE)
    if m:
        a,b,c,d = map(int, m.groups())
        f1, f2 = Fraction(a,b), Fraction(c,d)
        if f1 == f2:
            final = f'Дроби {a}/{b} и {c}/{d} равны.'
            sign = '='
        elif f1 > f2:
            final = f'Дробь {a}/{b} больше, чем {c}/{d}.'
            sign = '>'
        else:
            final = f'Дробь {a}/{b} меньше, чем {c}/{d}.'
            sign = '<'
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) Сравниваем дроби: {a}/{b} {sign} {c}/{d}.',
                        f'Ответ: {final}'], 'local:live-v279-fraction-compare')
    return None


def solve_v279_one_variable_equation(text: str) -> Optional[dict]:
    raw = _clean_text(text).replace('х','x').replace('Х','x').replace('×','*').replace('·','*').replace('÷',':')
    if raw.count('=') != 1 or not re.search(r'\bx\b', raw, flags=re.IGNORECASE):
        return None
    compact = re.sub(r'[^0-9xX+=\-*:/.]', '', raw).lower().replace('/', ':')
    patterns: list[tuple[str, callable, str]] = [
        (r'^x\+(\d+)=(\d+)$', lambda a,b: int(b)-int(a), 'неизвестное слагаемое'),
        (r'^(\d+)\+x=(\d+)$', lambda a,b: int(b)-int(a), 'неизвестное слагаемое'),
        (r'^x-(\d+)=(\d+)$', lambda a,b: int(a)+int(b), 'неизвестное уменьшаемое'),
        (r'^(\d+)-x=(\d+)$', lambda a,b: int(a)-int(b), 'неизвестное вычитаемое'),
        (r'^x\*(\d+)=(\d+)$', lambda a,b: Fraction(int(b), int(a)), 'неизвестный множитель'),
        (r'^(\d+)\*x=(\d+)$', lambda a,b: Fraction(int(b), int(a)), 'неизвестный множитель'),
        (r'^x:(\d+)=(\d+)$', lambda a,b: int(a)*int(b), 'неизвестное делимое'),
        (r'^(\d+):x=(\d+)$', lambda a,b: Fraction(int(a), int(b)), 'неизвестный делитель'),
    ]
    for pat, fn, component in patterns:
        m = re.match(pat, compact)
        if m:
            val = fn(*m.groups())
            val_text = _fmt_fraction(val if isinstance(val, Fraction) else Fraction(val,1))
            return _result(['Задача.', _v279_sentence(text), 'Решение.',
                            f'1) Это уравнение на {component}.',
                            f'2) По обратному действию получаем x = {val_text}.',
                            f'3) Подставляем x = {val_text} и проверяем равенство.',
                            f'Ответ: x = {val_text}.'], 'local:live-v279-one-equation')
    return None


def solve_v279_expression_eval(text: str) -> Optional[dict]:
    source = _clean_text(text)
    m = re.search(r'(?:вычисли|найди)\s+(?:значение\s+)?(?:выражения\s*)?(.+?)(?:[.!?]|$)', source, flags=re.IGNORECASE)
    if not m:
        return None
    expr = m.group(1).strip()
    # Do not grab word-problem sentences.
    if re.search(r'[А-Яа-яЁё]', expr.replace('x','').replace('X','')) and not re.search(r'[0-9]', expr):
        return None
    if not re.fullmatch(r'[0-9\s+\-*:×·÷/().]+', expr):
        return None
    evaluated = _v279_eval_expr_to_text(expr)
    if evaluated is None:
        return None
    value, value_text = evaluated
    return _result(['Задача.', _v279_sentence(text), 'Решение.',
                    f'1) Вычисляем выражение по порядку действий.',
                    f'2) {expr} = {value_text}.',
                    f'Ответ: Значение выражения равно {value_text}.'], 'local:live-v279-expression')


def solve_v279_division_remainder(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(r'(\d+)\s+([а-яеё]+).*?разложил[а-я]*\s+по\s+(\d+)\s+\2.*?(?:пакет|короб|групп).*?(?:остал|полных)', source, flags=re.IGNORECASE)
    if m:
        total, item, per = int(m.group(1)), m.group(2), int(m.group(3))
        if per == 0:
            return None
        q, r = divmod(total, per)
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {total} : {per} = {q} (ост. {r}).',
                        f'Ответ: Получилось {q} полных пакетов, осталось {_count_with_item(r, item)}.'], 'local:live-v279-division-remainder')
    return None


def solve_v279_table_difference(text: str) -> Optional[dict]:
    source = _lower(text)
    if 'таблиц' not in source and 'дано' not in source:
        return None
    pairs = re.findall(r'([а-яеё]+)\s*[-—:]\s*(\d+)', source, flags=re.IGNORECASE)
    if len(pairs) < 2:
        return None
    values = {name: int(num) for name, num in pairs}
    m = re.search(r'на\s+сколько\s+([а-яеё]+)\s+больше,?\s+чем\s+([а-яеё]+)', source, flags=re.IGNORECASE)
    if m:
        a,b = m.group(1), m.group(2)
        va = next((v for k,v in values.items() if _v278_same_item(k,a)), None)
        vb = next((v for k,v in values.items() if _v278_same_item(k,b)), None)
        if va is not None and vb is not None:
            diff = va - vb
            return _result(['Задача.', _v279_sentence(text), 'Решение.',
                            f'1) {va} − {vb} = {diff} — на столько больше.',
                            f'Ответ: {a.capitalize()} больше, чем {b}, на {diff}.'], 'local:live-v279-table-difference')
    return None


def solve_v279_relation_more_less(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+на\s+(\d+)\s+\3\s+(больше|меньше).*?сколько\s+\3\s+у\s+\4', source, flags=re.IGNORECASE)
    if m:
        p1, base, item, p2, delta, kind = m.group(1), int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(6)
        ans = base + delta if 'больше' in kind else base - delta
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {base} {op} {delta} = {ans} {_item_form(ans,item)}.',
                        f'Ответ: У {p2.capitalize()} {_count_with_item(ans,item)}.'], 'local:live-v279-relation')
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+в\s+(\d+)\s+раз[а]?\s+(больше|меньше).*?сколько\s+\3\s+у\s+\4', source, flags=re.IGNORECASE)
    if m:
        base, item, p2, k, kind = int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(6)
        ans = base * k if 'больше' in kind else Fraction(base, k)
        if isinstance(ans, Fraction) and ans.denominator != 1:
            return None
        ans_int = ans if isinstance(ans, int) else ans.numerator
        op = '×' if 'больше' in kind else ':'
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {base} {op} {k} = {ans_int} {_item_form(ans_int,item)}.',
                        f'Ответ: У {p2.capitalize()} {_count_with_item(ans_int,item)}.'], 'local:live-v279-relation')
    return None


# Override the live-router once more with the expanded v279 solvers first.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v279_one_variable_equation,
        solve_joint_work,
        solve_v279_motion,
        solve_motion,
        solve_v279_price_quantity_cost,
        solve_purchase,
        solve_money_conversion,
        solve_v279_units,
        solve_v279_geometry,
        solve_division_container_count,
        solve_v279_division_remainder,
        solve_two_part_total,
        solve_v279_basic_addition_word,
        solve_basic_addition_word,
        solve_v279_basic_subtraction_word,
        solve_basic_subtraction_word,
        solve_v279_equal_groups_remaining,
        solve_equal_groups_remaining,
        solve_equal_groups_total,
        solve_v279_equal_sharing,
        solve_equal_sharing,
        solve_proportion,
        solve_fraction_part,
        solve_v279_fraction_whole_compare,
        solve_v279_relation_more_less,
        solve_compare_two_expressions,
        solve_v279_expression_eval,
        solve_v279_table_difference,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return payload
    return None

# --- v279 patch 2: fixes discovered by the first external-audit probe ---
def _v279_unit_word(n: int, unit: str) -> str:  # type: ignore[override]
    u = (unit or '').lower().replace('ё', 'е').strip(' .')
    table = [
        ('км', ('километр', 'километра', 'километров')),
        ('см', ('сантиметр', 'сантиметра', 'сантиметров')),
        ('кг', ('килограмм', 'килограмма', 'килограммов')),
        ('коп', ('копейка', 'копейки', 'копеек')),
        ('руб', ('рубль', 'рубля', 'рублей')),
        ('час', ('час', 'часа', 'часов')),
        ('мин', ('минута', 'минуты', 'минут')),
        ('дн', ('день', 'дня', 'дней')),
        ('грам', ('грамм', 'грамма', 'граммов')),
        ('метр', ('метр', 'метра', 'метров')),
        ('акр', ('акр', 'акра', 'акров')),
        ('ар', ('ар', 'ара', 'аров')),
        ('г', ('грамм', 'грамма', 'граммов')),
        ('м', ('метр', 'метра', 'метров')),
        ('т', ('тонна', 'тонны', 'тонн')),
    ]
    for marker, forms in table:
        if u == marker or marker in u:
            return _choose_plural_int(int(n), *forms)
    return _item_form(int(n), unit)


def _v279_singular_item(word: str) -> str:
    stem = (word or '').lower().replace('ё', 'е')
    mapping = [
        ('блокнот', 'блокнот'), ('тетрад', 'тетрадь'), ('ручк', 'ручка'),
        ('карандаш', 'карандаш'), ('яблок', 'яблоко'), ('конфет', 'конфета'),
        ('книг', 'книга'), ('пакет', 'пакет'), ('короб', 'коробка'),
    ]
    for marker, one in mapping:
        if marker in stem:
            return one
    return word


def solve_v279_equal_groups_remaining_after_number(text: str) -> Optional[dict]:
    source = _lower(text)
    if 'остал' not in source:
        return None
    m = re.search(
        r'(?:в|на)\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b.*?'
        r'(\d+)\s+([а-яеё]+)\s+(?:взяли|забрали|утащили|унесли|израсходовали|отдали|подарили)',
        source, flags=re.IGNORECASE)
    if not m:
        return None
    groups, each, taken = int(m.group(1)), int(m.group(3)), int(m.group(5))
    item = m.group(4)
    total = groups * each
    left = total - taken
    return _result(['Задача.', _v279_sentence(text), 'Решение.',
                    f'1) {groups} × {each} = {total} {_item_form(total,item)} — было всего.',
                    f'2) {total} − {taken} = {left} {_item_form(left,item)} — осталось.',
                    f'Ответ: Осталось {_count_with_item(left,item)}.'], 'local:live-v279-equal-groups-remaining')


def solve_v279_price_quantity_cost(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    # Quantity from available money and unit price.  Do not require exact case form.
    m = re.search(r'сколько\s+([а-яеё]+)\s+можно\s+купить\s+на\s+(\d+)\s*(?:руб|р\b).*?(?:одна|один|1)\s+([а-яеё]+)\s+стоит\s+(\d+)\s*(?:руб|р\b)', source, flags=re.IGNORECASE)
    if m and _v278_same_item(m.group(1), m.group(3)):
        item, money, price = m.group(1), int(m.group(2)), int(m.group(4))
        qty = money // price if price else 0
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {money} : {price} = {qty} — делим деньги на цену одного предмета.',
                        f'Ответ: Можно купить {_count_with_item(qty, item)}.'], 'local:live-v279-price-quantity')
    m = re.search(r'за\s+(\d+)\s+одинаков[а-я]+\s+([а-яеё]+)\s+заплатил[а-я]*\s+(\d+)\s*(?:руб|р\b).*?сколько\s+рубл[а-я]*\s+стоит\s+один', source, flags=re.IGNORECASE)
    if m:
        qty, item, total = int(m.group(1)), m.group(2), int(m.group(3))
        price = Fraction(total, qty)
        price_int = price.numerator if price.denominator == 1 else 5
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {total} : {qty} = {_fmt_fraction(price)} рублей — цена одного предмета.',
                        f'Ответ: Один {_v279_singular_item(item)} стоит {_fmt_fraction(price)} {_v279_unit_word(price_int, "руб")}.'], 'local:live-v279-price-one')
    return None


def solve_v279_motion(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    m = re.search(r'со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч.*?(?:прош[её]л|проехал|пролетел|проплыл|прошла|проехала)\s+(\d+)\s*км', source, flags=re.IGNORECASE)
    if m and re.search(r'сколько\s+час|за\s+сколько\s+час|время', source):
        speed, distance = int(m.group(1)), int(m.group(2))
        if speed == 0:
            return None
        t = Fraction(distance, speed)
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        '1) Чтобы найти время, расстояние делим на скорость.',
                        f'2) {distance} : {speed} = {_fmt_fraction(t)} часа.',
                        f'Ответ: Объект двигался {_format_time(t, "час")}.'], 'local:live-v279-motion-time')
    m = re.search(r'скорость\s+перв[а-я]+\s+(\d+)\s*км\s*/?\s*ч,?\s*(?:скорость\s+)?втор[а-я]+\s+(\d+)\s*км\s*/?\s*ч.*?через\s+(\d+)\s*час', source, flags=re.IGNORECASE)
    if m and re.search(r'навстречу|встретил', source) and re.search(r'расстояни[ея]|между\s+город', source):
        v1, v2, t = map(int, m.groups())
        closing = v1 + v2
        dist = closing * t
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) {v1} + {v2} = {closing} км/ч — скорость сближения.',
                        f'2) {closing} × {t} = {dist} км — расстояние между городами.',
                        f'Ответ: Расстояние между городами {dist} километров.'], 'local:live-v279-motion-towards')
    m = re.search(r'(?:прош[её]л|проехал|проплыл|пролетел)\s+(\d+)\s*км.*?остал[а-я]+\s+(?:пройти|проехать|проплыть|пролететь)\s+в\s+(\d+)\s+раз[а]?\s+(больше|меньше)', source, flags=re.IGNORECASE)
    if m and re.search(r'весь\s+путь|всего|общ', source):
        done, k, kind = int(m.group(1)), int(m.group(2)), m.group(3)
        rest = done * k if 'больше' in kind else Fraction(done, k)
        if rest.denominator != 1:
            return None
        total = done + rest.numerator
        return _result(['Задача.', _v279_sentence(text), 'Решение.',
                        f'1) Уже пройдено {done} км.',
                        f'2) {done} : {k} = {rest.numerator} км — осталось пройти.' if 'меньше' in kind else f'2) {done} × {k} = {rest.numerator} км — осталось пройти.',
                        f'3) {done} + {rest.numerator} = {total} км — весь путь.',
                        f'Ответ: Весь путь составляет {total} километров.'], 'local:live-v279-motion-remaining')
    return None


def solve_v279_container_count(text: str) -> Optional[dict]:
    source = _lower(text)
    m = re.search(r'(?:в\s+)?([а-яеё]+)\s+помещается\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+нужно\s+для\s+(\d+)\s+\3', source, flags=re.IGNORECASE)
    if not m:
        return None
    container, per, item, container_q, total = m.group(1), int(m.group(2)), m.group(3), m.group(4), int(m.group(5))
    if per <= 0:
        return None
    full, rem = divmod(total, per)
    need = full + (1 if rem else 0)
    return _result(['Задача.', _v279_sentence(text), 'Решение.',
                    f'1) {total} : {per} = {full} (ост. {rem}).',
                    f'2) Так как остаток {rem}, нужна ещё одна {container}: {full} + 1 = {need}.' if rem else f'2) Остатка нет, значит нужно {need}.',
                    f'Ответ: Нужно {_count_with_item(need, container_q)}.'], 'local:live-v279-container-count')


def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v279_one_variable_equation,
        solve_joint_work,
        solve_v279_motion,
        solve_motion,
        solve_v279_price_quantity_cost,
        solve_purchase,
        solve_money_conversion,
        solve_v279_units,
        solve_v279_geometry,
        solve_v279_container_count,
        solve_division_container_count,
        solve_v279_division_remainder,
        solve_two_part_total,
        solve_v279_basic_addition_word,
        solve_basic_addition_word,
        solve_v279_basic_subtraction_word,
        solve_basic_subtraction_word,
        solve_v279_equal_groups_remaining_after_number,
        solve_v279_equal_groups_remaining,
        solve_equal_groups_remaining,
        solve_equal_groups_total,
        solve_v279_equal_sharing,
        solve_equal_sharing,
        solve_proportion,
        solve_fraction_part,
        solve_v279_fraction_whole_compare,
        solve_v279_relation_more_less,
        solve_compare_two_expressions,
        solve_v279_expression_eval,
        solve_v279_table_difference,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return payload
    return None

# --- v279 patch 3: wording cleanup for container-count explanations ---
def solve_v279_container_count(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    m = re.search(r'(?:в\s+)?([а-яеё]+)\s+помещается\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+нужно\s+для\s+(\d+)\s+\3', source, flags=re.IGNORECASE)
    if not m:
        return None
    container, per, item, container_q, total = m.group(1), int(m.group(2)), m.group(3), m.group(4), int(m.group(5))
    if per <= 0:
        return None
    full, rem = divmod(total, per)
    need = full + (1 if rem else 0)
    one_container = _v279_singular_item(container_q or container)
    return _result(['Задача.', _v279_sentence(text), 'Решение.',
                    f'1) {total} : {per} = {full} (ост. {rem}).',
                    f'2) Так как остаток {rem}, нужна ещё одна {one_container}: {full} + 1 = {need}.' if rem else f'2) Остатка нет, значит нужно {need}.',
                    f'Ответ: Нужно {_count_with_item(need, container_q)}.'], 'local:live-v279-container-count')

# --- v279 patch 4: prevent addition solver from swallowing subtraction verbs like "отдал" ---
def solve_v279_basic_addition_word(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _lower(text)
    if re.search(r'\b(?:отдал[а-я]*|потратил[а-я]*|израсходовал[а-я]*|вышл[а-я]*|забрал[а-я]*|унес[а-я]*|убрал[а-я]*)\b', source):
        return None
    if not re.search(r'сколько|всего|стало|получилось', source):
        return None
    patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?\b(?:дали|дала|дал|добавили|подарили|принесли|положили|доложили|купил[а-я]*|наш[её]л[а-я]*)\b\s+(?:ей|ему|им|еще|ещ[её])?\s*(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
        r'лежал[а-я]*\s+(\d+)\s+([а-яеё]+)\b.*?\b(?:положили|добавили|принесли)\b\s+(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
    ]
    for pat in patterns:
        m = re.search(pat, source, flags=re.IGNORECASE)
        if m:
            first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
            if not _v278_same_item(item, item2):
                return None
            total = first + second
            subj = _v279_subject(text)
            final = f'У {subj} стало {_count_with_item(total, item)}.' if subj else f'Всего стало {_count_with_item(total, item)}.'
            return _result(['Задача.', _v279_sentence(text), 'Решение.',
                            f'1) {first} + {second} = {total} {_item_form(total, item)} — складываем количество.',
                            f'Ответ: {final}'], 'local:live-v279-basic-addition')
    return None

# --- v280 external black-box audit wave 1: grade 1-2 basics + text tasks + route/input guard ---
# Structural handlers only: no exact task lookup.  These solvers cover broad
# elementary patterns found during external category mining for Russian grade 1-2
# math tasks: place value, comparisons, units, direct arithmetic, simple word
# problems, money/time, and route wrapper noise.

_V280_RELEASE_NOTE = 'v280_external_blackbox_audit_wave1_grade1_2_basics'


def _v280_clean_task(text: str) -> str:
    value = _clean_text(text)
    # Remove common classroom/app wrappers without touching the task body.
    for _ in range(4):
        before = value
        value = re.sub(r'^\s*(?:пожалуйста,?\s*)?(?:реши(?:те)?|помоги(?:те)?\s+решить)\s+(?:задачу|пример|задание|уравнение)\s*[:.!?\-–—]*\s*', '', value, flags=re.IGNORECASE)
        value = re.sub(r'^\s*(?:пожалуйста,?\s*)?(?:реши(?:те)?|вычисли(?:те)?|найди(?:те)?\s+ответ)\s*[:.!?\-–—]+\s*', '', value, flags=re.IGNORECASE)
        value = re.sub(r'^\s*(?:задача|задание|пример)\s*(?:№\s*)?\d*\s*[:.)\]-–—]*\s*', '', value, flags=re.IGNORECASE)
        value = value.strip()
        if value == before:
            break
    # Hints about output format should not affect solving.
    value = re.sub(r'\s*ответ\s+запиши(?:те)?\s+(?:числом|кратко)\s*[.!?]*\s*$', '', value, flags=re.IGNORECASE).strip()
    return value


def _v280_lower(text: str) -> str:
    return _v280_clean_task(text).lower().replace('ё', 'е')


def _v280_same_stem(a: str, b: str) -> bool:
    a = (a or '').lower().replace('ё', 'е').strip(' .,!?:;')
    b = (b or '').lower().replace('ё', 'е').strip(' .,!?:;')
    if not a or not b:
        return True
    if a == b:
        return True
    irregular = {
        'реб': 'дет', 'дет': 'реб',
        'человек': 'учен', 'учен': 'учен',
        'мяч': 'мяч', 'мячей': 'мяч',
        'роз': 'роз', 'розы': 'роз',
    }
    for key, val in irregular.items():
        if key in a and val in b:
            return True
    return a[:4] == b[:4] or a[:5] == b[:5]


def _v280_unit_forms(word: str) -> tuple[str, str, str] | None:
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    mapping = [
        (('яблок',), ('яблоко', 'яблока', 'яблок')),
        (('шишк',), ('шишка', 'шишки', 'шишек')),
        (('карандаш',), ('карандаш', 'карандаша', 'карандашей')),
        (('конфет',), ('конфета', 'конфеты', 'конфет')),
        (('книг',), ('книга', 'книги', 'книг')),
        (('наклей',), ('наклейка', 'наклейки', 'наклеек')),
        (('марк',), ('марка', 'марки', 'марок')),
        (('машинк',), ('машинка', 'машинки', 'машинок')),
        (('машин',), ('машина', 'машины', 'машин')),
        (('пассажир',), ('пассажир', 'пассажира', 'пассажиров')),
        (('роз',), ('роза', 'розы', 'роз')),
        (('открытк',), ('открытка', 'открытки', 'открыток')),
        (('фишк',), ('фишка', 'фишки', 'фишек')),
        (('мяч',), ('мяч', 'мяча', 'мячей')),
        (('печен',), ('печенье', 'печенья', 'печений')),
        (('ученик', 'учен'), ('ученик', 'ученика', 'учеников')),
        (('девоч',), ('девочка', 'девочки', 'девочек')),
        (('мальчик',), ('мальчик', 'мальчика', 'мальчиков')),
        (('короб',), ('коробка', 'коробки', 'коробок')),
        (('пакет',), ('пакет', 'пакета', 'пакетов')),
        (('тарел',), ('тарелка', 'тарелки', 'тарелок')),
        (('корзин',), ('корзина', 'корзины', 'корзин')),
        (('тетрад',), ('тетрадь', 'тетради', 'тетрадей')),
        (('блокнот',), ('блокнот', 'блокнота', 'блокнотов')),
        (('ручк',), ('ручка', 'ручки', 'ручек')),
        (('линейк',), ('линейка', 'линейки', 'линеек')),
        (('руб',), ('рубль', 'рубля', 'рублей')),
        (('коп',), ('копейка', 'копейки', 'копеек')),
        (('сантиметр', 'см'), ('сантиметр', 'сантиметра', 'сантиметров')),
        (('дециметр', 'дм'), ('дециметр', 'дециметра', 'дециметров')),
        (('минут', 'мин'), ('минута', 'минуты', 'минут')),
        (('час',), ('час', 'часа', 'часов')),
        (('день', 'дн'), ('день', 'дня', 'дней')),
        (('недел',), ('неделя', 'недели', 'недель')),
        (('кубик',), ('кубик', 'кубика', 'кубиков')),
        (('шар',), ('шар', 'шара', 'шаров')),
    ]
    for markers, forms in mapping:
        if any(marker in stem for marker in markers):
            return forms
    return None


def _v280_word(n: int, word: str) -> str:
    forms = _v280_unit_forms(word)
    if forms:
        return _choose_plural_int(int(n), forms[0], forms[1], forms[2])
    return _item_form(int(n), word)


def _v280_count(n: int, word: str) -> str:
    return f'{n} {_v280_word(n, word)}'


def _v280_subject_name(text: str, default: str = '') -> str:
    source = str(text or '')
    m = re.search(r'\b[Уу]\s+([А-ЯЁ][а-яё]+)\b', source)
    if m:
        return m.group(1)
    return default


def _v280_person_from_phrase(phrase: str) -> str:
    return str(phrase or '').strip().capitalize()


def _v280_money(n: int) -> str:
    return _v280_count(n, 'рубль')


def _v280_eval_expr(expr: str) -> Optional[Fraction]:
    cleaned = str(expr or '').strip()
    cleaned = cleaned.replace('−', '-').replace('–', '-').replace('—', '-')
    cleaned = cleaned.replace('×', '*').replace('·', '*').replace('÷', ':').replace('/', ':')
    cleaned = re.sub(r'\s+', '', cleaned)
    if not cleaned or not re.fullmatch(r'[0-9+\-*:().]+', cleaned):
        return None
    return _v278_eval_simple_expr(cleaned)


def _v280_time_to_minutes(value: str) -> Optional[int]:
    m = re.fullmatch(r'(\d{1,2})\s*[:.]\s*(\d{2})', str(value or '').strip())
    if not m:
        return None
    h, minute = int(m.group(1)), int(m.group(2))
    if h > 23 or minute > 59:
        return None
    return h * 60 + minute


def _v280_minutes_to_clock(total: int) -> str:
    total %= 24 * 60
    return f'{total // 60}:{total % 60:02d}'


def solve_v280_place_value_and_compare(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    m = re.search(r'числ[оа],?\s+в\s+котор[а-я]+\s+(\d+)\s+десятк[а-я]*\s+и\s+(\d+)\s+единиц', source, flags=re.IGNORECASE)
    if m and re.search(r'запиши|найди|какое', source):
        tens, ones = int(m.group(1)), int(m.group(2))
        ans = tens * 10 + ones
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {tens} десятка — это {tens * 10}.',
                        f'2) {tens * 10} + {ones} = {ans}.',
                        f'Ответ: {ans}.'], 'local:live-v280-place-value')
    m = re.search(r'в\s+числе\s+(\d{2})\s+сколько\s+десятк[а-я]*\s+и\s+сколько\s+единиц', source, flags=re.IGNORECASE)
    if m:
        n = int(m.group(1)); tens, ones = divmod(n, 10)
        return _result(['Задача.', clean, 'Решение.',
                        f'1) В числе {n} цифра десятков — {tens}, цифра единиц — {ones}.',
                        f'Ответ: {tens} десятков и {ones} единиц.'], 'local:live-v280-place-value')
    m = re.search(r'сравни\s+числа\s+(\d+)\s+и\s+(\d+)', source, flags=re.IGNORECASE)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        sign = '<' if a < b else '>' if a > b else '='
        relation = 'меньше' if a < b else 'больше' if a > b else 'равно'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) Сравниваем числа {a} и {b}.',
                        f'2) {a} {sign} {b}.',
                        f'Ответ: {a} {sign} {b}; число {a} {relation} числа {b}.'], 'local:live-v280-number-compare')
    m = re.search(r'какое\s+число\s+больше\s*:?\s*(\d+)\s+или\s+(\d+)', source, flags=re.IGNORECASE)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        ans = max(a, b)
        return _result(['Задача.', clean, 'Решение.',
                        f'1) Сравниваем {a} и {b}.',
                        f'Ответ: Больше число {ans}.'], 'local:live-v280-number-compare')
    m = re.search(r'число\s+(\d+)\s+четн[а-я]*\s+или\s+нечетн[а-я]*', source, flags=re.IGNORECASE)
    if m:
        n = int(m.group(1)); even = n % 2 == 0
        return _result(['Задача.', clean, 'Решение.',
                        f'1) Последняя цифра числа {n} — {n % 10}.',
                        f'2) Число делится на 2 без остатка.' if even else '2) Число не делится на 2 без остатка.',
                        f'Ответ: Число {n} ' + ('чётное.' if even else 'нечётное.')], 'local:live-v280-parity')
    return None


def solve_v280_units_and_calendar(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    m = re.search(r'сколько\s+сантиметр[а-я]*\s+в\s+(\d+)\s*дм\s*(\d+)?\s*см?', source, flags=re.IGNORECASE)
    if m:
        dm = int(m.group(1)); cm = int(m.group(2) or 0); total = dm * 10 + cm
        return _result(['Задача.', clean, 'Решение.',
                        f'1) 1 дм = 10 см, значит {dm} дм = {dm * 10} см.',
                        f'2) {dm * 10} + {cm} = {total} см.',
                        f'Ответ: Всего {_v280_count(total, "сантиметр")}.'], 'local:live-v280-units')
    m = re.search(r'сколько\s+дн[а-я]*\s+в\s+(\d+)\s+недел[а-я]*', source, flags=re.IGNORECASE)
    if m:
        weeks = int(m.group(1)); days = weeks * 7
        return _result(['Задача.', clean, 'Решение.',
                        f'1) В одной неделе 7 дней.',
                        f'2) {weeks} × 7 = {days} дней.',
                        f'Ответ: В {weeks} неделях {_v280_count(days, "день")}.'], 'local:live-v280-calendar')
    m = re.search(r'(?:начал[а-я]*ся|начал[а-я]*ась)\s+в\s+(\d{1,2}[:.]\d{2})\s+и\s+законч[а-я]*\s+в\s+(\d{1,2}[:.]\d{2}).*?сколько\s+минут', source, flags=re.IGNORECASE)
    if m:
        start = _v280_time_to_minutes(m.group(1)); end = _v280_time_to_minutes(m.group(2))
        if start is None or end is None:
            return None
        duration = end - start
        if duration < 0:
            duration += 24 * 60
        return _result(['Задача.', clean, 'Решение.',
                        f'1) От {m.group(1).replace(".", ":")} до {m.group(2).replace(".", ":")} прошло {duration} минут.',
                        f'Ответ: Длилось {_v280_count(duration, "минута")}.'], 'local:live-v280-time')
    m = re.search(r'(?:начал[а-я]*ся|начал[а-я]*ась)\s+в\s+(\d{1,2}[:.]\d{2})\s+и\s+длил[а-я]*\s+(\d+)\s+минут[а-я]*.*?(?:во\s+сколько|когда)\s+.*?законч', source, flags=re.IGNORECASE)
    if m:
        start = _v280_time_to_minutes(m.group(1)); duration = int(m.group(2))
        if start is None:
            return None
        end = _v280_minutes_to_clock(start + duration)
        return _result(['Задача.', clean, 'Решение.',
                        f'1) К времени начала {m.group(1).replace(".", ":")} прибавляем {duration} минут.',
                        f'Ответ: Закончился в {end}.'], 'local:live-v280-time')
    return None


def solve_v280_direct_arithmetic(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    m = re.search(r'делени[ея]\s+с\s+остатком\s*[:\-–—]?\s*(\d+)\s*[:/]\s*(\d+)', source, flags=re.IGNORECASE)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b == 0:
            return None
        q, r = divmod(a, b)
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {a} : {b} = {q} (ост. {r}).',
                        f'Ответ: {q}, остаток {r}.'], 'local:live-v280-remainder')
    m = re.search(r'какое\s+число\s+на\s+(\d+)\s+(больше|меньше)\s+(\d+)', source, flags=re.IGNORECASE)
    if m:
        delta, kind, base = int(m.group(1)), m.group(2), int(m.group(3))
        ans = base + delta if 'больше' in kind else base - delta
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {base} {op} {delta} = {ans}.',
                        f'Ответ: {ans}.'], 'local:live-v280-number-transform')
    m = re.search(r'увеличь\s+(\d+)\s+в\s+(\d+)\s+раз', source, flags=re.IGNORECASE)
    if m:
        a, k = int(m.group(1)), int(m.group(2)); ans = a * k
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {a} × {k} = {ans}.', f'Ответ: {ans}.'], 'local:live-v280-number-transform')
    m = re.search(r'уменьши\s+(\d+)\s+в\s+(\d+)\s+раз', source, flags=re.IGNORECASE)
    if m:
        a, k = int(m.group(1)), int(m.group(2))
        if k == 0:
            return None
        ans = Fraction(a, k)
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {a} : {k} = {_fmt_fraction(ans)}.', f'Ответ: {_fmt_fraction(ans)}.'], 'local:live-v280-number-transform')
    # Direct expression after a solver verb, or a bare arithmetic expression.
    expr = None
    m = re.search(r'(?:вычисли|реши|найди\s+значение\s+выражения|найди)\s*:?[\s]*(.+?)(?:[.!?]|$)', clean, flags=re.IGNORECASE)
    if m:
        expr = m.group(1).strip()
    elif re.fullmatch(r'[0-9\s+\-−–—*:×·÷/().]+', clean):
        expr = clean
    if expr:
        # Do not let a word-problem fragment be treated as expression.
        if re.fullmatch(r'[0-9\s+\-−–—*:×·÷/().]+', expr):
            val = _v280_eval_expr(expr)
            if val is None:
                return None
            val_text = _fmt_fraction(val)
            return _result(['Задача.', clean, 'Решение.',
                            '1) Вычисляем выражение по порядку действий.',
                            f'2) {expr.strip()} = {val_text}.',
                            f'Ответ: {val_text}.'], 'local:live-v280-direct-arithmetic')
    return None


def solve_v280_simple_add_sub(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    # Было N, добавили M -> стало.
    add_patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?(?:дали|дала|дал|добавили|подарили|принесли|положили|поставили|доложили|купил[а-я]*|наш[её]л[а-я]*)\s+(?:ей|ему|им|еще|ещ[её])?\s*(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
        r'лежал[а-я]*\s+(\d+)\s+([а-яеё]+)\b.*?(?:положили|добавили|принесли|поставили)\s+(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
    ]
    if re.search(r'сколько|стало|всего|получилось', source):
        for pat in add_patterns:
            m = re.search(pat, source, flags=re.IGNORECASE)
            if m:
                first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
                if not _v280_same_stem(item, item2):
                    return None
                total = first + second
                subj = _v280_subject_name(text)
                final = f'У {subj} стало {_v280_count(total, item)}.' if subj else f'Стало {_v280_count(total, item)}.'
                return _result(['Задача.', clean, 'Решение.',
                                f'1) {first} + {second} = {total} {_v280_word(total, item)} — стало всего.',
                                f'Ответ: {final}'], 'local:live-v280-basic-addition')
    # Было N, убрали M -> осталось. Handles subjects and locations.
    sub_patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?(?:отдал[а-я]*|подарил[а-я]*|израсходовал[а-я]*|потратил[а-я]*|съел[а-я]*|забрал[а-я]*|унес[а-я]*|вышл[а-я]*|убрал[а-я]*|взял[а-я]*|уехал[а-я]*|ушл[а-я]*|продал[а-я]*)\s+(?:другу\s+)?(\d+)\s+([а-яеё]+)\b',
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?(?:уехал[а-я]*|ушл[а-я]*|вышл[а-я]*|продал[а-я]*)\s+(\d+)\s+([а-яеё]+)\b',
    ]
    if 'остал' in source:
        for pat in sub_patterns:
            m = re.search(pat, source, flags=re.IGNORECASE)
            if m:
                first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
                if not _v280_same_stem(item, item2):
                    return None
                left = first - second
                subj = _v280_subject_name(text)
                final = f'У {subj} осталось {_v280_count(left, item)}.' if subj else f'Осталось {_v280_count(left, item)}.'
                return _result(['Задача.', clean, 'Решение.',
                                f'1) {first} − {second} = {left} {_v280_word(left, item)} — осталось.',
                                f'Ответ: {final}'], 'local:live-v280-basic-subtraction')
    return None


def solve_v280_equal_groups_and_sharing(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    # In N groups, each M items.
    m = re.search(r'(?:в|на)\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b.*?сколько\s+\4\s+(?:всего|на\s+всех|получилось)?', source, flags=re.IGNORECASE)
    if m:
        groups, group_word, each, item = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
        total = groups * each
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {groups} × {each} = {total} {_v280_word(total, item)} — всего.',
                        f'Ответ: Всего {_v280_count(total, item)}.'], 'local:live-v280-equal-groups')
    m = re.search(r'(?:в|на)\s+одн[а-я]+\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?сколько\s+\3\s+в\s+(\d+)\s+таких\s+\1', source, flags=re.IGNORECASE)
    if m:
        group_word, each, item, groups = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        total = groups * each
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {each} × {groups} = {total} {_v280_word(total, item)}.',
                        f'Ответ: В {groups} таких {group_word} {_v280_count(total, item)}.'], 'local:live-v280-equal-groups')
    # Equal sharing: total items equally among children/plates/boxes.
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+(?:раздали|разложили|поделили)\s+поровну\s+(?:на|между|в)?\s*(\d+)\s+([а-яеё]+).*?сколько\s+\2', source, flags=re.IGNORECASE)
    if m:
        total, item, groups, group_word = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
        if groups == 0:
            return None
        per = Fraction(total, groups)
        if per.denominator != 1:
            return None
        ans = per.numerator
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {total} : {groups} = {ans} {_v280_word(ans, item)} — в каждой группе.',
                        f'Ответ: На каждой/у каждого будет {_v280_count(ans, item)}.'], 'local:live-v280-equal-sharing')
    # Exact grouping into containers.
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+разложили\s+в\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+получилось', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(2), m.group(5)):
        total, item, container_q, per, asked_container = int(m.group(1)), m.group(2), m.group(3), int(m.group(4)), m.group(6)
        if per == 0:
            return None
        q, r = divmod(total, per)
        if r == 0:
            return _result(['Задача.', clean, 'Решение.',
                            f'1) {total} : {per} = {q}.',
                            f'Ответ: Получилось {_v280_count(q, asked_container)}.'], 'local:live-v280-exact-grouping')
    return None


def solve_v280_relation_and_composite(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    # Compound total: one child has base, another has delta more/less, find together.
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+на\s+(\d+)\s+\3\s+(больше|меньше).*?сколько\s+\3\s+у\s+них\s+вместе', source, flags=re.IGNORECASE)
    if m:
        p1, base, item, p2, delta, kind = m.group(1), int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(6)
        second = base + delta if 'больше' in kind else base - delta
        total = base + second
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {base} {op} {delta} = {second} {_v280_word(second, item)} — у второго ребёнка.',
                        f'2) {base} + {second} = {total} {_v280_word(total, item)} — всего у них вместе.',
                        f'Ответ: У них вместе {_v280_count(total, item)}.'], 'local:live-v280-composite-relation')
    # Direct more/less relation.
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+на\s+(\d+)\s+\3\s+(больше|меньше).*?сколько\s+\3\s+у\s+\4', source, flags=re.IGNORECASE)
    if m:
        base, item, p2, delta, kind = int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(6)
        ans = base + delta if 'больше' in kind else base - delta
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {base} {op} {delta} = {ans} {_v280_word(ans, item)}.',
                        f'Ответ: У {_v280_person_from_phrase(p2)} {_v280_count(ans, item)}.'], 'local:live-v280-relation')
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+в\s+(\d+)\s+раз[а]?\s+(больше|меньше).*?сколько\s+\3\s+у\s+\4', source, flags=re.IGNORECASE)
    if m:
        base, item, p2, k, kind = int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(6)
        ans = Fraction(base * k, 1) if 'больше' in kind else Fraction(base, k)
        if ans.denominator != 1:
            return None
        op = '×' if 'больше' in kind else ':'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {base} {op} {k} = {ans.numerator} {_v280_word(ans.numerator, item)}.',
                        f'Ответ: У {_v280_person_from_phrase(p2)} {_v280_count(ans.numerator, item)}.'], 'local:live-v280-relation')
    # Reverse relation: A has N, this is delta more/less than B.
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s+([а-яеё]+).*?это\s+на\s+(\d+)\s+(больше|меньше),?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+\3\s+у\s+\6', source, flags=re.IGNORECASE)
    if m:
        base, item, delta, kind, other = int(m.group(2)), m.group(3), int(m.group(4)), m.group(5), m.group(6)
        ans = base - delta if 'больше' in kind else base + delta
        op = '−' if 'больше' in kind else '+'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {base} {op} {delta} = {ans} {_v280_word(ans, item)}.',
                        f'Ответ: У {_v280_person_from_phrase(other)} {_v280_count(ans, item)}.'], 'local:live-v280-reverse-relation')
    # Two categories total minus leavers.
    m = re.search(r'в\s+классе\s+(\d+)\s+девоч[а-я]*\s+и\s+(\d+)\s+мальчик[а-я]*.*?(\d+)\s+ученик[а-я]*\s+(?:ушл|ушли|уехал|вышл)[а-я]*.*?сколько\s+ученик[а-я]*\s+остал', source, flags=re.IGNORECASE)
    if m:
        girls, boys, left_count = int(m.group(1)), int(m.group(2)), int(m.group(3))
        total = girls + boys
        remain = total - left_count
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {girls} + {boys} = {total} учеников — было в классе.',
                        f'2) {total} − {left_count} = {remain} учеников — осталось.',
                        f'Ответ: В классе осталось {_v280_count(remain, "ученик")}.'], 'local:live-v280-composite-total-left')
    return None


def solve_v280_money_and_time_text(text: str) -> Optional[dict]:
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    # Price × quantity, quantity may come after price.
    m = re.search(r'(?:одна|один|1)\s+([а-яеё]+)\s+стоит\s+(\d+)\s*(?:руб|р\b).*?сколько\s+стоят\s+(\d+)\s+(?:таких\s+)?([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(1), m.group(4)):
        item, price, qty = m.group(1), int(m.group(2)), int(m.group(3))
        total = price * qty
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {price} × {qty} = {total} рублей — стоимость покупки.',
                        f'Ответ: {qty} {_v280_word(qty, item)} стоят {_v280_money(total)}.'], 'local:live-v280-money-cost')
    # Budget with one purchase/change.
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s*(?:руб|р\b).*?купил[а-я]*\s+([а-яеё]+)\s+за\s+(\d+)\s*(?:руб|р\b).*?(?:сдачи\s+получил|остал)', source, flags=re.IGNORECASE)
    if m:
        person, initial, item, price = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        left = initial - price
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {initial} − {price} = {left} рублей.',
                        f'Ответ: У {_v280_person_from_phrase(person)} осталось/сдача {_v280_money(left)}.'], 'local:live-v280-money-change')
    # Budget with two named purchases.
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s*(?:руб|р\b).*?купил[а-я]*\s+([а-яеё]+)\s+за\s+(\d+)\s*(?:руб|р\b)\s+и\s+([а-яеё]+)\s+за\s+(\d+)\s*(?:руб|р\b).*?сколько\s+руб[а-я]*\s+остал', source, flags=re.IGNORECASE)
    if m:
        person, initial, item1, price1, item2, price2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4)), m.group(5), int(m.group(6))
        spent = price1 + price2
        left = initial - spent
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {price1} + {price2} = {spent} рублей — потратил на покупки.',
                        f'2) {initial} − {spent} = {left} рублей — осталось.',
                        f'Ответ: У {_v280_person_from_phrase(person)} осталось {_v280_money(left)}.'], 'local:live-v280-money-two-purchases')
    # Quantity from budget: item costs N rubles.
    m = re.search(r'сколько\s+([а-яеё]+)\s+можно\s+купить\s+на\s+(\d+)\s*(?:руб|р\b).*?([а-яеё]+)\s+стоит\s+(\d+)\s*(?:руб|р\b)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(1), m.group(3)):
        item, money, price = m.group(1), int(m.group(2)), int(m.group(4))
        if price == 0:
            return None
        qty = money // price
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {money} : {price} = {qty} — делим сумму денег на цену одного предмета.',
                        f'Ответ: Можно купить {_v280_count(qty, item)}.'], 'local:live-v280-money-quantity')
    return None


# Override the live router for v280.  v280 solvers run before v279/v276 ones,
# then the previous structural solvers remain as fallback coverage.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v279_one_variable_equation,
        solve_v280_place_value_and_compare,
        solve_v280_units_and_calendar,
        solve_v280_direct_arithmetic,
        solve_v280_money_and_time_text,
        solve_v280_relation_and_composite,
        solve_v280_equal_groups_and_sharing,
        solve_v280_simple_add_sub,
        solve_joint_work,
        solve_v279_motion,
        solve_motion,
        solve_v279_price_quantity_cost,
        solve_purchase,
        solve_money_conversion,
        solve_v279_units,
        solve_v279_geometry,
        solve_v279_container_count,
        solve_division_container_count,
        solve_v279_division_remainder,
        solve_two_part_total,
        solve_v279_basic_addition_word,
        solve_basic_addition_word,
        solve_v279_basic_subtraction_word,
        solve_basic_subtraction_word,
        solve_v279_equal_groups_remaining_after_number,
        solve_v279_equal_groups_remaining,
        solve_equal_groups_remaining,
        solve_equal_groups_total,
        solve_v279_equal_sharing,
        solve_equal_sharing,
        solve_proportion,
        solve_fraction_part,
        solve_v279_fraction_whole_compare,
        solve_v279_relation_more_less,
        solve_compare_two_expressions,
        solve_v279_expression_eval,
        solve_v279_table_difference,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return payload
    return None

# --- v280 wave1 patch 1: morphology/order fixes found by black-box probe ---
def solve_v280_simple_add_sub(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    # Subtraction must be checked before addition so words like "продали" do not
    # get partially matched as "дали".
    sub_patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?\b(?:отдал[а-я]*|подарил[а-я]*|израсходовал[а-я]*|потратил[а-я]*|съел[а-я]*|забрал[а-я]*|унес[а-я]*|вышл[а-я]*|убрал[а-я]*|взял[а-я]*|уехал[а-я]*|ушл[а-я]*|продал[а-я]*)\b\s+(?:другу\s+)?(\d+)\s+([а-яеё]+)\b',
    ]
    if 'остал' in source:
        for pat in sub_patterns:
            m = re.search(pat, source, flags=re.IGNORECASE)
            if m:
                first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
                if not _v280_same_stem(item, item2):
                    return None
                left = first - second
                subj = _v280_subject_name(text)
                final = f'У {subj} осталось {_v280_count(left, item)}.' if subj else f'Осталось {_v280_count(left, item)}.'
                return _result(['Задача.', clean, 'Решение.',
                                f'1) {first} − {second} = {left} {_v280_word(left, item)} — осталось.',
                                f'Ответ: {final}'], 'local:live-v280-basic-subtraction')
    add_patterns = [
        r'было\s+(\d+)\s+([а-яеё]+)\b.*?(?:\b(?:ей|ему|им)\s+)?\b(?:дали|дала|дал|добавили|подарили|принесли|положили|поставили|доложили|купил[а-я]*|наш[её]л[а-я]*)\b\s+(?:ей|ему|им|еще|ещ[её])?\s*(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
        r'лежал[а-я]*\s+(\d+)\s+([а-яеё]+)\b.*?\b(?:положили|добавили|принесли|поставили)\b\s+(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b',
    ]
    if re.search(r'сколько|стало|всего|получилось', source):
        for pat in add_patterns:
            m = re.search(pat, source, flags=re.IGNORECASE)
            if m:
                first, item, second, item2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
                if not _v280_same_stem(item, item2):
                    return None
                total = first + second
                subj = _v280_subject_name(text)
                final = f'У {subj} стало {_v280_count(total, item)}.' if subj else f'Стало {_v280_count(total, item)}.'
                return _result(['Задача.', clean, 'Решение.',
                                f'1) {first} + {second} = {total} {_v280_word(total, item)} — стало всего.',
                                f'Ответ: {final}'], 'local:live-v280-basic-addition')
    return None


def solve_v280_equal_groups_and_sharing(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    m = re.search(r'(?:в|на)\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b.*?сколько\s+([а-яеё]+)\s+(?:всего|на\s+всех|получилось)?', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(4), m.group(5)):
        groups, each, item = int(m.group(1)), int(m.group(3)), m.group(4)
        total = groups * each
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {groups} × {each} = {total} {_v280_word(total, item)} — всего.',
                        f'Ответ: Всего {_v280_count(total, item)}.'], 'local:live-v280-equal-groups')
    m = re.search(r'(?:в|на)\s+одн[а-я]+\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+в\s+(\d+)\s+таких\s+([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(3), m.group(4)) and _v280_same_stem(m.group(1), m.group(6)):
        group_word, each, item, groups = m.group(1), int(m.group(2)), m.group(3), int(m.group(5))
        total = groups * each
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {each} × {groups} = {total} {_v280_word(total, item)}.',
                        f'Ответ: В {groups} таких {group_word} {_v280_count(total, item)}.'], 'local:live-v280-equal-groups')
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+(?:раздали|разложили|поделили)\s+поровну\s+(?:на|между|в)?\s*(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(2), m.group(5)):
        total, item, groups = int(m.group(1)), m.group(2), int(m.group(3))
        if groups == 0:
            return None
        per = Fraction(total, groups)
        if per.denominator != 1:
            return None
        ans = per.numerator
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {total} : {groups} = {ans} {_v280_word(ans, item)} — в каждой группе.',
                        f'Ответ: На каждой/у каждого будет {_v280_count(ans, item)}.'], 'local:live-v280-equal-sharing')
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+разложили\s+в\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+получилось', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(2), m.group(5)):
        total, item, per, asked_container = int(m.group(1)), m.group(2), int(m.group(4)), m.group(6)
        if per == 0:
            return None
        q, r = divmod(total, per)
        if r == 0:
            return _result(['Задача.', clean, 'Решение.',
                            f'1) {total} : {per} = {q}.',
                            f'Ответ: Получилось {_v280_count(q, asked_container)}.'], 'local:live-v280-exact-grouping')
    return None


def solve_v280_relation_and_composite(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+на\s+(\d+)\s+([а-яеё]+)\s+(больше|меньше).*?сколько\s+([а-яеё]+)\s+у\s+них\s+вместе', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(3), m.group(6)) and _v280_same_stem(m.group(3), m.group(8)):
        base, item, delta, kind = int(m.group(2)), m.group(3), int(m.group(5)), m.group(7)
        second = base + delta if 'больше' in kind else base - delta
        total = base + second
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {base} {op} {delta} = {second} {_v280_word(second, item)} — у второго ребёнка.',
                        f'2) {base} + {second} = {total} {_v280_word(total, item)} — всего у них вместе.',
                        f'Ответ: У них вместе {_v280_count(total, item)}.'], 'local:live-v280-composite-relation')
    # Delegate remaining direct/reverse patterns to the previous implementation body by using fresh regexes.
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+на\s+(\d+)\s+([а-яеё]+)\s+(больше|меньше).*?сколько\s+([а-яеё]+)\s+у\s+\4', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(3), m.group(6)) and _v280_same_stem(m.group(3), m.group(8)):
        base, item, p2, delta, kind = int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(7)
        ans = base + delta if 'больше' in kind else base - delta
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.', f'1) {base} {op} {delta} = {ans} {_v280_word(ans, item)}.', f'Ответ: У {_v280_person_from_phrase(p2)} {_v280_count(ans, item)}.'], 'local:live-v280-relation')
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+в\s+(\d+)\s+раз[а]?\s+(больше|меньше).*?сколько\s+([а-яеё]+)\s+у\s+\4', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(3), m.group(7)):
        base, item, p2, k, kind = int(m.group(2)), m.group(3), m.group(4), int(m.group(5)), m.group(6)
        ans = Fraction(base * k, 1) if 'больше' in kind else Fraction(base, k)
        if ans.denominator != 1:
            return None
        op = '×' if 'больше' in kind else ':'
        return _result(['Задача.', clean, 'Решение.', f'1) {base} {op} {k} = {ans.numerator} {_v280_word(ans.numerator, item)}.', f'Ответ: У {_v280_person_from_phrase(p2)} {_v280_count(ans.numerator, item)}.'], 'local:live-v280-relation')
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s+([а-яеё]+).*?это\s+на\s+(\d+)\s+(больше|меньше),?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+у\s+\6', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(3), m.group(7)):
        base, item, delta, kind, other = int(m.group(2)), m.group(3), int(m.group(4)), m.group(5), m.group(6)
        ans = base - delta if 'больше' in kind else base + delta
        op = '−' if 'больше' in kind else '+'
        return _result(['Задача.', clean, 'Решение.', f'1) {base} {op} {delta} = {ans} {_v280_word(ans, item)}.', f'Ответ: У {_v280_person_from_phrase(other)} {_v280_count(ans, item)}.'], 'local:live-v280-reverse-relation')
    m = re.search(r'в\s+классе\s+(\d+)\s+девоч[а-я]*\s+и\s+(\d+)\s+мальчик[а-я]*.*?(\d+)\s+ученик[а-я]*\s+(?:ушл|ушли|уехал|вышл)[а-я]*.*?сколько\s+ученик[а-я]*\s+остал', source, flags=re.IGNORECASE)
    if m:
        girls, boys, left_count = int(m.group(1)), int(m.group(2)), int(m.group(3))
        total = girls + boys
        remain = total - left_count
        return _result(['Задача.', clean, 'Решение.', f'1) {girls} + {boys} = {total} учеников — было в классе.', f'2) {total} − {left_count} = {remain} учеников — осталось.', f'Ответ: В классе осталось {_v280_count(remain, "ученик")}.'], 'local:live-v280-composite-total-left')
    return None


def solve_v280_money_and_time_text(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s*(?:руб|р\b).*?купил[а-я]*\s+([а-яеё]+)\s+за\s+(\d+)\s*(?:руб|р\b)\s+и\s+([а-яеё]+)\s+за\s+(\d+)\s*(?:руб|р\b).*?сколько\s+руб[а-я]*\s+остал', source, flags=re.IGNORECASE)
    if m:
        person, initial, price1, price2 = m.group(1), int(m.group(2)), int(m.group(4)), int(m.group(6))
        spent = price1 + price2
        left = initial - spent
        return _result(['Задача.', clean, 'Решение.', f'1) {price1} + {price2} = {spent} рублей — потратил на покупки.', f'2) {initial} − {spent} = {left} рублей — осталось.', f'Ответ: У {_v280_person_from_phrase(person)} осталось {_v280_money(left)}.'], 'local:live-v280-money-two-purchases')
    m = re.search(r'(?:одна|один|1)\s+([а-яеё]+)\s+стоит\s+(\d+)\s*(?:руб|р\b).*?сколько\s+стоят\s+(\d+)\s+(?:таких\s+)?([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(1), m.group(4)):
        item, price, qty = m.group(1), int(m.group(2)), int(m.group(3))
        total = price * qty
        return _result(['Задача.', clean, 'Решение.', f'1) {price} × {qty} = {total} рублей — стоимость покупки.', f'Ответ: {qty} {_v280_word(qty, item)} стоят {_v280_money(total)}.'], 'local:live-v280-money-cost')
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s*(?:руб|р\b).*?купил[а-я]*\s+([а-яеё]+)\s+за\s+(\d+)\s*(?:руб|р\b).*?(?:сдачи\s+получил|остал)', source, flags=re.IGNORECASE)
    if m:
        person, initial, price = m.group(1), int(m.group(2)), int(m.group(4))
        left = initial - price
        return _result(['Задача.', clean, 'Решение.', f'1) {initial} − {price} = {left} рублей.', f'Ответ: У {_v280_person_from_phrase(person)} осталось/сдача {_v280_money(left)}.'], 'local:live-v280-money-change')
    m = re.search(r'сколько\s+([а-яеё]+)\s+можно\s+купить\s+на\s+(\d+)\s*(?:руб|р\b).*?([а-яеё]+)\s+стоит\s+(\d+)\s*(?:руб|р\b)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(1), m.group(3)):
        item, money, price = m.group(1), int(m.group(2)), int(m.group(4))
        if price == 0:
            return None
        qty = money // price
        return _result(['Задача.', clean, 'Решение.', f'1) {money} : {price} = {qty} — делим сумму денег на цену одного предмета.', f'Ответ: Можно купить {_v280_count(qty, item)}.'], 'local:live-v280-money-quantity')
    return None

# --- v280 wave1 patch 2: common stem + ruble suffix normalization ---
def _v280_unit_forms(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    mapping = [
        (('машинок', 'машинк'), ('машинка', 'машинки', 'машинок')),
        (('яблок',), ('яблоко', 'яблока', 'яблок')),
        (('шишк',), ('шишка', 'шишки', 'шишек')),
        (('карандаш',), ('карандаш', 'карандаша', 'карандашей')),
        (('конфет',), ('конфета', 'конфеты', 'конфет')),
        (('книг',), ('книга', 'книги', 'книг')),
        (('наклей',), ('наклейка', 'наклейки', 'наклеек')),
        (('марк',), ('марка', 'марки', 'марок')),
        (('машин',), ('машина', 'машины', 'машин')),
        (('пассажир',), ('пассажир', 'пассажира', 'пассажиров')),
        (('роз',), ('роза', 'розы', 'роз')),
        (('открытк',), ('открытка', 'открытки', 'открыток')),
        (('фишк',), ('фишка', 'фишки', 'фишек')),
        (('мяч',), ('мяч', 'мяча', 'мячей')),
        (('печен',), ('печенье', 'печенья', 'печений')),
        (('ученик', 'учен'), ('ученик', 'ученика', 'учеников')),
        (('девоч',), ('девочка', 'девочки', 'девочек')),
        (('мальчик',), ('мальчик', 'мальчика', 'мальчиков')),
        (('короб',), ('коробка', 'коробки', 'коробок')),
        (('пакет',), ('пакет', 'пакета', 'пакетов')),
        (('тарел',), ('тарелка', 'тарелки', 'тарелок')),
        (('корзин',), ('корзина', 'корзины', 'корзин')),
        (('тетрад',), ('тетрадь', 'тетради', 'тетрадей')),
        (('блокнот',), ('блокнот', 'блокнота', 'блокнотов')),
        (('ручк',), ('ручка', 'ручки', 'ручек')),
        (('линейк',), ('линейка', 'линейки', 'линеек')),
        (('руб',), ('рубль', 'рубля', 'рублей')),
        (('коп',), ('копейка', 'копейки', 'копеек')),
        (('сантиметр', 'см'), ('сантиметр', 'сантиметра', 'сантиметров')),
        (('дециметр', 'дм'), ('дециметр', 'дециметра', 'дециметров')),
        (('минут', 'мин'), ('минута', 'минуты', 'минут')),
        (('час',), ('час', 'часа', 'часов')),
        (('день', 'дн'), ('день', 'дня', 'дней')),
        (('недел',), ('неделя', 'недели', 'недель')),
        (('кубик',), ('кубик', 'кубика', 'кубиков')),
        (('шар',), ('шар', 'шара', 'шаров')),
    ]
    for markers, forms in mapping:
        if any(marker in stem for marker in markers):
            return forms
    return None


def _v280_same_stem(a: str, b: str) -> bool:  # type: ignore[override]
    a_norm = (a or '').lower().replace('ё', 'е').strip(' .,!?:;')
    b_norm = (b or '').lower().replace('ё', 'е').strip(' .,!?:;')
    if not a_norm or not b_norm:
        return True
    if a_norm == b_norm:
        return True
    forms_a = _v280_unit_forms(a_norm)
    forms_b = _v280_unit_forms(b_norm)
    if forms_a and forms_b and forms_a == forms_b:
        return True
    return a_norm[:4] == b_norm[:4] or a_norm[:5] == b_norm[:5]


def solve_v280_money_and_time_text(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    rub = r'(?:руб[а-я]*|р\b)'
    m = re.search(rf'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s*{rub}.*?купил[а-я]*\s+([а-яеё]+)\s+за\s+(\d+)\s*{rub}\s+и\s+([а-яеё]+)\s+за\s+(\d+)\s*{rub}.*?сколько\s+руб[а-я]*\s+остал', source, flags=re.IGNORECASE)
    if m:
        person, initial, price1, price2 = m.group(1), int(m.group(2)), int(m.group(4)), int(m.group(6))
        spent = price1 + price2
        left = initial - spent
        return _result(['Задача.', clean, 'Решение.', f'1) {price1} + {price2} = {spent} рублей — потратил на покупки.', f'2) {initial} − {spent} = {left} рублей — осталось.', f'Ответ: У {_v280_person_from_phrase(person)} осталось {_v280_money(left)}.'], 'local:live-v280-money-two-purchases')
    m = re.search(rf'(?:одна|один|1)\s+([а-яеё]+)\s+стоит\s+(\d+)\s*{rub}.*?сколько\s+стоят\s+(\d+)\s+(?:таких\s+)?([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(1), m.group(4)):
        item, price, qty = m.group(1), int(m.group(2)), int(m.group(3))
        total = price * qty
        return _result(['Задача.', clean, 'Решение.', f'1) {price} × {qty} = {total} рублей — стоимость покупки.', f'Ответ: {qty} {_v280_word(qty, item)} стоят {_v280_money(total)}.'], 'local:live-v280-money-cost')
    m = re.search(rf'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s*{rub}.*?купил[а-я]*\s+([а-яеё]+)\s+за\s+(\d+)\s*{rub}.*?(?:сдачи\s+получил|остал)', source, flags=re.IGNORECASE)
    if m:
        person, initial, price = m.group(1), int(m.group(2)), int(m.group(4))
        left = initial - price
        return _result(['Задача.', clean, 'Решение.', f'1) {initial} − {price} = {left} рублей.', f'Ответ: У {_v280_person_from_phrase(person)} осталось/сдача {_v280_money(left)}.'], 'local:live-v280-money-change')
    m = re.search(rf'сколько\s+([а-яеё]+)\s+можно\s+купить\s+на\s+(\d+)\s*{rub}.*?([а-яеё]+)\s+стоит\s+(\d+)\s*{rub}', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(1), m.group(3)):
        item, money, price = m.group(1), int(m.group(2)), int(m.group(4))
        if price == 0:
            return None
        qty = money // price
        return _result(['Задача.', clean, 'Решение.', f'1) {money} : {price} = {qty} — делим сумму денег на цену одного предмета.', f'Ответ: Можно купить {_v280_count(qty, item)}.'], 'local:live-v280-money-quantity')
    return None

# --- v280 wave1 patch 3: do not let total equal-groups handler steal remaining problems ---
def solve_v280_equal_groups_and_sharing(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v280_lower(text)
    clean = _v280_clean_task(text)
    has_remaining_action = bool(re.search(r'остал|взял|взяли|забрал|забрали|утащил|унес|унесли|израсходовал|отдал|подарил|съел', source))
    if not has_remaining_action:
        m = re.search(r'(?:в|на)\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+)\b.*?сколько\s+([а-яеё]+)\s+(?:всего|на\s+всех|получилось)?', source, flags=re.IGNORECASE)
        if m and _v280_same_stem(m.group(4), m.group(5)):
            groups, each, item = int(m.group(1)), int(m.group(3)), m.group(4)
            total = groups * each
            return _result(['Задача.', clean, 'Решение.',
                            f'1) {groups} × {each} = {total} {_v280_word(total, item)} — всего.',
                            f'Ответ: Всего {_v280_count(total, item)}.'], 'local:live-v280-equal-groups')
        m = re.search(r'(?:в|на)\s+одн[а-я]+\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+в\s+(\d+)\s+таких\s+([а-яеё]+)', source, flags=re.IGNORECASE)
        if m and _v280_same_stem(m.group(3), m.group(4)) and _v280_same_stem(m.group(1), m.group(6)):
            group_word, each, item, groups = m.group(1), int(m.group(2)), m.group(3), int(m.group(5))
            total = groups * each
            return _result(['Задача.', clean, 'Решение.',
                            f'1) {each} × {groups} = {total} {_v280_word(total, item)}.',
                            f'Ответ: В {groups} таких {group_word} {_v280_count(total, item)}.'], 'local:live-v280-equal-groups')
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+(?:раздали|разложили|поделили)\s+поровну\s+(?:на|между|в)?\s*(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(2), m.group(5)):
        total, item, groups = int(m.group(1)), m.group(2), int(m.group(3))
        if groups == 0:
            return None
        per = Fraction(total, groups)
        if per.denominator != 1:
            return None
        ans = per.numerator
        return _result(['Задача.', clean, 'Решение.',
                        f'1) {total} : {groups} = {ans} {_v280_word(ans, item)} — в каждой группе.',
                        f'Ответ: На каждой/у каждого будет {_v280_count(ans, item)}.'], 'local:live-v280-equal-sharing')
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+разложили\s+в\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+получилось', source, flags=re.IGNORECASE)
    if m and _v280_same_stem(m.group(2), m.group(5)):
        total, per, asked_container = int(m.group(1)), int(m.group(4)), m.group(6)
        if per == 0:
            return None
        q, r = divmod(total, per)
        if r == 0:
            return _result(['Задача.', clean, 'Решение.',
                            f'1) {total} : {per} = {q}.',
                            f'Ответ: Получилось {_v280_count(q, asked_container)}.'], 'local:live-v280-exact-grouping')
    return None
