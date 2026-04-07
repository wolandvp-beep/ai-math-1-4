import ast
import math
import os
import re
from fractions import Fraction
from typing import Optional

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

SYSTEM_PROMPT = """
Ты — спокойный и очень точный учитель математики для детей 7–10 лет.
Нужно, чтобы ответ нравился и ребёнку, и родителю: он должен быть понятным, аккуратным и без ошибок.

Пиши только на русском языке.
Пиши без markdown, списков, нумерации, смайликов и лишних вступлений.
Не используй похвалу и оценки: нельзя писать "Отлично", "Молодец", "Давай разберёмся", "Хорошо", "Посмотрим".
Не используй слова "Запомни" и "Памятка".
Каждая строка — одна мысль.
Каждая строка должна вести к ответу по порядку.
Не повторяй одну и ту же мысль разными словами.
Не пиши пустые фразы вроде "Известны два количества" или "Нужно оставить x отдельно", если в строке нет нового смысла.
Короткие предложения лучше длинных.

Формат ответа всегда такой:
сначала 2–4 короткие строки объяснения;
если есть проверка, отдельная строка "Проверка: ...";
потом строка "Ответ: ...";
последняя строка "Совет: ...".

В объяснении оставляй только полезные строки:
короткое правило;
или вычисление;
или короткую проверку.
Если строка ничего не добавляет к решению, не пиши её.

Правила по типам задач:
Если это текстовая задача, коротко скажи, что известно, что нужно найти и почему выбирается это действие.
Если это обычный пример, объясни способ кратко и по делу. Не дублируй подробные внутренние шаги столбика.
Если это выражение со скобками, сначала считай в скобках, потом остальное.
Если это уравнение, оставь x отдельно, коротко покажи смену действия и сделай короткую проверку.
Если это дроби, скажи про знаменатели и общий знаменатель только если это действительно нужно.
Если это геометрия, сначала скажи, что именно ищем и какое правило используем.

Не выдумывай данные, которых нет в условии.
Если запись непонятная или это не задача по математике, спокойно попроси записать пример понятнее.
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



def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: в задачах 'во сколько раз' нужно делить на ненулевое число",
        )
    if bigger % smaller != 0:
        return None

    result = bigger // smaller
    return join_explanation_lines(
        "Нужно узнать, во сколько раз одно число больше или меньше другого",
        f"Для этого делим большее число на меньшее: {bigger} : {smaller} = {result}",
        f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
        "Совет: вопрос 'во сколько раз больше или меньше' обычно решаем делением",
    )



def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Ищем, сколько всего вместе",
        f"Считаем: {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько стало или сколько всего, часто подходит сложение",
    )



def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
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
        "Сравниваем два числа",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос 'на сколько больше или меньше' обычно решаем вычитанием",
    )



def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
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
        "Сравниваем, на сколько стало меньше",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, вычти то, что осталось, из того, что было",
    )



def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    group_word = plural_form(groups, "группа", "группы", "групп")
    return join_explanation_lines(
        f"Есть {groups} {group_word} по {per_group}",
        f"Считаем: {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова 'по ... в каждой' часто подсказывают умножение",
    )



def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь, на сколько частей делят предметы",
        )

    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"Нужно разделить {total} поровну на {groups} частей",
            f"Делим: {total} : {groups} = {quotient}",
            f"Значит каждый получит {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова 'поровну' и 'каждый' часто подсказывают деление",
        )

    return join_explanation_lines(
        f"Нужно разделить {total} поровну на {groups} частей",
        f"Делим: {total} : {groups} = {quotient}, остаток {remainder}",
        f"Каждый получит {quotient}, и останется {remainder}",
        f"Ответ: каждому по {quotient}, остаток {remainder}",
        "Совет: при делении поровну остаток должен быть меньше делителя",
    )



def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "В одной группе не может быть ноль предметов",
            "Ответ: запись задачи неверная",
            "Совет: проверь, сколько предметов должно быть в одной группе",
        )

    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        group_word = plural_form(quotient, "группа", "группы", "групп")
        return join_explanation_lines(
            f"Нужно узнать, сколько групп по {per_group} получится из {total}",
            f"Делим: {total} : {per_group} = {quotient}",
            f"Получится {quotient} {group_word}",
            f"Ответ: {quotient}",
            "Совет: если известно, сколько предметов в одной группе, число групп находим делением",
        )

    if needs_extra_group:
        return join_explanation_lines(
            f"Полных групп по {per_group} получается {quotient}, и ещё остаётся {remainder}",
            "Чтобы все предметы поместились, нужна ещё одна группа",
            f"Ответ: {quotient + 1}",
            "Совет: если что-то осталось, иногда нужна ещё одна коробка или место",
        )

    if explicit_remainder:
        full_group_phrase = plural_form(quotient, "полная группа", "полные группы", "полных групп")
        return join_explanation_lines(
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
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти длину, делим площадь на ширину: {area} : {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: если известны площадь и ширина, длину находим делением",
        )

    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines(
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
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Считаем: {side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь показывает, сколько места занимает фигура",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
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
    cleaned = re.sub(r"^\s*\d+[.)]\s*", "", cleaned, flags=re.MULTILINE)
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
    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Складываем десятки и единицы",
            f"{left_tens} + {right_tens} = {left_tens + right_tens}",
            f"{left_units} + {right_units} = {left_units + right_units}",
            f"{left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: большие числа удобно складывать по частям",
        )

    return join_explanation_lines(
        f"Складываем числа: {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: считай спокойно и не пропускай числа",
    )



def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
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
            "Вычитаем по частям",
            f"{left} - {tens} = {middle}",
            f"{middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: в вычитании удобно сначала убрать десятки, потом единицы",
        )

    return join_explanation_lines(
        f"Вычитаем: {left} - {right} = {result}",
        f"Ответ: {result}",
        "Совет: считай по порядку и проверяй знак действия",
    )



def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)

    if big >= 10 and small <= 10:
        tens = big - big % 10
        units = big % 10
        return join_explanation_lines(
            f"Умножаем {big} на {small}",
            f"{tens} × {small} = {tens * small}",
            f"{units} × {small} = {units * small}",
            f"{tens * small} + {units * small} = {result}",
            f"Ответ: {result}",
            "Совет: умножение удобно разложить на десятки и единицы",
        )

    return join_explanation_lines(
        f"Умножаем: {left} × {right} = {result}",
        f"Ответ: {result}",
        "Совет: если трудно, представь умножение как одинаковые группы",
    )



def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь делитель перед вычислением",
        )

    quotient, remainder = divmod(left, right)
    if remainder == 0:
        return join_explanation_lines(
            f"Делим {left} на {right}",
            f"{left} : {right} = {quotient}",
            f"Проверка: {quotient} × {right} = {left}",
            f"Ответ: {quotient}",
            "Совет: после деления полезно сделать проверку умножением",
        )

    return join_explanation_lines(
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
    return join_explanation_lines(*body_lines, f"Ответ: {answer}", f"Совет: {advice}")



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
                "Плюс меняем на минус",
                f"x = {format_fraction(rhs_value)} - {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x + {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число переносим через знак равно обратным действием",
            )

        if kind == "x_minus":
            answer = rhs_value + number
            return join_explanation_lines(
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
                        "Здесь x умножают на 0",
                        "0 всегда даёт 0",
                        "Ответ: подходит любое число",
                        "Совет: при умножении на ноль результат всегда ноль",
                    )
                return join_explanation_lines(
                    "Число, умноженное на 0, не может дать другой результат",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = rhs_value / number
            return join_explanation_lines(
                "Умножение меняем на деление",
                f"x = {format_fraction(rhs_value)} : {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x × {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: множитель переносим через знак равно делением",
            )

        if kind == "x_div":
            if number == 0:
                return join_explanation_lines(
                    "На ноль делить нельзя",
                    "Такое уравнение не имеет решения",
                    "Ответ: решения нет",
                    "Совет: проверь делитель перед вычислением",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Деление меняем на умножение",
                f"x = {format_fraction(rhs_value)} × {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"x : {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x делят на число, справа нужно умножить",
            )

        if kind == "plus_x":
            answer = rhs_value - number
            return join_explanation_lines(
                "Плюс меняем на минус",
                f"x = {format_fraction(rhs_value)} - {format_fraction(number)} = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} + x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число переносим через знак равно обратным действием",
            )

        if kind == "minus_x":
            answer = number - rhs_value
            return join_explanation_lines(
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
                        "Здесь 0 умножают на x",
                        "0 всегда даёт 0",
                        "Ответ: подходит любое число",
                        "Совет: при умножении на ноль результат всегда ноль",
                    )
                return join_explanation_lines(
                    "0 не может дать другой результат при умножении",
                    "Ответ: решения нет",
                    "Совет: проверь запись уравнения",
                )
            answer = rhs_value / number
            return join_explanation_lines(
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
                        "В делимом стоит 0",
                        "0, делённое на любое ненулевое число, остаётся 0",
                        "Значит подходит любое число, кроме 0",
                        "Ответ: любое число, кроме 0",
                        "Совет: в делителе ноль быть не может",
                    )
                return join_explanation_lines(
                    "В делимом стоит 0",
                    f"0, делённое на ненулевое число, не может дать {format_fraction(rhs_value)}",
                    "Ответ: решения нет",
                    "Совет: проверь делимое и результат",
                )
            if rhs_value == 0:
                return join_explanation_lines(
                    "Деление не может дать ноль, если делимое не равно нулю",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "x стоит в делителе",
                f"x = {format_fraction(number)} : {format_fraction(rhs_value)} = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} : x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x стоит в делителе, раздели делимое на результат",
            )

    return None


async def call_deepseek(payload: dict, timeout_seconds: float = 45.0):
    if not DEEPSEEK_API_KEY:
        return {"error": "API key not configured", "details": "Переменная окружения myapp_ai_math_1_4_API_key не установлена"}
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


async def build_explanation(user_text: str) -> dict:
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )

    if local_explanation:
        kind = infer_task_kind(user_text)
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    kind = infer_task_kind(user_text)
    extra_instruction = ""
    if kind == "word":
        extra_instruction = (
            "Это текстовая задача. В первых строках коротко скажи, что известно, "
            "что нужно найти и почему подходит выбранное действие. "
            "Потом выполни вычисление и закончи строками Ответ и Совет.\n\n"
        )
    elif kind == "geometry":
        extra_instruction = (
            "Это задача по геометрии. Сначала скажи, что именно ищем и какое правило используем, "
            "потом сделай вычисление и закончи строками Ответ и Совет.\n\n"
        )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "Объясни решение так, чтобы ребёнок 7–10 лет понял ход решения, "
                    "а родителю было спокойно за точность. "
                    "Дай ответ строго в заданном формате и не растягивай объяснение.\n\n"
                    f"{extra_instruction}{user_text}"
                ),
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

# STYLE_TUNING_PATCH_V8
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
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}",
            f"Складываем результаты: {left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: большие числа складывай по частям",
        )

    return join_explanation_lines(
        f"Складываем: {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: считай по порядку",
    )



def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
            f"Вычитаем: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: сначала сравни числа",
        )

    if right >= 10:
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}",
            f"Потом вычитаем единицы: {middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: вычитай по частям",
        )

    return join_explanation_lines(
        f"Вычитаем: {left} - {right} = {result}",
        f"Ответ: {result}",
        "Совет: считай по порядку",
    )



def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь делитель",
        )

    quotient, remainder = divmod(left, right)
    if remainder == 0:
        return join_explanation_lines(
            f"Делим: {left} : {right} = {quotient}",
            f"Проверка: {quotient} × {right} = {left}",
            f"Ответ: {quotient}",
            "Совет: проверяй деление умножением",
        )

    return join_explanation_lines(
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
                "Ищем x",
                f"Вычитаем {number_text}: x = {rhs_text} - {number_text} = {format_fraction(answer)}",
                check,
                f"Ответ: {format_fraction(answer)}",
                "Совет: число после плюса переносим вычитанием",
            )

        if kind == "x_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Ищем x",
                f"Прибавляем {number_text}: x = {rhs_text} + {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x - {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: число после минуса переносим сложением",
            )

        if kind == "minus_x":
            answer = number - rhs_value
            return join_explanation_lines(
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
                        "0 при умножении всегда даёт 0",
                        "Ответ: подходит любое число",
                        "Совет: умножение на ноль всегда даёт ноль",
                    )
                return join_explanation_lines(
                    "0 при умножении не может дать другой результат",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение",
                )
            answer = rhs_value / number
            check = format_equation_check("x × " + number_text if kind == "x_mul" else number_text + " × x", format_fraction(answer), rhs_text)
            return join_explanation_lines(
                "Ищем x",
                f"Делим {rhs_text} на {number_text}: x = {rhs_text} : {number_text} = {format_fraction(answer)}",
                check,
                f"Ответ: {format_fraction(answer)}",
                "Совет: множитель переносим делением",
            )

        if kind == "x_div":
            if number == 0:
                return join_explanation_lines(
                    "На ноль делить нельзя",
                    "Ответ: решения нет",
                    "Совет: проверь делитель",
                )
            answer = rhs_value * number
            return join_explanation_lines(
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
                        "0, делённое на ненулевое число, всегда равно 0",
                        "Ответ: любое число, кроме 0",
                        "Совет: в делителе ноль быть не может",
                    )
                return join_explanation_lines(
                    "0, делённое на ненулевое число, не может дать другой результат",
                    "Ответ: решения нет",
                    "Совет: проверь делимое и результат",
                )
            if rhs_value == 0:
                return join_explanation_lines(
                    "Ненулевое число при делении не может дать 0",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение",
                )
            answer = number / rhs_value
            return join_explanation_lines(
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
        "Ищем разницу между числами",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос 'на сколько' решаем вычитанием",
    )



def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
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
        "Ищем, сколько убрали",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вычти, сколько осталось, из того, что было",
    )



def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Ищем, сколько всего",
        f"Считаем: {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова 'по ... в каждой' подсказывают умножение",
    )



def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь, на сколько частей делят",
        )

    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Ищем, сколько получит каждый",
            f"Считаем: {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова 'поровну' и 'каждый' подсказывают деление",
        )

    return join_explanation_lines(
        "Ищем, сколько получит каждый",
        f"Считаем: {total} : {groups} = {quotient}, остаток {remainder}",
        f"Ответ: каждому по {quotient}, остаток {remainder}",
        "Совет: остаток меньше делителя",
    )



def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "В группе не может быть 0 предметов",
            "Ответ: запись задачи неверная",
            "Совет: проверь размер группы",
        )

    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Ищем, сколько групп получится",
            f"Считаем: {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находим делением",
        )

    if needs_extra_group:
        return join_explanation_lines(
            f"Считаем: {total} : {per_group} = {quotient}, остаток {remainder}",
            "Осталось ещё несколько предметов, нужна ещё одна группа",
            f"Ответ: {quotient + 1}",
            "Совет: если что-то осталось, иногда нужна ещё одна коробка",
        )

    if explicit_remainder:
        full_group_phrase = plural_form(quotient, "полная группа", "полные группы", "полных групп")
        return join_explanation_lines(
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
        f"Сначала находим второе число: {base} {first_sign} {first_delta} = {middle}",
        f"Потом третье: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
        "Совет: решай по шагам",
    )



def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
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
            "Ищем длину прямоугольника",
            f"Делим площадь на ширину: {area} : {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: длина = площадь : ширина",
        )

    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines(
            "Ищем периметр квадрата",
            f"Считаем: {side} × 4 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у квадрата 4 равные стороны",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
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
            "Ищем площадь квадрата",
            f"Считаем: {side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь квадрата — это сторона на сторону",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Ищем площадь прямоугольника",
            f"Считаем: {length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь = длина × ширина",
        )

    return None

# STYLE_TUNING_PATCH_V8_FIX_CAPITALIZE

def capitalize_if_needed(text: str) -> str:
    line = str(text or "").strip()
    if not line:
        return ""
    first = line[0]
    if first.isalpha() and first.islower():
        return first.upper() + line[1:]
    return line


# EXPLANATION_STRUCTURE_PATCH_V9

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
            "Ищем сумму",
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}",
            f"Теперь складываем результаты: {left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: разбивай большие числа на десятки и единицы",
        )

    return join_explanation_lines(
        "Ищем сумму",
        f"Считаем: {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: называй числа по порядку",
    )


def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
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
            "Ищем разность",
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}",
            f"Потом вычитаем единицы: {middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: удобно сначала работать с десятками, потом с единицами",
        )

    return join_explanation_lines(
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
            "Ищем произведение",
            f"Разбиваем {big} на {tens} и {units}",
            f"{tens} × {small} = {tens * small}",
            f"{units} × {small} = {units * small}",
            f"Теперь складываем части: {tens * small} + {units * small} = {result}",
            f"Ответ: {result}",
            "Совет: умножение удобно разбирать на части",
        )

    return join_explanation_lines(
        "Ищем произведение",
        f"Считаем: {left} × {right} = {result}",
        f"Ответ: {result}",
        "Совет: умножение показывает одинаковые группы",
    )


def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала смотри на делитель",
        )

    quotient, remainder = divmod(left, right)

    if left < 100 and right < 10:
        if remainder == 0:
            return join_explanation_lines(
                "Ищем, сколько раз делитель помещается в делимом",
                f"{quotient} × {right} = {left}, значит {left} : {right} = {quotient}",
                f"Ответ: {quotient}",
                "Совет: в делении ищи число, которое при умножении даёт делимое",
            )
        return join_explanation_lines(
            "Ищем, сколько полных раз делитель помещается в делимом",
            f"{quotient} × {right} = {quotient * right}",
            f"После вычитания остаётся {left - quotient * right}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше делителя",
        )

    model = _build_long_division_steps_v9(left, right)
    steps = model["steps"]
    lines = ["Ищем частное"]

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
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная",
            "Совет: сначала проверь знаменатели",
        )

    action_symbol = "+" if operator == "+" else "-"
    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)

    if b == d:
        top_result = a + c if operator == "+" else a - c
        lines = [
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


SYSTEM_PROMPT_V10 = """
Ты — спокойный, точный и доброжелательный учитель математики для детей 7–10 лет.
Главная цель — объяснить ход решения так, чтобы ребёнок мог читать и слушать по строкам.

Пиши только на русском языке.
Пиши без markdown, списков, нумерации, смайликов и лишних вступлений.
Не используй похвалу и оценки.
Каждая строка — одна полезная мысль.
Не повторяй одну и ту же мысль разными словами.
Убирай пустые фразы, которые ничего не объясняют.

Структура ответа:
сначала 2–5 коротких строк последовательного объяснения;
только для уравнения добавь строку "Проверка: ...";
потом строка "Ответ: ...";
последняя строка "Совет: ...".

Главные правила:
Не сообщай итоговый ответ в первой строке.
Для обычного примера не пиши строку "Проверка:".
Не пиши строку вида "25155 : 39 = 645" как начало объяснения.
Не дублируй ответ в объяснении и в отдельной строке "Ответ:".
Совет должен быть учебным и конкретным.

Как объяснять по типам:
Если это обычный пример, сначала скажи, что ищем: сумму, разность, произведение или частное.
Если это деление, объясняй ход по шагам: неполное делимое, подбор цифры частного, умножение, вычитание, снос следующей цифры.
Если это выражение со скобками, сначала считай в скобках, потом остальные действия по порядку.
Если это уравнение, сначала скажи, что ищем x, потом объясни перенос или обратное действие, потом сделай короткую проверку.
Если это текстовая задача, сначала скажи, что нужно узнать и почему подходит это действие, потом выполни вычисление.
Если это дроби, сначала смотри на знаменатели.
Если это геометрия, сначала назови правило, потом подставь числа.

