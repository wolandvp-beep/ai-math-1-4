from __future__ import annotations

"""Statically materialized runtime module for tail_runtime_module.py.

This preserves shard execution order while making this runtime layer a
normal importable Python module.
"""

# --- merged segment 001: backend.legacy_runtime_module_shards.tail_runtime_module.segment_001 ---
import re
from fractions import Fraction
def _frac20260416_cont_try_simple_unit_fraction(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    m = re.fullmatch(r'Найти\s+(\d+)\s*/\s*(\d+)\s+от\s+1\s+(см|дм|м|кг|л)\.?', text, flags=re.IGNORECASE)
    if not m:
        return None
    num, den = int(m.group(1)), int(m.group(2))
    unit = m.group(3).lower()
    smaller = {'см': ('мм', 10), 'дм': ('см', 10), 'м': ('см', 100), 'кг': ('г', 1000), 'л': ('мл', 1000)}
    if unit not in smaller:
        return None
    small_unit, coeff = smaller[unit]
    base = coeff
    if (base * num) % den != 0:
        return None
    part = (base * num) // den
    lines = [
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: нужно найти {num}/{den} от 1 {unit}.',
        'Что нужно найти: значение этой части.',
        f'1) Переводим 1 {unit} в более мелкие единицы: 1 {unit} = {base} {small_unit}.',
        f'2) Находим {num}/{den} от {base} {small_unit}: {base} : {den} × {num} = {part} {small_unit}.',
        f'Ответ: {part} {small_unit}',
        'Совет: чтобы найти дробь от величины, сначала удобно перевести её в более мелкие единицы',
    ]
    return _mass20260416x_finalize(lines)


def _frac20260416_cont_try_fraction_text_tasks(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    lower = text.lower()

    m = re.fullmatch(r'(\d+)\s*/\s*(\d+)\s*=\s*(\d+)', lower)
    if m:
        num, den, part = map(int, m.groups())
        if num > 0:
            one = part // num if part % num == 0 else part / num
            whole = int(one * den) if float(one * den).is_integer() else one * den
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: {num}/{den} числа равны {part}.',
                'Что нужно найти: всё число.',
                f'1) Находим одну долю: {part} : {num} = {one}.',
                f'2) Находим всё число: {one} × {den} = {whole}.',
                f'Ответ: {whole}',
                'Совет: если известны несколько долей числа, сначала находят одну долю, а потом всё число',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'Найди длину всей ленты, если\s*(\d+)\s*/\s*(\d+)\s*составляют\s*(\d+)\s*м', text, flags=re.IGNORECASE)
    if m:
        num, den, part = map(int, m.groups())
        one = part // num if part % num == 0 else part / num
        whole = int(one * den) if float(one * den).is_integer() else one * den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: {num}/{den} длины ленты составляют {part} м.',
            'Что нужно найти: всю длину ленты.',
            f'1) Находим одну долю: {part} : {num} = {one} м.',
            f'2) Находим всю длину: {one} × {den} = {whole} м.',
            f'Ответ: {whole} м',
            'Совет: если известны несколько долей величины, сначала находят одну долю, а потом всю величину',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'Найди\s*1\s*/\s*(\d+)\s+длины провода, если\s*(\d+)\s*/\s*(\d+)\s+этой длины составляют\s*(\d+)\s*м', text, flags=re.IGNORECASE)
    if m:
        ask_den, num, den, part = map(int, m.groups())
        if den == ask_den and num > 0:
            one = part // num if part % num == 0 else part / num
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: {num}/{den} длины провода составляют {part} м.',
                f'Что нужно найти: 1/{ask_den} длины провода.',
                f'1) Находим одну долю: {part} : {num} = {one} м.',
                f'Ответ: {one} м',
                'Совет: если нужно найти одну долю, число долей делят на их количество',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'велосипедист проехал\s*(\d+)\s*км, что составляет\s*(\d+)\s*/\s*(\d+)\s*част', lower)
    if m:
        part, num, den = map(int, m.groups())
        if num > 0:
            one = part // num if part % num == 0 else part / num
            whole = int(one * den) if float(one * den).is_integer() else one * den
            lines = [
                'Задача.',
                _audit_task_line(raw_text),
                'Решение.',
                f'Что известно: {num}/{den} маршрута составляют {part} км.',
                'Что нужно найти: длину всего маршрута.',
                f'1) Находим одну долю маршрута: {part} : {num} = {one} км.',
                f'2) Находим весь маршрут: {one} × {den} = {whole} км.',
                f'Ответ: {whole} км',
                'Совет: если известна часть пути, сначала находят одну долю, а потом весь путь',
            ]
            return _mass20260416x_finalize(lines)

    m = re.search(r'прош[её]л\s+(?:четвертую|шестую)\s+часть пути за\s*(\d+)\s*минут', lower)
    if m:
        part_time = int(m.group(1))
        den = 4 if 'четверт' in lower else 6
        whole = part_time * den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: 1/{den} пути пройдена за {part_time} минут.',
            'Что нужно найти: время на весь путь.',
            f'1) Весь путь состоит из {den} таких частей.',
            f'2) Находим всё время: {part_time} × {den} = {whole} минут.',
            f'Ответ: {whole} минут',
            'Совет: если одна доля пути занимает известное время, всё время находят умножением на число долей',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'почтовый голубь в час пролетает\s*(\d+)\s*км\.\s*сколько км он пролетит за\s*(\d+)\s*/\s*(\d+)\s*часа', lower)
    if m:
        per_hour, num, den = map(int, m.groups())
        part = per_hour * num // den if (per_hour * num) % den == 0 else per_hour * num / den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: за 1 час голубь пролетает {per_hour} км.',
            f'Что нужно найти: сколько он пролетит за {num}/{den} часа.',
            f'1) Находим {num}/{den} от {per_hour}: {per_hour} : {den} × {num} = {part} км.',
            f'Ответ: {part} км',
            'Совет: чтобы найти дробь от числа, число делят на знаменатель и умножают на числитель',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'один литр керосина весит\s*(\d+)\s*г\.\s*сколько весит\s*(\d+)\s*/\s*(\d+)\s*литра', lower)
    if m:
        total, num, den = map(int, m.groups())
        part = total * num // den if (total * num) % den == 0 else total * num / den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: 1 литр керосина весит {total} г.',
            f'Что нужно найти: сколько весит {num}/{den} литра.',
            f'1) Находим {num}/{den} от {total}: {total} : {den} × {num} = {part} г.',
            f'Ответ: {part} г',
            'Совет: чтобы найти дробь от массы, массу делят на знаменатель и умножают на числитель',
        ]
        return _mass20260416x_finalize(lines)

    if 'большой праздничный пирог' in lower and '1/4' in lower and '2/4' in lower:
        eaten = '3/4'
        left = '1/4'
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            'Что известно: сначала съели 1/4 пирога, потом ещё 2/4 пирога.',
            'Что нужно найти: какая часть пирога съедена и какая часть осталась.',
            '1) Находим съеденную часть: 1/4 + 2/4 = 3/4.',
            '2) Находим оставшуюся часть: 1 - 3/4 = 1/4.',
            f'Ответ: съели {eaten}, осталось {left}',
            'Совет: дроби с одинаковыми знаменателями складывают и вычитают по числителям',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'полоска ткани длиной\s*(\d+)\s*см\.\s*из\s*(\d+)\s*/\s*(\d+)\s*части.*сколько см ткани у нее осталось\?\s*сколько см ткани ушло', lower)
    if m:
        total, num, den = map(int, m.groups())
        part = total * num // den if (total * num) % den == 0 else total * num / den
        left = total - part
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: длина ткани {total} см, на кофточку ушло {num}/{den} ткани.',
            'Что нужно найти: сколько ткани ушло и сколько осталось.',
            f'1) Находим, сколько ткани ушло: {total} : {den} × {num} = {part} см.',
            f'2) Находим, сколько ткани осталось: {total} - {part} = {left} см.',
            f'Ответ: ушло {part} см, осталось {left} см',
            'Совет: чтобы найти остаток после дробной части, сначала находят эту часть, а потом вычитают её из целого',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'зарплату\s*(\d+)\s*руб.*(\d+)\s*/\s*(\d+)\s*из этих денег.*подарки.*(\d+)\s*/\s*(\d+)\s*потратила на фрукты', lower)
    if m:
        total, g_num, g_den, f_num, f_den = map(int, m.groups())
        gifts = total * g_num // g_den if (total * g_num) % g_den == 0 else total * g_num / g_den
        fruits = total * f_num // f_den if (total * f_num) % f_den == 0 else total * f_num / f_den
        left = total - gifts - fruits
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'Что известно: всего {total} руб., на подарки потратили {g_num}/{g_den}, на фрукты {f_num}/{f_den} всех денег.',
            'Что нужно найти: сколько потратили на подарки, на фрукты и сколько денег осталось.',
            f'1) Находим деньги на подарки: {total} : {g_den} × {g_num} = {gifts} руб.',
            f'2) Находим деньги на фрукты: {total} : {f_den} × {f_num} = {fruits} руб.',
            f'3) Находим остаток: {total} - {gifts} - {fruits} = {left} руб.',
            f'Ответ: на подарки {gifts} руб., на фрукты {fruits} руб., осталось {left} руб.',
            'Совет: если нужно найти несколько дробных частей одного числа, каждую часть считают отдельно',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в куске ткани\s*(\d+)\s*м.*отрезали\s*(\d+)\s*/\s*(\d+)\s*част', lower)
    if m:
        total, num, den = map(int, m.groups())
        part = total * num // den if (total * num) % den == 0 else total * num / den
        left = total - part
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько ткани отрезали: {total} : {den} × {num} = {part} м.',
            f'2) Находим, сколько ткани осталось: {total} - {part} = {left} м.',
            f'Ответ: {left} м',
            'Совет: чтобы найти остаток после дробной части, сначала находят эту часть',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в поход пошли\s*(\d+)\s*человек.*мальчиков\s*(\d+)\s*человек.*девочек\s*[-–]\s*третья часть от всех мальчиков.*остальные взрослые', lower)
    if m:
        total, boys = map(int, m.groups())
        girls = boys // 3
        adults = total - boys - girls
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим число девочек: {boys} : 3 = {girls}.',
            f'2) Находим число взрослых: {total} - {boys} - {girls} = {adults}.',
            f'Ответ: {adults} взрослых',
            'Совет: если сказано «третья часть», сначала находят эту часть, а потом остаток',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в саду\s*(\d+)\s*роз, тюльпанов четвертая часть от роз, ромашек\s*(\d+)', lower)
    if m:
        roses, daisies = map(int, m.groups())
        tulips = roses // 4
        total = roses + tulips + daisies
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим количество тюльпанов: {roses} : 4 = {tulips}.',
            f'2) Находим общее количество цветов: {roses} + {tulips} + {daisies} = {total}.',
            f'Ответ: {total} цветов',
            'Совет: если одна величина составляет часть другой, сначала находят эту часть, а потом складывают все количества',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в саду\s*(\d+)\s*цветов\.\s*ромашек\s*(\d+)\s*штук\.\s*роз\s*[-–]?\s*1\s*/\s*(\d+)\s*часть от ромашек.*остальные цветы[-–]? тюльпаны', lower)
    if m:
        total, daisies, den = map(int, m.groups())
        roses = daisies // den
        tulips = total - daisies - roses
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим количество роз: {daisies} : {den} = {roses}.',
            f'2) Находим количество тюльпанов: {total} - {daisies} - {roses} = {tulips}.',
            f'Ответ: {tulips} тюльпанов',
            'Совет: если одна часть известна, а другая выражена дробью от неё, сначала находят эту дробную часть, а потом остаток',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'в магазин привезли\s*(\d+)\s*метров красной ткани, синей[–-]\s*1\s*/\s*(\d+)\s*часть от красной, зеленой[–-]\s*(\d+)\s*метров', lower)
    if m:
        red, den, green = map(int, m.groups())
        blue = red // den
        total = red + blue + green
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько метров синей ткани привезли: {red} : {den} = {blue} м.',
            f'2) Находим общее количество ткани: {red} + {blue} + {green} = {total} м.',
            f'Ответ: {total} м',
            'Совет: если одна величина составляет дробную часть другой, сначала находят эту часть, а потом общий итог',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'куриное яйцо весит\s*(\d+)\s*г.*скорлупу приходится\s*1\s*/\s*(\d+).*белок\s*1\s*/\s*(\d+).*остальное[ –-]+желток', lower)
    if m:
        total, shell_den, white_den = map(int, m.groups())
        shell = total // shell_den
        white = total // white_den
        yolk = total - shell - white
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим массу скорлупы: {total} : {shell_den} = {shell} г.',
            f'2) Находим массу белка: {total} : {white_den} = {white} г.',
            f'3) Находим массу желтка: {total} - {shell} - {white} = {yolk} г.',
            f'Ответ: {yolk} г',
            'Совет: если часть массы уже известна по долям, остальные части находят вычитанием из всей массы',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'на свете существует\s*(\d+)\s*разновидностей акул.*1\s*/\s*(\d+)\s*часть нападает', lower)
    if m:
        total, den = map(int, m.groups())
        count = total // den
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим {1}/{den} от {total}: {total} : {den} = {count}.',
            f'Ответ: {count} видов',
            'Совет: чтобы найти одну долю числа, число делят на количество равных частей',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'длина тела лирохвоста\s*(\d+)\s*см, она составляет\s*1\s*/\s*(\d+)\s*длины хвоста', lower)
    if m:
        body, den = map(int, m.groups())
        tail = body * den
        diff = tail - body
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим длину хвоста: {body} × {den} = {tail} см.',
            f'2) Узнаём, на сколько тело короче хвоста: {tail} - {body} = {diff} см.',
            f'Ответ: {diff} см',
            'Совет: если одна величина составляет долю другой, большую величину находят умножением на число долей',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'вес морской черепахи\s*(\d+)\s*кг, вес сухопутной черепахи составляет\s*1\s*/\s*(\d+)\s*веса морской', lower)
    if m:
        sea, den = map(int, m.groups())
        land = sea // den
        diff = sea - land
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим вес сухопутной черепахи: {sea} : {den} = {land} кг.',
            f'2) Находим разницу: {sea} - {land} = {diff} кг.',
            f'Ответ: {diff} кг',
            'Совет: если нужно узнать, на сколько одна величина больше другой, из большей величины вычитают меньшую',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'длина отреза\s*(\d+)\s*м.*продали\s*1\s*/\s*(\d+)\s*част', lower)
    if m:
        total, den = map(int, m.groups())
        sold = total // den
        left = total - sold
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим, сколько метров продали: {total} : {den} = {sold} м.',
            f'2) Находим, сколько осталось: {total} - {sold} = {left} м.',
            f'Ответ: {left} м',
            'Совет: если продали часть куска, сначала находят эту часть, а потом остаток',
        ]
        return _mass20260416x_finalize(lines)

    m = re.search(r'блокнот стоит\s*(\d+)\s*руб.*что составляет\s*1\s*/\s*(\d+)\s*часть книги', lower)
    if m:
        notebook, den = map(int, m.groups())
        book = notebook * den
        total = notebook + book
        lines = [
            'Задача.',
            _audit_task_line(raw_text),
            'Решение.',
            f'1) Находим цену книги: {notebook} × {den} = {book} руб.',
            f'2) Находим общую стоимость блокнота и книги: {notebook} + {book} = {total} руб.',
            f'Ответ: книга стоит {book} руб., вместе {total} руб.',
            'Совет: если цена одной вещи составляет долю цены другой, большую цену находят умножением на число долей',
        ]
        return _mass20260416x_finalize(lines)

    return None






