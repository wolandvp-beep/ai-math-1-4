import ast
import math
import os
import re
from fractions import Fraction
from typing import Optional, List, Tuple

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://wolandvp-beep.github.io"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DEEPSEEK_API_KEY = os.environ.get("myapp_ai_math_1_4_API_key")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("Переменная окружения myapp_ai_math_1_4_API_key не установлена")

SYSTEM_PROMPT = """
Ты — точный и спокойный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Не используй markdown, списки, нумерацию, смайлики, похвалу, лишние вступления и пустые фразы.
Каждая строка — одна полезная мысль.
Не повторяй одну и ту же мысль разными словами.

Формат ответа:
сначала 2–5 коротких строк объяснения;
только для уравнения добавь строку "Проверка: ...";
потом строка "Ответ: ...";
последняя строка "Совет: ...".

Правила:
Не пиши готовый ответ в первой строке.
Не дублируй итог в объяснении и в строке "Ответ:".
Совет должен быть коротким, учебным и конкретным.
Для обычного примера не пиши "Проверка:".
Для деления объясняй шаги по порядку.

Сам определи тип задачи и объясняй так:
текстовая задача — что нужно найти и почему подходит это действие;
пример или выражение — что ищем и в каком порядке считаем;
уравнение — оставь x отдельно и сделай короткую проверку;
дроби — сначала смотри на знаменатели;
геометрия — сначала назови правило, потом подставь числа.

Не выдумывай данные.
Если запись непонятная или это не задача по математике, попроси записать пример понятнее.
""".strip()

BANNED_OPENERS = re.compile(
    r"^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\b",
    re.IGNORECASE,
)
LEADING_FILLER_SENTENCE = re.compile(
    r"^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\b[^.!?\n]*[.!?]\s*",
    re.IGNORECASE,
)

NON_MATH_REPLY = (
    "Не видно точной математической записи.\n"
    "Напишите пример или задачу понятнее.\n"
    "Ответ: сначала нужно уточнить запись.\n"
    "Совет: пишите числа и знаки действия полностью."
)

DEFAULT_ADVICE = {
    "expression": "считай по порядку и не пропускай действие.",
    "equation": "в уравнении оставляй x отдельно и делай проверку.",
    "fraction": "сначала смотри на знаменатели, потом выполняй действие.",
    "geometry": "сначала пойми, что нужно найти, а потом выбирай правило.",
    "word": "сначала пойми смысл задачи, а потом выбирай действие.",
    "other": "прочитай запись ещё раз и решай по шагам.",
}

OPERATOR_SYMBOLS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "×",
    ast.Div: ":",
}

OPERATOR_VERBS = {
    ast.Add: "складываем",
    ast.Sub: "вычитаем",
    ast.Mult: "умножаем",
    ast.Div: "делим",
}

PRECEDENCE = {
    ast.Add: 1,
    ast.Sub: 1,
    ast.Mult: 2,
    ast.Div: 2,
}

def is_int_literal_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int

def int_from_literal_node(node: ast.AST) -> int:
    if not is_int_literal_node(node):
        raise ValueError("Expected integer literal node")
    return int(node.value)

WORD_GAIN_HINTS = (
    "еще",
    "ещё",
    "добав",
    "купил",
    "купила",
    "купили",
    "подар",
    "наш",
    "принес",
    "принёс",
    "принесли",
    "положил",
    "положила",
    "положили",
    "стало",
    "теперь",
    "прилетели",
    "приехали",
)

WORD_LOSS_HINTS = (
    "отдал",
    "отдала",
    "отдали",
    "съел",
    "съела",
    "съели",
    "убрал",
    "убрала",
    "убрали",
    "забрал",
    "забрала",
    "забрали",
    "потер",
    "потрат",
    "продал",
    "продала",
    "продали",
    "ушло",
    "остал",
    "сломал",
    "сломала",
    "сломали",
    "снял",
    "сняла",
    "сняли",
)

WORD_COMPARISON_HINTS = (
    "на сколько больше",
    "на сколько меньше",
)

GROUPING_VERBS = (
    "разлож",
    "раздал",
    "раздала",
    "раздали",
    "расстав",
    "упакова",
    "улож",
    "постав",
    "посад",
    "слож",
)

GEOMETRY_UNIT_RE = re.compile(r"\b(мм|см|дм|м|км)\b", re.IGNORECASE)

def strip_known_prefix(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(
        r"^(?:задача|пример|уравнение|дроби|геометрия|выражение|математика)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()

def normalize_dashes(text: str) -> str:
    return (
        str(text or "")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
    )

def normalize_cyrillic_x(text: str) -> str:
    return str(text or "").replace("Х", "x").replace("х", "x")

def to_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None

    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace("×", "*").replace("÷", "/").replace(":", "/")
    text = re.sub(r"(?<=\d)\s*[xXx]\s*(?=\d)", " * ", text)
    text = re.sub(r"\s*=\s*\??\s*$", "", text).strip()
    text = re.sub(r"\s*\?\s*$", "", text).strip()

    if re.search(r"[A-Za-zА-Яа-я]", text):
        return None
    if not re.fullmatch(r"[\d\s()+\-*/]+", text):
        return None

    compact = re.sub(r"\s+", "", text)
    if not compact or not re.search(r"[+\-*/]", compact):
        return None
    return compact

def to_equation_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None

    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace("X", "x")
    text = text.replace("×", "*").replace("÷", "/").replace(":", "/")
    text = re.sub(r"\s+", "", text)

    if text.count("=") != 1 or text.count("x") != 1:
        return None
    if not re.fullmatch(r"[\dx=+\-*/]+", text):
        return None
    return text

def to_fraction_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None

    text = normalize_dashes(text)
    text = re.sub(r"[=?]+$", "", text).strip()
    if not re.fullmatch(r"\s*\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+\s*", text):
        return None
    return text

def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"

def format_number(value: int) -> str:
    return str(value)

def normalize_sentence(text: str) -> str:
    line = str(text or "").strip()
    if not line:
        return ""
    line = line.rstrip()
    if line[-1] not in ".!?":
        line += "."
    return line

def join_explanation_lines(*lines: str) -> str:
    parts = [normalize_sentence(line) for line in lines if str(line or "").strip()]
    return "\n".join(parts)

def default_advice(kind: str) -> str:
    return DEFAULT_ADVICE.get(kind, DEFAULT_ADVICE["other"])

def normalize_word_problem_text(text: str) -> str:
    cleaned = strip_known_prefix(text)
    cleaned = normalize_dashes(cleaned)
    cleaned = cleaned.replace("ё", "е").replace("Ё", "Е")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

def extract_ordered_numbers(text: str):
    return [int(value) for value in re.findall(r"\d+", str(text or ""))]

def contains_any_fragment(text: str, fragments) -> bool:
    base = str(text or "")
    return any(fragment in base for fragment in fragments)

def geometry_unit(text: str) -> str:
    match = GEOMETRY_UNIT_RE.search(str(text or ""))
    return match.group(1).lower() if match else ""

def with_unit(value: int, unit: str, square: bool = False) -> str:
    suffix = ""
    if unit:
        suffix = f" {unit}²" if square else f" {unit}"
    return f"{value}{suffix}"

def plural_form(count: int, one: str, few: str, many: str) -> str:
    value = abs(int(count)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return many
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many

def build_column_addition_steps(numbers: List[int]) -> List[str]:
    if len(numbers) < 2:
        return []
    str_nums = [str(n) for n in numbers]
    max_len = max(len(s) for s in str_nums)
    padded = [s.rjust(max_len, '0') for s in str_nums]
    lines = ["Решение."]
    lines.append("Записываем числа в столбик (единицы под единицами, десятки под десятками):")
    for i, p in enumerate(padded):
        sign = "+" if i == 0 else " "
        lines.append(f"{sign}{p}")
    lines.append("---")
    carry = 0
    result_digits = []
    steps = []
    for pos in range(max_len - 1, -1, -1):
        column_sum = carry
        place_name = ""
        if pos == max_len - 1:
            place_name = "единицы"
        elif pos == max_len - 2:
            place_name = "десятки"
        elif pos == max_len - 3:
            place_name = "сотни"
        elif pos == max_len - 4:
            place_name = "тысячи"
        else:
            place_name = f"разряд {max_len - pos}"
        for p in padded:
            column_sum += int(p[pos])
        digit = column_sum % 10
        carry = column_sum // 10
        result_digits.insert(0, str(digit))
        if carry:
            steps.append(f"Складываем {place_name}: {column_sum}, пишем {digit}, {carry} запоминаем.")
        else:
            steps.append(f"Складываем {place_name}: {column_sum}, пишем {digit}.")
    if carry:
        result_digits.insert(0, str(carry))
        steps.append(f"Остался {carry} — записываем его слева.")
    result = int(''.join(result_digits))
    return lines + steps + [f"Ответ: {result}"]

def build_column_subtraction_steps(minuend: int, subtrahend: int) -> List[str]:
    if minuend < subtrahend:
        return ["Решение.", "Нельзя вычесть большее из меньшего (в начальной школе).", "Ответ: отрицательное число."]
    str_min = str(minuend)
    str_sub = str(subtrahend).rjust(len(str_min), '0')
    lines = ["Решение."]
    lines.append("Записываем вычитаемое под уменьшаемым (единицы под единицами):")
    lines.append(str_min)
    lines.append(f"-{str_sub}")
    lines.append("---")
    borrow = 0
    result_digits = []
    steps = []
    for pos in range(len(str_min)-1, -1, -1):
        min_digit = int(str_min[pos]) - borrow
        sub_digit = int(str_sub[pos])
        if min_digit < sub_digit:
            min_digit += 10
            borrow = 1
            steps.append(f"В разряде {len(str_min)-pos} занимаем десяток: {min_digit} - {sub_digit} = {min_digit - sub_digit}")
        else:
            borrow = 0
            steps.append(f"В разряде {len(str_min)-pos}: {min_digit} - {sub_digit} = {min_digit - sub_digit}")
        result_digits.insert(0, str(min_digit - sub_digit))
    result = int(''.join(result_digits))
    return lines + steps + [f"Ответ: {result}"]

def build_column_multiplication_steps(multiplicand: int, multiplier: int) -> List[str]:
    if multiplier == 0:
        return ["Решение.", "При умножении на ноль результат всегда ноль."]
    if multiplier == 1:
        return ["Решение.", "При умножении на единицу число не меняется."]
    str_multi = str(multiplicand)
    str_multiplier = str(multiplier)
    lines = ["Решение."]
    lines.append(f"Записываем умножение в столбик: {str_multi} × {str_multiplier}")
    lines.append(" " * (len(str_multi) - len(str_multiplier) + 2) + str_multiplier)
    lines.append(" " * (len(str_multi) + 2) + "×")
    lines.append("---")
    partial_products = []
    for i, ch in enumerate(reversed(str_multiplier)):
        digit = int(ch)
        product = multiplicand * digit
        if product == 0:
            continue
        padding = " " * (len(str_multi) - len(str(product)) + i)
        partial_products.append(f"{padding}{product}")
        lines.append(f"{padding}{product}  ← умножаем на {digit} (разряд {i+1})")
    if not partial_products:
        lines.append("0")
        return lines + ["Ответ: 0"]
    lines.append("---")
    total = 0
    for pp in partial_products:
        total += int(pp.strip())
    lines.append(f"Складываем частичные произведения: {total}")
    return lines + [f"Ответ: {total}"]

def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: в задачах 'во сколько раз' нужно делить на ненулевое число",
        )
    if bigger % smaller != 0:
        return None

    result = bigger // smaller
    return join_explanation_lines(
        "Решение.",
        f"Нужно узнать, во сколько раз одно число больше или меньше другого",
        f"Для этого делим большее число на меньшее: {bigger} : {smaller} = {result}",
        f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
        "Совет: вопрос 'во сколько раз больше или меньше' обычно решаем делением",
    )

def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Решение.",
        f"Если было {first} и добавили {second}, то всего стало {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько стало или сколько всего, часто подходит сложение",
    )

def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Решение.",
        f"Было {first}, убрали {second}",
        f"Считаем: {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если что-то убрали, отдали или съели, обычно нужно вычитание",
    )