Не выдумывай данные, которых нет в условии.
Если запись непонятная или это не задача по математике, спокойно попроси записать пример понятнее.
""".strip()


async def build_explanation(user_text: str) -> dict:
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )

    kind = infer_task_kind(user_text)

    if local_explanation:
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    extra_instruction = ""
    if kind == "word":
        extra_instruction = (
            "Это текстовая задача. Сначала скажи, что нужно найти и почему выбирается это действие. "
            "Потом выполни вычисление.\n\n"
        )
    elif kind == "geometry":
        extra_instruction = (
            "Это задача по геометрии. Сначала назови правило, потом подставь числа и выполни вычисление.\n\n"
        )
    elif kind == "expression":
        extra_instruction = (
            "Это обычный пример или выражение. Не пиши готовый ответ в первой строке. "
            "Если есть деление, объясняй ход последовательно и без строки Проверка.\n\n"
        )
    elif kind == "fraction":
        extra_instruction = (
            "Это задача с дробями. Сначала скажи, одинаковые ли знаменатели. "
            "Потом выполни вычисление.\n\n"
        )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_V10,
            },
            {
                "role": "user",
                "content": (
                    "Объясни решение так, чтобы ребёнок мог слушать текст и идти по нему глазами строка за строкой. "
                    "Сначала объяснение, потом ответ, а не наоборот. "
                    "Ответ дай строго в заданной структуре.\n\n"
                    f"{extra_instruction}{user_text}"
                ),
            },
        ],
        "max_tokens": 550,
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


# === V11 textbook pedagogy patch ===
# The goal of this patch is to align explanations with primary-school methods:
# what we look for -> why this action -> step(s) -> answer -> short teaching advice.

ADDITIVE_RELATION_RE_V11 = re.compile(r"на\s+(\d+)(?:\s+[а-яё]+){0,3}\s+(больше|меньше)", re.IGNORECASE)
MULTIPLICATIVE_RELATION_RE_V11 = re.compile(r"в\s+(\d+)\s+раз(?:а)?(?:\s+[а-яё]+){0,3}\s+(больше|меньше)", re.IGNORECASE)
DOUBLE_GROUP_RE_V11 = re.compile(r"(\d+)\s+[а-яё]+(?:\s+[а-яё]+){0,3}\s+по\s+(\d+)", re.IGNORECASE)


def _invert_more_less_v11(mode: str) -> str:
    return "меньше" if mode == "больше" else "больше"



def _sign_from_mode_v11(mode: str) -> str:
    return "+" if mode == "больше" else "-"



def _action_word_from_mode_v11(mode: str) -> str:
    return "прибавляем" if mode == "больше" else "вычитаем"



def _normalize_wording_v11(text: str) -> str:
    return normalize_word_problem_text(text).lower()



def _is_indirect_form_v11(text: str) -> bool:
    lower = _normalize_wording_v11(text)
    return bool(re.search(r"\bэто\b", lower) or re.search(r"\bчто\b[^.?!]*\bчем\b", lower))



def extract_relation_pairs(text: str):
    lower = _normalize_wording_v11(text)
    return [(int(match.group(1)), match.group(2).lower()) for match in ADDITIVE_RELATION_RE_V11.finditer(lower)]



def extract_multiplicative_relation_pairs_v11(text: str):
    lower = _normalize_wording_v11(text)
    return [(int(match.group(1)), match.group(2).lower()) for match in MULTIPLICATIVE_RELATION_RE_V11.finditer(lower)]



def _safe_related_value_v11(base: int, delta_or_factor: int, mode: str, multiplicative: bool = False) -> Optional[int]:
    if multiplicative:
        if delta_or_factor == 0:
            return None
        if mode == "больше":
            return base * delta_or_factor
        if base % delta_or_factor != 0:
            return None
        return base // delta_or_factor
    return apply_more_less(base, delta_or_factor, mode)



def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Нужно узнать, сколько всего вместе",
        "Это задача на сумму, значит складываем",
        f"Считаем: {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: слова «всего» и «вместе» часто подсказывают сложение",
    )



def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько осталось",
        "Чтобы найти остаток, вычитаем",
        f"Считаем: {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: слова «осталось», «убрали», «отдали» часто подсказывают вычитание",
    )



def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, на сколько одно число больше или меньше другого",
        "Для этого из большего числа вычитаем меньшее",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько больше или меньше» решаем вычитанием",
    )



def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Нужно найти, сколько было сначала",
        "Чтобы найти, сколько было, складываем то, что осталось, и то, что убрали",
        f"Считаем: {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: если часть убрали, а спрашивают, сколько было, помогает сложение",
    )



def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно найти, сколько было сначала",
        "Чтобы найти начальное число, из того, что стало, вычитаем добавленное",
        f"Считаем: {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: если сначала было меньше, а потом добавили, ищем начальное число вычитанием",
    )



def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько добавили",
        "Сравниваем, сколько было и сколько стало",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, сравни число было и число стало",
    )



def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько убрали",
        "Сравниваем, сколько было и сколько осталось",
        f"Считаем: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, вычитай остаток из того, что было",
    )



def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Нужно узнать, сколько всего в одинаковых группах",
        f"Число {per_group} повторяется {groups} раз, значит используем умножение",
        f"Считаем: {per_group} × {groups} = {result}",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» часто подсказывают умножение",
    )



def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: проверь, на сколько частей делят предметы",
        )

    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько получит каждый",
            "Сказано «поровну», значит делим",
            f"Считаем: {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» обычно подсказывают деление",
        )

    return join_explanation_lines(
        "Нужно узнать, сколько получит каждый",
        "Сказано «поровну», значит делим",
        f"Считаем: {total} : {groups} = {quotient}, остаток {remainder}",
        f"Ответ: каждому по {quotient}, остаток {remainder}",
        "Совет: при делении поровну остаток всегда меньше делителя",
    )



def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "В одной группе не может быть 0 предметов",
            "Ответ: запись задачи неверная",
            "Совет: проверь, сколько предметов должно быть в одной группе",
        )

    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько групп получится",
            f"Известно, что в каждой группе по {per_group}, значит число групп находим делением",
            f"Считаем: {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: если известно, сколько предметов в одной группе, число групп находим делением",
        )

    if needs_extra_group:
        return join_explanation_lines(
            "Нужно узнать, сколько коробок или мест понадобится",
            f"Считаем: {total} : {per_group} = {quotient}, остаток {remainder}",
            "Есть остаток, значит нужна ещё одна коробка",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления есть остаток, иногда нужна ещё одна коробка или место",
        )

    if explicit_remainder:
        return join_explanation_lines(
            "Нужно узнать, сколько полных групп получится",
            f"Считаем: {total} : {per_group} = {quotient}, остаток {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше делителя",
        )

    return None



def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: в вопросе «во сколько раз» делим только на ненулевое число",
        )
    if bigger % smaller != 0:
        return None
    result = bigger // smaller
    return join_explanation_lines(
        "Нужно узнать, во сколько раз одно число больше или меньше другого",
        "Для этого большее число делим на меньшее",
        f"Считаем: {bigger} : {smaller} = {result}",
        f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
        "Совет: вопрос «во сколько раз» обычно решаем делением",
    )



def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = _safe_related_value_v11(base, delta, mode)
    if result is None:
        return None
    sign = _sign_from_mode_v11(mode)
    action = _action_word_from_mode_v11(mode)
    return join_explanation_lines(
        "Нужно найти второе количество",
        f"Сказано «на {delta} {mode}», значит {action}",
        f"Считаем: {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        f"Совет: слова «на {delta} {mode}» помогают выбрать действие",
    )



def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = _safe_related_value_v11(base, delta, mode)
    if related is None:
        return None
    sign = _sign_from_mode_v11(mode)
    action = _action_word_from_mode_v11(mode)
    total = base + related
    return join_explanation_lines(
        "Сразу ответить нельзя",
        f"Сначала находим второе количество. Сказано «на {delta} {mode}», значит {action}",
        f"Считаем: {base} {sign} {delta} = {related}",
        f"Теперь находим всё вместе: {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находи неизвестную часть, потом отвечай на главный вопрос",
    )



def explain_multiplicative_quantity_word_problem_v11(base: int, factor: int, mode: str) -> Optional[str]:
    result = _safe_related_value_v11(base, factor, mode, multiplicative=True)
    if result is None:
        return None
    if mode == "больше":
        action_text = "умножаем"
        calc = f"{base} × {factor} = {result}"
    else:
        action_text = "делим"
        calc = f"{base} : {factor} = {result}"
    return join_explanation_lines(
        "Нужно найти второе количество",
        f"Сказано «в {factor} раза {mode}», значит {action_text}",
        f"Считаем: {calc}",
        f"Ответ: {result}",
        f"Совет: слова «в {factor} раза {mode}» подсказывают {'умножение' if mode == 'больше' else 'деление'}",
    )



def explain_multiplicative_total_word_problem_v11(base: int, factor: int, mode: str) -> Optional[str]:
    related = _safe_related_value_v11(base, factor, mode, multiplicative=True)
    if related is None:
        return None
    if mode == "больше":
        calc = f"{base} × {factor} = {related}"
    else:
        calc = f"{base} : {factor} = {related}"
    total = base + related
    return join_explanation_lines(
        "Сразу ответить нельзя",
        f"Сначала находим второе количество: {calc}",
        f"Теперь находим всё вместе: {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: если одно число в несколько раз больше или меньше другого, сначала найди это число",
    )



def explain_sequential_change_word_problem(start: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = _safe_related_value_v11(start, first_delta, "больше" if first_mode == "gain" else "меньше")
    if middle is None:
        return None
    result = _safe_related_value_v11(middle, second_delta, "больше" if second_mode == "gain" else "меньше")
    if result is None:
        return None

    first_sign = "+" if first_mode == "gain" else "-"
    second_sign = "+" if second_mode == "gain" else "-"
    return join_explanation_lines(
        "Сразу ответить нельзя",
        f"Сначала считаем первое изменение: {start} {first_sign} {first_delta} = {middle}",
        f"Потом считаем второе изменение: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
        "Совет: если в задаче несколько изменений, выполняй их по порядку",
    )



def explain_relation_chain_word_problem(base: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str, ask_total: bool = False) -> Optional[str]:
    middle = _safe_related_value_v11(base, first_delta, first_mode)
    if middle is None:
        return None
    result = _safe_related_value_v11(middle, second_delta, second_mode)
    if result is None:
        return None

    first_sign = _sign_from_mode_v11(first_mode)
    second_sign = _sign_from_mode_v11(second_mode)
    lines = [
        "Сразу ответить нельзя",
        f"Сначала находим второе количество: {base} {first_sign} {first_delta} = {middle}",
        f"Потом находим третье количество: {middle} {second_sign} {second_delta} = {result}",
    ]
    if ask_total:
        total = base + middle + result
        lines.append(f"Теперь находим всё вместе: {base} + {middle} + {result} = {total}")
        lines.append(f"Ответ: {total}")
    else:
        lines.append(f"Ответ: {result}")
    lines.append("Совет: если одно число зависит от другого несколько раз, находи их по очереди")
    return join_explanation_lines(*lines)



def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        "Сразу ответить нельзя",
        f"Сначала находим, сколько в одинаковых группах: {per_group} × {groups} = {grouped_total}",
        f"Потом прибавляем ещё {extra}: {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
        "Совет: если часть предметов собрана в одинаковые группы, сначала считай эту часть умножением",
    )



def explain_two_products_total_word_problem_v11(groups1: int, per1: int, groups2: int, per2: int) -> str:
    total1 = groups1 * per1
    total2 = groups2 * per2
    total = total1 + total2
    return join_explanation_lines(
        "Сразу ответить нельзя",
        f"Сначала находим первую часть: {per1} × {groups1} = {total1}",
        f"Потом находим вторую часть: {per2} × {groups2} = {total2}",
        f"Теперь складываем: {total1} + {total2} = {total}",
        f"Ответ: {total}",
        "Совет: если есть две разные группы, сначала посчитай каждую отдельно",
    )



def _question_has_plain_quantity_v11(lower: str, asks_total: bool, asks_now: bool, asks_left: bool, asks_initial: bool, asks_ratio: bool, asks_compare: bool) -> bool:
    return "сколько" in lower and not any((asks_total, asks_now, asks_left, asks_initial, asks_ratio, asks_compare))



def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    if not re.search(r"[а-я]", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 3:
        return None

    asks_total = bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower))
    asks_current = bool(re.search(r"сколько[^.?!]*\b(стало|теперь|осталось)\b", lower))
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_current, False, False, False, False)

    two_products = DOUBLE_GROUP_RE_V11.findall(lower)
    if asks_total and len(two_products) >= 2:
        (g1, p1), (g2, p2) = two_products[:2]
        return explain_two_products_total_word_problem_v11(int(g1), int(p1), int(g2), int(p2))

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if len(numbers) == 2 and len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_total:
            return explain_related_total_word_problem(numbers[0], delta, effective_mode)
        if asks_plain_quantity:
            return explain_related_quantity_word_problem(numbers[0], delta, effective_mode)

    if len(numbers) == 2 and len(multiplicative_pairs) == 1:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_total:
            return explain_multiplicative_total_word_problem_v11(numbers[0], factor, effective_mode)
        if asks_plain_quantity:
            return explain_multiplicative_quantity_word_problem_v11(numbers[0], factor, effective_mode)

    if len(numbers) == 3 and len(relation_pairs) >= 2:
        (delta1, mode1), (delta2, mode2) = relation_pairs[:2]
        chain = explain_relation_chain_word_problem(numbers[0], delta1, mode1, delta2, mode2, ask_total=asks_total)
        if chain:
            return chain

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

    if len(numbers) == 3 and asks_total and ("ещё" in lower or "еще" in lower or "отдельно" in lower) and "по" in lower:
        groups_match = re.search(r"\b(?:в|на)?\s*(\d+)\s+[а-яё]+(?:\s+[а-яё]+){0,2}\s+по\s+(\d+)\b", lower)
        if groups_match:
            groups = int(groups_match.group(1))
            per_group = int(groups_match.group(2))
            remaining = list(numbers)
            for value in (groups, per_group):
                if value in remaining:
                    remaining.remove(value)
            if len(remaining) == 1:
                return explain_groups_plus_extra_word_problem(groups, per_group, remaining[0])

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
    asks_left = bool(re.search(r"сколько[^.?!]*\bостал", lower))
    asks_now = bool(re.search(r"сколько[^.?!]*\b(стало|теперь)\b", lower))
    asks_total = bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower))
    asks_each = "кажд" in lower or "поровну" in lower
    asks_added = contains_any_fragment(lower, ("сколько добав", "сколько подар", "сколько куп", "сколько прин", "сколько полож"))
    asks_removed = contains_any_fragment(lower, ("сколько отдал", "сколько съел", "сколько убрал", "сколько забрал", "сколько потрат", "сколько продал", "сколько потер"))
    asks_groups = contains_any_fragment(lower, (
        "сколько короб", "сколько корзин", "сколько пакет", "сколько тарел", "сколько полок", "сколько ряд", "сколько групп", "сколько ящик", "сколько банок", "сколько парт", "сколько машин", "сколько мест", "сколько сеток",
    ))
    asks_remainder = "остат" in lower or "сколько остан" in lower or "полных" in lower
    needs_extra_group = contains_any_fragment(lower, ("нужно", "нужны", "понадоб", "потребует", "понадобится"))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_now, asks_left, asks_initial, asks_ratio, asks_compare)

    if asks_ratio:
        ratio = explain_ratio_word_problem(first, second)
        if ratio:
            return ratio

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if relation_pairs:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_compare:
            return explain_comparison_word_problem(first, second)
        if asks_total:
            return explain_related_total_word_problem(first, delta, effective_mode)
        if asks_plain_quantity:
            return explain_related_quantity_word_problem(first, delta, effective_mode)

    if multiplicative_pairs:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_total:
            return explain_multiplicative_total_word_problem_v11(first, factor, effective_mode)
        if asks_plain_quantity:
            return explain_multiplicative_quantity_word_problem_v11(first, factor, effective_mode)

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

    if asks_each and contains_any_fragment(lower, ("раздел", "раздал", "раздала", "раздали", "получ", "достал", "достан")):
        return explain_sharing_word_problem(first, second)

    if "по" in lower and (asks_groups or has_grouping):
        total = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        grouped = explain_group_count_word_problem(total, size, needs_extra_group=needs_extra_group, explicit_remainder=asks_remainder)
        if grouped:
            return grouped

    if "по" in lower and "сколько" in lower and not asks_groups and not asks_each:
        groups = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        return explain_multiplication_word_problem(groups, size)

    if has_loss and (asks_left or asks_now):
        explanation = explain_subtraction_word_problem(first, second)
        return explanation or None

    if (has_gain and (asks_total or asks_now)) or (asks_total and not has_loss and "по" not in lower):
        return explain_addition_word_problem(first, second)

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
            "Ищем сторону квадрата",
            "Чтобы найти сторону квадрата, периметр делим на 4",
            f"Считаем: {perimeter} : 4 = {side}",
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
            "Ищем ширину прямоугольника",
            "Сначала находим полупериметр",
            f"{perimeter} : 2 = {half}",
            f"Потом вычитаем известную длину: {half} - {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: у прямоугольника длина и ширина повторяются по два раза",
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
            "Ищем длину прямоугольника",
            "Сначала находим полупериметр",
            f"{perimeter} : 2 = {half}",
            f"Потом вычитаем известную ширину: {half} - {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: у прямоугольника длина и ширина повторяются по два раза",
        )

    if "квадрат" in lower and asks_area and asks_side and nums:
        area = nums[0]
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return join_explanation_lines(
            "Ищем сторону квадрата",
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Ищем число, которое при умножении на себя даёт {area}",
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
            "Ищем ширину прямоугольника",
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
            "Ищем длину прямоугольника",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти длину, делим площадь на ширину: {area} : {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: если известны площадь и ширина, длину находим делением",
        )

    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines(
            "Ищем периметр квадрата",
            "У квадрата 4 равные стороны",
            f"Считаем: {side} × 4 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: периметр — это сумма длин всех сторон",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
            "Ищем периметр прямоугольника",
            "Сначала складываем длину и ширину",
            f"{length} + {width} = {length + width}",
            f"Потом умножаем на 2: ({length} + {width}) × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у прямоугольника удобно сначала сложить длину и ширину, потом умножить на 2",
        )

    if "квадрат" in lower and asks_area and nums:
        side = nums[0]
        result = side * side
        return join_explanation_lines(
            "Ищем площадь квадрата",
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Считаем: {side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь показывает, сколько места занимает фигура",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Ищем площадь прямоугольника",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Считаем: {length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: чтобы найти площадь прямоугольника, умножь длину на ширину",
        )

    return None



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
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная",
            "Совет: проверь знаменатель каждой дроби",
        )

    action_symbol = "+" if operator == "+" else "-"
    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)

    if b == d:
        top_result = a + c if operator == "+" else a - c
        lines = [
            "Сначала смотрим на знаменатели",
            "Знаменатели одинаковые, значит меняем только числители",
            f"Считаем: {a}/{b} {action_symbol} {c}/{d} = {top_result}/{b}",
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
        "Сначала делаем одинаковые знаменатели",
        f"Общий знаменатель: {common}",
        f"{a}/{b} = {a_scaled}/{common}, а {c}/{d} = {c_scaled}/{common}",
        f"Теперь считаем: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top_result}/{common}",
    ]
    if format_fraction(simplified) != f"{top_result}/{common}":
        lines.append(f"Сокращаем: {top_result}/{common} = {format_fraction(simplified)}")
    lines.extend([
        f"Ответ: {format_fraction(result)}",
        "Совет: если знаменатели разные, сначала приведи дроби к общему знаменателю",
    ])
    return join_explanation_lines(*lines)



def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left < 10 and right < 10 and total >= 10:
        need = 10 - left
        if 0 < need < right:
            rest = right - need
            return join_explanation_lines(
                "Ищем сумму",
                f"Сначала дополняем {left} до 10",
                f"Разбиваем {right} на {need} и {rest}",
                f"{left} + {need} = 10, потом 10 + {rest} = {total}",
                f"Ответ: {total}",
                "Совет: если удобно, сначала дополняй число до 10",
            )

    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Ищем сумму",
            f"Разбиваем числа на десятки и единицы: {left} = {left_tens} + {left_units}, {right} = {right_tens} + {right_units}",
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}",
            f"Теперь складываем части: {left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
            "Совет: большие числа удобно складывать по разрядам",
        )

    return join_explanation_lines(
        "Ищем сумму",
        f"Считаем: {left} + {right} = {total}",
        f"Ответ: {total}",
        "Совет: если нужно узнать, сколько всего, складывай",
    )



def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
            "Сначала сравниваем числа",
            f"{left} меньше {right}, поэтому ответ будет отрицательным",
            f"Считаем: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: перед вычитанием полезно сравнить числа",
        )

    if left < 20 and right < 10 and left % 10 < right:
        first_part = left % 10
        second_part = right - first_part
        return join_explanation_lines(
            "Ищем разность",
            f"Число {right} удобно разложить на {first_part} и {second_part}",
            f"Сначала {left} - {first_part} = {left - first_part}",
            f"Потом {left - first_part} - {second_part} = {result}",
            f"Ответ: {result}",
            "Совет: если не хватает единиц, вычитай число по частям",
        )

    if right >= 10:
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            "Ищем разность",
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}",
            f"Потом вычитаем единицы: {middle} - {units} = {result}",
            f"Ответ: {result}",
            "Совет: удобно сначала работать с десятками, потом с единицами",
        )

    return join_explanation_lines(
        "Ищем разность",
        f"Считаем: {left} - {right} = {result}",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько осталось, вычитай",
    )



def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)

    if big < 10 and small < 10:
        repeated = " + ".join([str(big)] * small)
        return join_explanation_lines(
            "Ищем произведение",
            "Умножение — это сумма одинаковых слагаемых",
            f"{big} × {small} = {repeated} = {result}",
            f"Ответ: {result}",
            "Совет: умножение показывает, сколько одинаковых групп мы взяли",
        )

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
            "Совет: двузначное число удобно умножать по частям",
        )

    return join_explanation_lines(
        "Ищем произведение",
        f"Считаем: {left} × {right} = {result}",
        f"Ответ: {result}",
        "Совет: умножение — это быстрый способ сложить одинаковые числа",
    )



def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала смотри на делитель",
        )

    quotient, remainder = divmod(left, right)
    if left < 100 and right < 10:
        if remainder == 0:
            return join_explanation_lines(
                "Ищем частное",
                "Деление — действие, обратное умножению",
                f"Ищем число, которое при умножении на {right} даёт {left}",
                f"Это {quotient}, потому что {quotient} × {right} = {left}",
                f"Ответ: {quotient}",
                "Совет: при делении полезно вспоминать таблицу умножения",
            )
        return join_explanation_lines(
            "Ищем, сколько полных раз делитель помещается в делимом",
            f"{quotient} × {right} = {quotient * right}",
            f"После вычитания остаётся {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше делителя",
        )

    model = _build_long_division_steps_v9(left, right)
    answer_text = str(quotient) if remainder == 0 else f"{quotient}, остаток {remainder}"
    return join_explanation_lines(
        "Ищем частное",
        "Будем делить по шагам: берём неполное делимое, подбираем цифру частного, умножаем, вычитаем и сносим следующую цифру",
        f"Ответ: {answer_text}",
        "Совет: в делении столбиком повторяй шаги: взял, подобрал, умножил, вычел",
    )



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
        (r"^x\+(\d+)$", "unknown_addend"),
        (r"^(\d+)\+x$", "unknown_addend"),
        (r"^x-(\d+)$", "unknown_minuend"),
        (r"^(\d+)-x$", "unknown_subtrahend"),
        (r"^x\*(\d+)$", "unknown_factor"),
        (r"^(\d+)\*x$", "unknown_factor"),
        (r"^x/(\d+)$", "unknown_dividend"),
        (r"^(\d+)/x$", "unknown_divisor"),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue
        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind == "unknown_addend":
            answer = rhs_value - number
            if lhs.startswith("x"):
                template = f"x + {number_text}"
            else:
                template = f"{number_text} + x"
            return join_explanation_lines(
                "Ищем неизвестное слагаемое",
                "Чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое",
                f"x = {rhs_text} - {number_text} = {format_fraction(answer)}",
                format_equation_check(template, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала назови неизвестный компонент уравнения",
            )

        if kind == "unknown_minuend":
            answer = rhs_value + number
            return join_explanation_lines(
                "Ищем неизвестное уменьшаемое",
                "Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое",
                f"x = {rhs_text} + {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x - {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала назови неизвестный компонент уравнения",
            )

        if kind == "unknown_subtrahend":
            answer = number - rhs_value
            return join_explanation_lines(
                "Ищем неизвестное вычитаемое",
                "Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность",
                f"x = {number_text} - {rhs_text} = {format_fraction(answer)}",
                format_equation_check(f"{number_text} - x", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала назови неизвестный компонент уравнения",
            )

        if kind == "unknown_factor":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Ищем неизвестный множитель",
                        "При умножении на 0 всегда получается 0",
                        "Ответ: подходит любое число",
                        "Совет: умножение на ноль всегда даёт ноль",
                    )
                return join_explanation_lines(
                    "Ищем неизвестный множитель",
                    "0 не может дать ненулевой результат",
                    "Ответ: решения нет",
                    "Совет: проверь запись уравнения",
                )
            answer = rhs_value / number
            template = f"x × {number_text}" if lhs.startswith("x") else f"{number_text} × x"
            return join_explanation_lines(
                "Ищем неизвестный множитель",
                "Чтобы найти неизвестный множитель, произведение делим на известный множитель",
                f"x = {rhs_text} : {number_text} = {format_fraction(answer)}",
                format_equation_check(template, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала назови неизвестный компонент уравнения",
            )

        if kind == "unknown_dividend":
            if number == 0:
                return join_explanation_lines(
                    "Ищем неизвестное делимое",
                    "На ноль делить нельзя",
                    "Ответ: решения нет",
                    "Совет: проверь делитель",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Ищем неизвестное делимое",
                "Чтобы найти неизвестное делимое, делитель умножаем на частное",
                f"x = {rhs_text} × {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x : {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала назови неизвестный компонент уравнения",
            )

        if kind == "unknown_divisor":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Ищем неизвестный делитель",
                        "0, делённое на любое ненулевое число, даёт 0",
                        "Ответ: подходит любое число, кроме 0",
                        "Совет: в делителе ноль быть не может",
                    )
                return join_explanation_lines(
                    "Ищем неизвестный делитель",
                    "0 не может дать ненулевое частное",
                    "Ответ: решения нет",
                    "Совет: проверь делимое и частное",
                )
            if rhs_value == 0:
                return join_explanation_lines(
                    "Ищем неизвестный делитель",
                    "Ненулевое число при делении не может дать 0",
                    "Ответ: решения нет",
                    "Совет: проверь запись уравнения",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "Ищем неизвестный делитель",
                "Чтобы найти неизвестный делитель, делимое делим на частное",
                f"x = {number_text} : {rhs_text} = {format_fraction(answer)}",
                format_equation_check(f"{number_text} : x", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала назови неизвестный компонент уравнения",
            )

    return None


SYSTEM_PROMPT_V11 = """
Ты — спокойный и точный учитель математики для детей 7–10 лет.
Главная цель — не просто сообщить ответ, а научить ходу решения.

Пиши только на русском языке.
Пиши без markdown, списков, нумерации и смайликов.
Не используй похвалу и лишние вступления.
Каждая строка — одна полезная мысль.
Не повторяй одну и ту же мысль разными словами.

Общий порядок объяснения такой:
сначала скажи, что нужно найти;
потом коротко скажи, почему подходит это действие или правило;
потом выполни действие или шаги по порядку;
только в конце дай строку "Ответ: ...";
последняя строка — "Совет: ...".

Для составной задачи можно писать "Сразу ответить нельзя", если это правда.
После этого пиши: "Сначала узнаем...", "Потом узнаем...".

Для текстовой задачи опирайся на смысл слов:
«всего», «вместе» — часто сложение;
«осталось» — часто вычитание;
«на ... больше» — прибавляем;
«на ... меньше» — вычитаем;
«в ... раза больше» — умножаем;
«в ... раза меньше» — делим;
«поровну», «каждый» — делим.
Если задача в косвенной форме, сначала переведи её в прямой смысл.

Для уравнения сначала назови неизвестный компонент:
неизвестное слагаемое, уменьшаемое, вычитаемое, множитель, делимое или делитель.
Потом назови правило и только затем считай.
Проверка нужна только у уравнений.

Для письменного деления объясняй так:
берём неполное делимое;
подбираем цифру частного;
умножаем;
вычитаем;
сносим следующую цифру.
Не пиши готовый ответ в первой строке.
Не пиши строку "Проверка:" для обычного примера.

Для геометрии сначала назови, что ищем и какое правило используем.
Для дробей сначала смотри на знаменатели.

