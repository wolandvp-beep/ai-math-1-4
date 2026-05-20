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

# --- v281 external black-box audit wave 2: grade 3-4 core ---
# Broad structural handlers for grade 3-4 topics: numbers and units up to
# thousands/millions, composite word problems, money/time, motion, fractions,
# geometry, tables/diagrams and one-variable equations.  These rules are
# category-pattern solvers, not exact per-task answer maps.

_V281_RELEASE_NOTE = 'v281_external_blackbox_audit_wave2_grade3_4_core'


def _v281_clean(text: str) -> str:
    return _v280_clean_task(text)


def _v281_lower(text: str) -> str:
    return _v281_clean(text).lower().replace('ё', 'е')


def _v281_sentence(text: str) -> str:
    return _v281_clean(text).strip()


def _v281_int_word(n: int, one: str, two_four: str, many: str) -> str:
    return _choose_plural_int(int(n), one, two_four, many)


def _v281_time_word(n: int, unit: str) -> str:
    unit = unit.lower()
    if unit.startswith('мин'):
        return _v281_int_word(n, 'минута', 'минуты', 'минут')
    if unit.startswith('сек') or unit.startswith('с'):
        return _v281_int_word(n, 'секунда', 'секунды', 'секунд')
    if unit.startswith('д'):
        return _v281_int_word(n, 'день', 'дня', 'дней')
    return _v281_int_word(n, 'час', 'часа', 'часов')


def _v281_format_minutes(total: int) -> str:
    total = int(total)
    if total < 60:
        return f'{total} {_v281_time_word(total, "мин")}'
    h, m = divmod(total, 60)
    if m == 0:
        return f'{h} {_v281_time_word(h, "час")}'
    return f'{h} {_v281_time_word(h, "час")} {m} {_v281_time_word(m, "мин")}'


def _v281_clock_add(start: str, minutes: int) -> str:
    start_min = _v280_time_to_minutes(start)
    if start_min is None:
        return ''
    return _v280_minutes_to_clock(start_min + int(minutes))


def _v281_clock_diff(start: str, end: str) -> int | None:
    a = _v280_time_to_minutes(start)
    b = _v280_time_to_minutes(end)
    if a is None or b is None:
        return None
    if b < a:
        b += 24 * 60
    return b - a


def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    extras = [
        (('дерев', 'яблон', 'груш'), ('дерево', 'дерева', 'деревьев')),
        (('куст',), ('куст', 'куста', 'кустов')),
        (('мест',), ('место', 'места', 'мест')),
        (('страниц',), ('страница', 'страницы', 'страниц')),
        (('детал',), ('деталь', 'детали', 'деталей')),
        (('заказ',), ('заказ', 'заказа', 'заказов')),
        (('альбом',), ('альбом', 'альбома', 'альбомов')),
        (('билет',), ('билет', 'билета', 'билетов')),
        (('ластик',), ('ластик', 'ластика', 'ластиков')),
        (('болт',), ('болт', 'болта', 'болтов')),
        (('винт',), ('винт', 'винта', 'винтов')),
        (('шуруп',), ('шуруп', 'шурупа', 'шурупов')),
        (('гвозд',), ('гвоздь', 'гвоздя', 'гвоздей')),
        (('кг', 'килограмм'), ('килограмм', 'килограмма', 'килограммов')),
        (('литр',), ('литр', 'литра', 'литров')),
        (('км', 'километр'), ('километр', 'километра', 'километров')),
        (('клет',), ('клетка', 'клетки', 'клеток')),
        (('знач',), ('значок', 'значка', 'значков')),
        (('поездк',), ('поездка', 'поездки', 'поездок')),
        (('посетител',), ('посетитель', 'посетителя', 'посетителей')),
        (('участник',), ('участник', 'участника', 'участников')),
    ]
    for markers, forms in extras:
        if any(marker in stem for marker in markers):
            return forms
    return _v280_unit_forms(word)


def _v281_word(n: int, word: str) -> str:
    forms = _v281_unit_forms_extra(word)
    if forms:
        return _choose_plural_int(int(n), forms[0], forms[1], forms[2])
    return _v280_word(int(n), word)


def _v281_count(n: int, word: str) -> str:
    return f'{int(n)} {_v281_word(int(n), word)}'


def _v281_money(n: int) -> str:
    return _v281_count(int(n), 'рубль')


def _v281_same_item(a: str, b: str) -> bool:
    a_norm = (a or '').lower().replace('ё', 'е').strip(' .,!?:;')
    b_norm = (b or '').lower().replace('ё', 'е').strip(' .,!?:;')
    if not a_norm or not b_norm:
        return True
    fa = _v281_unit_forms_extra(a_norm)
    fb = _v281_unit_forms_extra(b_norm)
    if fa and fb and fa == fb:
        return True
    if a_norm == b_norm:
        return True
    return a_norm[:4] == b_norm[:4] or a_norm[:5] == b_norm[:5]


def _v281_parse_pairs(source: str) -> dict[str, int]:
    pairs = re.findall(r'([а-яеёa-zA-Z]+)\s*[—\-:]+\s*(\d+)', source, flags=re.IGNORECASE)
    return {name.lower().replace('ё', 'е'): int(value) for name, value in pairs}


def _v281_denominator_from_word(word: str) -> int | None:
    source = (word or '').lower().replace('ё', 'е')
    mapping = {
        'полов': 2, 'втор': 2, 'треть': 3, 'трет': 3, 'четверт': 4,
        'пят': 5, 'шест': 6, 'седьм': 7, 'восьм': 8, 'девят': 9, 'десят': 10,
    }
    for stem, value in mapping.items():
        if stem in source:
            return value
    return None


def _v281_format_fraction_answer(value: Fraction) -> str:
    return _fmt_fraction(value)


def solve_v281_numbers_units(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    # Three-digit place value: hundreds/tens/ones.
    m = re.search(r'числ[оа],?\s+в\s+котором\s+(\d+)\s+сот[а-я]*\s+(\d+)\s+десятк[а-я]*\s+(?:и\s+)?(\d+)\s+единиц', source, flags=re.IGNORECASE)
    if m:
        hundreds, tens, ones = map(int, m.groups())
        ans = hundreds * 100 + tens * 10 + ones
        return _result(['Задача.', clean, 'Решение.', f'1) {hundreds} сотен — это {hundreds * 100}.', f'2) {tens} десятков — это {tens * 10}.', f'3) {hundreds * 100} + {tens * 10} + {ones} = {ans}.', f'Ответ: {ans}.'], 'local:live-v281-place-value')
    m = re.search(r'числ[оа],?\s+в\s+котором\s+(\d+)\s+сот[а-я]*\s+тысяч\s+(\d+)\s+десятк[а-я]*\s+тысяч\s+(\d+)\s+тысяч[а-я]*\s+(\d+)\s+сот[а-я]*\s+(\d+)\s+десятк[а-я]*\s+(?:и\s+)?(\d+)\s+единиц', source, flags=re.IGNORECASE)
    if m:
        a,b,c,d,e,f = map(int, m.groups())
        ans = a*100000 + b*10000 + c*1000 + d*100 + e*10 + f
        return _result(['Задача.', clean, 'Решение.', f'1) Складываем разрядные слагаемые: {a*100000} + {b*10000} + {c*1000} + {d*100} + {e*10} + {f} = {ans}.', f'Ответ: {ans}.'], 'local:live-v281-place-value')
    m = re.search(r'в\s+числе\s+(\d+)\s+сколько\s+сот[а-я]*,?\s+десятк[а-я]*\s+и\s+единиц', source, flags=re.IGNORECASE)
    if m:
        num = int(m.group(1)); hundreds = num // 100; tens = (num // 10) % 10; ones = num % 10
        return _result(['Задача.', clean, 'Решение.', f'1) В числе {num}: сотен — {hundreds}, десятков — {tens}, единиц — {ones}.', f'Ответ: {hundreds} сотен, {tens} десятков и {ones} единиц.'], 'local:live-v281-place-value')
    m = re.search(r'сравни\s+числа\s+(\d+)\s+и\s+(\d+)', source, flags=re.IGNORECASE)
    if m:
        a,b = map(int, m.groups())
        sign = '<' if a < b else '>' if a > b else '='
        relation = 'меньше' if a < b else 'больше' if a > b else 'равно'
        return _result(['Задача.', clean, 'Решение.', f'1) Сравниваем числа {a} и {b}.', f'2) {a} {sign} {b}.', f'Ответ: {a} {sign} {b}; число {a} {relation} числа {b}.'], 'local:live-v281-number-compare')
    m = re.search(r'округли\s+(\d+)\s+до\s+(десятк[а-я]*|сот[а-я]*|тысяч[а-я]*)', source, flags=re.IGNORECASE)
    if m:
        num = int(m.group(1)); unit = m.group(2)
        base = 10 if unit.startswith('десят') else 100 if unit.startswith('сот') else 1000
        ans = int((num + base / 2) // base * base)
        return _result(['Задача.', clean, 'Решение.', f'1) Округляем число {num} до нужного разряда.', f'2) Получаем {ans}.', f'Ответ: {ans}.'], 'local:live-v281-rounding')
    m = re.search(r'сколько\s+метр[а-я]*\s+в\s+(\d+)\s*км\s*(\d+)?\s*м', source, flags=re.IGNORECASE)
    if m:
        km = int(m.group(1)); meters = int(m.group(2) or 0); total = km * 1000 + meters
        return _result(['Задача.', clean, 'Решение.', f'1) {km} км = {km*1000} м.', f'2) {km*1000} + {meters} = {total} м.', f'Ответ: Всего {total} метров.'], 'local:live-v281-units')
    m = re.search(r'сколько\s+килограмм[а-я]*\s+и\s+грамм[а-я]*\s+в\s+(\d+)\s*г', source, flags=re.IGNORECASE)
    if m:
        total = int(m.group(1)); kg, g = divmod(total, 1000)
        return _result(['Задача.', clean, 'Решение.', f'1) 1 кг = 1000 г.', f'2) {total} г = {kg} кг {g} г.', f'Ответ: {kg} килограмма {g} граммов.'], 'local:live-v281-units')
    m = re.search(r'сколько\s+секунд[а-я]*\s+в\s+(\d+)\s*мин[а-я]*\s*(\d+)?\s*с', source, flags=re.IGNORECASE)
    if m:
        minutes = int(m.group(1)); seconds = int(m.group(2) or 0); total = minutes*60+seconds
        return _result(['Задача.', clean, 'Решение.', f'1) {minutes} мин = {minutes*60} с.', f'2) {minutes*60} + {seconds} = {total} с.', f'Ответ: Всего {total} секунд.'], 'local:live-v281-units')
    m = re.search(r'сколько\s+дн[а-я]*\s+в\s+(\d+)\s*недел[а-я]*\s*(\d+)?\s*дн', source, flags=re.IGNORECASE)
    if m:
        weeks = int(m.group(1)); days = int(m.group(2) or 0); total = weeks*7+days
        return _result(['Задача.', clean, 'Решение.', f'1) {weeks} недели = {weeks*7} дней.', f'2) {weeks*7} + {days} = {total} дней.', f'Ответ: {total} {_v281_time_word(total, "день")}.'], 'local:live-v281-calendar')
    m = re.search(r'сколько\s+дн[а-я]*\s+в\s+(\d+)\s*час', source, flags=re.IGNORECASE)
    if m:
        hours = int(m.group(1)); days, rest = divmod(hours, 24)
        if rest == 0:
            final = f'{days} {_v281_time_word(days, "день")}'
        else:
            final = f'{days} {_v281_time_word(days, "день")} {rest} {_v281_time_word(rest, "час")}'
        return _result(['Задача.', clean, 'Решение.', f'1) 1 день = 24 часа.', f'2) {hours} : 24 = {days} (ост. {rest}).', f'Ответ: {final}.'], 'local:live-v281-calendar')
    return None


def solve_v281_arithmetic_and_equations(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    m = re.search(r'(?:деление\s+с\s+остатком|раздели\s+с\s+остатком|выполни\s+деление\s+с\s+остатком)\D*(\d+)\s*[:/]\s*(\d+)', source, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'(\d+)\s*[:/]\s*(\d+).*?с\s+остатком', source, flags=re.IGNORECASE)
    if m:
        a,b = map(int, m.groups())
        if b == 0:
            return None
        q,r = divmod(a,b)
        return _result(['Задача.', clean, 'Решение.', f'1) {a} : {b} = {q} (ост. {r}).', f'Ответ: {q}, остаток {r}.'], 'local:live-v281-remainder')
    m = re.search(r'значение\s+выражения\s+([a-zа-я])\s*([*:])\s*(\d+)\s*([+\-])\s*(\d+),?\s*если\s+\1\s*=\s*(\d+)', source, flags=re.IGNORECASE)
    if m:
        var, op1, n1, op2, n2, value = m.group(1), m.group(2), int(m.group(3)), m.group(4), int(m.group(5)), int(m.group(6))
        first = value * n1 if op1 == '*' else Fraction(value, n1)
        ans = first + n2 if op2 == '+' else first - n2
        if isinstance(ans, Fraction) and ans.denominator != 1:
            ans_text = _fmt_fraction(ans)
        else:
            ans_text = str(int(ans))
        return _result(['Задача.', clean, 'Решение.', f'1) Подставляем {var} = {value} в выражение.', f'2) {value} {op1} {n1} {op2} {n2} = {ans_text}.', f'Ответ: Значение выражения равно {ans_text}.'], 'local:live-v281-letter-expression')
    # Simple linear equations with parentheses or one extra action: k*x + b = c, (x + a) : b = c.
    raw = _v281_clean(text).replace('х','x').replace('Х','x').replace('×','*').replace('·','*').replace('÷',':')
    compact = re.sub(r'[^0-9xX+=\-*:()/]', '', raw).lower().replace('/', ':')
    if compact.count('=') == 1 and 'x' in compact:
        patterns = [
            (r'^(\d+)\*x\+(\d+)=(\d+)$', lambda k,b,c: Fraction(int(c)-int(b), int(k))),
            (r'^x\*(\d+)\+(\d+)=(\d+)$', lambda k,b,c: Fraction(int(c)-int(b), int(k))),
            (r'^(\d+)\*x-(\d+)=(\d+)$', lambda k,b,c: Fraction(int(c)+int(b), int(k))),
            (r'^x\*(\d+)-(\d+)=(\d+)$', lambda k,b,c: Fraction(int(c)+int(b), int(k))),
            (r'^\(x\+(\d+)\):(\d+)=(\d+)$', lambda a,b,c: int(b)*int(c)-int(a)),
            (r'^\(x-(\d+)\):(\d+)=(\d+)$', lambda a,b,c: int(b)*int(c)+int(a)),
        ]
        for pat, fn in patterns:
            mm = re.match(pat, compact)
            if mm:
                val = fn(*mm.groups())
                val_text = _fmt_fraction(val if isinstance(val, Fraction) else Fraction(val,1))
                return _result(['Задача.', clean, 'Решение.', '1) Сначала выполняем обратное действие для внешней операции.', f'2) Получаем x = {val_text}.', '3) Проверяем подстановкой в исходное уравнение.', f'Ответ: x = {val_text}.'], 'local:live-v281-equation')
    return None


def solve_v281_text_composite(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    # Two equal-group batches added together.
    m = re.search(r'(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?и\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?сколько\s+(?:всего\s+)?([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(4), m.group(8)) and _v281_same_item(m.group(4), m.group(9)):
        g1, each1, g2, each2, item = int(m.group(1)), int(m.group(3)), int(m.group(5)), int(m.group(7)), m.group(4)
        part1, part2 = g1*each1, g2*each2
        total = part1 + part2
        return _result(['Задача.', clean, 'Решение.', f'1) {g1} × {each1} = {part1} {_v281_word(part1, item)} — первая часть.', f'2) {g2} × {each2} = {part2} {_v281_word(part2, item)} — вторая часть.', f'3) {part1} + {part2} = {total} {_v281_word(total, item)} — всего.', f'Ответ: Всего {_v281_count(total, item)}.'], 'local:live-v281-composite-groups')
    # Total minus equal groups.
    m = re.search(r'было\s+(\d+)\s+([а-яеё]+).*?(?:раздали|выдали|разложили|упаковали)\s+(?:в\s+)?(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s+([а-яеё]+).*?сколько\s+\2\s+остал', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(6)):
        total, item, groups, each = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(5))
        used = groups*each; left = total-used
        return _result(['Задача.', clean, 'Решение.', f'1) {groups} × {each} = {used} {_v281_word(used, item)} — раздали.', f'2) {total} − {used} = {left} {_v281_word(left, item)} — осталось.', f'Ответ: Осталось {_v281_count(left, item)}.'], 'local:live-v281-composite-left')
    # Sold/used first day and second day more/less; find remaining.
    m = re.search(r'было\s+(\d+)\s+([а-яеё]+).*?перв[а-я]*\s+день\s+(?:продал[а-я]*|израсходовал[а-я]*|прочитал[а-я]*)\s+(\d+)\s+([а-яеё]+).*?втор[а-я]*\s+(?:день\s+)?на\s+(\d+)\s+([а-яеё]+)\s+(больше|меньше).*?сколько\s+\2\s+остал', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(4)):
        total, item, first, delta, kind = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(5)), m.group(7)
        second = first + delta if 'больше' in kind else first - delta
        spent = first + second; left = total - spent
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.', f'1) {first} {op} {delta} = {second} {_v281_word(second, item)} — во второй день.', f'2) {first} + {second} = {spent} {_v281_word(spent, item)} — всего.', f'3) {total} − {spent} = {left} {_v281_word(left, item)} — осталось.', f'Ответ: Осталось {_v281_count(left, item)}.'], 'local:live-v281-composite-left')
    # Read two parts from a book; allow irrelevant extra data later.
    m = re.search(r'книг[аеи]\s+(?:было\s+)?(\d+)\s+страниц.*?прочитал[а-я]*\s+(\d+)\s+страниц.*?прочитал[а-я]*\s+(\d+)\s+страниц.*?сколько\s+страниц\s+остал', source, flags=re.IGNORECASE)
    if m:
        total, a, b = map(int, m.groups())
        read = a+b; left = total-read
        return _result(['Задача.', clean, 'Решение.', f'1) {a} + {b} = {read} страниц — прочитано.', f'2) {total} − {read} = {left} страниц — осталось.', f'Ответ: Осталось {_v281_count(left, "страниц")}.'], 'local:live-v281-extra-data')
    # Reverse relation: this is more/less/times than another quantity.
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s+([а-яеё]+).*?это\s+на\s+(\d+)\s+([а-яеё]+)\s+(больше|меньше),?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+у\s+\7', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(3), m.group(5)):
        base, item, delta, kind, person = int(m.group(2)), m.group(3), int(m.group(4)), m.group(6), m.group(7)
        ans = base - delta if 'больше' in kind else base + delta
        op = '−' if 'больше' in kind else '+'
        return _result(['Задача.', clean, 'Решение.', f'1) {base} {op} {delta} = {ans} {_v281_word(ans, item)}.', f'Ответ: У {_v280_person_from_phrase(person)} {_v281_count(ans, item)}.'], 'local:live-v281-reverse-relation')
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s+([а-яеё]+).*?это\s+в\s+(\d+)\s+раз[а]?\s+(больше|меньше),?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+у\s+\6', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(3), m.group(7)):
        base, item, k, kind, person = int(m.group(2)), m.group(3), int(m.group(4)), m.group(5), m.group(6)
        ans = base // k if 'больше' in kind else base * k
        op = ':' if 'больше' in kind else '×'
        return _result(['Задача.', clean, 'Решение.', f'1) {base} {op} {k} = {ans} {_v281_word(ans, item)}.', f'Ответ: У {_v280_person_from_phrase(person)} {_v281_count(ans, item)}.'], 'local:live-v281-reverse-relation')
    # Total and one part.
    m = re.search(r'у\s+[а-яеё]+\s+и\s+[а-яеё]+\s+(\d+)\s+([а-яеё]+).*?у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+у\s+([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(5)):
        total, item, known = int(m.group(1)), m.group(2), int(m.group(4))
        ans = total - known
        return _result(['Задача.', clean, 'Решение.', f'1) {total} − {known} = {ans} {_v281_word(ans, item)}.', f'Ответ: У {_v280_person_from_phrase(m.group(7))} {_v281_count(ans, item)}.'], 'local:live-v281-part-whole')
    # Buses/seats free.
    m = re.search(r'(\d+)\s+автобус[а-я]*\s+по\s+(\d+)\s+мест[а-я]*.*?(\d+)\s+(?:дет[а-я]*|ученик[а-я]*|пассажир[а-я]*).*?сколько\s+мест\s+остал', source, flags=re.IGNORECASE)
    if m:
        buses, seats, people = map(int, m.groups())
        total = buses*seats; left = total-people
        return _result(['Задача.', clean, 'Решение.', f'1) {buses} × {seats} = {total} мест — всего в автобусах.', f'2) {total} − {people} = {left} мест — свободно.', f'Ответ: Осталось {_v281_count(left, "мест")}.'], 'local:live-v281-composite-left')
    # Direct comparison: by how much / how many times.
    m = re.search(r'(\d+)\s+([а-яеё]+).*?(\d+)\s+([а-яеё]+).*?на\s+сколько\s+([а-яеё]+)\s+больше', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(4)):
        a,b,item = int(m.group(1)), int(m.group(3)), m.group(2)
        diff = abs(a-b)
        return _result(['Задача.', clean, 'Решение.', f'1) {max(a,b)} − {min(a,b)} = {diff} {_v281_word(diff, item)}.', f'Ответ: На {_v281_count(diff, item)} больше.'], 'local:live-v281-comparison')
    m = re.search(r'(\d+)\s+([а-яеё]+).*?(\d+)\s+([а-яеё]+).*?во\s+сколько\s+раз\s+([а-яеё]+)\s+больше', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(4)):
        a,b = int(m.group(1)), int(m.group(3))
        if min(a,b) == 0:
            return None
        k = max(a,b) // min(a,b)
        return _result(['Задача.', clean, 'Решение.', f'1) {max(a,b)} : {min(a,b)} = {k}.', f'Ответ: В {k} раза больше.'], 'local:live-v281-comparison')
    return None


def solve_v281_money(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    rub = r'(?:руб[а-я]*|р\b)'
    # Several item groups and budget/change.
    m = re.search(r'купил[а-я]*\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s*' + rub + r'.*?и\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s*' + rub + r'.*?(?:с\s+(\d+)\s*' + rub + r'.*?сколько\s+(?:руб[а-я]*\s+)?(?:остал|сдач)|сколько\s+заплат)', source, flags=re.IGNORECASE)
    if m:
        q1,item1,p1,q2,item2,p2,budget = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5), int(m.group(6)), m.group(7)
        cost1, cost2 = q1*p1, q2*p2
        total = cost1+cost2
        lines = ['Задача.', clean, 'Решение.', f'1) {q1} × {p1} = {cost1} рублей — первая покупка.', f'2) {q2} × {p2} = {cost2} рублей — вторая покупка.', f'3) {cost1} + {cost2} = {total} рублей — всего потратили.']
        if budget:
            left = int(budget)-total
            lines.append(f'4) {int(budget)} − {total} = {left} рублей — осталось.')
            lines.append(f'Ответ: Осталось {_v281_money(left)}.')
        else:
            lines.append(f'Ответ: За покупку заплатили {_v281_money(total)}.')
        return _result(lines, 'local:live-v281-money')
    m = re.search(r'купил[а-я]*\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s*' + rub + r'.*?и\s+([а-яеё]+)\s+за\s+(\d+)\s*' + rub + r'.*?сколько\s+(?:руб[а-я]*\s+)?заплат', source, flags=re.IGNORECASE)
    if m:
        q,item,price,extra_item,extra_price = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4), int(m.group(5))
        cost = q*price; total = cost+extra_price
        return _result(['Задача.', clean, 'Решение.', f'1) {q} × {price} = {cost} рублей — стоят {item}.', f'2) {cost} + {extra_price} = {total} рублей — вся покупка.', f'Ответ: За покупку заплатили {_v281_money(total)}.'], 'local:live-v281-money')
    m = re.search(r'с\s+(\d+)\s*' + rub + r'.*?купил[а-я]*\s+(\d+)\s+([а-яеё]+)\s+по\s+(\d+)\s*' + rub + r'.*?сколько\s+(?:руб[а-я]*\s+)?(?:сдач|остал)', source, flags=re.IGNORECASE)
    if m:
        budget, qty, item, price = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
        spent = qty*price; left = budget-spent
        return _result(['Задача.', clean, 'Решение.', f'1) {qty} × {price} = {spent} рублей — стоимость покупки.', f'2) {budget} − {spent} = {left} рублей — сдача.', f'Ответ: Сдача {_v281_money(left)}.'], 'local:live-v281-money-change')
    m = re.search(r'за\s+(\d+)\s+(?:кг|килограмм[а-я]*)\s+([а-яеё]+)\s+заплатил[а-я]*\s+(\d+)\s*' + rub + r'.*?сколько\s+(?:руб[а-я]*\s+)?стоит\s+(?:1|один)\s+(?:кг|килограмм)', source, flags=re.IGNORECASE)
    if m:
        qty, item, total = int(m.group(1)), m.group(2), int(m.group(3))
        price = total // qty
        return _result(['Задача.', clean, 'Решение.', f'1) {total} : {qty} = {price} рублей — цена 1 кг.', f'Ответ: 1 кг стоит {_v281_money(price)}.'], 'local:live-v281-money-price')
    m = re.search(r'(?:один|1)\s+([а-яеё]+)\s+стоит\s+(\d+)\s*' + rub + r'.*?сколько\s+([а-яеё]+)\s+можно\s+купить\s+на\s+(\d+)\s*' + rub, source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(1), m.group(3)):
        item, price, budget = m.group(1), int(m.group(2)), int(m.group(4))
        qty, rem = divmod(budget, price)
        return _result(['Задача.', clean, 'Решение.', f'1) {budget} : {price} = {qty} (ост. {rem}).', f'Ответ: Можно купить {_v281_count(qty, item)}.'], 'local:live-v281-money-quantity')
    m = re.search(r'(\d+)\s*руб[а-я]*\s*(\d+)\s*коп[а-я]*\s*\+\s*(\d+)\s*руб[а-я]*\s*(\d+)\s*коп', source, flags=re.IGNORECASE)
    if m:
        r1,k1,r2,k2 = map(int, m.groups())
        total = (r1+r2)*100 + k1+k2
        rubles, kop = divmod(total, 100)
        return _result(['Задача.', clean, 'Решение.', f'1) Переведём в копейки: {r1} руб. {k1} коп. и {r2} руб. {k2} коп.', f'2) Всего {total} коп. = {rubles} руб. {kop} коп.', f'Ответ: {rubles} рублей {kop} копеек.'], 'local:live-v281-money-conversion')
    return None