def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Решение.",
        "Сравниваем два числа",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос 'на сколько больше или меньше' обычно решаем вычитанием",
    )

def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Решение.",
        f"Осталось {remaining}, убрали {removed}",
        f"Считаем: {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: если что-то убрали и спрашивают, сколько было сначала, помогает сложение",
    )

def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Решение.",
        f"Стало {final_total}, добавили {added}",
        f"Считаем: {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: если что-то добавили и спрашивают, сколько было сначала, обычно нужно вычитание",
    )

def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Решение.",
        "Сравниваем, на сколько стало больше",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, сравни число было и число стало",
    )

def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Решение.",
        "Сравниваем, на сколько стало меньше",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, вычти то, что осталось, из того, что было",
    )

def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    group_word = plural_form(groups, "группа", "группы", "групп")
    return join_explanation_lines(
        "Решение.",
        f"Есть {groups} {group_word} по {per_group}",
        f"Считаем: {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова 'по ... в каждой' часто подсказывают умножение",
    )

def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь, на сколько частей делят предметы",
        )

    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Решение.",
            f"Нужно разделить {total} поровну на {groups} частей",
            f"Делим: {total} : {groups} = {quotient}",
            f"Значит каждый получит {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова 'поровну' и 'каждый' часто подсказывают деление",
        )

    return join_explanation_lines(
        "Решение.",
        f"Нужно разделить {total} поровну на {groups} частей",
        f"Делим: {total} : {groups} = {quotient}, остаток {remainder}",
        f"Каждый получит {quotient}, и останется {remainder}",
        f"Ответ: каждому по {quotient}, остаток {remainder}",
        "Совет: при делении поровну остаток должен быть меньше делителя",
    )

def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "Решение.",
            "В одной группе не может быть ноль предметов",
            "Ответ: запись задачи неверная",
            "Совет: проверь, сколько предметов должно быть в одной группе",
        )

    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        group_word = plural_form(quotient, "группа", "группы", "групп")
        return join_explanation_lines(
            "Решение.",
            f"Нужно узнать, сколько групп по {per_group} получится из {total}",
            f"Делим: {total} : {per_group} = {quotient}",
            f"Получится {quotient} {group_word}",
            f"Ответ: {quotient}",
            "Совет: если известно, сколько предметов в одной группе, число групп находим делением",
        )

    if needs_extra_group:
        return join_explanation_lines(
            "Решение.",
            f"Полных групп по {per_group} получается {quotient}, и ещё остаётся {remainder}",
            "Чтобы все предметы поместились, нужна ещё одна группа",
            f"Ответ: {quotient + 1}",
            "Совет: если что-то осталось, иногда нужна ещё одна коробка или место",
        )

    if explicit_remainder:
        full_group_phrase = plural_form(quotient, "полная группа", "полные группы", "полных групп")
        return join_explanation_lines(
            "Решение.",
            f"Считаем, сколько полных групп по {per_group} получится из {total}",
            f"Делим: {total} : {per_group} = {quotient}, остаток {remainder}",
            f"Значит получится {quotient} {full_group_phrase}, и останется {remainder}",
            f"Ответ: {quotient} {full_group_phrase}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше числа предметов в одной группе",
        )

    return None

SEQUENTIAL_GAIN_STEMS = (
    "еще",
    "ещё",
    "добав",
    "купил",
    "купила",
    "купили",
    "подар",
    "наш",
    "принес",
    "принёс",
    "принесли",
    "положил",
    "положила",
    "положили",
    "дала",
    "дали",
    "получил",
    "получила",
    "получили",
    "вош",
    "заш",
    "прилет",
    "приех",
    "прибав",
)

SEQUENTIAL_LOSS_STEMS = (
    "отдал",
    "отдала",
    "отдали",
    "съел",
    "съела",
    "съели",
    "убрал",
    "убрала",
    "убрали",
    "забрал",
    "забрала",
    "забрали",
    "потер",
    "потрат",
    "продал",
    "продала",
    "продали",
    "выш",
    "уш",
    "снял",
    "сняла",
    "сняли",
    "улетел",
    "улетели",
    "уех",
    "завял",
)

def has_word_stem(text: str, stems) -> bool:
    fragment = str(text or "").lower().replace("ё", "е")
    return any(re.search(rf"\b{re.escape(stem)}", fragment) for stem in stems)

def apply_more_less(base: int, delta: int, mode: str) -> Optional[int]:
    if mode == "больше":
        return base + delta
    result = base - delta
    return result if result >= 0 else None

def extract_relation_pairs(text: str):
    return [(int(match.group(1)), match.group(2)) for match in re.finditer(r"на\s+(\d+)\s+(больше|меньше)", str(text or ""))]

def classify_change_fragment(fragment: str) -> Optional[str]:
    part = str(fragment or "").lower().replace("ё", "е")
    gain = has_word_stem(part, SEQUENTIAL_GAIN_STEMS)
    loss = has_word_stem(part, SEQUENTIAL_LOSS_STEMS)
    if gain and not loss:
        return "gain"
    if loss and not gain:
        return "loss"
    return None

def split_between_change_fragment(fragment: str):
    part = str(fragment or "")
    pieces = re.split(r"(?:,\s*)?(?:а\s+потом|потом|а\s+затем|затем)\b", part, maxsplit=1)
    if len(pieces) == 2:
        return pieces[0], pieces[1]
    return part, part

def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        "Решение.",
        f"Во втором количестве на {delta} {mode}",
        f"Считаем: {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: если одно количество больше или меньше другого, сначала найди его значение",
    )

def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        "Решение.",
        f"Во втором количестве: {base} {sign} {delta} = {related}",
        f"Теперь считаем вместе: {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: если одно количество зависит от другого, сначала найди его, потом считай всё вместе",
    )

def explain_sequential_change_word_problem(start: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = apply_more_less(start, first_delta, "больше" if first_mode == "gain" else "меньше")
    if middle is None:
        return None
    result = apply_more_less(middle, second_delta, "больше" if second_mode == "gain" else "меньше")
    if result is None:
        return None

    first_sign = "+" if first_mode == "gain" else "-"
    second_sign = "+" if second_mode == "gain" else "-"
    first_phrase = "больше" if first_mode == "gain" else "меньше"
    second_phrase = "больше" if second_mode == "gain" else "меньше"

    return join_explanation_lines(
        "Решение.",
        f"Сначала было {start}",
        f"После первого изменения стало на {first_delta} {first_phrase}: {start} {first_sign} {first_delta} = {middle}",
        f"Потом меняем число ещё раз: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах в два действия считай изменения по порядку",
    )

def explain_relation_chain_word_problem(base: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = apply_more_less(base, first_delta, first_mode)
    if middle is None:
        return None
    result = apply_more_less(middle, second_delta, second_mode)
    if result is None:
        return None

    first_sign = "+" if first_mode == "больше" else "-"
    second_sign = "+" if second_mode == "больше" else "-"

    return join_explanation_lines(
        "Решение.",
        "Сначала находим второе количество",
        f"Оно на {first_delta} {first_mode}: {base} {first_sign} {first_delta} = {middle}",
        f"Потом находим третье количество: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
        "Совет: если одно число зависит от другого несколько раз, находи их по очереди",
    )

def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        "Решение.",
        f"В одинаковых группах: {groups} × {per_group} = {grouped_total}",
        f"Потом прибавляем ещё {extra}: {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
        "Совет: если часть предметов собрана в одинаковые группы, сначала найди эту часть умножением",
    )

def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    if not re.search(r"[а-я]", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 2:
        return None

    asks_total = bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower))
    asks_current = bool(re.search(r"сколько[^.?!]*\b(стало|теперь|осталось)\b", lower))
    asks_plain_quantity = "сколько" in lower and not asks_total and not asks_current and "на сколько" not in lower and "во сколько" not in lower

    relation_pairs = extract_relation_pairs(lower)
    if len(numbers) == 2 and len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        if delta == numbers[1]:
            if asks_total:
                return explain_related_total_word_problem(numbers[0], delta, mode)
            if asks_plain_quantity:
                return explain_related_quantity_word_problem(numbers[0], delta, mode)

    if len(numbers) == 3 and len(relation_pairs) == 2 and asks_plain_quantity:
        (delta1, mode1), (delta2, mode2) = relation_pairs
        if delta1 == numbers[1] and delta2 == numbers[2]:
            chain = explain_relation_chain_word_problem(numbers[0], delta1, mode1, delta2, mode2)
            if chain:
                return chain

    if len(numbers) == 3 and asks_total and ("ещё" in lower or "еще" in lower or "отдельно" in lower) and "по" in lower:
        groups_match = re.search(r"\b(?:в|на)?\s*(\d+)\s+[а-я]+\s+по\s+(\d+)\b", lower)
        if groups_match:
            groups = int(groups_match.group(1))
            per_group = int(groups_match.group(2))
            remaining = list(numbers)
            for value in (groups, per_group):
                if value in remaining:
                    remaining.remove(value)
            if len(remaining) == 1:
                return explain_groups_plus_extra_word_problem(groups, per_group, remaining[0])

    if len(numbers) == 3 and (asks_total or asks_current):
        fragments = re.split(r"\d+", lower)
        if len(fragments) >= 4:
            first_following, second_leading = split_between_change_fragment(fragments[2])
            first_mode = classify_change_fragment(fragments[1]) or classify_change_fragment(first_following)
            second_mode = classify_change_fragment(second_leading) or classify_change_fragment(fragments[3])
            if first_mode and second_mode:
                sequential = explain_sequential_change_word_problem(numbers[0], numbers[1], first_mode, numbers[2], second_mode)
                if sequential:
                    return sequential

    return None