Если запись непонятная или это не задача по математике, спокойно попроси записать пример понятнее.
""".strip()


async def build_explanation(user_text: str) -> dict:
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )

    kind = infer_task_kind(user_text)

    if local_explanation:
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    extra_instruction = ""
    if kind == "word":
        extra_instruction = (
            "Это текстовая задача. Сначала скажи, что нужно найти. "
            "Потом объясни, почему подходит это действие. "
            "Если задача составная, скажи: «Сразу ответить нельзя», затем «Сначала узнаем...», «Потом узнаем...».\n\n"
        )
    elif kind == "geometry":
        extra_instruction = (
            "Это задача по геометрии. Сначала назови правило, потом подставь числа и выполни вычисление.\n\n"
        )
    elif kind == "expression":
        extra_instruction = (
            "Это обычный пример или выражение. Не пиши готовый ответ в первой строке. "
            "Если это деление, объясняй ход последовательно. Не добавляй строку «Проверка:».\n\n"
        )
    elif kind == "fraction":
        extra_instruction = (
            "Это задача с дробями. Сначала скажи, одинаковые ли знаменатели. Потом выполни вычисление.\n\n"
        )
    elif kind == "equation":
        extra_instruction = (
            "Это уравнение. Сначала назови неизвестный компонент, потом правило, потом вычисление и короткую проверку.\n\n"
        )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_V11},
            {
                "role": "user",
                "content": (
                    "Объясни решение так, чтобы ребёнок мог слушать текст и идти по нему глазами строка за строкой. "
                    "Ответ дай строго в заданной структуре.\n\n"
                    f"{extra_instruction}{user_text}"
                ),
            },
        ],
        "max_tokens": 650,
        "temperature": 0.05,
    }

    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result

    shaped = shape_explanation(llm_result["result"], kind)
    return {"result": shaped, "source": "llm", "validated": False}


# --- V11.1 targeted fixes ---
TOTAL_CONTEXT_RE_V11 = re.compile(r"сколько[^.?!]*\b(?:всего|вместе|на\s+(?:двух|трех|трёх|четырех|четырёх|пяти|шести|семи|восьми|девяти|десяти|\d+)|в\s+(?:двух|трех|трёх|четырех|четырёх|пяти|шести|семи|восьми|девяти|десяти|\d+))\b", re.IGNORECASE)
ONE_GROUP_RE_V11 = re.compile(r"(?:в|на)\s+(?:одной|одном|одну|1)\s+[а-яё]+(?:\s+[а-яё]+){0,3}\s+(\d+)\s+[а-яё]+", re.IGNORECASE)
QUESTION_GROUP_RE_V11 = re.compile(r"сколько[^.?!]*\b(?:в|на)\s+(\d+)\s+[а-яё]+", re.IGNORECASE)


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
    asks_left = bool(re.search(r"сколько[^.?!]*\bостал", lower))
    asks_now = bool(re.search(r"сколько[^.?!]*\b(стало|теперь)\b", lower))
    asks_total = bool(TOTAL_CONTEXT_RE_V11.search(lower))
    asks_each = "поровну" in lower or bool(re.search(r"сколько[^.?!]*кажд", lower))
    asks_added = contains_any_fragment(lower, ("сколько добав", "сколько подар", "сколько куп", "сколько прин", "сколько полож"))
    asks_removed = contains_any_fragment(lower, ("сколько отдал", "сколько съел", "сколько убрал", "сколько забрал", "сколько потрат", "сколько продал", "сколько потер"))
    asks_groups = contains_any_fragment(lower, (
        "сколько короб", "сколько корзин", "сколько пакет", "сколько тарел", "сколько полок", "сколько ряд", "сколько групп", "сколько ящик", "сколько банок", "сколько парт", "сколько машин", "сколько мест", "сколько сеток",
    ))
    asks_remainder = "остат" in lower or "сколько остан" in lower or "полных" in lower
    needs_extra_group = contains_any_fragment(lower, ("нужно", "нужны", "понадоб", "потребует", "понадобится"))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_now, asks_left, asks_initial, asks_ratio, asks_compare)

    if asks_ratio:
        ratio = explain_ratio_word_problem(first, second)
        if ratio:
            return ratio

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if relation_pairs:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_compare:
            return explain_comparison_word_problem(first, second)
        if asks_total:
            return explain_related_total_word_problem(first, delta, effective_mode)
        if asks_plain_quantity:
            return explain_related_quantity_word_problem(first, delta, effective_mode)

    if multiplicative_pairs:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_total:
            return explain_multiplicative_total_word_problem_v11(first, factor, effective_mode)
        if asks_plain_quantity:
            return explain_multiplicative_quantity_word_problem_v11(first, factor, effective_mode)

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

    if asks_each and contains_any_fragment(lower, ("раздел", "раздал", "раздала", "раздали", "получ", "достал", "достан")):
        return explain_sharing_word_problem(first, second)

    if "по" in lower and (asks_groups or has_grouping):
        total = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        grouped = explain_group_count_word_problem(total, size, needs_extra_group=needs_extra_group, explicit_remainder=asks_remainder)
        if grouped:
            return grouped

    if "по" in lower and "сколько" in lower and not asks_groups and not asks_each:
        groups = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        return explain_multiplication_word_problem(groups, size)

    one_group_match = ONE_GROUP_RE_V11.search(lower)
    question_groups_match = QUESTION_GROUP_RE_V11.search(lower)
    if asks_plain_quantity and one_group_match and question_groups_match:
        per_item = int(one_group_match.group(1))
        group_count = int(question_groups_match.group(1))
        return explain_multiplication_word_problem(group_count, per_item)

    if has_loss and (asks_left or asks_now):
        explanation = explain_subtraction_word_problem(first, second)
        return explanation or None

    if (has_gain and (asks_total or asks_now)) or (asks_total and not has_loss and "по" not in lower):
        return explain_addition_word_problem(first, second)

    return None



def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    normalized_for_numbers = re.sub(r"\b(мм|см|дм|м|км)(?:2|²)\b", r"\1", lower)
    nums = extract_ordered_numbers(normalized_for_numbers)
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
            "Ищем сторону квадрата",
            "Чтобы найти сторону квадрата, периметр делим на 4",
            f"Считаем: {perimeter} : 4 = {side}",
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
            "Ищем ширину прямоугольника",
            "Сначала находим полупериметр",
            f"{perimeter} : 2 = {half}",
            f"Потом вычитаем известную длину: {half} - {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: у прямоугольника длина и ширина повторяются по два раза",
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
            "Ищем длину прямоугольника",
            "Сначала находим полупериметр",
            f"{perimeter} : 2 = {half}",
            f"Потом вычитаем известную ширину: {half} - {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: у прямоугольника длина и ширина повторяются по два раза",
        )

    if "квадрат" in lower and asks_area and asks_side and nums:
        area = nums[0]
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return join_explanation_lines(
            "Ищем сторону квадрата",
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Ищем число, которое при умножении на себя даёт {area}",
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
            "Ищем ширину прямоугольника",
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
            "Ищем длину прямоугольника",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти длину, делим площадь на ширину: {area} : {width} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: если известны площадь и ширина, длину находим делением",
        )

    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return join_explanation_lines(
            "Ищем периметр квадрата",
            "У квадрата 4 равные стороны",
            f"Считаем: {side} × 4 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: периметр — это сумма длин всех сторон",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
            "Ищем периметр прямоугольника",
            "Сначала складываем длину и ширину",
            f"{length} + {width} = {length + width}",
            f"Потом умножаем на 2: ({length} + {width}) × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у прямоугольника удобно сначала сложить длину и ширину, потом умножить на 2",
        )

    if "квадрат" in lower and asks_area and nums:
        side = nums[0]
        result = side * side
        return join_explanation_lines(
            "Ищем площадь квадрата",
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Считаем: {side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь показывает, сколько места занимает фигура",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Ищем площадь прямоугольника",
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Считаем: {length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: чтобы найти площадь прямоугольника, умножь длину на ширину",
        )

    return None


# --- V11.2 word-task ordering fix ---
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
    asks_left = bool(re.search(r"сколько[^.?!]*\bостал", lower))
    asks_now = bool(re.search(r"сколько[^.?!]*\b(стало|теперь)\b", lower))
    asks_total = bool(TOTAL_CONTEXT_RE_V11.search(lower))
    asks_each = "поровну" in lower or bool(re.search(r"сколько[^.?!]*кажд", lower))
    asks_added = contains_any_fragment(lower, ("сколько добав", "сколько подар", "сколько куп", "сколько прин", "сколько полож"))
    asks_removed = contains_any_fragment(lower, ("сколько отдал", "сколько съел", "сколько убрал", "сколько забрал", "сколько потрат", "сколько продал", "сколько потер"))
    asks_groups = contains_any_fragment(lower, (
        "сколько короб", "сколько корзин", "сколько пакет", "сколько тарел", "сколько полок", "сколько ряд", "сколько групп", "сколько ящик", "сколько банок", "сколько парт", "сколько машин", "сколько мест", "сколько сеток",
    ))
    asks_remainder = "остат" in lower or "сколько остан" in lower or "полных" in lower
    needs_extra_group = contains_any_fragment(lower, ("нужно", "нужны", "понадоб", "потребует", "понадобится"))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_now, asks_left, asks_initial, asks_ratio, asks_compare)

    if asks_ratio:
        ratio = explain_ratio_word_problem(first, second)
        if ratio:
            return ratio

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if relation_pairs:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_compare:
            return explain_comparison_word_problem(first, second)
        if asks_total:
            return explain_related_total_word_problem(first, delta, effective_mode)
        if asks_plain_quantity:
            return explain_related_quantity_word_problem(first, delta, effective_mode)

    if multiplicative_pairs:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        if asks_total:
            return explain_multiplicative_total_word_problem_v11(first, factor, effective_mode)
        if asks_plain_quantity:
            return explain_multiplicative_quantity_word_problem_v11(first, factor, effective_mode)

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

    if asks_each and contains_any_fragment(lower, ("раздел", "раздал", "раздала", "раздали", "получ", "достал", "достан")):
        return explain_sharing_word_problem(first, second)

    if "по" in lower and (asks_groups or has_grouping):
        total = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        grouped = explain_group_count_word_problem(total, size, needs_extra_group=needs_extra_group, explicit_remainder=asks_remainder)
        if grouped:
            return grouped

    if "по" in lower and "сколько" in lower and not asks_groups and not asks_each:
        groups = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        return explain_multiplication_word_problem(groups, size)

    one_group_match = ONE_GROUP_RE_V11.search(lower)
    question_groups_match = QUESTION_GROUP_RE_V11.search(lower)
    if one_group_match and question_groups_match:
        per_item = int(one_group_match.group(1))
        group_count = int(question_groups_match.group(1))
        return explain_multiplication_word_problem(group_count, per_item)

    if has_loss and (asks_left or asks_now):
        explanation = explain_subtraction_word_problem(first, second)
        return explanation or None

    if (has_gain and (asks_total or asks_now)) or (asks_total and not has_loss and "по" not in lower):
        return explain_addition_word_problem(first, second)

    return None


# --- V11.3 wording polish ---
def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    times_word = plural_form(groups, 'раз', 'раза', 'раз')
    return join_explanation_lines(
        "Нужно узнать, сколько всего в одинаковых группах",
        f"Число {per_group} повторяется {groups} {times_word}, значит используем умножение",
        f"Считаем: {per_group} × {groups} = {result}",
        f"Ответ: {result}",
        "Совет: если одно и то же число повторяется несколько раз, удобно использовать умножение",
    )

# --- V12 book-based explanation methodology patch ---

def _v12_place_values(number: int):
    text = str(abs(int(number)))
    values = []
    for index, char in enumerate(text):
        digit = int(char)
        power = len(text) - index - 1
        value = digit * (10 ** power)
        if value:
            values.append(value)
    return values or [0]


def _v12_join_values(values):
    return " + ".join(str(value) for value in values if value) or "0"


def _v12_trailing_zero_count(number: int) -> int:
    text = str(abs(int(number)))
    return len(text) - len(text.rstrip("0"))


def _v12_prepend_explanation(text: Optional[str], *prefix_lines: str) -> Optional[str]:
    if not text:
        return text
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    return join_explanation_lines(*prefix_lines, *lines)


def _v12_additive_indirect_intro(delta: int, mode: str) -> str:
    opposite = _invert_more_less_v11(mode)
    return f"Сначала переведём условие в прямой смысл: если одно количество на {delta} {mode}, то другое на {delta} {opposite}."


def _v12_multiplicative_indirect_intro(factor: int, mode: str) -> str:
    opposite = _invert_more_less_v11(mode)
    return f"Сначала переведём условие в прямой смысл: если одно количество в {factor} раза {mode}, то другое в {factor} раза {opposite}."


def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left < 10 and right < 10 and total >= 10:
        need = 10 - left
        if 0 < need < right:
            rest = right - need
            return join_explanation_lines(
                "Нужно найти сумму.",
                f"Разложим {right} на {need} и {rest}.",
                f"Сначала {left} + {need} = 10.",
                f"Потом 10 + {rest} = {total}.",
                f"Ответ: {total}.",
                "Совет: если удобно, сначала дополняй число до 10.",
            )

    if left >= 10 or right >= 10:
        left_values = _v12_place_values(left)
        right_values = _v12_place_values(right)
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Нужно найти сумму.",
            "Представляем числа в виде разрядных слагаемых.",
            f"{left} = {_v12_join_values(left_values)}, {right} = {_v12_join_values(right_values)}.",
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}.",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}.",
            f"Теперь складываем полученные суммы: {left_tens + right_tens} + {left_units + right_units} = {total}.",
            f"Ответ: {total}.",
            "Совет: большие числа удобно складывать по разрядам.",
        )

    return join_explanation_lines(
        "Нужно найти сумму.",
        f"Если первое число {left}, а второе {right}, то {left} + {right} = {total}.",
        f"Ответ: {total}.",
        "Совет: когда нужно узнать, сколько всего, складывай.",
    )


def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
            "Нужно найти разность.",
            f"{left} меньше {right}, поэтому ответ будет отрицательным.",
            f"Считаем: {left} - {right} = {result}.",
            f"Ответ: {result}.",
            "Совет: перед вычитанием полезно сравнить числа.",
        )

    if left < 20 and right < 10 and left % 10 < right:
        first_part = left % 10
        second_part = right - first_part
        return join_explanation_lines(
            "Нужно найти разность.",
            f"Разложим {right} на {first_part} и {second_part}.",
            f"Сначала {left} - {first_part} = {left - first_part}.",
            f"Потом {left - first_part} - {second_part} = {result}.",
            f"Ответ: {result}.",
            "Совет: если единиц не хватает, вычитай число по частям.",
        )

    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        if left < 100 and right < 100:
            if left_units < right_units:
                adjusted_tens = left_tens - 10
                adjusted_units = left_units + 10
                tens_result = adjusted_tens - right_tens
                units_result = adjusted_units - right_units
                return join_explanation_lines(
                    "Нужно найти разность.",
                    "Представляем числа в виде удобных слагаемых.",
                    f"{left} = {adjusted_tens} + {adjusted_units}, {right} = {right_tens} + {right_units}.",
                    f"Вычитаем десятки: {adjusted_tens} - {right_tens} = {tens_result}.",
                    f"Вычитаем единицы: {adjusted_units} - {right_units} = {units_result}.",
                    f"Теперь складываем разности: {tens_result} + {units_result} = {result}.",
                    f"Ответ: {result}.",
                    "Совет: если единиц не хватает, одну десятку превращаем в 10 единиц.",
                )
            tens_result = left_tens - right_tens
            units_result = left_units - right_units
            return join_explanation_lines(
                "Нужно найти разность.",
                "Представляем числа в виде десятков и единиц.",
                f"{left} = {left_tens} + {left_units}, {right} = {right_tens} + {right_units}.",
                f"Вычитаем десятки: {left_tens} - {right_tens} = {tens_result}.",
                f"Вычитаем единицы: {left_units} - {right_units} = {units_result}.",
                f"Теперь складываем разности: {tens_result} + {units_result} = {result}.",
                f"Ответ: {result}.",
                "Совет: удобно отдельно работать с десятками и единицами.",
            )

        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            "Нужно найти разность.",
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}.",
            f"Потом вычитаем единицы: {middle} - {units} = {result}.",
            f"Ответ: {result}.",
            "Совет: сначала удобно вычитать десятки, потом единицы.",
        )

    return join_explanation_lines(
        "Нужно найти разность.",
        f"Если было {left}, а убрали {right}, то осталось {left} - {right} = {result}.",
        f"Ответ: {result}.",
        "Совет: когда нужно узнать, сколько осталось, вычитай.",
    )


def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)

    if big < 10 and small < 10:
        repeated = " + ".join([str(big)] * small)
        return join_explanation_lines(
            "Нужно найти произведение.",
            "Умножение можно понимать как сумму одинаковых слагаемых.",
            f"{big} × {small} = {repeated} = {result}.",
            f"Ответ: {result}.",
            "Совет: вспоминай таблицу умножения и смысл одинаковых групп.",
        )

    rounded = big if big % 10 == 0 and small < 10 else small if small % 10 == 0 and big < 10 else None
    other = small if rounded == big else big if rounded == small else None
    if rounded is not None and other is not None:
        zero_power = 10 ** _v12_trailing_zero_count(rounded)
        base = rounded // zero_power
        return join_explanation_lines(
            "Нужно найти произведение.",
            f"Представляем {rounded} как {base} × {zero_power}.",
            f"Сначала {base} × {other} = {base * other}.",
            f"Потом {base * other} × {zero_power} = {result}.",
            f"Ответ: {result}.",
            "Совет: круглое число удобно разложить на число и нули справа.",
        )

    if big >= 10 and small <= 10:
        parts = _v12_place_values(big)
        partial_products = [part * small for part in parts]
        partial_calc = ", ".join(f"{part} × {small} = {part * small}" for part in parts)
        return join_explanation_lines(
            "Нужно найти произведение.",
            f"Разложим {big} на разрядные слагаемые: {big} = {_v12_join_values(parts)}.",
            partial_calc + ".",
            f"Складываем результаты: {' + '.join(str(value) for value in partial_products)} = {result}.",
            f"Ответ: {result}.",
            "Совет: многозначное число удобно умножать по частям.",
        )

    return join_explanation_lines(
        "Нужно найти произведение.",
        f"Считаем: {left} × {right} = {result}.",
        f"Ответ: {result}.",
        "Совет: умножение — это быстрый способ сложить одинаковые числа.",
    )


def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя.",
            "Ответ: деление на ноль невозможно.",
            "Совет: сначала смотри на делитель.",
        )

    quotient, remainder = divmod(left, right)

    common_zeroes = min(_v12_trailing_zero_count(left), _v12_trailing_zero_count(right))
    if common_zeroes > 0 and remainder == 0:
        reduced_left = left // (10 ** common_zeroes)
        reduced_right = right // (10 ** common_zeroes)
        return join_explanation_lines(
            "Нужно найти частное.",
            f"У круглых чисел сокращаем по {common_zeroes} нулю справа: {left} : {right} = {reduced_left} : {reduced_right}.",
            f"Теперь делим: {reduced_left} : {reduced_right} = {quotient}.",
            f"Ответ: {quotient}.",
            "Совет: у круглых чисел сначала удобно сократить одинаковые нули справа.",
        )

    if remainder == 0 and left < 1000 and right < 100:
        next_try = right * (quotient + 1)
        detail = (
            f"Берём {quotient}, потому что {right} × {quotient} = {left}."
            if next_try <= left
            else f"Берём {quotient}, потому что {right} × {quotient} = {left}, а {right} × {quotient + 1} = {next_try}, это уже больше."
        )
        return join_explanation_lines(
            "Нужно найти частное.",
            f"Подбираем число, которое при умножении на {right} даёт {left}.",
            detail,
            f"Ответ: {quotient}.",
            "Совет: при делении полезно проверять себя таблицей умножения.",
        )

    if left < 1000 and right < 100:
        fitted = quotient * right
        return join_explanation_lines(
            "Нужно найти, сколько полных раз делитель помещается в делимом.",
            f"Самое большое подходящее число — {fitted}, потому что {quotient} × {right} = {fitted}.",
            f"Находим остаток: {left} - {fitted} = {remainder}.",
            f"Ответ: {quotient}, остаток {remainder}.",
            "Совет: остаток всегда должен быть меньше делителя.",
        )

    answer_text = str(quotient) if remainder == 0 else f"{quotient}, остаток {remainder}"
    return join_explanation_lines(
        "Нужно найти частное.",
        "Сначала выделяем первое неполное делимое.",
        "Потом повторяем шаги: делим, умножаем, вычитаем и сносим следующую цифру.",
        f"Ответ: {answer_text}.",
        "Совет: в делении столбиком повторяй шаги: неполное делимое, цифра частного, умножение, вычитание.",
    )


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Нужно узнать, сколько всего.",
        f"Если первое количество {first}, а второе {second}, то всего {first} + {second} = {result}.",
        f"Ответ: {result}.",
        "Совет: слова «всего» и «вместе» обычно подсказывают сложение.",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько осталось.",
        f"Если было {first}, а убрали {second}, то осталось {first} - {second} = {result}.",
        f"Ответ: {result}.",
        "Совет: слова «осталось», «убрали», «отдали» обычно подсказывают вычитание.",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, на сколько одно число больше или меньше другого.",
        f"Если большее число {bigger}, а меньшее {smaller}, то разница {bigger} - {smaller} = {result}.",
        f"Ответ: {result}.",
        "Совет: вопрос «на сколько больше или меньше» решаем вычитанием.",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала.",
        f"Если после того, как убрали {removed}, осталось {remaining}, то сначала было {remaining} + {removed} = {result}.",
        f"Ответ: {result}.",
        "Совет: если часть убрали, а спрашивают, сколько было, складываем остаток и убранную часть.",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала.",
        f"Если после того, как добавили {added}, стало {final_total}, то сначала было {final_total} - {added} = {result}.",
        f"Ответ: {result}.",
        "Совет: если число увеличили, а спрашивают начальное, вычитай прибавленное.",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько добавили.",
        f"Если было {smaller}, а стало {bigger}, то добавили {bigger} - {smaller} = {result}.",
        f"Ответ: {result}.",
        "Совет: чтобы узнать, сколько добавили, сравни число было и число стало.",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько убрали.",
        f"Если было {bigger}, а осталось {smaller}, то убрали {bigger} - {smaller} = {result}.",
        f"Ответ: {result}.",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычти остаток.",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Нужно узнать, сколько всего.",
        f"Если по {per_group} взяли {groups} {plural_form(groups, 'раз', 'раза', 'раз')}, то всего {per_group} × {groups} = {result}.",
        f"Ответ: {result}.",
        "Совет: когда одно и то же число повторяется несколько раз, удобно умножать.",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "На ноль делить нельзя.",
            "Ответ: деление на ноль невозможно.",
            "Совет: проверь, на сколько частей делят предметы.",
        )

    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько получит каждый.",
            f"Если {total} предметов разделить поровну на {groups}, то каждый получит {total} : {groups} = {quotient}.",
            f"Ответ: {quotient}.",
            "Совет: слова «поровну» и «каждый» обычно подсказывают деление.",
        )

    return join_explanation_lines(
        "Нужно узнать, сколько получит каждый.",
        f"Делим поровну: {total} : {groups} = {quotient}, остаток {remainder}.",
        f"Ответ: каждому по {quotient}, остаток {remainder}.",
        "Совет: при делении поровну остаток всегда меньше делителя.",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines(
            "В одной группе не может быть 0 предметов.",
            "Ответ: запись задачи неверная.",
            "Совет: проверь, сколько предметов должно быть в одной группе.",
        )

    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько групп получится.",
            f"Если всего {total} предметов и в каждой группе по {per_group}, то групп {total} : {per_group} = {quotient}.",
            f"Ответ: {quotient}.",
            "Совет: если известно, сколько предметов в одной группе, число групп находим делением.",
        )

    if needs_extra_group:
        return join_explanation_lines(
            "Нужно узнать, сколько мест понадобится.",
            f"Полных групп получится {total} : {per_group} = {quotient}, остаток {remainder}.",
            "Есть остаток, значит нужна ещё одна группа или коробка.",
            f"Ответ: {quotient + 1}.",
            "Совет: если после деления остаётся часть предметов, иногда нужна ещё одна коробка или место.",
        )

    if explicit_remainder:
        return join_explanation_lines(
            "Нужно узнать, сколько полных групп получится.",
            f"Делим: {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Ответ: {quotient}, остаток {remainder}.",
            "Совет: остаток всегда должен быть меньше делителя.",
        )

    return None


def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines(
            "На ноль делить нельзя.",
            "Ответ: деление на ноль невозможно.",
            "Совет: в вопросе «во сколько раз» делим только на ненулевое число.",
        )
    if bigger % smaller != 0:
        return None
    result = bigger // smaller
    return join_explanation_lines(
        "Нужно узнать, во сколько раз одно число больше или меньше другого.",
        f"Если большее число {bigger}, а меньшее {smaller}, то {bigger} : {smaller} = {result}.",
        f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}.",
        "Совет: вопрос «во сколько раз» обычно решаем делением.",
    )


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = _safe_related_value_v11(base, delta, mode)
    if result is None:
        return None
    sign = _sign_from_mode_v11(mode)
    action = _action_word_from_mode_v11(mode)
    return join_explanation_lines(
        "Нужно узнать второе количество.",
        f"Сказано «на {delta} {mode}». Чтобы стало {mode}, {action}.",
        f"Если первое количество {base}, то второе {base} {sign} {delta} = {result}.",
        f"Ответ: {result}.",
        f"Совет: слова «на {delta} {mode}» помогают выбрать действие.",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = _safe_related_value_v11(base, delta, mode)
    if related is None:
        return None
    sign = _sign_from_mode_v11(mode)
    action = _action_word_from_mode_v11(mode)
    total = base + related
    return join_explanation_lines(
        "Сразу ответить нельзя.",
        "Сначала узнаем второе количество.",
        f"Если первое количество {base}, а второе на {delta} {mode}, то второе равно {base} {sign} {delta} = {related}.",
        "Потом узнаем, сколько всего.",
        f"Если первое количество {base}, а второе {related}, то всего {base} + {related} = {total}.",
        f"Ответ: {total}.",
        f"Совет: в составной задаче сначала находи неизвестную часть, потом отвечай на главный вопрос.",
    )


def explain_multiplicative_quantity_word_problem_v11(base: int, factor: int, mode: str) -> Optional[str]:
    result = _safe_related_value_v11(base, factor, mode, multiplicative=True)
    if result is None:
        return None
    action_text = "умножаем" if mode == "больше" else "делим"
    calc = f"{base} × {factor} = {result}" if mode == "больше" else f"{base} : {factor} = {result}"
    return join_explanation_lines(
        "Нужно узнать второе количество.",
        f"Сказано «в {factor} раза {mode}». Значит {action_text}.",
        f"Если первое количество {base}, то второе {calc}.",
        f"Ответ: {result}.",
        f"Совет: слова «в {factor} раза {mode}» подсказывают {'умножение' if mode == 'больше' else 'деление'}.",
    )


def explain_multiplicative_total_word_problem_v11(base: int, factor: int, mode: str) -> Optional[str]:
    related = _safe_related_value_v11(base, factor, mode, multiplicative=True)
    if related is None:
        return None
    calc = f"{base} × {factor} = {related}" if mode == "больше" else f"{base} : {factor} = {related}"
    total = base + related
    return join_explanation_lines(
        "Сразу ответить нельзя.",
        "Сначала узнаем второе количество.",
        f"Если первое количество {base}, а второе в {factor} раза {mode}, то {calc}.",
        "Потом узнаем, сколько всего.",
        f"Если первое количество {base}, а второе {related}, то всего {base} + {related} = {total}.",
        f"Ответ: {total}.",
        "Совет: если одно число в несколько раз больше или меньше другого, сначала найди это число.",
    )


def explain_sequential_change_word_problem(start: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = _safe_related_value_v11(start, first_delta, "больше" if first_mode == "gain" else "меньше")
    if middle is None:
        return None
    result = _safe_related_value_v11(middle, second_delta, "больше" if second_mode == "gain" else "меньше")
    if result is None:
        return None

    first_sign = "+" if first_mode == "gain" else "-"
    second_sign = "+" if second_mode == "gain" else "-"
    return join_explanation_lines(
        "Сразу ответить нельзя.",
        "Сначала выполняем первое изменение.",
        f"Если было {start}, то после первого шага получаем {start} {first_sign} {first_delta} = {middle}.",
        "Потом выполняем второе изменение.",
        f"Если стало {middle}, то после второго шага получаем {middle} {second_sign} {second_delta} = {result}.",
        f"Ответ: {result}.",
        "Совет: если в задаче несколько изменений, выполняй их по порядку.",
    )


def explain_relation_chain_word_problem(base: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str, ask_total: bool = False) -> Optional[str]:
    middle = _safe_related_value_v11(base, first_delta, first_mode)
    if middle is None:
        return None
    result = _safe_related_value_v11(middle, second_delta, second_mode)
    if result is None:
        return None

    first_sign = _sign_from_mode_v11(first_mode)
    second_sign = _sign_from_mode_v11(second_mode)
    lines = [
        "Сразу ответить нельзя.",
        "Сначала узнаем второе количество.",
        f"Если первое количество {base}, то второе {base} {first_sign} {first_delta} = {middle}.",
        "Потом узнаем третье количество.",
        f"Если второе количество {middle}, то третье {middle} {second_sign} {second_delta} = {result}.",
    ]
    if ask_total:
        total = base + middle + result
        lines.extend([
            "Теперь узнаем, сколько всего.",
            f"Если количества равны {base}, {middle} и {result}, то всего {base} + {middle} + {result} = {total}.",
            f"Ответ: {total}.",
        ])
    else:
        lines.append(f"Ответ: {result}.")
    lines.append("Совет: если одно число зависит от другого несколько раз, находи их по очереди.")
    return join_explanation_lines(*lines)


def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        "Сразу ответить нельзя.",
        "Сначала узнаем, сколько в одинаковых группах.",
        f"Если по {per_group} взяли {groups} {plural_form(groups, 'раз', 'раза', 'раз')}, то в одинаковых группах получаем {per_group} × {groups} = {grouped_total}.",
        "Потом прибавляем оставшуюся часть.",
        f"Если в группах {grouped_total} и ещё {extra}, то всего {grouped_total} + {extra} = {result}.",
        f"Ответ: {result}.",
        "Совет: если часть предметов собрана в одинаковые группы, сначала считай эту часть умножением.",
    )


def explain_two_products_total_word_problem_v11(groups1: int, per1: int, groups2: int, per2: int) -> str:
    total1 = groups1 * per1
    total2 = groups2 * per2
    total = total1 + total2
    return join_explanation_lines(
        "Сразу ответить нельзя.",
        "Сначала узнаем, сколько в первой части.",
        f"Если по {per1} взяли {groups1} {plural_form(groups1, 'раз', 'раза', 'раз')}, то первая часть равна {per1} × {groups1} = {total1}.",
        "Потом узнаем, сколько во второй части.",
        f"Если по {per2} взяли {groups2} {plural_form(groups2, 'раз', 'раза', 'раз')}, то вторая часть равна {per2} × {groups2} = {total2}.",
        "Теперь узнаем, сколько всего.",
        f"Если первая часть {total1}, а вторая {total2}, то всего {total1} + {total2} = {total}.",
        f"Ответ: {total}.",
        "Совет: если есть две разные группы, сначала считай каждую отдельно.",
    )


def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    if not re.search(r"[а-я]", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 3:
        return None

    asks_total = bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower))
    asks_current = bool(re.search(r"сколько[^.?!]*\b(стало|теперь|осталось)\b", lower))
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_current, False, False, False, False)

    two_products = DOUBLE_GROUP_RE_V11.findall(lower)
    if asks_total and len(two_products) >= 2:
        (g1, p1), (g2, p2) = two_products[:2]
        return explain_two_products_total_word_problem_v11(int(g1), int(p1), int(g2), int(p2))

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if len(numbers) == 2 and len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        explanation = None
        if asks_total:
            explanation = explain_related_total_word_problem(numbers[0], delta, effective_mode)
        elif asks_plain_quantity:
            explanation = explain_related_quantity_word_problem(numbers[0], delta, effective_mode)
        if explanation and indirect:
            explanation = _v12_prepend_explanation(explanation, _v12_additive_indirect_intro(delta, mode))
        return explanation

    if len(numbers) == 2 and len(multiplicative_pairs) == 1:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        explanation = None
        if asks_total:
            explanation = explain_multiplicative_total_word_problem_v11(numbers[0], factor, effective_mode)
        elif asks_plain_quantity:
            explanation = explain_multiplicative_quantity_word_problem_v11(numbers[0], factor, effective_mode)
        if explanation and indirect:
            explanation = _v12_prepend_explanation(explanation, _v12_multiplicative_indirect_intro(factor, mode))
        return explanation

    if len(numbers) == 3 and len(relation_pairs) >= 2:
        (delta1, mode1), (delta2, mode2) = relation_pairs[:2]
        chain = explain_relation_chain_word_problem(numbers[0], delta1, mode1, delta2, mode2, ask_total=asks_total)
        if chain and indirect:
            chain = _v12_prepend_explanation(chain, "Сначала переведём условие из косвенной формы в прямую.")
        return chain

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

    if len(numbers) == 3 and asks_total and ("ещё" in lower or "еще" in lower or "отдельно" in lower) and "по" in lower:
        groups_match = re.search(r"\b(?:в|на)?\s*(\d+)\s+[а-яё]+(?:\s+[а-яё]+){0,2}\s+по\s+(\d+)\b", lower)
        if groups_match:
            groups = int(groups_match.group(1))
            per_group = int(groups_match.group(2))
            remaining = list(numbers)
            for value in (groups, per_group):
                if value in remaining:
                    remaining.remove(value)
            if len(remaining) == 1:
                return explain_groups_plus_extra_word_problem(groups, per_group, remaining[0])

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
    asks_left = bool(re.search(r"сколько[^.?!]*\bостал", lower))
    asks_now = bool(re.search(r"сколько[^.?!]*\b(стало|теперь)\b", lower))
    asks_total = bool(TOTAL_CONTEXT_RE_V11.search(lower))
    asks_each = "поровну" in lower or bool(re.search(r"сколько[^.?!]*кажд", lower))
    asks_added = contains_any_fragment(lower, ("сколько добав", "сколько подар", "сколько куп", "сколько прин", "сколько полож"))
    asks_removed = contains_any_fragment(lower, ("сколько отдал", "сколько съел", "сколько убрал", "сколько забрал", "сколько потрат", "сколько продал", "сколько потер"))
    asks_groups = contains_any_fragment(lower, (
        "сколько короб", "сколько корзин", "сколько пакет", "сколько тарел", "сколько полок", "сколько ряд", "сколько групп", "сколько ящик", "сколько банок", "сколько парт", "сколько машин", "сколько мест", "сколько сеток",
    ))
    asks_remainder = "остат" in lower or "сколько остан" in lower or "полных" in lower
    needs_extra_group = contains_any_fragment(lower, ("нужно", "нужны", "понадоб", "потребует", "понадобится"))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_now, asks_left, asks_initial, asks_ratio, asks_compare)

    if asks_ratio:
        ratio = explain_ratio_word_problem(first, second)
        if ratio:
            return ratio

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if relation_pairs:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        explanation = None
        if asks_compare:
            explanation = explain_comparison_word_problem(first, second)
        elif asks_total:
            explanation = explain_related_total_word_problem(first, delta, effective_mode)
        elif asks_plain_quantity:
            explanation = explain_related_quantity_word_problem(first, delta, effective_mode)
        if explanation and indirect and (asks_total or asks_plain_quantity):
            explanation = _v12_prepend_explanation(explanation, _v12_additive_indirect_intro(delta, mode))
        if explanation:
            return explanation

    if multiplicative_pairs:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        explanation = None
        if asks_total:
            explanation = explain_multiplicative_total_word_problem_v11(first, factor, effective_mode)
        elif asks_plain_quantity:
            explanation = explain_multiplicative_quantity_word_problem_v11(first, factor, effective_mode)
        if explanation and indirect:
            explanation = _v12_prepend_explanation(explanation, _v12_multiplicative_indirect_intro(factor, mode))
        if explanation:
            return explanation

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

    if asks_each and contains_any_fragment(lower, ("раздел", "раздал", "раздала", "раздали", "получ", "достал", "достан")):
        return explain_sharing_word_problem(first, second)

    if "по" in lower and (asks_groups or has_grouping):
        total = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        grouped = explain_group_count_word_problem(total, size, needs_extra_group=needs_extra_group, explicit_remainder=asks_remainder)
        if grouped:
            return grouped

    if "по" in lower and "сколько" in lower and not asks_groups and not asks_each:
        groups = other_value if other_value is not None and per_group is not None else first
        size = per_group if per_group is not None else second
        return explain_multiplication_word_problem(groups, size)

    one_group_match = ONE_GROUP_RE_V11.search(lower)
    question_groups_match = QUESTION_GROUP_RE_V11.search(lower)
    if one_group_match and question_groups_match:
        per_item = int(one_group_match.group(1))
        group_count = int(question_groups_match.group(1))
        return explain_multiplication_word_problem(group_count, per_item)

    if has_loss and (asks_left or asks_now):
        explanation = explain_subtraction_word_problem(first, second)
        return explanation or None

    if (has_gain and (asks_total or asks_now)) or (asks_total and not has_loss and "по" not in lower):
        return explain_addition_word_problem(first, second)

    return None


SYSTEM_PROMPT_V12 = """
Ты — спокойный и очень точный учитель математики для детей 7–10 лет.
Главная цель — не просто сообщить ответ, а научить ходу решения так, как объясняет хороший учитель начальной школы.