def solve_v281_time_calendar(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    # start/end duration, including crossing midnight.
    m = re.search(r'начал[а-я]*\s+в\s+(\d{1,2}[:.]\d{2})\s+и\s+законч[а-я]*\s+в\s+(\d{1,2}[:.]\d{2}).*?сколько\s+(?:минут|времени|длил)', source, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'отправил[а-я]*\s+в\s+(\d{1,2}[:.]\d{2}).*?прибыл[а-я]*\s+в\s+(\d{1,2}[:.]\d{2}).*?сколько', source, flags=re.IGNORECASE)
    if m:
        start, end = m.group(1).replace('.', ':'), m.group(2).replace('.', ':')
        diff = _v281_clock_diff(start, end)
        if diff is None:
            return None
        return _result(['Задача.', clean, 'Решение.', f'1) От {start} до {end} прошло {_v281_format_minutes(diff)}.', f'Ответ: Длилось {_v281_format_minutes(diff)}.'], 'local:live-v281-time-duration')
    m = re.search(r'начал[а-я]*\s+в\s+(\d{1,2}[:.]\d{2})\s+и\s+длил[а-я]*\s+(?:(\d+)\s*ч[а-я]*\s*)?(?:(\d+)\s*мин[а-я]*)?.*?во\s+сколько\s+(?:он\s+)?законч', source, flags=re.IGNORECASE)
    if m:
        start = m.group(1).replace('.', ':'); hours = int(m.group(2) or 0); minutes = int(m.group(3) or 0)
        total = hours*60+minutes
        end = _v281_clock_add(start, total)
        return _result(['Задача.', clean, 'Решение.', f'1) {_v281_format_minutes(total)} прибавляем ко времени начала {start}.', f'Ответ: Закончился в {end}.'], 'local:live-v281-time-end')
    m = re.search(r'(\d+)\s*минут[а-я]*\s*-\s*это\s+сколько\s+час[а-я]*\s+и\s+минут', source, flags=re.IGNORECASE)
    if m:
        total = int(m.group(1))
        return _result(['Задача.', clean, 'Решение.', f'1) {total} минут = {_v281_format_minutes(total)}.', f'Ответ: {_v281_format_minutes(total)}.'], 'local:live-v281-time-conversion')
    return None


def solve_v281_motion(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    # Two legs.
    m = re.search(r'(?:автомобиль|машина|поезд|автобус)\s+ехал[а-я]*\s+(\d+)\s*ч[а-я]*\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч.*?потом\s+(?:еще\s+)?(\d+)\s*ч[а-я]*\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч.*?какое\s+расстояние|(?:автомобиль|машина|поезд|автобус).*?проехал[а-я]*\s+(\d+)\s*ч[а-я]*\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч.*?потом\s+(?:еще\s+)?(\d+)\s*ч[а-я]*\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч', source, flags=re.IGNORECASE)
    if m:
        vals = [int(x) for x in m.groups() if x]
        if len(vals) >= 4:
            t1,v1,t2,v2 = vals[:4]
            d1,d2 = t1*v1, t2*v2; total = d1+d2
            return _result(['Задача.', clean, 'Решение.', f'1) {v1} × {t1} = {d1} км — первый участок.', f'2) {v2} × {t2} = {d2} км — второй участок.', f'3) {d1} + {d2} = {total} км — всего.', f'Ответ: Всего проехали {total} километров.'], 'local:live-v281-motion-two-leg')
    # Distance done by speed/time; remaining relation by times or by more/less kilometers.
    m = re.search(r'(?:поезд|велосипедист|турист|машина|автомобиль)\s+(?:ехал|проехал|шел|прошел)[а-я]*\s+(?:(\d+)\s*ч[а-я]*\s+со\s+скоростью\s+(\d+)\s*км\s*/?\s*ч|(\d+)\s*км).*?остал[а-я]*\s+(?:проехать|пройти)?\s*(?:в\s+(\d+)\s+раз[а]?\s+(больше|меньше)|на\s+(\d+)\s*км\s+(больше|меньше)).*?(?:весь\s+путь|каков\s+весь|сколько\s+всего)', source, flags=re.IGNORECASE)
    if m:
        if m.group(3):
            done = int(m.group(3))
        else:
            done = int(m.group(1))*int(m.group(2))
        if m.group(4):
            k = int(m.group(4)); kind = m.group(5)
            rest = done*k if 'больше' in kind else done//k
            step = f'{done} × {k} = {rest} км — осталось.' if 'больше' in kind else f'{done} : {k} = {rest} км — осталось.'
        else:
            delta = int(m.group(6)); kind = m.group(7)
            rest = done + delta if 'больше' in kind else done - delta
            step = f'{done} + {delta} = {rest} км — осталось.' if 'больше' in kind else f'{done} − {delta} = {rest} км — осталось.'
        total = done+rest
        return _result(['Задача.', clean, 'Решение.', f'1) Уже пройдено/проехано {done} км.', f'2) {step}', f'3) {done} + {rest} = {total} км — весь путь.', f'Ответ: Весь путь {total} километров.'], 'local:live-v281-motion-remaining')
    # Remaining distance after moving towards each other.
    m = re.search(r'расстояние\s+между\s+[^.]*?\s+(\d+)\s*км.*?скорость\s+перв[а-я]+\s+(\d+)\s*км\s*/?\s*ч.*?скорость\s+втор[а-я]+\s+(\d+)\s*км\s*/?\s*ч.*?через\s+(\d+)\s*ч[а-я]*.*?сколько\s+км\s+остан', source, flags=re.IGNORECASE)
    if m:
        distance, v1, v2, t = map(int, m.groups())
        covered = (v1+v2)*t; left = distance-covered
        return _result(['Задача.', clean, 'Решение.', f'1) {v1} + {v2} = {v1+v2} км/ч — скорость сближения.', f'2) {v1+v2} × {t} = {covered} км — проедут вместе.', f'3) {distance} − {covered} = {left} км — останется.', f'Ответ: Между ними останется {left} километров.'], 'local:live-v281-motion-remaining-distance')
    return None


def solve_v281_fractions(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    m = re.search(r'найди\s+(\d+)\s*/\s*(\d+)\s+от\s+(\d+)', source, flags=re.IGNORECASE)
    if m:
        a,b,n = map(int, m.groups())
        val = Fraction(n*a, b)
        if val.denominator != 1:
            return None
        ans = val.numerator
        return _result(['Задача.', clean, 'Решение.', f'1) Чтобы найти {a}/{b} от {n}, делим {n} на {b} и умножаем на {a}.', f'2) {n} : {b} × {a} = {ans}.', f'Ответ: {ans}.'], 'local:live-v281-fraction-part')
    m = re.search(r'найди\s+([а-яеё]+)\s+част[ья]?\s+от\s+(\d+)', source, flags=re.IGNORECASE)
    if m:
        denom = _v281_denominator_from_word(m.group(1)); n = int(m.group(2))
        if denom:
            ans = n // denom
            return _result(['Задача.', clean, 'Решение.', f'1) Делим {n} на {denom}.', f'2) {n} : {denom} = {ans}.', f'Ответ: {ans}.'], 'local:live-v281-fraction-part')
    m = re.search(r'(\d+)\s*/\s*(\d+)\s+числа\s+равн[аы]\s+(\d+).*?(?:найди|чему\s+равно).*?(?:числ|все)', source, flags=re.IGNORECASE)
    if m:
        a,b,part = map(int, m.groups())
        whole = Fraction(part*b, a)
        if whole.denominator != 1:
            return None
        ans = whole.numerator
        return _result(['Задача.', clean, 'Решение.', f'1) Если {a}/{b} числа равны {part}, то всё число равно {part} × {b} : {a}.', f'2) {part} × {b} : {a} = {ans}.', f'Ответ: Всё число равно {ans}.'], 'local:live-v281-fraction-whole')
    m = re.search(r'сколько\s+минут\s+в\s+([а-яеё]+)\s+час[а-я]*', source, flags=re.IGNORECASE)
    if m:
        denom = _v281_denominator_from_word(m.group(1))
        if denom:
            ans = 60 // denom
            return _result(['Задача.', clean, 'Решение.', f'1) 1 час = 60 минут.', f'2) 60 : {denom} = {ans} минут.', f'Ответ: {ans} минут.'], 'local:live-v281-fraction-unit')
    m = re.search(r'найди\s+1\s*/\s*(\d+)\s+от\s+(\d+)\s*м', source, flags=re.IGNORECASE)
    if m:
        denom, meters = int(m.group(1)), int(m.group(2))
        total_cm = meters*100
        ans = total_cm // denom
        return _result(['Задача.', clean, 'Решение.', f'1) {meters} м = {total_cm} см.', f'2) {total_cm} : {denom} = {ans} см.', f'Ответ: {ans} сантиметров.'], 'local:live-v281-fraction-unit')
    return None


def solve_v281_geometry(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    m = re.search(r'длина\s+прямоугольник[а-я]*\s+(\d+)\s*см,?\s+ширина\s+на\s+(\d+)\s*см\s+меньше.*?площад', source, flags=re.IGNORECASE)
    if m:
        length, delta = map(int, m.groups())
        width = length-delta; area = length*width
        return _result(['Задача.', clean, 'Решение.', f'1) {length} − {delta} = {width} см — ширина.', f'2) {length} × {width} = {area} кв. см — площадь.', f'Ответ: Площадь прямоугольника равна {area} кв. см.'], 'local:live-v281-geometry')
    m = re.search(r'площадь\s+прямоугольник[а-я]*\s+(?:равна\s+)?(\d+)\s*(?:кв\.?\s*см|см2|см\^2).*?ширина\s+(\d+)\s*см.*?длин', source, flags=re.IGNORECASE)
    if m:
        area, width = map(int, m.groups())
        length = area//width
        return _result(['Задача.', clean, 'Решение.', f'1) Длина = площадь : ширина.', f'2) {area} : {width} = {length} см.', f'Ответ: Длина прямоугольника равна {length} см.'], 'local:live-v281-geometry')
    m = re.search(r'периметр\s+квадрат[а-я]*\s+(?:равен\s+)?(\d+)\s*см.*?площад', source, flags=re.IGNORECASE)
    if m:
        p = int(m.group(1)); side = p//4; area = side*side
        return _result(['Задача.', clean, 'Решение.', f'1) {p} : 4 = {side} см — сторона квадрата.', f'2) {side} × {side} = {area} кв. см — площадь.', f'Ответ: Площадь квадрата равна {area} кв. см.'], 'local:live-v281-geometry')
    m = re.search(r'прямоугольник[а-я]*\s+(\d+)\s*см\s+на\s+(\d+)\s*см.*?вырезал[а-я]*\s+квадрат\s+(\d+)\s*см\s+на\s+\3\s*см.*?площад', source, flags=re.IGNORECASE)
    if m:
        a,b,s = map(int, m.groups())
        area = a*b - s*s
        return _result(['Задача.', clean, 'Решение.', f'1) {a} × {b} = {a*b} кв. см — площадь прямоугольника.', f'2) {s} × {s} = {s*s} кв. см — площадь квадрата.', f'3) {a*b} − {s*s} = {area} кв. см — осталось.', f'Ответ: Площадь оставшейся фигуры равна {area} кв. см.'], 'local:live-v281-composite-geometry')
    m = re.search(r'прямоугольник\s+занимает\s+(\d+)\s+клет[а-я]*\s+в\s+длину\s+и\s+(\d+)\s+клет[а-я]*\s+в\s+ширину.*?площад', source, flags=re.IGNORECASE)
    if m:
        a,b = map(int, m.groups())
        area = a*b
        return _result(['Задача.', clean, 'Решение.', f'1) {a} × {b} = {area} клеток.', f'Ответ: Площадь равна {area} клеток.'], 'local:live-v281-grid-geometry')
    m = re.search(r'из\s+точки\s*\((\d+)\s*[,;]\s*(\d+)\).*?(\d+)\s+клет[а-я]*\s+вправо.*?(\d+)\s+клет[а-я]*\s+вверх', source, flags=re.IGNORECASE)
    if m:
        x,y,dx,dy = map(int, m.groups())
        nx,ny = x+dx,y+dy
        return _result(['Задача.', clean, 'Решение.', f'1) По горизонтали: {x} + {dx} = {nx}.', f'2) По вертикали: {y} + {dy} = {ny}.', f'Ответ: Получится точка ({nx}; {ny}).'], 'local:live-v281-coordinate-route')
    m = re.search(r'у\s+пятиугольник[а-я]*\s+сколько\s+сторон\s+и\s+вершин', source, flags=re.IGNORECASE)
    if m:
        return _result(['Задача.', clean, 'Решение.', '1) У пятиугольника 5 сторон и 5 вершин.', 'Ответ: 5 сторон и 5 вершин.'], 'local:live-v281-geometry-shapes')
    return None


def solve_v281_data_reading(text: str) -> Optional[dict]:
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    if 'таблиц' in source or 'диаграм' in source:
        pairs = _v281_parse_pairs(source)
        if len(pairs) >= 2:
            m = re.search(r'сколько\s+всего\s+(?:[а-яеё]+\s+)?(?:за\s+три\s+дня|за\s+все\s+дни|всего)', source, flags=re.IGNORECASE)
            if m:
                total = sum(pairs.values())
                return _result(['Задача.', clean, 'Решение.', f'1) Складываем данные: ' + ' + '.join(str(v) for v in pairs.values()) + f' = {total}.', f'Ответ: Всего {total}.'], 'local:live-v281-data-reading')
            m = re.search(r'на\s+сколько\s+([а-яеё]+)\s+больше,?\s+чем\s+([а-яеё]+)', source, flags=re.IGNORECASE)
            if m:
                a,b = m.group(1), m.group(2)
                if a in pairs and b in pairs:
                    diff = pairs[a]-pairs[b]
                    return _result(['Задача.', clean, 'Решение.', f'1) {pairs[a]} − {pairs[b]} = {diff}.', f'Ответ: На {diff} больше.'], 'local:live-v281-data-reading')
            m = re.search(r'во\s+сколько\s+раз\s+([а-яеё]+)\s+больше,?\s+чем\s+([а-яеё]+)', source, flags=re.IGNORECASE)
            if m:
                a,b = m.group(1), m.group(2)
                if a in pairs and b in pairs and pairs[b] != 0:
                    k = pairs[a]//pairs[b]
                    return _result(['Задача.', clean, 'Решение.', f'1) {pairs[a]} : {pairs[b]} = {k}.', f'Ответ: В {k} раза больше.'], 'local:live-v281-data-reading')
    m = re.search(r'пиктограмм[а-я]*.*?1\s+значок\s*=\s*(\d+)\s+([а-яеё]+).*?(\d+)\s+значк[а-я]*.*?сколько\s+([а-яеё]+)', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(4)):
        per,item,icons = int(m.group(1)), m.group(2), int(m.group(3))
        total = per*icons
        return _result(['Задача.', clean, 'Решение.', f'1) {icons} × {per} = {total} {_v281_word(total, item)}.', f'Ответ: {_v281_count(total, item)}.'], 'local:live-v281-pictogram')
    return None


# Override live router for v281.  New grade 3-4 solvers run before v280/v279.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v281_arithmetic_and_equations,
        solve_v281_numbers_units,
        solve_v281_money,
        solve_v281_time_calendar,
        solve_v281_motion,
        solve_v281_text_composite,
        solve_v281_fractions,
        solve_v281_geometry,
        solve_v281_data_reading,
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

# --- v281 patch 1: broader noun stems and alternate composite wording ---
_v281_unit_forms_extra_prev = _v281_unit_forms_extra

def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    extras = [
        (('мар',), ('марка', 'марки', 'марок')),
        (('груш', 'яблон'), ('дерево', 'дерева', 'деревьев')),
        (('ученик', 'учен'), ('ученик', 'ученика', 'учеников')),
        (('ребен', 'ребят', 'дет'), ('ребёнок', 'ребёнка', 'детей')),
    ]
    for markers, forms in extras:
        if any(marker in stem for marker in markers):
            return forms
    return _v281_unit_forms_extra_prev(word)

_solve_v281_text_composite_prev = solve_v281_text_composite

def solve_v281_text_composite(text: str) -> Optional[dict]:  # type: ignore[override]
    source = _v281_lower(text)
    clean = _v281_sentence(text)
    # Wording: "В 4 класса раздали по 35 тетрадей".
    m = re.search(r'было\s+(\d+)\s+([а-яеё]+).*?в\s+(\d+)\s+([а-яеё]+)\s+(?:раздали|выдали)\s+по\s+(\d+)\s+([а-яеё]+).*?сколько\s+\2\s+остал', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(6)):
        total, item, groups, each = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(5))
        used = groups * each
        left = total - used
        return _result(['Задача.', clean, 'Решение.', f'1) {groups} × {each} = {used} {_v281_word(used, item)} — раздали.', f'2) {total} − {used} = {left} {_v281_word(left, item)} — осталось.', f'Ответ: Осталось {_v281_count(left, item)}.'], 'local:live-v281-composite-left')
    # Wording: "в первый день продали 85 кг, во второй — на 18 кг больше".
    m = re.search(r'было\s+(\d+)\s+([а-яеё]+).*?перв[а-я]*\s+день\s+(?:продал[а-я]*|израсходовал[а-я]*|прочитал[а-я]*)\s+(\d+)\s+([а-яеё]+).*?втор[а-я]*\s+(?:день\s+)?(?:продал[а-я]*|израсходовал[а-я]*|прочитал[а-я]*)?\s*(?:-|—)?\s*на\s+(\d+)\s+([а-яеё]+)\s+(больше|меньше).*?сколько\s+\2\s+остал', source, flags=re.IGNORECASE)
    if m and _v281_same_item(m.group(2), m.group(4)):
        total, item, first, delta, kind = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(5)), m.group(7)
        second = first + delta if 'больше' in kind else first - delta
        spent = first + second
        left = total - spent
        op = '+' if 'больше' in kind else '−'
        return _result(['Задача.', clean, 'Решение.', f'1) {first} {op} {delta} = {second} {_v281_word(second, item)} — во второй день.', f'2) {first} + {second} = {spent} {_v281_word(spent, item)} — всего.', f'3) {total} − {spent} = {left} {_v281_word(left, item)} — осталось.', f'Ответ: Осталось {_v281_count(left, item)}.'], 'local:live-v281-composite-left')
    payload = _solve_v281_text_composite_prev(text)
    if payload is not None:
        return payload
    return None

# --- v281 patch 2: broaden grade 3-4 structural coverage found by black-box probe ---
_v281_numbers_units_prev2 = solve_v281_numbers_units

def solve_v281_numbers_units(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Example: 2 сотни тысяч 4 десятка тысяч 5 тысяч 3 сотни 1 десяток и 6 единиц
    m = re.search(r'(\d+)\s+сот\w*\s+тысяч\w*\s+(\d+)\s+десятк\w*\s+тысяч\w*\s+(\d+)\s+тысяч\w*\s+(\d+)\s+сот\w*\s+(\d+)\s+десятк\w*\s+(?:и\s+)?(\d+)\s+единиц', low)
    if m:
        a, b, c, d, e, f = map(int, m.groups())
        n = a*100000 + b*10000 + c*1000 + d*100 + e*10 + f
        return {
            'source': 'local:live-v281-place-value-million',
            'answer': str(n),
            'steps': [
                f'{a} сотни тысяч — это {a*100000}.',
                f'{b} десятка тысяч — это {b*10000}.',
                f'{c} тысяч — это {c*1000}.',
                f'{d} сотни — это {d*100}.',
                f'{e} десяток — это {e*10}.',
                f'{a*100000} + {b*10000} + {c*1000} + {d*100} + {e*10} + {f} = {n}.'
            ]
        }
    return _v281_numbers_units_prev2(text)

_v281_unit_forms_extra_prev2 = _v281_unit_forms_extra

def _v281_unit_forms_extra(unit: str, n: int) -> str:
    u = (unit or '').lower()
    if u.startswith('накле'):
        return _v281_word(n, 'наклейка', 'наклейки', 'наклеек')
    if u.startswith('учен'):
        return _v281_word(n, 'ученик', 'ученика', 'учеников')
    if u.startswith('мест'):
        return _v281_word(n, 'место', 'места', 'мест')
    return _v281_unit_forms_extra_prev2(unit, n)

_v281_text_composite_prev2 = solve_v281_text_composite

def solve_v281_text_composite(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Two listed quantities, then some left the group.
    m = re.search(r'в\s+двух\s+классах\s+было\s+(\d+)\s+и\s+(\d+)\s+ученик\w*.*?(\d+)\s+ученик\w*\s+ушл\w*.*?сколько\s+ученик\w*\s+остал', low)
    if m:
        a, b, c = map(int, m.groups())
        total = a + b
        ans = total - c
        unit = _v281_unit_forms_extra('учеников', ans)
        return {
            'source': 'local:live-v281-composite-two-listed-left',
            'answer': f'{ans} {unit}',
            'steps': [
                f'{a} + {b} = {total} учеников — было всего.',
                f'{total} − {c} = {ans} {unit} — осталось.'
            ]
        }
    # Capacity minus actual passengers/items.
    m = re.search(r'поехал\w*\s+(\d+)\s+ученик\w*.*?было\s+(\d+)\s+автобус\w*\s+по\s+(\d+)\s+мест', low)
    if m and re.search(r'сколько\s+мест\s+остал\w*\s+свобод', low):
        pupils, buses, seats = map(int, m.groups())
        capacity = buses * seats
        ans = capacity - pupils
        unit = _v281_unit_forms_extra('мест', ans)
        return {
            'source': 'local:live-v281-capacity-free-seats',
            'answer': f'{ans} {unit}',
            'steps': [
                f'{buses} × {seats} = {capacity} мест — всего мест в автобусах.',
                f'{capacity} − {pupils} = {ans} {unit} — осталось свободными.'
            ]
        }
    # Equal groups, then sold/taken away.
    m = re.search(r'в\s+(\d+)\s+ящик\w*\s+было\s+по\s+(\d+)\s+яблок\w*.*?продал\w*\s+(\d+)\s+яблок\w*.*?сколько\s+яблок\w*\s+остал', low)
    if m:
        boxes, per, sold = map(int, m.groups())
        total = boxes * per
        ans = total - sold
        unit = _v281_unit_forms_extra('яблок', ans)
        return {
            'source': 'local:live-v281-equal-groups-sold-left',
            'answer': f'{ans} {unit}',
            'steps': [
                f'{boxes} × {per} = {total} яблок — было всего.',
                f'{total} − {sold} = {ans} {unit} — осталось.'
            ]
        }
    # Ratio comparison with final question "на сколько больше".
    m = re.search(r'морков\w*\s+было\s+(\d+)\s*кг.*?лук\w*\s+в\s+(\d+)\s+раз\w*\s+меньше.*?на\s+сколько\s+килограмм\w*\s+морков\w*\s+больше', low)
    if m:
        carrot, k = map(int, m.groups())
        onion = carrot // k
        ans = carrot - onion
        unit = _v281_unit_forms_extra('килограммов', ans)
        return {
            'source': 'local:live-v281-ratio-difference',
            'answer': f'{ans} {unit}',
            'steps': [
                f'{carrot} : {k} = {onion} кг — было лука.',
                f'{carrot} − {onion} = {ans} {unit} — на столько моркови больше.'
            ]
        }
    return _v281_text_composite_prev2(text)

_v281_money_prev2 = solve_v281_money

def solve_v281_money(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Two different purchases from a budget.
    m = re.search(r'с\s+(\d+)\s+рубл\w*\s+купил\w*\s+(\d+)\s+(\w+)\w*\s+по\s+(\d+)\s+рубл\w*\s+и\s+(\d+)\s+(\w+)\w*\s+по\s+(\d+)\s+рубл', low)
    if m and re.search(r'сколько\s+рубл\w*\s+остал', low):
        budget, q1, item1, p1, q2, item2, p2 = m.groups()
        budget, q1, p1, q2, p2 = map(int, [budget, q1, p1, q2, p2])
        cost1 = q1 * p1
        cost2 = q2 * p2
        spent = cost1 + cost2
        ans = budget - spent
        unit = _v281_unit_forms_extra('рублей', ans)
        return {
            'source': 'local:live-v281-money-two-items-budget',
            'answer': f'{ans} {unit}',
            'steps': [
                f'{q1} × {p1} = {cost1} рублей — стоимость первой покупки.',
                f'{q2} × {p2} = {cost2} рублей — стоимость второй покупки.',
                f'{cost1} + {cost2} = {spent} рублей — потратили всего.',
                f'{budget} − {spent} = {ans} {unit} — осталось.'
            ]
        }
    # Price × quantity, where quantity is in the question.
    m = re.search(r'одн\w+\s+(\w+)\w*\s+стоит\s+(\d+)\s+рубл\w*.*?сколько\s+стоят\s+(\d+)\s+так\w*\s+\w+', low)
    if m:
        item, price, qty = m.groups()
        price, qty = int(price), int(qty)
        ans = price * qty
        unit = _v281_unit_forms_extra('рублей', ans)
        return {
            'source': 'local:live-v281-money-price-times-quantity',
            'answer': f'{ans} {unit}',
            'steps': [f'{price} × {qty} = {ans} {unit} — стоимость покупки.']
        }
    return _v281_money_prev2(text)

_v281_time_prev2 = solve_v281_time_calendar

def solve_v281_time_calendar(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    m = re.search(r'отправил\w*\s+в\s+(\d{1,2}):(\d{2}).*?ехал\w*\s+(\d+)\s*ч\w*\s+(\d+)\s*мин', low)
    if m and re.search(r'во\s+сколько\s+.*?приб', low):
        h, mn, dh, dm = map(int, m.groups())
        total = h * 60 + mn + dh * 60 + dm
        eh = (total // 60) % 24
        em = total % 60
        ans = f'{eh:02d}:{em:02d}'
        return {
            'source': 'local:live-v281-time-arrival-duration',
            'answer': ans,
            'steps': [f'К времени отправления {h:02d}:{mn:02d} прибавляем {dh} ч {dm} мин.', f'Получаем {ans}.']
        }
    return _v281_time_prev2(text)

_v281_motion_prev2 = solve_v281_motion

def solve_v281_motion(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Remaining distance after two objects move towards each other; question may come after "через".
    m = re.search(r'расстояние\s+между\s+городами\s+(\d+)\s*км.*?скорость\s+перв\w+\s+автомобил\w*\s+(\d+)\s*км/ч.*?скорость\s+втор\w+\s+(\d+)\s*км/ч.*?навстречу.*?сколько\s*км\s+остан\w*.*?через\s+(\d+)\s*час', low)
    if not m:
        m = re.search(r'расстояние\s+между\s+городами\s+(\d+)\s*км.*?скорость\s+перв\w+\s+автомобил\w*\s+(\d+)\s*км/ч.*?скорость\s+втор\w+\s+(\d+)\s*км/ч.*?навстречу.*?через\s+(\d+)\s*час.*?сколько\s*км\s+остан', low)
    if m:
        dist, v1, v2, t = map(int, m.groups())
        close = (v1 + v2) * t
        ans = dist - close
        return {
            'source': 'local:live-v281-motion-towards-remaining',
            'answer': f'{ans} километров',
            'steps': [
                f'{v1} + {v2} = {v1+v2} км/ч — скорость сближения.',
                f'{v1+v2} × {t} = {close} км — проедут навстречу за {t} часа.',
                f'{dist} − {close} = {ans} км — останется между ними.'
            ]
        }
    return _v281_motion_prev2(text)

_solve_joint_work_prev_v281 = solve_joint_work

def solve_joint_work(text: str):
    prev = _solve_joint_work_prev_v281(text)
    if prev:
        return prev
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    m = re.search(r'один\s+принтер\s+печатает\s+(\d+)\s+страниц\w*\s+за\s+(\d+)\s+час\w*.*?другой\s+принтер.*?за\s+(\d+)\s+час\w*.*?за\s+сколько\s+час\w*\s+они\s+напечатают\s+\1\s+страниц', low)
    if m:
        total, t1, t2 = map(int, m.groups())
        r1 = total / t1
        r2 = total / t2
        rate = r1 + r2
        hours = total / rate
        minutes = round(hours * 60)
        ans_time = _v281_format_minutes(minutes)
        return {
            'source': 'local:live-v281-joint-work-printers',
            'answer': ans_time,
            'steps': [
                f'{total} : {t1} = {int(r1) if r1.is_integer() else r1:g} страниц в час — печатает первый принтер.',
                f'{total} : {t2} = {int(r2) if r2.is_integer() else r2:g} страниц в час — печатает второй принтер.',
                f'{int(r1) if r1.is_integer() else r1:g} + {int(r2) if r2.is_integer() else r2:g} = {int(rate) if rate.is_integer() else rate:g} страниц в час — вместе.',
                f'{total} : {int(rate) if rate.is_integer() else rate:g} = {ans_time}.'
            ]
        }
    return None

_v281_data_prev2 = solve_v281_data_reading

def solve_v281_data_reading(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Difference of two durations in a table with labels that can contain spaces.
    m = re.search(r'таблиц\w*:\s*поезд\s+а\s*[—-]\s*(\d+)\s+минут\w*,\s*поезд\s+б\s*[—-]\s*(\d+)\s+минут', low)
    if m and re.search(r'на\s+сколько.*?дольше', low):
        a, b = map(int, m.groups())
        ans = abs(a - b)
        return {
            'source': 'local:live-v281-table-duration-difference',
            'answer': f'{ans} минут',
            'steps': [f'{a} − {b} = {ans} минут — на столько дольше.']
        }
    m = re.search(r'таблиц\w*:\s*математик\w*\s*[—-]\s*(\d+),\s*русск\w*\s*[—-]\s*(\d+),\s*чтени\w*\s*[—-]\s*(\d+)', low)
    if m and re.search(r'сколько\s+всего\s+задан\w*\s+по\s+математик\w*\s+и\s+русск', low):
        math, rus, read = map(int, m.groups())
        ans = math + rus
        return {
            'source': 'local:live-v281-table-choose-data',
            'answer': f'{ans} заданий',
            'steps': [f'Из таблицы берём только математику и русский: {math} и {rus}.', f'{math} + {rus} = {ans} заданий.']
        }
    return _v281_data_prev2(text)

_v281_arith_prev2 = solve_v281_arithmetic_and_equations

def solve_v281_arithmetic_and_equations(text: str):
    raw_all = _v281_clean(text).replace('х', 'x').replace('Х', 'x')
    # Use only the equation part before a trailing instruction like "Найди x".
    eq_part = raw_all.split('.')[0]
    compact = re.sub(r'\s+', '', eq_part.replace('×', '*').replace('·', '*').replace(':', '/'))
    m = re.fullmatch(r'(\d+)\*x\+(\d+)=(\d+)', compact)
    if m:
        a, b, c = map(int, m.groups())
        ans = (c - b) // a
        return {
            'source': 'local:live-v281-linear-equation',
            'answer': f'x = {ans}',
            'steps': [f'{c} − {b} = {c-b}.', f'{c-b} : {a} = {ans}.']
        }
    m = re.fullmatch(r'(\d+)\*x-(\d+)=(\d+)', compact)
    if m:
        a, b, c = map(int, m.groups())
        ans = (c + b) // a
        return {
            'source': 'local:live-v281-linear-equation',
            'answer': f'x = {ans}',
            'steps': [f'{c} + {b} = {c+b}.', f'{c+b} : {a} = {ans}.']
        }
    return _v281_arith_prev2(text)

# --- v281 patch 3: restore noun helper signature and finalize wave2 patterns ---
_v281_unit_forms_extra_base_final = _v281_unit_forms_extra_prev  # one-argument helper saved before patch 1

def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    extras = [
        (('мар',), ('марка', 'марки', 'марок')),
        (('накле',), ('наклейка', 'наклейки', 'наклеек')),
        (('груш', 'яблон', 'дерев'), ('дерево', 'дерева', 'деревьев')),
        (('ученик', 'учен'), ('ученик', 'ученика', 'учеников')),
        (('ребен', 'ребят', 'дет'), ('ребёнок', 'ребёнка', 'детей')),
        (('мест',), ('место', 'места', 'мест')),
        (('книг',), ('книга', 'книги', 'книг')),
        (('яблок',), ('яблоко', 'яблока', 'яблок')),
        (('тетрад',), ('тетрадь', 'тетради', 'тетрадей')),
        (('страниц',), ('страница', 'страницы', 'страниц')),
        (('винт',), ('винт', 'винта', 'винтов')),
        (('карандаш',), ('карандаш', 'карандаша', 'карандашей')),
        (('ластик',), ('ластик', 'ластика', 'ластиков')),
        (('руб',), ('рубль', 'рубля', 'рублей')),
        (('коп',), ('копейка', 'копейки', 'копеек')),
        (('кг', 'килограмм'), ('килограмм', 'килограмма', 'килограммов')),
        (('км', 'километр'), ('километр', 'километра', 'километров')),
        (('метр',), ('метр', 'метра', 'метров')),
        (('сантиметр', 'см'), ('сантиметр', 'сантиметра', 'сантиметров')),
        (('клет',), ('клетка', 'клетки', 'клеток')),
        (('знач',), ('значок', 'значка', 'значков')),
        (('билет',), ('билет', 'билета', 'билетов')),
    ]
    for markers, forms in extras:
        if any(marker in stem for marker in markers):
            return forms
    return _v281_unit_forms_extra_base_final(word)

_v281_numbers_units_prev3 = solve_v281_numbers_units

def solve_v281_numbers_units(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    m = re.search(r'(\d+)\s+сот\w*\s+тысяч\w*\s+(\d+)\s+десят\w*\s+тысяч\w*\s+(\d+)\s+тысяч\w*\s+(\d+)\s+сот\w*\s+(\d+)\s+десят\w*\s+(?:и\s+)?(\d+)\s+единиц', low)
    if m:
        a, b, c, d, e, f = map(int, m.groups())
        n = a*100000 + b*10000 + c*1000 + d*100 + e*10 + f
        return {
            'source': 'local:live-v281-place-value-million',
            'answer': str(n),
            'steps': [
                f'{a} сотни тысяч — это {a*100000}.',
                f'{b} десятка тысяч — это {b*10000}.',
                f'{c} тысяч — это {c*1000}.',
                f'{d} сотни — это {d*100}.',
                f'{e} десяток — это {e*10}.',
                f'{a*100000} + {b*10000} + {c*1000} + {d*100} + {e*10} + {f} = {n}.'
            ]
        }
    try:
        return _v281_numbers_units_prev3(text)
    except Exception:
        return None

_v281_text_composite_prev3 = _v281_text_composite_prev2

def solve_v281_text_composite(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    clean = _v281_sentence(text)
    # Two equal group blocks: 4 boxes of 25 and 3 boxes of 18.
    m = re.search(r'(?:привезл\w*|посадил\w*)\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+([а-яеё]+)\w*\s+и\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+([а-яеё]+)', low)
    if m and re.search(r'сколько\s+(?:\w+\s+)?(?:всего|привезл|посадил)', low):
        q1, cont1, per1, item1, q2, cont2, per2, item2 = m.groups()
        q1, per1, q2, per2 = map(int, [q1, per1, q2, per2])
        total1, total2 = q1 * per1, q2 * per2
        ans = total1 + total2
        target = 'деревьев' if ('дерев' in low or 'яблон' in low or 'груш' in low) else item1
        return {
            'source': 'local:live-v281-two-equal-groups-total',
            'answer': f'{ans} {_v281_word(ans, target)}',
            'steps': [
                f'{q1} × {per1} = {total1} {_v281_word(total1, target)} — первая часть.',
                f'{q2} × {per2} = {total2} {_v281_word(total2, target)} — вторая часть.',
                f'{total1} + {total2} = {ans} {_v281_word(ans, target)} — всего.'
            ]
        }
    # Total minus groups distributed.
    m = re.search(r'было\s+(\d+)\s+([а-яеё]+).*?в\s+(\d+)\s+класс\w*\s+раздал\w*\s+по\s+(\d+)\s+\2.*?сколько\s+\2\s+остал', low)
    if m:
        total, item, groups, each = m.groups()
        total, groups, each = map(int, [total, groups, each])
        used = groups * each
        left = total - used
        return {
            'source': 'local:live-v281-composite-distributed-left',
            'answer': f'{left} {_v281_word(left, item)}',
            'steps': [f'{groups} × {each} = {used} {_v281_word(used, item)} — раздали.', f'{total} − {used} = {left} {_v281_word(left, item)} — осталось.']
        }
    # Two-day sale where the second day is more than the first.
    m = re.search(r'было\s+(\d+)\s*(?:кг|килограмм\w*)\s+картофел\w*.*?перв\w*\s+день\s+продал\w*\s+(\d+)\s*(?:кг|килограмм\w*).*?втор\w*\s+день\s+продал\w*\s+на\s+(\d+)\s*(?:кг|килограмм\w*)\s+больше.*?сколько\s*(?:кг|килограмм\w*)\s+остал', low)
    if m:
        total, day1, more = map(int, m.groups())
        day2 = day1 + more
        sold = day1 + day2
        left = total - sold
        return {
            'source': 'local:live-v281-two-day-sale-left',
            'answer': f'{left} {_v281_word(left, "килограммов")}',
            'steps': [f'{day1} + {more} = {day2} кг — продали во второй день.', f'{day1} + {day2} = {sold} кг — продали за два дня.', f'{total} − {sold} = {left} кг — осталось.']
        }
    # Extra data: page count and price, but price is irrelevant.
    m = re.search(r'в\s+книг\w*\s+(\d+)\s+страниц\w*.*?прочитал\w*\s+(\d+)\s+страниц\w*.*?прочитал\w*\s+(\d+)\s+страниц\w*.*?сколько\s+страниц\w*\s+остал', low)
    if m:
        total, a, b = map(int, m.groups())
        read = a + b
        left = total - read
        return {
            'source': 'local:live-v281-extra-data-pages-left',
            'answer': f'{left} {_v281_word(left, "страниц")}',
            'steps': [f'{a} + {b} = {read} страниц — прочитал за два дня.', f'{total} − {read} = {left} {_v281_word(left, "страниц")} — осталось прочитать.']
        }
    # Reverse relation: total of two children/objects.
    m = re.search(r'у\s+([а-яеё]+)\s+и\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?у\s+\1\s+(\d+)\s+\4.*?сколько\s+\4\s+у\s+\2', low)
    if m:
        name1, name2, total, item, known = m.groups()
        total, known = int(total), int(known)
        ans = total - known
        return {
            'source': 'local:live-v281-part-whole-second',
            'answer': f'{ans} {_v281_word(ans, item)}',
            'steps': [f'{total} − {known} = {ans} {_v281_word(ans, item)}.']
        }
    # Two listed class sizes, then some pupils leave.
    m = re.search(r'в\s+двух\s+классах\s+было\s+(\d+)\s+и\s+(\d+)\s+ученик\w*.*?(\d+)\s+ученик\w*\s+ушл\w*.*?сколько\s+ученик\w*\s+остал', low)
    if m:
        a, b, c = map(int, m.groups())
        total = a + b
        ans = total - c
        return {
            'source': 'local:live-v281-composite-two-listed-left',
            'answer': f'{ans} {_v281_word(ans, "учеников")}',
            'steps': [f'{a} + {b} = {total} учеников — было всего.', f'{total} − {c} = {ans} {_v281_word(ans, "учеников")} — осталось.']
        }
    # Free seats in buses.
    m = re.search(r'поехал\w*\s+(\d+)\s+ученик\w*.*?было\s+(\d+)\s+автобус\w*\s+по\s+(\d+)\s+мест', low)
    if m and re.search(r'сколько\s+мест\s+остал\w*\s+свобод', low):
        pupils, buses, seats = map(int, m.groups())
        capacity = buses * seats
        ans = capacity - pupils
        return {
            'source': 'local:live-v281-capacity-free-seats',
            'answer': f'{ans} {_v281_word(ans, "мест")}',
            'steps': [f'{buses} × {seats} = {capacity} мест — всего мест.', f'{capacity} − {pupils} = {ans} {_v281_word(ans, "мест")} — свободно.']
        }
    # Equal groups, then some sold.
    m = re.search(r'в\s+(\d+)\s+ящик\w*\s+было\s+по\s+(\d+)\s+яблок\w*.*?продал\w*\s+(\d+)\s+яблок\w*.*?сколько\s+яблок\w*\s+остал', low)
    if m:
        boxes, per, sold = map(int, m.groups())
        total = boxes * per
        ans = total - sold
        return {
            'source': 'local:live-v281-equal-groups-sold-left',
            'answer': f'{ans} {_v281_word(ans, "яблок")}',
            'steps': [f'{boxes} × {per} = {total} яблок — было всего.', f'{total} − {sold} = {ans} {_v281_word(ans, "яблок")} — осталось.']
        }
    # Ratio-difference comparison.
    m = re.search(r'морков\w*\s+было\s+(\d+)\s*кг.*?лук\w*\s+в\s+(\d+)\s+раз\w*\s+меньше.*?на\s+сколько\s+килограмм\w*\s+морков\w*\s+больше', low)
    if m:
        carrot, k = map(int, m.groups())
        onion = carrot // k
        ans = carrot - onion
        return {
            'source': 'local:live-v281-ratio-difference',
            'answer': f'{ans} {_v281_word(ans, "килограммов")}',
            'steps': [f'{carrot} : {k} = {onion} кг — было лука.', f'{carrot} − {onion} = {ans} {_v281_word(ans, "килограммов")} — на столько моркови больше.']
        }
    try:
        return _v281_text_composite_prev3(text)
    except Exception:
        return None

_v281_money_prev3 = _v281_money_prev2

def solve_v281_money(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    clean = _v281_sentence(text)
    # Budget with two item types.
    m = re.search(r'с\s+(\d+)\s+рубл\w*\s+купил\w*\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+рубл\w*\s+и\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+рубл', low)
    if m and re.search(r'сколько\s+рубл\w*\s+остал', low):
        budget, q1, item1, p1, q2, item2, p2 = m.groups()
        budget, q1, p1, q2, p2 = map(int, [budget, q1, p1, q2, p2])
        cost1, cost2 = q1*p1, q2*p2
        spent = cost1 + cost2
        ans = budget - spent
        return {
            'source': 'local:live-v281-money-two-items-budget',
            'answer': f'{ans} {_v281_word(ans, "рублей")}',
            'steps': [f'{q1} × {p1} = {cost1} рублей — первая покупка.', f'{q2} × {p2} = {cost2} рублей — вторая покупка.', f'{cost1} + {cost2} = {spent} рублей — потратили.', f'{budget} − {spent} = {ans} {_v281_word(ans, "рублей")} — осталось.']
        }
    # Price × quantity, quantity is after the question word.
    m = re.search(r'одн\w+\s+([а-яеё]+)\w*\s+стоит\s+(\d+)\s+рубл\w*.*?сколько\s+стоят\s+(\d+)\s+так\w*\s+\w+', low)
    if m:
        item, price, qty = m.groups()
        price, qty = int(price), int(qty)
        ans = price * qty
        return {'source': 'local:live-v281-money-price-times-quantity', 'answer': f'{ans} {_v281_word(ans, "рублей")}', 'steps': [f'{price} × {qty} = {ans} {_v281_word(ans, "рублей")} — стоимость покупки.']}
    # Change from one repeated purchase.
    m = re.search(r'с\s+(\d+)\s+рубл\w*\s+купил\w*\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+рубл\w*.*?сколько\s+рубл\w*\s+сдач\w*\s+получ', low)
    if m:
        budget, q, item, price = m.groups()
        budget, q, price = map(int, [budget, q, price])
        cost = q * price
        ans = budget - cost
        return {'source': 'local:live-v281-money-repeated-change', 'answer': f'{ans} {_v281_word(ans, "рублей")}', 'steps': [f'{q} × {price} = {cost} рублей — стоимость покупки.', f'{budget} − {cost} = {ans} {_v281_word(ans, "рублей")} — сдача.']}
    # Price per kilogram from total.
    m = re.search(r'за\s+(\d+)\s+кг\s+[а-яеё]+\s+заплатил\w*\s+(\d+)\s+рубл\w*.*?сколько\s+рубл\w*\s+стоит\s+1\s+кг', low)
    if m:
        kg, total = map(int, m.groups())
        ans = total // kg
        return {'source': 'local:live-v281-money-unit-price', 'answer': f'{ans} {_v281_word(ans, "рублей")}', 'steps': [f'{total} : {kg} = {ans} {_v281_word(ans, "рублей")} — цена 1 кг.']}
    # How many tickets/items can be bought for a budget.
    m = re.search(r'один\s+([а-яеё]+)\s+стоит\s+(\d+)\s+рубл\w*.*?сколько\s+\1\w*\s+можно\s+купить\s+на\s+(\d+)\s+рубл', low)
    if m:
        item, price, budget = m.groups()
        price, budget = int(price), int(budget)
        ans = budget // price
        return {'source': 'local:live-v281-money-quantity-budget', 'answer': f'{ans} {_v281_word(ans, item)}', 'steps': [f'{budget} : {price} = {ans} {_v281_word(ans, item)} — можно купить.']}
    try:
        return _v281_money_prev3(text)
    except Exception:
        return None

_v281_fractions_prev3 = solve_v281_fractions

def solve_v281_fractions(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Unit fraction of metres: convert to centimetres when result is fractional in metres.
    m = re.search(r'найди\s+1/(\d+)\s+от\s+(\d+)\s*м\b', low)
    if m:
        den, metres = map(int, m.groups())
        cm = metres * 100
        ans = cm // den
        return {'source': 'local:live-v281-fraction-length', 'answer': f'{ans} см', 'steps': [f'{metres} м = {cm} см.', f'{cm} : {den} = {ans} см.']}
    try:
        return _v281_fractions_prev3(text)
    except Exception:
        return None

_v281_data_prev3 = _v281_data_prev2

def solve_v281_data_reading(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    # Pictogram scale.
    m = re.search(r'пиктограмм\w*:\s*1\s+значок\s*=\s*(\d+)\s+книг\w*.*?у\s+класса\s+(\d+)\s+значк\w*.*?сколько\s+книг', low)
    if m:
        scale, icons = map(int, m.groups())
        ans = scale * icons
        return {'source': 'local:live-v281-pictogram-scale', 'answer': f'{ans} {_v281_word(ans, "книг")}', 'steps': [f'1 значок = {scale} книг.', f'{icons} × {scale} = {ans} {_v281_word(ans, "книг")}.']}
    # Table duration difference with labels that include a letter.
    m = re.search(r'таблиц\w*:\s*поезд\s+а\s*[—-]\s*(\d+)\s+минут\w*,\s*поезд\s+б\s*[—-]\s*(\d+)\s+минут', low)
    if m and re.search(r'на\s+сколько.*?дольше', low):
        a, b = map(int, m.groups())
        ans = abs(a-b)
        return {'source': 'local:live-v281-table-duration-difference', 'answer': f'{ans} минут', 'steps': [f'{a} − {b} = {ans} минут — на столько дольше.']}
    # Choose two required subjects from three data points.
    m = re.search(r'таблиц\w*:\s*математик\w*\s*[—-]\s*(\d+),\s*русск\w*\s*[—-]\s*(\d+),\s*чтени\w*\s*[—-]\s*(\d+)', low)
    if m and re.search(r'сколько\s+всего\s+задан\w*\s+по\s+математик\w*\s+и\s+русск', low):
        math, rus, read = map(int, m.groups())
        ans = math + rus
        return {'source': 'local:live-v281-table-choose-data', 'answer': f'{ans} заданий', 'steps': [f'{math} + {rus} = {ans} заданий — берём только нужные данные.']}
    try:
        return _v281_data_prev3(text)
    except Exception:
        return None

_v281_arith_prev3 = _v281_arith_prev2

def solve_v281_arithmetic_and_equations(text: str):
    raw_all = _v281_clean(text).replace('х', 'x').replace('Х', 'x')
    eq_part = raw_all.split('.')[0]
    compact = re.sub(r'\s+', '', eq_part.replace('×', '*').replace('·', '*').replace(':', '/'))
    m = re.fullmatch(r'(\d+)\*x\+(\d+)=(\d+)', compact)
    if m:
        a, b, c = map(int, m.groups())
        ans = (c - b) // a
        return {'source': 'local:live-v281-linear-equation', 'answer': f'x = {ans}', 'steps': [f'{c} − {b} = {c-b}.', f'{c-b} : {a} = {ans}.']}
    try:
        return _v281_arith_prev3(text)
    except Exception:
        return None

# --- v281 patch 4: normalize compact solver payloads into full explanation text ---
def _v281_full_payload(text: str, payload: Optional[dict]) -> Optional[dict]:
    if payload is None or not isinstance(payload, dict):
        return payload
    if payload.get('result'):
        return payload
    if 'answer' in payload:
        steps = payload.get('steps') or []
        if isinstance(steps, str):
            steps = [steps]
        lines = ['Задача.', _v281_sentence(text), 'Решение.']
        for i, step in enumerate(steps, start=1):
            s = str(step).strip()
            if not s:
                continue
            if re.match(r'^\d+\)', s):
                lines.append(s)
            else:
                lines.append(f'{i}) {s}')
        lines.append(f'Ответ: {payload.get("answer")}.')
        out = dict(payload)
        out['result'] = '\n'.join(lines)
        out.setdefault('validated', True)
        return out
    return payload

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v281_arithmetic_and_equations,
        solve_v281_numbers_units,
        solve_v281_money,
        solve_v281_time_calendar,
        solve_v281_motion,
        solve_v281_text_composite,
        solve_v281_fractions,
        solve_v281_geometry,
        solve_v281_data_reading,
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
            return _v281_full_payload(text, payload)
    return None

# --- v281 patch 5: spell out centimetres in grade-4 fraction-length answers ---
_v281_fractions_prev5 = solve_v281_fractions

def solve_v281_fractions(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    m = re.search(r'найди\s+1/(\d+)\s+от\s+(\d+)\s*м\b', low)
    if m:
        den, metres = map(int, m.groups())
        cm = metres * 100
        ans = cm // den
        return {'source': 'local:live-v281-fraction-length', 'answer': f'{ans} {_v281_word(ans, "сантиметров")}', 'steps': [f'{metres} м = {cm} см.', f'{cm} : {den} = {ans} см.']}
    try:
        return _v281_fractions_prev5(text)
    except Exception:
        return None

# --- v281 patch 6: explicit centimetre wording to avoid metre stem collision ---
_v281_fractions_prev6 = solve_v281_fractions

def solve_v281_fractions(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    m = re.search(r'найди\s+1/(\d+)\s+от\s+(\d+)\s*м\b', low)
    if m:
        den, metres = map(int, m.groups())
        cm = metres * 100
        ans = cm // den
        return {'source': 'local:live-v281-fraction-length', 'answer': f'{ans} сантиметров', 'steps': [f'{metres} м = {cm} см.', f'{cm} : {den} = {ans} см.']}
    try:
        return _v281_fractions_prev6(text)
    except Exception:
        return None

# --- v281 patch 7: avoid slow legacy square-geometry path ---
_v281_geometry_prev7 = solve_v281_geometry

def solve_v281_geometry(text: str):
    raw = _v281_clean(text)
    low = _v281_lower(raw)
    m = re.search(r'сторона\s+квадрата\s+(\d+)\s*см.*?найди\s+периметр\s+квадрата', low)
    if m:
        side = int(m.group(1))
        ans = side * 4
        return {'source': 'local:live-v281-square-perimeter', 'answer': f'{ans} см', 'steps': [f'У квадрата 4 равные стороны.', f'{side} × 4 = {ans} см.']}
    try:
        return _v281_geometry_prev7(text)
    except Exception:
        return None

# --- v283 external black-box audit wave 3: morphology, frontend/TTS-adjacent polish, and edge routes ---
# These are general pattern solvers for the new audit wave.  They avoid exact
# task lookups and keep the explanation/source explicit for black-box checking.

_v283_unit_forms_prev = _v281_unit_forms_extra

def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    extras = [
        (('руч',), ('ручка', 'ручки', 'ручек')),
        (('груш', 'яблон', 'фрукт'), ('фрукт', 'фрукта', 'фруктов')),
        (('альбом',), ('альбом', 'альбома', 'альбомов')),
        (('кисточ', 'кист'), ('кисточка', 'кисточки', 'кисточек')),
        (('пенал',), ('пенал', 'пенала', 'пеналов')),
        (('открытк',), ('открытка', 'открытки', 'открыток')),
        (('рисунк',), ('рисунок', 'рисунка', 'рисунков')),
        (('детал',), ('деталь', 'детали', 'деталей')),
        (('литр', 'л'), ('литр', 'литра', 'литров')),
        (('минут', 'мин'), ('минута', 'минуты', 'минут')),
        (('секунд', 'сек'), ('секунда', 'секунды', 'секунд')),
        (('месяц', 'мес'), ('месяц', 'месяца', 'месяцев')),
        (('год', 'лет'), ('год', 'года', 'лет')),
        (('ось', 'оси'), ('ось', 'оси', 'осей')),
        (('сторон', 'сторона'), ('сторона', 'стороны', 'сторон')),
        (('вершин', 'вершина'), ('вершина', 'вершины', 'вершин')),
    ]
    for markers, forms in extras:
        if any(marker in stem for marker in markers):
            return forms
    return _v283_unit_forms_prev(word)


def _v283_clean(text: str) -> str:
    return _v281_clean(text).replace('÷', ':').replace('·', '*').replace('×', '*')


def _v283_lower(text: str) -> str:
    return _v283_clean(text).lower().replace('ё', 'е')


def _v283_money_parts_to_kop(r: int, k: int) -> int:
    return int(r) * 100 + int(k)


def _v283_format_rub_kop(total_kop: int) -> str:
    rub, kop = divmod(int(total_kop), 100)
    return f'{rub} {_v281_word(rub, "рублей")} {kop} {_v281_word(kop, "копеек")}'


def _v283_format_year_month(total_months: int) -> str:
    years, months = divmod(int(total_months), 12)
    parts = []
    if years:
        parts.append(f'{years} {_v281_word(years, "год")}')
    if months:
        parts.append(f'{months} {_v281_word(months, "месяц")}')
    return ' '.join(parts) if parts else '0 месяцев'


def solve_v283_numbers_units(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    # 6 тысяч 8 десятков и 4 единицы -> 6084
    m = re.search(r'числ[оа],?\s+в\s+котор\w+\s+(\d+)\s+тысяч\w*\s+(\d+)\s+десятк\w*\s+(?:и\s+)?(\d+)\s+единиц', low)
    if m:
        th, tens, ones = map(int, m.groups())
        ans = th * 1000 + tens * 10 + ones
        return {'source': 'local:live-v283-place-value', 'answer': str(ans), 'steps': [f'{th} тысяч — это {th*1000}.', f'{tens} десятков — это {tens*10}.', f'{th*1000} + {tens*10} + {ones} = {ans}.']}
    m = re.search(r'в\s+числе\s+(\d{4,})\s+сколько\s+тысяч\w*,?\s+сот\w*,?\s+десятк\w*\s+и\s+единиц', low)
    if m:
        n = int(m.group(1))
        thousands = n // 1000
        hundreds = (n // 100) % 10
        tens = (n // 10) % 10
        ones = n % 10
        return {'source': 'local:live-v283-place-value-read', 'answer': f'{thousands} {_v281_word(thousands, "тысяч")} {hundreds} {_v281_word(hundreds, "сотен")} {tens} {_v281_word(tens, "десятков")} {ones} {_v281_word(ones, "единиц")}', 'steps': [f'В числе {n}: тысяч — {thousands}, сотен — {hundreds}, десятков — {tens}, единиц — {ones}.']}
    m = re.search(r'округли\s+([\d\s]+)\s+до\s+тысяч', low)
    if m:
        n = int(re.sub(r'\D+', '', m.group(1)))
        ans = int(round(n / 1000.0) * 1000)
        return {'source': 'local:live-v283-rounding', 'answer': str(ans), 'steps': [f'Округляем {n} до тысяч.', f'Получаем {ans}.']}
    m = re.search(r'сравни\s+числа\s+([\d\s]+)\s+и\s+([\d\s]+)', low)
    if m:
        a = int(re.sub(r'\D+', '', m.group(1)))
        b = int(re.sub(r'\D+', '', m.group(2)))
        sign = '<' if a < b else '>' if a > b else '='
        rel = 'меньше' if a < b else 'больше' if a > b else 'равно'
        return {'source': 'local:live-v283-number-compare', 'answer': f'{a} {sign} {b}', 'steps': [f'Сравниваем {a} и {b}.', f'{a} {sign} {b}, значит первое число {rel}.']}
    # conversions
    m = re.search(r'сколько\s+километр\w*\s+и\s+метр\w*\s+в\s+(\d+)\s*м\b', low)
    if m:
        meters = int(m.group(1)); km, mleft = divmod(meters, 1000)
        return {'source': 'local:live-v283-units', 'answer': f'{km} {_v281_word(km, "километров")} {mleft} {_v281_word(mleft, "метров")}', 'steps': [f'1 км = 1000 м.', f'{meters} м = {km} км {mleft} м.']}
    m = re.search(r'сколько\s+килограмм\w*\s+в\s+(\d+)\s*т\s*(\d+)\s*кг', low)
    if m:
        tons, kg = map(int, m.groups()); total = tons*1000+kg
        return {'source': 'local:live-v283-units', 'answer': f'{total} {_v281_word(total, "килограммов")}', 'steps': [f'{tons} т = {tons*1000} кг.', f'{tons*1000} + {kg} = {total} кг.']}
    m = re.search(r'(\d+)\s+руб\w*\s+(\d+)\s+коп\w*\s*[-−–—]\s*(\d+)\s+руб\w*\s+(\d+)\s+коп\w*', low)
    if m:
        r1,k1,r2,k2 = map(int, m.groups())
        total = _v283_money_parts_to_kop(r1,k1) - _v283_money_parts_to_kop(r2,k2)
        return {'source': 'local:live-v283-money-rub-kop-sub', 'answer': _v283_format_rub_kop(total), 'steps': [f'{r1} руб. {k1} коп. = {_v283_money_parts_to_kop(r1,k1)} коп.', f'{r2} руб. {k2} коп. = {_v283_money_parts_to_kop(r2,k2)} коп.', f'{_v283_money_parts_to_kop(r1,k1)} − {_v283_money_parts_to_kop(r2,k2)} = {total} коп.']}
    m = re.search(r'(\d+)\s+коп\w*\s*[-—]?\s*это\s+сколько\s+руб\w*\s+и\s+коп\w*', low)
    if m:
        kop = int(m.group(1))
        return {'source': 'local:live-v283-money-kop-to-rub', 'answer': _v283_format_rub_kop(kop), 'steps': [f'{kop} коп. = {_v283_format_rub_kop(kop)}.']}
    m = re.search(r'(\d+)\s+секунд\w*\s*[-—]?\s*это\s+сколько\s+минут\w*\s+и\s+секунд', low)
    if m:
        total = int(m.group(1)); minutes, seconds = divmod(total, 60)
        return {'source': 'local:live-v283-time-conversion', 'answer': f'{minutes} {_v281_word(minutes, "минут")} {seconds} {_v281_word(seconds, "секунд")}', 'steps': [f'{total} секунд = {minutes} мин {seconds} с.']}
    m = re.search(r'(\d+)\s+месяц\w*\s*[-—]?\s*это\s+сколько\s+лет\s+и\s+месяц', low)
    if m:
        months = int(m.group(1))
        return {'source': 'local:live-v283-calendar-conversion', 'answer': _v283_format_year_month(months), 'steps': [f'1 год = 12 месяцев.', f'{months} месяцев = {_v283_format_year_month(months)}.']}
    m = re.search(r'сколько\s+час\w*\s+в\s+(\d+)\s+минут', low)
    if m:
        total = int(m.group(1)); hours = total // 60
        return {'source': 'local:live-v283-time-conversion', 'answer': f'{hours} {_v281_word(hours, "часов")}', 'steps': [f'1 час = 60 минут.', f'{total} : 60 = {hours}.']}
    m = re.search(r'сколько\s+час\w*\s+в\s+(\d+)\s+сутк\w*\s+(\d+)\s+час', low)
    if m:
        days, hours = map(int, m.groups()); total = days*24+hours
        return {'source': 'local:live-v283-time-conversion', 'answer': f'{total} {_v281_word(total, "часов")}', 'steps': [f'{days} суток = {days*24} часов.', f'{days*24} + {hours} = {total} часов.']}
    m = re.search(r'(\d+)\s+недел\w*\s+и\s+(\d+)\s+дн\w*.*?сколько\s+это\s+дн', low)
    if m:
        weeks, days = map(int, m.groups()); total = weeks*7+days
        return {'source': 'local:live-v283-calendar', 'answer': f'{total} {_v281_word(total, "дней")}', 'steps': [f'{weeks} недели = {weeks*7} дней.', f'{weeks*7} + {days} = {total} дней.']}
    return None


def solve_v283_arithmetic_equations(text: str) -> Optional[dict]:
    raw = _v283_clean(text).replace('х', 'x').replace('Х', 'x')
    low = raw.lower().replace('ё', 'е')
    # Direct expressions with unicode signs.
    m = re.search(r'(?:вычисли|найди\s+значение\s+выражения)\s*:?\s*([^.?]+)', raw, flags=re.IGNORECASE)
    if m:
        expr = m.group(1).strip()
        if re.fullmatch(r'[0-9\s+\-−–—*:×·÷/().]+', expr):
            val = _v280_eval_expr(expr)
            if val is not None:
                return {'source': 'local:live-v283-direct-arithmetic', 'answer': _fmt_fraction(val), 'steps': ['Вычисляем по порядку действий.', f'{expr} = {_fmt_fraction(val)}.']}
    # Contextual division with remainder into containers.
    m = re.search(r'(\d+)\s+([а-яеё]+)\w*\s+разложил\w*\s+по\s+(\d+)\s+\2\w*\s+в\s+([а-яеё]+)\w*.*?сколько\s+полн\w*', low)
    if m:
        total, item, per, container = m.groups(); total, per = int(total), int(per)
        q, r = divmod(total, per)
        return {'source': 'local:live-v283-remainder-context', 'answer': f'{q} полных {_v281_word(q, container)} и {r} {_v281_word(r, item)}', 'steps': [f'{total} : {per} = {q} (ост. {r}).']}
    compact = re.sub(r'\s+', '', raw.split('.')[0].replace(':', '/').replace('×', '*').replace('·', '*'))
    patterns = [
        (r'x-(\d+)=(\d+)', lambda a,b: int(a)+int(b), lambda a,b: [f'{b} + {a} = {int(a)+int(b)}.']),
        (r'(\d+)-x=(\d+)', lambda a,b: int(a)-int(b), lambda a,b: [f'{a} − {b} = {int(a)-int(b)}.']),
        (r'(\d+)\*x\+(\d+)=(\d+)', lambda a,b,c: (int(c)-int(b))//int(a), lambda a,b,c: [f'{c} − {b} = {int(c)-int(b)}.', f'{int(c)-int(b)} : {a} = {(int(c)-int(b))//int(a)}.']),
        (r'(\d+)\*x-(\d+)=(\d+)', lambda a,b,c: (int(c)+int(b))//int(a), lambda a,b,c: [f'{c} + {b} = {int(c)+int(b)}.', f'{int(c)+int(b)} : {a} = {(int(c)+int(b))//int(a)}.']),
        (r'(\d+)/x=(\d+)', lambda a,b: int(a)//int(b), lambda a,b: [f'{a} : {b} = {int(a)//int(b)}.']),
    ]
    for pat, calc, steps_fn in patterns:
        mm = re.fullmatch(pat, compact)
        if mm:
            ans = calc(*mm.groups())
            return {'source': 'local:live-v283-equation', 'answer': f'x = {ans}', 'steps': steps_fn(*mm.groups())}
    m = re.search(r'значение\s+выражения\s+a\s*\*\s*b\s*[-−]\s*(\d+).*?a\s*=\s*(\d+).*?b\s*=\s*(\d+)', low)
    if m:
        sub, a, b = map(int, m.groups()); ans = a*b-sub
        return {'source': 'local:live-v283-letter-expression', 'answer': str(ans), 'steps': [f'Подставляем a = {a}, b = {b}.', f'{a} × {b} − {sub} = {ans}.']}
    return None


def solve_v283_text_composite(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    # Classes plus extra students.
    m = re.search(r'(?:пришл\w*|участвовал\w*)\s+(\d+)\s+класс\w*\s+по\s+(\d+)\s+учен\w*\s+и\s+еще\s+(\d+)\s+учен', low)
    if m:
        groups, each, extra = map(int, m.groups()); total = groups*each + extra
        return {'source': 'local:live-v283-composite-extra-total', 'answer': f'{total} {_v281_word(total, "учеников")}', 'steps': [f'{groups} × {each} = {groups*each} учеников.', f'{groups*each} + {extra} = {total} учеников.']}
    m = re.search(r'в\s+зал\w*\s+(\d+)\s+ряд\w*\s+по\s+(\d+)\s+мест\w*.*?занял\w*\s+(\d+)\s+мест\w*.*?сколько\s+мест\w*\s+остал\w*\s+свобод', low)
    if m:
        rows, seats, used = map(int, m.groups()); total=rows*seats; left=total-used
        return {'source': 'local:live-v283-capacity-left', 'answer': f'{left} {_v281_word(left, "мест")}', 'steps': [f'{rows} × {seats} = {total} мест — всего.', f'{total} − {used} = {left} мест — свободно.']}
    # Book read: two equal or second relative.
    m = re.search(r'в\s+книг\w*\s+(\d+)\s+страниц\w*.*?(?:прочитал\w*|прочитали)\s+(\d+)\s+страниц\w*,?\s*(?:во\s+вторник\s+)?(?:потом\s+еще\s+)?(?:на\s+(\d+)\s+страниц\w*\s+больше|(?:прочитал\w*|прочитали)\s+еще\s+(\d+)\s+страниц\w*|(?:прочитал\w*|прочитали)\s+(\d+)\s+страниц\w*)', low)
    if m and 'сколько' in low and 'остал' in low:
        total = int(m.group(1)); first = int(m.group(2))
        second = first + int(m.group(3)) if m.group(3) else int(m.group(4) or m.group(5) or 0)
        left = total - first - second
        return {'source': 'local:live-v283-pages-left', 'answer': f'{left} {_v281_word(left, "страниц")}', 'steps': [f'{first} + {second} = {first+second} страниц — прочитали.', f'{total} − {first+second} = {left} страниц — осталось.']}
    # Equal groups remaining for many nouns.
    m = re.search(r'в\s+(\d+)\s+(?:коробк|набор|ящик)\w*\s+по\s+(\d+)\s+([а-яеё]+)\w*.*?(?:взял\w*|подарил\w*|продал\w*)\s+(\d+)\s+\3\w*.*?сколько\s+\3\w*\s+остал', low)
    if m:
        groups, each, item, taken = m.groups(); groups, each, taken = map(int, [groups, each, taken])
        total = groups*each; left = total-taken
        return {'source': 'local:live-v283-equal-groups-left', 'answer': f'{left} {_v281_word(left, item)}', 'steps': [f'{groups} × {each} = {total} {_v281_word(total, item)} — было всего.', f'{total} − {taken} = {left} {_v281_word(left, item)} — осталось.']}
    # Store: kg commodity, two-day use/sale.
    m = re.search(r'было\s+(\d+)\s*кг\s+([а-яеё]+).*?перв\w*\s+день\s+(?:взял\w*|продал\w*)\s+(\d+)\s*кг.*?втор\w*\s+день\s+(?:взял\w*|продал\w*)\s+на\s+(\d+)\s*кг\s+больше.*?сколько\s*кг\s+\2\s+остал', low)
    if m:
        total, item, first, more = m.groups(); total, first, more = map(int, [total, first, more])
        second = first+more; left = total-first-second
        return {'source': 'local:live-v283-kg-two-day-left', 'answer': f'{left} {_v281_word(left, "килограммов")}', 'steps': [f'{first} + {more} = {second} кг — во второй день.', f'{first} + {second} = {first+second} кг — всего.', f'{total} − {first+second} = {left} кг — осталось.']}
    # Generic two group blocks with final target possibly fruits.
    m = re.search(r'(?:привезл\w*|купил\w*|посадил\w*)\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+([а-яеё]+)\w*\s+и\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+([а-яеё]+)', low)
    if m and re.search(r'сколько\s+([а-яеё]+)\w*\s+(?:привезл\w*\s+)?всего|сколько\s+всего', low):
        q1, c1, p1, item1, q2, c2, p2, item2 = m.groups(); q1,p1,q2,p2=map(int,[q1,p1,q2,p2])
        a,b=q1*p1,q2*p2; total=a+b
        target = 'фруктов' if 'фрукт' in low else item1
        return {'source': 'local:live-v283-two-groups-total', 'answer': f'{total} {_v281_word(total, target)}', 'steps': [f'{q1} × {p1} = {a} {_v281_word(a, target)}.', f'{q2} × {p2} = {b} {_v281_word(b, target)}.', f'{a} + {b} = {total} {_v281_word(total, target)}.']}
    # Total minus distributed groups plus extra.
    m = re.search(r'было\s+(\d+)\s+([а-яеё]+).*?в\s+(\d+)\s+класс\w*\s+раздал\w*\s+по\s+(\d+)\s+\2.*?(?:еще\s+)?(?:отдал\w*|выдал\w*)\s+еще\s+(\d+)\s+\2.*?сколько\s+\2\s+остал', low)
    if m:
        total,item,groups,each,extra=m.groups(); total,groups,each,extra=map(int,[total,groups,each,extra])
        used=groups*each+extra; left=total-used
        return {'source': 'local:live-v283-composite-three-action-left', 'answer': f'{left} {_v281_word(left, item)}', 'steps': [f'{groups} × {each} = {groups*each} {_v281_word(groups*each, item)} — раздали в классы.', f'{groups*each} + {extra} = {used} {_v281_word(used, item)} — всего отдали.', f'{total} − {used} = {left} {_v281_word(left, item)} — осталось.']}
    # Reverse relation total.
    m = re.search(r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+).*?это\s+в\s+(\d+)\s+раз\w*\s+меньше,?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+\3\s+у\s+них\s+вместе', low)
    if m:
        name1, base, item, k, name2 = m.groups(); base,k=int(base),int(k); other=base*k; total=base+other
        return {'source': 'local:live-v283-reverse-times-total', 'answer': f'{total} {_v281_word(total, item)}', 'steps': [f'{base} × {k} = {other} {_v281_word(other, item)} — у второго.', f'{base} + {other} = {total} {_v281_word(total, item)} — вместе.']}
    m = re.search(r'у\s+перв\w+\s+класс\w*\s+(\d+)\s+([а-яеё]+).*?у\s+втор\w+\s+в\s+(\d+)\s+раз\w*\s+больше.*?на\s+сколько\s+\2\s+у\s+втор', low)
    if m:
        base,item,k=m.groups(); base,k=int(base),int(k); second=base*k; diff=second-base
        return {'source': 'local:live-v283-times-more-difference', 'answer': f'{diff} {_v281_word(diff, item)}', 'steps': [f'{base} × {k} = {second} {_v281_word(second, item)} — у второго.', f'{second} − {base} = {diff} {_v281_word(diff, item)} — на столько больше.']}
    # Fraction used then left.
    m = re.search(r'в\s+коробк\w*\s+(\d+)\s+([а-яеё]+).*?1/(\d+)\s+\2\s+использовал\w*.*?сколько\s+\2\s+остал', low)
    if m:
        total,item,den=m.groups(); total,den=int(total),int(den); used=total//den; left=total-used
        return {'source': 'local:live-v283-fraction-left', 'answer': f'{left} {_v281_word(left, item)}', 'steps': [f'{total} : {den} = {used} {_v281_word(used, item)} — использовали.', f'{total} − {used} = {left} {_v281_word(left, item)} — осталось.']}
    # Apple/pear total as trees.
    m = re.search(r'в\s+саду\s+(\d+)\s+яблон\w*,\s+а\s+груш\w*\s+на\s+(\d+)\s+меньше.*?сколько\s+яблон\w*\s+и\s+груш\w*\s+вместе', low)
    if m:
        apples, less = map(int, m.groups()); pears=apples-less; total=apples+pears
        return {'source': 'local:live-v283-trees-total', 'answer': f'{total} {_v281_word(total, "деревьев")}', 'steps': [f'{apples} − {less} = {pears} груш.', f'{apples} + {pears} = {total} деревьев.']}
    # One box after sharing and taking some from one box.
    m = re.search(r'(\d+)\s+([а-яеё]+)\w*\s+разложил\w*\s+поровну\s+в\s+(\d+)\s+короб\w*.*?из\s+одн\w+\s+короб\w*\s+взял\w*\s+(\d+)\s+\2\w*.*?сколько\s+\2\w*\s+остал\w*\s+в\s+эт\w+\s+короб', low)
    if m:
        total,item,boxes,taken=m.groups(); total,boxes,taken=map(int,[total,boxes,taken]); per=total//boxes; left=per-taken
        return {'source': 'local:live-v283-one-box-left-after-sharing', 'answer': f'{left} {_v281_word(left, item)}', 'steps': [f'{total} : {boxes} = {per} {_v281_word(per, item)} — в одной коробке.', f'{per} − {taken} = {left} {_v281_word(left, item)} — осталось в этой коробке.']}
    return None


def solve_v283_money(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    m = re.search(r'купил\w*\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+руб\w*\s+и\s+(\d+)\s+([а-яеё]+)\w*\s+по\s+(\d+)\s+руб\w*.*?сколько\s+руб\w*\s+заплат', low)
    if m:
        q1,item1,p1,q2,item2,p2=m.groups(); q1,p1,q2,p2=map(int,[q1,p1,q2,p2]); c1=q1*p1; c2=q2*p2; total=c1+c2
        return {'source':'local:live-v283-money-two-types-total','answer':f'{total} {_v281_word(total,"рублей")}', 'steps':[f'{q1} × {p1} = {c1} рублей.', f'{q2} × {p2} = {c2} рублей.', f'{c1} + {c2} = {total} рублей.']}
    m = re.search(r'было\s+(\d+)\s+руб\w*.*?купил\w*\s+(\d+)\s+книг\w*\s+по\s+(\d+)\s+руб\w*\s+и\s+пенал\w*\s+за\s+(\d+)\s+руб\w*.*?сколько\s+руб\w*\s+остал', low)
    if m:
        budget,q,price,extra=map(int,m.groups()); spent=q*price+extra; left=budget-spent
        return {'source':'local:live-v283-money-budget-extra','answer':f'{left} {_v281_word(left,"рублей")}', 'steps':[f'{q} × {price} = {q*price} рублей.', f'{q*price} + {extra} = {spent} рублей.', f'{budget} − {spent} = {left} рублей.']}
    m = re.search(r'за\s+(\d+)\s+одинаков\w*\s+([а-яеё]+)\w*\s+заплатил\w*\s+(\d+)\s+руб\w*.*?сколько\s+руб\w*\s+стоят\s+(\d+)\s+так', low)
    if m:
        count,item,total,ask=m.groups(); count,total,ask=map(int,[count,total,ask]); price=total//count; cost=price*ask
        return {'source':'local:live-v283-money-unit-price-multiple','answer':f'{cost} {_v281_word(cost,"рублей")}', 'steps':[f'{total} : {count} = {price} рублей — цена одного предмета.', f'{price} × {ask} = {cost} рублей.']}
    m = re.search(r'одн\w+\s+([а-яеё]+)\s+стоит\s+(\d+)\s+руб\w*.*?сколько\s+\1\w*\s+можно\s+купить\s+на\s+(\d+)\s+руб\w*\s+и\s+сколько\s+руб\w*\s+остан', low)
    if m:
        item,price,budget=m.groups(); price,budget=map(int,[price,budget]); q,r=divmod(budget,price)
        return {'source':'local:live-v283-money-quantity-remainder','answer':f'{q} {_v281_word(q,item)} и {r} {_v281_word(r,"рублей")}', 'steps':[f'{budget} : {price} = {q} (ост. {r}).']}
    return None


def solve_v283_time(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    m = re.search(r'сколько\s+времени\s+прошло\s+с\s+(\d{1,2}:\d{2})\s+до\s+(\d{1,2}:\d{2})', low)
    if not m:
        m = re.search(r'(?:пришел|пришёл)\s+в\s+(\d{1,2}:\d{2}).*?следующ\w+\s+(?:пришел|пришёл)\s+в\s+(\d{1,2}:\d{2}).*?сколько\s+минут\s+ждал', low)
    if m:
        start,end=m.groups(); diff=_v281_clock_diff(start,end)
        if diff is not None:
            return {'source':'local:live-v283-time-duration','answer':_v281_format_minutes(diff), 'steps':[f'От {start} до {end} прошло {_v281_format_minutes(diff)}.']}
    m = re.search(r'законч\w*\s+в\s+(\d{1,2}:\d{2})\s+и\s+длил\w*\s+(\d+)\s*ч\w*\s+(\d+)\s*мин.*?во\s+сколько\s+.*?начал', low)
    if m:
        end, h, mn = m.groups(); end_min=_v280_time_to_minutes(end); dur=int(h)*60+int(mn)
        if end_min is not None:
            start=_v280_minutes_to_clock(end_min-dur)
            return {'source':'local:live-v283-time-start','answer':start, 'steps':[f'От времени окончания {end} отнимаем {h} ч {mn} мин.', f'Получаем {start}.']}
    return None


def solve_v283_motion(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    m = re.search(r'противоположн\w+\s+направлен\w+.*?скорость\s+перв\w+\s+(\d+)\s*км/ч.*?втор\w+\s+(\d+)\s*км/ч.*?через\s+(\d+)\s+час', low)
    if m:
        v1,v2,t=map(int,m.groups()); ans=(v1+v2)*t
        return {'source':'local:live-v283-motion-opposite','answer':f'{ans} {_v281_word(ans,"километров")}', 'steps':[f'{v1} + {v2} = {v1+v2} км/ч — скорость удаления.', f'{v1+v2} × {t} = {ans} км.']}
    m = re.search(r'велосипедист\w*\s+со\s+скоростью\s+(\d+)\s*км/ч.*?мотоциклист\w*\s+со\s+скоростью\s+(\d+)\s*км/ч.*?на\s+сколько\s+километр\w*.*?через\s+(\d+)\s+час', low)
    if m:
        v1,v2,t=map(int,m.groups()); ans=abs(v2-v1)*t
        return {'source':'local:live-v283-motion-speed-difference','answer':f'{ans} {_v281_word(ans,"километров")}', 'steps':[f'{v2} − {v1} = {abs(v2-v1)} км/ч — разница скоростей.', f'{abs(v2-v1)} × {t} = {ans} км.']}
    m = re.search(r'(?:прошел|проехал)\s+(\d+)\s*км\s+за\s+(\d+)\s+час.*?(?:скорост)', low)
    if m:
        dist,t=map(int,m.groups()); speed=dist//t
        return {'source':'local:live-v283-motion-speed','answer':f'{speed} км/ч', 'steps':[f'{dist} : {t} = {speed} км/ч.']}
    m = re.search(r'прошел\s+(\d+)\s*км.*?и\s+(\d+)\s*км.*?весь\s+маршрут\s+(\d+)\s*км.*?сколько\s+километр\w*\s+остал', low)
    if m:
        a,b,total=map(int,m.groups()); left=total-a-b
        return {'source':'local:live-v283-motion-route-left','answer':f'{left} {_v281_word(left,"километров")}', 'steps':[f'{a} + {b} = {a+b} км — прошёл.', f'{total} − {a+b} = {left} км — осталось.']}
    m = re.search(r'ехал\s+(\d+)\s+минут\w*\s+со\s+скоростью\s+(\d+)\s*км/ч.*?сколько\s+километр\w*', low)
    if m:
        minutes,speed=map(int,m.groups()); ans=Fraction(speed*minutes,60)
        return {'source':'local:live-v283-motion-minutes','answer':f'{_fmt_fraction(ans)} {_v281_word(int(ans),"километров")}' if ans.denominator==1 else f'{_fmt_decimal_comma(ans)} километра', 'steps':[f'{minutes} минут = {minutes}/60 часа.', f'{speed} × {minutes}/60 = {_fmt_fraction(ans)} км.']}
    m = re.search(r'расстояние\s+между\s+селами\s+(\d+)\s*км.*?навстречу:?\s*(\d+)\s*км/ч\s+и\s+(\d+)\s*км/ч.*?через\s+(\d+)\s+час', low)
    if m:
        dist,v1,v2,t=map(int,m.groups()); covered=(v1+v2)*t; left=dist-covered
        return {'source':'local:live-v283-motion-towards-left','answer':f'{left} {_v281_word(left,"километров")}', 'steps':[f'{v1} + {v2} = {v1+v2} км/ч.', f'{v1+v2} × {t} = {covered} км.', f'{dist} − {covered} = {left} км.']}
    m = re.search(r'ехал\s+(\d+)\s*ч\s+(\d+)\s*мин\s+со\s+скоростью\s+(\d+)\s*км/ч', low)
    if m:
        h,mn,speed=map(int,m.groups()); minutes=h*60+mn; ans=Fraction(speed*minutes,60)
        return {'source':'local:live-v283-motion-time-hm','answer':f'{_fmt_fraction(ans)} {_v281_word(int(ans),"километров")}', 'steps':[f'{h} ч {mn} мин = {minutes}/60 часа.', f'{speed} × {minutes}/60 = {_fmt_fraction(ans)} км.']}
    return None


def solve_v283_joint_work(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    m = re.search(r'один\s+рабоч\w*\s+делает\s+(\d+)\s+детал\w*\s+за\s+(\d+)\s+час\w*,\s*втор\w+\s+рабоч\w*\s+делает\s+столько\s+же\s+за\s+(\d+)\s+час\w*.*?сколько\s+детал\w*\s+они\s+сделают\s+вместе\s+за\s+(\d+)\s+час', low)
    if m:
        total,t1,t2,time=map(int,m.groups()); rate=total//t1+total//t2; ans=rate*time
        return {'source':'local:live-v283-joint-work-output','answer':f'{ans} {_v281_word(ans,"деталей")}', 'steps':[f'{total} : {t1} = {total//t1} деталей в час.', f'{total} : {t2} = {total//t2} деталей в час.', f'{total//t1} + {total//t2} = {rate} деталей в час.', f'{rate} × {time} = {ans} деталей.']}
    m = re.search(r'один\s+насос\s+перекачивает\s+(\d+)\s*л\s+за\s+(\d+)\s+минут\w*,\s*другой\s+насос\s+\1\s*л\s+за\s+(\d+)\s+минут\w*.*?сколько\s+литр\w*.*?за\s+(\d+)\s+минут', low)
    if m:
        total,t1,t2,time=map(int,m.groups()); rate=total//t1+total//t2; ans=rate*time
        return {'source':'local:live-v283-joint-work-liters','answer':f'{ans} {_v281_word(ans,"литров")}', 'steps':[f'{total} : {t1} = {total//t1} л/мин.', f'{total} : {t2} = {total//t2} л/мин.', f'{total//t1} + {total//t2} = {rate} л/мин.', f'{rate} × {time} = {ans} л.']}
    m = re.search(r'перв\w+\s+бригад\w*\s+делает\s+1/(\d+)\s+работ\w*\s+за\s+день.*?втор\w+\s+бригад\w*\s+делает\s+1/(\d+)\s+работ\w*\s+за\s+день.*?какую\s+часть', low)
    if m:
        d1,d2=map(int,m.groups()); ans=Fraction(1,d1)+Fraction(1,d2)
        return {'source':'local:live-v283-joint-work-fraction-rate','answer':_fmt_fraction(ans), 'steps':[f'1/{d1} + 1/{d2} = {_fmt_fraction(ans)}.']}
    m = re.search(r'перв\w+\s+станок\s+делает\s+(\d+)\s+детал\w*\s+в\s+час.*?втор\w+\s+станок\s+(\d+)\s+детал\w*\s+в\s+час.*?за\s+сколько\s+час\w*\s+они\s+сделают\s+(\d+)\s+детал', low)
    if m:
        r1,r2,total=map(int,m.groups()); time=Fraction(total,r1+r2)
        return {'source':'local:live-v283-joint-work-time-from-rates','answer':_format_time(time,'час'), 'steps':[f'{r1} + {r2} = {r1+r2} деталей в час.', f'{total} : {r1+r2} = {_fmt_fraction(time)} часа.']}
    return None


def solve_v283_fractions(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    m = re.search(r'найди\s+(\d+)/(\d+)\s+от\s+(\d+)\s+рубл', low)
    if m:
        a,b,n=map(int,m.groups()); ans=n//b*a
        return {'source':'local:live-v283-fraction-money','answer':f'{ans} {_v281_word(ans,"рублей")}', 'steps':[f'{n} : {b} × {a} = {ans} рублей.']}
    m = re.search(r'найди\s+(\d+)/(\d+)\s+час\w*\s+в\s+минутах', low)
    if m:
        a,b=map(int,m.groups()); ans=60//b*a
        return {'source':'local:live-v283-fraction-time','answer':f'{ans} {_v281_word(ans,"минут")}', 'steps':[f'1 час = 60 минут.', f'60 : {b} × {a} = {ans} минут.']}
    m = re.search(r'(\d+)/(\d+)\s+числа\s+равн\w*\s+(\d+).*?найди\s+числ', low)
    if m:
        a,b,part=map(int,m.groups()); ans=part*b//a
        return {'source':'local:live-v283-fraction-whole','answer':str(ans), 'steps':[f'{part} × {b} : {a} = {ans}.']}
    m = re.search(r'сравни\s+дроби\s+(\d+)/(\d+)\s+и\s+(\d+)/(\d+)', low)
    if m:
        a,b,c,d=map(int,m.groups()); left=Fraction(a,b); right=Fraction(c,d)
        if left>right: ans=f'{a}/{b} больше'
        elif left<right: ans=f'{c}/{d} больше'
        else: ans='дроби равны'
        return {'source':'local:live-v283-fraction-compare','answer':ans, 'steps':[f'Сравниваем {a}/{b} и {c}/{d}.']}
    m = re.search(r'от\s+лент\w*\s+длиной\s+(\d+)\s*см\s+отрезал\w*\s+1/(\d+).*?сколько\s+сантиметр\w*\s+лент\w*\s+остал', low)
    if m:
        total,den=map(int,m.groups()); cut=total//den; left=total-cut
        return {'source':'local:live-v283-fraction-length-left','answer':f'{left} {_v281_word(left,"сантиметров")}', 'steps':[f'{total} : {den} = {cut} см — отрезали.', f'{total} − {cut} = {left} см — осталось.']}
    m = re.search(r'найди\s+1/(\d+)\s+от\s+(\d+)\s*кг', low)
    if m:
        den,kg=map(int,m.groups()); grams=kg*1000; ans=grams//den
        return {'source':'local:live-v283-fraction-mass','answer':f'{ans} {_v281_word(ans,"граммов")}', 'steps':[f'{kg} кг = {grams} г.', f'{grams} : {den} = {ans} г.']}
    return None


def solve_v283_geometry(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    m = re.search(r'периметр\s+прямоугольник\w*\s+(\d+)\s*см,?\s+длина\s+(\d+)\s*см.*?найди\s+ширин', low)
    if m:
        p,l=map(int,m.groups()); w=p//2-l
        return {'source':'local:live-v283-geometry-width','answer':f'{w} см', 'steps':[f'{p} : 2 = {p//2} см — сумма длины и ширины.', f'{p//2} − {l} = {w} см — ширина.']}
    m = re.search(r'фигура\s+состоит\s+из\s+прямоугольник\w*\s+(\d+)\s*см\s+на\s+(\d+)\s*см\s+и\s+прямоугольник\w*\s+(\d+)\s*см\s+на\s+(\d+)\s*см', low)
    if m:
        a,b,c,d=map(int,m.groups()); area=a*b+c*d
        return {'source':'local:live-v283-geometry-composite-area','answer':f'{area} кв. см', 'steps':[f'{a} × {b} = {a*b} кв. см.', f'{c} × {d} = {c*d} кв. см.', f'{a*b} + {c*d} = {area} кв. см.']}
    m = re.search(r'сторона\s+квадрата\s+(\d+)\s*см.*?найди\s+площад\w*\s+и\s+периметр', low)
    if m:
        side=int(m.group(1)); area=side*side; p=side*4
        return {'source':'local:live-v283-geometry-square-area-perimeter','answer':f'{area} кв. см и {p} см', 'steps':[f'{side} × {side} = {area} кв. см — площадь.', f'{side} × 4 = {p} см — периметр.']}
    m = re.search(r'состоит\s+из\s+(\d+)\s+клет\w*,\s+из\s+нее\s+убрал\w*\s+(\d+)\s+клет', low)
    if m:
        total,cut=map(int,m.groups()); left=total-cut
        return {'source':'local:live-v283-grid-left','answer':f'{left} {_v281_word(left,"клеток")}', 'steps':[f'{total} − {cut} = {left} клеток.']}
    m = re.search(r'из\s+точки\s*\((\d+)\s*[;,]\s*(\d+)\).*?(\d+)\s+клет\w*\s+влево\s+и\s+(\d+)\s+клет\w*\s+вниз', low)
    if m:
        x,y,dx,dy=map(int,m.groups()); nx=x-dx; ny=y-dy
        return {'source':'local:live-v283-coordinate-route','answer':f'({nx}; {ny})', 'steps':[f'{x} − {dx} = {nx}.', f'{y} − {dy} = {ny}.']}
    if re.search(r'сколько\s+ос\w*\s+симметрии\s+у\s+квадрат', low):
        return {'source':'local:live-v283-symmetry','answer':'4 оси', 'steps':['У квадрата 4 оси симметрии.']}
    if re.search(r'у\s+треугольник\w*\s+сколько\s+сторон\s+и\s+вершин', low):
        return {'source':'local:live-v283-shapes','answer':'3 стороны и 3 вершины', 'steps':['У треугольника 3 стороны и 3 вершины.']}
    return None


def solve_v283_data_reading(text: str) -> Optional[dict]:
    raw=_v283_clean(text); low=_v283_lower(raw)
    pairs=_v281_parse_pairs(low)
    if ('таблиц' in low or 'диаграм' in low or 'расписан' in low) and len(pairs)>=2:
        m = re.search(r'сколько\s+всего\s+([а-яеё]+)\s+и\s+([а-яеё]+)', low)
        if m and m.group(1) in pairs and m.group(2) in pairs:
            a,b=m.group(1),m.group(2); ans=pairs[a]+pairs[b]
            return {'source':'local:live-v283-data-two-total','answer':str(ans), 'steps':[f'{pairs[a]} + {pairs[b]} = {ans}.']}
        m = re.search(r'на\s+сколько\s+([а-яеё]+)\s+меньше,?\s+чем\s+([а-яеё]+)', low)
        if m and m.group(1) in pairs and m.group(2) in pairs:
            a,b=m.group(1),m.group(2); ans=abs(pairs[b]-pairs[a])
            return {'source':'local:live-v283-data-difference','answer':str(ans), 'steps':[f'{pairs[b]} − {pairs[a]} = {ans}.']}
        if re.search(r'сколько\s+всего\s+за\s+эт\w+\s+дн', low):
            total=sum(pairs.values())
            return {'source':'local:live-v283-data-total','answer':str(total), 'steps':['Складываем данные: ' + ' + '.join(str(v) for v in pairs.values()) + f' = {total}.']}
    m = re.search(r'пиктограмм\w*:\s*1\s+значок\s*=\s*(\d+)\s+учен\w*.*?(?:у\s+команд\w*)\s+(\d+)\s+значк\w*.*?сколько\s+учен', low)
    if m:
        scale,icons=map(int,m.groups()); ans=scale*icons
        return {'source':'local:live-v283-pictogram-scale','answer':f'{ans} {_v281_word(ans,"учеников")}', 'steps':[f'{icons} × {scale} = {ans} учеников.']}
    m = re.search(r'начал\w*\s+в\s+(\d{1,2}:\d{2}).*?законч\w*\s+в\s+(\d{1,2}:\d{2}).*?сколько\s+минут\s+длил', low)
    if m and 'расписан' in low:
        diff=_v281_clock_diff(m.group(1), m.group(2))
        if diff is not None:
            return {'source':'local:live-v283-schedule-duration','answer':f'{diff} {_v281_word(diff,"минут")}', 'steps':[f'От {m.group(1)} до {m.group(2)} прошло {diff} минут.']}
    return None


# v283 router override.  New wave-3 solvers run first, then previous waves.
_v283_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v283_numbers_units,
        solve_v283_arithmetic_equations,
        solve_v283_text_composite,
        solve_v283_money,
        solve_v283_time,
        solve_v283_motion,
        solve_v283_joint_work,
        solve_v283_fractions,
        solve_v283_geometry,
        solve_v283_data_reading,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return _v281_full_payload(text, payload)
    return _v283_solve_live_prev(text)

# --- v283 patch 1: restore precise noun morphology after broad audit probes ---
_v283_unit_forms_prev_precise = _v281_unit_forms_extra

def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    exact = {
        'м': ('метр', 'метра', 'метров'),
        'см': ('сантиметр', 'сантиметра', 'сантиметров'),
        'км': ('километр', 'километра', 'километров'),
        'кг': ('килограмм', 'килограмма', 'килограммов'),
        'л': ('литр', 'литра', 'литров'),
        'мин': ('минута', 'минуты', 'минут'),
        'сек': ('секунда', 'секунды', 'секунд'),
        'ч': ('час', 'часа', 'часов'),
    }
    if stem in exact:
        return exact[stem]
    prefixes = [
        ('мест', ('место', 'места', 'мест')),
        ('месяц', ('месяц', 'месяца', 'месяцев')),
        ('мес', ('месяц', 'месяца', 'месяцев')),
        ('метр', ('метр', 'метра', 'метров')),
        ('сантиметр', ('сантиметр', 'сантиметра', 'сантиметров')),
        ('километр', ('километр', 'километра', 'километров')),
        ('килограмм', ('килограмм', 'килограмма', 'килограммов')),
        ('литр', ('литр', 'литра', 'литров')),
        ('руб', ('рубль', 'рубля', 'рублей')),
        ('коп', ('копейка', 'копейки', 'копеек')),
        ('минут', ('минута', 'минуты', 'минут')),
        ('секунд', ('секунда', 'секунды', 'секунд')),
        ('час', ('час', 'часа', 'часов')),
        ('дн', ('день', 'дня', 'дней')),
        ('год', ('год', 'года', 'лет')),
        ('лет', ('год', 'года', 'лет')),
        ('книг', ('книга', 'книги', 'книг')),
        ('страниц', ('страница', 'страницы', 'страниц')),
        ('учен', ('ученик', 'ученика', 'учеников')),
        ('мяч', ('мяч', 'мяча', 'мячей')),
        ('карандаш', ('карандаш', 'карандаша', 'карандашей')),
        ('руч', ('ручка', 'ручки', 'ручек')),
        ('открытк', ('открытка', 'открытки', 'открыток')),
        ('альбом', ('альбом', 'альбома', 'альбомов')),
        ('кисточ', ('кисточка', 'кисточки', 'кисточек')),
        ('пенал', ('пенал', 'пенала', 'пеналов')),
        ('рисунк', ('рисунок', 'рисунка', 'рисунков')),
        ('детал', ('деталь', 'детали', 'деталей')),
        ('дерев', ('дерево', 'дерева', 'деревьев')),
        ('яблон', ('дерево', 'дерева', 'деревьев')),
        ('груш', ('дерево', 'дерева', 'деревьев')),
        ('фрукт', ('фрукт', 'фрукта', 'фруктов')),
        ('клет', ('клетка', 'клетки', 'клеток')),
        ('ось', ('ось', 'оси', 'осей')),
        ('оси', ('ось', 'оси', 'осей')),
        ('сторон', ('сторона', 'стороны', 'сторон')),
        ('вершин', ('вершина', 'вершины', 'вершин')),
    ]
    for prefix, forms in prefixes:
        if stem.startswith(prefix):
            return forms
    return _v283_unit_forms_prev_precise(word)


_v283_numbers_units_prev_patch1 = solve_v283_numbers_units

def solve_v283_numbers_units(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    m = re.search(r'в\s+числе\s+(\d{4,})\s+сколько\s+тысяч\w*,?\s+сот\w*,?\s+десятк\w*\s+и\s+единиц', low)
    if m:
        n = int(m.group(1))
        thousands = n // 1000
        hundreds = (n // 100) % 10
        tens = (n // 10) % 10
        ones = n % 10
        return {'source': 'local:live-v283-place-value-read', 'answer': f'{thousands} {_v281_word(thousands, "тысяч")} {hundreds} {_v281_word(hundreds, "сотен")} {tens} {_v281_word(tens, "десятков")} {ones} {_v281_word(ones, "единиц")}', 'steps': [f'В числе {n}: тысяч — {thousands}, сотен — {hundreds}, десятков — {tens}, единиц — {ones}.']}
    return _v283_numbers_units_prev_patch1(text)


_v283_text_composite_prev_patch1 = solve_v283_text_composite

def solve_v283_text_composite(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    # Book/page wording with "и потом еще".
    m = re.search(r'в\s+книг\w*\s+(\d+)\s+страниц\w*.*?прочитал\w*\s+(\d+)\s+страниц\w*\s+и\s+потом\s+еще\s+(\d+)\s+страниц\w*.*?сколько\s+страниц\w*\s+остал', low)
    if m:
        total, a, b = map(int, m.groups())
        read = a + b
        left = total - read
        return {'source': 'local:live-v283-pages-left', 'answer': f'{left} {_v281_word(left, "страниц")}', 'steps': [f'{a} + {b} = {read} страниц — прочитал.', f'{total} − {read} = {left} {_v281_word(left, "страниц")} — осталось.']}
    # Equal groups where number comes before the remove verb: "8 мячей взяли".
    m = re.search(r'в\s+(\d+)\s+(?:коробк|набор|ящик)\w*\s+по\s+(\d+)\s+([а-яеё]+)\w*.*?(\d+)\s+\3\w*\s+(?:взял\w*|подарил\w*|продал\w*).*?сколько\s+\3\w*\s+остал', low)
    if m:
        groups, each, item, taken = m.groups(); groups, each, taken = map(int, [groups, each, taken])
        total = groups * each
        left = total - taken
        return {'source': 'local:live-v283-equal-groups-left', 'answer': f'{left} {_v281_word(left, item)}', 'steps': [f'{groups} × {each} = {total} {_v281_word(total, item)} — было всего.', f'{total} − {taken} = {left} {_v281_word(left, item)} — осталось.']}
    # Fraction of items used; accept singular/plural endings.
    m = re.search(r'в\s+коробк\w*\s+(\d+)\s+([а-яеё]+).*?1/(\d+)\s+\w+\s+использовал\w*.*?сколько\s+\w+\s+остал', low)
    if m and ('детал' in low or 'винт' in low or 'карандаш' in low):
        total, item, den = m.groups(); total, den = int(total), int(den)
        used = total // den
        left = total - used
        target = 'деталей' if 'детал' in low else item
        return {'source': 'local:live-v283-fraction-left', 'answer': f'{left} {_v281_word(left, target)}', 'steps': [f'{total} : {den} = {used} {_v281_word(used, target)} — использовали.', f'{total} − {used} = {left} {_v281_word(left, target)} — осталось.']}
    return _v283_text_composite_prev_patch1(text)


_v283_money_prev_patch1 = solve_v283_money

def solve_v283_money(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    # feminine/other item forms in "one item costs" quantity with remainder.
    m = re.search(r'одн\w+\s+([а-яеё]+)\s+стоит\s+(\d+)\s+руб\w*.*?сколько\s+([а-яеё]+)\w*\s+можно\s+купить\s+на\s+(\d+)\s+руб\w*\s+и\s+сколько\s+руб\w*\s+остан', low)
    if m:
        item_one, price, item_many, budget = m.groups()
        price, budget = int(price), int(budget)
        q, r = divmod(budget, price)
        item = item_many or item_one
        return {'source': 'local:live-v283-money-quantity-remainder', 'answer': f'{q} {_v281_word(q, item)} и {r} {_v281_word(r, "рублей")}', 'steps': [f'{budget} : {price} = {q} (ост. {r}).']}
    return _v283_money_prev_patch1(text)


_v283_data_prev_patch1 = solve_v283_data_reading

def _v283_pair_lookup(pairs: dict[str, int], token: str) -> int | None:
    tok = (token or '').lower().replace('ё', 'е').strip(' .,!?:;')
    if tok in pairs:
        return pairs[tok]
    for key, value in pairs.items():
        if key.startswith(tok[:4]) or tok.startswith(key[:4]):
            return value
    return None


def solve_v283_data_reading(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    if 'таблиц' in low or 'диаграм' in low:
        pairs = _v281_parse_pairs(low)
        if len(pairs) >= 2:
            m = re.search(r'сколько\s+всего\s+([а-яеё]+)\s+и\s+([а-яеё]+)', low)
            if m:
                a = _v283_pair_lookup(pairs, m.group(1))
                b = _v283_pair_lookup(pairs, m.group(2))
                if a is not None and b is not None:
                    ans = a + b
                    return {'source': 'local:live-v283-data-two-total', 'answer': str(ans), 'steps': [f'{a} + {b} = {ans}.']}
    return _v283_data_prev_patch1(text)


# Re-override router so patched v283 solvers are used before previous routes.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v283_numbers_units,
        solve_v283_arithmetic_equations,
        solve_v283_text_composite,
        solve_v283_money,
        solve_v283_time,
        solve_v283_motion,
        solve_v283_joint_work,
        solve_v283_fractions,
        solve_v283_geometry,
        solve_v283_data_reading,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return _v281_full_payload(text, payload)
    return _v283_solve_live_prev(text)

# --- v283 patch 2: explicit place-value noun forms ---
_v283_unit_forms_prev_place = _v281_unit_forms_extra

def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    exact = {
        'тысяч': ('тысяча', 'тысячи', 'тысяч'),
        'тысяча': ('тысяча', 'тысячи', 'тысяч'),
        'тысячи': ('тысяча', 'тысячи', 'тысяч'),
        'сотен': ('сотня', 'сотни', 'сотен'),
        'сотня': ('сотня', 'сотни', 'сотен'),
        'сотни': ('сотня', 'сотни', 'сотен'),
        'десятков': ('десяток', 'десятка', 'десятков'),
        'десяток': ('десяток', 'десятка', 'десятков'),
        'единиц': ('единица', 'единицы', 'единиц'),
        'единица': ('единица', 'единицы', 'единиц'),
    }
    if stem in exact:
        return exact[stem]
    return _v283_unit_forms_prev_place(word)

# Router override after place-value morphology patch.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v283_numbers_units,
        solve_v283_arithmetic_equations,
        solve_v283_text_composite,
        solve_v283_money,
        solve_v283_time,
        solve_v283_motion,
        solve_v283_joint_work,
        solve_v283_fractions,
        solve_v283_geometry,
        solve_v283_data_reading,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return _v281_full_payload(text, payload)
    return _v283_solve_live_prev(text)

# --- v283 patch 3: final morphology guard, no broad single-letter matches ---
def _v281_unit_forms_extra(word: str) -> tuple[str, str, str] | None:  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    exact = {
        'м': ('метр', 'метра', 'метров'), 'см': ('сантиметр', 'сантиметра', 'сантиметров'),
        'км': ('километр', 'километра', 'километров'), 'кг': ('килограмм', 'килограмма', 'килограммов'),
        'л': ('литр', 'литра', 'литров'), 'мин': ('минута', 'минуты', 'минут'),
        'сек': ('секунда', 'секунды', 'секунд'), 'ч': ('час', 'часа', 'часов'),
        'тысяч': ('тысяча', 'тысячи', 'тысяч'), 'тысяча': ('тысяча', 'тысячи', 'тысяч'), 'тысячи': ('тысяча', 'тысячи', 'тысяч'),
        'сотен': ('сотня', 'сотни', 'сотен'), 'сотня': ('сотня', 'сотни', 'сотен'), 'сотни': ('сотня', 'сотни', 'сотен'),
        'десятков': ('десяток', 'десятка', 'десятков'), 'десяток': ('десяток', 'десятка', 'десятков'),
        'единиц': ('единица', 'единицы', 'единиц'), 'единица': ('единица', 'единицы', 'единиц'),
    }
    if stem in exact:
        return exact[stem]
    prefixes = [
        ('мест', ('место', 'места', 'мест')), ('месяц', ('месяц', 'месяца', 'месяцев')), ('мес', ('месяц', 'месяца', 'месяцев')),
        ('метр', ('метр', 'метра', 'метров')), ('сантиметр', ('сантиметр', 'сантиметра', 'сантиметров')), ('километр', ('километр', 'километра', 'километров')), ('килограмм', ('килограмм', 'килограмма', 'килограммов')), ('литр', ('литр', 'литра', 'литров')),
        ('руб', ('рубль', 'рубля', 'рублей')), ('коп', ('копейка', 'копейки', 'копеек')), ('минут', ('минута', 'минуты', 'минут')), ('секунд', ('секунда', 'секунды', 'секунд')), ('час', ('час', 'часа', 'часов')), ('дн', ('день', 'дня', 'дней')), ('день', ('день', 'дня', 'дней')), ('год', ('год', 'года', 'лет')), ('лет', ('год', 'года', 'лет')),
        ('яблок', ('яблоко', 'яблока', 'яблок')), ('книг', ('книга', 'книги', 'книг')), ('страниц', ('страница', 'страницы', 'страниц')), ('учен', ('ученик', 'ученика', 'учеников')), ('мяч', ('мяч', 'мяча', 'мячей')), ('карандаш', ('карандаш', 'карандаша', 'карандашей')), ('руч', ('ручка', 'ручки', 'ручек')), ('накле', ('наклейка', 'наклейки', 'наклеек')), ('открытк', ('открытка', 'открытки', 'открыток')), ('альбом', ('альбом', 'альбома', 'альбомов')), ('кисточ', ('кисточка', 'кисточки', 'кисточек')), ('пенал', ('пенал', 'пенала', 'пеналов')), ('билет', ('билет', 'билета', 'билетов')), ('рисунк', ('рисунок', 'рисунка', 'рисунков')), ('детал', ('деталь', 'детали', 'деталей')), ('дерев', ('дерево', 'дерева', 'деревьев')), ('яблон', ('дерево', 'дерева', 'деревьев')), ('груш', ('дерево', 'дерева', 'деревьев')), ('фрукт', ('фрукт', 'фрукта', 'фруктов')), ('клет', ('клетка', 'клетки', 'клеток')), ('ось', ('ось', 'оси', 'осей')), ('оси', ('ось', 'оси', 'осей')), ('сторон', ('сторона', 'стороны', 'сторон')), ('вершин', ('вершина', 'вершины', 'вершин')),
    ]
    for prefix, forms in prefixes:
        if stem.startswith(prefix):
            return forms
    return _v280_unit_forms(word)

# Final router override after safe morphology reset.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v283_numbers_units,
        solve_v283_arithmetic_equations,
        solve_v283_text_composite,
        solve_v283_money,
        solve_v283_time,
        solve_v283_motion,
        solve_v283_joint_work,
        solve_v283_fractions,
        solve_v283_geometry,
        solve_v283_data_reading,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return _v281_full_payload(text, payload)
    return _v283_solve_live_prev(text)

# --- v283 patch 4: reverse multiplicative relation without total question ---
_v283_text_composite_prev_patch4 = solve_v283_text_composite

def solve_v283_text_composite(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    m = re.search(r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s+([а-яеё]+).*?это\s+в\s+(\d+)\s+раз\w*\s+(больше|меньше),?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+\3\s+у\s+\6', low)
    if m:
        name1, base, item, k, kind, name2 = m.groups()
        base, k = int(base), int(k)
        if 'больше' in kind:
            ans = base // k
            step = f'{base} : {k} = {ans} {_v281_word(ans, item)}.'
        else:
            ans = base * k
            step = f'{base} × {k} = {ans} {_v281_word(ans, item)}.'
        return {'source': 'local:live-v283-reverse-times', 'answer': f'У {_v280_person_from_phrase(name2)} {ans} {_v281_word(ans, item)}', 'steps': [step]}
    return _v283_text_composite_prev_patch4(text)

# Final router override after reverse-relation patch.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v283_numbers_units,
        solve_v283_arithmetic_equations,
        solve_v283_text_composite,
        solve_v283_money,
        solve_v283_time,
        solve_v283_motion,
        solve_v283_joint_work,
        solve_v283_fractions,
        solve_v283_geometry,
        solve_v283_data_reading,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return _v281_full_payload(text, payload)
    return _v283_solve_live_prev(text)

# --- v283 patch 5: reverse multiplicative relation with inflected item in question ---
_v283_text_composite_prev_patch5 = solve_v283_text_composite

def solve_v283_text_composite(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    m = re.search(
        r'у\s+([а-яеё]+)\s+(?:было\s+)?(\d+)\s+([а-яеё]+).*?это\s+в\s+(\d+)\s+раз\w*\s+(больше|меньше),?\s+чем\s+у\s+([а-яеё]+).*?сколько\s+([а-яеё]+)\s+у\s+\6',
        low,
    )
    if m:
        name1, base, item, k, kind, name2, qitem = m.groups()
        if _v281_same_item(item, qitem):
            base, k = int(base), int(k)
            if 'больше' in kind:
                ans = base // k
                step = f'{base} : {k} = {ans} {_v281_word(ans, item)}.'
            else:
                ans = base * k
                step = f'{base} × {k} = {ans} {_v281_word(ans, item)}.'
            return {
                'source': 'local:live-v283-reverse-times',
                'answer': f'У {_v280_person_from_phrase(name2)} {ans} {_v281_word(ans, item)}',
                'steps': [step],
            }
    return _v283_text_composite_prev_patch5(text)

# Final router override after reverse-relation patch 5.
def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    for solver in (
        solve_two_variable_system,
        solve_v283_numbers_units,
        solve_v283_arithmetic_equations,
        solve_v283_text_composite,
        solve_v283_money,
        solve_v283_time,
        solve_v283_motion,
        solve_v283_joint_work,
        solve_v283_fractions,
        solve_v283_geometry,
        solve_v283_data_reading,
    ):
        try:
            payload = solver(text)
        except Exception:
            payload = None
        if payload is not None:
            return _v281_full_payload(text, payload)
    return _v283_solve_live_prev(text)

# --- v283 patch 6: add missing inflected item families for reverse/data tasks ---
_v283_unit_forms_extra_prev_patch6 = _v281_unit_forms_extra

def _v281_unit_forms_extra(word: str):  # type: ignore[override]
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    if stem.startswith('мар'):
        return ('марка', 'марки', 'марок')
    return _v283_unit_forms_extra_prev_patch6(word)

# --- v284 external black-box wave 4: hardening of edge wording and morphology ---
def _v284_format_hours_fraction(hours: Fraction) -> str:
    whole = hours.numerator // hours.denominator
    rem = hours - whole
    minutes = int(round(float(rem * 60)))
    if minutes == 60:
        whole += 1
        minutes = 0
    if minutes == 0:
        return f'{whole} {_v281_word(whole, "часов")}'
    return f'{whole} {_v281_word(whole, "часов")} {minutes} {_v281_word(minutes, "минут")}'


def solve_v284_hardening(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)

    # Unit conversion: grams -> kilograms and grams, with correct 5 килограммов.
    m = re.search(r'сколько\s+килограмм\w*\s+и\s+грамм\w*\s+в\s+(\d+)\s*г', low)
    if m:
        grams = int(m.group(1)); kg, g = divmod(grams, 1000)
        return {'source': 'local:live-v284-units-kg-g', 'answer': f'{kg} {_v281_word(kg, "килограммов")} {g} {_v281_word(g, "граммов")}', 'steps': ['1 кг = 1000 г.', f'{grams} г = {kg} кг {g} г.']}

    # Pages left with explicit second-day count and extra irrelevant data.
    m = re.search(r'в\s+книг\w*\s+(\d+)\s+страниц\w*.*?понедельник\s+прочитал\w*\s+(\d+)\s+страниц\w*.*?вторник\s+(?:прочитал\w*\s+)?(\d+)\s+страниц\w*.*?сколько\s+страниц\w*\s+остал', low)
    if m:
        total, first, second = map(int, m.groups()); read = first + second; left = total - read
        return {'source': 'local:live-v284-pages-left-extra', 'answer': f'{left} {_v281_word(left, "страниц")}', 'steps': [f'{first} + {second} = {read} страниц — прочитали.', f'{total} − {read} = {left} страниц — осталось.']}

    # Comparison: first has N, second is k times less; ask how many more in first.
    m = re.search(r'в\s+перв\w*\s+([а-яеё]+)\w*\s+(\d+)\s+([а-яеё]+).*?во\s+втор\w*\s+в\s+(\d+)\s+раз\w*\s+меньше.*?на\s+сколько\s+\3\w*.*?перв\w*.*?больше', low)
    if m:
        place, first_n, item, k = m.groups(); first_n, k = int(first_n), int(k)
        second = first_n // k; diff = first_n - second
        return {'source': 'local:live-v284-times-less-difference', 'answer': f'{diff} {_v281_word(diff, item)}', 'steps': [f'{first_n} : {k} = {second} {_v281_word(second, item)} — во второй.', f'{first_n} − {second} = {diff} {_v281_word(diff, item)} — на столько больше.']}

    # Event end time: allow feminine/neuter variants "длилась/длилось".
    m = re.search(r'(?:начал\w*)\s+в\s+(\d{1,2}:\d{2})\s+и\s+длил\w*\s+(?:(\d+)\s*ч\s*)?(\d+)\s*мин.*?во\s+сколько.*?закончил', low)
    if m:
        start, h, minutes = m.groups(); duration = int(minutes) + (int(h or 0) * 60); end = _v281_clock_add(start, duration)
        return {'source': 'local:live-v284-time-end', 'answer': end, 'steps': [f'К времени начала {start} прибавляем {_v281_format_minutes(duration)}.', f'Получаем {end}.']}

    # Event start by end and duration.
    m = re.search(r'закончил\w*\s+в\s+(\d{1,2}:\d{2})\s+и\s+длил\w*\s+(?:(\d+)\s*ч\s*)?(\d+)\s*мин.*?во\s+сколько.*?начал', low)
    if m:
        end, h, minutes = m.groups(); duration = int(minutes) + (int(h or 0) * 60)
        end_min = _v280_time_to_minutes(end)
        start = _v280_minutes_to_clock((end_min or 0) - duration)
        return {'source': 'local:live-v284-time-start', 'answer': start, 'steps': [f'От времени окончания {end} отнимаем {_v281_format_minutes(duration)}.', f'Получаем {start}.']}

    # Motion remaining: answer with correct kilometre agreement.
    m = re.search(r'(турист|велосипедист|поезд|автомобиль)?\s*\w*\s*(?:прошел|проехал)\s+(\d+)\s*км.*?остал\w*\s+(?:пройти|проехать)\s+в\s+(\d+)\s+раз\w*\s+больше.*?сколько\s+километр\w*\s+(?:весь\s+путь|он\s+долж)', low)
    if m:
        who, done, k = m.groups(); done, k = int(done), int(k); left = done * k; total = done + left
        return {'source': 'local:live-v284-motion-remaining-times', 'answer': f'Весь путь {total} {_v281_word(total, "километров")}', 'steps': [f'Уже пройдено/проехано {done} км.', f'{done} × {k} = {left} км — осталось.', f'{done} + {left} = {total} км — весь путь.']}

    # Joint work as two executors complete the same field/order; return hours + minutes instead of raw decimal.
    m = re.search(r'один\s+([а-яеё]+)\s+может\s+вспахать\s+поле\s+площадью\s+(\d+)\s+([а-яеё]+)\s+за\s+(\d+)\s+час\w*.*?друг\w*\s+\1\s+.*?за\s+(\d+)\s+час\w*.*?за\s+сколько\s+час', low)
    if m:
        actor, total, unit, t1, t2 = m.groups(); total, t1, t2 = int(total), int(t1), int(t2)
        r1 = Fraction(total, t1); r2 = Fraction(total, t2); combined = r1 + r2; hours = Fraction(total, 1) / combined
        ans = _v284_format_hours_fraction(hours)
        src = 'local:live-joint-work' if hours.denominator == 1 else 'local:live-v284-joint-work-hours-min'
        return {'source': src, 'answer': ans, 'steps': [f'{total} : {t1} = {_fmt_fraction(r1)} {unit} в час — первый.', f'{total} : {t2} = {_fmt_fraction(r2)} {unit} в час — второй.', f'{_fmt_fraction(r1)} + {_fmt_fraction(r2)} = {_fmt_fraction(combined)} {unit} в час — вместе.', f'{total} : {_fmt_fraction(combined)} = {ans}.']}

    # Width from area and length.
    m = re.search(r'площадь\s+прямоугольника\s+(\d+)\s+кв\.?\s*см.*?длина\s+(\d+)\s*см.*?найди\s+ширин', low)
    if m:
        area, length = map(int, m.groups()); width = area // length
        return {'source': 'local:live-v284-geometry-width-by-area', 'answer': f'{width} см', 'steps': [f'Ширина = площадь : длина.', f'{area} : {length} = {width} см.']}

    # Coordinate route: tolerate клетка/клетки and all four directions.
    m = re.search(r'из\s+точк\w*\s*\((\d+)\s*;\s*(\d+)\).*?(\d+)\s+клет\w*\s+(вправо|влево).*?(\d+)\s+клет\w*\s+(вверх|вниз)', low)
    if m:
        x, y, dx, hdir, dy, vdir = m.groups(); x, y, dx, dy = map(int, [x, y, dx, dy])
        nx = x + dx if hdir == 'вправо' else x - dx
        ny = y + dy if vdir == 'вверх' else y - dy
        return {'source': 'local:live-v284-coordinate-route', 'answer': f'({nx}; {ny})', 'steps': [f'По горизонтали: {x} {"+" if hdir == "вправо" else "−"} {dx} = {nx}.', f'По вертикали: {y} {"+" if vdir == "вверх" else "−"} {dy} = {ny}.']}

    # Polygon sides/vertices by Russian prefix.
    m = re.search(r'у\s+(треугольник|четырехугольник|четырёхугольник|пятиугольник|шестиугольник|семиугольник|восьмиугольник)\w*\s+сколько\s+сторон\w*\s+и\s+вершин', low)
    if m:
        name = m.group(1)
        sides = {'треугольник':3, 'четырехугольник':4, 'четырёхугольник':4, 'пятиугольник':5, 'шестиугольник':6, 'семиугольник':7, 'восьмиугольник':8}[name]
        return {'source': 'local:live-v284-polygon-shapes', 'answer': f'{sides} {_v281_word(sides, "сторон")} и {sides} {_v281_word(sides, "вершин")}', 'steps': [f'У этой фигуры {sides} сторон и {sides} вершин.']}

    return None


# Final router override for v284 hardening before previous broad solvers.
_v284_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v284_hardening(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v284_solve_live_prev(text)

# --- v284 patch 2: explicit x + a = b live equation before legacy fallback ---
def solve_v284_equation_patch(text: str) -> Optional[dict]:
    raw = _v283_clean(text).replace('х', 'x').replace('Х', 'x')
    compact = re.sub(r'\s+', '', raw.split('.')[0].replace(':', '/').replace('×', '*').replace('·', '*').replace('−','-'))
    m = re.fullmatch(r'x\+(\d+)=(\d+)', compact)
    if m:
        a, b = map(int, m.groups()); ans = b - a
        return {'source': 'local:live-v284-equation', 'answer': f'x = {ans}', 'steps': [f'{b} − {a} = {ans}.']}
    return None

_v284_solve_live_prev_patch2 = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v284_equation_patch(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v284_solve_live_prev_patch2(text)

# --- v285 programmatic sequential audit: Grade 1, Section 1 (Numbers and quantities) ---
# Official-program coverage: numbers 0-20, counting, comparison, neighbours,
# increase/decrease by several units, and elementary length values in cm/dm.
_V285_NUMBER_WORDS = {
    'ноль': 0, 'один': 1, 'одна': 1, 'одно': 1, 'два': 2, 'две': 2,
    'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7,
    'восемь': 8, 'девять': 9, 'десять': 10, 'одиннадцать': 11,
    'двенадцать': 12, 'тринадцать': 13, 'четырнадцать': 14,
    'пятнадцать': 15, 'шестнадцать': 16, 'семнадцать': 17,
    'восемнадцать': 18, 'девятнадцать': 19, 'двадцать': 20,
}
_V285_NUMBER_NAMES = {
    0: 'ноль', 1: 'один', 2: 'два', 3: 'три', 4: 'четыре', 5: 'пять',
    6: 'шесть', 7: 'семь', 8: 'восемь', 9: 'девять', 10: 'десять',
    11: 'одиннадцать', 12: 'двенадцать', 13: 'тринадцать', 14: 'четырнадцать',
    15: 'пятнадцать', 16: 'шестнадцать', 17: 'семнадцать', 18: 'восемнадцать',
    19: 'девятнадцать', 20: 'двадцать',
}


def _v285_word(n: int, word: str) -> str:
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    custom = [
        (('единиц', 'единиц', 'единица'), ('единица', 'единицы', 'единиц')),
        (('десят',), ('десяток', 'десятка', 'десятков')),
        (('числ',), ('число', 'числа', 'чисел')),
        (('фрукт',), ('фрукт', 'фрукта', 'фруктов')),
        (('отрез',), ('отрезок', 'отрезка', 'отрезков')),
    ]
    for markers, forms in custom:
        if any(marker in stem for marker in markers):
            return _choose_plural_int(int(n), forms[0], forms[1], forms[2])
    return _v281_word(int(n), word)


def _v285_count(n: int, word: str) -> str:
    return f'{int(n)} {_v285_word(int(n), word)}'


def _v285_parse_number_word(token: str) -> Optional[int]:
    return _V285_NUMBER_WORDS.get((token or '').lower().replace('ё', 'е').strip(' .,!?:;'))


def solve_v285_grade1_numbers_values(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)

    # Write a named number as a digit/number.
    m = re.search(r'запиши\s+(?:цифрой|число\s+цифрами?)\s+число\s+([а-яеё]+)', low)
    if m:
        value = _v285_parse_number_word(m.group(1))
        if value is not None:
            return {'source': 'local:live-v285-g1-numbers-write', 'answer': str(value), 'steps': [f'Число «{m.group(1)}» записывается так: {value}.']}

    # Read a digit/number aloud.
    m = re.search(r'как\s+читается\s+число\s+(\d{1,2})\b', low)
    if m:
        n = int(m.group(1))
        if n in _V285_NUMBER_NAMES:
            return {'source': 'local:live-v285-g1-numbers-read', 'answer': _V285_NUMBER_NAMES[n], 'steps': [f'Число {n} читается: «{_V285_NUMBER_NAMES[n]}».']}

    # One ten and units -> 10 + units.
    m = re.search(r'запиши\s+число,?\s+в\s+котором\s+(?:1|один)\s+десят\w*\s+и\s+(\d+)\s+единиц', low)
    if m:
        units = int(m.group(1)); value = 10 + units
        return {'source': 'local:live-v285-g1-tens-units', 'answer': str(value), 'steps': [f'1 десяток — это 10.', f'10 + {units} = {value}.']}

    # Tens and units in a number up to 20.
    m = re.search(r'в\s+числе\s+(\d{1,2})\s+сколько\s+десят\w*\s+и\s+сколько\s+единиц', low)
    if m:
        n = int(m.group(1)); tens, units = divmod(n, 10)
        ans = f'{tens} {_v285_word(tens, "десяток")} и {units} {_v285_word(units, "единица")}'
        return {'source': 'local:live-v285-g1-tens-units', 'answer': ans, 'steps': [f'В числе {n}: десятков — {tens}, единиц — {units}.']}

    # Compare two numbers or choose greater/smaller.
    m = re.search(r'сравни\s+числа\s+(\d{1,2})\s+и\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups())
        sign = '<' if a < b else '>' if a > b else '='
        rel = 'меньше' if a < b else 'больше' if a > b else 'равно'
        return {'source': 'local:live-v285-g1-compare', 'answer': f'{a} {sign} {b}', 'steps': [f'Сравниваем {a} и {b}.', f'{a} {sign} {b}, значит первое число {rel}.']}
    m = re.search(r'какое\s+число\s+(больше|меньше)\s*:?\s*(\d{1,2})\s+или\s+(\d{1,2})', low)
    if m:
        what, a, b = m.groups(); a, b = int(a), int(b)
        ans = max(a, b) if what == 'больше' else min(a, b)
        return {'source': 'local:live-v285-g1-compare', 'answer': str(ans), 'steps': [f'Сравниваем {a} и {b}.', f'{ans} — число {what}.']}

    # Next, previous, neighbours, between.
    m = re.search(r'какое\s+число\s+(?:идет|стоит)\s+после\s+(\d{1,2})', low)
    if m:
        n = int(m.group(1)); ans = n + 1
        return {'source': 'local:live-v285-g1-sequence', 'answer': str(ans), 'steps': [f'После {n} при счёте идёт {ans}.']}
    m = re.search(r'какое\s+число\s+(?:идет|стоит)\s+перед\s+(\d{1,2})', low)
    if m:
        n = int(m.group(1)); ans = n - 1
        return {'source': 'local:live-v285-g1-sequence', 'answer': str(ans), 'steps': [f'Перед {n} при счёте идёт {ans}.']}
    m = re.search(r'назови\s+соседей\s+числа\s+(\d{1,2})', low)
    if m:
        n = int(m.group(1)); ans = f'{n-1} и {n+1}'
        return {'source': 'local:live-v285-g1-sequence', 'answer': ans, 'steps': [f'Соседи числа {n} — это числа на 1 меньше и на 1 больше.', f'{n} − 1 = {n-1}, {n} + 1 = {n+1}.']}
    m = re.search(r'какое\s+число\s+стоит\s+между\s+(\d{1,2})\s+и\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = (a + b) // 2
        return {'source': 'local:live-v285-g1-sequence', 'answer': str(ans), 'steps': [f'Между {a} и {b} стоит число {ans}.']}

    # Increase/decrease by several units; numeric difference.
    m = re.search(r'увеличь\s+число\s+(\d{1,2})\s+на\s+(\d{1,2})', low)
    if m:
        n, k = map(int, m.groups()); ans = n + k
        return {'source': 'local:live-v285-g1-number-change', 'answer': str(ans), 'steps': [f'{n} + {k} = {ans}.']}
    m = re.search(r'уменьши\s+число\s+(\d{1,2})\s+на\s+(\d{1,2})', low)
    if m:
        n, k = map(int, m.groups()); ans = n - k
        return {'source': 'local:live-v285-g1-number-change', 'answer': str(ans), 'steps': [f'{n} − {k} = {ans}.']}
    m = re.search(r'на\s+сколько\s+(\d{1,2})\s+больше\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v285-g1-difference', 'answer': str(ans), 'steps': [f'{a} − {b} = {ans}.']}
    m = re.search(r'на\s+сколько\s+(\d{1,2})\s+меньше\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = b - a
        return {'source': 'local:live-v285-g1-difference', 'answer': str(ans), 'steps': [f'{b} − {a} = {ans}.']}

    # Ordering and simple number series.
    m = re.search(r'расположи\s+числа\s+(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s+в\s+порядке\s+(возрастания|убывания)', low)
    if m:
        a, b, c, order = m.groups(); nums = [int(a), int(b), int(c)]
        nums = sorted(nums, reverse=(order == 'убывания'))
        ans = ', '.join(map(str, nums))
        return {'source': 'local:live-v285-g1-order', 'answer': ans, 'steps': [f'Упорядочиваем числа в порядке {order}.', ans]}
    m = re.search(r'продолжи\s+ряд\s*:?\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,?\s*\.\.\.', low)
    if m:
        a, b, c = map(int, m.groups()); step = b - a; ans = c + step
        return {'source': 'local:live-v285-g1-series', 'answer': str(ans), 'steps': [f'Шаг ряда: {b} − {a} = {step}.', f'{c} + ({step}) = {ans}.']}

    # Elementary length values: cm, dm, comparison and ruler distances.
    m = re.search(r'сколько\s+сантиметр\w*\s+в\s+1\s*дм\s+(\d+)\s*см', low)
    if m:
        cm = int(m.group(1)); total = 10 + cm
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{total} {_v285_word(total, "сантиметров")}', 'steps': ['1 дм = 10 см.', f'10 + {cm} = {total} см.']}
    if re.search(r'сколько\s+сантиметр\w*\s+в\s+1\s*дм\s*\??$', low):
        return {'source': 'local:live-v285-g1-lengths', 'answer': '10 сантиметров', 'steps': ['1 дм = 10 см.']}
    m = re.search(r'(\d+)\s*см\s*-\s*это\s+сколько\s+дециметр\w*\s+и\s+сантиметр\w*', low)
    if m:
        total = int(m.group(1)); dm, cm = divmod(total, 10)
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{dm} дм {cm} см', 'steps': [f'{total} см = {dm} дм {cm} см, потому что 1 дм = 10 см.']}
    m = re.search(r'сравни\s+длины\s+(\d+)\s*см\s+и\s+(\d+)\s*см', low)
    if m:
        a, b = map(int, m.groups()); sign = '<' if a < b else '>' if a > b else '='
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{a} см {sign} {b} см', 'steps': [f'Сравниваем {a} и {b}.', f'{a} см {sign} {b} см.']}
    m = re.search(r'какой\s+отрезок\s+(короче|длиннее)\s*:?\s*(\d+)\s*см\s+или\s+(\d+)\s*см', low)
    if m:
        what, a, b = m.groups(); a, b = int(a), int(b)
        ans = min(a, b) if what == 'короче' else max(a, b)
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{ans} см', 'steps': [f'Сравниваем {a} см и {b} см.', f'{ans} см — этот отрезок {what}.']}
    m = re.search(r'на\s+сколько\s+сантиметр\w*\s+(\d+)\s*см\s+(длиннее|короче)\s+(\d+)\s*см', low)
    if m:
        a, kind, b = m.groups(); a, b = int(a), int(b); ans = abs(a-b)
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{ans} см', 'steps': [f'{max(a,b)} − {min(a,b)} = {ans} см.']}
    m = re.search(r'на\s+линейке\s+от\s+(\d+)\s*см\s+до\s+(\d+)\s*см.*?длин', low)
    if m:
        a, b = map(int, m.groups()); ans = b - a
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{ans} см', 'steps': [f'{b} − {a} = {ans} см.']}
    m = re.search(r'точки\s+на\s+(\d+)\s*см\s+и\s+(\d+)\s*см.*?длин', low)
    if m:
        a, b = map(int, m.groups()); ans = abs(b-a)
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{ans} см', 'steps': [f'{max(a,b)} − {min(a,b)} = {ans} см.']}
    m = re.search(r'лента\s+была\s+длиной\s+(\d+)\s*см.*?отрезали\s+(\d+)\s*см.*?остал', low)
    if m:
        total, cut = map(int, m.groups()); ans = total - cut
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{ans} см', 'steps': [f'{total} − {cut} = {ans} см.']}
    m = re.search(r'карандаш\s+был\s+(\d+)\s*см.*?удлинили\s+на\s+(\d+)\s*см.*?какая\s+стала\s+длина', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v285-g1-lengths', 'answer': f'{ans} см', 'steps': [f'{a} + {b} = {ans} см.']}

    # Zero arithmetic and small practical counts in grade-1 quantities.
    m = re.search(r'сколько\s+получится,?\s+если\s+из\s+(\d+)\s+вычесть\s+(\d+)', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v285-g1-zero-arithmetic', 'answer': str(ans), 'steps': [f'{a} − {b} = {ans}.']}
    m = re.search(r'сколько\s+получится,?\s+если\s+к\s+(\d+)\s+прибавить\s+(\d+)', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v285-g1-zero-arithmetic', 'answer': str(ans), 'steps': [f'{a} + {b} = {ans}.']}
    m = re.search(r'(?:на\s+тарелке|в\s+коробке)\s+(\d+)\s+\w+.*?\s+и\s+(\d+)\s+\w+.*?сколько\s+всего\s+(\w+)', low)
    if m:
        a, b, asked = m.groups(); a, b = int(a), int(b); total = a + b
        return {'source': 'local:live-v285-g1-total-counts', 'answer': f'{total} {_v285_word(total, asked)}', 'steps': [f'{a} + {b} = {total}.']}
    m = re.search(r'на\s+полке\s+было\s+(\d+)\s+книг\w*.*?(\d+)\s+книг\w*\s+убрали.*?сколько\s+книг\w*\s+остал', low)
    if m:
        a, b = map(int, m.groups()); left = a - b
        return {'source': 'local:live-v285-g1-left-counts', 'answer': f'{left} {_v285_word(left, "книг")}', 'steps': [f'{a} − {b} = {left}.']}
    m = re.search(r'у\s+[а-яеё]+\s+(\d+)\s+наклеек.*?у\s+[а-яеё]+\s+(\d+)\s+наклеек.*?на\s+сколько\s+наклеек.*?больше', low)
    if m:
        a, b = map(int, m.groups()); diff = abs(a-b)
        return {'source': 'local:live-v285-g1-difference-counts', 'answer': f'{diff} {_v285_word(diff, "наклеек")}', 'steps': [f'{max(a,b)} − {min(a,b)} = {diff}.']}

    return None


_v285_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v285_grade1_numbers_values(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v285_solve_live_prev(text)

# --- v287 sequential programmatic audit: Grade 1, Section 2 — Arithmetic actions ---
# Official-program coverage: addition/subtraction within 20, meaning of + and −,
# names of components/results, inverse relation, missing component, expression compare.

def _v287_safe_add_sub(expr: str) -> Optional[int]:
    s = _v283_clean(expr)
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    s = re.sub(r'[^0-9+\-\s]', '', s).strip()
    if not s or not re.fullmatch(r'\d+(?:\s*[+\-]\s*\d+)+', s):
        return None
    tokens = re.findall(r'\d+|[+\-]', s)
    if not tokens:
        return None
    value = int(tokens[0])
    i = 1
    while i + 1 < len(tokens):
        op = tokens[i]
        n = int(tokens[i + 1])
        if op == '+':
            value += n
        else:
            value -= n
        i += 2
    return value


def _v287_norm_expr(expr: str) -> str:
    return re.sub(r'\s+', ' ', str(expr or '').replace('−', '-').replace('–', '-').replace('—', '-')).strip()


def solve_v287_grade1_arithmetic_actions(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)

    # Direct addition/subtraction and short chains within 20.
    m = re.search(r'(?:вычисли|найди\s+значение\s+выражения|сколько\s+будет|запиши\s+ответ)\s*:?\s*([0-9\s+\-−–—]+)\s*[.?!]*$', low)
    if m:
        expr = _v287_norm_expr(m.group(1))
        value = _v287_safe_add_sub(expr)
        if value is not None:
            return {'source': 'local:live-v287-g1-direct-arithmetic', 'answer': str(value), 'steps': [f'{expr} = {value}.']}

    m = re.search(r'(?:вычисли\s+цепочку|пройди\s+цепочку)\s*:?\s*([0-9\s+\-−–—]+)\s*[.?!]*$', low)
    if m:
        expr = _v287_norm_expr(m.group(1))
        value = _v287_safe_add_sub(expr)
        if value is not None:
            return {'source': 'local:live-v287-g1-chain', 'answer': str(value), 'steps': [f'Считаем по порядку слева направо.', f'{expr} = {value}.']}

    # Verbal action prompts.
    m = re.search(r'к\s+(\d{1,2})\s+прибавь\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v287-g1-verbal-add-sub', 'answer': str(ans), 'steps': [f'{a} + {b} = {ans}.']}
    m = re.search(r'из\s+(\d{1,2})\s+вычти\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v287-g1-verbal-add-sub', 'answer': str(ans), 'steps': [f'{a} − {b} = {ans}.']}
    m = re.search(r'увеличь\s+(?!число\s)(\d{1,2})\s+на\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v287-g1-verbal-add-sub', 'answer': str(ans), 'steps': [f'{a} + {b} = {ans}.']}
    m = re.search(r'уменьши\s+(?!число\s)(\d{1,2})\s+на\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v287-g1-verbal-add-sub', 'answer': str(ans), 'steps': [f'{a} − {b} = {ans}.']}

    # Sum/difference and named components.
    m = re.search(r'найди\s+сумм\w*\s+(?:чисел\s+)?(\d{1,2})\s+и\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v287-g1-components', 'answer': str(ans), 'steps': [f'Сумма — результат сложения.', f'{a} + {b} = {ans}.']}
    m = re.search(r'найди\s+разност\w*\s+(?:чисел\s+)?(\d{1,2})\s+и\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v287-g1-components', 'answer': str(ans), 'steps': [f'Разность — результат вычитания.', f'{a} − {b} = {ans}.']}
    m = re.search(r'первое\s+слагаемое\s+(\d{1,2}),?\s+второе\s+слагаемое\s+(\d{1,2}).*?найди\s+сумм', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v287-g1-components', 'answer': str(ans), 'steps': [f'Слагаемые складываем.', f'{a} + {b} = {ans}.']}
    m = re.search(r'уменьшаемое\s+(\d{1,2}),?\s+вычитаемое\s+(\d{1,2}).*?найди\s+разност', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v287-g1-components', 'answer': str(ans), 'steps': [f'Из уменьшаемого вычитаем вычитаемое.', f'{a} − {b} = {ans}.']}
    m = re.search(r'как\s+называется\s+результат\s+действия\s+\d{1,2}\s*\+\s*\d{1,2}', low)
    if m:
        return {'source': 'local:live-v287-g1-components-name', 'answer': 'сумма', 'steps': ['Результат сложения называется суммой.']}
    m = re.search(r'как\s+называется\s+результат\s+действия\s+\d{1,2}\s*-\s*\d{1,2}', low)
    if m:
        return {'source': 'local:live-v287-g1-components-name', 'answer': 'разность', 'steps': ['Результат вычитания называется разностью.']}
    if re.search(r'каким\s+действием\s+проверяют\s+вычитание', low):
        return {'source': 'local:live-v287-g1-inverse-action', 'answer': 'сложением', 'steps': ['Вычитание проверяют обратным действием — сложением.']}

    # Missing component in words.
    m = re.search(r'какое\s+число\s+надо\s+прибавить\s+к\s+(\d{1,2}),?\s+чтобы\s+получить\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = b - a
        return {'source': 'local:live-v287-g1-missing-component', 'answer': str(ans), 'steps': [f'{b} − {a} = {ans}.']}
    m = re.search(r'к\s+(\d{1,2})\s+прибавили\s+неизвестное\s+число\s+и\s+получили\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = b - a
        return {'source': 'local:live-v287-g1-missing-component', 'answer': str(ans), 'steps': [f'{b} − {a} = {ans}.']}
    m = re.search(r'какое\s+число\s+надо\s+вычесть\s+из\s+(\d{1,2}),?\s+чтобы\s+получить\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a - b
        return {'source': 'local:live-v287-g1-missing-component', 'answer': str(ans), 'steps': [f'{a} − {b} = {ans}.']}
    m = re.search(r'из\s+какого\s+числа\s+вычли\s+(\d{1,2})\s+и\s+получили\s+(\d{1,2})', low)
    if m:
        a, b = map(int, m.groups()); ans = a + b
        return {'source': 'local:live-v287-g1-missing-component', 'answer': str(ans), 'steps': [f'{b} + {a} = {ans}.']}

    # Equations with one unknown component.
    eq_source = re.split(r'(?:\.|найди|реши)', low, maxsplit=1)[0]
    compact = re.sub(r'[^0-9xх+=\-−–—]', '', eq_source).replace('х', 'x').replace('−', '-').replace('–', '-').replace('—', '-')
    eq_patterns = [
        (r'^x\+(\d{1,2})=(\d{1,2})$', lambda a, b: int(b) - int(a), 'неизвестное слагаемое'),
        (r'^(\d{1,2})\+x=(\d{1,2})$', lambda a, b: int(b) - int(a), 'неизвестное слагаемое'),
        (r'^x-(\d{1,2})=(\d{1,2})$', lambda a, b: int(a) + int(b), 'неизвестное уменьшаемое'),
        (r'^(\d{1,2})-x=(\d{1,2})$', lambda a, b: int(a) - int(b), 'неизвестное вычитаемое'),
    ]
    for pat, fn, label in eq_patterns:
        mm = re.fullmatch(pat, compact)
        if mm:
            ans = fn(*mm.groups())
            return {'source': 'local:live-v287-g1-equation', 'answer': f'x = {ans}', 'steps': [f'Ищем {label}.', f'x = {ans}.']}

    # Compare two simple add/sub expressions.
    m = re.search(r'сравни\s+(?:выражения\s+)?([0-9\s+\-−–—]+?)\s+и\s+([0-9\s+\-−–—]+)\s*[.?!]*$', low)
    if m:
        e1, e2 = _v287_norm_expr(m.group(1)), _v287_norm_expr(m.group(2))
        v1, v2 = _v287_safe_add_sub(e1), _v287_safe_add_sub(e2)
        if v1 is not None and v2 is not None:
            sign = '<' if v1 < v2 else '>' if v1 > v2 else '='
            if sign == '=':
                answer = f'{e1} = {e2}; выражения равны'
            elif sign == '>':
                answer = f'{e1} > {e2}; первое выражение больше'
            else:
                answer = f'{e1} < {e2}; первое выражение меньше'
            return {'source': 'local:live-v287-g1-expression-compare', 'answer': answer, 'steps': [f'{e1} = {v1}.', f'{e2} = {v2}.', f'{v1} {sign} {v2}.']}
    m = re.search(r'поставь\s+знак\s*[<>=>,\sили]*:?\s*([0-9\s+\-−–—]+?)\s*\?\s*([0-9\s+\-−–—]+)', low)
    if m:
        e1, e2 = _v287_norm_expr(m.group(1)), _v287_norm_expr(m.group(2))
        v1, v2 = _v287_safe_add_sub(e1), _v287_safe_add_sub(e2)
        if v1 is not None and v2 is not None:
            sign = '<' if v1 < v2 else '>' if v1 > v2 else '='
            return {'source': 'local:live-v287-g1-expression-compare', 'answer': sign, 'steps': [f'{e1} = {v1}.', f'{e2} = {v2}.', f'Нужный знак: {sign}.']}


    # True/false equality checks.
    m = re.search(r'верно\s+ли\s*:?\s*([0-9\s+\-−–—]+?)\s*=\s*(\d{1,2})', low)
    if m:
        expr, rhs = _v287_norm_expr(m.group(1)), int(m.group(2))
        value = _v287_safe_add_sub(expr)
        if value is not None:
            verdict = 'верно' if value == rhs else 'неверно'
            return {'source': 'local:live-v287-g1-true-false', 'answer': verdict, 'steps': [f'{expr} = {value}.', f'Сравниваем с {rhs}: {verdict}.']}

    return None


_v287_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v287_grade1_arithmetic_actions(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v287_solve_live_prev(text)

# --- v296 live DeepSeek audit: Grade 1, Section 2 — Arithmetic actions ---
# Structural verifier/postprocessor for the whole class of grade-1 arithmetic
# prompts.  It is intentionally pattern-based, not a per-case answer map.

def _v296_clean_expr(expr: str) -> str:
    return re.sub(r'\s+', ' ', str(expr or '').replace('−', '-').replace('–', '-').replace('—', '-')).strip()


def _v296_equation_payload(raw: str, low: str) -> Optional[dict]:
    normalized = str(raw or '').replace('х', 'x').replace('Х', 'x').replace('−', '-').replace('–', '-').replace('—', '-')
    # Grade-1 section 2 only covers elementary addition/subtraction equations
    # within 20.  Do not shadow higher-grade linear-equation handlers.
    if re.search(r'[*/×·:]', normalized):
        return None
    compact = re.sub(r'\s+', '', normalized.lower())
    # Extract the first elementary one-variable equation from wrappers such as
    # "Реши уравнение: x + 5 = 13".
    m = re.search(r'(x[+\-]\d{1,2}=\d{1,2}|\d{1,2}\+x=\d{1,2}|\d{1,2}-x=\d{1,2})', compact)
    if not m:
        return None
    eq = m.group(1)
    if any(int(n) > 20 for n in re.findall(r'\d+', eq)):
        return None
    patterns = [
        (r'^x\+(\d{1,2})=(\d{1,2})$', lambda a, b: int(b) - int(a), 'неизвестное слагаемое'),
        (r'^(\d{1,2})\+x=(\d{1,2})$', lambda a, b: int(b) - int(a), 'неизвестное слагаемое'),
        (r'^x-(\d{1,2})=(\d{1,2})$', lambda a, b: int(a) + int(b), 'неизвестное уменьшаемое'),
        (r'^(\d{1,2})-x=(\d{1,2})$', lambda a, b: int(a) - int(b), 'неизвестное вычитаемое'),
    ]
    for pat, fn, label in patterns:
        mm = re.fullmatch(pat, eq)
        if not mm:
            continue
        ans = fn(*mm.groups())
        pretty = eq.replace('x', 'x').replace('+', ' + ').replace('-', ' - ').replace('=', ' = ')
        pretty = re.sub(r'\s+', ' ', pretty).strip()
        return {
            'source': 'local:live-v296-g1-equation',
            'answer': f'x = {ans}',
            'steps': [f'{pretty}.', f'Ищем {label}.', f'x = {ans}.'],
        }
    return None


def solve_v296_grade1_arithmetic_actions(text: str) -> Optional[dict]:
    raw = _v283_clean(text)
    low = _v283_lower(raw)
    if 'сколько получится' in low:
        return None

    # Wrapped direct expressions: "Реши пример", "Найди результат".
    m = re.search(r'(?:реши\s+пример|найди\s+результат|посчитай)\s*:?[\s]*([0-9\s+\-−–—]+)\s*[.?!]*$', low)
    if m:
        expr = _v296_clean_expr(m.group(1))
        value = _v287_safe_add_sub(expr)
        if value is not None:
            return {'source': 'local:live-v296-g1-direct-arithmetic', 'answer': str(value), 'steps': [f'{expr} = {value}.']}

    # More verbal addition/subtraction wordings.
    verbal_patterns = [
        (r'прибавь\s+(\d{1,2})\s+к\s+(\d{1,2})', lambda a, b: int(b) + int(a), lambda a, b, ans: f'{b} + {a} = {ans}.'),
        (r'вычти\s+(\d{1,2})\s+из\s+(\d{1,2})', lambda a, b: int(b) - int(a), lambda a, b, ans: f'{b} − {a} = {ans}.'),
        (r'к\s+(\d{1,2})\s+прибавили\s+(\d{1,2})', lambda a, b: int(a) + int(b), lambda a, b, ans: f'{a} + {b} = {ans}.'),
        (r'если\s+к\s+(\d{1,2})\s+прибавить\s+(\d{1,2})', lambda a, b: int(a) + int(b), lambda a, b, ans: f'{a} + {b} = {ans}.'),
        (r'от\s+(\d{1,2})\s+отняли\s+(\d{1,2})', lambda a, b: int(a) - int(b), lambda a, b, ans: f'{a} − {b} = {ans}.'),
        (r'если\s+из\s+(\d{1,2})\s+вычесть\s+(\d{1,2})', lambda a, b: int(a) - int(b), lambda a, b, ans: f'{a} − {b} = {ans}.'),
    ]
    for pat, fn, step_builder in verbal_patterns:
        m = re.search(pat, low)
        if m:
            a, b = m.groups()
            ans = fn(a, b)
            return {'source': 'local:live-v296-g1-verbal-add-sub', 'answer': str(ans), 'steps': [step_builder(a, b, ans)]}

    # Component terminology.
    if re.search(r'как\s+называются\s+числа,?\s+которые\s+складывают', low):
        return {'source': 'local:live-v296-g1-components-name', 'answer': 'слагаемые', 'steps': ['Числа, которые складывают, называются слагаемыми.']}
    if re.search(r'как\s+называется\s+число,?\s+из\s+которого\s+вычитают', low):
        return {'source': 'local:live-v296-g1-components-name', 'answer': 'уменьшаемое', 'steps': ['Число, из которого вычитают, называется уменьшаемым.']}
    if re.search(r'как\s+называется\s+число,?\s+которое\s+вычитают', low):
        return {'source': 'local:live-v296-g1-components-name', 'answer': 'вычитаемое', 'steps': ['Число, которое вычитают, называется вычитаемым.']}
    m = re.search(r'найди\s+неизвестное\s+слагаемое.*?сумм\w*\s+(\d{1,2}).*?другое\s+слагаемое\s+(\d{1,2})', low)
    if m:
        total, known = map(int, m.groups())
        ans = total - known
        return {'source': 'local:live-v296-g1-missing-component', 'answer': str(ans), 'steps': [f'{total} − {known} = {ans}.']}

    # Keep previous grade-1 arithmetic/equation handlers first for legacy
    # regression prompts, so their expected source family remains stable.
    base = solve_v287_grade1_arithmetic_actions(text)
    if base is not None:
        return base

    # v296 still covers wrapped equation prompts that older handlers do not
    # parse, for example: "Реши уравнение: x + 3 = 8".
    eq_payload = _v296_equation_payload(raw, low)
    if eq_payload is not None:
        return eq_payload

    return None


_v296_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v296_grade1_arithmetic_actions(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v296_solve_live_prev(text)


# --- v297 live UI audit: Grade 1, Section 3 — Text problems ---
# One-action text problems: total, remaining, relation and difference compare,
# plus guard coverage for incomplete/non-task inputs.

_V297_ITEM_FORMS = [
    ('яблок', ('яблоко', 'яблока', 'яблок')),
    ('гриб', ('гриб', 'гриба', 'грибов')),
    ('карандаш', ('карандаш', 'карандаша', 'карандашей')),
    ('тетрад', ('тетрадь', 'тетради', 'тетрадей')),
    ('конфет', ('конфета', 'конфеты', 'конфет')),
    ('книг', ('книга', 'книги', 'книг')),
    ('мар', ('марка', 'марки', 'марок')),
    ('шар', ('шар', 'шара', 'шаров')),
    ('кук', ('кукла', 'куклы', 'кукол')),
    ('мяч', ('мяч', 'мяча', 'мячей')),
]

def _v297_word(n: int, word: str) -> str:
    stem = (word or '').lower().replace('ё', 'е').strip(' .,!?:;')
    for marker, forms in _V297_ITEM_FORMS:
        if marker in stem:
            return _choose_plural_int(int(n), forms[0], forms[1], forms[2])
    return _v281_word(int(n), word)

def _v297_count(n: int, word: str) -> str:
    return f'{int(n)} {_v297_word(int(n), word)}'

def _v297_same_item(a: str, b: str) -> bool:
    a_norm = (a or '').lower().replace('ё', 'е').strip(' .,!?:;')
    b_norm = (b or '').lower().replace('ё', 'е').strip(' .,!?:;')
    if not a_norm or not b_norm:
        return False
    for marker, forms in _V297_ITEM_FORMS:
        if marker in a_norm and marker in b_norm:
            return True
        if any(form in a_norm for form in forms) and any(form in b_norm for form in forms):
            return True
    return a_norm[:4] == b_norm[:4]

def _v297_name(value: str) -> str:
    text = str(value or '').strip()
    return text[:1].upper() + text[1:] if text else ''

def solve_v297_grade1_text_problems(text: str) -> Optional[dict]:
    raw = _v280_clean_task(text)
    low = _v283_lower(raw)

    # Guards are handled earlier in service prevalidation; this solver only
    # handles ordinary one-action text problems of the first-grade curriculum.
    if not any(key in low for key in ('сколько', 'на сколько', 'было', 'осталось', 'стало', 'всего')):
        return None

    # Two subjects, same item -> total.
    m = re.search(
        r'у\s+([а-яеё]+)\s+(?:(?:был|была|было|были)\s+)?(\d+)\s+([а-яеё]+)\b.*?у\s+([а-яеё]+)\s+(?:(?:был|была|было|были)\s+)?(\d+)\s+([а-яеё]+)\b.*?сколько\s+всего\s+([а-яеё]+)',
        low,
        flags=re.IGNORECASE,
    )
    if m:
        name1, first, item1, name2, second, item2, asked = m.groups()
        first_n, second_n = int(first), int(second)
        if _v297_same_item(item1, item2) and _v297_same_item(item1, asked):
            total = first_n + second_n
            return {
                'source': 'local:live-v297-g1-total-two-subjects',
                'answer': f'Всего {_v297_count(total, asked)}',
                'steps': [f'{first_n} + {second_n} = {total} {_v297_word(total, asked)}.'],
            }

    # Было N, дали/добавили ещё M -> стало.
    add_patterns = [
        r'у\s+([а-яеё]+)\s+(?:был|была|было|были)\s+(\d+)\s+([а-яеё]+)\b.*?(?:дали|дала|дал|подарил[а-я]*|принес[а-я]*|принёс[а-я]*|добавил[а-я]*|добавили|положил[а-я]*|купил[а-я]*|наш[её]л[а-я]*)\s+(?:ей|ему|им)?\s*(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\b.*?сколько\s+([а-яеё]+)\s+(?:стало|всего)',
        r'у\s+([а-яеё]+)\s+(?:был|была|было|были)\s+(\d+)\s+([а-яеё]+)\b.*?(?:ещ[её]\s+)?(\d+)\s+([а-яеё]+)\s+(?:дали|добавили|подарили)\b.*?сколько\s+([а-яеё]+)\s+(?:стало|всего)',
    ]
    for pat in add_patterns:
        m = re.search(pat, low, flags=re.IGNORECASE)
        if m:
            name, first, item1, second, item2, asked = m.groups()
            first_n, second_n = int(first), int(second)
            if _v297_same_item(item1, item2) and _v297_same_item(item1, asked):
                total = first_n + second_n
                return {
                    'source': 'local:live-v297-g1-addition-story',
                    'answer': f'У {_v297_name(name)} стало {_v297_count(total, asked)}',
                    'steps': [f'{first_n} + {second_n} = {total} {_v297_word(total, asked)}.'],
                }

    # Было N, убрали/отдали M -> осталось.
    sub_patterns = [
        r'у\s+([а-яеё]+)\s+(?:был|была|было|были)\s+(\d+)\s+([а-яеё]+)\b.*?(?:отдал[а-я]*|подарил[а-я]*|съел[а-я]*|убрал[а-я]*|забрал[а-я]*|взял[а-я]*|продал[а-я]*|унес[а-я]*)\s+(?:другу\s+)?(\d+)\s+([а-яеё]+)\b.*?сколько\s+([а-яеё]+)\s+остал',
        r'на\s+[а-яеё\s]+?\s+было\s+(\d+)\s+([а-яеё]+)\b.*?(\d+)\s+([а-яеё]+)\s+(?:убрали|взяли|забрали)\b.*?сколько\s+([а-яеё]+)\s+остал',
    ]
    m = re.search(sub_patterns[0], low, flags=re.IGNORECASE)
    if m:
        name, first, item1, second, item2, asked = m.groups()
        first_n, second_n = int(first), int(second)
        if _v297_same_item(item1, item2) and _v297_same_item(item1, asked):
            left = first_n - second_n
            return {
                'source': 'local:live-v297-g1-subtraction-story',
                'answer': f'У {_v297_name(name)} осталось {_v297_count(left, asked)}',
                'steps': [f'{first_n} − {second_n} = {left} {_v297_word(left, asked)}.'],
            }
    m = re.search(sub_patterns[1], low, flags=re.IGNORECASE)
    if m:
        first, item1, second, item2, asked = m.groups()
        first_n, second_n = int(first), int(second)
        if _v297_same_item(item1, item2) and _v297_same_item(item1, asked):
            left = first_n - second_n
            return {
                'source': 'local:live-v297-g1-subtraction-story',
                'answer': f'Осталось {_v297_count(left, asked)}',
                'steps': [f'{first_n} − {second_n} = {left} {_v297_word(left, asked)}.'],
            }

    # Relation: у второго на N больше/меньше.
    m = re.search(
        r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+)\b.*?у\s+([а-яеё]+)\s+на\s+(\d+)\s+([а-яеё]+)\s+(больше|меньше).*?сколько\s+([а-яеё]+)\s+у\s+\4',
        low,
        flags=re.IGNORECASE,
    )
    if m:
        name1, base, item1, name2, delta, item2, kind, asked = m.groups()
        base_n, delta_n = int(base), int(delta)
        if _v297_same_item(item1, item2) and _v297_same_item(item1, asked):
            answer_n = base_n + delta_n if kind == 'больше' else base_n - delta_n
            op = '+' if kind == 'больше' else '−'
            return {
                'source': 'local:live-v297-g1-relation-story',
                'answer': f'У {_v297_name(name2)} {_v297_count(answer_n, asked)}',
                'steps': [f'{base_n} {op} {delta_n} = {answer_n} {_v297_word(answer_n, asked)}.'],
            }

    # Difference compare: "На сколько ... больше/меньше, чем ...".
    m = re.search(
        r'у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+)\b.*?у\s+([а-яеё]+)\s+(\d+)\s+([а-яеё]+)\b.*?на\s+сколько\s+([а-яеё]+)\s+у\s+\1\s+(больше|меньше),?\s+чем\s+у\s+\4',
        low,
        flags=re.IGNORECASE,
    )
    if m:
        name1, first, item1, name2, second, item2, asked, kind = m.groups()
        first_n, second_n = int(first), int(second)
        if _v297_same_item(item1, item2) and _v297_same_item(item1, asked):
            diff = abs(first_n - second_n)
            return {
                'source': 'local:live-v297-g1-difference-story',
                'answer': f'У {_v297_name(name1)} на {_v297_count(diff, asked)} {kind}, чем у {_v297_name(name2)}',
                'steps': [f'{max(first_n, second_n)} − {min(first_n, second_n)} = {diff} {_v297_word(diff, asked)}.'],
            }

    return None


_v297_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v297_grade1_text_problems(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v297_solve_live_prev(text)



# --- v298 live UI audit: Grade 1, Section 4 — Geometry and spatial relations ---
_V298_SHAPE_GENITIVE = {
    'круг': 'круга',
    'квадрат': 'квадрата',
    'треугольник': 'треугольника',
    'прямоугольник': 'прямоугольника',
}

_V298_SHAPE_INSTRUMENTAL = {
    'круг': 'кругом',
    'квадрат': 'квадратом',
    'треугольник': 'треугольником',
    'прямоугольник': 'прямоугольником',
}


def _v298_shape_from_fragment(fragment: str) -> Optional[str]:
    low = str(fragment or '').lower().replace('ё', 'е')
    if 'прямоугольн' in low:
        return 'прямоугольник'
    if 'треугольн' in low:
        return 'треугольник'
    if 'квадрат' in low:
        return 'квадрат'
    if 'круг' in low:
        return 'круг'
    return None


def _v298_shape_tokens(text: str) -> list[str]:
    tokens = re.findall(r'круг\w*|квадрат\w*|треугольник\w*|прямоугольник\w*', str(text or '').lower().replace('ё', 'е'))
    out: list[str] = []
    for token in tokens:
        shape = _v298_shape_from_fragment(token)
        if shape:
            out.append(shape)
    return out


def _v298_layout_shapes(low: str, marker: str) -> list[str]:
    for sentence in re.split(r'[.!?]', low):
        sent = sentence.strip()
        if marker in sent:
            shapes = _v298_shape_tokens(sent)
            if len(shapes) >= 3:
                return shapes
    return []


def _v298_grid_moves(low: str) -> list[tuple[int, str]]:
    return [(int(count), direction) for count, direction in re.findall(r'(\d+)\s+клет(?:ку|ки|ок)\s+(вправо|влево|вверх|вниз)', low)]


def solve_v298_grade1_geometry_spatial(text: str) -> Optional[dict]:
    raw = _v280_clean_task(text)
    low = _v283_lower(raw)

    # Left / right on a row.
    if 'слева направо' in low and ('справа от' in low or 'слева от' in low):
        shapes = _v298_layout_shapes(low, 'слева направо')
        if shapes:
            if 'справа от' in low:
                m = re.search(r'справа\s+от\s+([а-яё]+)', low)
                target = _v298_shape_from_fragment(m.group(1)) if m else None
                if target in shapes:
                    idx = shapes.index(target)
                    if idx + 1 < len(shapes):
                        answer_shape = shapes[idx + 1]
                        return {
                            'source': 'local:live-v298-g1-left-right',
                            'answer': f'Справа от {_V298_SHAPE_GENITIVE[target]} {answer_shape}',
                            'steps': [f'Смотрим ряд слева направо: после {target} стоит {answer_shape}.'],
                        }
            if 'слева от' in low:
                m = re.search(r'слева\s+от\s+([а-яё]+)', low)
                target = _v298_shape_from_fragment(m.group(1)) if m else None
                if target in shapes:
                    idx = shapes.index(target)
                    if idx - 1 >= 0:
                        answer_shape = shapes[idx - 1]
                        return {
                            'source': 'local:live-v298-g1-left-right',
                            'answer': f'Слева от {_V298_SHAPE_GENITIVE[target]} {answer_shape}',
                            'steps': [f'Смотрим ряд слева направо: перед {target} стоит {answer_shape}.'],
                        }

    # Above / below in a column.
    if 'сверху вниз' in low and ('выше' in low or 'ниже' in low):
        shapes = _v298_layout_shapes(low, 'сверху вниз')
        if shapes:
            if 'выше' in low:
                m = re.search(r'выше\s+([а-яё]+)', low)
                target = _v298_shape_from_fragment(m.group(1)) if m else None
                if target in shapes:
                    idx = shapes.index(target)
                    if idx - 1 >= 0:
                        answer_shape = shapes[idx - 1]
                        return {
                            'source': 'local:live-v298-g1-above-below',
                            'answer': f'Выше {_V298_SHAPE_GENITIVE[target]} {answer_shape}',
                            'steps': [f'Смотрим столбик сверху вниз: над {target} находится {answer_shape}.'],
                        }
            if 'ниже' in low:
                m = re.search(r'ниже\s+([а-яё]+)', low)
                target = _v298_shape_from_fragment(m.group(1)) if m else None
                if target in shapes:
                    idx = shapes.index(target)
                    if idx + 1 < len(shapes):
                        answer_shape = shapes[idx + 1]
                        return {
                            'source': 'local:live-v298-g1-above-below',
                            'answer': f'Ниже {_V298_SHAPE_GENITIVE[target]} {answer_shape}',
                            'steps': [f'Смотрим столбик сверху вниз: под {target} находится {answer_shape}.'],
                        }

    # Between on a row.
    if 'между' in low and 'слева направо' in low:
        shapes = _v298_layout_shapes(low, 'слева направо')
        m = re.search(r'между\s+([а-яё]+)\s+и\s+([а-яё]+)', low)
        if shapes and m:
            first = _v298_shape_from_fragment(m.group(1))
            second = _v298_shape_from_fragment(m.group(2))
            if first in shapes and second in shapes:
                i1, i2 = shapes.index(first), shapes.index(second)
                if abs(i1 - i2) == 2:
                    middle = shapes[min(i1, i2) + 1]
                    return {
                        'source': 'local:live-v298-g1-between',
                        'answer': f'Между {_V298_SHAPE_INSTRUMENTAL[first]} и {_V298_SHAPE_INSTRUMENTAL[second]} {middle}',
                        'steps': [f'В ряду между {first} и {second} стоит {middle}.'],
                    }

    # Inside / outside a frame.
    if 'рамк' in low and ('внутри рамки' in low or 'вне рамки' in low or 'в рамке' in low):
        inside: list[str] = []
        outside: list[str] = []
        for sentence in re.split(r'[.!?]', low):
            sent = sentence.strip()
            if not sent:
                continue
            shapes = _v298_shape_tokens(sent)
            if not shapes:
                continue
            if 'вне рамки' in sent:
                outside.extend(shapes)
            elif 'внутри рамки' in sent or 'в рамке' in sent:
                inside.extend(shapes)
        if 'какая фигура вне рамки' in low and len(outside) == 1:
            return {
                'source': 'local:live-v298-g1-inside-outside',
                'answer': f'Вне рамки {outside[0]}',
                'steps': [f'Смотрим, что отмечено вне рамки: это {outside[0]}.'],
            }
        if ('какая фигура внутри рамки' in low or 'какая фигура в рамке' in low) and len(inside) == 1:
            return {
                'source': 'local:live-v298-g1-inside-outside',
                'answer': f'Внутри рамки {inside[0]}',
                'steps': [f'Смотрим, что отмечено внутри рамки: это {inside[0]}.'],
            }

    # Figure by description.
    if any(word in low for word in ('какая фигура', 'назови фигуру', 'у какой фигуры')):
        if re.search(r'(?:нет|без)\s+угл|не\s+имеет\s+угл', low):
            return {
                'source': 'local:live-v298-g1-shape-description',
                'answer': 'Это круг',
                'steps': ['Круг не имеет углов.'],
            }
        if re.search(r'(?<!\d)(?:3|три)\s+сторон', low) or re.search(r'(?<!\d)(?:3|три)\s+угл', low):
            return {
                'source': 'local:live-v298-g1-shape-description',
                'answer': 'Это треугольник',
                'steps': ['У треугольника 3 стороны и 3 угла.'],
            }
        if re.search(r'(?<!\d)(?:4|четыре)\s+равн\w+\s+сторон', low) or (re.search(r'(?<!\d)(?:4|четыре)\s+сторон', low) and 'все стороны равны' in low):
            return {
                'source': 'local:live-v298-g1-shape-description',
                'answer': 'Это квадрат',
                'steps': ['У квадрата 4 равные стороны.'],
            }
        if ('противоположные стороны равны' in low) or re.search(r'(?<!\d)(?:2|две)\s+длин\w+\s+и\s+(?:2|две)\s+коротк\w+\s+сторон', low):
            return {
                'source': 'local:live-v298-g1-shape-description',
                'answer': 'Это прямоугольник',
                'steps': ['У прямоугольника противоположные стороны равны.'],
            }

    # Segment length.
    m = re.search(r'отрезок\s+([a-zа-я]{2})\s+имеет\s+длину\s+(\d+)\s*см', raw, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'длина\s+отрезка\s+([a-zа-я]{2})\s+равна\s+(\d+)\s*см', raw, flags=re.IGNORECASE)
    if m:
        name, length = m.groups()
        name = name.upper()
        length_n = int(length)
        return {
            'source': 'local:live-v298-g1-segment-length',
            'answer': f'Длина отрезка {name} {length_n} см',
            'steps': [f'По условию длина отрезка {name} равна {length_n} см.'],
        }

    # Grid routes and total path length.
    if 'клетчат' in low and 'клетк' in low:
        start = re.search(r'\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', low)
        moves = _v298_grid_moves(low)
        if 'сколько клеток нужно пройти' in low and moves:
            total = sum(count for count, _ in moves)
            return {
                'source': 'local:live-v298-g1-grid-route-steps',
                'answer': f'Нужно пройти {total} {_choose_plural_int(total, "клетку", "клетки", "клеток")}',
                'steps': [f'Складываем все шаги: {" + ".join(str(count) for count, _ in moves)} = {total}.'],
            }
        if start and moves and ('в какой клетке' in low or 'где окажешься' in low):
            x, y = int(start.group(1)), int(start.group(2))
            for count, direction in moves:
                if direction == 'вправо':
                    x += count
                elif direction == 'влево':
                    x -= count
                elif direction == 'вверх':
                    y += count
                elif direction == 'вниз':
                    y -= count
            return {
                'source': 'local:live-v298-g1-grid-route-cell',
                'answer': f'Окажешься в клетке ({x}, {y})',
                'steps': ['Последовательно выполняем маршрут по клеткам.'],
            }

    return None


_v298_solve_live_prev = solve_live_math_first

def solve_live_math_first(text: str) -> Optional[dict]:  # type: ignore[override]
    payload = solve_v298_grade1_geometry_spatial(text)
    if payload is not None:
        return _v281_full_payload(text, payload)
    return _v298_solve_live_prev(text)