def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    unit = geometry_unit(lower)
    question_parts = [part.strip() for part in re.split(r"[?.!]", lower) if part.strip()]
    question = question_parts[-1] if question_parts else lower
    asks_perimeter = "периметр" in lower
    asks_area = "площад" in lower
    asks_side = any(fragment in question for fragment in ("найди сторону", "найди длину стороны", "одной стороны", "какова сторона"))
    asks_width = any(fragment in question for fragment in ("найди ширину", "какова ширина"))
    asks_length = any(fragment in question for fragment in ("найди длину", "какова длина")) and not asks_width

    if "квадрат" in lower and asks_perimeter and asks_side and nums:
        perimeter = nums[0]
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        return join_explanation_lines(
            "Решение.",
            "У квадрата все стороны равны",
            f"Если периметр равен {perimeter}, одну сторону находим делением на 4",
            f"Считаем: {perimeter} : 4 = {side}",
            f"Ответ: {with_unit(side, unit)}",
            "Совет: чтобы найти сторону квадрата по периметру, дели периметр на 4",
        )

    if "прямоугольник" in lower and asks_perimeter and asks_width and len(nums) >= 2:
        perimeter, length = nums[0], nums[1]
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        width = half - length
        if width < 0:
            return None
        return join_explanation_lines(
            "Решение.",
            "У прямоугольника длина и ширина повторяются по два раза",
            f"Сначала находим сумму длины и ширины: {perimeter} : 2 = {half}",
            f"Потом вычитаем известную длину: {half} - {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: по периметру прямоугольника сначала находи половину периметра",
        )

    if "прямоугольник" in lower and asks_perimeter and asks_length and len(nums) >= 2:
        perimeter, width = nums[0], nums[1]
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        length = half - width
        if length < 0:
            return None
        return join_explanation_lines(
            "Решение.",
            "У прямоугольника длина и ширина повторяются по два раза",
            f"Сначала находим сумму длины и ширины: {perimeter} : 2 = {half}",
            f"Потом вычитаем известную ширину: {half} - {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: по периметру прямоугольника сначала находи половину периметра",
        )

    if "квадрат" in lower and asks_area and asks_side and nums:
        area = nums[0]
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return join_explanation_lines(
            "Решение.",
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Нужно найти число, которое при умножении на себя даёт {area}",
            f"Это {side}, потому что {side} × {side} = {area}",
            f"Ответ: {with_unit(side, unit)}",
            "Совет: если знаешь площадь квадрата, ищи такую сторону, которая в квадрате даёт эту площадь",
        )

    if "прямоугольник" in lower and asks_area and asks_width and len(nums) >= 2:
        area, length = nums[0], nums[1]
        if length == 0 or area % length != 0:
            return None
        width = area // length
        return join_explanation_lines(
            "Решение.",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти ширину, делим площадь на длину: {area} : {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: если известны площадь и длина, ширину находим делением",
        )

    if "прямоугольник" in lower and asks_area and asks_length and len(nums) >= 2:
        area, width = nums[0], nums[1]
        if width == 0 or area % width != 0:
            return None
        length = area // width
        return join_explanation_lines(
            "Решение.",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти длину, делим площадь на ширину: {area} : {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: если известны площадь и ширина, длину находим делением",
        )

    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines(
            "Решение.",
            "Периметр — это сумма всех сторон",
            "У квадрата все стороны равны",
            f"Считаем: {side} × 4 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у квадрата периметр равен четырем одинаковым сторонам",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
            "Решение.",
            "Периметр прямоугольника — это сумма всех сторон",
            f"Сначала складываем длину и ширину: {length} + {width} = {length + width}",
            f"Потом умножаем на 2: ({length} + {width}) × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у прямоугольника удобно сначала сложить длину и ширину, потом умножить на 2",
        )

    if "квадрат" in lower and asks_area and nums:
        side = nums[0]
        result = side * side
        return join_explanation_lines(
            "Решение.",
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Считаем: {side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь показывает, сколько места занимает фигура",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Решение.",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Считаем: {length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: для площади прямоугольника нужно умножить длину на ширину",
        )

    return None

def try_local_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    if not re.search(r"[а-я]", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) != 2:
        return None

    first, second = numbers
    per_group_match = re.search(r"\bпо\s+(\d+)\b", lower)
    per_group = int(per_group_match.group(1)) if per_group_match else None
    other_numbers = list(numbers)
    if per_group is not None and per_group in other_numbers:
        other_numbers.remove(per_group)
    other_value = other_numbers[0] if other_numbers else None

    asks_ratio = "во сколько" in lower and ("больше" in lower or "меньше" in lower)
    asks_compare = contains_any_fragment(lower, WORD_COMPARISON_HINTS) or ("на сколько" in lower and ("больше" in lower or "меньше" in lower))
    asks_initial = "сколько было" in lower
    asks_left = bool(re.search(r"сколько[^.?!]*\bосталось\b", lower))
    asks_now = bool(re.search(r"сколько[^.?!]*\b(стало|теперь)\b", lower))
    asks_total = bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower))
    asks_each = "кажд" in lower or "поровну" in lower
    asks_added = contains_any_fragment(lower, ("сколько добав", "сколько подар", "сколько куп", "сколько прин", "сколько полож"))
    asks_removed = contains_any_fragment(lower, ("сколько отдал", "сколько съел", "сколько убрал", "сколько забрал", "сколько потрат", "сколько продал", "сколько потер"))
    asks_groups = contains_any_fragment(lower, (
        "сколько короб",
        "сколько корзин",
        "сколько пакет",
        "сколько тарел",
        "сколько полок",
        "сколько ряд",
        "сколько групп",
        "сколько ящик",
        "сколько банок",
        "сколько парт",
        "сколько машин",
        "сколько мест",
    ))
    asks_remainder = "остат" in lower or "сколько остан" in lower or "полных" in lower
    needs_extra_group = contains_any_fragment(lower, ("нужно", "нужны", "понадоб", "потребует"))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)

    if asks_ratio:
        ratio = explain_ratio_word_problem(first, second)
        if ratio:
            return ratio

    relation_pairs = extract_relation_pairs(lower)
    if relation_pairs:
        return None

    if asks_compare:
        return explain_comparison_word_problem(first, second)

    if asks_initial and has_loss:
        return explain_find_initial_after_loss_problem(first, second)

    if asks_initial and has_gain:
        explanation = explain_find_initial_after_gain_problem(max(first, second), min(first, second))
        return explanation or None

    if asks_added:
        return explain_find_added_problem(first, second)

    if asks_removed:
        return explain_find_removed_problem(first, second)

    if asks_each and ("раздел" in lower or "раздал" in lower or "раздала" in lower or "раздали" in lower or "получ" in lower or "достал" in lower or "достан" in lower):
        return explain_sharing_word_problem(first, second)

    if "по" in lower and (asks_groups or has_grouping):
        total = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        grouped = explain_group_count_word_problem(total, size, needs_extra_group=needs_extra_group, explicit_remainder=asks_remainder)
        if grouped:
            return grouped

    if "по" in lower and asks_total:
        groups = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        return explain_multiplication_word_problem(groups, size)

    if has_loss and (asks_left or asks_now):
        explanation = explain_subtraction_word_problem(first, second)
        return explanation or None

    if (has_gain and (asks_total or asks_now)) or (asks_total and not has_loss and "по" not in lower):
        return explain_addition_word_problem(first, second)

    return None

def infer_task_kind(text: str) -> str:
    base = strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()

    if re.search(r"\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+", lowered):
        return "fraction"
    if "x" in lowered and "=" in lowered:
        return "equation"
    if re.search(r"периметр|площадь|прямоугольник|квадрат|сторон|длина|ширина|сторона", lowered):
        return "geometry"
    if re.search(r"[а-я]", lowered):
        return "word"
    if re.search(r"[+\-*/()×÷:]", lowered):
        return "expression"
    return "other"

def sanitize_model_text(text: str) -> str:
    cleaned = str(text or "")
    while True:
        updated = LEADING_FILLER_SENTENCE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    cleaned = cleaned.replace("\r", "")
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("\\(", "").replace("\\)", "")
    cleaned = cleaned.replace("\\[", "").replace("\\]", "")
    cleaned = cleaned.replace("\\", "")
    cleaned = re.sub(r"^\s*[-*•]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*Шаг\s*\d+\s*:?\s*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"\b(Запомни|Памятка)\b\s*[—:-]?", "Совет:", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(Ответ\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(Совет\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(Проверка\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    raw_lines = [line.strip() for line in cleaned.split("\n")]
    lines = []
    seen = set()
    for raw in raw_lines:
        if not raw:
            continue
        if BANNED_OPENERS.match(raw):
            continue
        line = re.sub(r"\s+", " ", raw)
        line = re.sub(r"^Совет:\s*Совет:\s*", "Совет: ", line, flags=re.IGNORECASE)
        line = re.sub(r"^Ответ:\s*Ответ:\s*", "Ответ: ", line, flags=re.IGNORECASE)
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)

    return "\n".join(lines).strip()

GENERIC_BODY_LINE_RE = re.compile(
    r"^(?:"
    r"известны два количества|"
    r"сначала смотрим, сколько было|"
    r"сначала находим второе количество|"
    r"сначала узна(?:е|ё)м, сколько предметов в одинаковых группах|"
    r"нужно оставить x отдельно"
    r")[.!?]?$",
    re.IGNORECASE,
)

def line_has_math_signal(text: str) -> bool:
    return bool(re.search(r"\d|x|х|[+\-=:×÷/]", str(text or ""), flags=re.IGNORECASE))

def shorten_body_line(line: str) -> str:
    text = re.sub(r"\s+", " ", str(line or "").strip())
    if not text:
        return ""

    replacements = [
        (r"^Число\s+(.+?)\s+переносим\s+вправо[.!?]?$", lambda m: f"Переносим {m.group(1)} вправо"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+плюс\s+меняется\s+на\s+минус[.!?]?$", lambda m: "Плюс меняем на минус"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+минус\s+меняется\s+на\s+плюс[.!?]?$", lambda m: "Минус меняем на плюс"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+умножение\s+меняется\s+на\s+деление[.!?]?$", lambda m: "Умножение меняем на деление"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+деление\s+меняется\s+на\s+умножение[.!?]?$", lambda m: "Деление меняем на умножение"),
        (r"^Нужно\s+узнать,\s+сколько\s+получится\s+вместе:\s*(.+)$", lambda m: f"Вместе: {m.group(1).strip()}"),
        (r"^Потом\s+узнаем,\s+сколько\s+убрали:\s*(.+)$", lambda m: f"Убрали: {m.group(1).strip()}"),
        (r"^Потом\s+узнаём,\s+сколько\s+убрали:\s*(.+)$", lambda m: f"Убрали: {m.group(1).strip()}"),
        (r"^Нужно\s+узнать\s+разницу\s+между\s+двумя\s+числами[.!?]?$", lambda m: "Сравниваем два числа"),
        (r"^Чтобы\s+узнать,\s+сколько\s+всего,\s+используем\s+умножение[.!?]?$", lambda m: ""),
        (r"^Чтобы\s+узнать,\s+сколько\s+было\s+сначала,\s+нужно\s+сложить[.!?]?$", lambda m: ""),
        (r"^Чтобы\s+узнать,\s+сколько\s+было\s+сначала,\s+нужно\s+вычесть\s+добавленное[.!?]?$", lambda m: ""),
    ]

    for pattern, repl in replacements:
        text, count = re.subn(pattern, repl, text, flags=re.IGNORECASE)
        if count:
            break

    return text.strip(" ")

def normalize_body_lines(lines):
    raw = []
    seen = set()

    for line in lines:
        cleaned = shorten_body_line(line)
        if not cleaned:
            continue
        key = cleaned.lower().rstrip(".!?")
        if key in seen:
            continue
        seen.add(key)
        raw.append(cleaned)

    informative_exists = any(line_has_math_signal(line) for line in raw)
    result = []

    for line in raw:
        if informative_exists and GENERIC_BODY_LINE_RE.match(line.strip()):
            continue
        result.append(line)

    if not result:
        return raw

    return result

def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    cleaned = sanitize_model_text(text)
    if not cleaned:
        advice = forced_advice or default_advice(kind)
        if forced_answer:
            return join_explanation_lines(f"Ответ: {forced_answer}", f"Совет: {advice}")
        return join_explanation_lines("Напишите задачу понятнее", "Ответ: нужно уточнить запись", f"Совет: {advice}")

    body_lines = []
    answer_line = None
    advice_line = None

    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if lower.startswith("ответ:"):
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if value:
                answer_line = f"Ответ: {value}"
            continue
        if lower.startswith("совет:"):
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if value:
                advice_line = f"Совет: {value}"
            continue
        body_lines.append(line)

    check_line = None
    non_check_body = []
    for line in body_lines:
        if line.lower().startswith("проверка:"):
            if check_line is None:
                check_line = line
            continue
        non_check_body.append(line)

    non_check_body = normalize_body_lines(non_check_body)

    max_body_lines = 3 if check_line else 4
    if len(non_check_body) > max_body_lines:
        summary_line = None
        if not check_line:
            maybe_summary = re.search(r"=\s*([^=]+)$", non_check_body[-1])
            if maybe_summary:
                summary_line = f"Дальше считаем по порядку и получаем {maybe_summary.group(1).strip()}"
        compact_tail = summary_line or non_check_body[-1]
        compact_body = non_check_body[: max_body_lines - 1] + [compact_tail]
    else:
        compact_body = non_check_body[:max_body_lines]

    if check_line:
        compact_body.append(check_line)

    if forced_answer is not None:
        answer_line = f"Ответ: {forced_answer}"
    elif answer_line is None and non_check_body:
        maybe_result = re.search(r"=\s*([^=]+)$", non_check_body[-1])
        if maybe_result:
            answer_line = f"Ответ: {maybe_result.group(1).strip()}"

    if answer_line is None:
        answer_line = "Ответ: проверь запись задачи"

    advice_value = forced_advice or (advice_line.split(":", 1)[1].strip() if advice_line else default_advice(kind))
    advice_line = f"Совет: {advice_value}"

    final_lines = compact_body + [answer_line, advice_line]
    return join_explanation_lines(*final_lines)

def validate_expression_ast(node: ast.AST) -> bool:
    if isinstance(node, ast.Expression):
        return validate_expression_ast(node.body)
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)) and validate_expression_ast(node.left) and validate_expression_ast(node.right)
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, ast.USub) and validate_expression_ast(node.operand)
    return is_int_literal_node(node)