Пиши только на русском языке.
Пиши без markdown, без списков, без нумерации и без смайликов.
Не используй похвалу, лишние вступления и пустые фразы.
Каждая строка — одна законченная мысль.
Не повторяй одно и то же разными словами.
Не пиши ответ в первой строке.
Проверка нужна только у уравнений.

Общая структура ответа:
сначала скажи, что нужно найти;
потом назови правило, способ или смысл действия;
затем решай по шагам;
потом строка «Ответ: ...»;
последняя строка — «Совет: ...».

Для примеров и выражений объясняй как в начальной школе:
если удобно, используй состав числа, сложение и вычитание по частям, разложение на десятки и единицы, разрядные слагаемые, распределительный закон, подбор, деление круглых чисел, деление с остатком;
если это письменное вычисление, не дублируй готовый ответ в начале и не пиши строку вида «Делим: 25155 : 39 = 645»;
для деления столбиком держи порядок: первое неполное делимое -> цифра частного -> умножение -> вычитание -> снос следующей цифры.

Для уравнений сначала назови неизвестный компонент.
Используй школьные правила:
чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое;
чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое;
чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность;
чтобы найти неизвестный множитель, произведение делим на известный множитель;
чтобы найти неизвестное делимое, делитель умножаем на частное;
чтобы найти неизвестный делитель, делимое делим на частное.
После этого обязательно делай короткую проверку.

Для текстовых задач объясняй по действиям.
У задачи есть условие и вопрос.
Если задача простая, делай один логический шаг по образцу «Если ..., то ...».
Если задача составная, сначала скажи «Сразу ответить нельзя.», затем пиши «Сначала узнаем...», «Потом узнаем...». Каждый шаг формулируй как законченный вывод.
Если задача в косвенной форме, сначала переведи её в прямой смысл.

Подсказки по выбору действия:
«всего», «вместе» — обычно сложение;
«осталось» — вычитание;
«на ... больше» — прибавляем;
«на ... меньше» — вычитаем;
«в ... раза больше» — умножаем;
«в ... раза меньше» — делим;
«поровну», «каждый» — деление;
«по ... в каждой» — умножение или деление по смыслу.

Для задач на цену, количество и стоимость, на скорость, время и расстояние, на приведение к единице, на сумму двух произведений, на долю и число по доле сначала находи промежуточную величину, потом отвечай на главный вопрос.

Для дробей сначала смотри на знаменатели.
Для геометрии сначала говори, что именно ищем, и какое правило используем.

Если запись непонятная или это не задача по математике, спокойно попроси записать пример понятнее.
""".strip()


async def build_explanation(user_text: str) -> dict:
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )

    kind = infer_task_kind(user_text)

    if local_explanation:
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    extra_instruction = ""
    if kind == "word":
        extra_instruction = (
            "Это текстовая задача. Объясняй по действиям. "
            "Если задача простая, используй один логический шаг по образцу «Если ..., то ...». "
            "Если задача составная, сначала скажи «Сразу ответить нельзя.», потом пиши «Сначала узнаем...», «Потом узнаем...». "
            "Если задача в косвенной форме, сначала переведи её в прямой смысл.\n\n"
        )
    elif kind == "geometry":
        extra_instruction = (
            "Это задача по геометрии. Сначала назови, что ищем, потом правило, потом подставь числа и выполни вычисление.\n\n"
        )
    elif kind == "expression":
        extra_instruction = (
            "Это пример или выражение. Не пиши готовый ответ в первой строке. "
            "Если удобно, используй состав числа, вычисление по частям, десятки и единицы, разрядные слагаемые, подбор или деление круглых чисел. "
            "Если пример будет решаться столбиком, не дублируй строку с готовым ответом в начале.\n\n"
        )
    elif kind == "fraction":
        extra_instruction = (
            "Это задача с дробями. Сначала посмотри на знаменатели. Если знаменатели разные, приведи дроби к общему знаменателю.\n\n"
        )
    elif kind == "equation":
        extra_instruction = (
            "Это уравнение. Сначала назови неизвестный компонент, потом правило его нахождения, потом вычисление и только в конце короткую проверку.\n\n"
        )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_V12},
            {
                "role": "user",
                "content": (
                    "Объясни решение так, чтобы ребёнок мог слушать текст и идти по нему глазами строка за строкой. "
                    "Текст должен быть последовательным, без лишних слов и без скачка сразу к ответу.\n\n"
                    f"{extra_instruction}{user_text}"
                ),
            },
        ],
        "max_tokens": 800,
        "temperature": 0.05,
    }

    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result

    shaped = shape_explanation(llm_result["result"], kind)
    return {"result": shaped, "source": "llm", "validated": False}

BODY_LINE_LIMITS_V9["word"] = max(BODY_LINE_LIMITS_V9.get("word", 5), 7)

# =========================
# V13 book-method overrides
# =========================

SECTION_PREFIX_RE_V13 = re.compile(r"^(правило|краткое\s+условие|решение|ответ|проверка|совет)\s*:\s*", re.IGNORECASE)
LOW_VALUE_INTRO_RE_V13 = re.compile(r"^(?:ищем|нужно\s+найти)\s+(?:сумму|разность|произведение|частное|второе\s+количество|периметр|площадь|сторону|неизвестное\s+слагаемое|неизвестное\s+уменьшаемое|неизвестное\s+вычитаемое|неизвестный\s+множитель|неизвестное\s+делимое|неизвестный\s+делитель)[.!?]?$", re.IGNORECASE)
DIRECT_RESULT_RE_V13 = re.compile(r"^(?:считаем|делим|умножаем|складываем|вычитаем|получаем|если\s+.+?,\s+то)\s*:?\s*.*=\s*([^=]+)$", re.IGNORECASE)
BODY_LINE_LIMITS_V13 = {
    "equation": 6,
    "expression": 8,
    "fraction": 7,
    "geometry": 7,
    "word": 9,
    "other": 7,
}


def _v13_condition(*parts: str) -> str:
    values = [str(part or "").strip() for part in parts if str(part or "").strip()]
    return "; ".join(values)



def _v13_normalize_section(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    pairs = [
        (r"^правило\s*:\s*", "Правило"),
        (r"^краткое\s+условие\s*:\s*", "Краткое условие"),
        (r"^решение\s*:\s*", "Решение"),
        (r"^ответ\s*:\s*", "Ответ"),
        (r"^проверка\s*:\s*", "Проверка"),
        (r"^совет\s*:\s*", "Совет"),
    ]
    for pattern, label in pairs:
        if re.match(pattern, text, flags=re.IGNORECASE):
            tail = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
            return f"{label}: {tail}" if tail else f"{label}:"
    return text



def _v13_extract_answer_value(answer_line: str) -> str:
    if not answer_line:
        return ""
    return re.sub(r"^Ответ:\s*", "", str(answer_line), flags=re.IGNORECASE).strip().rstrip(".!?").strip()



def _v13_math_signal(line: str) -> bool:
    return bool(re.search(r"\d|[xх]|[+\-=:×÷/]", str(line or ""), flags=re.IGNORECASE))



def _v13_clean_body_lines(lines, kind: str):
    normalized = []
    seen = set()
    informative_exists = any(_v13_math_signal(line) for line in lines)

    for raw in lines:
        line = _v13_normalize_section(raw)
        if not line:
            continue
        key = line.lower().rstrip(".!?")
        if key in seen:
            continue
        seen.add(key)
        normalized.append(line)

    cleaned = []
    for index, line in enumerate(normalized):
        text = str(line).strip()
        if kind != "equation" and informative_exists and LOW_VALUE_INTRO_RE_V13.match(text) and len(normalized) > 1:
            continue
        if kind != "equation" and index == 0 and DIRECT_RESULT_RE_V13.match(text) and len(normalized) > 1:
            continue
        cleaned.append(text)

    return cleaned[: BODY_LINE_LIMITS_V13.get(kind, BODY_LINE_LIMITS_V13["other"])]



def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    cleaned = sanitize_model_text(text)
    if not cleaned:
        lines = ["Напишите задачу понятнее", "Ответ: сначала нужно уточнить запись"]
        if forced_advice:
            lines.append(f"Совет: {forced_advice}")
        return join_explanation_lines(*lines)

    if str(cleaned).lstrip().startswith("Ошибка:"):
        return str(cleaned).replace("\r", "").strip()

    body_lines = []
    answer_line = ""
    advice_line = ""
    check_line = ""

    for raw_line in str(cleaned).splitlines():
        line = _v13_normalize_section(raw_line)
        if not line:
            continue
        if re.match(r"^Ответ:\s*", line, flags=re.IGNORECASE):
            value = re.sub(r"^Ответ:\s*", "", line, flags=re.IGNORECASE).strip()
            if value:
                answer_line = f"Ответ: {value}"
            continue
        if re.match(r"^Совет:\s*", line, flags=re.IGNORECASE):
            value = re.sub(r"^Совет:\s*", "", line, flags=re.IGNORECASE).strip()
            if value:
                advice_line = f"Совет: {value}"
            continue
        if re.match(r"^Проверка:\s*", line, flags=re.IGNORECASE):
            value = re.sub(r"^Проверка:\s*", "", line, flags=re.IGNORECASE).strip()
            if value:
                check_line = f"Проверка: {value}"
            continue
        body_lines.append(line)

    body_lines = _v13_clean_body_lines(body_lines, kind)

    if kind != "equation":
        check_line = ""

    if forced_answer is not None:
        answer_line = f"Ответ: {forced_answer}"

    if not answer_line and body_lines:
        tail = body_lines[-1]
        match = re.search(r"=\s*([^=]+)$", tail)
        if match:
            answer_line = f"Ответ: {match.group(1).strip()}"

    if not answer_line:
        answer_line = "Ответ: проверь запись задачи"

    final_lines = list(body_lines)
    if check_line:
        final_lines.append(check_line)
    final_lines.append(answer_line)
    if forced_advice:
        advice_line = f"Совет: {forced_advice}"
    if advice_line:
        final_lines.append(advice_line)
    return join_explanation_lines(*final_lines)



def _v13_additive_phrase(mode: str) -> str:
    return "больше" if mode == "больше" else "меньше"



def _v13_opposite_more_less(mode: str) -> str:
    return "меньше" if mode == "больше" else "больше"



def _v13_mul_phrase(mode: str) -> str:
    return "больше" if mode == "больше" else "меньше"



def _v13_unknown_component_intro(name: str, rule: str, calc: str, check: str, answer: str) -> str:
    return join_explanation_lines(
        f"Ищем {name}",
        f"Правило: {rule}",
        calc,
        f"Проверка: {check}",
        f"Ответ: {answer}",
    )



def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left < 10 and right < 10 and total >= 10:
        need = 10 - left
        if 0 < need < right:
            rest = right - need
            return join_explanation_lines(
                "Правило: при переходе через десяток удобно сначала дополнить число до 10",
                f"Разложим {right} на {need} и {rest}",
                f"{left} + {need} = 10",
                f"10 + {rest} = {total}",
                f"Ответ: {total}",
            )
    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        return join_explanation_lines(
            "Правило: числа удобно разложить на десятки и единицы",
            f"{left} = {left_tens} + {left_units}, {right} = {right_tens} + {right_units}",
            f"Складываем десятки: {left_tens} + {right_tens} = {left_tens + right_tens}",
            f"Складываем единицы: {left_units} + {right_units} = {left_units + right_units}",
            f"Складываем полученные числа: {left_tens + right_tens} + {left_units + right_units} = {total}",
            f"Ответ: {total}",
        )
    return join_explanation_lines(
        f"Считаем: {left} + {right} = {total}",
        f"Ответ: {total}",
    )



def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return join_explanation_lines(
            f"Считаем: {left} - {right} = {result}",
            f"Ответ: {result}",
        )
    if left >= 10 and right < 10 and left % 10 < right:
        first_part = left % 10
        second_part = right - first_part
        return join_explanation_lines(
            "Правило: если единиц не хватает, удобно вычитать по частям",
            f"Разложим {right} на {first_part} и {second_part}",
            f"{left} - {first_part} = {left - first_part}",
            f"{left - first_part} - {second_part} = {result}",
            f"Ответ: {result}",
        )
    if left >= 10 or right >= 10:
        left_tens, left_units = left - left % 10, left % 10
        right_tens, right_units = right - right % 10, right % 10
        if left < 100 and right < 100 and left_units >= right_units:
            return join_explanation_lines(
                "Правило: числа удобно разложить на десятки и единицы",
                f"{left} = {left_tens} + {left_units}, {right} = {right_tens} + {right_units}",
                f"Вычитаем десятки: {left_tens} - {right_tens} = {left_tens - right_tens}",
                f"Вычитаем единицы: {left_units} - {right_units} = {left_units - right_units}",
                f"Складываем полученные числа: {left_tens - right_tens} + {left_units - right_units} = {result}",
                f"Ответ: {result}",
            )
        tens = right - right % 10
        units = right % 10
        middle = left - tens
        return join_explanation_lines(
            "Правило: из числа можно вычитать по частям: сначала десятки, потом единицы",
            f"{left} - {tens} = {middle}",
            f"{middle} - {units} = {result}",
            f"Ответ: {result}",
        )
    return join_explanation_lines(
        f"Считаем: {left} - {right} = {result}",
        f"Ответ: {result}",
    )



def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)
    if big < 10 and small < 10:
        repeated = " + ".join([str(big)] * small)
        return join_explanation_lines(
            "Правило: умножение показывает сумму одинаковых слагаемых",
            f"{big} × {small} = {repeated} = {result}",
            f"Ответ: {result}",
        )
    if big % 10 == 0 and small < 10:
        tens = big // 10
        return join_explanation_lines(
            "Правило: круглое число удобно представить десятками",
            f"{big} = {tens} дес.",
            f"{tens} дес. × {small} = {tens * small} дес.",
            f"Получаем {result}",
            f"Ответ: {result}",
        )
    if big >= 10 and small <= 10:
        parts = [value for value in (big // 100 * 100, (big % 100) // 10 * 10, big % 10) if value]
        partials = [part * small for part in parts]
        return join_explanation_lines(
            "Правило: многозначное число умножаем по разрядным слагаемым",
            f"{big} = {' + '.join(str(part) for part in parts)}",
            *[f"{part} × {small} = {part * small}" for part in parts],
            f"Складываем результаты: {' + '.join(str(value) for value in partials)} = {result}",
            f"Ответ: {result}",
        )
    return join_explanation_lines(
        f"Считаем: {left} × {right} = {result}",
        f"Ответ: {result}",
    )



def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
        )

    quotient, remainder = divmod(left, right)
    common_zeroes = min(_v12_trailing_zero_count(left), _v12_trailing_zero_count(right))
    if common_zeroes > 0 and remainder == 0:
        reduced_left = left // (10 ** common_zeroes)
        reduced_right = right // (10 ** common_zeroes)
        return join_explanation_lines(
            "Правило: у круглых чисел можно сократить одинаковые нули справа",
            f"{left} : {right} = {reduced_left} : {reduced_right}",
            f"{reduced_left} : {reduced_right} = {quotient}",
            f"Ответ: {quotient}",
        )

    if left < 1000 and right < 100:
        if remainder == 0:
            trial = quotient + 1
            next_product = right * trial
            lines = [
                "Правило: деление проверяем подбором и таблицей умножения",
                f"Ищем число, которое при умножении на {right} даёт {left}",
            ]
            if next_product > left:
                lines.append(f"Подходит {quotient}, потому что {quotient} × {right} = {left}, а {trial} × {right} = {next_product}, это уже больше")
            else:
                lines.append(f"Подходит {quotient}, потому что {quotient} × {right} = {left}")
            lines.append(f"Ответ: {quotient}")
            return join_explanation_lines(*lines)
        fitted = quotient * right
        return join_explanation_lines(
            "Правило: при делении с остатком находим наибольшее подходящее произведение",
            f"Берём {quotient}, потому что {quotient} × {right} = {fitted}",
            f"Находим остаток: {left} - {fitted} = {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
        )

    answer_text = str(quotient) if remainder == 0 else f"{quotient}, остаток {remainder}"
    model = _build_long_division_steps_v9(left, right)
    steps = model.get("steps", [])
    lines = [
        "Правило: в делении столбиком сначала выделяем первое неполное делимое, потом подбираем цифру частного, умножаем, вычитаем и сносим следующую цифру",
    ]
    if steps:
        first_current = steps[0]["current"]
        lines.append(f"Сначала берём первое неполное делимое {first_current}")
        first = steps[0]
        lines.append(
            f"Подбираем {first['q_digit']}, потому что {first['q_digit']} × {right} = {first['product']}"
            + (f", а {first['q_digit'] + 1} × {right} = {(first['q_digit'] + 1) * right}, это уже больше" if (first['q_digit'] + 1) * right > first_current else "")
        )
        if len(steps) > 1:
            remaining = ", ".join(str(step["current"]) for step in steps[1:])
            lines.append(f"Дальше по тому же правилу работаем с {remaining}")
    lines.append(f"Ответ: {answer_text}")
    return join_explanation_lines(*lines)



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
            "У дроби знаменатель не может быть равен нулю",
            "Ответ: запись дроби неверная",
        )

    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)
    sign = "+" if operator == "+" else "-"

    if b == d:
        top = a + c if operator == "+" else a - c
        lines = [
            "Правило: если знаменатели одинаковые, работаем только с числителями",
            f"{a}/{b} {sign} {c}/{d} = {top}/{b}",
        ]
        if format_fraction(result) != f"{top}/{b}":
            lines.append(f"Сокращаем дробь: {top}/{b} = {format_fraction(result)}")
        lines.append(f"Ответ: {format_fraction(result)}")
        return join_explanation_lines(*lines)

    common = math.lcm(b, d)
    a_scaled = a * (common // b)
    c_scaled = c * (common // d)
    top = a_scaled + c_scaled if operator == "+" else a_scaled - c_scaled
    simplified = Fraction(top, common)
    lines = [
        f"Правило: сначала приводим дроби к общему знаменателю {common}",
        f"{a}/{b} = {a_scaled}/{common}, {c}/{d} = {c_scaled}/{common}",
        f"Теперь считаем: {a_scaled}/{common} {sign} {c_scaled}/{common} = {top}/{common}",
    ]
    if format_fraction(simplified) != f"{top}/{common}":
        lines.append(f"Сокращаем дробь: {top}/{common} = {format_fraction(simplified)}")
    lines.append(f"Ответ: {format_fraction(simplified)}")
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
        (r"^x\+(\d+)$", "unknown_addend"),
        (r"^(\d+)\+x$", "unknown_addend"),
        (r"^x-(\d+)$", "unknown_minuend"),
        (r"^(\d+)-x$", "unknown_subtrahend"),
        (r"^x\*(\d+)$", "unknown_factor"),
        (r"^(\d+)\*x$", "unknown_factor"),
        (r"^x/(\d+)$", "unknown_dividend"),
        (r"^(\d+)/x$", "unknown_divisor"),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue
        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind == "unknown_addend":
            answer = rhs_value - number
            check = f"{format_fraction(answer)} + {number_text} = {rhs_text}" if lhs.startswith("x") else f"{number_text} + {format_fraction(answer)} = {rhs_text}"
            return join_explanation_lines(
                "Ищем неизвестное слагаемое",
                "Правило: чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое",
                f"x = {rhs_text} - {number_text} = {format_fraction(answer)}",
                f"Проверка: {check}",
                f"Ответ: {format_fraction(answer)}",
            )

        if kind == "unknown_minuend":
            answer = rhs_value + number
            return join_explanation_lines(
                "Ищем неизвестное уменьшаемое",
                "Правило: чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое",
                f"x = {rhs_text} + {number_text} = {format_fraction(answer)}",
                f"Проверка: {format_fraction(answer)} - {number_text} = {rhs_text}",
                f"Ответ: {format_fraction(answer)}",
            )

        if kind == "unknown_subtrahend":
            answer = number - rhs_value
            return join_explanation_lines(
                "Ищем неизвестное вычитаемое",
                "Правило: чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность",
                f"x = {number_text} - {rhs_text} = {format_fraction(answer)}",
                f"Проверка: {number_text} - {format_fraction(answer)} = {rhs_text}",
                f"Ответ: {format_fraction(answer)}",
            )

        if kind == "unknown_factor":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Ищем неизвестный множитель",
                        "Если один множитель равен 0, произведение всегда равно 0",
                        "Ответ: подходит любое число",
                    )
                return join_explanation_lines(
                    "Ищем неизвестный множитель",
                    "0 не может дать ненулевое произведение",
                    "Ответ: решения нет",
                )
            answer = rhs_value / number
            if lhs.startswith("x"):
                check = f"{format_fraction(answer)} × {number_text} = {rhs_text}"
            else:
                check = f"{number_text} × {format_fraction(answer)} = {rhs_text}"
            return join_explanation_lines(
                "Ищем неизвестный множитель",
                "Правило: чтобы найти неизвестный множитель, произведение делим на известный множитель",
                f"x = {rhs_text} : {number_text} = {format_fraction(answer)}",
                f"Проверка: {check}",
                f"Ответ: {format_fraction(answer)}",
            )

        if kind == "unknown_dividend":
            if number == 0:
                return join_explanation_lines(
                    "Ищем неизвестное делимое",
                    "На ноль делить нельзя",
                    "Ответ: решения нет",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Ищем неизвестное делимое",
                "Правило: чтобы найти неизвестное делимое, делитель умножаем на частное",
                f"x = {rhs_text} × {number_text} = {format_fraction(answer)}",
                f"Проверка: {format_fraction(answer)} : {number_text} = {rhs_text}",
                f"Ответ: {format_fraction(answer)}",
            )

        if kind == "unknown_divisor":
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "Ищем неизвестный делитель",
                        "0, делённое на любое ненулевое число, равно 0",
                        "Ответ: подходит любое число, кроме 0",
                    )
                return join_explanation_lines(
                    "Ищем неизвестный делитель",
                    "0 не может дать ненулевое частное",
                    "Ответ: решения нет",
                )
            if rhs_value == 0:
                return join_explanation_lines(
                    "Ищем неизвестный делитель",
                    "Ненулевое число при делении не может дать 0",
                    "Ответ: решения нет",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "Ищем неизвестный делитель",
                "Правило: чтобы найти неизвестный делитель, делимое делим на частное",
                f"x = {number_text} : {rhs_text} = {format_fraction(answer)}",
                f"Проверка: {number_text} : {format_fraction(answer)} = {rhs_text}",
                f"Ответ: {format_fraction(answer)}",
            )

    return None



def explain_addition_word_problem(first: int, second: int) -> str:
    total = first + second
    return join_explanation_lines(
        f"Краткое условие: {first} и ещё {second}",
        f"Если было {first} и ещё {second}, то всего {first} + {second} = {total}",
        f"Ответ: {total}",
    )



def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    return join_explanation_lines(
        f"Краткое условие: было {first}, убрали {second}",
        f"Если было {first} и убрали {second}, то осталось {first} - {second} = {result}",
        f"Ответ: {result}",
    )



def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    diff = bigger - smaller
    return join_explanation_lines(
        f"Правило: чтобы узнать, на сколько одно число больше или меньше другого, из большего вычитаем меньшее",
        f"{bigger} - {smaller} = {diff}",
        f"Ответ: {diff}",
    )



def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    total = remaining + removed
    return join_explanation_lines(
        f"Краткое условие: осталось {remaining}, убрали {removed}",
        "Ищем уменьшаемое",
        "Правило: чтобы найти уменьшаемое, к разности прибавляем вычитаемое",
        f"{remaining} + {removed} = {total}",
        f"Ответ: {total}",
    )



def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    start = final_total - added
    return join_explanation_lines(
        f"Краткое условие: стало {final_total}, добавили {added}",
        "Ищем число, которое было сначала",
        f"Если после прибавления получилось {final_total}, то сначала было {final_total} - {added} = {start}",
        f"Ответ: {start}",
    )



def explain_find_added_problem(before: int, after: int) -> str:
    added = after - before
    return join_explanation_lines(
        f"Краткое условие: было {before}, стало {after}",
        "Ищем, сколько добавили",
        f"Если было {before}, а стало {after}, то добавили {after} - {before} = {added}",
        f"Ответ: {added}",
    )



def explain_find_removed_problem(before: int, after: int) -> str:
    removed = before - after
    return join_explanation_lines(
        f"Краткое условие: было {before}, осталось {after}",
        "Ищем, сколько убрали",
        f"Если было {before}, а осталось {after}, то убрали {before} - {after} = {removed}",
        f"Ответ: {removed}",
    )



def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    total = groups * per_group
    return join_explanation_lines(
        f"Краткое условие: {groups} {plural_form(groups, 'группа', 'группы', 'групп')}, по {per_group} в каждой",
        f"Если групп {groups}, а в каждой по {per_group}, то всего {per_group} × {groups} = {total}",
        f"Ответ: {total}",
    )



def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return None
    quotient, remainder = divmod(total, groups)
    lines = [
        f"Краткое условие: всего {total}, поровну на {groups} частей",
        f"Если {total} разделить поровну на {groups} частей, то {total} : {groups} = {quotient}",
    ]
    if remainder:
        lines[-1] = f"Если {total} разделить поровну на {groups} частей, то получится {quotient} и остаток {remainder}"
        lines.append(f"Ответ: {quotient}, остаток {remainder}")
    else:
        lines.append(f"Ответ: {quotient}")
    return join_explanation_lines(*lines)



def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return None
    quotient, remainder = divmod(total, per_group)
    lines = [
        f"Краткое условие: всего {total}, по {per_group} в каждой группе",
        f"Если всего {total}, а в каждой группе по {per_group}, то {total} : {per_group} = {quotient}",
    ]
    if remainder and (needs_extra_group or explicit_remainder):
        lines.append(f"Остаётся ещё {remainder}")
    if remainder and needs_extra_group:
        lines.append(f"Значит, нужна ещё одна группа")
        lines.append(f"Ответ: {quotient + 1}")
    elif remainder:
        lines.append(f"Ответ: {quotient}, остаток {remainder}")
    else:
        lines.append(f"Ответ: {quotient}")
    return join_explanation_lines(*lines)



def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
        )
    if bigger % smaller != 0:
        return None
    result = bigger // smaller
    return join_explanation_lines(
        "Правило: чтобы узнать, во сколько раз одно число больше или меньше другого, большее число делим на меньшее",
        f"{bigger} : {smaller} = {result}",
        f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
    )



def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = _safe_related_value_v11(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"Краткое условие: первое количество {base}, второе на {delta} {mode}",
        f"Если второе количество на {delta} {mode} первого, то {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
    )



def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = _safe_related_value_v11(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"Краткое условие: первое количество {base}, второе на {delta} {mode}",
        "Сразу ответить на вопрос нельзя",
        f"Сначала узнаем второе количество: {base} {sign} {delta} = {related}",
        f"Потом узнаем, сколько всего: {base} + {related} = {total}",
        f"Ответ: {total}",
    )



def explain_multiplicative_quantity_word_problem_v11(base: int, factor: int, mode: str) -> Optional[str]:
    result = _safe_related_value_v11(base, factor, mode, multiplicative=True)
    if result is None:
        return None
    calc = f"{base} × {factor} = {result}" if mode == "больше" else f"{base} : {factor} = {result}"
    return join_explanation_lines(
        f"Краткое условие: первое количество {base}, второе в {factor} раза {mode}",
        f"Если второе количество в {factor} раза {mode} первого, то {calc}",
        f"Ответ: {result}",
    )



def explain_multiplicative_total_word_problem_v11(base: int, factor: int, mode: str) -> Optional[str]:
    related = _safe_related_value_v11(base, factor, mode, multiplicative=True)
    if related is None:
        return None
    calc = f"{base} × {factor} = {related}" if mode == "больше" else f"{base} : {factor} = {related}"
    total = base + related
    return join_explanation_lines(
        f"Краткое условие: первое количество {base}, второе в {factor} раза {mode}",
        "Сразу ответить на вопрос нельзя",
        f"Сначала узнаем второе количество: {calc}",
        f"Потом узнаем, сколько всего: {base} + {related} = {total}",
        f"Ответ: {total}",
    )



def explain_sequential_change_word_problem(start: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str) -> Optional[str]:
    middle = _safe_related_value_v11(start, first_delta, "больше" if first_mode == "gain" else "меньше")
    if middle is None:
        return None
    result = _safe_related_value_v11(middle, second_delta, "больше" if second_mode == "gain" else "меньше")
    if result is None:
        return None
    first_sign = "+" if first_mode == "gain" else "-"
    second_sign = "+" if second_mode == "gain" else "-"
    return join_explanation_lines(
        f"Краткое условие: было {start}, потом {first_sign} {first_delta}, потом {second_sign} {second_delta}",
        "Сразу ответить на вопрос нельзя",
        f"Сначала узнаем, что получилось после первого изменения: {start} {first_sign} {first_delta} = {middle}",
        f"Потом узнаем, что получилось после второго изменения: {middle} {second_sign} {second_delta} = {result}",
        f"Ответ: {result}",
    )



def explain_relation_chain_word_problem(base: int, first_delta: int, first_mode: str, second_delta: int, second_mode: str, ask_total: bool = False) -> Optional[str]:
    middle = _safe_related_value_v11(base, first_delta, first_mode)
    if middle is None:
        return None
    result = _safe_related_value_v11(middle, second_delta, second_mode)
    if result is None:
        return None
    first_sign = "+" if first_mode == "больше" else "-"
    second_sign = "+" if second_mode == "больше" else "-"
    lines = [
        f"Краткое условие: первое число {base}, второе на {first_delta} {first_mode}, третье на {second_delta} {second_mode} второго",
        "Сразу ответить на вопрос нельзя",
        f"Сначала узнаем второе число: {base} {first_sign} {first_delta} = {middle}",
        f"Потом узнаем третье число: {middle} {second_sign} {second_delta} = {result}",
    ]
    if ask_total:
        total = base + middle + result
        lines.append(f"Теперь узнаем, сколько всего: {base} + {middle} + {result} = {total}")
        lines.append(f"Ответ: {total}")
    else:
        lines.append(f"Ответ: {result}")
    return join_explanation_lines(*lines)



def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        f"Краткое условие: {groups} {plural_form(groups, 'группа', 'группы', 'групп')} по {per_group} и ещё {extra}",
        "Сразу ответить на вопрос нельзя",
        f"Сначала узнаем, сколько в одинаковых группах: {per_group} × {groups} = {grouped_total}",
        f"Потом прибавим ещё {extra}: {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
    )



def explain_two_products_total_word_problem_v11(groups1: int, per1: int, groups2: int, per2: int) -> str:
    total1 = groups1 * per1
    total2 = groups2 * per2
    total = total1 + total2
    return join_explanation_lines(
        f"Краткое условие: первая часть — {groups1} {plural_form(groups1, 'группа', 'группы', 'групп')} по {per1}, вторая часть — {groups2} {plural_form(groups2, 'группа', 'группы', 'групп')} по {per2}",
        "Сразу ответить на вопрос нельзя",
        f"Сначала узнаем первую часть: {per1} × {groups1} = {total1}",
        f"Потом узнаем вторую часть: {per2} × {groups2} = {total2}",
        f"Теперь узнаем, сколько всего: {total1} + {total2} = {total}",
        f"Ответ: {total}",
    )



def _v12_additive_indirect_intro(delta: int, mode: str) -> str:
    if mode == "меньше":
        return f"Если одно количество на {delta} меньше другого, то другое на {delta} больше первого"
    return f"Если одно количество на {delta} больше другого, то другое на {delta} меньше первого"



def _v12_multiplicative_indirect_intro(factor: int, mode: str) -> str:
    if mode == "меньше":
        return f"Если одно количество в {factor} раза меньше другого, то другое в {factor} раза больше первого"
    return f"Если одно количество в {factor} раза больше другого, то другое в {factor} раза меньше первого"



def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if not nums:
        return None

    asks_perimeter = "периметр" in lower
    asks_area = "площад" in lower
    asks_side = bool(re.search(r"найд[иите]{1,4}[^.?!]*сторон|как[а-я ]*сторон", lower))
    asks_width = bool(re.search(r"найд[иите]{1,4}[^.?!]*ширин|какова ширин", lower))
    unit = geometry_unit(text)

    if "квадрат" in lower and asks_perimeter and asks_side:
        perimeter = nums[0]
        side = perimeter // 4
        return join_explanation_lines(
            "Правило: у квадрата все стороны равны, поэтому сторону находим делением периметра на 4",
            f"{perimeter} : 4 = {side}",
            f"Ответ: {with_unit(side, unit)}",
        )

    if "прямоугольник" in lower and asks_perimeter and asks_width and len(nums) >= 2:
        perimeter, length = nums[0], nums[1]
        half = perimeter // 2
        width = half - length
        return join_explanation_lines(
            "Правило: полупериметр прямоугольника равен сумме длины и ширины",
            f"{perimeter} : 2 = {half}",
            f"{half} - {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
        )

    if "квадрат" in lower and asks_area and asks_side:
        area = nums[0]
        side = math.isqrt(area)
        if side * side != area:
            return None
        return join_explanation_lines(
            "Правило: площадь квадрата равна произведению стороны на саму себя",
            f"Ищем число, которое в квадрате даёт {area}. Это {side}",
            f"Ответ: {with_unit(side, unit)}",
        )

    if "прямоугольник" in lower and asks_area and asks_width and len(nums) >= 2:
        area, length = nums[0], nums[1]
        if length == 0 or area % length != 0:
            return None
        width = area // length
        return join_explanation_lines(
            "Правило: площадь прямоугольника равна длине, умноженной на ширину",
            f"{area} : {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
        )

    if "квадрат" in lower and asks_perimeter:
        side = nums[0]
        perimeter = side * 4
        return join_explanation_lines(
            "Правило: периметр квадрата равен сумме четырёх одинаковых сторон",
            f"{side} × 4 = {perimeter}",
            f"Ответ: {with_unit(perimeter, unit)}",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
            "Правило: периметр прямоугольника равен 2 × (длина + ширина)",
            f"({length} + {width}) × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
        )

    if "квадрат" in lower and asks_area:
        side = nums[0]
        result = side * side
        return join_explanation_lines(
            "Правило: площадь квадрата равна произведению стороны на саму себя",
            f"{side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Правило: площадь прямоугольника равна длине, умноженной на ширину",
            f"{length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
        )

    return None


SYSTEM_PROMPT_V13 = """
Ты — очень точный и спокойный учитель математики начальной школы.
Объясняй так, как объясняют в хороших методических пособиях для 1–4 класса.

