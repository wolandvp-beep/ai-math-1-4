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
if not DEEPSEEK_API_KEY:
    raise RuntimeError("Переменная окружения myapp_ai_math_1_4_API_key не установлена")

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
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int)
    if isinstance(node, ast.Num):
        return isinstance(node.n, int)
    return False



def parse_expression_ast(source: str) -> Optional[ast.AST]:
    try:
        parsed = ast.parse(source, mode="eval")
    except SyntaxError:
        return None
    if not validate_expression_ast(parsed):
        return None
    return parsed.body



def eval_fraction_node(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant):
        return Fraction(int(node.value), 1)
    if isinstance(node, ast.Num):
        return Fraction(int(node.n), 1)
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
    if isinstance(node, ast.Constant):
        return str(int(node.value))
    if isinstance(node, ast.Num):
        return str(int(node.n))
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
    if isinstance(node, (ast.Constant, ast.Num)):
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
    if not isinstance(node.left, (ast.Constant, ast.Num)) or not isinstance(node.right, (ast.Constant, ast.Num)):
        return None

    left = int(node.left.n if isinstance(node.left, ast.Num) else node.left.value)
    right = int(node.right.n if isinstance(node.right, ast.Num) else node.right.value)

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
