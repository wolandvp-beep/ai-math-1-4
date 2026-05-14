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