Главная цель — не просто дать ответ, а показать школьный способ решения.
Ребёнок должен видеть последовательность действий и понимать, почему выбрано именно это действие.

Пиши только по-русски.
Пиши plain text.
Без markdown, смайликов, лишних вступлений и похвалы.
Не пиши «молодец», «отлично», «давай», «разберёмся».
Одна строка — одна полезная мысль.
Не повторяй одно и то же разными словами.
Не ставь готовый ответ в первой строке, если способ ещё не показан.
Не добавляй строку «Совет:» по умолчанию.

Общая школьная логика:
1. У любой задачи есть условие и вопрос.
2. Решение нужно строить по действиям.
3. Каждое действие должно быть понятным выводом из условия.
4. Для текстовых задач полезна логика «Если ..., то ...», но используй её только там, где она действительно помогает понять выбор действия.
5. После решения нужен ответ. Проверка обязательна только у уравнений.

Для примеров, выражений, письменных вычислений, дробей, геометрии и простых уравнений используй школьную схему:
правило или способ -> последовательные шаги -> ответ.

Для текстовых задач используй школьную схему решения по действиям:
очень короткое условие -> можно ли ответить сразу -> если нельзя, сначала узнаем ..., потом узнаем ... -> ответ.

Когда подходит, используй строку «Краткое условие: ...».
Для составной задачи обязательно пиши «Сразу ответить на вопрос нельзя.» только тогда, когда это действительно составная задача.
Для простой задачи не пиши эту строку.

Для примеров и выражений разрешено и желательно использовать такие методы:
- состав числа и переход через десяток;
- вычисление по частям;
- разрядные слагаемые;
- письменное сложение и вычитание по разрядам;
- умножение как сумму одинаковых слагаемых;
- распределительный закон при умножении многозначного числа на однозначное;
- умножение и деление круглых чисел;
- подбор при делении;
- деление с остатком;
- деление столбиком: первое неполное делимое -> цифра частного -> умножение -> вычитание -> снос следующей цифры.

Для уравнений сначала назови неизвестный компонент.
Используй точные школьные правила:
- чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое;
- чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое;
- чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность;
- чтобы найти неизвестный множитель, произведение делим на известный множитель;
- чтобы найти неизвестное делимое, делитель умножаем на частное;
- чтобы найти неизвестный делитель, делимое делим на частное.
После этого делай короткую проверку.

Для текстовых задач ориентируйся на слова условия:
- «всего», «вместе», «стало» часто ведут к сложению;
- «осталось», «убрали», «отдали», «съели» ведут к вычитанию;
- «на ... больше» означает прибавить;
- «на ... меньше» означает вычесть;
- «в ... раза больше» означает умножить;
- «в ... раза меньше» означает делить;
- «во сколько раз» означает деление;
- «по ... в каждой» часто означает умножение;
- «поровну», «каждый» означают деление на равные части.

Для косвенной формы сначала переводи условие в прямую мысль.
Пример логики: если одного на 4 меньше, то другого на 4 больше.
Если одного в 3 раза меньше, то другого в 3 раза больше.

Для задач на цену, количество, стоимость, на движение, на приведение к единице, на сумму двух произведений, на долю и число по доле сначала находи промежуточную величину, а потом отвечай на главный вопрос.

Для дробей:
- если знаменатели одинаковые, работай с числителями;
- если знаменатели разные, сначала приведи дроби к общему знаменателю.

Для геометрии сначала говори, что ищем и какое правило используем.
Например:
- периметр квадрата — четыре одинаковые стороны;
- периметр прямоугольника — 2 × (длина + ширина);
- площадь прямоугольника — длина × ширина;
- площадь квадрата — сторона × сторону.

Требования к структуре ответа:
- не пиши лишние технические фразы;
- не перепрыгивай сразу к ответу;
- не дублируй в начале строку вида «25155 : 39 = 645» для деления столбиком;
- если есть письменный метод, сначала дай короткое объяснение метода, а потом шаги;
- у обычных примеров и выражений не пиши строку «Проверка: ...»;
- строка «Ответ: ...» должна быть в конце основного объяснения.

Если запись непонятная или это не математика начальной школы, спокойно попроси записать задачу понятнее.
Не выдумывай данные, которых нет в условии.
""".strip()


async def build_explanation(user_text: str) -> dict:
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )

    kind = infer_task_kind(user_text)

    if local_explanation:
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    extra_instruction = ""
    if kind == "word":
        extra_instruction = (
            "Это текстовая задача. "
            "Сначала выдели условие и вопрос. "
            "Если задача простая, используй один понятный вывод по образцу «Если ..., то ...». "
            "Если задача составная, обязательно скажи «Сразу ответить на вопрос нельзя.», а потом пиши «Сначала узнаем...», «Потом узнаем...». "
            "Если задача в косвенной форме, сначала переведи её в прямую мысль.\n\n"
        )
    elif kind == "geometry":
        extra_instruction = (
            "Это задача по геометрии. Сначала назови правило, потом подставь числа и выполни вычисление.\n\n"
        )
    elif kind == "expression":
        extra_instruction = (
            "Это пример или выражение. Не ставь готовый ответ в первой строке. "
            "Если подходит, используй состав числа, вычисление по частям, десятки и единицы, разрядные слагаемые, подбор, деление круглых чисел или письменный способ.\n\n"
        )
    elif kind == "fraction":
        extra_instruction = (
            "Это действие с дробями. Сначала посмотри на знаменатели и выбери правильный способ.\n\n"
        )
    elif kind == "equation":
        extra_instruction = (
            "Это уравнение. Сначала назови неизвестный компонент, потом правило его нахождения, потом вычисление и в конце короткую проверку.\n\n"
        )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_V13},
            {
                "role": "user",
                "content": (
                    "Объясни решение так, чтобы ребёнок мог читать или слушать текст строка за строкой. "
                    "Объяснение должно быть последовательным, школьным и без лишних слов.\n\n"
                    f"{extra_instruction}{user_text}"
                ),
            },
        ],
        "max_tokens": 900,
        "temperature": 0.03,
    }

    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result

    shaped = shape_explanation(llm_result["result"], kind)
    return {"result": shaped, "source": "llm", "validated": False}


def _v13_geometry_numbers(text: str):
    cleaned = re.sub(r"\b(мм|см|дм|м|км)2\b", r"\1²", str(text or ""), flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(мм|см|дм|м|км)\^2\b", r"\1²", cleaned, flags=re.IGNORECASE)
    return extract_ordered_numbers(cleaned)



def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    nums = _v13_geometry_numbers(lower)
    if not nums:
        return None

    asks_perimeter = "периметр" in lower
    asks_area = "площад" in lower
    asks_side = bool(re.search(r"найд[а-я]*[^.?!]*сторон|какова[^.?!]*сторон", lower))
    asks_width = bool(re.search(r"найд[а-я]*[^.?!]*ширин|какова[^.?!]*ширин", lower))
    unit = geometry_unit(text)

    if "квадрат" in lower and asks_perimeter and asks_side:
        perimeter = nums[0]
        side = perimeter // 4
        return join_explanation_lines(
            "Правило: у квадрата все стороны равны, поэтому сторону находим делением периметра на 4",
            f"{perimeter} : 4 = {side}",
            f"Ответ: {with_unit(side, unit)}",
        )

    if "прямоугольник" in lower and asks_perimeter and asks_width and len(nums) >= 2:
        perimeter, length = nums[0], nums[1]
        half = perimeter // 2
        width = half - length
        return join_explanation_lines(
            "Правило: полупериметр прямоугольника равен сумме длины и ширины",
            f"{perimeter} : 2 = {half}",
            f"{half} - {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
        )

    if "квадрат" in lower and asks_area and asks_side:
        area = nums[0]
        side = math.isqrt(area)
        if side * side != area:
            return None
        return join_explanation_lines(
            "Правило: площадь квадрата равна произведению стороны на саму себя",
            f"Ищем число, которое в квадрате даёт {area}. Это {side}",
            f"Ответ: {with_unit(side, unit)}",
        )

    if "прямоугольник" in lower and asks_area and asks_width and len(nums) >= 2:
        area, length = nums[0], nums[1]
        if length == 0 or area % length != 0:
            return None
        width = area // length
        return join_explanation_lines(
            "Правило: площадь прямоугольника равна длине, умноженной на ширину",
            f"{area} : {length} = {width}",
            f"Ответ: {with_unit(width, unit)}",
        )

    if "квадрат" in lower and asks_perimeter:
        side = nums[0]
        perimeter = side * 4
        return join_explanation_lines(
            "Правило: периметр квадрата равен сумме четырёх одинаковых сторон",
            f"{side} × 4 = {perimeter}",
            f"Ответ: {with_unit(perimeter, unit)}",
        )

    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return join_explanation_lines(
            "Правило: периметр прямоугольника равен 2 × (длина + ширина)",
            f"({length} + {width}) × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
        )

    if "квадрат" in lower and asks_area:
        side = nums[0]
        result = side * side
        return join_explanation_lines(
            "Правило: площадь квадрата равна произведению стороны на саму себя",
            f"{side} × {side} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
        )

    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return join_explanation_lines(
            "Правило: площадь прямоугольника равна длине, умноженной на ширину",
            f"{length} × {width} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
        )

    return None



def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    if not re.search(r"[а-я]", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 3:
        return None

    asks_total = bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower))
    asks_current = bool(re.search(r"сколько[^.?!]*\b(стало|теперь|осталось)\b", lower))
    asks_plain_quantity = _question_has_plain_quantity_v11(lower, asks_total, asks_current, False, False, False, False)

    two_products = DOUBLE_GROUP_RE_V11.findall(lower)
    if asks_total and len(two_products) >= 2:
        (g1, p1), (g2, p2) = two_products[:2]
        return explain_two_products_total_word_problem_v11(int(g1), int(p1), int(g2), int(p2))

    if len(numbers) == 3 and asks_total and ("ещё" in lower or "еще" in lower or "отдельно" in lower) and "по" in lower:
        groups_match = re.search(r"\b(?:в|на)?\s*(\d+)\s+[а-яё]+(?:\s+[а-яё]+){0,2}\s+по\s+(\d+)\b", lower)
        if groups_match:
            groups = int(groups_match.group(1))
            per_group = int(groups_match.group(2))
            remaining = list(numbers)
            for value in (groups, per_group):
                if value in remaining:
                    remaining.remove(value)
            if len(remaining) == 1:
                return explain_groups_plus_extra_word_problem(groups, per_group, remaining[0])

    relation_pairs = extract_relation_pairs(lower)
    multiplicative_pairs = extract_multiplicative_relation_pairs_v11(lower)
    indirect = _is_indirect_form_v11(lower)

    if len(numbers) == 2 and len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        explanation = None
        if asks_total:
            explanation = explain_related_total_word_problem(numbers[0], delta, effective_mode)
        elif asks_plain_quantity:
            explanation = explain_related_quantity_word_problem(numbers[0], delta, effective_mode)
        if explanation and indirect:
            explanation = _v12_prepend_explanation(explanation, _v12_additive_indirect_intro(delta, mode))
        return explanation

    if len(numbers) == 2 and len(multiplicative_pairs) == 1:
        factor, mode = multiplicative_pairs[0]
        effective_mode = _invert_more_less_v11(mode) if indirect else mode
        explanation = None
        if asks_total:
            explanation = explain_multiplicative_total_word_problem_v11(numbers[0], factor, effective_mode)
        elif asks_plain_quantity:
            explanation = explain_multiplicative_quantity_word_problem_v11(numbers[0], factor, effective_mode)
        if explanation and indirect:
            explanation = _v12_prepend_explanation(explanation, _v12_multiplicative_indirect_intro(factor, mode))
        return explanation

    if len(numbers) == 3 and len(relation_pairs) >= 2:
        (delta1, mode1), (delta2, mode2) = relation_pairs[:2]
        chain = explain_relation_chain_word_problem(numbers[0], delta1, mode1, delta2, mode2, ask_total=asks_total)
        if chain and indirect:
            chain = _v12_prepend_explanation(chain, "Сначала переводим условие из косвенной формы в прямую")
        return chain

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


def geometry_unit(text: str) -> str:
    match = re.search(r"\b(мм|см|дм|м|км)(?:2|²)?\b", str(text or ""), flags=re.IGNORECASE)
    return match.group(1).lower() if match else ""
# =========================
# V14 textbook sync overrides
# =========================

SYSTEM_PROMPT_V14 = """
Ты - очень точный и спокойный учитель математики начальной школы для детей 7-10 лет.
Объясняй решение так, как его объясняют в хороших пособиях для 1-4 класса.

Главная цель - не просто дать ответ, а показать школьный ход решения.
Ребёнок должен видеть последовательность действий и понимать, почему выбрано именно это действие.

Пиши только по-русски.
Пиши plain text, без markdown, смайликов и лишних вступлений.
Не используй слова «молодец», «отлично», «давай», «разберёмся».
Одна строка - одна полезная мысль.
Не повторяй одну и ту же мысль разными словами.
Не ставь готовый ответ в первой строке.
Не добавляй строку «Совет:» автоматически.

Общая логика решения:
- у любой задачи есть условие и вопрос;
- решение строим по действиям;
- каждое действие должно быть понятным выводом;
- в текстовых задачах полезна логика «Если ..., то ...», когда она помогает понять выбор действия;
- проверка обязательна только у уравнений.

Для обычных примеров и выражений используй школьные способы:
- состав числа и переход через десяток;
- вычисление по частям;
- десятки и единицы;
- разрядные слагаемые;
- подбор;
- деление круглых чисел;
- деление с остатком;
- письменные вычисления в столбик.

Если подходит письменный способ, не убирай его.
Для вычислений в столбик сохраняй школьный порядок:
- сложение и вычитание: единицы под единицами, десятки под десятками, начинаем с единиц;
- умножение: начинаем с единиц нижнего числа;
- деление: первое неполное делимое -> цифра частного -> умножение -> вычитание -> снос следующей цифры.

Для уравнений сначала называй неизвестный компонент.
Используй точные школьные правила:
- чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое;
- чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое;
- чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность;
- чтобы найти неизвестный множитель, произведение делим на известный множитель;
- чтобы найти неизвестное делимое, делитель умножаем на частное;
- чтобы найти неизвестный делитель, делимое делим на частное.
После этого делай короткую проверку.

Для текстовых задач:
- если задача простая, можно дать короткое условие и один вывод;
- если задача составная, пиши «Сразу ответить на вопрос нельзя.» только тогда, когда это действительно так;
- затем используй переходы «Сначала узнаем...», «Потом узнаем...», «Теперь ответим на вопрос задачи.»;
- для косвенной формы сначала переводи условие в прямую мысль.

Подсказки по выбору действия:
- «всего», «вместе» - обычно сложение;
- «осталось» - вычитание;
- «на ... больше» - прибавляем;
- «на ... меньше» - вычитаем;
- «в ... раза больше» - умножаем;
- «в ... раза меньше» - делим;
- «во сколько раз» - деление;
- «по ... в каждой» - умножение или деление по смыслу;
- «поровну», «каждый» - деление на равные части.

Для задач на цену, количество и стоимость, на скорость, время и расстояние, на приведение к единице, на пропорциональное деление, на сумму двух произведений, на долю и число по доле сначала находи промежуточную величину, а потом отвечай на главный вопрос.

Для дробей:
- если знаменатели одинаковые, работай с числителями;
- если знаменатели разные, сначала приведи дроби к общему знаменателю.
- чтобы найти часть от числа, делим число на знаменатель и умножаем на числитель;
- чтобы найти число по его части, делим на числитель и умножаем на знаменатель.

Для геометрии сначала говори, что ищем и какое правило используем.
Например:
- периметр квадрата - это сумма четырёх одинаковых сторон;
- периметр прямоугольника - 2 x (длина + ширина);
- площадь прямоугольника - длина x ширина;
- площадь квадрата - сторона x сторону.

Структура ответа:
- по возможности короткое правило или краткое условие;
- затем последовательные действия;
- для уравнения после действий короткая проверка;
- в конце строка «Ответ: ...».