def parse_expression_ast(source: str) -> Optional[ast.AST]:
    try:
        parsed = ast.parse(source, mode="eval")
    except SyntaxError:
        return None
    if not validate_expression_ast(parsed):
        return None
    return parsed.body

def eval_fraction_node(node: ast.AST) -> Fraction:
    if is_int_literal_node(node):
        return Fraction(int_from_literal_node(node), 1)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -eval_fraction_node(node.operand)
    if isinstance(node, ast.BinOp):
        left = eval_fraction_node(node.left)
        right = eval_fraction_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("division by zero")
            return left / right
    raise ValueError("Unsupported expression")

def precedence_for_node(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return PRECEDENCE[type(node.op)]
    if isinstance(node, ast.UnaryOp):
        return 3
    return 4

def render_node(node: ast.AST, parent_precedence: int = 0, is_right_child: bool = False) -> str:
    if is_int_literal_node(node):
        return str(int_from_literal_node(node))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = render_node(node.operand, 3)
        return f"-{inner}"
    if isinstance(node, ast.BinOp):
        current_precedence = PRECEDENCE[type(node.op)]
        left_text = render_node(node.left, current_precedence, False)
        right_text = render_node(node.right, current_precedence, True)
        text = f"{left_text} {OPERATOR_SYMBOLS[type(node.op)]} {right_text}"
        needs_brackets = current_precedence < parent_precedence or (
            is_right_child and isinstance(node.op, (ast.Add, ast.Sub)) and parent_precedence == current_precedence
        )
        if needs_brackets:
            return f"({text})"
        return text
    raise ValueError("Unsupported node")

def build_eval_steps(node: ast.AST):
    if is_int_literal_node(node):
        return eval_fraction_node(node), []
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return eval_fraction_node(node), []
    if not isinstance(node, ast.BinOp):
        return eval_fraction_node(node), []

    left_value, left_steps = build_eval_steps(node.left)
    right_value, right_steps = build_eval_steps(node.right)
    result_value = eval_fraction_node(node)

    step = {
        "verb": OPERATOR_VERBS[type(node.op)],
        "left": format_fraction(left_value),
        "operator": OPERATOR_SYMBOLS[type(node.op)],
        "right": format_fraction(right_value),
        "result": format_fraction(result_value),
    }

    return result_value, left_steps + right_steps + [step]

def format_step_lines(steps, raw_source: str):
    lines = []
    has_brackets = "(" in raw_source or ")" in raw_source
    for index, step in enumerate(steps):
        if index == 0 and has_brackets and len(steps) > 1:
            prefix = "Сначала считаем в скобках"
            lines.append(f"{prefix}: {step['left']} {step['operator']} {step['right']} = {step['result']}")
            continue
        if index == 0:
            prefix = "Сначала"
        elif index == 1:
            prefix = "Потом"
        else:
            prefix = "Дальше"
        lines.append(f"{prefix} {step['verb']}: {step['left']} {step['operator']} {step['right']} = {step['result']}")
    return lines

def root_operator_name(node: ast.AST) -> Optional[str]:
    if not isinstance(node, ast.BinOp):
        return None
    if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        return type(node.op).__name__.lower()
    return None

def advice_for_expression(node: ast.AST, source: str) -> str:
    if "(" in source or ")" in source:
        return "в выражении со скобками сначала считай в скобках."

    kinds = []
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp):
            kinds.append(type(child.op))

    unique_kinds = {kind for kind in kinds}
    if len(unique_kinds) > 1:
        return "сначала выполняй умножение и деление, потом сложение и вычитание."
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return "большие числа удобно складывать по частям."
        if isinstance(node.op, ast.Sub):
            return "в вычитании удобно идти по частям."
        if isinstance(node.op, ast.Mult):
            return "умножение удобно разложить на десятки и единицы."
        if isinstance(node.op, ast.Div):
            return "после деления полезно сделать проверку умножением."
    return default_advice("expression")

def try_simple_binary_int_expression(node: ast.AST) -> Optional[dict]:
    if not isinstance(node, ast.BinOp):
        return None
    if not is_int_literal_node(node.left) or not is_int_literal_node(node.right):
        return None

    left = int_from_literal_node(node.left)
    right = int_from_literal_node(node.right)

    if left < 0 or right < 0:
        return None

    return {
        "operator": type(node.op),
        "left": left,
        "right": right,
    }

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left >= 100 or right >= 100 or (left >= 10 and right >= 10):
        steps = build_column_addition_steps([left, right])
        return join_explanation_lines(*steps, f"Совет: записывай числа столбиком, чтобы не ошибиться.")
    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Решение.",
            "Складываем десятки и единицы",
            f"{left_tens} + {right_tens} = {left_tens + right_tens}",
            f"{left_units} + {right_units} = {left_units + right_units}",
            f"{left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: большие числа удобно складывать по частям",
        )
    return join_explanation_lines(
        "Решение.",
        f"Если к {left} прибавить {right}, то получится {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: считай спокойно и не пропускай числа",
    )

def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if left >= 100 or right >= 100:
        steps = build_column_subtraction_steps(left, right)
        return join_explanation_lines(*steps, f"Совет: при вычитании в столбик не забывай про занимание десятка.")
    if result < 0:
        return join_explanation_lines(
            "Решение.",
            "Первое число меньше второго",
            f"Поэтому ответ будет отрицательным: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: сначала сравни числа, а потом выполняй вычитание",
        )
    if right >= 10:
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            "Решение.",
            "Вычитаем по частям",
            f"{left} - {tens} = {middle}",
            f"{middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: в вычитании удобно сначала убрать десятки, потом единицы",
        )
    return join_explanation_lines(
        "Решение.",
        f"Если из {left} вычесть {right}, то получится {left} - {right} = {result}",
        f"Ответ: {result}",
        "Совет: считай по порядку и проверяй знак действия",
    )

def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    if left >= 100 or right >= 100 or (left >= 10 and right >= 10):
        steps = build_column_multiplication_steps(left, right)
        return join_explanation_lines(*steps, f"Совет: умножение в столбик помогает не пропустить разряды.")
    big = max(left, right)
    small = min(left, right)
    if big >= 10 and small <= 10:
        tens = big - big % 10
        units = big % 10
        return join_explanation_lines(
            "Решение.",
            f"Умножаем {big} на {small}",
            f"{tens} × {small} = {tens * small}",
            f"{units} × {small} = {units * small}",
            f"{tens * small} + {units * small} = {result}",
            f"Ответ: {result}",
            "Совет: умножение удобно разложить на десятки и единицы",
        )
    return join_explanation_lines(
        "Решение.",
        f"Если умножить {left} на {right}, то получится {left} × {right} = {result}",
        f"Ответ: {result}",
        "Совет: если трудно, представь умножение как одинаковые группы",
    )

def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь делитель перед вычислением",
        )

    quotient, remainder = divmod(left, right)
    if remainder == 0:
        return join_explanation_lines(
            "Решение.",
            f"Делим {left} на {right}",
            f"{left} : {right} = {quotient}",
            f"Проверка: {quotient} × {right} = {left}",
            f"Ответ: {quotient}",
            "Совет: после деления полезно сделать проверку умножением",
        )

    return join_explanation_lines(
        "Решение.",
        f"Делим {left} на {right}",
        f"Получаем {quotient} и остаток {remainder}",
        f"Проверка: {quotient} × {right} = {quotient * right}, ещё остаётся {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )

def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None

    node = parse_expression_ast(source)
    if node is None:
        return None

    simple = try_simple_binary_int_expression(node)
    if simple:
        operator = simple["operator"]
        left = simple["left"]
        right = simple["right"]
        if operator is ast.Add:
            return explain_simple_addition(left, right)
        if operator is ast.Sub:
            return explain_simple_subtraction(left, right)
        if operator is ast.Mult:
            return explain_simple_multiplication(left, right)
        if operator is ast.Div:
            return explain_simple_division(left, right)

    try:
        value, steps = build_eval_steps(node)
    except ZeroDivisionError:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь делитель перед вычислением",
        )
    except Exception:
        return None

    if not steps:
        return None

    body_lines = format_step_lines(steps, source)
    answer = format_fraction(value)
    advice = advice_for_expression(node, source)
    return join_explanation_lines("Решение.", *body_lines, f"Ответ: {answer}", f"Совет: {advice}")

