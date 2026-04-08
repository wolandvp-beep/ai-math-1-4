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
    allow_origins=["https://wolandvp-beep.github.io"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DEEPSEEK_API_KEY = os.environ.get("myapp_ai_math_1_4_API_key")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("Переменная окружения myapp_ai_math_1_4_API_key не установлена")

# ========================= НОВЫЙ СИСТЕМНЫЙ ПРОМПТ (стиль Math2++.txt) =========================
SYSTEM_PROMPT_V11 = """
Ты — учитель математики для детей 7–10 лет. Объясняй решение так, как в хороших учебниках: кратко, ясно, по шагам.

Правила:
- Пиши только на русском языке.
- Не используй markdown, списки, смайлики, лишние вступления.
- Не хвали ученика, не говори "молодец", "отлично".
- Каждая строка — одна мысль.

Структура ответа:
1. Коротко запиши условие (что известно) и вопрос (что нужно найти). Например: "На первой полке 2 книги, на второй 3. Сколько книг на обеих полках?"
2. Решение по действиям. Каждое действие начинай с "Если ... , то ...". Например: "Если на первой полке 2 книги, а на второй 3, то на обеих полках 2 + 3 = 5 книг."
3. Если задача составная (в два действия и более), сначала спроси: "Можем ли мы сразу ответить на вопрос? Нет, потому что не знаем ..." Затем: "Сначала узнаем ..." и "Потом узнаем ...".
4. Для уравнений: "Обозначим неизвестное через x. Составим уравнение: ... Решаем: ... Делаем проверку: ..."
5. Для деления в столбик: объясняй по шагам: неполное делимое, подбираем цифру частного, умножаем, вычитаем, сносим следующую цифру.
6. В конце каждой задачи напиши "Ответ: ..." и, если нужно, "Совет: ..." (совет должен быть кратким, например: "Чтобы найти сумму, складывай числа.").

Пример для простой задачи:
Условие: на первой полке 2 книги, на второй 3. Вопрос: сколько книг на обеих полках?
Решение:
Если на первой полке 2 книги и на второй 3, то вместе их 2 + 3 = 5.
Ответ: 5 книг.
Совет: если спрашивают "сколько всего", нужно сложить.

Пример для составной:
Условие: на первой полке 5 книг, на второй на 3 больше. Вопрос: сколько книг на двух полках?
Решение:
Можем ли мы сразу ответить на вопрос? Нет, потому что не знаем, сколько книг на второй полке.
Сначала узнаем, сколько книг на второй полке: если на первой 5, а на второй на 3 больше, то на второй 5 + 3 = 8.
Теперь узнаем, сколько на двух полках: если на первой 5, а на второй 8, то вместе 5 + 8 = 13.
Ответ: 13 книг.
Совет: в задачах, где одно число больше другого, сначала найди второе число.

Пример для уравнения:
Условие: на полке было 10 книг. После того как несколько книг забрали, осталось 3. Сколько книг забрали?
Решение:
Обозначим количество забранных книг через x. Составим уравнение: 10 - x = 3.
Чтобы найти x, нужно из уменьшаемого вычесть разность: x = 10 - 3 = 7.
Проверка: если было 10 и забрали 7, то осталось 10 - 7 = 3. Верно.
Ответ: 7 книг.
Совет: чтобы найти вычитаемое, вычти разность из уменьшаемого.

Всегда придерживайся этой структуры. Не пиши ответ в первой строке.
""".strip()

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (БЕЗ ИЗМЕНЕНИЙ) ========================

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

def swap_equation_sides_if_needed(lhs: str, rhs: str):
    if "x" not in lhs and "x" in rhs:
        return rhs, lhs
    return lhs, rhs

def format_equation_check(template: str, value_text: str, expected_text: str) -> str:
    expression = template.replace("x", value_text)
    return f"Проверка: {expression} = {expected_text}"

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

# ======================== НОВЫЕ ЛОКАЛЬНЫЕ ОБЪЯСНЕНИЯ (стиль Math2++.txt) ========================

def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return (
        f"Условие: известно {first} и {second}. Вопрос: сколько всего?\n"
        f"Решение:\n"
        f"Если к {first} прибавить {second}, то получится {first} + {second} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: если спрашивают «сколько всего» или «сколько стало», нужно складывать."
    )

def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return (
        f"Условие: было {first}, убрали {second}. Вопрос: сколько осталось?\n"
        f"Решение:\n"
        f"Если из {first} вычесть {second}, то останется {first} - {second} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: если что-то убрали, отдали или съели, используй вычитание."
    )

def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return (
        f"Условие: даны числа {first} и {second}. Вопрос: на сколько одно больше другого?\n"
        f"Решение:\n"
        f"Если из большего числа вычесть меньшее, то получим разницу: {bigger} - {smaller} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: вопрос «на сколько больше или меньше» решается вычитанием."
    )

def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return (
        f"Условие: осталось {remaining}, убрали {removed}. Вопрос: сколько было сначала?\n"
        f"Решение:\n"
        f"Если к остатку прибавить убранное, получим начальное количество: {remaining} + {removed} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: чтобы найти, сколько было до того, как убрали, нужно сложить остаток и убранное."
    )

def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return (
        f"Условие: стало {final_total}, добавили {added}. Вопрос: сколько было сначала?\n"
        f"Решение:\n"
        f"Если из конечного числа вычесть добавленное, получим начальное: {final_total} - {added} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: если что-то добавили, начальное число находим вычитанием."
    )

def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return (
        f"Условие: было {before}, стало {after}. Вопрос: сколько добавили?\n"
        f"Решение:\n"
        f"Если из большего числа вычесть меньшее, узнаем, на сколько увеличилось: {bigger} - {smaller} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: чтобы найти, сколько добавили, сравни, что было и что стало."
    )

def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return (
        f"Условие: было {before}, стало {after}. Вопрос: сколько убрали?\n"
        f"Решение:\n"
        f"Если из того, что было, вычесть то, что осталось, узнаем, сколько убрали: {bigger} - {smaller} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: вычитай остаток из начального количества."
    )

def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return (
        f"Условие: {groups} группы по {per_group} предметов. Вопрос: сколько всего предметов?\n"
        f"Решение:\n"
        f"Если взять {groups} раз по {per_group}, то всего будет {groups} × {per_group} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: слова «по … в каждой» подсказывают умножение."
    )

def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return (
            "Условие: нужно разделить поровну на 0 частей. Вопрос: сколько получит каждый?\n"
            "Решение:\n"
            "На ноль делить нельзя.\n"
            "Ответ: деление на ноль невозможно.\n"
            "Совет: проверь, на сколько частей делят предметы."
        )
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return (
            f"Условие: {total} предметов разложили поровну на {groups} частей. Вопрос: сколько в каждой части?\n"
            f"Решение:\n"
            f"Если {total} разделить на {groups} равных частей, то в каждой будет {total} : {groups} = {quotient}.\n"
            f"Ответ: {quotient}.\n"
            f"Совет: слова «поровну» и «каждый» подсказывают деление."
        )
    else:
        return (
            f"Условие: {total} предметов разложили поровну на {groups} частей. Вопрос: сколько в каждой части и сколько останется?\n"
            f"Решение:\n"
            f"При делении {total} на {groups} получаем {quotient} и остаток {remainder}: {total} : {groups} = {quotient} (ост. {remainder}).\n"
            f"Ответ: каждому по {quotient}, остаток {remainder}.\n"
            f"Совет: остаток всегда меньше делителя."
        )

def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return (
            "Условие: в одной группе 0 предметов. Вопрос: сколько групп получится?\n"
            "Решение:\n"
            "В группе не может быть ноль предметов.\n"
            "Ответ: задача неверная.\n"
            "Совет: проверь размер группы."
        )
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return (
            f"Условие: {total} предметов разложили в группы по {per_group}. Вопрос: сколько групп?\n"
            f"Решение:\n"
            f"Если {total} разделить на {per_group}, то получится {total} : {per_group} = {quotient} групп.\n"
            f"Ответ: {quotient}.\n"
            f"Совет: число групп находим делением."
        )
    if needs_extra_group:
        return (
            f"Условие: {total} предметов нужно разложить в группы по {per_group}. Вопрос: сколько групп потребуется, чтобы уместить всё?\n"
            f"Решение:\n"
            f"Сначала узнаем, сколько полных групп: {total} : {per_group} = {quotient} (ост. {remainder}).\n"
            f"Остаток {remainder} требует ещё одну группу. Всего групп: {quotient} + 1 = {quotient + 1}.\n"
            f"Ответ: {quotient + 1}.\n"
            f"Совет: если что-то остаётся, нужна ещё одна коробка или место."
        )
    if explicit_remainder:
        full_group_phrase = plural_form(quotient, "полная группа", "полные группы", "полных групп")
        return (
            f"Условие: {total} предметов разложили в группы по {per_group}. Вопрос: сколько полных групп и сколько останется?\n"
            f"Решение:\n"
            f"Разделим {total} на {per_group}: {total} : {per_group} = {quotient} (ост. {remainder}).\n"
            f"Ответ: {quotient} {full_group_phrase}, остаток {remainder}.\n"
            f"Совет: остаток всегда меньше размера группы."
        )
    return None

def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return (
        f"Условие: одно число равно {base}, другое на {delta} {mode}. Вопрос: чему равно другое число?\n"
        f"Решение:\n"
        f"Если число на {delta} {mode}, то его находим действием {sign}: {base} {sign} {delta} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: сначала определи, больше или меньше, потом выполняй сложение или вычитание."
    )

def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return (
        f"Условие: первое число {base}, второе на {delta} {mode}. Вопрос: сколько всего?\n"
        f"Решение:\n"
        f"Сначала узнаем второе число: {base} {sign} {delta} = {related}.\n"
        f"Теперь сложим оба: {base} + {related} = {total}.\n"
        f"Ответ: {total}.\n"
        f"Совет: сначала найди второе число, потом считай сумму."
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
    return (
        f"Условие: сначала было {start}. Потом число изменили дважды. Вопрос: каким оно стало?\n"
        f"Решение:\n"
        f"Сначала {first_action} {first_delta}: {start} {first_sign} {first_delta} = {middle}.\n"
        f"Потом {second_action} {second_delta}: {middle} {second_sign} {second_delta} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: считай изменения по порядку."
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
    return (
        f"Условие: даны три числа, каждое следующее зависит от предыдущего. Вопрос: найти третье.\n"
        f"Решение:\n"
        f"Сначала находим второе: {base} {first_sign} {first_delta} = {middle}.\n"
        f"Потом третье: {middle} {second_sign} {second_delta} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: решай по шагам, последовательно находя каждое число."
    )

def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return (
        f"Условие: есть {groups} групп по {per_group} предметов и ещё {extra} предметов отдельно. Вопрос: сколько всего?\n"
        f"Решение:\n"
        f"Сначала узнаем, сколько в группах: {groups} × {per_group} = {grouped_total}.\n"
        f"Теперь прибавим отдельные предметы: {grouped_total} + {extra} = {result}.\n"
        f"Ответ: {result}.\n"
        f"Совет: сначала посчитай одинаковые группы, потом добавь остаток."
    )

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if left >= 10 or right >= 10:
        left_tens, left_units = divmod(left, 10)
        right_tens, right_units = divmod(right, 10)
        tens_sum = left_tens + right_tens
        units_sum = left_units + right_units
        return (
            f"Условие: нужно сложить {left} и {right}.\n"
            f"Решение:\n"
            f"Разбиваем на десятки и единицы: {left} = {left_tens*10} + {left_units}, {right} = {right_tens*10} + {right_units}.\n"
            f"Складываем десятки: {left_tens*10} + {right_tens*10} = {tens_sum*10}.\n"
            f"Складываем единицы: {left_units} + {right_units} = {units_sum}.\n"
            f"Складываем результаты: {tens_sum*10} + {units_sum} = {total}.\n"
            f"Ответ: {total}.\n"
            f"Совет: большие числа удобно складывать по частям."
        )
    else:
        return (
            f"Условие: нужно сложить {left} и {right}.\n"
            f"Решение:\n"
            f"Если к {left} прибавить {right}, получится {left} + {right} = {total}.\n"
            f"Ответ: {total}.\n"
            f"Совет: складывай по порядку."
        )

def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if result < 0:
        return (
            f"Условие: из {left} вычесть {right}.\n"
            f"Решение:\n"
            f"{left} меньше {right}, поэтому ответ будет отрицательным: {left} - {right} = {result}.\n"
            f"Ответ: {result}.\n"
            f"Совет: сначала сравни числа."
        )
    if right >= 10:
        tens = (right // 10) * 10
        units = right % 10
        middle = left - tens
        return (
            f"Условие: нужно вычесть {right} из {left}.\n"
            f"Решение:\n"
            f"Разбиваем вычитаемое на десятки и единицы: {right} = {tens} + {units}.\n"
            f"Сначала вычитаем десятки: {left} - {tens} = {middle}.\n"
            f"Потом вычитаем единицы: {middle} - {units} = {result}.\n"
            f"Ответ: {result}.\n"
            f"Совет: вычитай по частям: сначала десятки, потом единицы."
        )
    else:
        return (
            f"Условие: нужно вычесть {right} из {left}.\n"
            f"Решение:\n"
            f"Если из {left} вычесть {right}, получится {left} - {right} = {result}.\n"
            f"Ответ: {result}.\n"
            f"Совет: вычитай спокойно и не пропускай знак минус."
        )

def explain_simple_multiplication(left: int, right: int) -> str:
    result = left * right
    big = max(left, right)
    small = min(left, right)
    if big >= 10 and small <= 10:
        tens = (big // 10) * 10
        units = big % 10
        return (
            f"Условие: нужно умножить {left} на {right}.\n"
            f"Решение:\n"
            f"Разбиваем большее число {big} на {tens} и {units}.\n"
            f"Умножаем десятки: {tens} × {small} = {tens * small}.\n"
            f"Умножаем единицы: {units} × {small} = {units * small}.\n"
            f"Складываем результаты: {tens * small} + {units * small} = {result}.\n"
            f"Ответ: {result}.\n"
            f"Совет: умножение удобно разбивать на десятки и единицы."
        )
    else:
        return (
            f"Условие: нужно умножить {left} на {right}.\n"
            f"Решение:\n"
            f"Если {left} умножить на {right}, получится {left} × {right} = {result}.\n"
            f"Ответ: {result}.\n"
            f"Совет: умножение показывает, сколько будет одинаковых групп."
        )

def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return (
            "Условие: нужно разделить на 0.\n"
            "Решение:\n"
            "На ноль делить нельзя.\n"
            "Ответ: деление на ноль невозможно.\n"
            "Совет: проверь делитель."
        )
    quotient, remainder = divmod(left, right)
    if left < 100 and right < 10:
        if remainder == 0:
            return (
                f"Условие: нужно разделить {left} на {right}.\n"
                f"Решение:\n"
                f"Ищем число, которое при умножении на {right} даёт {left}. Это {quotient}, потому что {quotient} × {right} = {left}.\n"
                f"Ответ: {quotient}.\n"
                f"Совет: деление проверяй умножением."
            )
        else:
            return (
                f"Условие: нужно разделить {left} на {right}.\n"
                f"Решение:\n"
                f"{left} : {right} = {quotient} (ост. {remainder}), так как {quotient} × {right} = {quotient*right}, а остаётся {remainder}.\n"
                f"Ответ: {quotient}, остаток {remainder}.\n"
                f"Совет: остаток всегда меньше делителя."
            )
    else:
        steps_data = _build_long_division_steps_v9(left, right)
        steps = steps_data["steps"]
        quotient = steps_data["quotient"]
        remainder = steps_data["remainder"]
        lines = [
            f"Условие: нужно разделить {left} на {right}.",
            "Решение (деление столбиком):"
        ]
        if not steps:
            lines.append(f"{left} меньше {right}, поэтому в частном будет 0, остаток {left}.")
        else:
            first = steps[0]
            lines.append(f"Берём первое неполное делимое: {first['current']}.")
            for i, step in enumerate(steps):
                current = step['current']
                q_digit = step['q_digit']
                product = step['product']
                remainder_val = step['remainder']
                lines.append(f"Подбираем цифру частного: {q_digit}, потому что {q_digit} × {right} = {product} ≤ {current}.")
                lines.append(f"Вычитаем: {current} - {product} = {remainder_val}.")
                if i + 1 < len(steps):
                    next_digit = steps[i+1]['current']
                    lines.append(f"Сносим следующую цифру, получаем {next_digit}.")
            if remainder == 0:
                lines.append(f"Деление закончено. Частное = {quotient}.")
            else:
                lines.append(f"Остаток = {remainder}.")
        answer = f"{quotient}" if remainder == 0 else f"{quotient}, остаток {remainder}"
        lines.append(f"Ответ: {answer}.")
        lines.append("Совет: при делении в столбик повторяй шаги: взял, подобрал, умножил, вычел, снёс.")
        return "\n".join(lines)

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
        return (
            f"Условие: периметр квадрата равен {perimeter}{unit}. Вопрос: найти сторону.\n"
            f"Решение:\n"
            f"У квадрата все стороны равны. Периметр — это сумма всех четырёх сторон.\n"
            f"Если периметр {perimeter}{unit}, то одна сторона равна {perimeter} : 4 = {side}{unit}.\n"
            f"Ответ: {side}{unit}.\n"
            f"Совет: чтобы найти сторону квадрата по периметру, раздели периметр на 4."
        )
    if "прямоугольник" in lower and asks_perimeter and asks_width and len(nums) >= 2:
        perimeter, length = nums[0], nums[1]
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        width = half - length
        if width < 0:
            return None
        return (
            f"Условие: периметр прямоугольника {perimeter}{unit}, длина {length}{unit}. Вопрос: найти ширину.\n"
            f"Решение:\n"
            f"Периметр прямоугольника = (длина + ширина) × 2. Сначала найдём половину периметра: {perimeter} : 2 = {half}{unit}.\n"
            f"Это сумма длины и ширины. Тогда ширина = {half} - {length} = {width}{unit}.\n"
            f"Ответ: {width}{unit}.\n"
            f"Совет: половина периметра — это длина плюс ширина."
        )
    if "прямоугольник" in lower and asks_perimeter and asks_length and len(nums) >= 2:
        perimeter, width = nums[0], nums[1]
        if perimeter % 2 != 0:
            return None
        half = perimeter // 2
        length = half - width
        if length < 0:
            return None
        return (
            f"Условие: периметр прямоугольника {perimeter}{unit}, ширина {width}{unit}. Вопрос: найти длину.\n"
            f"Решение:\n"
            f"Периметр = (длина + ширина) × 2. Половина периметра = {perimeter} : 2 = {half}{unit}.\n"
            f"Длина = {half} - {width} = {length}{unit}.\n"
            f"Ответ: {length}{unit}.\n"
            f"Совет: сначала найди половину периметра."
        )
    if "квадрат" in lower and asks_area and asks_side and nums:
        area = nums[0]
        side = int(math.isqrt(area))
        if side * side != area:
            return None
        return (
            f"Условие: площадь квадрата равна {area}{unit}². Вопрос: найти сторону.\n"
            f"Решение:\n"
            f"Площадь квадрата = сторона × сторона. Нужно найти число, которое при умножении на себя даёт {area}. Это {side}, потому что {side} × {side} = {area}.\n"
            f"Ответ: {side}{unit}.\n"
            f"Совет: чтобы найти сторону квадрата по площади, извлеки квадратный корень (подбери число)."
        )
    if "прямоугольник" in lower and asks_area and asks_width and len(nums) >= 2:
        area, length = nums[0], nums[1]
        if length == 0 or area % length != 0:
            return None
        width = area // length
        return (
            f"Условие: площадь прямоугольника {area}{unit}², длина {length}{unit}. Вопрос: найти ширину.\n"
            f"Решение:\n"
            f"Площадь прямоугольника = длина × ширина. Чтобы найти ширину, разделим площадь на длину: {area} : {length} = {width}{unit}.\n"
            f"Ответ: {width}{unit}.\n"
            f"Совет: ширина = площадь : длина."
        )
    if "прямоугольник" in lower and asks_area and asks_length and len(nums) >= 2:
        area, width = nums[0], nums[1]
        if width == 0 or area % width != 0:
            return None
        length = area // width
        return (
            f"Условие: площадь прямоугольника {area}{unit}², ширина {width}{unit}. Вопрос: найти длину.\n"
            f"Решение:\n"
            f"Площадь = длина × ширина. Длина = площадь : ширина = {area} : {width} = {length}{unit}.\n"
            f"Ответ: {length}{unit}.\n"
            f"Совет: длина = площадь : ширина."
        )
    if "квадрат" in lower and asks_perimeter and nums:
        side = nums[0]
        result = side * 4
        return (
            f"Условие: сторона квадрата {side}{unit}. Вопрос: найти периметр.\n"
            f"Решение:\n"
            f"Периметр квадрата = сторона × 4 = {side} × 4 = {result}{unit}.\n"
            f"Ответ: {result}{unit}.\n"
            f"Совет: у квадрата 4 равные стороны."
        )
    if "прямоугольник" in lower and asks_perimeter and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = 2 * (length + width)
        return (
            f"Условие: длина прямоугольника {length}{unit}, ширина {width}{unit}. Вопрос: найти периметр.\n"
            f"Решение:\n"
            f"Периметр = (длина + ширина) × 2 = ({length} + {width}) × 2 = {result}{unit}.\n"
            f"Ответ: {result}{unit}.\n"
            f"Совет: сначала сложи длину и ширину, потом умножь на 2."
        )
    if "квадрат" in lower and asks_area and nums:
        side = nums[0]
        result = side * side
        return (
            f"Условие: сторона квадрата {side}{unit}. Вопрос: найти площадь.\n"
            f"Решение:\n"
            f"Площадь квадрата = сторона × сторона = {side} × {side} = {result}{unit}².\n"
            f"Ответ: {result}{unit}².\n"
            f"Совет: площадь квадрата — это сторона, умноженная на себя."
        )
    if "прямоугольник" in lower and asks_area and len(nums) >= 2:
        length, width = nums[0], nums[1]
        result = length * width
        return (
            f"Условие: длина прямоугольника {length}{unit}, ширина {width}{unit}. Вопрос: найти площадь.\n"
            f"Решение:\n"
            f"Площадь = длина × ширина = {length} × {width} = {result}{unit}².\n"
            f"Ответ: {result}{unit}².\n"
            f"Совет: для площади умножай длину на ширину."
        )
    return None

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
        num_str = format_fraction(number)
        rhs_str = format_fraction(rhs_value)
        if kind in ("x_plus", "plus_x"):
            answer = rhs_value - number
            ans_str = format_fraction(answer)
            check = f"Проверка: подставляем x = {ans_str}: {lhs.replace('x', ans_str)} = {rhs_str}"
            return (
                f"Условие: уравнение {lhs} = {rhs}. Вопрос: найти x.\n"
                f"Решение:\n"
                f"Обозначим неизвестное через x. Чтобы найти x, нужно перенести число {num_str} в правую часть с противоположным знаком.\n"
                f"x = {rhs_str} - {num_str} = {ans_str}.\n"
                f"{check}\n"
                f"Ответ: {ans_str}.\n"
                f"Совет: если x складывают с числом, число переносим вычитанием."
            )
        if kind == "x_minus":
            answer = rhs_value + number
            ans_str = format_fraction(answer)
            return (
                f"Условие: уравнение {lhs} = {rhs}. Вопрос: найти x.\n"
                f"Решение:\n"
                f"x - {num_str} = {rhs_str}. Переносим {num_str} в правую часть со знаком плюс.\n"
                f"x = {rhs_str} + {num_str} = {ans_str}.\n"
                f"Проверка: {ans_str} - {num_str} = {rhs_str}.\n"
                f"Ответ: {ans_str}.\n"
                f"Совет: если x уменьшают на число, при переносе число становится положительным."
            )
        if kind == "minus_x":
            answer = number - rhs_value
            ans_str = format_fraction(answer)
            return (
                f"Условие: уравнение {lhs} = {rhs}. Вопрос: найти x.\n"
                f"Решение:\n"
                f"{num_str} - x = {rhs_str}. Чтобы найти x, вычтем {rhs_str} из {num_str}.\n"
                f"x = {num_str} - {rhs_str} = {ans_str}.\n"
                f"Проверка: {num_str} - {ans_str} = {rhs_str}.\n"
                f"Ответ: {ans_str}.\n"
                f"Совет: если x стоит после минуса, вычти результат из первого числа."
            )
        if kind in ("x_mul", "mul_x"):
            if number == 0:
                if rhs_value == 0:
                    return (
                        f"Условие: {lhs} = {rhs}.\n"
                        "Решение:\n"
                        "0 при умножении на любое число даёт 0. Значит, x может быть любым числом.\n"
                        "Ответ: любое число.\n"
                        "Совет: умножение на ноль всегда даёт ноль."
                    )
                else:
                    return (
                        f"Условие: {lhs} = {rhs}.\n"
                        "Решение:\n"
                        "0, умноженный на x, не может дать ненулевое число. Решений нет.\n"
                        "Ответ: решений нет.\n"
                        "Совет: проверь уравнение."
                    )
            answer = rhs_value / number
            ans_str = format_fraction(answer)
            return (
                f"Условие: уравнение {lhs} = {rhs}. Вопрос: найти x.\n"
                f"Решение:\n"
                f"Чтобы найти x, нужно {rhs_str} разделить на {num_str}: x = {rhs_str} : {num_str} = {ans_str}.\n"
                f"Проверка: {num_str} × {ans_str} = {rhs_str}.\n"
                f"Ответ: {ans_str}.\n"
                f"Совет: множитель переносим делением."
            )
        if kind == "x_div":
            if number == 0:
                return (
                    f"Условие: {lhs} = {rhs}.\n"
                    "Решение:\n"
                    "На ноль делить нельзя. Уравнение не имеет решений.\n"
                    "Ответ: решений нет.\n"
                    "Совет: проверь делитель."
                )
            answer = rhs_value * number
            ans_str = format_fraction(answer)
            return (
                f"Условие: уравнение {lhs} = {rhs}. Вопрос: найти x.\n"
                f"Решение:\n"
                f"x : {num_str} = {rhs_str}. Чтобы найти x, умножим {rhs_str} на {num_str}: x = {rhs_str} × {num_str} = {ans_str}.\n"
                f"Проверка: {ans_str} : {num_str} = {rhs_str}.\n"
                f"Ответ: {ans_str}.\n"
                f"Совет: деление меняем на умножение."
            )
        if kind == "div_x":
            if number == 0:
                if rhs_value == 0:
                    return (
                        f"Условие: {lhs} = {rhs}.\n"
                        "Решение:\n"
                        "0, делённое на любое ненулевое число, даёт 0. x может быть любым, кроме 0.\n"
                        "Ответ: любое число, кроме 0.\n"
                        "Совет: в делителе ноль быть не может."
                    )
                else:
                    return (
                        f"Условие: {lhs} = {rhs}.\n"
                        "Решение:\n"
                        "0, делённое на ненулевое число, не может дать ненулевой результат. Решений нет.\n"
                        "Ответ: решений нет.\n"
                        "Совет: проверь уравнение."
                    )
            if rhs_value == 0:
                return (
                    f"Условие: {lhs} = {rhs}.\n"
                    "Решение:\n"
                    "Ненулевое число, делённое на x, не может равняться 0. Решений нет.\n"
                    "Ответ: решений нет.\n"
                    "Совет: проверь, может ли частное быть нулём."
                )
            answer = number / rhs_value
            ans_str = format_fraction(answer)
            return (
                f"Условие: уравнение {lhs} = {rhs}. Вопрос: найти x.\n"
                f"Решение:\n"
                f"{num_str} : x = {rhs_str}. Чтобы найти x, разделим {num_str} на {rhs_str}: x = {num_str} : {rhs_str} = {ans_str}.\n"
                f"Проверка: {num_str} : {ans_str} = {rhs_str}.\n"
                f"Ответ: {ans_str}.\n"
                f"Совет: если x в делителе, дели делимое на результат."
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
    a, b, c, d = int(a), int(b), int(c), int(d)
    if b == 0 or d == 0:
        return (
            "Условие: дроби с нулевым знаменателем.\n"
            "Решение:\n"
            "Знаменатель дроби не может быть нулём.\n"
            "Ответ: запись неверная.\n"
            "Совет: проверь знаменатели."
        )
    action_word = "Складываем" if operator == "+" else "Вычитаем"
    action_symbol = "+" if operator == "+" else "-"
    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)
    if b == d:
        top = a + c if operator == "+" else a - c
        lines = [
            f"Условие: вычислить {a}/{b} {action_symbol} {c}/{d}.",
            "Решение:",
            f"Знаменатели одинаковые, поэтому {action_word.lower()} числители: {a} {action_symbol} {c} = {top}.",
            f"Получаем {top}/{b}."
        ]
        if format_fraction(result) != f"{top}/{b}":
            lines.append(f"Сокращаем: {top}/{b} = {format_fraction(result)}.")
        lines.append(f"Ответ: {format_fraction(result)}.")
        lines.append("Совет: если знаменатели одинаковые, работай только с числителями.")
        return "\n".join(lines)
    common = math.lcm(b, d)
    a_scaled = a * (common // b)
    c_scaled = c * (common // d)
    top = a_scaled + c_scaled if operator == "+" else a_scaled - c_scaled
    lines = [
        f"Условие: вычислить {a}/{b} {action_symbol} {c}/{d}.",
        "Решение:",
        f"Приводим дроби к общему знаменателю {common}:",
        f"{a}/{b} = {a_scaled}/{common}, {c}/{d} = {c_scaled}/{common}.",
        f"Теперь {action_word.lower()}: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top}/{common}."
    ]
    simplified = Fraction(top, common)
    if format_fraction(simplified) != f"{top}/{common}":
        lines.append(f"Сокращаем: {top}/{common} = {format_fraction(simplified)}.")
    lines.append(f"Ответ: {format_fraction(result)}.")
    lines.append("Совет: сначала приведи дроби к общему знаменателю.")
    return "\n".join(lines)

def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None
    simple = try_simple_binary_int_expression(node)
    if simple:
        op = simple["operator"]
        left = simple["left"]
        right = simple["right"]
        if op is ast.Add:
            return explain_simple_addition(left, right)
        if op is ast.Sub:
            return explain_simple_subtraction(left, right)
        if op is ast.Mult:
            return explain_simple_multiplication(left, right)
        if op is ast.Div:
            return explain_simple_division(left, right)
    try:
        value, steps = build_eval_steps(node)
    except ZeroDivisionError:
        return (
            "Условие: в выражении есть деление на ноль.\n"
            "Решение:\n"
            "На ноль делить нельзя.\n"
            "Ответ: деление на ноль невозможно.\n"
            "Совет: проверь делитель."
        )
    except Exception:
        return None
    if not steps:
        return None
    lines = [f"Условие: вычислить {source}.", "Решение:"]
    for i, step in enumerate(steps):
        if i == 0:
            lines.append(f"Сначала {step['verb']}: {step['left']} {step['operator']} {step['right']} = {step['result']}.")
        elif i == 1:
            lines.append(f"Потом {step['verb']}: {step['left']} {step['operator']} {step['right']} = {step['result']}.")
        else:
            lines.append(f"Дальше {step['verb']}: {step['left']} {step['operator']} {step['right']} = {step['result']}.")
    answer = format_fraction(value)
    lines.append(f"Ответ: {answer}.")
    lines.append("Совет: выполняй действия по порядку, сначала в скобках, потом умножение и деление, затем сложение и вычитание.")
    return "\n".join(lines)

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
    asks_groups = contains_any_fragment(lower, ("сколько короб", "сколько корзин", "сколько пакет", "сколько тарел", "сколько полок", "сколько ряд", "сколько групп", "сколько ящик", "сколько банок", "сколько парт", "сколько машин", "сколько мест"))
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

# ========================= НОВАЯ ФУНКЦИЯ shape_explanation (упрощённая, без лишних пустых строк) =========================

def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    cleaned = sanitize_model_text(text)
    if not cleaned:
        advice = forced_advice or default_advice(kind)
        if forced_answer:
            return f"Ответ: {forced_answer}\nСовет: {advice}"
        return "Напишите задачу понятнее\nОтвет: нужно уточнить запись\nСовет: уточните условие"
    lines = cleaned.split("\n")
    result_lines = []
    for line in lines:
        line = line.strip()
        if line:
            result_lines.append(line)
    if not any(l.lower().startswith("ответ:") for l in result_lines):
        if forced_answer:
            result_lines.append(f"Ответ: {forced_answer}")
        else:
            for i in range(len(result_lines)-1, -1, -1):
                if "=" in result_lines[i]:
                    parts = result_lines[i].split("=")
                    if len(parts) > 1:
                        result_lines.append(f"Ответ: {parts[-1].strip()}")
                        break
            else:
                result_lines.append("Ответ: проверь запись")
    if not any(l.lower().startswith("совет:") for l in result_lines):
        result_lines.append(f"Совет: {forced_advice or default_advice(kind)}")
    return "\n".join(result_lines)

# ========================= ФУНКЦИЯ build_explanation (использует новый промпт) =========================

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
            "Это текстовая задача. Следуй структуре: условие, вопрос, решение по действиям с 'Если …, то …', "
            "для составных задач используй 'Можем ли мы сразу ответить? Нет, потому что…', 'Сначала узнаем…', 'Потом узнаем…'.\n\n"
        )
    elif kind == "geometry":
        extra_instruction = (
            "Это задача по геометрии. Сначала запиши условие и вопрос, затем назови правило, подставь числа, выполни вычисление.\n\n"
        )
    elif kind == "expression":
        extra_instruction = (
            "Это арифметический пример. Запиши условие, затем решение по шагам с 'Сначала…', 'Потом…'. Если есть деление, объясни столбиком.\n\n"
        )
    elif kind == "fraction":
        extra_instruction = (
            "Это пример с дробями. Запиши условие, затем решение: одинаковы ли знаменатели, приведение к общему знаменателю, вычисление.\n\n"
        )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_V11},
            {"role": "user", "content": (
                "Объясни решение так, как в хорошем учебнике: кратко, ясно, по шагам. "
                "Не давай ответ в первой строке. Следуй структуре: условие, вопрос, решение, ответ, совет.\n\n"
                f"{extra_instruction}{user_text}"
            )},
        ],
        "max_tokens": 600,
        "temperature": 0.05,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    shaped = shape_explanation(llm_result["result"], kind)
    return {"result": shaped, "source": "llm", "validated": False}

# ========================= МАРШРУТЫ (БЕЗ ИЗМЕНЕНИЙ) =========================

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