Если запись непонятная или данных не хватает, спокойно попроси записать задачу понятнее.
Не выдумывай данные, которых нет в условии.
""".strip()


def _v14_text(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text)



def _v14_lower(raw_text: str) -> str:
    return _v14_text(raw_text).lower()



def _v14_question(raw_text: str) -> str:
    text = _v14_text(raw_text)
    parts = [part.strip() for part in re.split(r"(?<=[?.!])\s+", text) if part.strip()]
    if not parts:
        return text
    questions = [part for part in parts if "?" in part]
    return questions[-1] if questions else parts[-1]



def _v14_has(text: str, *fragments: str) -> bool:
    base = str(text or "")
    return any(fragment in base for fragment in fragments)



def _v14_numbers_without_first_fraction(text: str):
    source = str(text or "")
    nums = extract_ordered_numbers(source)
    frac = re.search(r"(\d+)\s*/\s*(\d+)", source)
    if not frac:
        return nums
    num = int(frac.group(1))
    den = int(frac.group(2))
    remaining = []
    remove_stage = 0
    for value in nums:
        if remove_stage == 0 and value == num:
            remove_stage = 1
            continue
        if remove_stage == 1 and value == den:
            remove_stage = 2
            continue
        remaining.append(value)
    return remaining



def _v14_is_integer_fraction(value: Fraction) -> bool:
    return value.denominator == 1



def _v14_int_fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else format_fraction(value)



def _v14_question_asks_total(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"сколько[^.?!]*\b(всего|вместе)\b", q))



def _v14_question_asks_compare(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"на\s+сколько|во\s+сколько", q))



def _v14_question_asks_plain_quantity(question: str) -> bool:
    q = str(question or "").lower()
    if "сколько" not in q:
        return False
    if any(marker in q for marker in ("всего", "вместе", "осталось", "стало", "теперь", "было", "на сколько", "во сколько")):
        return False
    return True



def _v14_question_asks_speed(question: str) -> bool:
    q = str(question or "").lower()
    return "скорост" in q



def _v14_question_asks_time(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"сколько[^.?!]*\b(ч|час|часа|часов|мин|минут|минуты)\b", q))



def _v14_question_asks_distance(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"какое[^.?!]*расстояни|какой[^.?!]*путь|сколько[^.?!]*\b(км|м|см)\b", q))



def _v14_speed_unit(distance_unit: str, time_unit: str) -> str:
    d = str(distance_unit or "").lower()
    t = str(time_unit or "").lower()
    if t.startswith("ч"):
        return f"{d}/ч"
    if t.startswith("мин"):
        return f"{d}/мин"
    return f"{d}/{t}" if d and t else ""



def _v14_contains_relation_words(text: str) -> bool:
    base = str(text or "")
    return bool(re.search(r"на\s+\d+[^.?!]*\b(больше|меньше)\b|в\s+\d+\s+раз[^.?!]*\b(больше|меньше)\b", base))



def explain_unknown_addend_word_problem_v14(total: int, known: int) -> str:
    unknown = total - known
    return join_explanation_lines(
        f"Краткое условие: всего {total}, одна часть {known}, другая часть - ?",
        "Ищем неизвестное слагаемое",
        "Правило: чтобы найти неизвестное слагаемое, из суммы вычитаем известное слагаемое",
        f"{total} - {known} = {unknown}",
        f"Ответ: {unknown}",
    )



def try_local_unknown_part_word_problem_v14(raw_text: str) -> Optional[str]:
    lower = _v14_lower(raw_text)
    question = _v14_question(raw_text).lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    if _v14_contains_relation_words(lower):
        return None
    if _v14_question_asks_total(question) or _v14_question_asks_compare(question):
        return None
    if not _v14_question_asks_plain_quantity(question):
        return None
    if _v14_has(lower, "руб", "км/ч", "периметр", "площад", "скорост"):
        return None
    cues = (
        "перв", "втор", "из них", "осталь", "на двух", "на обеих", "за два дня", "за 2 дня",
        "вместе", "всего", "нашел", "нашла", "нашли", "прочитал", "прочитала", "прошел", "прошла"
    )
    if not _v14_has(lower, *cues):
        return None
    total = max(nums)
    known = min(nums)
    if total < known:
        return None
    return explain_unknown_addend_word_problem_v14(total, known)



def try_local_proportional_split_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    if not _v14_has(question, "каждая", "каждый", "каждой"):
        return None

    count_match = (
        re.search(r"в одной[^\d]*(\d+)[^\d]+в другой[^\d]*(\d+)", lower)
        or re.search(r"одна[^\d]*(\d+)[^\d]+другая[^\d]*(\d+)", lower)
        or re.search(r"перв[а-я]*[^\d]*(\d+)[^\d]+втор[а-я]*[^\d]*(\d+)", lower)
    )
    if not count_match:
        return None

    first_count = int(count_match.group(1))
    second_count = int(count_match.group(2))
    if first_count <= 0 or second_count <= 0:
        return None

    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (first_count, second_count):
        if value in remaining:
            remaining.remove(value)
    if not remaining:
        return None

    total = max(remaining)
    parts_total = first_count + second_count
    if parts_total == 0 or total % parts_total != 0:
        return None

    part_value = total // parts_total
    first_share = first_count * part_value
    second_share = second_count * part_value

    answer_suffix = ""
    unit_word = ""
    if "руб" in lower:
        answer_suffix = " руб."
        unit_word = "руб."
    elif "детал" in lower:
        answer_suffix = f" {plural_form(first_share, 'деталь', 'детали', 'деталей')}"
        unit_word = plural_form(part_value, 'деталь', 'детали', 'деталей')
    elif "ящик" in lower or "мешк" in lower or "человек" in lower:
        unit_word = "части"
    else:
        unit_word = "части"

    return join_explanation_lines(
        f"Краткое условие: первая группа - {first_count} частей, вторая группа - {second_count} частей, всего - {total}",
        "Сразу ответить на вопрос нельзя.",
        f"Сначала узнаем, сколько всего частей: {first_count} + {second_count} = {parts_total}",
        f"Потом узнаем, сколько приходится на 1 часть: {total} : {parts_total} = {part_value} {unit_word}".strip(),
        f"Теперь узнаем первую долю: {part_value} × {first_count} = {first_share}",
        f"И вторую долю: {part_value} × {second_count} = {second_share}",
        f"Ответ: первая группа - {first_share}{answer_suffix}, вторая группа - {second_share}{answer_suffix}",
    )



def try_local_price_quantity_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Цена одной вещи -> стоимость нескольких.
    m_one_price = re.search(r"\b\w+[а-яё\- ]*?\s+стоит\s+(\d+)\s*руб", lower)
    m_buy_count = re.search(r"сколько\s+стоят?\s+(\d+)", question)
    if m_one_price and m_buy_count:
        price = int(m_one_price.group(1))
        count = int(m_buy_count.group(1))
        total = price * count
        return join_explanation_lines(
            f"Краткое условие: цена 1 предмета - {price} руб., количество - {count}",
            "Правило: чтобы найти стоимость, цену умножаем на количество",
            f"{price} × {count} = {total}",
            f"Ответ: {total} руб.",
        )

    # Стоимость нескольких -> цена одной.
    m_many_cost = re.search(r"(\d+)\s+\w+[а-яё\- ]*?\s+стоят?\s+(\d+)\s*руб", lower)
    if m_many_cost and re.search(r"сколько\s+стоит\s+(?:1|одн)\w*", question):
        count = int(m_many_cost.group(1))
        total = int(m_many_cost.group(2))
        if count == 0 or total % count != 0:
            return None
        price = total // count
        return join_explanation_lines(
            f"Краткое условие: {count} предметов стоят {total} руб.",
            "Правило: чтобы найти цену, стоимость делим на количество",
            f"{total} : {count} = {price}",
            f"Ответ: {price} руб.",
        )

    # Сначала цена одной вещи, потом количество на другую сумму.
    m_buy = re.search(r"за\s+(\d+)\s+[а-яё\- ]+?\s+заплат\w*\s+(\d+)\s*руб", lower)
    m_other_sum = re.search(r"на\s+(\d+)\s*руб", question)
    if m_buy and m_other_sum and _v14_has(question, "сколько"):
        count = int(m_buy.group(1))
        total = int(m_buy.group(2))
        other_sum = int(m_other_sum.group(1))
        if count == 0 or total % count != 0:
            return None
        price = total // count
        if other_sum % price != 0:
            return None
        other_count = other_sum // price
        return join_explanation_lines(
            f"Краткое условие: {count} предметов - {total} руб., ? предметов - {other_sum} руб.",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем цену одного предмета: {total} : {count} = {price} руб.",
            f"Потом узнаем количество: {other_sum} : {price} = {other_count}",
            f"Ответ: {other_count}",
        )

    # Сначала узнаём цену двух товаров при одинаковом количестве, потом сравниваем.
    m_compare = re.search(r"за\s+(\d+)\s+[а-яё\- ]+?\s+заплатил\w*\s+(\d+)\s*руб[^.?!]*за\s+столько\s+же\s+[а-яё\- ]+?\s+заплатил\w*\s+(\d+)\s*руб", lower)
    if m_compare and "на сколько" in question:
        count = int(m_compare.group(1))
        total_a = int(m_compare.group(2))
        total_b = int(m_compare.group(3))
        if count == 0 or total_a % count != 0 or total_b % count != 0:
            return None
        price_a = total_a // count
        price_b = total_b // count
        diff = abs(price_a - price_b)
        return join_explanation_lines(
            f"Краткое условие: {count} предметов - {total_a} руб. и {total_b} руб.",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем цену первого предмета: {total_a} : {count} = {price_a}",
            f"Потом узнаем цену второго предмета: {total_b} : {count} = {price_b}",
            f"Теперь узнаем разницу: {max(price_a, price_b)} - {min(price_a, price_b)} = {diff}",
            f"Ответ: {diff} руб.",
        )

    # Равная цена набора или пропорциональная оплата по одинаковой цене.
    m_total_money = re.search(r"(?:заплатили|выписали\s+на|уплатили)\s+(?:за\s+всю\s+покупку\s+)?(?:на\s+)?(\d+)\s*руб", lower)
    m_counts = re.search(r"(\d+)\s+[а-яё\- ]+?\s+и\s+(\d+)\s+[а-яё\- ]+", lower)
    if m_total_money and m_counts and (_v14_has(question, "каждая", "каждой", "каждый") or _v14_has(lower, "цена", "одинаков")):
        total_money = int(m_total_money.group(1))
        first_count = int(m_counts.group(1))
        second_count = int(m_counts.group(2))
        if first_count + second_count == 0 or total_money % (first_count + second_count) != 0:
            return None
        price = total_money // (first_count + second_count)
        first_total = first_count * price
        second_total = second_count * price
        return join_explanation_lines(
            f"Краткое условие: первая часть - {first_count} наб., вторая часть - {second_count} наб., всего - {total_money} руб.",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько всего наборов: {first_count} + {second_count} = {first_count + second_count}",
            f"Потом узнаем цену одного набора: {total_money} : {first_count + second_count} = {price} руб.",
            f"Теперь узнаем стоимость первой части: {price} × {first_count} = {first_total} руб.",
            f"И стоимость второй части: {price} × {second_count} = {second_total} руб.",
            f"Ответ: первая часть - {first_total} руб., вторая часть - {second_total} руб.",
        )

    # Приведение к единице по массе/длине/объёму.
    m_measure = re.search(r"в\s+(\d+)\s+[а-яё\- ]+?\s+(\d+)\s*(кг|л|м)\b", lower)
    q_measure = re.search(r"(?:чтобы|если|сколько\s+потребуется)[^.?!]*?(\d+)\s*(кг|л|м)\b", question)
    if m_measure and q_measure:
        count = int(m_measure.group(1))
        total = int(m_measure.group(2))
        unit = m_measure.group(3)
        needed = int(q_measure.group(1))
        if count == 0 or total % count != 0:
            return None
        per_part = total // count
        if needed % per_part != 0:
            return None
        answer = needed // per_part
        return join_explanation_lines(
            f"Краткое условие: {count} частей - {total} {unit}, ? частей - {needed} {q_measure.group(2)}",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько в 1 части: {total} : {count} = {per_part} {unit}",
            f"Потом узнаем количество частей: {needed} : {per_part} = {answer}",
            f"Ответ: {answer}",
        )

    # Масса балки по длине.
    m_beam = re.search(r"длиной\s+(\d+)\s*(?:метр|метра|метров|м)[^.?!]*весит\s+(\d+)\s*кг[^.?!]*длиной\s+(\d+)\s*(?:метр|метра|метров|м)", lower)
    if m_beam and _v14_has(question, "сколько весит"):
        first_len = int(m_beam.group(1))
        first_weight = int(m_beam.group(2))
        second_len = int(m_beam.group(3))
        if first_len == 0 or first_weight % first_len != 0:
            return None
        per_meter = first_weight // first_len
        result = per_meter * second_len
        return join_explanation_lines(
            f"Краткое условие: {first_len} м - {first_weight} кг, {second_len} м - ? кг",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем массу 1 м: {first_weight} : {first_len} = {per_meter} кг",
            f"Потом узнаем массу {second_len} м: {per_meter} × {second_len} = {result} кг",
            f"Ответ: {result} кг.",
        )

    return None



def try_local_fraction_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    frac = re.search(r"(\d+)\s*/\s*(\d+)", lower)

    if frac:
        num = int(frac.group(1))
        den = int(frac.group(2))
        if den == 0:
            return None
        other_numbers = _v14_numbers_without_first_fraction(lower)

        # Часть от числа.
        if other_numbers and not _v14_has(lower, "это") and not _v14_has(question, "сколько было") and not _v14_has(question, "какова длина") and not _v14_has(question, "какое расстояние"):
            total = other_numbers[0]
            part = Fraction(total * num, den)
            if not _v14_is_integer_fraction(part):
                return None

            if _v14_has(question, "остал", "во второй день", "во 2 день") or _v14_has(lower, "потрат", "израсход", "использ", "в первый день"):
                remainder = total - part.numerator
                return join_explanation_lines(
                    f"Краткое условие: всего {total}, использовали {num}/{den}, осталось - ?",
                    "Сразу ответить на вопрос нельзя.",
                    f"Сначала узнаем, сколько составляет {num}/{den} числа: {total} : {den} × {num} = {part.numerator}",
                    f"Потом узнаем остаток: {total} - {part.numerator} = {remainder}",
                    f"Ответ: {remainder}",
                )

            return join_explanation_lines(
                f"Краткое условие: целое - {total}, нужно найти {num}/{den} этого числа",
                "Правило: чтобы найти часть от числа, делим число на знаменатель и умножаем на числитель",
                f"{total} : {den} × {num} = {part.numerator}",
                f"Ответ: {part.numerator}",
            )

        # Число по его части: «это 2/3 всего пути».
        if other_numbers and _v14_has(lower, "это") and _v14_has(question, "какое", "сколько", "какова"):
            part_value = other_numbers[0]
            whole = Fraction(part_value * den, num)
            if not _v14_is_integer_fraction(whole):
                return None
            return join_explanation_lines(
                f"Краткое условие: {part_value} - это {num}/{den} целого",
                "Правило: чтобы найти число по его части, делим на числитель и умножаем на знаменатель",
                f"{part_value} : {num} × {den} = {whole.numerator}",
                f"Ответ: {whole.numerator}",
            )

        # Если известен остаток после расходования части.
        if other_numbers and _v14_has(question, "сколько", "какова") and _v14_has(lower, "остал"):
            remaining_value = other_numbers[0]
            remain_num = den - num
            if remain_num <= 0:
                return None
            whole = Fraction(remaining_value * den, remain_num)
            if not _v14_is_integer_fraction(whole):
                return None
            return join_explanation_lines(
                f"Краткое условие: израсходовали {num}/{den}, осталось {remaining_value}",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, какая часть осталась: 1 - {num}/{den} = {remain_num}/{den}",
                f"Потом узнаем всё число: {remaining_value} : {remain_num} × {den} = {whole.numerator}",
                f"Ответ: {whole.numerator}",
            )

    if "половин" in lower:
        nums = extract_ordered_numbers(lower)
        if nums and _v14_has(question, "какова", "какой", "сколько"):
            whole = nums[0] * 2
            return join_explanation_lines(
                f"Краткое условие: 1/2 числа равна {nums[0]}",
                "Правило: чтобы найти целое по половине, умножаем на 2",
                f"{nums[0]} × 2 = {whole}",
                f"Ответ: {whole}",
            )

    return None



def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Простые задачи на S = v × t, v = S : t, t = S : v.
    m_distance = re.search(r"скорост[ьяию]+\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?\b(?:за|в течение)\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
    if m_distance and _v14_question_asks_distance(question):
        speed = int(m_distance.group(1))
        speed_unit = m_distance.group(2)
        time = int(m_distance.group(3))
        distance = speed * time
        dist_unit = speed_unit.split("/")[0]
        time_label = "ч" if speed_unit.endswith("ч") else "мин"
        return join_explanation_lines(
            f"Краткое условие: v = {speed} {speed_unit}, t = {time} {time_label}, S = ?",
            "Правило: чтобы найти расстояние, скорость умножаем на время",
            f"{speed} × {time} = {distance}",
            f"Ответ: {distance} {dist_unit}.",
        )

    m_speed = re.search(r"за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?(?:проехал|прош[её]л|пролетел|проплыл|пробежал)\s+(\d+)\s*(км|м|см)", lower)
    if m_speed and _v14_question_asks_speed(question):
        time = int(m_speed.group(1))
        time_unit = m_speed.group(2)
        distance = int(m_speed.group(3))
        dist_unit = m_speed.group(4)
        if time == 0 or distance % time != 0:
            return None
        speed = distance // time
        speed_unit = _v14_speed_unit(dist_unit, time_unit)
        time_label = "ч" if time_unit.startswith("ч") else "мин"
        return join_explanation_lines(
            f"Краткое условие: S = {distance} {dist_unit}, t = {time} {time_label}, v = ?",
            "Правило: чтобы найти скорость, расстояние делим на время",
            f"{distance} : {time} = {speed}",
            f"Ответ: {speed} {speed_unit}.",
        )

    m_time = re.search(r"скорост[ьяию]+\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?(?:прош[её]л|проехал|пролетел|проплыл|пробежал)\s+(\d+)\s*(км|м|см)", lower)
    if m_time and _v14_question_asks_time(question):
        speed = int(m_time.group(1))
        speed_unit = m_time.group(2)
        distance = int(m_time.group(3))
        dist_unit = m_time.group(4)
        if speed == 0 or distance % speed != 0:
            return None
        time = distance // speed
        time_label = "ч" if speed_unit.endswith("ч") else "мин"
        return join_explanation_lines(
            f"Краткое условие: v = {speed} {speed_unit}, S = {distance} {dist_unit}, t = ?",
            "Правило: чтобы найти время, расстояние делим на скорость",
            f"{distance} : {speed} = {time}",
            f"Ответ: {time} {time_label}.",
        )

    # Навстречу или в противоположных направлениях: общая скорость и расстояние.
    if (_v14_has(lower, "навстречу", "в противоположных направлениях") and _v14_question_asks_distance(question)):
        speed_values = [int(value) for value in re.findall(r"скорост[ьяию]+\s+(\d+)", lower)]
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов)", lower)
        if len(speed_values) >= 2 and time_match:
            speed1, speed2 = speed_values[:2]
            time = int(time_match.group(1))
            total_speed = speed1 + speed2
            distance = total_speed * time
            rate_name = "скорость сближения" if "навстречу" in lower else "скорость удаления"
            return join_explanation_lines(
                f"Краткое условие: v1 = {speed1} км/ч, v2 = {speed2} км/ч, t = {time} ч, S = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем {rate_name}: {speed1} + {speed2} = {total_speed} км/ч",
                f"Потом узнаем расстояние: {total_speed} × {time} = {distance} км",
                f"Ответ: {distance} км.",
            )

    # Движение в одном направлении, догоняет.
    if _v14_has(lower, "догон", "догонит") and _v14_question_asks_time(question):
        nums = extract_ordered_numbers(lower)
        if len(nums) >= 3:
            distance = nums[0]
            speed1 = nums[1]
            speed2 = nums[2]
            diff = abs(speed1 - speed2)
            if diff == 0 or distance % diff != 0:
                return None
            time = distance // diff
            faster = max(speed1, speed2)
            slower = min(speed1, speed2)
            return join_explanation_lines(
                f"Краткое условие: расстояние между машинами - {distance} км, скорости - {faster} км/ч и {slower} км/ч",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем скорость сближения: {faster} - {slower} = {diff} км/ч",
                f"Потом узнаем время: {distance} : {diff} = {time} ч",
                f"Ответ: {time} ч.",
            )

    return None



def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
        )

    quotient, remainder = divmod(left, right)
    common_zeroes = min(_v12_trailing_zero_count(left), _v12_trailing_zero_count(right))
    if common_zeroes > 0 and remainder == 0:
        reduced_left = left // (10 ** common_zeroes)
        reduced_right = right // (10 ** common_zeroes)
        return join_explanation_lines(
            "Правило: у круглых чисел можно сократить одинаковые нули справа",
            f"{left} : {right} = {reduced_left} : {reduced_right}",
            f"{reduced_left} : {reduced_right} = {quotient}",
            f"Ответ: {quotient}",
        )

    if left < 100 and right < 100 and remainder == 0:
        trial = quotient + 1
        next_product = right * trial
        lines = [
            "Правило: при делении небольших чисел удобно пользоваться подбором и таблицей умножения",
            f"Ищем число, которое при умножении на {right} даёт {left}",
        ]
        if next_product > left:
            lines.append(f"Подходит {quotient}, потому что {quotient} × {right} = {left}, а {trial} × {right} = {next_product}, это уже больше")
        else:
            lines.append(f"Подходит {quotient}, потому что {quotient} × {right} = {left}")
        lines.append(f"Ответ: {quotient}")
        return join_explanation_lines(*lines)

    if left < 100 and right < 100 and remainder != 0:
        fitted = quotient * right
        return join_explanation_lines(
            "Правило: при делении с остатком находим наибольшее подходящее произведение",
            f"Берём {quotient}, потому что {quotient} × {right} = {fitted}",
            f"Находим остаток: {left} - {fitted} = {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
        )

    model = _build_long_division_steps_v9(left, right)
    steps = model.get("steps", [])
    answer_text = str(quotient) if remainder == 0 else f"{quotient}, остаток {remainder}"
    lines = [
        "Правило: в делении столбиком сначала выделяем первое неполное делимое, потом подбираем цифру частного, умножаем, вычитаем и сносим следующую цифру",
    ]
    if steps:
        first = steps[0]
        lines.append(f"Сначала берём первое неполное делимое {first['current']}")
        lines.append(f"Подбираем {first['q_digit']}, потому что {first['q_digit']} × {right} = {first['product']}")
        if first.get("remainder") is not None:
            lines.append(f"Вычитаем: {first['current']} - {first['product']} = {first['remainder']}")
        if len(steps) > 1:
            second = steps[1]
            lines.append(f"Сносим следующую цифру и получаем {second['current']}")
            lines.append(f"Дальше делим так же и получаем частное {quotient}")
    lines.append(f"Ответ: {answer_text}")
    return join_explanation_lines(*lines)



def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    if not text:
        return None

    lower = text.lower()
    question = _v14_question(text).lower()
    unit = geometry_unit(text)

    # Прямые задачи на квадрат.
    m_square_side = re.search(r"сторон[аы]?\s+квадрат[а-я]*\s+(?:равна|=)?\s*(\d+)", lower)
    if "квадрат" in lower and m_square_side and "площад" in question and "периметр" in question:
        side = int(m_square_side.group(1))
        area = side * side
        perimeter = side * 4
        return join_explanation_lines(
            f"Краткое условие: a = {side}",
            f"Сначала узнаем площадь квадрата: {side} × {side} = {area}",
            f"Потом узнаем периметр квадрата: {side} × 4 = {perimeter}",
            f"Ответ: площадь - {with_unit(area, unit, square=True)}, периметр - {with_unit(perimeter, unit)}.",
        )

    if "квадрат" in lower and m_square_side and "площад" in question:
        side = int(m_square_side.group(1))
        area = side * side
        return join_explanation_lines(
            "Правило: площадь квадрата равна произведению стороны на саму себя",
            f"{side} × {side} = {area}",
            f"Ответ: {with_unit(area, unit, square=True)}.",
        )

    if "квадрат" in lower and m_square_side and "периметр" in question:
        side = int(m_square_side.group(1))
        perimeter = side * 4
        return join_explanation_lines(
            "Правило: у квадрата четыре равные стороны",
            f"{side} × 4 = {perimeter}",
            f"Ответ: {with_unit(perimeter, unit)}.",
        )

    # Прямые задачи на прямоугольник.
    m_rect_sides = re.search(r"(?:со\s+сторонами|длина[^\d]*(\d+)[^.?!]*ширина[^\d]*(\d+)|ширина[^\d]*(\d+)[^.?!]*длина[^\d]*(\d+))", lower)
    m_rect_lengths = re.search(r"длин[аы]?[^\d]*(\d+)[^.?!]*ширин[аы]?[^\d]*(\d+)", lower)
    if not m_rect_lengths:
        m_rect_lengths = re.search(r"ширин[аы]?[^\d]*(\d+)[^.?!]*длин[аы]?[^\d]*(\d+)", lower)
        if m_rect_lengths:
            width = int(m_rect_lengths.group(1))
            length = int(m_rect_lengths.group(2))
        else:
            width = length = None
    else:
        length = int(m_rect_lengths.group(1))
        width = int(m_rect_lengths.group(2))

    m_rect_two_numbers = re.search(r"со\s+сторонами\s+(\d+)[^.?!]*?(\d+)", lower)
    if "прямоугольник" in lower and m_rect_two_numbers and (length is None or width is None):
        length = int(m_rect_two_numbers.group(1))
        width = int(m_rect_two_numbers.group(2))

    if "прямоугольник" in lower and length and width and "площад" in question and "периметр" in question:
        area = length * width
        perimeter = 2 * (length + width)
        return join_explanation_lines(
            f"Краткое условие: длина = {length}, ширина = {width}",
            f"Сначала узнаем площадь: {length} × {width} = {area}",
            f"Потом узнаем периметр: ({length} + {width}) × 2 = {perimeter}",
            f"Ответ: площадь - {with_unit(area, unit, square=True)}, периметр - {with_unit(perimeter, unit)}.",
        )

    if "прямоугольник" in lower and length and width and "площад" in question:
        area = length * width
        return join_explanation_lines(
            "Правило: площадь прямоугольника равна длине, умноженной на ширину",
            f"{length} × {width} = {area}",
            f"Ответ: {with_unit(area, unit, square=True)}.",
        )

    if "прямоугольник" in lower and length and width and "периметр" in question:
        perimeter = 2 * (length + width)
        return join_explanation_lines(
            "Правило: периметр прямоугольника равен 2 × (длина + ширина)",
            f"({length} + {width}) × 2 = {perimeter}",
            f"Ответ: {with_unit(perimeter, unit)}.",
        )

    # Обратные задачи на прямоугольник.
    m_rect_area_from_perimeter = re.search(r"периметр[^\d]*(\d+)[^.?!]*длин[аы]?[^\d]*(\d+)", lower)
    if "прямоугольник" in lower and m_rect_area_from_perimeter and "площад" in question:
        perimeter = int(m_rect_area_from_perimeter.group(1))
        length = int(m_rect_area_from_perimeter.group(2))
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        width = half - length
        area = length * width
        return join_explanation_lines(
            f"Краткое условие: P = {perimeter}, длина = {length}, площадь - ?",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем ширину: {perimeter} : 2 = {half}, {half} - {length} = {width}",
            f"Потом узнаем площадь: {length} × {width} = {area}",
            f"Ответ: {with_unit(area, unit, square=True)}.",
        )

    m_rect_perimeter_from_area = re.search(r"площад[^\d]*(\d+)[^.?!]*длин[аы]?[^\d]*(\d+)", lower)
    if "прямоугольник" in lower and m_rect_perimeter_from_area and "периметр" in question:
        area = int(m_rect_perimeter_from_area.group(1))
        length = int(m_rect_perimeter_from_area.group(2))
        if length == 0 or area % length != 0:
            return None
        width = area // length
        perimeter = 2 * (length + width)
        return join_explanation_lines(
            f"Краткое условие: S = {area}, длина = {length}, периметр - ?",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем ширину: {area} : {length} = {width}",
            f"Потом узнаем периметр: ({length} + {width}) × 2 = {perimeter}",
            f"Ответ: {with_unit(perimeter, unit)}.",
        )

    # Найти сторону квадрата по периметру.
    m_square_perimeter = re.search(r"периметр[^\d]*(\d+)", lower)
    if "квадрат" in lower and m_square_perimeter and _v14_has(question, "сторон", "длин"):
        perimeter = int(m_square_perimeter.group(1))
        if perimeter % 4 != 0:
            return None
        side = perimeter // 4
        return join_explanation_lines(
            "Правило: у квадрата все стороны равны, поэтому сторону находим делением периметра на 4",
            f"{perimeter} : 4 = {side}",
            f"Ответ: {with_unit(side, unit)}.",
        )

    # Равный периметр треугольника и квадрата.
    m_triangle = re.search(r"сторон[аы]?\s+равностороннего\s+треугольника\s+(?:равна|=)?\s*(\d+)", lower)
    if "равностороннего треугольника" in lower and "квадрат" in lower and _v14_has(question, "сторон", "длин") and m_triangle:
        triangle_side = int(m_triangle.group(1))
        triangle_perimeter = triangle_side * 3
        if triangle_perimeter % 4 != 0:
            return None
        square_side = triangle_perimeter // 4
        return join_explanation_lines(
            f"Краткое условие: сторона треугольника = {triangle_side}, P квадрата = P треугольника",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем периметр треугольника: {triangle_side} × 3 = {triangle_perimeter}",
            f"Потом узнаем сторону квадрата: {triangle_perimeter} : 4 = {square_side}",
            f"Ответ: {with_unit(square_side, unit)}.",
        )

    return None



async def build_explanation(user_text: str) -> dict:
    inferred_kind = infer_task_kind(user_text)
    local_explanation = None
    local_kind = inferred_kind

    handlers = [
        (try_local_equation_explanation, "equation"),
        (try_local_fraction_word_problem_v14, "word"),
        (try_local_fraction_explanation, "fraction"),
        (try_local_expression_explanation, "expression"),
        (try_local_geometry_explanation, "geometry"),
        (try_local_motion_explanation_v14, "word"),
        (try_local_price_quantity_explanation_v14, "word"),
        (try_local_proportional_split_explanation_v14, "word"),
        (try_local_unknown_part_word_problem_v14, "word"),
        (try_local_compound_word_problem_explanation, "word"),
        (try_local_word_problem_explanation, "word"),
    ]

    for handler, kind_name in handlers:
        try:
            candidate = handler(user_text)
        except Exception:
            candidate = None
        if candidate:
            local_explanation = candidate
            local_kind = kind_name
            break

    if local_explanation:
        return {
            "result": shape_explanation(local_explanation, local_kind),
            "source": "local",
            "validated": True,
        }

    extra_instruction = ""
    if inferred_kind == "word":
        extra_instruction = (
            "Это текстовая задача. Сначала выдели условие и вопрос. "
            "Если задача простая, используй один понятный вывод по образцу «Если ..., то ...». "
            "Если задача составная, только тогда пиши «Сразу ответить на вопрос нельзя.», а потом «Сначала узнаем...», «Потом узнаем...». "
            "Если задача в косвенной форме, сначала переведи её в прямую мысль.\n\n"
        )
    elif inferred_kind == "geometry":
        extra_instruction = "Это задача по геометрии. Сначала назови правило, потом подставь числа и выполни вычисление.\n\n"
    elif inferred_kind == "expression":
        extra_instruction = (
            "Это пример или выражение. Не ставь готовый ответ в первой строке. "
            "Если подходит, используй состав числа, вычисление по частям, десятки и единицы, разрядные слагаемые, подбор, деление круглых чисел или письменный способ.\n\n"
        )
    elif inferred_kind == "fraction":
        extra_instruction = "Это действие с дробями. Сначала посмотри на знаменатели и выбери правильный способ.\n\n"
    elif inferred_kind == "equation":
        extra_instruction = (
            "Это уравнение. Сначала назови неизвестный компонент, потом правило его нахождения, потом вычисление и в конце короткую проверку.\n\n"
        )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_V14},
            {
                "role": "user",
                "content": (
                    "Объясни решение так, чтобы ребёнок мог читать или слушать текст строка за строкой. "
                    "Объяснение должно быть последовательным, школьным и без лишних слов.\n\n"
                    f"{extra_instruction}{user_text}"
                ),
            },
        ],
        "max_tokens": 900,
        "temperature": 0.03,
    }

    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result

    shaped = shape_explanation(llm_result["result"], inferred_kind)
    return {"result": shaped, "source": "llm", "validated": False}

# =========================
# V14.1 fixes after regression pass
# =========================


def _v14_question_asks_plain_quantity(question: str) -> bool:
    q = str(question or "").lower()
    if "сколько" not in q:
        return False
    if any(marker in q for marker in ("на сколько", "во сколько", "сколько всего", "сколько вместе", "сколько осталось", "сколько стало", "сколько теперь")):
        return False
    return True



def try_local_unknown_part_word_problem_v14(raw_text: str) -> Optional[str]:
    lower = _v14_lower(raw_text)
    question = _v14_question(raw_text).lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    if _v14_contains_relation_words(lower):
        return None
    if _v14_question_asks_total(question) or _v14_question_asks_compare(question):
        return None
    if not _v14_question_asks_plain_quantity(question):
        return None
    if _v14_has(lower, "руб", "км/ч", "периметр", "площад", "скорост"):
        return None
    if re.search(r"сколько[^.?!]*\bбыло\b", question) and not _v14_has(question, "на второй", "на первой", "во второй", "во 2", "синего", "другой", "остальные"):
        return None
    cues = (
        "перв", "втор", "из них", "осталь", "на двух", "на обеих", "за два дня", "за 2 дня",
        "вместе", "всего", "нашел", "нашла", "нашли", "прочитал", "прочитала", "прошел", "прошла"
    )
    if not _v14_has(lower, *cues):
        return None
    total = max(nums)
    known = min(nums)
    if total < known:
        return None
    return explain_unknown_addend_word_problem_v14(total, known)



def try_local_fraction_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    frac = re.search(r"(\d+)\s*/\s*(\d+)", lower)

    if frac:
        num = int(frac.group(1))
        den = int(frac.group(2))
        if den == 0:
            return None
        other_numbers = _v14_numbers_without_first_fraction(lower)
        has_exact_eto = bool(re.search(r"\bэто\b", lower))
        asks_initial_amount = bool(re.search(r"сколько[^.?!]*\bбыло\b", question))

        # Число по его части: «это 2/3 всего пути».
        if has_exact_eto and other_numbers and _v14_has(question, "какое", "сколько", "какова"):
            part_value = other_numbers[0]
            whole = Fraction(part_value * den, num)
            if not _v14_is_integer_fraction(whole):
                return None
            return join_explanation_lines(
                f"Краткое условие: {part_value} - это {num}/{den} целого",
                "Правило: чтобы найти число по его части, делим на числитель и умножаем на знаменатель",
                f"{part_value} : {num} × {den} = {whole.numerator}",
                f"Ответ: {whole.numerator}",
            )

        # Если известен остаток после расходования части.
        if other_numbers and asks_initial_amount and _v14_has(lower, "остал"):
            remaining_value = other_numbers[0]
            remain_num = den - num
            if remain_num <= 0:
                return None
            whole = Fraction(remaining_value * den, remain_num)
            if not _v14_is_integer_fraction(whole):
                return None
            return join_explanation_lines(
                f"Краткое условие: израсходовали {num}/{den}, осталось {remaining_value}",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, какая часть осталась: 1 - {num}/{den} = {remain_num}/{den}",
                f"Потом узнаем всё число: {remaining_value} : {remain_num} × {den} = {whole.numerator}",
                f"Ответ: {whole.numerator}",
            )

        # Часть от числа или остаток после нахождения части.
        if other_numbers:
            total = other_numbers[0]
            part = Fraction(total * num, den)
            if not _v14_is_integer_fraction(part):
                return None
            if _v14_has(question, "остал", "во второй день", "во 2 день") or _v14_has(lower, "потрат", "израсход", "использ", "в первый день"):
                remainder = total - part.numerator
                return join_explanation_lines(
                    f"Краткое условие: всего {total}, использовали {num}/{den}, осталось - ?",
                    "Сразу ответить на вопрос нельзя.",
                    f"Сначала узнаем, сколько составляет {num}/{den} числа: {total} : {den} × {num} = {part.numerator}",
                    f"Потом узнаем остаток: {total} - {part.numerator} = {remainder}",
                    f"Ответ: {remainder}",
                )

            return join_explanation_lines(
                f"Краткое условие: целое - {total}, нужно найти {num}/{den} этого числа",
                "Правило: чтобы найти часть от числа, делим число на знаменатель и умножаем на числитель",
                f"{total} : {den} × {num} = {part.numerator}",
                f"Ответ: {part.numerator}",
            )

    if "половин" in lower:
        nums = extract_ordered_numbers(lower)
        if nums and _v14_has(question, "какова", "какой", "сколько"):
            whole = nums[0] * 2
            return join_explanation_lines(
                f"Краткое условие: 1/2 числа равна {nums[0]}",
                "Правило: чтобы найти целое по половине, умножаем на 2",
                f"{nums[0]} × 2 = {whole}",
                f"Ответ: {whole}",
            )

    return None



def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Простые задачи на скорость.
    if _v14_question_asks_speed(question) and not _v14_has(lower, "навстречу", "в противоположных", "догон"):
        m = re.search(r"(?:прош[её]л|проехал|пролетел|проплыл|пробежал)\s+(?:дистанцию\s+)?(\d+)\s*(км|м|см)[^.?!]*?за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        if not m:
            m = re.search(r"за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?(\d+)\s*(км|м|см)", lower)
            if m:
                time = int(m.group(1))
                time_unit = m.group(2)
                distance = int(m.group(3))
                dist_unit = m.group(4)
            else:
                time = time_unit = distance = dist_unit = None
        else:
            distance = int(m.group(1))
            dist_unit = m.group(2)
            time = int(m.group(3))
            time_unit = m.group(4)
        if m and time and distance is not None:
            if time == 0 or distance % time != 0:
                return None
            speed = distance // time
            speed_unit = _v14_speed_unit(dist_unit, time_unit)
            time_label = "ч" if str(time_unit).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: S = {distance} {dist_unit}, t = {time} {time_label}, v = ?",
                "Правило: чтобы найти скорость, расстояние делим на время",
                f"{distance} : {time} = {speed}",
                f"Ответ: {speed} {speed_unit}.",
            )

    # Простые задачи на расстояние.
    if _v14_question_asks_distance(question) and not _v14_has(lower, "навстречу", "в противоположных"):
        m = re.search(r"(?:ехал|ш[её]л|двигал[а-я]*|летел|плыл|ползла|полз|бежал)\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if not m:
            m = re.search(r"со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
            if m:
                speed = int(m.group(1))
                speed_unit = m.group(2)
                time = int(m.group(3))
                time_unit = m.group(4)
            else:
                speed = speed_unit = time = time_unit = None
        else:
            time = int(m.group(1))
            time_unit = m.group(2)
            speed = int(m.group(3))
            speed_unit = m.group(4)
        if m:
            distance = speed * time
            dist_unit = str(speed_unit).split("/")[0]
            time_label = "ч" if str(time_unit).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, t = {time} {time_label}, S = ?",
                "Правило: чтобы найти расстояние, скорость умножаем на время",
                f"{speed} × {time} = {distance}",
                f"Ответ: {distance} {dist_unit}.",
            )

    # Простые задачи на время.
    if _v14_question_asks_time(question) and not _v14_has(lower, "догон"):
        m = re.search(r"(?:прош[её]л|проехал|пролетел|проплыл|пробежал)\s+(\d+)\s*(км|м|см)[^.?!]*?со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if not m:
            m = re.search(r"со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?(\d+)\s*(км|м|см)", lower)
            if m:
                speed = int(m.group(1))
                speed_unit = m.group(2)
                distance = int(m.group(3))
                dist_unit = m.group(4)
            else:
                speed = speed_unit = distance = dist_unit = None
        else:
            distance = int(m.group(1))
            dist_unit = m.group(2)
            speed = int(m.group(3))
            speed_unit = m.group(4)
        if m and speed:
            if distance % speed != 0:
                return None
            time = distance // speed
            time_label = "ч" if str(speed_unit).endswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, S = {distance} {dist_unit}, t = ?",
                "Правило: чтобы найти время, расстояние делим на скорость",
                f"{distance} : {speed} = {time}",
                f"Ответ: {time} {time_label}.",
            )

    # Навстречу или в противоположных направлениях.
    if (_v14_has(lower, "навстречу", "в противоположных направлениях") and _v14_question_asks_distance(question)):
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        if len(speed_matches) >= 2 and time_match:
            speed1 = int(speed_matches[0][0])
            speed2 = int(speed_matches[1][0])
            unit = speed_matches[0][1]
            time = int(time_match.group(1))
            total_speed = speed1 + speed2
            distance = total_speed * time
            distance_unit = unit.split("/")[0]
            rate_name = "скорость сближения" if "навстречу" in lower else "скорость удаления"
            return join_explanation_lines(
                f"Краткое условие: v1 = {speed1} {unit}, v2 = {speed2} {unit}, t = {time}, S = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем {rate_name}: {speed1} + {speed2} = {total_speed} {unit}",
                f"Потом узнаем расстояние: {total_speed} × {time} = {distance} {distance_unit}",
                f"Ответ: {distance} {distance_unit}.",
            )

    # Движение в одном направлении, догоняет.
    if _v14_has(lower, "догон", "догонит") and _v14_question_asks_time(question):
        nums = extract_ordered_numbers(lower)
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if len(nums) >= 3 and len(speed_matches) >= 2:
            distance = nums[0]
            speed1 = int(speed_matches[0][0])
            speed2 = int(speed_matches[1][0])
            unit = speed_matches[0][1]
            diff = abs(speed1 - speed2)
            if diff == 0 or distance % diff != 0:
                return None
            time = distance // diff
            faster = max(speed1, speed2)
            slower = min(speed1, speed2)
            return join_explanation_lines(
                f"Краткое условие: расстояние между машинами - {distance} км, скорости - {faster} {unit} и {slower} {unit}",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем скорость сближения: {faster} - {slower} = {diff} {unit}",
                f"Потом узнаем время: {distance} : {diff} = {time} ч",
                f"Ответ: {time} ч.",
            )

    return None

# =========================
# V14.2 motion pattern fixes
# =========================


def _v14_question_asks_distance(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"каков[ао][^.?!]*расстояни|какое[^.?!]*расстояни|какой[^.?!]*путь|сколько[^.?!]*\b(км|м|см)\b", q))



def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    move_verbs = r"(?:ехал[ао]?|ш[её]л[аи]?|двигал[а-я]*|летел[ао]?|плыл[ао]?|ползл?[ао]?|бежал[ао]?|проехал[ао]?|прош[её]л[аи]?|пролетел[ао]?|проплыл[ао]?|пробежал[ао]?)"

    if _v14_question_asks_speed(question) and not _v14_has(lower, "навстречу", "в противоположных", "догон"):
        m = re.search(rf"{move_verbs}\s+(?:дистанцию\s+)?(\d+)\s*(км|м|см)[^.?!]*?за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        if not m:
            m = re.search(rf"за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?{move_verbs}[^.?!]*?(\d+)\s*(км|м|см)", lower)
            if m:
                time = int(m.group(1))
                time_unit = m.group(2)
                distance = int(m.group(3))
                dist_unit = m.group(4)
            else:
                time = time_unit = distance = dist_unit = None
        else:
            distance = int(m.group(1))
            dist_unit = m.group(2)
            time = int(m.group(3))
            time_unit = m.group(4)
        if m and time and distance is not None:
            if time == 0 or distance % time != 0:
                return None
            speed = distance // time
            speed_unit = _v14_speed_unit(dist_unit, time_unit)
            time_label = "ч" if str(time_unit).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: S = {distance} {dist_unit}, t = {time} {time_label}, v = ?",
                "Правило: чтобы найти скорость, расстояние делим на время",
                f"{distance} : {time} = {speed}",
                f"Ответ: {speed} {speed_unit}.",
            )

    if _v14_question_asks_distance(question) and not _v14_has(lower, "навстречу", "в противоположных"):
        m = re.search(rf"{move_verbs}\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if not m:
            m = re.search(rf"со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?{move_verbs}[^.?!]*?(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
            if m:
                speed = int(m.group(1))
                speed_unit = m.group(2)
                time = int(m.group(3))
                time_unit = m.group(4)
            else:
                speed = speed_unit = time = time_unit = None
        else:
            time = int(m.group(1))
            time_unit = m.group(2)
            speed = int(m.group(3))
            speed_unit = m.group(4)
        if m:
            distance = speed * time
            dist_unit = str(speed_unit).split("/")[0]
            time_label = "ч" if str(time_unit).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, t = {time} {time_label}, S = ?",
                "Правило: чтобы найти расстояние, скорость умножаем на время",
                f"{speed} × {time} = {distance}",
                f"Ответ: {distance} {dist_unit}.",
            )

    if _v14_question_asks_time(question) and not _v14_has(lower, "догон"):
        m = re.search(rf"{move_verbs}\s+(\d+)\s*(км|м|см)[^.?!]*?со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if not m:
            m = re.search(rf"со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?{move_verbs}[^.?!]*?(\d+)\s*(км|м|см)", lower)
            if m:
                speed = int(m.group(1))
                speed_unit = m.group(2)
                distance = int(m.group(3))
                dist_unit = m.group(4)
            else:
                speed = speed_unit = distance = dist_unit = None
        else:
            distance = int(m.group(1))
            dist_unit = m.group(2)
            speed = int(m.group(3))
            speed_unit = m.group(4)
        if m and speed:
            if distance % speed != 0:
                return None
            time = distance // speed
            time_label = "ч" if str(speed_unit).endswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, S = {distance} {dist_unit}, t = ?",
                "Правило: чтобы найти время, расстояние делим на скорость",
                f"{distance} : {speed} = {time}",
                f"Ответ: {time} {time_label}.",
            )

    if (_v14_has(lower, "навстречу", "в противоположных направлениях") and _v14_question_asks_distance(question)):
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        if len(speed_matches) >= 2 and time_match:
            speed1 = int(speed_matches[0][0])
            speed2 = int(speed_matches[1][0])
            unit = speed_matches[0][1]
            time = int(time_match.group(1))
            total_speed = speed1 + speed2
            distance = total_speed * time
            distance_unit = unit.split("/")[0]
            time_label = "ч" if time_match.group(2).startswith("ч") else "мин"
            rate_name = "скорость сближения" if "навстречу" in lower else "скорость удаления"
            return join_explanation_lines(
                f"Краткое условие: v1 = {speed1} {unit}, v2 = {speed2} {unit}, t = {time} {time_label}, S = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем {rate_name}: {speed1} + {speed2} = {total_speed} {unit}",
                f"Потом узнаем расстояние: {total_speed} × {time} = {distance} {distance_unit}",
                f"Ответ: {distance} {distance_unit}.",
            )

    if _v14_has(lower, "догон", "догонит") and _v14_question_asks_time(question):
        nums = extract_ordered_numbers(lower)
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if len(nums) >= 3 and len(speed_matches) >= 2:
            distance = nums[0]
            speed1 = int(speed_matches[0][0])
            speed2 = int(speed_matches[1][0])
            unit = speed_matches[0][1]
            diff = abs(speed1 - speed2)
            if diff == 0 or distance % diff != 0:
                return None
            time = distance // diff
            faster = max(speed1, speed2)
            slower = min(speed1, speed2)
            return join_explanation_lines(
                f"Краткое условие: расстояние между машинами - {distance} км, скорости - {faster} {unit} и {slower} {unit}",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем скорость сближения: {faster} - {slower} = {diff} {unit}",
                f"Потом узнаем время: {distance} : {diff} = {time} ч",
                f"Ответ: {time} ч.",
            )

    return None

# =========================
# V14.3 extra motion cases
# =========================


def _v14_question_asks_time(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"сколько[^.?!]*\b(ч|час|часа|часов|мин|минут|минуты)\b|сколько[^.?!]*времени|какое[^.?!]*время", q))



def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    move_verbs = r"(?:ехал[ао]?|ш[её]л[аи]?|двигал[а-я]*|летел[ао]?|плыл[ао]?|ползл?[ао]?|бежал[ао]?|проехал[ао]?|прош[её]л[аи]?|пролетел[ао]?|проплыл[ао]?|пробежал[ао]?)"

    # 1. Простые задачи на скорость.
    if _v14_question_asks_speed(question) and not _v14_has(lower, "навстречу", "в противоположных", "догон"):
        m = re.search(rf"{move_verbs}\s+(?:дистанцию\s+)?(\d+)\s*(км|м|см)[^.?!]*?за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        if not m:
            m = re.search(rf"за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?{move_verbs}[^.?!]*?(\d+)\s*(км|м|см)", lower)
            if m:
                time = int(m.group(1)); time_unit = m.group(2); distance = int(m.group(3)); dist_unit = m.group(4)
            else:
                time = time_unit = distance = dist_unit = None
        else:
            distance = int(m.group(1)); dist_unit = m.group(2); time = int(m.group(3)); time_unit = m.group(4)
        if m and time and distance is not None:
            if time == 0 or distance % time != 0:
                return None
            speed = distance // time
            speed_unit = _v14_speed_unit(dist_unit, time_unit)
            time_label = "ч" if str(time_unit).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: S = {distance} {dist_unit}, t = {time} {time_label}, v = ?",
                "Правило: чтобы найти скорость, расстояние делим на время",
                f"{distance} : {time} = {speed}",
                f"Ответ: {speed} {speed_unit}.",
            )

    # 2. Простые задачи на расстояние.
    if _v14_question_asks_distance(question) and not _v14_has(lower, "навстречу", "в противоположных"):
        m = re.search(rf"{move_verbs}\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)[^.?!]*?со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if not m:
            m = re.search(rf"со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?{move_verbs}[^.?!]*?(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
            if m:
                speed = int(m.group(1)); speed_unit = m.group(2); time = int(m.group(3)); time_unit = m.group(4)
            else:
                speed = speed_unit = time = time_unit = None
        else:
            time = int(m.group(1)); time_unit = m.group(2); speed = int(m.group(3)); speed_unit = m.group(4)
        if m:
            distance = speed * time
            dist_unit = str(speed_unit).split("/")[0]
            time_label = "ч" if str(time_unit).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, t = {time} {time_label}, S = ?",
                "Правило: чтобы найти расстояние, скорость умножаем на время",
                f"{speed} × {time} = {distance}",
                f"Ответ: {distance} {dist_unit}.",
            )

    # 3. Простые задачи на время.
    if _v14_question_asks_time(question) and not _v14_has(lower, "догон"):
        m = re.search(rf"{move_verbs}\s+(\d+)\s*(км|м|см)[^.?!]*?со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if not m:
            m = re.search(rf"со\s+скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)[^.?!]*?{move_verbs}[^.?!]*?(\d+)\s*(км|м|см)", lower)
            if m:
                speed = int(m.group(1)); speed_unit = m.group(2); distance = int(m.group(3)); dist_unit = m.group(4)
            else:
                speed = speed_unit = distance = dist_unit = None
        else:
            distance = int(m.group(1)); dist_unit = m.group(2); speed = int(m.group(3)); speed_unit = m.group(4)
        if m and speed:
            if distance % speed != 0:
                return None
            time = distance // speed
            time_label = "ч" if str(speed_unit).endswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, S = {distance} {dist_unit}, t = ?",
                "Правило: чтобы найти время, расстояние делим на скорость",
                f"{distance} : {speed} = {time}",
                f"Ответ: {time} {time_label}.",
            )

    # 4. Навстречу или в противоположных направлениях: расстояние по общей скорости.
    if (_v14_has(lower, "навстречу", "в противоположных направлениях") and _v14_question_asks_distance(question)):
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        if len(speed_matches) >= 2 and time_match:
            speed1 = int(speed_matches[0][0]); speed2 = int(speed_matches[1][0]); unit = speed_matches[0][1]
            time = int(time_match.group(1))
            total_speed = speed1 + speed2
            distance = total_speed * time
            distance_unit = unit.split("/")[0]
            time_label = "ч" if time_match.group(2).startswith("ч") else "мин"
            rate_name = "скорость сближения" if "навстречу" in lower else "скорость удаления"
            return join_explanation_lines(
                f"Краткое условие: v1 = {speed1} {unit}, v2 = {speed2} {unit}, t = {time} {time_label}, S = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем {rate_name}: {speed1} + {speed2} = {total_speed} {unit}",
                f"Потом узнаем расстояние: {total_speed} × {time} = {distance} {distance_unit}",
                f"Ответ: {distance} {distance_unit}.",
            )

    # 5. В противоположных направлениях: известны общее расстояние, время и скорость первого, ищем скорость второго.
    if _v14_has(lower, "в противоположных направлениях") and _v14_question_asks_speed(question):
        total_distance_match = re.search(r"расстояние[^\d]*(\d+)\s*(км|м|см)", lower)
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", lower)
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if total_distance_match and time_match and speed_matches:
            total_distance = int(total_distance_match.group(1))
            first_speed = int(speed_matches[0][0])
            unit = speed_matches[0][1]
            time = int(time_match.group(1))
            first_distance = first_speed * time
            second_distance = total_distance - first_distance
            if time == 0 or second_distance < 0 or second_distance % time != 0:
                return None
            second_speed = second_distance // time
            return join_explanation_lines(
                f"Краткое условие: S = {total_distance} {total_distance_match.group(2)}, v1 = {first_speed} {unit}, t = {time} ч, v2 = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем путь первого участника: {first_speed} × {time} = {first_distance}",
                f"Потом узнаем путь второго участника: {total_distance} - {first_distance} = {second_distance}",
                f"Теперь узнаем скорость второго участника: {second_distance} : {time} = {second_speed}",
                f"Ответ: {second_speed} {unit}.",
            )

    # 6. Навстречу: известны общее расстояние, скорость первого и его путь, ищем скорость второго.
    if _v14_has(lower, "навстречу") and _v14_question_asks_speed(question):
        nums = extract_ordered_numbers(lower)
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        total_distance_match = re.search(r"расстояние[^\d]*(\d+)\s*(км|м|см)", lower)
        path_match = re.search(r"прош[её]л[^\d]*(\d+)\s*(км|м|см)", lower)
        if total_distance_match and path_match and speed_matches:
            total_distance = int(total_distance_match.group(1))
            first_speed = int(speed_matches[0][0])
            unit = speed_matches[0][1]
            first_distance = int(path_match.group(1))
            if first_speed == 0 or first_distance % first_speed != 0:
                return None
            time = first_distance // first_speed
            second_distance = total_distance - first_distance
            if second_distance < 0 or time == 0 or second_distance % time != 0:
                return None
            second_speed = second_distance // time
            return join_explanation_lines(
                f"Краткое условие: S = {total_distance} {total_distance_match.group(2)}, v1 = {first_speed} {unit}, S1 = {first_distance}, v2 = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем время движения до встречи: {first_distance} : {first_speed} = {time}",
                f"Потом узнаем путь второго участника: {total_distance} - {first_distance} = {second_distance}",
                f"Теперь узнаем его скорость: {second_distance} : {time} = {second_speed}",
                f"Ответ: {second_speed} {unit}.",
            )

    # 7. Навстречу: скорость второго на несколько единиц больше, время известно, надо найти расстояние.
    if _v14_has(lower, "навстречу") and _v14_question_asks_distance(question):
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов)", lower)
        first_speed_match = re.search(r"скорость\s+одного[^\d]*(\d+)\s*(км/час|км/ч)", lower)
        delta_match = re.search(r"на\s+(\d+)\s*(км/час|км/ч)?\s*больше", lower)
        if time_match and first_speed_match and delta_match:
            time = int(time_match.group(1))
            first_speed = int(first_speed_match.group(1))
            delta = int(delta_match.group(1))
            second_speed = first_speed + delta
            first_distance = first_speed * time
            second_distance = second_speed * time
            total_distance = first_distance + second_distance
            return join_explanation_lines(
                f"Краткое условие: v1 = {first_speed} км/ч, v2 на {delta} км/ч больше, t = {time} ч, S = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем скорость второго участника: {first_speed} + {delta} = {second_speed} км/ч",
                f"Потом узнаем путь первого: {first_speed} × {time} = {first_distance} км",
                f"Потом узнаем путь второго: {second_speed} × {time} = {second_distance} км",
                f"Теперь узнаем расстояние между пунктами: {first_distance} + {second_distance} = {total_distance} км",
                f"Ответ: {total_distance} км.",
            )

    # 8. Движение в одном направлении, догоняет.
    if _v14_has(lower, "догон", "догонит") and _v14_question_asks_time(question):
        nums = extract_ordered_numbers(lower)
        speed_matches = re.findall(r"(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        if len(nums) >= 3 and len(speed_matches) >= 2:
            distance = nums[0]
            speed1 = int(speed_matches[0][0])
            speed2 = int(speed_matches[1][0])
            unit = speed_matches[0][1]
            diff = abs(speed1 - speed2)
            if diff == 0 or distance % diff != 0:
                return None
            time = distance // diff
            faster = max(speed1, speed2)
            slower = min(speed1, speed2)
            return join_explanation_lines(
                f"Краткое условие: расстояние между машинами - {distance} км, скорости - {faster} {unit} и {slower} {unit}",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем скорость сближения: {faster} - {slower} = {diff} {unit}",
                f"Потом узнаем время: {distance} : {diff} = {time} ч",
                f"Ответ: {time} ч.",
            )

    return None

# =========================
# V14.4 question intent fix
# =========================


def _v14_question_asks_distance(question: str) -> bool:
    q = str(question or "").lower()
    return bool(re.search(r"найд[а-я]*[^.?!]*расстояни|каков[ао][^.?!]*расстояни|какое[^.?!]*расстояни|какой[^.?!]*путь|сколько[^.?!]*\b(км|м|см)\b", q))

# =========================
# V14.5 motion wrapper for relative speed cases
# =========================

_v14_motion_handler_base = try_local_motion_explanation_v14


def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Навстречу: скорость второго на несколько единиц больше, время известно, надо найти расстояние.
    if _v14_has(lower, "навстречу") and _v14_question_asks_distance(question):
        time_match = re.search(r"через\s+(\d+)\s*(ч|час|часа|часов)", lower)
        first_speed_match = re.search(r"скорость\s+одного[^\d]*(\d+)\s*(км/час|км/ч)", lower)
        delta_match = re.search(r"на\s+(\d+)\s*(км/час|км/ч)?\s*больше", lower)
        if time_match and first_speed_match and delta_match:
            time = int(time_match.group(1))
            first_speed = int(first_speed_match.group(1))
            delta = int(delta_match.group(1))
            second_speed = first_speed + delta
            first_distance = first_speed * time
            second_distance = second_speed * time
            total_distance = first_distance + second_distance
            return join_explanation_lines(
                f"Краткое условие: v1 = {first_speed} км/ч, v2 на {delta} км/ч больше, t = {time} ч, S = ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем скорость второго участника: {first_speed} + {delta} = {second_speed} км/ч",
                f"Потом узнаем путь первого: {first_speed} × {time} = {first_distance} км",
                f"Потом узнаем путь второго: {second_speed} × {time} = {second_distance} км",
                f"Теперь узнаем расстояние между городами: {first_distance} + {second_distance} = {total_distance} км",
                f"Ответ: {total_distance} км.",
            )

    return _v14_motion_handler_base(raw_text)

# =========================
# V14.6 book-pattern compound tasks
# =========================


def try_local_book_compound_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    nums = extract_ordered_numbers(lower)

    # Сложили два количества, потом вычли ушедшую часть.
    if len(nums) == 3 and _v14_has(question, "остал") and _v14_has(lower, "и", "уехал", "уехало", "ушло", "съели", "продали", "взяли") and "по" not in lower:
        first, second, removed = nums
        total = first + second
        if total >= removed:
            left = total - removed
            return join_explanation_lines(
                f"Краткое условие: было {first} и {second}, ушло {removed}, осталось - ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, сколько было всего: {first} + {second} = {total}",
                f"Потом узнаем, сколько осталось: {total} - {removed} = {left}",
                f"Ответ: {left}",
            )

    # Из общего количества вычитаем две известные части.
    if len(nums) == 3 and _v14_has(lower, "несколько") and _v14_question_asks_plain_quantity(question):
        total, first, second = nums[0], nums[1], nums[2]
        unknown = total - first - second
        if unknown >= 0:
            return join_explanation_lines(
                f"Краткое условие: всего {total}, известно {first} и {second}, неизвестная часть - ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, сколько составляют известные части: {first} + {second} = {first + second}",
                f"Потом узнаем неизвестную часть: {total} - {first + second} = {unknown}",
                f"Ответ: {unknown}",
            )

    # Поровну: найти количество в одной группе.
    if len(nums) == 2 and _v14_has(lower, "поровну") and _v14_has(question, "кажд"):
        groups, total = nums[0], nums[1]
        if groups > 0 and total % groups == 0:
            each = total // groups
            return join_explanation_lines(
                f"Краткое условие: {groups} групп - {total}, в 1 группе - ?",
                "Правило: чтобы узнать, сколько в одной группе, делим общее количество на число групп",
                f"{total} : {groups} = {each}",
                f"Ответ: {each}",
            )

    # По нескольким одинаковым группам находим другое количество или число групп.
    if len(nums) == 3 and not _v14_contains_relation_words(lower):
        first_groups, first_total, target = nums[0], nums[1], nums[2]
        if first_groups > 0 and first_total % first_groups == 0:
            per_group = first_total // first_groups
            if _v14_has(question, "таких же", "в ") and _v14_question_asks_plain_quantity(question):
                result = per_group * target
                return join_explanation_lines(
                    f"Краткое условие: {first_groups} групп - {first_total}, {target} групп - ?",
                    "Сразу ответить на вопрос нельзя.",
                    f"Сначала узнаем, сколько в 1 группе: {first_total} : {first_groups} = {per_group}",
                    f"Потом узнаем, сколько будет в {target} группах: {per_group} × {target} = {result}",
                    f"Ответ: {result}",
                )
            if _v14_has(question, "в скольких", "сколько потребуется") and target % per_group == 0:
                groups_needed = target // per_group
                return join_explanation_lines(
                    f"Краткое условие: {first_groups} групп - {first_total}, ? групп - {target}",
                    "Сразу ответить на вопрос нельзя.",
                    f"Сначала узнаем, сколько в 1 группе: {first_total} : {first_groups} = {per_group}",
                    f"Потом узнаем число групп: {target} : {per_group} = {groups_needed}",
                    f"Ответ: {groups_needed}",
                )

    # Привезли по ящикам, часть продали, найти остаток.
    m_minus_sold = re.search(r"(\d+)\s+[а-яё\- ]+?по\s+(\d+)\s*(кг|л|м)?[^.?!]*?(?:продали|израсходовали|использовали|съели)\s+(\d+)", lower)
    if m_minus_sold and _v14_has(question, "остал"):
        groups = int(m_minus_sold.group(1))
        per_group = int(m_minus_sold.group(2))
        sold = int(m_minus_sold.group(4))
        total = groups * per_group
        left = total - sold
        unit = m_minus_sold.group(3) or ""
        return join_explanation_lines(
            f"Краткое условие: {groups} групп по {per_group}{(' ' + unit) if unit else ''}, продали {sold}{(' ' + unit) if unit else ''}, осталось - ?",
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько было всего: {groups} × {per_group} = {total}",
            f"Потом узнаем остаток: {total} - {sold} = {left}",
            f"Ответ: {with_unit(left, unit)}.",
        )

    # Сумма двух произведений.
    pair_matches = re.findall(r"(\d+)\s+[а-яё\- ]+?по\s+(\d+)\s*(руб|кг|л|м)?", lower)
    if len(pair_matches) >= 2 and (_v14_question_asks_total(question) or _v14_has(question, "сколько стоила", "сколько кг", "сколько было", "сколько фруктов")):
        g1, p1, unit1 = pair_matches[0]
        g2, p2, unit2 = pair_matches[1]
        g1 = int(g1); p1 = int(p1); g2 = int(g2); p2 = int(p2)
        first_total = g1 * p1
        second_total = g2 * p2
        total = first_total + second_total
        unit = unit1 or unit2 or ("руб" if "руб" in lower else "")
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем первую часть: {g1} × {p1} = {first_total}",
            f"Потом узнаем вторую часть: {g2} × {p2} = {second_total}",
            f"Теперь узнаем всё вместе: {first_total} + {second_total} = {total}",
            f"Ответ: {with_unit(total, unit)}.",
        )

    # Из общей суммы вычитаем известную покупку и находим цену второй.
    m_unknown_price = re.search(r"(\d+)\s+[а-яё\- ]+?по\s+(\d+)\s*руб[^.?!]*?и\s+(\d+)\s+[а-яё\- ]+?[^.?!]*?за\s+вс[её]\s+заплатили\s+(\d+)\s*руб", lower)
    if m_unknown_price and re.search(r"сколько\s+стоила?\s+1", question):
        known_count = int(m_unknown_price.group(1))
        known_price = int(m_unknown_price.group(2))
        unknown_count = int(m_unknown_price.group(3))
        total_money = int(m_unknown_price.group(4))
        known_total = known_count * known_price
        unknown_total = total_money - known_total
        if unknown_count == 0 or unknown_total < 0 or unknown_total % unknown_count != 0:
            return None
        price = unknown_total // unknown_count
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем стоимость известной покупки: {known_count} × {known_price} = {known_total} руб.",
            f"Потом узнаем стоимость второй покупки: {total_money} - {known_total} = {unknown_total} руб.",
            f"Теперь узнаем цену 1 предмета: {unknown_total} : {unknown_count} = {price} руб.",
            f"Ответ: {price} руб.",
        )

    # В каждой клетке по ... и ... , всего ... Найти число клеток.
    m_cages = re.search(r"в\s+каждой[^\d]*по\s+(\d+)[^.?!]*?и\s+(\d+)[^.?!]*?всего[^\d]*(\d+)", lower)
    if m_cages and _v14_question_asks_plain_quantity(question):
        first = int(m_cages.group(1))
        second = int(m_cages.group(2))
        total = int(m_cages.group(3))
        per_group = first + second
        if per_group == 0 or total % per_group != 0:
            return None
        groups = total // per_group
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько попугаев в 1 клетке: {first} + {second} = {per_group}",
            f"Потом узнаем число клеток: {total} : {per_group} = {groups}",
            f"Ответ: {groups}",
        )

    # Общие деньги делим на цену одного предмета.
    m_shared_money = re.search(r"(\d+)\s*руб[^\d]+(\d+)\s*руб[^.?!]*?стоит\s+(\d+)\s*руб", lower)
    if m_shared_money and _v14_question_asks_plain_quantity(question):
        first_money = int(m_shared_money.group(1))
        second_money = int(m_shared_money.group(2))
        price = int(m_shared_money.group(3))
        total_money = first_money + second_money
        if price == 0 or total_money % price != 0:
            return None
        count = total_money // price
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько денег у ребят вместе: {first_money} + {second_money} = {total_money} руб.",
            f"Потом узнаем, сколько предметов можно купить: {total_money} : {price} = {count}",
            f"Ответ: {count}",
        )

    # Скорость на оставшейся части пути.
    m_rest_speed = re.search(r"(\d+)\s*км[^.?!]*?первые\s+(\d+)\s*час[^.?!]*?скоростью\s+(\d+)\s*км/час[^.?!]*?за\s+(\d+)\s*час", lower)
    if m_rest_speed and _v14_question_asks_speed(question):
        total_distance = int(m_rest_speed.group(1))
        first_time = int(m_rest_speed.group(2))
        first_speed = int(m_rest_speed.group(3))
        second_time = int(m_rest_speed.group(4))
        first_distance = first_time * first_speed
        second_distance = total_distance - first_distance
        if second_time == 0 or second_distance < 0 or second_distance % second_time != 0:
            return None
        second_speed = second_distance // second_time
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, какой путь прошли за первые {first_time} ч: {first_speed} × {first_time} = {first_distance} км",
            f"Потом узнаем, сколько осталось пройти: {total_distance} - {first_distance} = {second_distance} км",
            f"Теперь узнаем скорость на остальном пути: {second_distance} : {second_time} = {second_speed} км/ч",
            f"Ответ: {second_speed} км/ч.",
        )

    # За то же время движется второй участник.
    m_same_time = re.search(r"(\d+)\s*(м|см|км)[^.?!]*?скоростью\s+(\d+)\s*(м/мин|см/мин|км/ч)[^.?!]*?за\s+это\s+же\s+время[^\d]*(\d+)\s*(м|см|км)", lower)
    if m_same_time and _v14_question_asks_speed(question):
        first_distance = int(m_same_time.group(1))
        first_distance_unit = m_same_time.group(2)
        first_speed = int(m_same_time.group(3))
        first_speed_unit = m_same_time.group(4)
        second_distance = int(m_same_time.group(5))
        second_distance_unit = m_same_time.group(6)
        if not first_speed_unit.startswith(first_distance_unit):
            return None
        time_unit = first_speed_unit.split("/")[1]
        if first_speed == 0 or first_distance % first_speed != 0:
            return None
        time = first_distance // first_speed
        if time == 0 or second_distance % time != 0:
            return None
        second_speed = second_distance // time
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем время движения первого участника: {first_distance} : {first_speed} = {time} {time_unit}",
            f"Потом узнаем скорость второго участника: {second_distance} : {time} = {second_speed} {second_distance_unit}/{time_unit}",
            f"Ответ: {second_speed} {second_distance_unit}/{time_unit}.",
        )

    return None


_v14_compound_handler_base = try_local_compound_word_problem_explanation


def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    return try_local_book_compound_word_problem_v14(raw_text) or _v14_compound_handler_base(raw_text)

# =========================
# V14.7 cross-sentence pattern fixes
# =========================

_v14_book_compound_prev = try_local_book_compound_word_problem_v14


def try_local_book_compound_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    m_minus_sold = re.search(r"(\d+)\s+[а-яё\- ]+?по\s+(\d+)\s*(кг|л|м)[\s\S]*?(?:продали|израсходовали|использовали|съели)\s+(\d+)\s*(кг|л|м)", lower, flags=re.IGNORECASE)
    if m_minus_sold and _v14_has(question, "остал"):
        groups = int(m_minus_sold.group(1))
        per_group = int(m_minus_sold.group(2))
        unit = m_minus_sold.group(3)
        sold = int(m_minus_sold.group(4))
        total = groups * per_group
        left = total - sold
        if left >= 0:
            return join_explanation_lines(
                f"Краткое условие: {groups} групп по {per_group} {unit}, продали {sold} {unit}, осталось - ?",
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, сколько было всего: {groups} × {per_group} = {total}",
                f"Потом узнаем остаток: {total} - {sold} = {left}",
                f"Ответ: {with_unit(left, unit)}.",
            )

    m_unknown_price = re.search(r"(\d+)\s+[а-яё\- ]+?по\s+(\d+)\s*руб[а-я]*[\s\S]*?и\s+(\d+)\s+[а-яё\- ]+?[\s\S]*?заплатили\s+(\d+)\s*руб", lower, flags=re.IGNORECASE)
    if m_unknown_price and re.search(r"сколько\s+стоила?\s+1", question):
        known_count = int(m_unknown_price.group(1))
        known_price = int(m_unknown_price.group(2))
        unknown_count = int(m_unknown_price.group(3))
        total_money = int(m_unknown_price.group(4))
        known_total = known_count * known_price
        unknown_total = total_money - known_total
        if unknown_count > 0 and unknown_total >= 0 and unknown_total % unknown_count == 0:
            price = unknown_total // unknown_count
            return join_explanation_lines(
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем стоимость известной покупки: {known_count} × {known_price} = {known_total} руб.",
                f"Потом узнаем стоимость второй покупки: {total_money} - {known_total} = {unknown_total} руб.",
                f"Теперь узнаем цену 1 предмета: {unknown_total} : {unknown_count} = {price} руб.",
                f"Ответ: {price} руб.",
            )

    m_cages = re.search(r"в\s+каждой[^\d]*по\s*(\d+)[\s\S]*?и\s*(\d+)[\s\S]*?всего[^\d]*(\d+)", lower, flags=re.IGNORECASE)
    if m_cages and _v14_question_asks_plain_quantity(question):
        first = int(m_cages.group(1))
        second = int(m_cages.group(2))
        total = int(m_cages.group(3))
        per_group = first + second
        if per_group > 0 and total % per_group == 0:
            groups = total // per_group
            return join_explanation_lines(
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, сколько попугаев в 1 клетке: {first} + {second} = {per_group}",
                f"Потом узнаем число клеток: {total} : {per_group} = {groups}",
                f"Ответ: {groups}",
            )

    m_shared_money = re.search(r"(\d+)\s*руб[.,]?[^\d]+(\d+)\s*руб[\s\S]*?стоит\s+(\d+)\s*руб", lower, flags=re.IGNORECASE)
    if m_shared_money and _v14_question_asks_plain_quantity(question):
        first_money = int(m_shared_money.group(1))
        second_money = int(m_shared_money.group(2))
        price = int(m_shared_money.group(3))
        total_money = first_money + second_money
        if price > 0 and total_money % price == 0:
            count = total_money // price
            return join_explanation_lines(
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, сколько денег у ребят вместе: {first_money} + {second_money} = {total_money} руб.",
                f"Потом узнаем, сколько предметов можно купить: {total_money} : {price} = {count}",
                f"Ответ: {count}",
            )

    return _v14_book_compound_prev(raw_text)


_v14_motion_handler_prev = try_local_motion_explanation_v14


def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    m_rest_speed = re.search(r"(\d+)\s*км[\s\S]*?первые\s+(\d+)\s*час[а-я]*[\s\S]*?скоростью\s+(\d+)\s*км/час[\s\S]*?за\s+(\d+)\s*час", lower, flags=re.IGNORECASE)
    if m_rest_speed and _v14_question_asks_speed(question):
        total_distance = int(m_rest_speed.group(1))
        first_time = int(m_rest_speed.group(2))
        first_speed = int(m_rest_speed.group(3))
        second_time = int(m_rest_speed.group(4))
        first_distance = first_time * first_speed
        second_distance = total_distance - first_distance
        if second_time > 0 and second_distance >= 0 and second_distance % second_time == 0:
            second_speed = second_distance // second_time
            return join_explanation_lines(
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, какой путь прошли за первые {first_time} ч: {first_speed} × {first_time} = {first_distance} км",
                f"Потом узнаем, сколько осталось пройти: {total_distance} - {first_distance} = {second_distance} км",
                f"Теперь узнаем скорость на остальном пути: {second_distance} : {second_time} = {second_speed} км/ч",
                f"Ответ: {second_speed} км/ч.",
            )

    m_same_time = re.search(r"(\d+)\s*(м|см|км)[\s\S]*?скоростью\s+(\d+)\s*(м/мин|см/мин|км/ч)[\s\S]*?за\s+это\s+же\s+время[\s\S]*?(\d+)\s*(м|см|км)", lower, flags=re.IGNORECASE)
    if m_same_time and _v14_question_asks_speed(question):
        first_distance = int(m_same_time.group(1))
        first_distance_unit = m_same_time.group(2)
        first_speed = int(m_same_time.group(3))
        first_speed_unit = m_same_time.group(4)
        second_distance = int(m_same_time.group(5))
        second_distance_unit = m_same_time.group(6)
        if first_speed_unit.startswith(first_distance_unit) and first_speed > 0 and first_distance % first_speed == 0:
            time = first_distance // first_speed
            time_unit = first_speed_unit.split("/")[1]
            if time > 0 and second_distance % time == 0:
                second_speed = second_distance // time
                return join_explanation_lines(
                    "Сразу ответить на вопрос нельзя.",
                    f"Сначала узнаем время движения первого участника: {first_distance} : {first_speed} = {time} {time_unit}",
                    f"Потом узнаем скорость второго участника: {second_distance} : {time} = {second_speed} {second_distance_unit}/{time_unit}",
                    f"Ответ: {second_speed} {second_distance_unit}/{time_unit}.",
                )

    return _v14_motion_handler_prev(raw_text)

# =========================
# V14.8 work-rate cases
# =========================

_v14_book_compound_prev2 = try_local_book_compound_word_problem_v14


def try_local_book_compound_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Производительность по дням и числу бригад.
    m_brigades = re.search(r"за\s+(\d+)\s+дн[а-я]*[^\d]*(\d+)\s*(м|км|детал[ьяеи])[^.?!]*?(\d+)\s+так[а-яё\- ]+?\s+бригад[а-я]*[^\d]*(\d+)\s+дн", lower)
    if m_brigades and _v14_question_asks_plain_quantity(question):
        days = int(m_brigades.group(1))
        total = int(m_brigades.group(2))
        unit = m_brigades.group(3)
        brigades = int(m_brigades.group(4))
        new_days = int(m_brigades.group(5))
        if days == 0 or total % days != 0:
            return None
        one_brigade_per_day = total // days
        daily_all = one_brigade_per_day * brigades
        result = daily_all * new_days
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько делает 1 бригада за 1 день: {total} : {days} = {one_brigade_per_day}",
            f"Потом узнаем, сколько делают {brigades} бригады за 1 день: {one_brigade_per_day} × {brigades} = {daily_all}",
            f"Теперь узнаем, сколько они сделают за {new_days} дней: {daily_all} × {new_days} = {result}",
            f"Ответ: {with_unit(result, unit)}.",
        )

    # Совместная работа двух насосов.
    m_pumps = re.search(r"(\d+)\s+в[её]дер[^.?!]*?за\s+(\d+)\s*мин[^.?!]*?за\s+(\d+)\s*мин[^.?!]*?(\d+)\s+в[её]дер", lower)
    if m_pumps and _v14_question_asks_time(question):
        amount = int(m_pumps.group(1))
        first_time = int(m_pumps.group(2))
        second_time = int(m_pumps.group(3))
        target = int(m_pumps.group(4))
        if first_time == 0 or second_time == 0 or amount % first_time != 0 or amount % second_time != 0:
            return None
        first_rate = amount // first_time
        second_rate = amount // second_time
        total_rate = first_rate + second_rate
        if total_rate == 0 or target % total_rate != 0:
            return None
        total_time = target // total_rate
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем производительность первого насоса: {amount} : {first_time} = {first_rate} вёдер в минуту",
            f"Потом узнаем производительность второго насоса: {amount} : {second_time} = {second_rate} вёдер в минуту",
            f"Теперь узнаем общую производительность: {first_rate} + {second_rate} = {total_rate} вёдер в минуту",
            f"Потом узнаем время работы вместе: {target} : {total_rate} = {total_time} мин",
            f"Ответ: {total_time} мин.",
        )

    return _v14_book_compound_prev2(raw_text)

# =========================
# V14.9 numeric work wrappers
# =========================

_v14_book_compound_prev3 = try_local_book_compound_word_problem_v14


def try_local_book_compound_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    nums = extract_ordered_numbers(lower)

    if _v14_has(lower, "бригада", "бригады") and _v14_has(question, "такие бригады") and len(nums) >= 4:
        days, total, brigades, new_days = nums[:4]
        if days > 0 and total % days == 0:
            one_brigade_per_day = total // days
            daily_all = one_brigade_per_day * brigades
            result = daily_all * new_days
            unit = "м" if " м" in lower else ""
            return join_explanation_lines(
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем, сколько делает 1 бригада за 1 день: {total} : {days} = {one_brigade_per_day}",
                f"Потом узнаем, сколько делают {brigades} бригады за 1 день: {one_brigade_per_day} × {brigades} = {daily_all}",
                f"Теперь узнаем, сколько они сделают за {new_days} дней: {daily_all} × {new_days} = {result}",
                f"Ответ: {with_unit(result, unit)}.",
            )

    if _v14_has(lower, "насос") and _v14_has(lower, "вёдер", "ведер") and _v14_question_asks_time(question) and len(nums) >= 4:
        amount, first_time, second_time, target = nums[:4]
        if first_time > 0 and second_time > 0 and amount % first_time == 0 and amount % second_time == 0:
            first_rate = amount // first_time
            second_rate = amount // second_time
            total_rate = first_rate + second_rate
            if total_rate > 0 and target % total_rate == 0:
                total_time = target // total_rate
                return join_explanation_lines(
                    "Сразу ответить на вопрос нельзя.",
                    f"Сначала узнаем производительность первого насоса: {amount} : {first_time} = {first_rate} вёдер в минуту",
                    f"Потом узнаем производительность второго насоса: {amount} : {second_time} = {second_rate} вёдер в минуту",
                    f"Теперь узнаем общую производительность: {first_rate} + {second_rate} = {total_rate} вёдер в минуту",
                    f"Потом узнаем время работы вместе: {target} : {total_rate} = {total_time} мин",
                    f"Ответ: {total_time} мин.",
                )

    return _v14_book_compound_prev3(raw_text)

# =========================
# V14.10 remaining book cases
# =========================

_v14_book_compound_prev4 = try_local_book_compound_word_problem_v14


def try_local_book_compound_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    nums = extract_ordered_numbers(lower)

    # Неизвестное уменьшаемое в текстовой задаче.
    if len(nums) == 2 and _v14_has(lower, "осталось") and re.search(r"сколько[^.?!]*\bбыло\b", question):
        removed, remaining = nums[0], nums[1]
        initial = removed + remaining
        return join_explanation_lines(
            f"Краткое условие: взяли {removed}, осталось {remaining}, было - ?",
            "Ищем неизвестное уменьшаемое.",
            "Правило: чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое",
            f"{remaining} + {removed} = {initial}",
            f"Ответ: {initial}",
        )

    # Косвенная форма: брат старше сестры.
    m_sister = re.search(r"брату\s+(\d+)\s+лет[^.?!]*?на\s+(\d+)\s+год[а-я]*\s+старше\s+сестры", lower)
    if m_sister and _v14_question_asks_plain_quantity(question):
        brother_age = int(m_sister.group(1))
        delta = int(m_sister.group(2))
        sister_age = brother_age - delta
        return join_explanation_lines(
            "Сначала переведём условие в прямую форму.",
            f"Если брат на {delta} года старше сестры, то сестра на {delta} года младше брата.",
            f"{brother_age} - {delta} = {sister_age}",
            f"Ответ: {sister_age}",
        )

    # Цепочка «в ... раз меньше», потом «в ... раза больше», затем общий итог.
    if len(nums) == 3 and _v14_has(lower, "вороб", "снегир", "синиц") and _v14_question_asks_total(question):
        sparrows, less_factor, more_factor = nums[:3]
        if less_factor == 0:
            return None
        bullfinches = sparrows // less_factor if sparrows % less_factor == 0 else None
        if bullfinches is None:
            return None
        tits = bullfinches * more_factor
        total = sparrows + bullfinches + tits
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько было снегирей: {sparrows} : {less_factor} = {bullfinches}",
            f"Потом узнаем, сколько было синиц: {bullfinches} × {more_factor} = {tits}",
            f"Теперь узнаем, сколько птиц было всего: {sparrows} + {bullfinches} + {tits} = {total}",
            f"Ответ: {total}",
        )

    # Сын на ... меньше, чем родители вместе.
    if len(nums) == 3 and _v14_has(lower, "меньше, чем", "вместе") and _v14_question_asks_plain_quantity(question):
        first, second, delta = nums[:3]
        combined = first + second
        result = combined - delta
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем, сколько вместе: {first} + {second} = {combined}",
            f"Потом узнаем искомое число: {combined} - {delta} = {result}",
            f"Ответ: {result}",
        )

    # Сумма двух произведений со словами «сколько килограммов».
    pair_matches = re.findall(r"(\d+)\s+[а-яё\- ]+?по\s+(\d+)\s*(руб|кг|л|м)?", lower)
    if len(pair_matches) >= 2 and _v14_has(question, "сколько килограммов", "сколько кг", "сколько стоила", "сколько фруктов"):
        g1, p1, unit1 = pair_matches[0]
        g2, p2, unit2 = pair_matches[1]
        g1 = int(g1); p1 = int(p1); g2 = int(g2); p2 = int(p2)
        first_total = g1 * p1
        second_total = g2 * p2
        total = first_total + second_total
        unit = unit1 or unit2 or ("руб" if "руб" in lower else "")
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем первую часть: {g1} × {p1} = {first_total}",
            f"Потом узнаем вторую часть: {g2} × {p2} = {second_total}",
            f"Теперь узнаем всё вместе: {first_total} + {second_total} = {total}",
            f"Ответ: {with_unit(total, unit)}.",
        )

    # Сравнение цены одного предмета по двум покупкам, разбитым на предложения.
    m_compare = re.search(r"за\s+(\d+)\s+[а-яё\- ]+?\s+заплатил\w*\s+(\d+)\s*руб[\s\S]*?за\s+столько\s+же\s+[а-яё\- ]+?\s+заплатил\w*\s+(\d+)\s*руб", lower, flags=re.IGNORECASE)
    if m_compare and "на сколько" in question:
        count = int(m_compare.group(1))
        total_a = int(m_compare.group(2))
        total_b = int(m_compare.group(3))
        if count > 0 and total_a % count == 0 and total_b % count == 0:
            price_a = total_a // count
            price_b = total_b // count
            diff = abs(price_a - price_b)
            return join_explanation_lines(
                "Сразу ответить на вопрос нельзя.",
                f"Сначала узнаем цену первого предмета: {total_a} : {count} = {price_a}",
                f"Потом узнаем цену второго предмета: {total_b} : {count} = {price_b}",
                f"Теперь узнаем разницу: {max(price_a, price_b)} - {min(price_a, price_b)} = {diff}",
                f"Ответ: {diff} руб.",
            )

    return _v14_book_compound_prev4(raw_text)


_v14_motion_handler_prev2 = try_local_motion_explanation_v14


def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Скорость в условии, время в вопросе или наоборот.
    if _v14_question_asks_distance(question):
        speed_match = re.search(r"скоростью\s+(\d+)\s*(км/ч|м/мин|см/мин)", lower)
        time_in_question = re.search(r"за\s+(\d+)\s*(ч|час|часа|часов|мин|минуты|минут|мин)", question)
        if speed_match and time_in_question:
            speed = int(speed_match.group(1))
            speed_unit = speed_match.group(2)
            time = int(time_in_question.group(1))
            distance = speed * time
            dist_unit = speed_unit.split("/")[0]
            time_label = "ч" if time_in_question.group(2).startswith("ч") else "мин"
            return join_explanation_lines(
                f"Краткое условие: v = {speed} {speed_unit}, t = {time} {time_label}, S = ?",
                "Правило: чтобы найти расстояние, скорость умножаем на время",
                f"{speed} × {time} = {distance}",
                f"Ответ: {distance} {dist_unit}.",
            )

    return _v14_motion_handler_prev2(raw_text)

# =========================
# V14.11 final answer fixes
# =========================

_v14_fraction_handler_prev = try_local_fraction_word_problem_v14


def try_local_fraction_word_problem_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()
    frac = re.search(r"(\d+)\s*/\s*(\d+)", lower)
    if frac and _v14_has(question, "сколько метров", "сколько литров", "сколько кг") and not _v14_has(question, "остал", "во второй день"):
        num = int(frac.group(1))
        den = int(frac.group(2))
        other_numbers = _v14_numbers_without_first_fraction(lower)
        if den != 0 and other_numbers:
            total = other_numbers[0]
            part = total * num
            if part % den == 0:
                result = part // den
                return join_explanation_lines(
                    f"Краткое условие: целое - {total}, нужно найти {num}/{den} этого числа",
                    "Правило: чтобы найти часть от числа, делим число на знаменатель и умножаем на числитель",
                    f"{total} : {den} × {num} = {result}",
                    f"Ответ: {result}",
                )
    return _v14_fraction_handler_prev(raw_text)


_v14_motion_handler_prev3 = try_local_motion_explanation_v14


def try_local_motion_explanation_v14(raw_text: str) -> Optional[str]:
    text = _v14_text(raw_text)
    lower = text.lower()
    question = _v14_question(text).lower()

    # Сначала находим путь по скорости и времени автобуса, потом время велосипедиста.
    m_same_path = re.search(r"(?:автобус|машина|поезд)\s+ехал\s+(\d+)\s*(ч|час|часа|часов)\s+со\s+скоростью\s+(\d+)\s*(км/ч|км/час)", lower)
    q_other_speed = re.search(r"со\s+скоростью\s+(\d+)\s*(км/ч|км/час)", question)
    if m_same_path and q_other_speed and _v14_question_asks_time(question):
        first_time = int(m_same_path.group(1))
        first_speed = int(m_same_path.group(3))
        second_speed = int(q_other_speed.group(1))
        distance = first_speed * first_time
        if second_speed == 0 or distance % second_speed != 0:
            return None
        second_time = distance // second_speed
        return join_explanation_lines(
            "Сразу ответить на вопрос нельзя.",
            f"Сначала узнаем длину пути: {first_speed} × {first_time} = {distance} км",
            f"Потом узнаем время второго участника: {distance} : {second_speed} = {second_time} ч",
            f"Ответ: {second_time} ч.",
        )

    return _v14_motion_handler_prev3(raw_text)