def try_local_fraction_explanation(raw_text: str) -> Optional[str]:
    source = to_fraction_source(raw_text)
    if not source:
        return None

    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*([+\-])\s*(\d+)\s*/\s*(\d+)\s*", source)
    if not match:
        return None

    a, b, operator, c, d = match.groups()
    a = int(a)
    b = int(b)
    c = int(c)
    d = int(d)

    if b == 0 or d == 0:
        return join_explanation_lines(
            "Решение.",
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная",
            "Совет: проверь знаменатель каждой дроби",
        )

    if operator == "+":
        result = Fraction(a, b) + Fraction(c, d)
        operator_word = "складываем"
        action_symbol = "+"
    else:
        result = Fraction(a, b) - Fraction(c, d)
        operator_word = "вычитаем"
        action_symbol = "-"

    if b == d:
        top_result = a + c if operator == "+" else a - c
        lines = [
            "Решение.",
            "Знаменатели одинаковые",
            f"Считаем: {a}/{b} {action_symbol} {c}/{d} = {top_result}/{b}",
        ]
        if format_fraction(result) != f"{top_result}/{b}":
            lines.append(f"Сокращаем: {top_result}/{b} = {format_fraction(result)}")
        lines.extend([
            f"Ответ: {format_fraction(result)}",
            "Совет: если знаменатели одинаковые, меняется только числитель",
        ])
        return join_explanation_lines(*lines)

    common = math.lcm(b, d)
    a_scaled = a * (common // b)
    c_scaled = c * (common // d)
    top_result = a_scaled + c_scaled if operator == "+" else a_scaled - c_scaled
    lines = [
        "Решение.",
        f"Приводим дроби к общему знаменателю {common}",
        f"{a}/{b} = {a_scaled}/{common}, {c}/{d} = {c_scaled}/{common}",
        f"Считаем: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top_result}/{common}",
    ]
    simplified = Fraction(top_result, common)
    if format_fraction(simplified) != f"{top_result}/{common}":
        lines.append(f"Сокращаем: {top_result}/{common} = {format_fraction(simplified)}")

    lines.extend([
        f"Ответ: {format_fraction(result)}",
        "Совет: если знаменатели разные, сначала приведи дроби к общему знаменателю",
    ])
    return join_explanation_lines(*lines)

def swap_equation_sides_if_needed(lhs: str, rhs: str):
    if "x" not in lhs and "x" in rhs:
        return rhs, lhs
    return lhs, rhs

def format_equation_check(template: str, value_text: str, expected_text: str) -> str:
    expression = template.replace("x", value_text)
    return f"Проверка: {expression} = {expected_text}"

def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None

    lhs, rhs = source.split("=", 1)
    lhs, rhs = swap_equation_sides_if_needed(lhs, rhs)

    try:
        rhs_value = Fraction(int(rhs), 1)
    except ValueError:
        return None

    patterns = [
        (r"^x\+(\d+)$", "x_plus"),
        (r"^x-(\d+)$", "x_minus"),
        (r"^x\*(\d+)$", "x_mul"),
        (r"^x/(\d+)$", "x_div"),
        (r"^(\d+)\+x$", "plus_x"),
        (r"^(\d+)-x$", "minus_x"),
        (r"^(\d+)\*x$", "mul_x"),
        (r"^(\d+)/x$", "div_x"),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue
        number = Fraction(int(match.group(1)), 1)

        if kind == "x_plus":
            answer = rhs_value - number
            return join_explanation_lines(
                "Решение.",
                "Плюс меняем на минус",
                f"x = {format_fraction(rhs_value)} - {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x + {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число переносим через знак равно обратным действием",
            )

        if kind == "x_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Решение.",
                "Минус меняем на плюс",
                f"x = {format_fraction(rhs_value)} + {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x - {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число переносим через знак равно обратным действием",
            )

        if kind == "x_mul":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Решение.",
                        "Здесь x умножают на 0",
                        "0 всегда даёт 0",
                        "Ответ: подходит любое число",
                        "Совет: при умножении на ноль результат всегда ноль",
                    )
                return join_explanation_lines(
                    "Решение.",
                    "Число, умноженное на 0, не может дать другой результат",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = rhs_value / number
            return join_explanation_lines(
                "Решение.",
                "Умножение меняем на деление",
                f"x = {format_fraction(rhs_value)} : {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x × {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: множитель переносим через знак равно делением",
            )

        if kind == "x_div":
            if number == 0:
                return join_explanation_lines(
                    "Решение.",
                    "На ноль делить нельзя",
                    "Такое уравнение не имеет решения",
                    "Ответ: решения нет",
                    "Совет: проверь делитель перед вычислением",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Решение.",
                "Деление меняем на умножение",
                f"x = {format_fraction(rhs_value)} × {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x : {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x делят на число, справа нужно умножить",
            )

        if kind == "plus_x":
            answer = rhs_value - number
            return join_explanation_lines(
                "Решение.",
                "Плюс меняем на минус",
                f"x = {format_fraction(rhs_value)} - {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} + x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число переносим через знак равно обратным действием",
            )

        if kind == "minus_x":
            answer = number - rhs_value
            return join_explanation_lines(
                "Решение.",
                "x стоит после минуса",
                f"x = {format_fraction(number)} - {format_fraction(rhs_value)} = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} - x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x стоит после минуса, вычти ответ из первого числа",
            )

        if kind == "mul_x":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Решение.",
                        "Здесь 0 умножают на x",
                        "0 всегда даёт 0",
                        "Ответ: подходит любое число",
                        "Совет: при умножении на ноль результат всегда ноль",
                    )
                return join_explanation_lines(
                    "Решение.",
                    "0 не может дать другой результат при умножении",
                    "Ответ: решения нет",
                    "Совет: проверь запись уравнения",
                )
            answer = rhs_value / number
            return join_explanation_lines(
                "Решение.",
                "Умножение меняем на деление",
                f"x = {format_fraction(rhs_value)} : {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} × x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: множитель переносим через знак равно делением",
            )

        if kind == "div_x":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Решение.",
                        "В делимом стоит 0",
                        "0, делённое на любое ненулевое число, остаётся 0",
                        "Значит подходит любое число, кроме 0",
                        "Ответ: любое число, кроме 0",
                        "Совет: в делителе ноль быть не может",
                    )
                return join_explanation_lines(
                    "Решение.",
                    "В делимом стоит 0",
                    f"0, делённое на ненулевое число, не может дать {format_fraction(rhs_value)}",
                    "Ответ: решения нет",
                    "Совет: проверь делимое и результат",
                )
            if rhs_value == 0:
                return join_explanation_lines(
                    "Решение.",
                    "Деление не может дать ноль, если делимое не равно нулю",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "Решение.",
                "x стоит в делителе",
                f"x = {format_fraction(number)} : {format_fraction(rhs_value)} = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} : x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x стоит в делителе, раздели делимое на результат",
            )

    return None

async def call_deepseek(payload: dict, timeout_seconds: float = 45.0):
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        return {
            "error": f"DeepSeek API error {response.status_code}",
            "details": response.text[:1500],
        }

    try:
        result = response.json()
    except Exception:
        return {
            "error": "DeepSeek вернул не JSON",
            "details": response.text[:1500],
        }

    if "choices" not in result or not result["choices"]:
        return {
            "error": "DeepSeek вернул неожиданный формат ответа",
            "details": str(result)[:1500],
        }

    message = result["choices"][0].get("message", {})
    answer = (message.get("content") or "").strip()

    if not answer:
        return {
            "error": "DeepSeek вернул пустой ответ",
            "details": str(result)[:1500],
        }

    return {"result": answer}

@app.options("/")
async def options():
    return {"message": "OK"}

@app.get("/")
def read_root():
    return {"message": "Proxy is running. Use POST request with 'action' and payload."}

@app.post("/")
async def proxy(request: Request):
    try:
        data = await request.json()
        action = data.get("action")

        if action != "explain":
            return JSONResponse(status_code=400, content={"error": "Invalid action"})

        user_text = (data.get("text") or "").strip()
        if not user_text:
            return JSONResponse(status_code=400, content={"error": "Пустой текст задачи"})

        if len(user_text) > 2000:
            return JSONResponse(status_code=400, content={"error": "Текст задачи слишком длинный"})

        if not re.search(r"\d|x|х|[+\-*/=×÷:]", user_text):
            return {"result": NON_MATH_REPLY, "source": "guard", "validated": True}

        return await build_explanation(user_text)

    except httpx.ReadTimeout:
        return JSONResponse(status_code=504, content={"error": "DeepSeek timeout: сервер не дождался ответа от API"})
    except httpx.ConnectTimeout:
        return JSONResponse(status_code=504, content={"error": "DeepSeek connect timeout: сервер не смог подключиться к API"})
    except httpx.ConnectError as e:
        return JSONResponse(status_code=502, content={"error": f"DeepSeek connect error: {str(e)}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Server exception: {str(e)}"})

COMPACT_DEFAULT_ADVICE = {
    "expression": "считай по порядку.",
    "equation": "оставляй x отдельно.",
    "fraction": "сначала смотри на знаменатели.",
    "geometry": "сначала выбери правило.",
    "word": "сначала пойми, что нужно найти.",
    "other": "решай по шагам.",
}

LOW_VALUE_BODY_PATTERNS = [
    re.compile(r"^это (?:составная )?задача(?:[^.!?]*)$", re.IGNORECASE),
    re.compile(r"^известны два количества$", re.IGNORECASE),
    re.compile(r"^сначала смотрим, сколько было$", re.IGNORECASE),
    re.compile(r"^сравниваем, на сколько стало (?:больше|меньше)$", re.IGNORECASE),
    re.compile(r"^у квадрата все стороны равны$", re.IGNORECASE),
    re.compile(r"^у прямоугольника длина и ширина повторяются по два раза$", re.IGNORECASE),
    re.compile(r"^площадь квадрата равна стороне, умноженной на сторону$", re.IGNORECASE),
    re.compile(r"^площадь прямоугольника равна длине, умноженной на ширину$", re.IGNORECASE),
]

BODY_LINE_LIMITS = {
    "expression": 4,
    "fraction": 4,
    "equation": 4,
    "geometry": 3,
    "word": 3,
    "other": 3,
}

def default_advice(kind: str) -> str:
    return COMPACT_DEFAULT_ADVICE.get(kind, COMPACT_DEFAULT_ADVICE["other"])

def shorten_body_line(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""

    replacements = [
        (r"^Это (?:составная )?задача, поэтому решаем по действиям$", "Решаем по действиям"),
        (r"^Это задача на два действия$", "Решаем по действиям"),
        (r"^Нужно узнать, сколько ", "Ищем, сколько "),
        (r"^Нужно узнать разницу между двумя числами$", "Ищем разницу между числами"),
        (r"^Сначала смотрим, сколько было$", ""),
        (r"^Потом узнаем, сколько убрали:?\s*(.+)$", r"Убрали: \1"),
        (r"^Потом узнаем, сколько добавили:?\s*(.+)$", r"Добавили: \1"),
        (r"^Потом узнаем, сколько прибавили:?\s*(.+)$", r"Прибавили: \1"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+умножение\s+меняется\s+на\s+деление[.!?]?$", "Умножение меняем на деление"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+деление\s+меняется\s+на\s+умножение[.!?]?$", "Деление меняем на умножение"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+плюс\s+меняется\s+на\s+минус[.!?]?$", "Плюс меняем на минус"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+минус\s+меняется\s+на\s+плюс[.!?]?$", "Минус меняем на плюс"),
        (r"^Нужно оставить x отдельно$", "Ищем x"),
        (r"^Число\s+([\d/]+)\s+переносим\s+вправо$", r"Переносим \1 вправо"),
        (r"^Если периметр равен\s+(\d+),\s+одну сторону находим делением на 4$", r"Делим периметр на 4"),
        (r"^Чтобы найти ширину, делим площадь на длину:\s*(.+)$", r"Делим площадь на длину: \1"),
        (r"^Чтобы найти длину, делим площадь на ширину:\s*(.+)$", r"Делим площадь на ширину: \1"),
        (r"^Чтобы узнать, сколько было сначала, нужно\s+", "Чтобы узнать, сколько было сначала, "),
        (r"^Чтобы узнать, сколько получилось вместе, используем\s+", "Чтобы узнать итог, используем "),
        (r"^Чтобы узнать, сколько всего, используем\s+", "Чтобы узнать итог, используем "),
        (r"^Потом меняем число ещё раз:\s*(.+)$", r"Потом: \1"),
        (r"^Теперь считаем вместе:\s*(.+)$", r"Потом: \1"),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    text = re.sub(r"\bобычно\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bчасто\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bудобно\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.;")
    return capitalize_if_needed(text)

def shorten_advice_line(line: str, kind: str) -> str:
    text = str(line or "").strip()
    if not text:
        return default_advice(kind)

    replacements = [
        (r"^большие числа удобно складывать по частям$", "большие числа складывай по частям"),
        (r"^в вычитании удобно сначала убрать десятки, потом единицы$", "сначала убирай десятки, потом единицы"),
        (r"^в вычитании удобно идти по частям$", "вычитай по частям"),
        (r"^если трудно, представь умножение как одинаковые группы$", "умножение можно представить как одинаковые группы"),
        (r"^после деления полезно сделать проверку умножением$", "проверяй деление умножением"),
        (r"^остаток всегда должен быть меньше делителя$", "остаток меньше делителя"),
        (r"^множитель переносим через знак равно делением$", "множитель переносим делением"),
        (r"^при переносе множителя вправо выполняем деление$", "множитель переносим делением"),
        (r"^если x делят на число, справа нужно умножить$", "деление меняем на умножение"),
        (r"^если x стоит в делителе, раздели делимое на результат$", "если x в делителе, дели делимое на результат"),
        (r"^если x стоит после минуса, вычти ответ из первого числа$", "если x после минуса, вычитай из первого числа"),
        (r"^если знаменатели одинаковые, меняется только числитель$", "при одинаковых знаменателях меняется только числитель"),
        (r"^если знаменатели разные, сначала приведи дроби к общему знаменателю$", "сначала приведи дроби к общему знаменателю"),
        (r"^если нужно узнать, сколько всего, складывай$", "если спрашивают про всё вместе, складывай"),
        (r"^если что-то убрали, используй вычитание$", "если что-то убрали, используй вычитание"),
        (r"^если что-то убрали, отдали или съели, нужно вычитание$", "если что-то убрали, используй вычитание"),
        (r"^если одно количество больше или меньше другого, сначала найди его значение$", "сначала найди второе число"),
        (r"^если одно количество зависит от другого, сначала найди его, потом считай всё вместе$", "сначала найди второе число"),
        (r"^в задачах в два действия считай изменения по порядку$", "считай по порядку"),
        (r"^если числа зависят друг от друга по цепочке, решай по шагам$", "решай по шагам"),
        (r"^у квадрата 4 равные стороны$", "у квадрата 4 равные стороны"),
        (r"^если известны площадь и длина, ширину находим делением$", "ширина = площадь : длина"),
        (r"^если известны площадь и ширина, длину находим делением$", "длина = площадь : ширина"),
        (r"^по периметру прямоугольника сначала находи половину периметра$", "сначала найди половину периметра"),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    text = re.sub(r"\bобычно\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bчасто\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bудобно\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.;")
    return text or default_advice(kind)

def line_relevance_score(line: str, index: int) -> int:
    text = str(line or "")
    lower = text.lower()
    score = 0
    if "=" in text:
        score += 5
    if re.search(r"\d|x|х", lower):
        score += 2
    if re.search(r"\b(складываем|вычитаем|умножаем|делим|получаем|переносим|проверка|приводим|ищем|решаем|сначала|потом)\b", lower):
        score += 3
    if lower.startswith("ищем"):
        score += 2
    if index == 0:
        score += 1
    if is_low_value_body_line(text):
        score -= 4
    return score

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Решение.",
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}",
            f"Складываем результаты: {left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: большие числа складывай по частям",
        )

    return join_explanation_lines(
        "Решение.",
        f"Складываем: {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: считай по порядку",
    )

def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
            "Решение.",
            f"Вычитаем: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: сначала сравни числа",
        )

    if right >= 10:
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            "Решение.",
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}",
            f"Потом вычитаем единицы: {middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: вычитай по частям",
        )

    return join_explanation_lines(
        "Решение.",
        f"Вычитаем: {left} - {right} = {result}",
        f"Ответ: {result}",
        "Совет: считай по порядку",
    )