# Fix formatting of mixed named-quantity answers when the working base unit is not the smallest one.
_UNIT20260416_CONT_SMALLEST_SCALES = {
    'time': {'сут': 86400, 'ч': 3600, 'мин': 60, 'с': 1},
    'mass': {'т': 1000000, 'ц': 100000, 'кг': 1000, 'г': 1},
    'length': {'км': 1000000, 'м': 1000, 'дм': 100, 'см': 10, 'мм': 1},
}






def _frac20260416_cont_try_fraction_time_total(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    lower = text.lower()
    m = re.search(r'(?:проехал|прошел|прошёл)\s+(?:четвертую|шестую)\s+часть пути за\s*(\d+)\s*минут', lower)
    if not m:
        return None
    part_time = int(m.group(1))
    den = 4 if 'четверт' in lower else 6
    whole = part_time * den
    lines = [
        'Задача.',
        _audit_task_line(raw_text),
        'Решение.',
        f'Что известно: 1/{den} пути пройдена за {part_time} минут.',
        'Что нужно найти: время на весь путь.',
        f'1) Весь путь состоит из {den} таких частей.',
        f'2) Находим всё время: {part_time} × {den} = {whole} минут.',
        f'Ответ: {whole} минут',
        'Совет: если одна доля пути занимает известное время, всё время находят умножением на число долей',
    ]
    return _mass20260416x_finalize(lines)






# Keep mixed-length answers in the same unit pattern the child entered, e.g. м + см -> м и см.
def _unit20260416_cont_format_compound_from_base(total_value: int, group: str, base_unit: str, units_present: list[str]) -> str:
    ordered = {
        'time': ['сут', 'ч', 'мин', 'с'],
        'mass': ['т', 'ц', 'кг', 'г'],
        'length': ['км', 'м', 'дм', 'см', 'мм'],
    }[group]
    scales = _UNIT20260416_CONT_SMALLEST_SCALES[group]
    present = set(units_present)
    use_units = [u for u in ordered if u in present]
    if base_unit not in use_units:
        use_units.append(base_unit)
        use_units.sort(key=lambda u: ordered.index(u))
    total_smallest = int(round(total_value * scales[base_unit]))
    smallest_unit = use_units[-1]
    remainder = total_smallest
    smallest_scale = scales[smallest_unit]
    parts = []
    for unit in use_units:
        per = scales[unit] // smallest_scale
        count = remainder // (per * smallest_scale)
        remainder = remainder - count * per * smallest_scale
        if count or parts or unit == use_units[-1]:
            parts.append(f'{int(count)} {unit}')
    return ' '.join(parts)


# Align named-quantity arithmetic with the same visible structure as other expressions.
def _unit20260416_cont_try_arithmetic(raw_text: str) -> Optional[str]:
    text = _frac20260416_cont_norm(raw_text)
    m = re.fullmatch(r'(.+?)\s*([+\-])\s*(.+?)\s*=?', text)
    if not m:
        return None
    left_text, op, right_text = m.group(1).strip(), m.group(2), m.group(3).strip()
    left = _unit20260416_cont_parse_quantity(left_text)
    right = _unit20260416_cont_parse_quantity(right_text)
    if not left or not right or left['group'] != right['group']:
        return None

    all_units = left['units'] + right['units']
    group = left['group']
    base_unit = _unit20260416_cont_base_unit(group, all_units)
    left_base = _unit20260416_cont_total_in_unit(left, base_unit)
    right_base = _unit20260416_cont_total_in_unit(right, base_unit)
    result_base = left_base + right_base if op == '+' else left_base - right_base
    if result_base < 0:
        return None

    answer_text = _unit20260416_cont_format_compound_from_base(result_base, group, base_unit, all_units)
    sign_text = '+' if op == '+' else '-'
    action_text = 'Складываем' if op == '+' else 'Вычитаем'
    lines = [
        'Пример: ' + raw_text.strip(),
        'Порядок действий:',
        '1',
        raw_text.strip(),
        'Решение по действиям:',
        f'1) Переводим первое именованное число в {base_unit}: {left["pretty"]} = {left_base} {base_unit}.',
        f'2) Переводим второе именованное число в {base_unit}: {right["pretty"]} = {right_base} {base_unit}.',
        f'3) {action_text}: {left_base} {sign_text} {right_base} = {result_base} {base_unit}.',
        f'4) Переводим ответ обратно: {result_base} {base_unit} = {answer_text}.',
        f'Ответ: {answer_text}',
        'Совет: при действиях с именованными величинами сначала переводят их в одинаковые единицы',
    ]
    return _mass20260416x_finalize(lines)


# --- integrated extra patch from extra_patch_20260416ak.py ---
import ast
import json
import math
import os
import re
from fractions import Fraction
from typing import Any, Callable, Optional



def _find_post_change_distribution_anchor(lower_text: str) -> Optional[re.Match[str]]:
    pattern = re.compile(
        r'\b(?:раздали|раздал|раздала|разложили|разложил|разложила|разделили|разделил|разделила|поделили|поделил|поделила|распределили|распределил|распределила)\b(?=[^.?!]*\bпоровну\b)',
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(lower_text))
    return matches[-1] if matches else None


def _extract_distribution_group(lower_text: str, start_index: int) -> tuple[Optional[Fraction], str]:
    tail = lower_text[start_index:]
    patterns = (
        re.compile(r'поровну\s+(?:в|на|между|по)\s*(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+)', re.IGNORECASE),
        re.compile(
            r'(?:раздали|раздал|раздала|разложили|разложил|разложила|разделили|разделил|разделила|поделили|поделил|поделила|распределили|распределил|распределила)\s+поровну\s*(?:в|на|между|по)?\s*(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+)',
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.search(tail)
        if match:
            return _to_fraction(match.group(1)), _normalize_space(match.group(2)).strip(' .,!?:;')
    number_match = re.search(r'\d+(?:[.,]\d+)?', tail)
    if not number_match:
        return None, ''
    return _to_fraction(number_match.group(0)), _extract_word_after(tail, number_match.end())


def _looks_like_post_change_equal_parts_problem(text: str) -> bool:
    cleaned = _clean_text(text)
    lower = cleaned.lower().replace('ё', 'е')
    distribution_match = _find_post_change_distribution_anchor(lower)
    if 'поровну' not in lower or distribution_match is None:
        return False
    prefix = lower[:distribution_match.start()]
    actions, _ = _extract_sequential_actions(prefix)
    if actions:
        return True
    quantities = [quantity for quantity in _extract_compound_quantities(cleaned) if quantity['end'] <= distribution_match.start()]
    return len(quantities) >= 2


def _extract_purchase_entries_for_local_solver(parsing_lower: str) -> list[dict[str, Any]]:
    purchase_pattern = re.compile(
        r'(\d+(?:[.,]\d+)?)\s+([а-яёa-z-]+(?:\s+[а-яёa-z-]+){0,2})\s+по\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE,
        re.IGNORECASE,
    )
    single_price_pattern = re.compile(
        r'(?:(\d+(?:[.,]\d+)?)\s+)?([а-яёa-z-]+(?:\s+[а-яёa-z-]+){0,2})\s+за\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE + r'\s*$',
        re.IGNORECASE,
    )
    purchases: list[dict[str, Any]] = []

    for match in purchase_pattern.finditer(parsing_lower):
        quantity = _to_fraction(match.group(1))
        item_label = _normalize_space(match.group(2)).strip(' .,!?:;')
        unit_price = _to_fraction(match.group(3))
        if quantity <= 0 or unit_price < 0:
            return []
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
    return purchases


def _extract_initial_money_for_local_solver(parsing_lower: str, ask_remaining: bool) -> tuple[Optional[Fraction], Optional[tuple[int, int]], str]:
    initial_money = None
    initial_money_span = None
    money_source = 'initial'
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
    return initial_money, initial_money_span, money_source


def _extract_extra_expenses_for_local_solver(parsing_lower: str, initial_money_span: Optional[tuple[int, int]]) -> list[dict[str, Any]]:
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

    return extra_expenses


def _extract_extra_incomes_for_local_solver(parsing_lower: str, initial_money_span: Optional[tuple[int, int]]) -> list[dict[str, Any]]:
    extra_incomes: list[dict[str, Any]] = []
    seen_income_spans: set[tuple[int, int]] = set()

    def _add_extra_income(amount_text: str, label: str, span: tuple[int, int]) -> None:
        if span in seen_income_spans:
            return
        if initial_money_span and not (span[1] <= initial_money_span[0] or span[0] >= initial_money_span[1]):
            return
        amount = _to_fraction(amount_text)
        if amount < 0:
            return
        seen_income_spans.add(span)
        cleaned_label = _normalize_space(label).strip(' .,!?:;') or 'дополнительные деньги'
        extra_incomes.append({'amount': amount, 'label': cleaned_label})

    income_patterns = (
        re.compile(
            r'(?:^|[,.!?;]\s*|\s+)(?:потом|затем|после\s+этого|позже)?\s*(?:(?:мама|папа|бабушка|дедушка|друг|подруга|учитель(?:ница)?|тетя|тётя|дядя)\s+)?(?:дал(?:а|и)?|дадут|подарил(?:а|и)?|подарят|вернул(?:а|и)?|вернут)\s*(?:ей|ему|им|мне|нам)?\s*(?:ещё|еще)?\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE + r'(?!\s*за)',
            re.IGNORECASE,
        ),
        re.compile(
            r'(?:^|[,.!?;]\s*|\s+)(?:потом|затем|после\s+этого|позже)?\s*(?:ей|ему|им|мне|нам)\s*(?:дали|дала|дал|дадут|подарили|подарила|подарил|подарят|вернули|вернул(?:а|и)?|вернут)\s*(?:ещё|еще)?\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE + r'(?!\s*за)',
            re.IGNORECASE,
        ),
        re.compile(
            r'(?:^|[,.!?;]\s*|\s+)(?:потом|затем|после\s+этого|позже)?\s*(?:получил(?:а|и)?|получит|получат)\s*(?:ещё|еще)?\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE + r'(?!\s*за)',
            re.IGNORECASE,
        ),
    )
    for pattern in income_patterns:
        for match in pattern.finditer(parsing_lower):
            _add_extra_income(match.group(1), 'дополнительные деньги', match.span(1))
    return extra_incomes


def _extract_final_money_balance_for_local_solver(parsing_lower: str) -> Optional[Fraction]:
    result_value: Optional[Fraction] = None
    patterns = (
        re.compile(r'(?:остал(?:ось|ся|ась|ись)|стал(?:о|а|и)|получил(?:ось)?|получилось|получили|вышло|вышла|вышли)\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE, re.IGNORECASE),
        re.compile(r'у\s+[а-яёa-z-]+\s+(?:остал(?:ось|ся|ась|ись)|стал(?:о|а|и))\s*(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE, re.IGNORECASE),
    )
    for pattern in patterns:
        for match in pattern.finditer(parsing_lower):
            result_value = _to_fraction(match.group(1))
    return result_value


def _looks_like_reverse_money_purchase_problem(text: str) -> bool:
    lower = _clean_text(text).lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if 'сколько' not in question:
        return False
    if 'сначала' not in question and 'было' not in question:
        return False
    if re.search(_RUBLE_RE, lower) is None and 'денег' not in lower:
        return False
    if _looks_like_any_reverse_dual_subject_total_after_changes_problem(text):
        return False
    parsing_lower = _replace_small_number_words(lower)
    if not _extract_purchase_entries_for_local_solver(parsing_lower):
        return False
    return _extract_final_money_balance_for_local_solver(parsing_lower) is not None


def _looks_like_money_purchase_flow_problem(text: str) -> bool:
    lower = _clean_text(text).lower().replace('ё', 'е')
    if re.search(r'по\s*\d+(?:[.,]\d+)?\s*' + _RUBLE_RE, lower) is None and re.search(r'за\s*\d+(?:[.,]\d+)?\s*' + _RUBLE_RE, lower) is None:
        return False
    if _looks_like_any_reverse_dual_subject_total_after_changes_problem(text):
        return False
    question = _question_text(text).lower().replace('ё', 'е')
    ask_difference_to_initial = (
        'на сколько рублей стало меньше' in question
        or 'на сколько денег стало меньше' in question
        or re.search(r'на\s+сколько[^?.!]*меньше[^?.!]*(?:было|сначала)', question) is not None
    )
    has_extra_income = any(token in lower for token in (' дал', ' дала', ' дали', ' дадут', 'подар', 'получил', 'получила', 'получили', 'получит', 'вернул', 'вернули', 'вернут'))
    return ask_difference_to_initial or has_extra_income


def _looks_like_unit_price_purchase_problem(text: str) -> bool:
    lower = _clean_text(text).lower().replace('ё', 'е')
    if _looks_like_any_reverse_dual_subject_total_after_changes_problem(text):
        return False
    return (
        re.search(r'по\s*\d+(?:[.,]\d+)?\s*' + _RUBLE_RE, lower) is not None
        and any(word in lower for word in ('купил', 'купила', 'купили', 'заплатил', 'заплатила', 'заплатили', 'осталось', 'сколько заплат'))
    )


def _split_money_action_fragments(raw_text: str) -> list[str]:
    text = _normalize_space(raw_text)
    if not text:
        return []
    parts = re.split(r'[.?!;]+|,\s*|\s+а\s+потом\s+|\s+потом\s+|\s+затем\s+|\s+после\s+этого\s+', text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _looks_like_dual_subject_money_after_changes_problem(raw_text: str) -> bool:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if re.search(_RUBLE_RE, lower) is None and 'денег' not in lower:
        return False
    question = _question_text(text).lower().replace('ё', 'е')
    if not question or _question_asks_initial_state(question):
        return False
    if not any(marker in question for marker in ('сколько', 'на сколько', 'во сколько')):
        return False
    matches = list(_ACTION_VERB_RE.finditer(lower))
    if not matches:
        return False
    prefix = lower[:matches[0].start()]
    if len(re.findall(r'\bу\s+[а-яёa-z-]+\b', prefix, re.IGNORECASE)) < 2 and not (re.search(r'\bперв\w*\b', prefix, re.IGNORECASE) and re.search(r'\bвтор\w*\b', prefix, re.IGNORECASE)):
        return False
    number_matches = list(re.finditer(r'(\d+(?:[.,]\d+)?)\s*' + _RUBLE_RE, prefix, re.IGNORECASE))
    if len(number_matches) < 2:
        return False
    subject_entries = _extract_dual_subject_entries(prefix, number_matches)
    if len(subject_entries) < 2:
        return False
    return True


_FRACTION_WORD_PATTERNS: tuple[tuple[re.Pattern[str], Fraction, str], ...] = (
    (re.compile(r'\bполовин(?:а|у|ы|ой)?\b', re.IGNORECASE), Fraction(1, 2), '1/2'),
    (re.compile(r'\bтреть(?:ю|и|я)?\b', re.IGNORECASE), Fraction(1, 3), '1/3'),
    (re.compile(r'\bчетверт(?:ь|и|ью|ю)?\b', re.IGNORECASE), Fraction(1, 4), '1/4'),
)


def _format_fraction_value(value: Fraction) -> str:
    fraction = Fraction(value)
    if fraction.denominator == 1:
        return _format_number(fraction)
    return f'{_format_number(fraction.numerator)}/{_format_number(fraction.denominator)}'


def _extract_text_fractions(text: str) -> list[dict[str, Any]]:
    lower = _clean_text(text).lower().replace('ё', 'е')
    items: list[dict[str, Any]] = []
    for match in _FRACTION_RE.finditer(lower):
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        if denominator == 0:
            continue
        value = Fraction(numerator, denominator)
        items.append({
            'value': value,
            'display': f'{numerator}/{denominator}',
            'start': match.start(),
            'end': match.end(),
            'raw': match.group(0),
        })
    for pattern, value, display in _FRACTION_WORD_PATTERNS:
        for match in pattern.finditer(lower):
            items.append({
                'value': value,
                'display': display,
                'start': match.start(),
                'end': match.end(),
                'raw': match.group(0),
            })
    items.sort(key=lambda item: item['start'])
    return items


def _fraction_answer_label(raw_text: str, default: str = '') -> str:
    question = _question_text(raw_text).lower().replace('ё', 'е')
    for pattern in (
        r'на\s+сколько\s+(?:остальных\s+)?([а-яёa-z/-]+)',
        r'сколько\s+(?:остальных\s+|осталось\s+|стало\s+|получилось\s+|будет\s+)?([а-яёa-z/-]+)',
    ):
        match = re.search(pattern, question)
        if match:
            label = match.group(1).strip('.,!?')
            if label not in {'остальных', 'осталось', 'стало', 'получилось', 'будет'}:
                return label
    question_label = _question_count_label(raw_text)
    if question_label and question_label not in {'остальных', 'осталось', 'стало', 'получилось', 'будет'}:
        return question_label
    return default

# --- merged segment 002: backend.legacy_runtime_module_shards.tail_runtime_module.segment_002 ---
def _parse_fraction_related_subject_problem(raw_text: str) -> Optional[dict[str, Any]]:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if _extract_compound_quantities(text):
        return None

    fractions = _extract_text_fractions(text)
    if not fractions:
        return None

    quantity_pattern = re.compile(
        r'у\s+([а-яёa-z-]+)\s+(?:было\s*)?(\d+(?:[.,]\d+)?)\s+([а-яёa-z/-]+)',
        re.IGNORECASE,
    )
    quantity_matches = list(quantity_pattern.finditer(lower))
    if not quantity_matches:
        return None

    subject_mentions = list(re.finditer(r'\bу\s+([а-яёa-z-]+)\b', lower, re.IGNORECASE))
    distinct_subjects: list[tuple[str, str]] = []
    for mention in subject_mentions:
        name = mention.group(1)
        key = _soft_person_key(name)
        if key and all(existing_key != key for existing_key, _ in distinct_subjects):
            distinct_subjects.append((key, name))
    if len(distinct_subjects) < 2:
        return None

    for fraction_item in fractions:
        fraction_value = fraction_item['value']
        if fraction_value <= 0:
            continue

        after = lower[fraction_item['end']: fraction_item['end'] + 96]
        before = lower[max(0, fraction_item['start'] - 96): fraction_item['start']]
        if not any(marker in after for marker in ('колич', 'числ', 'от ')) and 'это' not in before:
            continue

        relation_mention = None
        for mention in subject_mentions:
            if mention.start() < fraction_item['start']:
                relation_mention = mention
            else:
                break
        if relation_mention is None:
            continue

        relation_name = relation_mention.group(1)
        relation_key = _soft_person_key(relation_name)
        if not relation_key:
            continue

        known_match = next((match for match in quantity_matches if match.start() < fraction_item['start']), None)
        if known_match is None:
            continue

        known_name = known_match.group(1)
        known_key = _soft_person_key(known_name)
        known_value = _to_fraction(known_match.group(2))
        if known_value <= 0:
            continue
        answer_label = known_match.group(3).strip('.,!?')

        base_name = ''
        base_key = ''
        for pattern in (
            r'(?:от\s+)?(?:количества|числа)\s+([а-яёa-z-]+)',
            r'от\s+([а-яёa-z-]+)',
        ):
            candidate_match = re.search(pattern, after, re.IGNORECASE)
            if candidate_match:
                candidate_name = candidate_match.group(1)
                candidate_key = _soft_person_key(candidate_name)
                if candidate_key:
                    base_name = candidate_name
                    base_key = candidate_key
                    break

        if not base_key:
            other_subjects = [name for key, name in distinct_subjects if key != relation_key]
            if len(other_subjects) == 1:
                base_name = other_subjects[0]
                base_key = _soft_person_key(base_name)

        if not base_key or base_key == relation_key:
            continue

        if known_key == relation_key:
            mode = 'reverse'
            relation_value = known_value
            base_value = relation_value / fraction_value
        elif known_key == base_key:
            mode = 'forward'
            base_value = known_value
            relation_value = base_value * fraction_value
        else:
            continue

        if base_value < 0 or relation_value < 0:
            continue

        return {
            'text': text,
            'lower': lower,
            'question': _question_text(text).lower().replace('ё', 'е'),
            'fraction': fraction_value,
            'fraction_display': _format_fraction_value(fraction_value),
            'fraction_end': fraction_item['end'],
            'mode': mode,
            'answer_label': answer_label,
            'base_name': base_name.capitalize(),
            'base_key': base_key,
            'base_value': base_value,
            'relation_name': relation_name.capitalize(),
            'relation_key': relation_key,
            'relation_value': relation_value,
        }
    return None


def _looks_like_reverse_measured_change_problem(raw_text: str) -> bool:
    text = _clean_text(raw_text)
    if _looks_like_any_reverse_dual_subject_measured_total_after_changes_problem(text):
        return False
    lower = text.lower().replace('ё', 'е')
    quantities = _extract_compound_quantities(text)
    if len(quantities) < 2:
        return False
    if len({quantity['group'] for quantity in quantities}) != 1:
        return False
    if quantities[0]['group'] == 'length' and '/ч' in lower:
        return False
    question = _question_text(text).lower().replace('ё', 'е')
    if not _question_asks_initial_state(question):
        return False
    if not _measure_quantity_has_final_state_marker(lower, quantities[-1]):
        return False

    previous_end = 0
    action_count = 0
    for quantity in quantities[:-1]:
        sign = _infer_measure_change_sign(lower, quantity, previous_end)
        if sign is None:
            return False
        action_count += 1
        previous_end = quantity['end']
    return action_count > 0


def _direct_dual_subject_question_mode(question_lower: str, subject_entries: list[dict[str, Any]]) -> str:
    mode = _reverse_initial_question_mode(question_lower)
    if mode != 'target':
        return mode
    question = _normalize_space(question_lower).lower().replace('ё', 'е')
    order = _question_subject_order(question, subject_entries)
    if len(order) >= 2 and ' и ' in question:
        return 'both'
    return mode


def _subject_location_phrase(entry: dict[str, Any]) -> str:
    label = _normalize_space(str(entry.get('label') or _reverse_subject_phrase(entry)))
    lowered = label.lower().replace('ё', 'е')
    if lowered.startswith(('в ', 'во ', 'из ', 'на ', 'под ', 'над ', 'у ')):
        return label
    return f'у {label}'


def _format_measure_value_text(value: Fraction, group: str, base_unit: str, visible_units: list[str]) -> str:
    return _format_measure_total(value * _MEASURE_GROUP_SCALES[group][base_unit], group, visible_units)


def _looks_like_dual_subject_measured_after_changes_problem(raw_text: str) -> bool:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    question = _question_text(text).lower().replace('ё', 'е')
    if not question or _question_asks_initial_state(question):
        return False
    if not any(marker in question for marker in ('сколько', 'на сколько', 'во сколько')):
        return False
    matches = list(_ACTION_VERB_RE.finditer(lower))
    if not matches:
        return False
    prefix_text = text[:matches[0].start()]
    infos = _extract_dual_measure_subject_infos(prefix_text)
    if len(infos) < 2:
        return False
    if any(info.get('quantity') is None for info in infos[:2]):
        return False
    groups = {info['quantity']['group'] for info in infos[:2]}
    if len(groups) != 1:
        return False
    return True


_PLAIN_NUMBER_RE = re.compile(r'(?<!/)\b(\d+(?:[.,]\d+)?)\b(?!\s*/)')
_FRACTION_RE = re.compile(r'(\d+)\s*/\s*(\d+)')
_FRACTION_CHANGE_ACTION_HINTS = (
    'отдал', 'отдала', 'отдали', 'съел', 'съела', 'съели', 'раздали', 'раздал', 'раздала',
    'продали', 'продал', 'продала', 'использовали', 'использовал', 'использовала',
    'отрезали', 'отрезал', 'отрезала', 'прошли', 'прошёл', 'прошел', 'прошла',
    'проехали', 'проехал', 'проехала', 'осталось', 'остался', 'осталась',
)
_TEMPERATURE_UP_HINTS = {'теплее', 'выше'}
_TEMPERATURE_DOWN_HINTS = {'холоднее', 'ниже'}


def _allowed_ai_extra_numbers_for_text(user_text: str) -> set[Fraction]:
    lower = _clean_text(user_text).lower().replace('ё', 'е')
    allowed: set[Fraction] = set()
    if 'периметр' in lower and any(shape in lower for shape in ('прямоугольник', 'квадрат')):
        allowed.add(Fraction(2))
    if re.search(r'\b(?:ч|час(?:а|ов)?|мин(?:ут(?:а|ы|у)?)?|сек(?:унд(?:а|ы|у)?)?|км/ч|км/мин|м/ч|м/мин|м/с|см/с)\b', lower):
        allowed.add(Fraction(60))
    if (re.search(r'\bм\b', lower) and re.search(r'\bсм\b', lower)) or re.search(r'процент|%', lower):
        allowed.add(Fraction(100))
    return allowed


class _AiMathValidationError(ValueError):
    pass


def _plain_number_matches(text: str) -> list[re.Match[str]]:
    return list(_PLAIN_NUMBER_RE.finditer(text))


def _looks_like_fraction_change_problem(text: str) -> bool:
    lower = _clean_text(text).lower()
    return bool(_FRACTION_RE.search(lower)) and any(marker in lower for marker in _FRACTION_CHANGE_ACTION_HINTS)


def _looks_like_equal_parts_problem(text: str) -> bool:
    lower = _clean_text(text).lower()
    if 'равные части' in lower and bool(re.search(r'(?:разделили|разрезали|распилили|поделили)\s+на\s*\d+', lower)):
        return True
    return bool(
        re.search(
            r'(?:на|в)\s*\d+(?:[.,]\d+)?\s+[а-яёa-z-]+[^.!?]{0,120}?(?:поровну\s+)?(?:расставили|разложили|раздали|распределили|разместили|развесили|разделили)\s*\d+(?:[.,]\d+)?\s+[а-яёa-z-]+',
            lower,
        )
    )


def _looks_like_temperature_change_problem(text: str) -> bool:
    lower = _clean_text(text).lower()
    return 'градус' in lower and any(word in lower for word in _TEMPERATURE_UP_HINTS | _TEMPERATURE_DOWN_HINTS)


def _looks_like_volume_change_problem(text: str) -> bool:
    lower = _clean_text(text).lower().replace('ё', 'е')
    return any(unit in lower for unit in (' л', ' мл', 'литр', 'миллилитр')) and any(marker in lower for marker in _NEGATIVE_CHANGE_MARKERS + _POSITIVE_CHANGE_MARKERS)


def _parse_fraction_like(value: Any) -> Optional[Fraction]:
    text = _normalize_space(str(value))
    if not text:
        return None
    if re.fullmatch(r'-?\d+\s+\d+/\d+', text):
        sign = -1 if text.startswith('-') else 1
        body = text[1:] if sign < 0 else text
        whole_part, fraction_part = body.split()
        numerator, denominator = fraction_part.split('/')
        return sign * (Fraction(int(whole_part), 1) + Fraction(int(numerator), int(denominator)))
    if re.fullmatch(r'-?\d+/\d+', text):
        numerator, denominator = text.split('/')
        return Fraction(int(numerator), int(denominator))
    if re.fullmatch(r'-?\d+(?:[.,]\d+)?', text):
        return Fraction(text.replace(',', '.'))
    return None


def _eval_fraction_ast(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Expression):
        return _eval_fraction_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_fraction_ast(node.operand)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _eval_fraction_ast(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _eval_fraction_ast(node.left) + _eval_fraction_ast(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
        return _eval_fraction_ast(node.left) - _eval_fraction_ast(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _eval_fraction_ast(node.left) * _eval_fraction_ast(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        denominator = _eval_fraction_ast(node.right)
        if denominator == 0:
            raise _AiMathValidationError('division by zero')
        return _eval_fraction_ast(node.left) / denominator
    raise _AiMathValidationError('unsupported expression')


def _safe_eval_fraction_expression(expression: str) -> Optional[Fraction]:
    cleaned = _normalize_ai_equation(expression)
    if not cleaned or not re.fullmatch(r'[0-9+\-*/().]+', cleaned):
        return None
    try:
        tree = ast.parse(cleaned, mode='eval')
        return _eval_fraction_ast(tree)
    except Exception:
        return None


def _equation_uses_only_prompt_numbers(expression: str, user_text: str) -> bool:
    equation_numbers = {_parse_fraction_like(token) for token in re.findall(r'\d+(?:\.\d+)?', _normalize_ai_equation(expression))}
    input_numbers = {_parse_fraction_like(token) for token in re.findall(r'\d+(?:[.,]\d+)?', _clean_text(user_text))}
    equation_numbers.discard(None)
    input_numbers.discard(None)
    return equation_numbers.issubset(input_numbers | _allowed_ai_extra_numbers_for_text(user_text))


def _validate_diagram_spec(spec: Any) -> Optional[dict[str, Any]]:
    if spec in (None, '', []):
        return None
    if not isinstance(spec, dict):
        return None
    diagram_type = str(spec.get('type') or '').strip()
    labels = spec.get('labels') if isinstance(spec.get('labels'), dict) else {}
    normalized_labels = {str(key): str(value) for key, value in labels.items() if str(key).strip() and str(value).strip()}
    highlight = str(spec.get('highlight') or '').strip() or None
    if not diagram_type:
        return None
    return {
        'type': diagram_type,
        'labels': normalized_labels,
        'highlight': highlight,
    }


def _should_prevent_old_price_solver(text: str) -> bool:
    return _looks_like_direct_price_problem(text)


def _should_prevent_old_motion_solver(text: str) -> bool:
    return _looks_like_relative_motion_distance(text)


def _should_prevent_old_fraction_change_solver(text: str) -> bool:
    return _looks_like_fraction_change_problem(text)


def _should_prevent_old_equal_parts_solver(text: str) -> bool:
    return _looks_like_equal_parts_problem(text)


def _should_prevent_old_post_change_equal_parts_solver(text: str) -> bool:
    return _looks_like_post_change_equal_parts_problem(text)


def _should_prevent_old_ratio_after_change_solver(text: str) -> bool:
    return _looks_like_ratio_after_change_problem(text)


def _should_prevent_old_difference_after_change_solver(text: str) -> bool:
    return _looks_like_difference_after_change_problem(text)


def _should_prevent_old_temperature_solver(text: str) -> bool:
    return _looks_like_temperature_change_problem(text)


def _looks_like_any_reverse_dual_subject_total_after_changes_problem(raw_text: str) -> bool:
    text = _clean_text(raw_text)
    lower = text.lower().replace('ё', 'е')
    if _extract_compound_quantities(text):
        return False
    question = _question_text(text).lower().replace('ё', 'е')
    if not question or not any(marker in question for marker in ('сколько', 'на сколько', 'во сколько')):
        return False
    if not _question_asks_initial_state(question):
        return False
    if _extract_reverse_transfer_total_value(text) is None:
        return False

    actions, matches = _extract_sequential_actions(lower)
    if not actions or not matches or len(actions) != len(matches):
        return False

    subject_entries = _extract_reverse_transfer_subject_entries(lower)
    if len(subject_entries) < 2:
        subject_entries = _extract_named_subject_entries_from_text(lower)
    if len(subject_entries) < 2:
        return False

    classified = _classify_reverse_transfer_mixed_actions(lower, actions, matches, subject_entries)
    if not classified:
        return False
    return not any(item['kind'] == 'transfer' for item in classified)


def _looks_like_ambiguous_reverse_dual_subject_total_after_changes_problem(raw_text: str) -> bool:
    return (
        _looks_like_any_reverse_dual_subject_total_after_changes_problem(raw_text)
        and not _looks_like_reverse_dual_subject_total_relation_after_changes_problem(raw_text)
        and not _looks_like_reverse_dual_subject_total_after_changes_problem(raw_text)
    )