def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь делитель",
        )

    quotient, remainder = divmod(left, right)
    if remainder == 0:
        return join_explanation_lines(
            "Решение.",
            f"Делим: {left} : {right} = {quotient}",
            f"Проверка: {quotient} × {right} = {left}",
            f"Ответ: {quotient}",
            "Совет: проверяй деление умножением",
        )

    return join_explanation_lines(
        "Решение.",
        f"Делим: {left} : {right} = {quotient}, остаток {remainder}",
        f"Проверка: {quotient} × {right} = {quotient * right}, ещё остаётся {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток меньше делителя",
    )

def try_local_fraction_explanation(raw_text: str) -> Optional[str]:
    source = to_fraction_source(raw_text)
    if not source:
        return None

    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*([+\-])\s*(\d+)\s*/\s*(\d+)\s*", source)
    if not match:
        return None

    a, b, operator, c, d = match.groups()
    a = int(a)
    b = int(b)
    c = int(c)
    d = int(d)

    if b == 0 or d == 0:
        return join_explanation_lines(
            "Решение.",
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная",
            "Совет: проверь знаменатель",
        )

    action_symbol = "+" if operator == "+" else "-"
    action_word = "Складываем" if operator == "+" else "Вычитаем"
    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)

    if b == d:
        top_result = a + c if operator == "+" else a - c
        lines = [
            "Решение.",
            "Знаменатели одинаковые",
            f"{action_word} числители: {a} {action_symbol} {c} = {top_result}",
        ]
        raw_fraction = f"{top_result}/{b}"
        if format_fraction(result) != raw_fraction:
            lines.append(f"Получаем: {raw_fraction} = {format_fraction(result)}")
        else:
            lines.append(f"Получаем: {raw_fraction}")
        lines.extend([
            f"Ответ: {format_fraction(result)}",
            "Совет: при одинаковых знаменателях меняется только числитель",
        ])
        return join_explanation_lines(*lines)

    common = math.lcm(b, d)
    a_scaled = a * (common // b)
    c_scaled = c * (common // d)
    top_result = a_scaled + c_scaled if operator == "+" else a_scaled - c_scaled
    simplified = Fraction(top_result, common)
    lines = [
        "Решение.",
        f"Приводим к знаменателю {common}",
        f"{a}/{b} = {a_scaled}/{common}, {c}/{d} = {c_scaled}/{common}",
        f"{action_word}: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top_result}/{common}",
    ]
    if format_fraction(simplified) != f"{top_result}/{common}":
        lines.append(f"Сокращаем: {top_result}/{common} = {format_fraction(simplified)}")
    lines.extend([
        f"Ответ: {format_fraction(result)}",
        "Совет: сначала приведи дроби к общему знаменателю",
    ])
    return join_explanation_lines(*lines)

def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None

    lhs, rhs = source.split("=", 1)
    lhs, rhs = swap_equation_sides_if_needed(lhs, rhs)

    try:
        rhs_value = Fraction(int(rhs), 1)
    except ValueError:
        return None

    patterns = [
        (r"^x\+(\d+)$", "x_plus"),
        (r"^x-(\d+)$", "x_minus"),
        (r"^x\*(\d+)$", "x_mul"),
        (r"^x/(\d+)$", "x_div"),
        (r"^(\d+)\+x$", "plus_x"),
        (r"^(\d+)-x$", "minus_x"),
        (r"^(\d+)\*x$", "mul_x"),
        (r"^(\d+)/x$", "div_x"),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue
        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind in {"x_plus", "plus_x"}:
            answer = rhs_value - number
            check = format_equation_check("x + " + number_text if kind == "x_plus" else number_text + " + x", format_fraction(answer), rhs_text)
            return join_explanation_lines(
                "Решение.",
                "Ищем x",
                f"Вычитаем {number_text}: x = {rhs_text} - {number_text} = {format_fraction(answer)}",
                check,
                f"Ответ: {format_fraction(answer)}",
                "Совет: число после плюса переносим вычитанием",
            )

        if kind == "x_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Решение.",
                "Ищем x",
                f"Прибавляем {number_text}: x = {rhs_text} + {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x - {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число после минуса переносим сложением",
            )

        if kind == "minus_x":
            answer = number - rhs_value
            return join_explanation_lines(
                "Решение.",
                "Ищем x",
                f"Вычитаем {rhs_text} из {number_text}: x = {number_text} - {rhs_text} = {format_fraction(answer)}",
                format_equation_check(f"{number_text} - x", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x после минуса, вычитай из первого числа",
            )

        if kind in {"x_mul", "mul_x"}:
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Решение.",
                        "0 при умножении всегда даёт 0",
                        "Ответ: подходит любое число",
                        "Совет: умножение на ноль всегда даёт ноль",
                    )
                return join_explanation_lines(
                    "Решение.",
                    "0 при умножении не может дать другой результат",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение",
                )
            answer = rhs_value / number
            check = format_equation_check("x × " + number_text if kind == "x_mul" else number_text + " × x", format_fraction(answer), rhs_text)
            return join_explanation_lines(
                "Решение.",
                "Ищем x",
                f"Делим {rhs_text} на {number_text}: x = {rhs_text} : {number_text} = {format_fraction(answer)}",
                check,
                f"Ответ: {format_fraction(answer)}",
                "Совет: множитель переносим делением",
            )

        if kind == "x_div":
            if number == 0:
                return join_explanation_lines(
                    "Решение.",
                    "На ноль делить нельзя",
                    "Ответ: решения нет",
                    "Совет: проверь делитель",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Решение.",
                "Ищем x",
                f"Умножаем {rhs_text} на {number_text}: x = {rhs_text} × {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x : {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: деление меняем на умножение",
            )

        if kind == "div_x":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Решение.",
                        "0, делённое на ненулевое число, всегда равно 0",
                        "Ответ: любое число, кроме 0",
                        "Совет: в делителе ноль быть не может",
                    )
                return join_explanation_lines(
                    "Решение.",
                    "0, делённое на ненулевое число, не может дать другой результат",
                    "Ответ: решения нет",
                    "Совет: проверь делимое и результат",
                )
            if rhs_value == 0:
                return join_explanation_lines(
                    "Решение.",
                    "Ненулевое число при делении не может дать 0",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "Решение.",
                "Ищем x",
                f"Делим {number_text} на {rhs_text}: x = {number_text} : {rhs_text} = {format_fraction(answer)}",
                format_equation_check(f"{number_text} : x", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x в делителе, дели делимое на результат",
            )

    return None

def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько всего или сколько стало",
        f"Считаем: {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают про всё вместе, складывай",
    )

def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько осталось",
        f"Считаем: {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если что-то убрали, используй вычитание",
    )

def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Решение.",
        "Ищем разницу между числами",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос 'на сколько' решаем вычитанием",
    )

def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько было сначала",
        f"Считаем: {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: если часть убрали, начальное число находим сложением",
    )

def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько было сначала",
        f"Считаем: {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: если что-то добавили, начальное число находим вычитанием",
    )

def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько добавили",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: сравни число было и число стало",
    )

def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько убрали",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вычти, сколько осталось, из того, что было",
    )

def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько всего",
        f"Считаем: {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова 'по ... в каждой' подсказывают умножение",
    )

def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь, на сколько частей делят",
        )

    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Решение.",
            "Ищем, сколько получит каждый",
            f"Считаем: {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова 'поровну' и 'каждый' подсказывают деление",
        )

    return join_explanation_lines(
        "Решение.",
        "Ищем, сколько получит каждый",
        f"Считаем: {total} : {groups} = {quotient}, остаток {remainder}",
        f"Ответ: каждому по {quotient}, остаток {remainder}",
        "Совет: остаток меньше делителя",
    )

def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "Решение.",
            "В группе не может быть 0 предметов",
            "Ответ: запись задачи неверная",
            "Совет: проверь размер группы",
        )

    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Решение.",
            "Ищем, сколько групп получится",
            f"Считаем: {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находим делением",
        )

    if needs_extra_group:
        return join_explanation_lines(
            "Решение.",
            f"Считаем: {total} : {per_group} = {quotient}, остаток {remainder}",
            "Осталось ещё несколько предметов, нужна ещё одна группа",
            f"Ответ: {quotient + 1}",
            "Совет: если что-то осталось, иногда нужна ещё одна коробка",
        )

    if explicit_remainder:
        full_group_phrase = plural_form(quotient, "полная группа", "полные группы", "полных групп")
        return join_explanation_lines(
            "Решение.",
            "Ищем, сколько полных групп получится",
            f"Считаем: {total} : {per_group} = {quotient}, остаток {remainder}",
            f"Ответ: {quotient} {full_group_phrase}, остаток {remainder}",
            "Совет: остаток меньше размера группы",
        )

    return None

def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        "Решение.",
        "Ищем второе количество",
        f"Считаем: {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: сначала найди второе число",
    )

def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        "Решение.",
        f"Сначала находим второе количество: {base} {sign} {delta} = {related}",
        f"Потом считаем вместе: {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: сначала найди второе число",
    )

def explain_sequential_change_word_problem(start: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = apply_more_less(start, first_delta, "больше" if first_mode == "gain" else "меньше")
    if middle is None:
        return None
    result = apply_more_less(middle, second_delta, "больше" if second_mode == "gain" else "меньше")
    if result is None:
        return None

    first_sign = "+" if first_mode == "gain" else "-"
    second_sign = "+" if second_mode == "gain" else "-"
    first_action = "прибавляем" if first_mode == "gain" else "вычитаем"
    second_action = "прибавляем" if second_mode == "gain" else "вычитаем"
    return join_explanation_lines(
        "Решение.",
        f"Сначала {first_action} {first_delta}: {start} {first_sign} {first_delta} = {middle}",
        f"Потом {second_action} {second_delta}: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
        "Совет: считай по порядку",
    )

def explain_relation_chain_word_problem(base: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = apply_more_less(base, first_delta, first_mode)
    if middle is None:
        return None
    result = apply_more_less(middle, second_delta, second_mode)
    if result is None:
        return None

    first_sign = "+" if first_mode == "больше" else "-"
    second_sign = "+" if second_mode == "больше" else "-"
    return join_explanation_lines(
        "Решение.",
        f"Сначала находим второе число: {base} {first_sign} {first_delta} = {middle}",
        f"Потом третье: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
        "Совет: решай по шагам",
    )

def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        "Решение.",
        f"Сначала считаем группы: {groups} × {per_group} = {grouped_total}",
        f"Потом прибавляем ещё {extra}: {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
        "Совет: сначала посчитай одинаковые группы",
    )

def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    unit = geometry_unit(lower)
    question_parts = [part.strip() for part in re.split(r"[?.!]", lower) if part.strip()]
    question = question_parts[-1] if question_parts else lower
    asks_perimeter = "периметр" in lower
    asks_area = "площад" in lower
    asks_side = any(fragment in question for fragment in ("найди сторону", "найди длину стороны", "одной стороны", "какова сторона"))
    asks_width = any(fragment in question for fragment in ("найди ширину", "какова ширина"))
    asks_length = any(fragment in question for fragment in ("найди длину", "какова длина")) and not asks_width

    if "квадрат" in lower and asks_perimeter and asks_side and nums:
        perimeter = nums[0]
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        return join_explanation_lines(
            "Решение.",
            "Ищем сторону квадрата",
            f"Делим периметр на 4: {perimeter} : 4 = {side}",
            f"Ответ: {with_unit(side, unit)}",
            "Совет: у квадрата 4 равные стороны",
        )

    if "прямоугольник" in lower and asks_perimeter and asks_width and len(nums) >= 2:
        perimeter, length = nums[0], nums[1]
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        width = half - length
        if width < 0:
            return None
        return join_explanation_lines(
            "Решение.",
            "Ищем ширину прямоугольника",
            f"Сначала делим периметр пополам: {perimeter} : 2 = {half}",
            f"Потом вычитаем длину: {half} - {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: половина периметра — это длина плюс ширина",
        )

    if "прямоугольник" in lower and asks_perimeter and asks_length and len(nums) >= 2:
        perimeter, width = nums[0], nums[1]
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        length = half - width
        if length < 0:
            return None
        return join_explanation_lines(
            "Решение.",
            "Ищем длину прямоугольника",
            f"Сначала делим периметр пополам: {perimeter} : 2 = {half}",
            f"Потом вычитаем ширину: {half} - {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: половина периметра — это длина плюс ширина",
        )

    if "квадрат" in lower and asks_area and asks_side and nums:
        area = nums[0]
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return join_explanation_lines(
            "Решение.",
            "Ищем сторону квадрата",
            f"Нужно число, которое в квадрате даёт {area}",
            f"Это {side}, потому что {side} × {side} = {area}",
            f"Ответ: {with_unit(side, unit)}",
            "Совет: сторона квадрата в квадрате даёт площадь",
        )

    if "прямоугольник" in lower and asks_area and asks_width and len(nums) >= 2:
        area, length = nums[0], nums[1]
        if length == 0 or area % length != 0:
            return None
        width = area // length
        return join_explanation_lines(
            "Решение.",
            "Ищем ширину прямоугольника",
            f"Делим площадь на длину: {area} : {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: ширина = площадь : длина",
        )

    if "прямоугольник" in lower and asks_area and asks_length and len(nums) >= 2:
        area, width = nums[0], nums[1]
        if width == 0 or area % width != 0:
            return None
        length = area // width
        return join_explanation_lines(
            "Решение.",
            "Ищем длину прямоугольника",
            f"Делим площадь на ширину: {area} : {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: длина = площадь : ширина",
        )

    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines(
            "Решение.",
            "Ищем периметр квадрата",
            f"Считаем: {side} × 4 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у квадрата 4 равные стороны",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
            "Решение.",
            "Ищем периметр прямоугольника",
            f"Сначала: {length} + {width} = {length + width}",
            f"Потом: {length + width} × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: сначала сложи длину и ширину",
        )

    if "квадрат" in lower and asks_area and nums:
        side = nums[0]
        result = side * side
        return join_explanation_lines(
            "Решение.",
            "Ищем площадь квадрата",
            f"Считаем: {side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь квадрата — это сторона на сторону",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Решение.",
            "Ищем площадь прямоугольника",
            f"Считаем: {length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь = длина × ширина",
        )

    return None

def capitalize_if_needed(text: str) -> str:
    line = str(text or "").strip()
    if not line:
        return ""
    first = line[0]
    if first.isalpha() and first.islower():
        return first.upper() + line[1:]
    return line

TEACHING_DEFAULT_ADVICE_V9 = {
    "expression": "двигайся по шагам и называй каждое действие",
    "equation": "сначала оставь x один, потом сделай проверку",
    "fraction": "сначала смотри на знаменатели, потом считай",
    "geometry": "сначала назови правило, потом подставь числа",
    "word": "сначала пойми, что известно и что нужно найти",
    "other": "решай по шагам",
}

BODY_LINE_LIMITS_V9 = {
    "expression": 6,
    "fraction": 5,
    "equation": 5,
    "geometry": 5,
    "word": 5,
    "other": 4,
}

LOW_VALUE_BODY_PATTERNS_V9 = [
    re.compile(r"^это (?:составная )?задача(?:[^.!?]*)$", re.IGNORECASE),
    re.compile(r"^решаем по действиям$", re.IGNORECASE),
    re.compile(r"^известны два количества$", re.IGNORECASE),
    re.compile(r"^сначала смотрим, сколько было$", re.IGNORECASE),
    re.compile(r"^нужно оставить x отдельно$", re.IGNORECASE),
]

DIRECT_RESULT_INTRO_RE_V9 = re.compile(
    r"^(?:делим|складываем|вычитаем|умножаем|считаем)\s*:?\s*[^=]+=\s*([^=]+)$",
    re.IGNORECASE,
)

SECTION_PREFIX_RE_V9 = re.compile(r"^(ответ|совет|проверка)\s*:\s*", re.IGNORECASE)

def default_advice(kind: str) -> str:
    return TEACHING_DEFAULT_ADVICE_V9.get(kind, TEACHING_DEFAULT_ADVICE_V9["other"])

def _normalize_body_line_v9(line: str) -> str:
    text = re.sub(r"\s+", " ", str(line or "").strip())
    if not text:
        return ""

    replacements = [
        (r"^Нужно оставить x отдельно[.!?]?$", "Ищем x"),
        (r"^Нужно узнать, сколько всего вместе[.!?]?$", "Ищем, сколько всего вместе"),
        (r"^Нужно узнать, сколько осталось[.!?]?$", "Ищем, сколько осталось"),
        (r"^Нужно узнать, сколько получилось вместе[.!?]?$", "Ищем, сколько получилось вместе"),
        (r"^Потом узнаем, сколько убрали:\s*(.+)$", r"Потом смотрим, сколько убрали: \1"),
        (r"^Потом узнаём, сколько убрали:\s*(.+)$", r"Потом смотрим, сколько убрали: \1"),
        (r"^Потом узнаем, сколько добавили:\s*(.+)$", r"Потом смотрим, сколько добавили: \1"),
        (r"^Потом узнаём, сколько добавили:\s*(.+)$", r"Потом смотрим, сколько добавили: \1"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+умножение\s+меняется\s+на\s+деление[.!?]?$", "Умножение меняем на деление"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+деление\s+меняется\s+на\s+умножение[.!?]?$", "Деление меняем на умножение"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+плюс\s+меняется\s+на\s+минус[.!?]?$", "Плюс меняем на минус"),
        (r"^При\s+переносе\s+через\s+знак\s+равно\s+минус\s+меняется\s+на\s+плюс[.!?]?$", "Минус меняем на плюс"),
        (r"^Сначала:\s*(.+)$", r"Сначала \1"),
        (r"^Потом:\s*(.+)$", r"Потом \1"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    text = re.sub(r"\b(?:обычно|часто)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.;")
    return capitalize_if_needed(text)

def _normalize_advice_line_v9(text: str, kind: str) -> str:
    value = str(text or "").strip().rstrip(".!?")
    if not value:
        return default_advice(kind)

    replacements = [
        (r"^проверяй деление умножением$", "в делении столбиком повторяй шаги: подбери, умножь, вычти"),
        (r"^остаток меньше делителя$", "остаток всегда должен быть меньше делителя"),
        (r"^решай по шагам$", "двигайся по шагам и не перескакивай"),
        (r"^считай по порядку$", "называй каждое действие по порядку"),
        (r"^большие числа складывай по частям$", "разбивай большие числа на десятки и единицы"),
        (r"^сначала убирай десятки, потом единицы$", "сначала работай с десятками, потом с единицами"),
        (r"^вычитай по частям$", "удобно вычитать по частям"),
        (r"^умножение можно представить как одинаковые группы$", "умножение можно представить как одинаковые группы"),
        (r"^сначала приведи дроби к общему знаменателю$", "сначала делай одинаковые знаменатели"),
        (r"^при одинаковых знаменателях меняется только числитель$", "при одинаковых знаменателях меняется только числитель"),
        (r"^множитель переносим делением$", "множитель переносим делением"),
        (r"^деление меняем на умножение$", "если x делят на число, справа умножаем"),
        (r"^если x в делителе, дели делимое на результат$", "если x стоит в делителе, дели делимое на результат"),
        (r"^у квадрата 4 равные стороны$", "у квадрата все стороны равны"),
        (r"^половина периметра — это длина плюс ширина$", "сначала находи половину периметра"),
        (r"^ширина = площадь : длина$", "ширину находим делением площади на длину"),
        (r"^длина = площадь : ширина$", "длину находим делением площади на ширину"),
        (r"^площадь = длина × ширина$", "для площади умножай длину на ширину"),
        (r"^сначала пойми, что нужно найти$", "сначала пойми, что спрашивают"),
        (r"^сначала выбери правило$", "сначала выбери нужное правило"),
    ]
    for pattern, repl in replacements:
        if re.fullmatch(pattern, value, flags=re.IGNORECASE):
            value = repl
            break

    value = re.sub(r"\s{2,}", " ", value).strip(" ,.;")
    return value or default_advice(kind)

def _is_low_value_body_line_v9(line: str) -> bool:
    text = str(line or "").strip()
    return any(pattern.fullmatch(text) for pattern in LOW_VALUE_BODY_PATTERNS_V9)

def _body_line_has_math_signal_v9(line: str) -> bool:
    return bool(re.search(r"\d|x|х|[+\-=:×÷/]", str(line or ""), flags=re.IGNORECASE))

def _extract_answer_value_v9(answer_line: str) -> str:
    if not answer_line:
        return ""
    return re.sub(r"^Ответ:\s*", "", answer_line, flags=re.IGNORECASE).strip().rstrip(".!?").strip()

def _looks_like_direct_result_intro_v9(line: str, answer_value: str, kind: str) -> bool:
    if kind == "equation":
        return False
    text = str(line or "").strip().rstrip(".!?").strip()
    if not text or "=" not in text:
        return False
    match = DIRECT_RESULT_INTRO_RE_V9.match(text)
    if not match:
        return False
    if answer_value:
        right_value = match.group(1).strip().rstrip(".!?").strip()
        if right_value != answer_value:
            return False
    return True

def _limit_body_lines_v9(lines, kind: str):
    limit = BODY_LINE_LIMITS_V9.get(kind, BODY_LINE_LIMITS_V9["other"])
    return lines[:limit]

def _teaching_intro_from_direct_result_v9(line: str) -> str:
    lower = str(line or "").lower()
    if lower.startswith("делим"):
        return "Ищем частное"
    if lower.startswith("складываем"):
        return "Ищем сумму"
    if lower.startswith("вычитаем"):
        return "Ищем разность"
    if lower.startswith("умножаем"):
        return "Ищем произведение"
    if lower.startswith("считаем"):
        return "Решаем по шагам"
    return ""

def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    cleaned = sanitize_model_text(text)
    if not cleaned:
        advice = _normalize_advice_line_v9(forced_advice or "", kind)
        if forced_answer:
            return join_explanation_lines(f"Ответ: {forced_answer}", f"Совет: {advice}")
        return join_explanation_lines("Напишите задачу понятнее", "Ответ: нужно уточнить запись", f"Совет: {advice}")

    body_lines = []
    answer_line = None
    advice_line = None
    check_line = None

    for raw_line in cleaned.split("\n"):
        line = str(raw_line or "").strip()
        if not line:
            continue
        normalized = SECTION_PREFIX_RE_V9.sub(lambda m: f"{m.group(1).capitalize()}: ", line)
        lower = normalized.lower()
        if lower.startswith("ответ:"):
            value = normalized.split(":", 1)[1].strip()
            if value:
                answer_line = f"Ответ: {value}"
            continue
        if lower.startswith("совет:"):
            value = normalized.split(":", 1)[1].strip()
            if value:
                advice_line = value
            continue
        if lower.startswith("проверка:"):
            value = normalized.split(":", 1)[1].strip()
            if value:
                check_line = f"Проверка: {value}"
            continue
        body_lines.append(normalized)

    normalized_body = []
    seen = set()
    for line in body_lines:
        normalized = _normalize_body_line_v9(line)
        if not normalized:
            continue
        key = normalized.lower().rstrip(".!?")
        if key in seen:
            continue
        seen.add(key)
        normalized_body.append(normalized)
    body_lines = normalized_body

    if any(_body_line_has_math_signal_v9(line) for line in body_lines):
        body_lines = [line for line in body_lines if not _is_low_value_body_line_v9(line)]

    if kind != "equation":
        check_line = None

    if forced_answer is not None:
        answer_line = f"Ответ: {forced_answer}"

    answer_value = _extract_answer_value_v9(answer_line or "")
    if body_lines:
        first_line = body_lines[0]
        if _looks_like_direct_result_intro_v9(first_line, answer_value, kind):
            if len(body_lines) > 1:
                body_lines = body_lines[1:]
            else:
                intro = _teaching_intro_from_direct_result_v9(first_line)
                if intro:
                    body_lines = [intro]

    if answer_line is None and body_lines:
        tail = body_lines[-1]
        match = re.search(r"=\s*([^=]+)$", tail)
        if match:
            answer_line = f"Ответ: {match.group(1).strip()}"

    if answer_line is None:
        answer_line = "Ответ: проверь запись задачи"

    body_lines = _limit_body_lines_v9(body_lines, kind)

    advice_value = _normalize_advice_line_v9(forced_advice or advice_line or "", kind)
    final_lines = list(body_lines)
    if check_line:
        final_lines.append(check_line)
    final_lines.append(answer_line)
    final_lines.append(f"Совет: {advice_value}")
    return join_explanation_lines(*final_lines)

def _build_long_division_steps_v9(dividend: int, divisor: int):
    digits = list(str(dividend))
    steps = []
    current = ""
    quotient = ""
    started = False

    for index, digit in enumerate(digits):
        current += digit
        current_number = int(current)

        if current_number < divisor:
            if started:
                quotient += "0"
            continue

        started = True
        q_digit = current_number // divisor
        product = q_digit * divisor
        remainder = current_number - product

        steps.append({
            "current": current_number,
            "q_digit": q_digit,
            "product": product,
            "remainder": remainder,
            "next_digit": int(digits[index + 1]) if index + 1 < len(digits) else None,
        })
        quotient += str(q_digit)
        current = str(remainder)

    if not started:
        quotient = "0"

    remainder = int(current or "0")
    return {
        "steps": steps,
        "quotient": quotient,
        "remainder": remainder,
    }

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Решение.",
            "Ищем сумму",
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}",
            f"Теперь складываем результаты: {left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: разбивай большие числа на десятки и единицы",
        )

    return join_explanation_lines(
        "Решение.",
        "Ищем сумму",
        f"Считаем: {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: называй числа по порядку",
    )

def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
            "Решение.",
            "Сначала сравниваем числа",
            f"{left} меньше {right}, поэтому ответ будет отрицательным",
            f"Считаем: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: перед вычитанием полезно сравнить числа",
        )

    if right >= 10:
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            "Решение.",
            "Ищем разность",
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}",
            f"Потом вычитаем единицы: {middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: удобно сначала работать с десятками, потом с единицами",
        )

    return join_explanation_lines(
        "Решение.",
        "Ищем разность",
        f"Считаем: {left} - {right} = {result}",
        f"Ответ: {result}",
        "Совет: вычитай спокойно и не пропускай знак минус",
    )

def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)

    if big >= 10 and small <= 10:
        tens = big - big % 10
        units = big % 10
        return join_explanation_lines(
            "Решение.",
            "Ищем произведение",
            f"Разбиваем {big} на {tens} и {units}",
            f"{tens} × {small} = {tens * small}",
            f"{units} × {small} = {units * small}",
            f"Теперь складываем части: {tens * small} + {units * small} = {result}",
            f"Ответ: {result}",
            "Совет: умножение удобно разбирать на части",
        )

    return join_explanation_lines(
        "Решение.",
        "Ищем произведение",
        f"Считаем: {left} × {right} = {result}",
        f"Ответ: {result}",
        "Совет: умножение показывает одинаковые группы",
    )

def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "Решение.",
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала смотри на делитель",
        )

    quotient, remainder = divmod(left, right)

    if left < 100 and right < 10:
        if remainder == 0:
            return join_explanation_lines(
                "Решение.",
                "Ищем, сколько раз делитель помещается в делимом",
                f"{quotient} × {right} = {left}, значит {left} : {right} = {quotient}",
                f"Ответ: {quotient}",
                "Совет: в делении ищи число, которое при умножении даёт делимое",
            )
        return join_explanation_lines(
            "Решение.",
            "Ищем, сколько полных раз делитель помещается в делимом",
            f"{quotient} × {right} = {quotient * right}",
            f"После вычитания остаётся {left - quotient * right}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше делителя",
        )

    model = _build_long_division_steps_v9(left, right)
    steps = model["steps"]
    lines = ["Решение.", "Ищем частное"]

    if not steps:
        lines.append(f"{left} меньше {right}, значит в частном будет 0")
        if remainder:
            lines.append(f"Остаток равен {remainder}")
        answer_text = "0" if remainder == 0 else f"0, остаток {remainder}"
        return join_explanation_lines(
            *lines,
            f"Ответ: {answer_text}",
            "Совет: если делимое меньше делителя, частное начинается с нуля",
        )

    first_step = steps[0]
    lines.append(f"Сначала берём первое неполное делимое {first_step['current']}")

    for index, step in enumerate(steps):
        current = step["current"]
        q_digit = step["q_digit"]
        product = step["product"]
        remainder_value = step["remainder"]
        next_current = steps[index + 1]["current"] if index + 1 < len(steps) else None
        next_try = (q_digit + 1) * right
        if next_try > current:
            choice_part = f"Подбираем {q_digit}, потому что {q_digit} × {right} = {product}, а {q_digit + 1} × {right} = {next_try}, это уже больше"
        else:
            choice_part = f"Подбираем {q_digit}, потому что {q_digit} × {right} = {product}"

        if next_current is not None:
            lines.append(
                f"{choice_part}. После вычитания остаётся {remainder_value}, сносим следующую цифру и получаем {next_current}"
            )
        elif remainder_value == 0:
            lines.append(f"{choice_part}. После вычитания остаётся 0, деление закончено")
        else:
            lines.append(f"{choice_part}. После вычитания остаётся {remainder_value}, это и есть остаток")

    answer_text = str(quotient) if remainder == 0 else f"{quotient}, остаток {remainder}"
    advice = "в делении столбиком повторяй шаги: взял, подобрал, умножил, вычел"
    return join_explanation_lines(*lines, f"Ответ: {answer_text}", f"Совет: {advice}")

def try_local_fraction_explanation(raw_text: str) -> Optional[str]:
    source = to_fraction_source(raw_text)
    if not source:
        return None

    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*([+\-])\s*(\d+)\s*/\s*(\d+)\s*", source)
    if not match:
        return None

    a, b, operator, c, d = match.groups()
    a = int(a)
    b = int(b)
    c = int(c)
    d = int(d)

    if b == 0 or d == 0:
        return join_explanation_lines(
            "Решение.",
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная",
            "Совет: сначала проверь знаменатели",
        )

    action_symbol = "+" if operator == "+" else "-"
    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)

    if b == d:
        top_result = a + c if operator == "+" else a - c
        lines = [
            "Решение.",
            "Смотрим на знаменатели. Они одинаковые",
            f"Значит, работаем только с числителями: {a} {action_symbol} {c} = {top_result}",
            f"Получаем дробь {top_result}/{b}",
        ]
        if format_fraction(result) != f"{top_result}/{b}":
            lines.append(f"Сокращаем: {top_result}/{b} = {format_fraction(result)}")
        lines.extend([
            f"Ответ: {format_fraction(result)}",
            "Совет: при одинаковых знаменателях меняется только числитель",
        ])
        return join_explanation_lines(*lines)

    common = math.lcm(b, d)
    a_scaled = a * (common // b)
    c_scaled = c * (common // d)
    top_result = a_scaled + c_scaled if operator == "+" else a_scaled - c_scaled
    simplified = Fraction(top_result, common)
    lines = [
        "Решение.",
        f"Сначала делаем одинаковые знаменатели: {common}",
        f"{a}/{b} = {a_scaled}/{common}, а {c}/{d} = {c_scaled}/{common}",
        f"Теперь считаем: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top_result}/{common}",
    ]
    if format_fraction(simplified) != f"{top_result}/{common}":
        lines.append(f"Сокращаем: {top_result}/{common} = {format_fraction(simplified)}")
    lines.extend([
        f"Ответ: {format_fraction(result)}",
        "Совет: сначала делай одинаковые знаменатели",
    ])
    return join_explanation_lines(*lines)

async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )

    if local_explanation:
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_text,
            },
        ],
        "max_tokens": 500,
        "temperature": 0.05,
    }

    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result

    shaped = shape_explanation(llm_result["result"], kind)
    return {
        "result": shaped,
        "source": "llm",
        "validated": False,
    }