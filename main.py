import ast
import math
import os
import re
from fractions import Fraction
from typing import List, Optional, Tuple

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


SYSTEM_PROMPT = """
Ты — спокойный и точный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно и по-школьному.
Не используй markdown, таблицы, смайлики, лишние вступления и похвалу.
Каждая строка — одна полезная мысль.

Строй ответ так:
сначала 3–8 строк объяснения;
только для уравнения добавь строку "Проверка: ...";
потом строка "Ответ: ...";
последняя строка "Совет: ...".

Общие правила:
Не пиши готовый ответ в первой строке.
Не выдумывай данные и не меняй числа из задачи.
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку в одной строке "Ответ: ...; ...".
Совет должен быть коротким, учебным и конкретным.

Как объяснять:
Если это текстовая задача, сначала коротко скажи, что известно и что нужно найти.
Решай задачу по действиям и не пропускай промежуточный результат.
Если задача в косвенной форме, сначала переведи её в прямую: если одно число больше, то другое на столько же меньше; если одно число меньше, то другое на столько же больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, сначала найди неизвестную цену, количество или стоимость.
Если задача на движение, используй связи S = v × t, v = S : t, t = S : v.
При движении навстречу называй скорость сближения, а в противоположных направлениях — скорость удаления.
Если это выражение, называй порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это дроби, сначала смотри на знаменатели.
Если это геометрия, сначала назови правило или формулу, потом подставь числа.

Используй школьные приёмы:
сложение через десяток — разложи число так, чтобы сначала получить 10;
вычитание через десяток — вычитай по частям через 10;
двузначные числа удобно раскладывать на десятки и единицы;
если числа большие, объясняй по разрядам;
для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

BANNED_OPENERS = re.compile(
    r"^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\b",
    re.IGNORECASE,
)
LEADING_FILLER_SENTENCE = re.compile(
    r"^(?:отлично|давай(?:те)?|хорошо|молодец|правильно|посмотрим|разбер[её]мся|начн[её]м)\b[^.!?\n]*[.!?]\s*",
    re.IGNORECASE,
)
SECTION_PREFIX_RE = re.compile(r"^(ответ|совет|проверка)\s*:\s*", re.IGNORECASE)

NON_MATH_REPLY = (
    "Не видно точной математической записи.\n"
    "Напишите пример или задачу понятнее.\n"
    "Ответ: сначала нужно уточнить запись.\n"
    "Совет: пишите числа и знаки действия полностью."
)

DEFAULT_ADVICE = {
    "expression": "называй действия по порядку и следи за знаками",
    "equation": "сначала оставь x один, потом сделай проверку",
    "fraction": "сначала смотри на знаменатели, потом считай",
    "geometry": "сначала назови правило, потом подставь числа",
    "word": "сначала пойми, что известно и что нужно найти",
    "other": "решай по шагам и не перескакивай",
}

BODY_LIMITS = {
    "expression": 8,
    "equation": 6,
    "fraction": 6,
    "geometry": 7,
    "word": 8,
    "other": 6,
}

LOW_VALUE_BODY_PATTERNS = [
    re.compile(r"^решаем по шагам$", re.IGNORECASE),
    re.compile(r"^это задача(?:[^.!?]*)$", re.IGNORECASE),
    re.compile(r"^известны числа$", re.IGNORECASE),
]

WORD_GAIN_HINTS = (
    "еще", "ещё", "добав", "купил", "купила", "купили", "подар", "наш", "принес",
    "принёс", "принесли", "положил", "положила", "положили", "стало", "теперь",
    "получил", "получила", "получили", "прилет", "приех", "прибав",
)
WORD_LOSS_HINTS = (
    "отдал", "отдала", "отдали", "съел", "съела", "съели", "убрал", "убрала", "убрали",
    "забрал", "забрала", "забрали", "потер", "потрат", "продал", "продала", "продали",
    "ушло", "остал", "сломал", "сломала", "сломали", "снял", "сняла", "сняли",
)
WORD_COMPARISON_HINTS = ("на сколько больше", "на сколько меньше")
GROUPING_VERBS = (
    "разлож", "раздал", "раздала", "раздали", "расстав", "упакова", "улож", "постав",
    "посад", "слож",
)
GEOMETRY_UNIT_RE = re.compile(r"\b(мм|см|дм|м|км)\b", re.IGNORECASE)
FRACTION_IN_TEXT_RE = re.compile(r"(\d+)\s*/\s*(\d+)")

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
PLACE_NAMES = ["единицы", "десятки", "сотни", "тысячи", "десятки тысяч", "сотни тысяч", "миллионы"]
NEXT_PLACE_NAMES = ["десяток", "сотню", "тысячу", "десяток тысяч", "сотню тысяч", "миллион", "следующий разряд"]


def default_advice(kind: str) -> str:
    return DEFAULT_ADVICE.get(kind, DEFAULT_ADVICE["other"])


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
    return str(text or "").replace("−", "-").replace("–", "-").replace("—", "-")


def normalize_cyrillic_x(text: str) -> str:
    return str(text or "").replace("Х", "x").replace("х", "x")


def normalize_word_problem_text(text: str) -> str:
    cleaned = strip_known_prefix(text)
    cleaned = normalize_dashes(cleaned)
    cleaned = cleaned.replace("ё", "е").replace("Ё", "Е")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_sentence(text: str) -> str:
    line = str(text or "").strip()
    if not line:
        return ""
    if re.fullmatch(r"[+\-×:=/() 0-9]+", line):
        return line
    if line[-1] not in ".!?":
        line += "."
    return line


def join_explanation_lines(*lines: str) -> str:
    parts = [normalize_sentence(line) for line in lines if str(line or "").strip()]
    return "\n".join(parts)


def sanitize_model_text(text: str) -> str:
    cleaned = str(text or "").replace("\r", "")
    while True:
        updated = LEADING_FILLER_SENTENCE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    cleaned = cleaned.replace("\\", "")
    cleaned = re.sub(r"^\s*[-*•]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    raw_lines = [line.strip() for line in cleaned.split("\n")]
    lines = []
    seen = set()
    for raw in raw_lines:
        if not raw:
            continue
        if BANNED_OPENERS.match(raw):
            continue
        raw = SECTION_PREFIX_RE.sub(lambda m: f"{m.group(1).capitalize()}: ", raw)
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(raw)
    return "\n".join(lines).strip()


def is_low_value_body_line(text: str) -> bool:
    line = str(text or "").strip()
    return any(p.fullmatch(line) for p in LOW_VALUE_BODY_PATTERNS)


def extract_answer_value(answer_line: str) -> str:
    if not answer_line:
        return ""
    return re.sub(r"^Ответ:\s*", "", answer_line, flags=re.IGNORECASE).strip().rstrip(".!?").strip()


def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    cleaned = sanitize_model_text(text)
    if not cleaned:
        advice = forced_advice or default_advice(kind)
        if forced_answer:
            return join_explanation_lines(f"Ответ: {forced_answer}", f"Совет: {advice}")
        return join_explanation_lines("Напишите задачу понятнее", "Ответ: нужно уточнить запись", f"Совет: {advice}")

    body_lines: List[str] = []
    answer_line: Optional[str] = None
    advice_line: Optional[str] = None
    check_line: Optional[str] = None

    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("ответ:"):
            value = line.split(":", 1)[1].strip()
            if value:
                answer_line = f"Ответ: {value}"
            continue
        if lower.startswith("совет:"):
            value = line.split(":", 1)[1].strip()
            if value:
                advice_line = value
            continue
        if lower.startswith("проверка:"):
            value = line.split(":", 1)[1].strip()
            if value:
                check_line = f"Проверка: {value}"
            continue
        body_lines.append(line)

    if forced_answer is not None:
        answer_line = f"Ответ: {forced_answer}"
    if answer_line is None and body_lines:
        match = re.search(r"=\s*([^=]+)$", body_lines[-1])
        if match:
            answer_line = f"Ответ: {match.group(1).strip()}"
    if answer_line is None:
        answer_line = "Ответ: проверь запись задачи"

    normalized_body = []
    seen = set()
    answer_value = extract_answer_value(answer_line)
    for line in body_lines:
        line = re.sub(r"\s+", " ", line).strip(" ,;")
        if not line:
            continue
        key = line.lower().rstrip(".!?")
        if key in seen:
            continue
        seen.add(key)
        if is_low_value_body_line(line):
            continue
        normalized_body.append(line)

    limit = BODY_LIMITS.get(kind, BODY_LIMITS["other"])
    normalized_body = normalized_body[:limit]

    if kind != "equation":
        check_line = None

    final_lines = list(normalized_body)
    if check_line:
        final_lines.append(check_line)
    final_lines.append(answer_line)
    final_lines.append(f"Совет: {(forced_advice or advice_line or default_advice(kind)).strip().rstrip('.!?')}")
    return join_explanation_lines(*final_lines)


def contains_any_fragment(text: str, fragments) -> bool:
    base = str(text or "")
    return any(fragment in base for fragment in fragments)


def extract_ordered_numbers(text: str) -> List[int]:
    return [int(value) for value in re.findall(r"\d+", str(text or ""))]


def extract_fraction_pair(text: str) -> Optional[Tuple[int, int]]:
    match = FRACTION_IN_TEXT_RE.search(str(text or ""))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def geometry_unit(text: str) -> str:
    match = GEOMETRY_UNIT_RE.search(str(text or ""))
    return match.group(1).lower() if match else ""


def with_unit(value: int, unit: str, square: bool = False) -> str:
    if not unit:
        return str(value)
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


def has_multiple_questions(text: str) -> bool:
    return len(re.findall(r"\?", str(text or ""))) >= 2


def asks_total_like(text: str) -> bool:
    lower = str(text or "").lower().replace("ё", "е")
    if re.search(r"сколько[^.?!]*\b(всего|вместе)\b", lower):
        return True
    if re.search(r"сколько[^.?!]*\b(на|в)\s+(?:двух|трех|трёх|четырех|четырёх|обеих|обоих|всех)\b", lower):
        return True
    if re.search(r"сколько[^.?!]*\b(обеих|обоих|всех)\b", lower):
        return True
    if re.search(r"сколько[^.?!]*\bполках\b", lower) and re.search(r"\b(двух|трех|трёх|обеих|обоих|четырех|четырёх)\b", lower):
        return True
    if re.search(r"сколько[^.?!]*\bкружках\b", lower) and re.search(r"\b(двух|трех|трёх|обеих|обоих)\b", lower):
        return True
    return False


def extract_keyword_number(text: str, keyword: str) -> Optional[int]:
    base = str(text or "").lower()
    patterns = [
        rf"{keyword}[^\d]{{0,80}}(\d+)",
        rf"{keyword}\s*=\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, base)
        if match:
            return int(match.group(1))
    return None


def extract_pairs_after_po(text: str) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for match in re.finditer(r"(\d+)\s+[^\d?.!]{0,40}?по\s+(\d+)", str(text or "").lower()):
        pairs.append((int(match.group(1)), int(match.group(2))))
    return pairs


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def infer_task_kind(text: str) -> str:
    base = strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()
    if re.search(r"\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+", lowered):
        return "fraction"
    if "x" in lowered and "=" in lowered:
        return "equation"
    if re.search(r"периметр|площадь|прямоугольник|квадрат|треугольник|сторон|длина|ширина", lowered):
        return "geometry"
    if re.search(r"[а-я]", lowered):
        return "word"
    if re.search(r"[+\-*/()×÷:]", lowered):
        return "expression"
    return "other"


def to_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")
    text = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " * ", text)
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
    text = text.replace("X", "x").replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")
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


def is_int_literal_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int


def int_from_literal_node(node: ast.AST) -> int:
    if not is_int_literal_node(node):
        raise ValueError("Expected integer literal node")
    return int(node.value)


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
        return f"({text})" if needs_brackets else text
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
            lines.append(f"Сначала считаем в скобках: {step['left']} {step['operator']} {step['right']} = {step['result']}")
            continue
        prefix = "Сначала" if index == 0 else "Потом" if index == 1 else "Дальше"
        lines.append(f"{prefix} {step['verb']}: {step['left']} {step['operator']} {step['right']} = {step['result']}")
    return lines


def flatten_add_chain(node: ast.AST) -> Optional[List[int]]:
    if is_int_literal_node(node):
        value = int_from_literal_node(node)
        return [value] if value >= 0 else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = flatten_add_chain(node.left)
        right = flatten_add_chain(node.right)
        if left is None or right is None:
            return None
        return left + right
    return None


def count_two_digit_numbers(nums: List[int]) -> int:
    return sum(1 for n in nums if 10 <= abs(n) <= 99)


def should_use_column_for_sum(nums: List[int]) -> bool:
    if any(abs(n) >= 100 for n in nums):
        return True
    return count_two_digit_numbers(nums) > 2


def get_digits(n: int) -> List[int]:
    return [int(ch) for ch in str(abs(n))]


def digits_by_place(n: int, width: int) -> List[int]:
    s = str(abs(n)).rjust(width, "0")
    return [int(ch) for ch in s]


def split_tens_units(n: int) -> Tuple[int, int]:
    return n - n % 10, n % 10


def explain_addition_via_ten(left: int, right: int) -> str:
    to_ten = 10 - left
    rest = right - to_ten
    total = left + right
    return join_explanation_lines(
        "Ищем сумму",
        f"Чтобы получить 10, к {left} нужно прибавить {to_ten}",
        f"Разложим {right} на {to_ten} и {rest}",
        f"{left} + {to_ten} = 10, потом 10 + {rest} = {total}",
        f"Ответ: {total}",
        "Совет: если удобно, сначала доводи число до 10",
    )


def explain_subtraction_via_ten(left: int, right: int) -> str:
    first_part = left % 10
    second_part = right - first_part
    result = left - right
    return join_explanation_lines(
        "Ищем разность",
        f"Разложим {right} на {first_part} и {second_part}",
        f"Сначала {left} - {first_part} = 10",
        f"Потом 10 - {second_part} = {result}",
        f"Ответ: {result}",
        "Совет: при вычитании через десяток удобно сначала дойти до 10",
    )


def explain_subtraction_two_digit_with_borrow(minuend: int, subtrahend: int) -> Optional[str]:
    """Объяснение вычитания двузначных чисел с переходом через десяток (устный приём)."""
    if minuend < 20 or subtrahend < 10:
        return None
    if minuend % 10 >= subtrahend % 10:
        return None  # нет перехода
    tens = (minuend // 10 - 1) * 10
    units = 10 + (minuend % 10)
    subtrahend_tens = (subtrahend // 10) * 10
    subtrahend_units = subtrahend % 10
    result = minuend - subtrahend
    return join_explanation_lines(
        "Ищем разность",
        f"Представим {minuend} как {tens} + {units}",
        f"Представим {subtrahend} как {subtrahend_tens} + {subtrahend_units}",
        f"Вычитаем десятки: {tens} - {subtrahend_tens} = {tens - subtrahend_tens}",
        f"Вычитаем единицы: {units} - {subtrahend_units} = {units - subtrahend_units}",
        f"Складываем полученные разности: {tens - subtrahend_tens} + {units - subtrahend_units} = {result}",
        f"Ответ: {result}",
        "Совет: при вычитании с переходом через десяток удобно разложить уменьшаемое",
    )


def explain_column_addition(numbers: List[int]) -> str:
    ordered = sorted(numbers, key=lambda x: (len(str(abs(x))), abs(x)), reverse=True)
    width = max(len(str(abs(n))) for n in ordered)
    columns = [digits_by_place(n, width) for n in ordered]
    carry = 0
    lines = [
        "Пишем числа в столбик: единицы под единицами, десятки под десятками и так далее",
        "Начинаем сложение с единиц",
    ]
    for pos_from_right in range(width):
        idx = width - 1 - pos_from_right
        digits = [col[idx] for col in columns]
        total = sum(digits) + carry
        digit = total % 10
        new_carry = total // 10
        place_name = PLACE_NAMES[pos_from_right] if pos_from_right < len(PLACE_NAMES) else "разряд"
        expr = " + ".join(str(d) for d in digits)
        if carry:
            if new_carry:
                next_place = NEXT_PLACE_NAMES[pos_from_right] if pos_from_right < len(NEXT_PLACE_NAMES) else "следующий разряд"
                lines.append(f"{place_name.capitalize()}: {expr} и ещё {carry} = {total}. Пишем {digit}, {new_carry} {next_place} запоминаем")
            else:
                lines.append(f"{place_name.capitalize()}: {expr} и ещё {carry} = {total}. Пишем {digit}")
        else:
            if new_carry:
                next_place = NEXT_PLACE_NAMES[pos_from_right] if pos_from_right < len(NEXT_PLACE_NAMES) else "следующий разряд"
                lines.append(f"{place_name.capitalize()}: {expr} = {total}. Пишем {digit}, {new_carry} {next_place} запоминаем")
            else:
                lines.append(f"{place_name.capitalize()}: {expr} = {total}. Пишем {digit}")
        carry = new_carry
    if carry:
        lines.append(f"В следующем разряде записываем {carry}")
    total = sum(ordered)
    lines.append(f"Читаем ответ: сумма равна {total}")
    return join_explanation_lines(*lines, f"Ответ: {total}", "Совет: в столбике всегда начинай с младшего разряда")


def explain_column_subtraction(minuend: int, subtrahend: int) -> str:
    if subtrahend > minuend:
        return join_explanation_lines(
            "Первое число меньше второго",
            f"Считаем: {minuend} - {subtrahend} = {minuend - subtrahend}",
            f"Ответ: {minuend - subtrahend}",
            "Совет: перед вычитанием сравни числа",
        )
    work = get_digits(minuend)
    sub = get_digits(subtrahend)
    width = max(len(work), len(sub))
    work = [0] * (width - len(work)) + work
    sub = [0] * (width - len(sub)) + sub
    lines = [
        "Пишем числа в столбик: единицы под единицами, десятки под десятками и так далее",
        "Начинаем вычитание с единиц",
    ]
    result = [0] * width

    for pos_from_right in range(width):
        idx = width - 1 - pos_from_right
        top = work[idx]
        bottom = sub[idx]
        place_name = PLACE_NAMES[pos_from_right] if pos_from_right < len(PLACE_NAMES) else "разряд"
        if top >= bottom:
            result[idx] = top - bottom
            lines.append(f"{place_name.capitalize()}: {top} - {bottom} = {result[idx]}")
            continue

        j = idx - 1
        while j >= 0 and work[j] == 0:
            j -= 1
        if j < 0:
            return join_explanation_lines(
                "В этом примере не получается выполнить вычитание обычным способом",
                "Ответ: проверь запись примера",
                "Совет: уменьшаемое должно быть не меньше вычитаемого",
            )

        work[j] -= 1
        for k in range(j + 1, idx):
            work[k] = 9
        work[idx] += 10
        borrowed_value = work[idx]
        if idx - j == 1:
            higher_place = NEXT_PLACE_NAMES[pos_from_right] if pos_from_right < len(NEXT_PLACE_NAMES) else "следующий разряд"
            lines.append(
                f"Из {top} нельзя вычесть {bottom}. Занимаем 1 {higher_place}. Получаем {borrowed_value}. {borrowed_value} - {bottom} = {borrowed_value - bottom}"
            )
        else:
            lines.append(
                f"Из {top} нельзя вычесть {bottom}. Слева есть нули, поэтому занимаем в более старшем разряде. Получаем {borrowed_value}. {borrowed_value} - {bottom} = {borrowed_value - bottom}"
            )
        result[idx] = borrowed_value - bottom
        work[idx] = result[idx]

    answer = int("".join(str(d) for d in result))
    lines.append(f"Читаем ответ: разность равна {answer}")
    return join_explanation_lines(*lines, f"Ответ: {answer}", "Совет: если разряда не хватает, занимаем 1 из соседнего старшего разряда")


def explain_long_multiplication(left: int, right: int) -> str:
    a, b = left, right
    if len(str(abs(a))) < len(str(abs(b))):
        a, b = b, a
    result = a * b
    lines = ["Пишем множители столбиком: единицы под единицами, десятки под десятками и так далее"]
    if abs(b) < 10:
        carry = 0
        digits = get_digits(a)
        for pos_from_right, digit in enumerate(reversed(digits)):
            place_name = PLACE_NAMES[pos_from_right] if pos_from_right < len(PLACE_NAMES) else "разряд"
            total = digit * b + carry
            write_digit = total % 10
            new_carry = total // 10
            if carry:
                if new_carry:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} и ещё {carry} = {total}. Пишем {write_digit}, {new_carry} запоминаем")
                else:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} и ещё {carry} = {total}. Пишем {write_digit}")
            else:
                if new_carry:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} = {total}. Пишем {write_digit}, {new_carry} запоминаем")
                else:
                    lines.append(f"{place_name.capitalize()}: {digit} × {b} = {total}. Пишем {write_digit}")
            carry = new_carry
        if carry:
            lines.append(f"В старшем разряде записываем {carry}")
        lines.append(f"Читаем ответ: произведение равно {result}")
        return join_explanation_lines(*lines, f"Ответ: {result}", "Совет: в столбике умножай по разрядам справа налево")

    digits_b = list(reversed(get_digits(b)))
    partials = []
    for idx, digit in enumerate(digits_b):
        place_value = digit * (10 ** idx)
        if digit == 0:
            lines.append(f"В разряде {PLACE_NAMES[idx] if idx < len(PLACE_NAMES) else 'разряда'} второго множителя стоит 0, это неполное произведение пропускаем")
            continue
        partial = a * place_value
        partials.append(partial)
        lines.append(f"Находим неполное произведение: {a} × {place_value} = {partial}")
    if len(partials) > 1:
        lines.append(f"Складываем неполные произведения: {' + '.join(str(p) for p in partials)} = {result}")
    lines.append(f"Читаем ответ: произведение равно {result}")
    return join_explanation_lines(*lines, f"Ответ: {result}", "Совет: в умножении столбиком сначала находят неполные произведения, потом их складывают")


def build_long_division_steps(dividend: int, divisor: int):
    digits = list(str(dividend))
    steps = []
    current = ""
    quotient_digits = []
    started = False
    for index, digit in enumerate(digits):
        current += digit
        current_number = int(current)
        if current_number < divisor:
            if started:
                quotient_digits.append(("zero", current_number, index))
            continue
        started = True
        q_digit = current_number // divisor
        product = q_digit * divisor
        remainder = current_number - product
        next_digit = int(digits[index + 1]) if index + 1 < len(digits) else None
        steps.append({"current": current_number, "q_digit": q_digit, "product": product, "remainder": remainder, "next_digit": next_digit, "index": index})
        quotient_digits.append(("digit", q_digit, index))
        current = str(remainder)
    if not started:
        quotient_digits = [("digit", 0, 0)]
    remainder = int(current or "0")
    return {"steps": steps, "quotient": dividend // divisor if divisor != 0 else None, "remainder": remainder, "quotient_digits": quotient_digits}


def explain_long_division(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: сначала смотри на делитель")
    quotient, remainder = divmod(dividend, divisor)
    model = build_long_division_steps(dividend, divisor)
    steps = model["steps"]
    lines = ["Пишем деление столбиком", "Сначала находим первое неполное делимое"]
    if not steps:
        lines.append(f"{dividend} меньше {divisor}, значит в частном будет 0")
        if remainder:
            lines.append(f"Остаток равен {remainder}")
        answer_text = "0" if remainder == 0 else f"0, остаток {remainder}"
        return join_explanation_lines(*lines, f"Ответ: {answer_text}", "Совет: если делимое меньше делителя, частное начинается с нуля")

    lines.append(f"Первое неполное делимое — {steps[0]['current']}")
    step_idx = 0
    quotient_started = False
    current = ""
    digits = list(str(dividend))
    for digit_char in digits:
        current += digit_char
        current_number = int(current)
        if current_number < divisor and quotient_started:
            lines.append(f"Число {current_number} меньше {divisor}, поэтому в частном пишем 0 и сносим следующую цифру")
            continue
        if current_number < divisor:
            continue
        quotient_started = True
        step = steps[step_idx]
        q_digit = step["q_digit"]
        product = step["product"]
        remainder_here = step["remainder"]
        next_try = (q_digit + 1) * divisor
        if next_try > current_number:
            choose_line = f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше"
        else:
            choose_line = f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}"
        if step["next_digit"] is not None:
            next_number = int(str(remainder_here) + str(step["next_digit"]))
            lines.append(f"{choose_line}. Вычитаем: {step['current']} - {product} = {remainder_here}. Сносим следующую цифру и получаем {next_number}")
        elif remainder_here == 0:
            lines.append(f"{choose_line}. Вычитаем: {step['current']} - {product} = 0. Деление закончено")
        else:
            lines.append(f"{choose_line}. Вычитаем: {step['current']} - {product} = {remainder_here}. Это остаток")
        current = str(remainder_here)
        step_idx += 1

    if remainder == 0:
        lines.append(f"Читаем ответ: частное равно {quotient}")
        return join_explanation_lines(*lines, f"Ответ: {quotient}", "Совет: в столбике повторяй шаги: взял, подобрал, умножил, вычел, снес цифру")
    lines.append(f"Читаем ответ: частное равно {quotient}, остаток {remainder}")
    return join_explanation_lines(*lines, f"Ответ: {quotient}, остаток {remainder}", "Совет: остаток всегда должен быть меньше делителя")


def explain_simple_addition(left: int, right: int) -> str:
    total = left + right
    if 0 <= left < 10 and 0 <= right < 10 and total > 10:
        return explain_addition_via_ten(left, right)
    if 10 <= left <= 99 and 10 <= right <= 99:
        lt, lu = split_tens_units(left)
        rt, ru = split_tens_units(right)
        return join_explanation_lines(
            "Ищем сумму",
            f"Разложим числа на десятки и единицы: {left} = {lt} + {lu}, {right} = {rt} + {ru}",
            f"Складываем десятки: {lt} + {rt} = {lt + rt}",
            f"Складываем единицы: {lu} + {ru} = {lu + ru}",
            f"Теперь складываем результаты: {lt + rt} + {lu + ru} = {total}",
            f"Ответ: {total}",
            "Совет: двузначные числа удобно раскладывать на десятки и единицы",
        )
    if left >= 100 or right >= 100:
        return explain_column_addition([left, right])
    return join_explanation_lines("Ищем сумму", f"Считаем: {left} + {right} = {total}", f"Ответ: {total}", "Совет: называй числа по порядку")


def explain_simple_subtraction(left: int, right: int) -> str:
    result = left - right
    if 10 < left < 20 and 0 < right < 10 and left % 10 < right:
        return explain_subtraction_via_ten(left, right)
    if 10 <= left <= 99 and 10 <= right <= 99 and result >= 0 and left < 100:
        # попробуем устный приём с переходом через десяток
        if left % 10 < right % 10:
            explanation = explain_subtraction_two_digit_with_borrow(left, right)
            if explanation:
                return explanation
        lt, lu = split_tens_units(left)
        rt, ru = split_tens_units(right)
        if lu >= ru:
            return join_explanation_lines(
                "Ищем разность",
                f"Разложим числа на десятки и единицы: {left} = {lt} + {lu}, {right} = {rt} + {ru}",
                f"Вычитаем десятки: {lt} - {rt} = {lt - rt}",
                f"Вычитаем единицы: {lu} - {ru} = {lu - ru}",
                f"Теперь складываем результаты: {lt - rt} + {lu - ru} = {result}",
                f"Ответ: {result}",
                "Совет: двузначные числа удобно раскладывать на десятки и единицы",
            )
    if left >= 100 and right >= 0 and result >= 0:
        return explain_column_subtraction(left, right)
    if result < 0:
        return join_explanation_lines(
            "Сначала сравниваем числа",
            f"{left} меньше {right}, поэтому ответ будет отрицательным",
            f"Считаем: {left} - {right} = {result}",
            f"Ответ: {result}",
            "Совет: перед вычитанием полезно сравнить числа",
        )
    return join_explanation_lines("Ищем разность", f"Считаем: {left} - {right} = {result}", f"Ответ: {result}", "Совет: вычитай спокойно и следи за знаком минус")


def explain_two_digit_by_two_digit_multiplication(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    tens, units = split_tens_units(small)
    first = big * tens
    second = big * units
    result = left * right
    return join_explanation_lines(
        "Ищем произведение",
        f"Разложим {small} на {tens} и {units}",
        f"{big} × {tens} = {first}",
        f"{big} × {units} = {second}",
        f"Складываем частичные результаты: {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: при умножении удобно разложить одно число на десятки и единицы",
    )


def explain_multiply_divide_by_power_of_10(left: int, right: int, op) -> Optional[str]:
    """Объяснение умножения/деления на 10, 100, 1000."""
    if op is ast.Mult:
        if right in (10, 100, 1000):
            result = left * right
            zeros = len(str(right)) - 1
            return join_explanation_lines(
                f"Умножение на {right}",
                f"При умножении на {right} к числу справа дописываем {zeros} нул{'ь' if zeros == 1 else 'я' if 2 <= zeros <= 4 else 'ей'}",
                f"{left} × {right} = {result}",
                f"Ответ: {result}",
                "Совет: запомни правило умножения на 10, 100, 1000",
            )
        if left in (10, 100, 1000):
            return explain_multiply_divide_by_power_of_10(right, left, op)
    elif op is ast.Div:
        if right in (10, 100, 1000):
            if left % right != 0:
                return None
            result = left // right
            zeros = len(str(right)) - 1
            return join_explanation_lines(
                f"Деление на {right}",
                f"При делении на {right} у числа справа отбрасываем {zeros} нул{'ь' if zeros == 1 else 'я' if 2 <= zeros <= 4 else 'ей'}",
                f"{left} : {right} = {result}",
                f"Ответ: {result}",
                "Совет: запомни правило деления на 10, 100, 1000",
            )
    return None


def explain_two_digit_division(dividend: int, divisor: int) -> Optional[str]:
    """Объяснение деления двузначного на двузначное с однозначным частным методом подбора."""
    if divisor < 10 or dividend < 10 or dividend >= 100 or divisor >= 100:
        return None
    if dividend % divisor != 0:
        return None
    quotient = dividend // divisor
    if quotient >= 10:
        return None
    return join_explanation_lines(
        f"Нужно разделить {dividend} на {divisor}",
        f"Подбираем число, которое при умножении на {divisor} даст {dividend}",
        f"Пробуем: {divisor} × {quotient} = {dividend}",
        f"Значит, {dividend} : {divisor} = {quotient}",
        f"Ответ: {quotient}",
        "Совет: при делении двузначного на двузначное подбирай частное умножением",
    )


def explain_simple_multiplication(left: int, right: int) -> str:
    # сначала проверяем умножение на 10,100,1000
    power10 = explain_multiply_divide_by_power_of_10(left, right, ast.Mult)
    if power10:
        return power10
    result = left * right
    big = max(left, right)
    small = min(left, right)
    if big >= 100:
        return explain_long_multiplication(left, right)
    if 10 <= left <= 99 and 10 <= right <= 99:
        return explain_two_digit_by_two_digit_multiplication(left, right)
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
    return join_explanation_lines("Ищем произведение", f"Считаем: {left} × {right} = {result}", f"Ответ: {result}", "Совет: умножение показывает одинаковые группы")


def explain_simple_division(left: int, right: int) -> str:
    if right == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: сначала смотри на делитель")
    # проверка деления на 10,100,1000
    power10 = explain_multiply_divide_by_power_of_10(left, right, ast.Div)
    if power10:
        return power10
    quotient, remainder = divmod(left, right)
    if left < 100 and right < 100 and 10 <= right <= 99 and remainder == 0 and quotient < 10:
        two_digit_div = explain_two_digit_division(left, right)
        if two_digit_div:
            return two_digit_div
    if left < 100 and right < 10:
        if remainder == 0:
            return join_explanation_lines(
                "Ищем, на какое число нужно умножить делитель, чтобы получить делимое",
                f"{quotient} × {right} = {left}, значит {left} : {right} = {quotient}",
                f"Ответ: {quotient}",
                "Совет: в простом делении полезно проверять умножением",
            )
        return join_explanation_lines(
            "Ищем, сколько полных раз делитель помещается в делимом",
            f"{quotient} × {right} = {quotient * right}",
            f"Остаток: {left} - {quotient * right} = {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше делителя",
        )
    if left < 100 and right < 100 and remainder == 0:
        return join_explanation_lines(
            "Ищем, на какое число нужно умножить делитель, чтобы получить делимое",
            f"{right} × {quotient} = {left}",
            f"Значит, {left} : {right} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: при делении двузначных чисел помогает подбор и проверка умножением",
        )
    return explain_long_division(left, right)


def try_simple_binary_int_expression(node: ast.AST) -> Optional[dict]:
    if not isinstance(node, ast.BinOp):
        return None
    if not is_int_literal_node(node.left) or not is_int_literal_node(node.right):
        return None
    left = int_from_literal_node(node.left)
    right = int_from_literal_node(node.right)
    if left < 0 or right < 0:
        return None
    return {"operator": type(node.op), "left": left, "right": right}


def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None

    add_chain = flatten_add_chain(node)
    if add_chain and all(n >= 0 for n in add_chain):
        if should_use_column_for_sum(add_chain):
            return explain_column_addition(add_chain)
        if len(add_chain) == 2:
            return explain_simple_addition(add_chain[0], add_chain[1])
        current = add_chain[0]
        lines = ["Ищем сумму нескольких чисел"]
        for idx, n in enumerate(add_chain[1:], start=1):
            new_total = current + n
            prefix = "Сначала" if idx == 1 else "Потом" if idx == 2 else "Дальше"
            lines.append(f"{prefix} складываем: {current} + {n} = {new_total}")
            current = new_total
        lines.extend([f"Ответ: {current}", "Совет: при нескольких действиях считай по порядку"])
        return join_explanation_lines(*lines)

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
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: сначала смотри на делитель")
    except Exception:
        return None

    if not steps:
        return None

    body_lines = format_step_lines(steps, source)
    answer = format_fraction(value)
    advice = "сначала выполняй умножение и деление, потом сложение и вычитание" if re.search(r"[+\-].*[*/]|[*/].*[+\-]", source) else default_advice("expression")
    return join_explanation_lines(*body_lines, f"Ответ: {answer}", f"Совет: {advice}")


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
        return join_explanation_lines("У дроби знаменатель не может быть равен нулю", "Ответ: запись дроби неверная", "Совет: сначала проверь знаменатели")
    action_symbol = "+" if operator == "+" else "-"
    result = Fraction(a, b) + Fraction(c, d) if operator == "+" else Fraction(a, b) - Fraction(c, d)
    if b == d:
        top_result = a + c if operator == "+" else a - c
        lines = [
            "Сначала смотрим на знаменатели. Они одинаковые",
            f"Значит, работаем только с числителями: {a} {action_symbol} {c} = {top_result}",
            f"Получаем дробь {top_result}/{b}",
        ]
        if format_fraction(result) != f"{top_result}/{b}":
            lines.append(f"Сокращаем: {top_result}/{b} = {format_fraction(result)}")
        lines.extend([f"Ответ: {format_fraction(result)}", "Совет: при одинаковых знаменателях меняется только числитель"])
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
    lines.extend([f"Ответ: {format_fraction(result)}", "Совет: сначала приводи дроби к общему знаменателю"])
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
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind in {"x_plus", "plus_x"}:
            answer = rhs_value - number
            check_template = f"x + {number_text}" if kind == "x_plus" else f"{number_text} + x"
            return join_explanation_lines(
                "Ищем неизвестное слагаемое",
                f"Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {rhs_text} - {number_text} = {format_fraction(answer)}",
                format_equation_check(check_template, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное слагаемое находим вычитанием",
            )

        if kind == "x_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Ищем неизвестное уменьшаемое",
                f"Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: {rhs_text} + {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x - {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное уменьшаемое находим сложением",
            )

        if kind == "minus_x":
            answer = number - rhs_value
            return join_explanation_lines(
                "Ищем неизвестное вычитаемое",
                f"Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: {number_text} - {rhs_text} = {format_fraction(answer)}",
                format_equation_check(f"{number_text} - x", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное вычитаемое находим вычитанием",
            )

        if kind in {"x_mul", "mul_x"}:
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines("При умножении на 0 всегда получается 0", "Значит, подходит любое число", "Ответ: подходит любое число", "Совет: 0 × любое число = 0")
                return join_explanation_lines("При умножении на 0 нельзя получить другое число", "Ответ: решения нет", "Совет: проверь уравнение ещё раз")
            answer = rhs_value / number
            check_template = f"x × {number_text}" if kind == "x_mul" else f"{number_text} × x"
            return join_explanation_lines(
                "Ищем неизвестный множитель",
                f"Чтобы найти неизвестный множитель, произведение делим на известный множитель: {rhs_text} : {number_text} = {format_fraction(answer)}",
                format_equation_check(check_template, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестный множитель находим делением",
            )

        if kind == "x_div":
            if number == 0:
                return join_explanation_lines("На ноль делить нельзя", "Ответ: решения нет", "Совет: проверь делитель")
            answer = rhs_value * number
            return join_explanation_lines(
                "Ищем неизвестное делимое",
                f"Чтобы найти неизвестное делимое, делитель умножаем на частное: {rhs_text} × {number_text} = {format_fraction(answer)}",
                format_equation_check(f"x : {number_text}", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное делимое находим умножением",
            )

        if kind == "div_x":
            if rhs_value == 0:
                return join_explanation_lines("На ноль делить нельзя, а частное здесь равно 0", "Ответ: решения нет", "Совет: проверь уравнение ещё раз")
            answer = number / rhs_value
            return join_explanation_lines(
                "Ищем неизвестный делитель",
                f"Чтобы найти неизвестный делитель, делимое делим на частное: {number_text} : {rhs_text} = {format_fraction(answer)}",
                format_equation_check(f"{number_text} : x", format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестный делитель находим делением",
            )
    return None


def apply_more_less(base: int, delta: int, mode: str) -> Optional[int]:
    if mode == "больше":
        return base + delta
    result = base - delta
    return result if result >= 0 else None


def apply_times_relation(base: int, factor: int, mode: str) -> Optional[int]:
    if factor == 0:
        return None
    if mode == "больше":
        return base * factor
    if base % factor != 0:
        return None
    return base // factor


def explain_ratio_word_problem(first: int, second: int) -> Optional[str]:
    bigger = max(first, second)
    smaller = min(first, second)
    if smaller == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: в задаче «во сколько раз» делим только на ненулевое число")
    if bigger % smaller != 0:
        return None
    result = bigger // smaller
    return join_explanation_lines(
        "Нужно узнать, во сколько раз одно число больше или меньше другого",
        f"Для этого большее число делим на меньшее: {bigger} : {smaller} = {result}",
        f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
        "Совет: вопрос «во сколько раз» решаем делением",
    )


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Нужно узнать, сколько всего или сколько стало",
        f"Подходит сложение: {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают про всё вместе, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько осталось или сколько стало меньше",
        f"Подходит вычитание: {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если что-то убрали, отдали или потратили, обычно нужно вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, на сколько одно число больше или меньше другого",
        f"Для этого из большего числа вычитаем меньшее: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решаем вычитанием",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала",
        f"Если осталось {remaining} и убрали {removed}, то сначала было {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находим сложением",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала",
        f"Если стало {final_total} после прибавления {added}, то сначала было {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: если к числу что-то прибавили, начальное число находим вычитанием",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько добавили",
        f"Сравниваем, сколько было и сколько стало: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, сравни число было и число стало",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько убрали",
        f"Из того, что было, вычитаем то, что осталось: {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестное вычитаемое находим вычитанием",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Нужно узнать, сколько всего одинаковых предметов",
        f"Если число {per_group} повторяется {groups} раз, используем умножение: {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: проверь, на сколько частей делят")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько получит каждый",
            f"Для этого делим поровну: {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        "Нужно разделить поровну",
        f"Делим: {total} : {groups} = {quotient}, остаток {remainder}",
        f"Ответ: каждому по {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов", "Ответ: запись задачи неверная", "Совет: проверь, сколько предметов должно быть в одной группе")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько групп получится",
            f"Для этого делим общее количество на число предметов в одной группе: {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находим делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}",
            "Но предметы ещё остались, значит нужна ещё одна группа",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления что-то осталось, иногда нужна ещё одна коробка или место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            "Нужно узнать, сколько полных групп получится",
            f"Делим: {total} : {per_group} = {quotient}, остаток {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        "Сначала находим второе количество",
        f"Оно на {delta} {mode}, значит считаем так: {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: если одно число больше или меньше другого, сначала найди это число",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {sign} {delta} = {related}",
        f"Потом находим всё вместе: {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала найди недостающее число, потом отвечай на главный вопрос",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        "Сначала находим второе количество",
        f"Оно в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, значит считаем так: {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: если число стало в несколько раз больше, умножаем; если в несколько раз меньше, делим",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    total = base + related
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {op} {factor} = {related}",
        f"Потом находим всё вместе: {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: сначала найди зависимое число, потом считай общее количество",
    )


def explain_related_quantity_and_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {sign} {delta} = {related}",
        f"Потом находим всё вместе: {base} + {related} = {total}",
        f"Ответ: второе количество — {related}; всего — {total}",
        "Совет: сначала найди второе число, потом считай всё вместе",
    )


def explain_related_quantity_and_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {op} {factor} = {related}",
        f"Потом находим всё вместе: {base} + {related} = {total}",
        f"Ответ: второе количество — {related}; всего — {total}",
        "Совет: сначала найди второе число, потом считай всё вместе",
    )


def explain_indirect_plus_minus_total_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        other = base - delta
        if other < 0:
            return None
        sign = "-"
        relation_text = "другое число на столько же меньше"
    else:
        other = base + delta
        sign = "+"
        relation_text = "другое число на столько же больше"
    total = base + other
    return join_explanation_lines(
        f"Это косвенная форма: если здесь на {delta} {relation}, то {relation_text}",
        f"Сначала находим второе число: {base} {sign} {delta} = {other}",
        f"Потом находим всё вместе: {base} + {other} = {total}",
        f"Ответ: второе количество — {other}; всего — {total}",
        "Совет: в косвенной задаче сначала переведи её в прямую",
    )


def explain_indirect_times_total_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        other = base // factor
        op = ":"
        relation_text = "другое число во столько же раз меньше"
    else:
        other = base * factor
        op = "×"
        relation_text = "другое число во столько же раз больше"
    total = base + other
    return join_explanation_lines(
        f"Это косвенная форма: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {relation_text}",
        f"Сначала находим второе число: {base} {op} {factor} = {other}",
        f"Потом находим всё вместе: {base} + {other} = {total}",
        f"Ответ: второе количество — {other}; всего — {total}",
        "Совет: в косвенной задаче сначала переведи её в прямую",
    )


def explain_relation_chain_total_word_problem(base: int, delta1: int, mode1: str, delta2: int, mode2: str) -> Optional[str]:
    second = apply_more_less(base, delta1, mode1)
    if second is None:
        return None
    third = apply_more_less(second, delta2, mode2)
    if third is None:
        return None
    total = base + second + third
    sign1 = "+" if mode1 == "больше" else "-"
    sign2 = "+" if mode2 == "больше" else "-"
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {sign1} {delta1} = {second}",
        f"Потом находим третье количество: {second} {sign2} {delta2} = {third}",
        f"Теперь находим всё вместе: {base} + {second} + {third} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят все неизвестные количества",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"Сначала находим одну группу: {total_amount} : {groups} = {one_group}",
        f"Потом находим {target_groups} таких же групп: {one_group} × {target_groups} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_find_third_addend_word_problem(total: int, first: int, second: int) -> Optional[str]:
    known = first + second
    result = total - known
    if result < 0:
        return None
    return join_explanation_lines(
        f"Сначала находим сумму известных частей: {first} + {second} = {known}",
        f"Потом из общего количества вычитаем эту сумму: {total} - {known} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестную часть находим вычитанием из целого",
    )


def explain_initial_from_taken_and_left_word_problem(first_taken: int, second_taken: int, left: int) -> Optional[str]:
    taken = first_taken + second_taken
    total = taken + left
    return join_explanation_lines(
        f"Сначала находим, сколько всего взяли: {first_taken} + {second_taken} = {taken}",
        f"Потом находим, сколько было сначала: {taken} + {left} = {total}",
        f"Ответ: {total}",
        "Совет: если известны взяли и осталось, начальное число находим сложением",
    )


def explain_other_from_total_and_part_word_problem(total: int, known_part: int) -> Optional[str]:
    other = total - known_part
    if other < 0:
        return None
    return join_explanation_lines(
        f"Из общего количества вычитаем известную часть: {total} - {known_part} = {other}",
        f"Ответ: {other}",
        "Совет: если известно всё число и одна часть, другую часть находят вычитанием",
    )


def explain_compare_from_total_and_part_word_problem(total: int, known_part: int) -> Optional[str]:
    other = total - known_part
    if other < 0:
        return None
    bigger = max(known_part, other)
    smaller = min(known_part, other)
    diff = bigger - smaller
    return join_explanation_lines(
        f"Сначала находим вторую часть: {total} - {known_part} = {other}",
        f"Потом сравниваем части: {bigger} - {smaller} = {diff}",
        f"Ответ: {diff}",
        "Совет: в такой задаче сначала найди неизвестную часть, потом сравни",
    )


def explain_sum_of_two_products_word_problem(first_count: int, first_value: int, second_count: int, second_value: int) -> str:
    first_total = first_count * first_value
    second_total = second_count * second_value
    total = first_total + second_total
    return join_explanation_lines(
        f"Сначала находим первую часть: {first_count} × {first_value} = {first_total}",
        f"Потом находим вторую часть: {second_count} × {second_value} = {second_total}",
        f"Теперь находим всё вместе: {first_total} + {second_total} = {total}",
        f"Ответ: {total}",
        "Совет: если есть две группы вида «по столько-то», сначала находят каждую группу",
    )


def explain_meeting_other_speed_word_problem(total_distance: int, first_speed: int, first_path: int, distance_unit: str = "", speed_unit: str = "") -> Optional[str]:
    if first_speed == 0 or first_path % first_speed != 0:
        return None
    time_value = first_path // first_speed
    second_path = total_distance - first_path
    if time_value <= 0 or second_path < 0 or second_path % time_value != 0:
        return None
    second_speed = second_path // time_value
    answer = f"{second_speed} {speed_unit}".strip() if speed_unit else str(second_speed)
    return join_explanation_lines(
        f"Сначала находим время до встречи: {first_path} : {first_speed} = {time_value}",
        f"Потом находим путь второго участника: {total_distance} - {first_path} = {second_path}",
        f"Теперь находим его скорость: {second_path} : {time_value} = {second_speed}",
        f"Ответ: {answer}",
        "Совет: если известны путь и время, скорость находят делением",
    )


def explain_opposite_other_speed_word_problem(distance_after: int, time_value: int, first_speed: int, speed_unit: str = "") -> Optional[str]:
    if time_value == 0:
        return None
    first_path = first_speed * time_value
    second_path = distance_after - first_path
    if second_path < 0 or second_path % time_value != 0:
        return None
    second_speed = second_path // time_value
    answer = f"{second_speed} {speed_unit}".strip() if speed_unit else str(second_speed)
    return join_explanation_lines(
        f"Сначала находим путь первого участника: {first_speed} × {time_value} = {first_path}",
        f"Потом находим путь второго участника: {distance_after} - {first_path} = {second_path}",
        f"Теперь находим его скорость: {second_path} : {time_value} = {second_speed}",
        f"Ответ: {answer}",
        "Совет: если известны путь и время, скорость находят делением",
    )


def explain_meeting_distance_with_related_speed_word_problem(time_value: int, first_speed: int, delta: int, mode: str, distance_unit: str = "") -> Optional[str]:
    second_speed = apply_more_less(first_speed, delta, mode)
    if second_speed is None:
        return None
    first_path = first_speed * time_value
    second_path = second_speed * time_value
    total_distance = first_path + second_path
    answer = f"{total_distance} {distance_unit}".strip() if distance_unit else str(total_distance)
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"Сначала находим скорость второго участника: {first_speed} {sign} {delta} = {second_speed}",
        f"Потом находим путь первого участника: {first_speed} × {time_value} = {first_path}",
        f"Находим путь второго участника: {second_speed} × {time_value} = {second_path}",
        f"Теперь складываем пути: {first_path} + {second_path} = {total_distance}",
        f"Ответ: {answer}",
        "Совет: при встречном движении расстояние складывается из двух путей",
    )


def explain_indirect_plus_minus_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        result = base - delta
        if result < 0:
            return None
        relation_text = "другое число на столько же меньше"
        op = "-"
    else:
        result = base + delta
        relation_text = "другое число на столько же больше"
        op = "+"
    return join_explanation_lines(
        f"Задача в косвенной форме: если это число на {delta} {relation}, то {relation_text}",
        f"Считаем: {base} {op} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала пойми, какое число больше, а какое меньше",
    )


def explain_indirect_times_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        result = base // factor
        op = ":"
        relation_text = "другое число во столько же раз меньше"
    else:
        result = base * factor
        op = "×"
        relation_text = "другое число во столько же раз больше"
    return join_explanation_lines(
        f"Задача в косвенной форме: если это число в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {relation_text}",
        f"Считаем: {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи слова в правильное действие",
    )


def explain_relation_chain_times_total_word_problem(base: int, factor1: int, mode1: str, factor2: int, mode2: str) -> Optional[str]:
    second = apply_times_relation(base, factor1, mode1)
    if second is None:
        return None
    third = apply_times_relation(second, factor2, mode2)
    if third is None:
        return None
    total = base + second + third
    op1 = "×" if mode1 == "больше" else ":"
    op2 = "×" if mode2 == "больше" else ":"
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {op1} {factor1} = {second}",
        f"Потом третье количество: {second} {op2} {factor2} = {third}",
        f"Теперь находим всё вместе: {base} + {second} + {third} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят зависимые количества, потом общее",
    )


def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        f"Сначала считаем, сколько предметов в одинаковых группах: {groups} × {per_group} = {grouped_total}",
        f"Потом прибавляем ещё {extra}: {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
        "Совет: если часть предметов разбита на одинаковые группы, сначала находи эту часть умножением",
    )


def explain_fraction_of_number_word_problem(total: int, numerator: int, denominator: int, ask_remaining: bool = False) -> Optional[str]:
    if denominator == 0 or numerator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    taken = one_part * numerator
    if ask_remaining:
        remaining = total - taken
        return join_explanation_lines(
            f"Сначала находим одну долю: {total} : {denominator} = {one_part}",
            f"Потом находим {numerator}/{denominator} числа: {one_part} × {numerator} = {taken}",
            f"Теперь находим, сколько осталось: {total} - {taken} = {remaining}",
            f"Ответ: {remaining}",
            "Совет: чтобы найти часть от числа, сначала дели на знаменатель, потом умножай на числитель",
        )
    return join_explanation_lines(
        f"Сначала находим одну долю: {total} : {denominator} = {one_part}",
        f"Потом находим {numerator}/{denominator} числа: {one_part} × {numerator} = {taken}",
        f"Ответ: {taken}",
        "Совет: чтобы найти часть от числа, сначала дели на знаменатель, потом умножай на числитель",
    )


def explain_number_by_fraction_word_problem(part_value: int, numerator: int, denominator: int) -> Optional[str]:
    if numerator == 0 or part_value % numerator != 0:
        return None
    one_part = part_value // numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"Сначала находим одну долю: {part_value} : {numerator} = {one_part}",
        f"Потом находим всё число: {one_part} × {denominator} = {whole}",
        f"Ответ: {whole}",
        "Совет: чтобы найти число по его части, дели на числитель и умножай на знаменатель",
    )


def explain_unit_rate_boxes_problem(groups: int, total_amount: int, wanted_amount: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    per_group = total_amount // groups
    if per_group == 0 or wanted_amount % per_group != 0:
        return None
    result = wanted_amount // per_group
    return join_explanation_lines(
        f"Сначала находим, сколько приходится на одну группу: {total_amount} : {groups} = {per_group}",
        f"Потом узнаём, сколько групп нужно: {wanted_amount} : {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят значение одной группы",
    )


def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"Сначала находим цену одной коробки: {total_cost} : {quantity} = {price}",
        f"Потом узнаём, сколько коробок можно купить: {wanted_cost} : {price} = {result}",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находи стоимость одной штуки",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    return join_explanation_lines(
        f"Сначала находим цену первой покупки: {total_a} : {quantity} = {price_a}",
        f"Потом находим цену второй покупки: {total_b} : {quantity} = {price_b}",
        f"Теперь сравниваем цены: {max(price_a, price_b)} - {min(price_a, price_b)} = {diff}",
        f"Ответ: {diff}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находи цену одной штуки",
    )


def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти расстояние",
        f"Расстояние равно скорости, умноженной на время: {speed} × {time_value} = {result}",
        f"Ответ: {answer}",
        "Совет: чтобы найти расстояние, скорость умножают на время",
    )


def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти скорость",
        f"Скорость равна расстоянию, делённому на время: {distance} : {time_value} = {result}",
        f"Ответ: {answer}",
        "Совет: чтобы найти скорость, расстояние делят на время",
    )


def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти время",
        f"Время равно расстоянию, делённому на скорость: {distance} : {speed} = {result}",
        f"Ответ: {answer}",
        "Совет: чтобы найти время, расстояние делят на скорость",
    )


def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"Сначала находим скорость сближения: {v1} + {v2} = {closing_speed}",
        f"Потом находим всё расстояние: {closing_speed} × {time_value} = {distance}",
        f"Ответ: {answer}",
        "Совет: при движении навстречу сначала находят скорость сближения",
    )


def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"Сначала находим скорость удаления: {v1} + {v2} = {removal_speed}",
        f"Потом находим расстояние: {removal_speed} × {time_value} = {distance}",
        f"Ответ: {answer}",
        "Совет: при движении в разные стороны сначала находят скорость удаления",
    )


def explain_catch_up_motion(distance: int, speed_diff: int, unit: str = "ч") -> Optional[str]:
    if speed_diff == 0 or distance % speed_diff != 0:
        return None
    time_value = distance // speed_diff
    answer = f"{time_value} {unit}".strip() if unit else str(time_value)
    return join_explanation_lines(
        "Нужно узнать, через сколько времени расстояние исчезнет",
        f"Для этого делим расстояние между объектами на скорость сближения: {distance} : {speed_diff} = {time_value}",
        f"Ответ: {answer}",
        "Совет: в задаче на догонку делят расстояние на разность скоростей",
    )


def has_word_stem(text: str, stems) -> bool:
    fragment = str(text or "").lower().replace("ё", "е")
    return any(re.search(rf"\b{re.escape(stem)}", fragment) for stem in stems)


def classify_change_fragment(fragment: str) -> Optional[str]:
    part = str(fragment or "").lower().replace("ё", "е")
    gain = has_word_stem(part, WORD_GAIN_HINTS)
    loss = has_word_stem(part, WORD_LOSS_HINTS)
    if gain and not loss:
        return "gain"
    if loss and not gain:
        return "loss"
    return None


def extract_relation_pairs(text: str):
    return [(int(match.group(1)), match.group(2)) for match in re.finditer(r"на\s+(\d+)\s+(больше|меньше)", str(text or ""))]


def extract_scale_pairs(text: str):
    return [(int(match.group(1)), match.group(2)) for match in re.finditer(r"в\s+(\d+)\s+раз(?:а)?\s+(больше|меньше)", str(text or ""))]


def split_between_change_fragment(fragment: str):
    part = str(fragment or "")
    pieces = re.split(r"(?:,\s*)?(?:а\s+потом|потом|а\s+затем|затем)\b", part, maxsplit=1)
    if len(pieces) == 2:
        return pieces[0], pieces[1]
    return part, part


def try_local_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    frac = extract_fraction_pair(lower)
    numbers = extract_ordered_numbers(lower)
    if not frac or len(numbers) < 3:
        return None
    numerator, denominator = frac
    candidates = [n for n in numbers if n not in {numerator, denominator}]
    if not candidates:
        return None
    first_number = candidates[0]
    if re.search(r"это\s+\d+\s*/\s*\d+\s+(?:всего\s+)?пути|это\s+\d+\s*/\s*\d+\s+всего", lower):
        return explain_number_by_fraction_word_problem(first_number, numerator, denominator)
    if "остал" in lower:
        return explain_fraction_of_number_word_problem(first_number, numerator, denominator, ask_remaining=True)
    if contains_any_fragment(lower, ("сколько потрат", "сколько выпил", "сколько израсход", "сколько взяли", "сколько состав")):
        return explain_fraction_of_number_word_problem(first_number, numerator, denominator, ask_remaining=False)
    if "сколько" in lower:
        if "всего" in lower or "какое расстояние" in lower or "какова длина" in lower or "какое число" in lower:
            return explain_number_by_fraction_word_problem(first_number, numerator, denominator)
        return explain_fraction_of_number_word_problem(first_number, numerator, denominator, ask_remaining=False)
    return None


def try_local_motion_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None

    distance_unit = "км" if "км" in lower else "м" if re.search(r"\bм\b", lower) else ""
    time_unit = "ч" if re.search(r"\bч\b|час", lower) else "мин" if "мин" in lower else ""
    speed_unit = "км/ч" if "км/ч" in lower else "м/с" if "м/с" in lower else ("км/ч" if distance_unit == "км" and time_unit == "ч" else "")

    speed_values = [int(v) for v in re.findall(r"(\d+)\s*км/ч", lower)] or [int(v) for v in re.findall(r"скорост[ьяию][^\d]{0,20}(\d+)", lower)]
    through_match = re.search(r"через\s+(\d+)\s*(?:ч|час|мин)", lower)
    speed_delta_match = re.search(r"на\s+(\d+)\s*км/ч\s+(больше|меньше)", lower)

    if "навстречу" in lower and "расстояние между" in lower and "до встречи" in lower:
        total_match = re.search(r"расстояние между[^\d]{0,40}(\d+)", lower)
        path_match = re.search(r"прош[её]л[^\d]{0,20}(\d+)\s*(?:км|м)", lower)
        if total_match and path_match and speed_values:
            total_distance = int(total_match.group(1))
            first_path = int(path_match.group(1))
            solved = explain_meeting_other_speed_word_problem(total_distance, speed_values[0], first_path, distance_unit, speed_unit)
            if solved:
                return solved

    if "в противоположных направлениях" in lower and through_match and "расстояние между" in lower:
        distance_match = re.search(r"расстояние между[^\d]{0,40}(\d+)", lower)
        first_speed_match = re.search(r"скорост[ьяию] первого[^\d]{0,20}(\d+)", lower)
        first_speed = int(first_speed_match.group(1)) if first_speed_match else (speed_values[0] if speed_values else None)
        if distance_match and first_speed is not None:
            solved = explain_opposite_other_speed_word_problem(int(distance_match.group(1)), int(through_match.group(1)), first_speed, speed_unit)
            if solved:
                return solved

    if "навстречу" in lower and through_match and speed_delta_match and speed_values:
        delta = int(speed_delta_match.group(1))
        mode = speed_delta_match.group(2)
        solved = explain_meeting_distance_with_related_speed_word_problem(int(through_match.group(1)), speed_values[0], delta, mode, distance_unit)
        if solved:
            return solved

    if "навстречу" in lower and len(speed_values) >= 2 and through_match and not speed_delta_match:
        return explain_meeting_motion(speed_values[0], speed_values[1], int(through_match.group(1)), distance_unit)
    if "в противоположных направлениях" in lower and len(speed_values) >= 2 and through_match and not speed_delta_match:
        return explain_opposite_motion(speed_values[0], speed_values[1], int(through_match.group(1)), distance_unit)
    if contains_any_fragment(lower, ("догонит", "догонку")) and len(nums) >= 2:
        return explain_catch_up_motion(nums[0], nums[1], time_unit or "ч")

    asks_distance = contains_any_fragment(lower, ("какое расстояние", "сколько километров", "какое расстояние пройдет", "какое расстояние он пройдет"))
    asks_speed = contains_any_fragment(lower, ("с какой скоростью", "какова скорость"))
    asks_time = contains_any_fragment(lower, ("сколько часов", "сколько времени", "за какое время"))

    if asks_distance and len(nums) >= 2:
        return explain_simple_motion_distance(nums[0], nums[1], distance_unit)
    if asks_speed and len(nums) >= 2:
        return explain_simple_motion_speed(nums[1], nums[0], speed_unit)
    if asks_time and len(nums) >= 2:
        return explain_simple_motion_time(nums[1], nums[0], time_unit or "ч")
    return None


def try_local_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None
    if contains_any_fragment(lower, ("за столько же", "на сколько пакет", "на сколько дороже", "на сколько дешевле")):
        return explain_price_difference_problem(nums[0], nums[1], nums[2])
    if contains_any_fragment(lower, ("сколько таких коробок", "сколько можно купить", "сколько коробок можно купить")):
        return explain_price_quantity_cost_problem(nums[0], nums[1], nums[2])
    return None


def try_local_unit_rate_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None

    if contains_any_fragment(lower, ("таких же", "такие же")):
        return explain_bring_to_unit_total_word_problem(nums[0], nums[1], nums[2])

    if contains_any_fragment(lower, ("сколько потребуется коробок", "сколько коробок", "сколько пакетов", "сколько сеток")) and "руб" not in lower:
        return explain_unit_rate_boxes_problem(nums[0], nums[1], nums[2])
    return None


def try_local_proportional_division_word_problem(raw_text: str) -> Optional[str]:
    """Задачи на пропорциональное деление: купили 10 наборов голубых и 4 красных, всего 350 руб."""
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None
    match = re.search(r"(\d+)\s+(?:набор|пакет|коробк|ящик)[а-я]*\s+[а-я]+\s+и\s+(\d+)\s+(?:набор|пакет|коробк|ящик)[а-я]*\s+[а-я]+", lower)
    if not match:
        return None
    count1 = int(match.group(1))
    count2 = int(match.group(2))
    total_cost = None
    for n in nums:
        if n not in (count1, count2) and n > count1 and n > count2:
            total_cost = n
            break
    if total_cost is None:
        return None
    total_count = count1 + count2
    if total_cost % total_count != 0:
        return None
    price_per_unit = total_cost // total_count
    cost1 = price_per_unit * count1
    cost2 = price_per_unit * count2
    return join_explanation_lines(
        f"Сначала находим общее количество наборов: {count1} + {count2} = {total_count}",
        f"Потом находим цену одного набора: {total_cost} : {total_count} = {price_per_unit}",
        f"Теперь находим стоимость первых наборов: {price_per_unit} × {count1} = {cost1}",
        f"И стоимость вторых наборов: {price_per_unit} × {count2} = {cost2}",
        f"Ответ: за первые наборы заплатили {cost1}, за вторые — {cost2}",
        "Совет: в задачах на пропорциональное деление сначала находят общее количество частей",
    )


def try_local_difference_unknown_word_problem(raw_text: str) -> Optional[str]:
    """Задачи на нахождение неизвестного по двум разностям (2099-2128)."""
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None

    # Шаблон: Собрали A кг моркови и B кг картофеля. Картофеля получилось на C мешков больше.
    # Или: В первом куске A м, во втором B м, второй дороже на C руб.
    match = re.search(r"(\d+)\s+(?:кг|м|л|шт)[а-я]*\s+(?:и|,)\s+(\d+)\s+(?:кг|м|л|шт)[а-я]*", lower)
    if not match:
        return None
    val1 = int(match.group(1))
    val2 = int(match.group(2))
    diff_count = None
    # Ищем фразу "на X больше/меньше/дороже"
    diff_match = re.search(r"на\s+(\d+)\s+(?:мешков|коробок|ящиков|руб|коп|больше|меньше|дороже)", lower)
    if diff_match:
        diff_count = int(diff_match.group(1))
    if diff_count is None:
        return None
    # Определяем, что есть что: большее значение обычно картофель, но не всегда
    # Предположим, что val1 и val2 - количества, diff_count - разница в мешках/единицах
    # Тогда находим разность количеств: разность_значений = abs(val1 - val2)
    diff_value = abs(val1 - val2)
    if diff_value % diff_count != 0:
        return None
    per_unit = diff_value // diff_count
    # Теперь нужно понять, сколько единиц каждого вида
    # Обычно в задаче спрашивают "сколько было мешков картофеля и моркови"
    # val1 и val2 - общие веса, diff_count - разница в мешках
    # Тогда количество мешков = вес / per_unit
    count1 = val1 // per_unit
    count2 = val2 // per_unit
    # Но нужно угадать, где что
    if val1 > val2:
        bigger_count = count1
        smaller_count = count2
    else:
        bigger_count = count2
        smaller_count = count1

    # Формируем ответ
    if "картофел" in lower and "морков" in lower:
        name1 = "картофеля" if val1 > val2 else "моркови"
        name2 = "моркови" if val1 > val2 else "картофеля"
        return join_explanation_lines(
            f"Сначала находим, на сколько больше собрали {name1}: {max(val1, val2)} - {min(val1, val2)} = {diff_value}",
            f"Эта разница поместилась в {diff_count} мешков, значит в одном мешке {diff_value} : {diff_count} = {per_unit} кг",
            f"Теперь находим мешки {name1}: {max(val1, val2)} : {per_unit} = {max(count1, count2)}",
            f"И мешки {name2}: {min(val1, val2)} : {per_unit} = {min(count1, count2)}",
            f"Ответ: {name1} — {max(count1, count2)} мешков, {name2} — {min(count1, count2)} мешков",
            "Совет: в задачах на нахождение неизвестного по двум разностям сначала находят разность величин",
        )
    elif "кусок" in lower and "ткани" in lower or "стоит" in lower:
        return join_explanation_lines(
            f"Находим разность длин: {max(val1, val2)} - {min(val1, val2)} = {diff_value} м",
            f"Эта разница стоит {diff_count} руб., значит 1 м стоит {diff_count} : {diff_value} = {per_unit} руб.",
            f"Первый кусок: {val1} × {per_unit} = {val1 * per_unit} руб.",
            f"Второй кусок: {val2} × {per_unit} = {val2 * per_unit} руб.",
            f"Ответ: первый кусок стоит {val1 * per_unit} руб., второй — {val2 * per_unit} руб.",
            "Совет: сначала найди цену одного метра, разделив разницу в стоимости на разницу в длине",
        )
    # Общий случай
    return join_explanation_lines(
        f"Разность величин: {max(val1, val2)} - {min(val1, val2)} = {diff_value}",
        f"Эта разность соответствует {diff_count} единицам, значит на одну единицу приходится {diff_value // diff_count}",
        f"Первое количество: {val1} : {per_unit} = {count1}",
        f"Второе количество: {val2} : {per_unit} = {count2}",
        f"Ответ: {count1} и {count2}",
        "Совет: найди значение одной единицы через разность",
    )


def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    unit = geometry_unit(lower)
    nums = extract_ordered_numbers(lower)
    question_parts = [part.strip() for part in re.split(r"[?.!]", lower) if part.strip()]
    question = question_parts[-1] if question_parts else lower

    asks_perimeter = "периметр" in question or "найти периметр" in lower or "узнайте периметр" in lower
    asks_area = "площад" in question or "найти площадь" in lower or "узнайте площадь" in lower
    asks_side = any(fragment in question for fragment in ("найти сторону", "найти длину стороны", "какова сторона"))
    asks_width = any(fragment in question for fragment in ("найти ширину", "какова ширина"))
    asks_length = any(fragment in question for fragment in ("найти длину", "какова длина")) and not asks_width

    if "прямоугольник" in lower and asks_area and asks_perimeter and "со сторонами" in lower and len(nums) >= 2:
        length, width = nums[0], nums[1]
        area = length * width
        perimeter = 2 * (length + width)
        return join_explanation_lines(
            f"Сначала находим площадь: {length} × {width} = {area}",
            f"Потом находим периметр: ({length} + {width}) × 2 = {perimeter}",
            f"Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}",
            "Совет: для прямоугольника отдельно считают площадь и периметр",
        )

    perimeter_val = extract_keyword_number(lower, "периметр")
    area_val = extract_keyword_number(lower, "площад")
    length_val = extract_keyword_number(lower, "длина")
    width_val = extract_keyword_number(lower, "ширина")

    square_side_match = re.search(r"сторона квадрата[^\d]{0,80}(\d+)|квадрат[^.?!]*сторон[аы][^\d]{0,80}(\d+)", lower)
    square_side_val = int(next(group for group in square_side_match.groups() if group)) if square_side_match else None
    triangle_side_match = re.search(r"равносторонн[а-я ]*треугольник[а-я ]*сторон[аы][^\d]{0,80}(\d+)", lower)
    triangle_side_val = int(triangle_side_match.group(1)) if triangle_side_match else None

    explicit = re.search(r"периметр прямоугольника равен\s+(\d+).*?длина прямоугольника равна\s+(\d+).*?(?:найти|найдите) площадь", lower)
    if explicit:
        perimeter = int(explicit.group(1))
        length = int(explicit.group(2))
        if perimeter % 2 == 0:
            half = perimeter // 2
            width = half - length
            if width >= 0:
                area = length * width
                return join_explanation_lines(
                    "Сначала находим сумму длины и ширины",
                    f"Половина периметра равна сумме длины и ширины: {perimeter} : 2 = {half}",
                    f"Потом находим ширину: {half} - {length} = {width}",
                    f"Теперь находим площадь: {length} × {width} = {area}",
                    f"Ответ: {with_unit(area, unit, square=True)}",
                    "Совет: если известен периметр прямоугольника, сначала находят его половину",
                )

    explicit = re.search(r"площадь прямоугольника равна\s+(\d+).*?длина[^\d]{0,80}(\d+).*?(?:найти|найдите) периметр", lower)
    if explicit:
        area = int(explicit.group(1))
        length = int(explicit.group(2))
        if length != 0 and area % length == 0:
            width = area // length
            perimeter = 2 * (length + width)
            return join_explanation_lines(
                "Сначала находим ширину прямоугольника",
                f"Ширина равна площади, делённой на длину: {area} : {length} = {width}",
                f"Потом находим периметр: ({length} + {width}) × 2 = {perimeter}",
                f"Ответ: {with_unit(perimeter, unit)}",
                "Совет: если известны площадь и длина, сначала находят ширину",
            )

    explicit = re.search(r"сторона равностороннего треугольника равна\s+(\d+).*?стороны квадрата.*?периметр которого равен периметру треугольника", lower)
    if explicit:
        tri_side = int(explicit.group(1))
        tri_perimeter = tri_side * 3
        if tri_perimeter % 4 == 0:
            square_side = tri_perimeter // 4
            return join_explanation_lines(
                "Сначала находим периметр равностороннего треугольника",
                f"У треугольника три равные стороны: {tri_side} × 3 = {tri_perimeter}",
                f"Теперь находим сторону квадрата: {tri_perimeter} : 4 = {square_side}",
                f"Ответ: {with_unit(square_side, unit)}",
                "Совет: у равностороннего треугольника три равные стороны, а у квадрата четыре",
            )

    if "квадрат" in lower and asks_area and asks_perimeter and (square_side_val is not None or nums):
        side = square_side_val if square_side_val is not None else nums[0]
        area = side * side
        perimeter = side * 4
        return join_explanation_lines(
            f"Сначала находим площадь квадрата: {side} × {side} = {area}",
            f"Потом находим периметр квадрата: {side} × 4 = {perimeter}",
            f"Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}",
            "Совет: у квадрата площадь и периметр считают по стороне",
        )

    if "равносторон" in lower and "треугольник" in lower and "квадрат" in lower and "равен периметру" in lower and triangle_side_val is not None and asks_side:
        triangle_perimeter = triangle_side_val * 3
        if triangle_perimeter % 4 != 0:
            return None
        square_side = triangle_perimeter // 4
        return join_explanation_lines(
            "Сначала находим периметр равностороннего треугольника",
            f"У треугольника три равные стороны: {triangle_side_val} × 3 = {triangle_perimeter}",
            f"Теперь находим сторону квадрата: {triangle_perimeter} : 4 = {square_side}",
            f"Ответ: {with_unit(square_side, unit)}",
            "Совет: у равностороннего треугольника три равные стороны, а у квадрата четыре",
        )

    if "прямоугольник" in lower and area_val is not None and length_val is not None and asks_perimeter:
        if length_val == 0 or area_val % length_val != 0:
            return None
        width = area_val // length_val
        perimeter = 2 * (length_val + width)
        return join_explanation_lines(
            "Сначала находим ширину прямоугольника",
            f"Ширина равна площади, делённой на длину: {area_val} : {length_val} = {width}",
            f"Потом находим периметр: ({length_val} + {width}) × 2 = {perimeter}",
            f"Ответ: {with_unit(perimeter, unit)}",
            "Совет: если известны площадь и длина, сначала находят ширину",
        )

    if "прямоугольник" in lower and perimeter_val is not None and length_val is not None and asks_area:
        if perimeter_val % 2 != 0:
            return None
        half = perimeter_val // 2
        width = half - length_val
        if width < 0:
            return None
        area = length_val * width
        return join_explanation_lines(
            "Сначала находим сумму длины и ширины",
            f"Половина периметра равна сумме длины и ширины: {perimeter_val} : 2 = {half}",
            f"Потом находим ширину: {half} - {length_val} = {width}",
            f"Теперь находим площадь: {length_val} × {width} = {area}",
            f"Ответ: {with_unit(area, unit, square=True)}",
            "Совет: если известен периметр прямоугольника, сначала находят его половину",
        )

    if "квадрат" in lower and perimeter_val is not None and asks_side:
        if perimeter_val % 4 != 0:
            return None
        side = perimeter_val // 4
        return join_explanation_lines(
            "У квадрата все стороны равны",
            f"Чтобы найти сторону, делим периметр на 4: {perimeter_val} : 4 = {side}",
            f"Ответ: {with_unit(side, unit)}",
            "Совет: сторона квадрата равна периметру, делённому на 4",
        )

    if "квадрат" in lower and area_val is not None and asks_side:
        side = int(math.isqrt(area_val))
        if side * side != area_val:
            return None
        return join_explanation_lines(
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Нужно найти число, которое в квадрате даёт {area_val}",
            f"Это {side}, потому что {side} × {side} = {area_val}",
            f"Ответ: {with_unit(side, unit)}",
            "Совет: если знаешь площадь квадрата, ищи такую сторону, которая в квадрате даёт эту площадь",
        )

    if "прямоугольник" in lower and area_val is not None and length_val is not None and asks_width:
        if length_val == 0 or area_val % length_val != 0:
            return None
        width = area_val // length_val
        return join_explanation_lines(
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти ширину, делим площадь на длину: {area_val} : {length_val} = {width}",
            f"Ответ: {with_unit(width, unit)}",
            "Совет: ширину находим делением площади на длину",
        )

    if "прямоугольник" in lower and area_val is not None and width_val is not None and asks_length:
        if width_val == 0 or area_val % width_val != 0:
            return None
        length = area_val // width_val
        return join_explanation_lines(
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Чтобы найти длину, делим площадь на ширину: {area_val} : {width_val} = {length}",
            f"Ответ: {with_unit(length, unit)}",
            "Совет: длину находим делением площади на ширину",
        )

    if "квадрат" in lower and square_side_val is not None and asks_perimeter:
        result = square_side_val * 4
        return join_explanation_lines(
            "Периметр квадрата — это сумма четырёх равных сторон",
            f"Считаем: {square_side_val} × 4 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: у квадрата все четыре стороны равны",
        )

    if "прямоугольник" in lower and length_val is not None and width_val is not None and asks_perimeter:
        result = 2 * (length_val + width_val)
        return join_explanation_lines(
            "Периметр прямоугольника равен сумме длины и ширины, умноженной на 2",
            f"Сначала складываем длину и ширину: {length_val} + {width_val} = {length_val + width_val}",
            f"Потом умножаем на 2: ({length_val} + {width_val}) × 2 = {result}",
            f"Ответ: {with_unit(result, unit)}",
            "Совет: для периметра прямоугольника сначала сложи длину и ширину",
        )

    if "квадрат" in lower and square_side_val is not None and asks_area:
        result = square_side_val * square_side_val
        return join_explanation_lines(
            "Площадь квадрата равна стороне, умноженной на сторону",
            f"Считаем: {square_side_val} × {square_side_val} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: площадь квадрата — это сторона на сторону",
        )

    if "прямоугольник" in lower and length_val is not None and width_val is not None and asks_area:
        result = length_val * width_val
        return join_explanation_lines(
            "Площадь прямоугольника равна длине, умноженной на ширину",
            f"Считаем: {length_val} × {width_val} = {result}",
            f"Ответ: {with_unit(result, unit, square=True)}",
            "Совет: для площади прямоугольника умножай длину на ширину",
        )
    return None


def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if not re.search(r"[а-я]", lower):
        return None
    numbers = extract_ordered_numbers(lower)
    if len(numbers) < 2:
        return None

    asks_total = asks_total_like(lower)
    asks_current = bool(re.search(r"сколько[^.?!]*\b(стало|теперь|осталось)\b", lower))
    asks_plain_quantity = "сколько" in lower and not asks_total and not asks_current and "на сколько" not in lower and "во сколько" not in lower
    asks_initial = "сколько было" in lower or "сколько было сначала" in lower or "сначала" in lower
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    multiple = has_multiple_questions(text)
    pairs_after_po = extract_pairs_after_po(lower)
    has_indirect_hint = bool(re.search(r"\b(?:это|что|он|она)\b[^.?!]{0,30}(?:на\s+\d+|в\s+\d+\s+раз(?:а)?)", lower))

    if len(pairs_after_po) == 2 and "сколько" in lower and ("покупк" in lower or "всего" in lower or "заплат" in lower):
        (count1, value1), (count2, value2) = pairs_after_po[0], pairs_after_po[1]
        return explain_sum_of_two_products_word_problem(count1, value1, count2, value2)

    if len(numbers) == 3 and contains_any_fragment(lower, ("таких же", "такие же")):
        unit = explain_bring_to_unit_total_word_problem(numbers[0], numbers[1], numbers[2])
        if unit:
            return unit

    if len(numbers) == 3 and asks_plain_quantity and ("несколько" in lower or "осталь" in lower):
        third = explain_find_third_addend_word_problem(numbers[0], numbers[1], numbers[2])
        if third:
            return third

    if len(numbers) == 3 and asks_initial and ("остал" in lower or "осталось" in lower) and contains_any_fragment(lower, WORD_LOSS_HINTS):
        initial = explain_initial_from_taken_and_left_word_problem(numbers[0], numbers[1], numbers[2])
        if initial:
            return initial

    if len(numbers) == 2 and len(relation_pairs) == 1 and "столько, сколько" in lower:
        delta, mode = relation_pairs[0]
        if delta == numbers[1]:
            second = apply_more_less(numbers[0], delta, mode)
            if second is not None:
                third = numbers[0] + second
                if multiple and asks_total:
                    total = numbers[0] + second + third
                    return join_explanation_lines(
                        f"Сначала находим маки: {numbers[0]} {'+' if mode == 'больше' else '-'} {delta} = {second}",
                        f"Потом находим астры: {numbers[0]} + {second} = {third}",
                        f"Теперь находим все цветы: {numbers[0]} + {second} + {third} = {total}",
                        f"Ответ: астр — {third}; всего — {total}",
                        "Совет: если сказано «столько, сколько вместе», сначала найди сумму этих частей",
                    )
                return join_explanation_lines(
                    f"Сначала находим второе количество: {numbers[0]} {'+' if mode == 'больше' else '-'} {delta} = {second}",
                    f"Потом находим третье количество: {numbers[0]} + {second} = {third}",
                    f"Ответ: {third}",
                    "Совет: если сказано «столько, сколько вместе», сначала найди сумму этих частей",
                )

    if len(numbers) == 3 and asks_total and len(relation_pairs) == 2:
        (delta1, mode1), (delta2, mode2) = relation_pairs
        if delta1 == numbers[1] and delta2 == numbers[2]:
            chain = explain_relation_chain_total_word_problem(numbers[0], delta1, mode1, delta2, mode2)
            if chain:
                return chain

    if len(numbers) == 3 and len(scale_pairs) == 2 and asks_total:
        (factor1, mode1), (factor2, mode2) = scale_pairs
        if factor1 == numbers[1] and factor2 == numbers[2]:
            chain = explain_relation_chain_times_total_word_problem(numbers[0], factor1, mode1, factor2, mode2)
            if chain:
                return chain

    if len(numbers) == 2 and len(relation_pairs) == 1 and not has_indirect_hint:
        delta, mode = relation_pairs[0]
        if delta == numbers[1]:
            if multiple and asks_total:
                rel = explain_related_quantity_and_total_word_problem(numbers[0], delta, mode)
                if rel:
                    return rel
            if asks_total:
                rel = explain_related_total_word_problem(numbers[0], delta, mode)
                if rel:
                    return rel
            if asks_plain_quantity:
                rel = explain_related_quantity_word_problem(numbers[0], delta, mode)
                if rel:
                    return rel

    if len(numbers) == 2 and len(scale_pairs) == 1 and not has_indirect_hint:
        factor, mode = scale_pairs[0]
        if factor == numbers[1]:
            if multiple and asks_total:
                rel = explain_related_quantity_and_total_times_word_problem(numbers[0], factor, mode)
                if rel:
                    return rel
            if asks_total:
                rel = explain_related_total_times_word_problem(numbers[0], factor, mode)
                if rel:
                    return rel
            if asks_plain_quantity:
                rel = explain_related_quantity_times_word_problem(numbers[0], factor, mode)
                if rel:
                    return rel

    if len(numbers) == 3 and (asks_total or asks_current):
        fragments = re.split(r"\d+", lower)
        if len(fragments) >= 4:
            first_following, second_leading = split_between_change_fragment(fragments[2])
            first_mode = classify_change_fragment(fragments[1]) or classify_change_fragment(first_following)
            second_mode = classify_change_fragment(second_leading) or classify_change_fragment(fragments[3])
            if first_mode and second_mode:
                mid = numbers[0] + numbers[1] if first_mode == "gain" else numbers[0] - numbers[1]
                end = mid + numbers[2] if second_mode == "gain" else mid - numbers[2]
                return join_explanation_lines(
                    f"Сначала меняем число первый раз: {numbers[0]} {'+' if first_mode == 'gain' else '-'} {numbers[1]} = {mid}",
                    f"Потом меняем число второй раз: {mid} {'+' if second_mode == 'gain' else '-'} {numbers[2]} = {end}",
                    f"Ответ: {end}",
                    "Совет: если в задаче два изменения, считай их по порядку",
                )

    if len(numbers) == 3 and asks_total and ("по" in lower) and ("еще" in lower or "ещё" in lower or "отдельно" in lower):
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
    return None


def try_local_indirect_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None

    asks_total = asks_total_like(lower)
    multiple = has_multiple_questions(text)
    base, delta_or_factor = nums

    match = re.search(r"(?:это|что|он|она)\s+на\s+(\d+)(?:\s+[а-я]+){0,4}\s+(старше|младше|больше|меньше)", lower)
    if match and int(match.group(1)) == delta_or_factor:
        relation = match.group(2)
        if asks_total and multiple:
            return explain_indirect_plus_minus_total_problem(base, delta_or_factor, relation)
        return explain_indirect_plus_minus_problem(base, delta_or_factor, relation)

    match = re.search(r"(?:это|что)\s+(старше|младше|больше|меньше).*?на\s+(\d+)", lower)
    if match and int(match.group(2)) == delta_or_factor:
        relation = match.group(1)
        if asks_total and multiple:
            return explain_indirect_plus_minus_total_problem(base, delta_or_factor, relation)
        return explain_indirect_plus_minus_problem(base, delta_or_factor, relation)

    match = re.search(r"(?:это|что|он|она)\s+в\s+(\d+)\s+раз(?:а)?\s+(больше|меньше)", lower)
    if match and int(match.group(1)) == delta_or_factor:
        relation = match.group(2)
        if asks_total and multiple:
            return explain_indirect_times_total_problem(base, delta_or_factor, relation)
        return explain_indirect_times_problem(base, delta_or_factor, relation)
    return None


def try_local_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
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
    asks_total = asks_total_like(lower)
    asks_each = "кажд" in lower or "поровну" in lower
    asks_added = contains_any_fragment(lower, ("сколько добав", "сколько подар", "сколько куп", "сколько прин", "сколько полож"))
    asks_removed = contains_any_fragment(lower, ("сколько отдал", "сколько съел", "сколько убрал", "сколько забрал", "сколько потрат", "сколько продал", "сколько потер"))
    asks_groups = contains_any_fragment(lower, ("сколько короб", "сколько корзин", "сколько пакет", "сколько ряд", "сколько групп", "сколько ящик", "сколько сет"))
    asks_remainder = "остат" in lower or "сколько остан" in lower or "полных" in lower
    needs_extra_group = contains_any_fragment(lower, ("нужно", "нужны", "понадоб", "потребует"))
    has_gain = contains_any_fragment(lower, WORD_GAIN_HINTS)
    has_loss = contains_any_fragment(lower, WORD_LOSS_HINTS)
    has_grouping = contains_any_fragment(lower, GROUPING_VERBS)
    scale_pairs = extract_scale_pairs(lower)

    if "осталь" in lower and asks_compare:
        total = max(first, second)
        part = min(first, second)
        comparison = explain_compare_from_total_and_part_word_problem(total, part)
        if comparison:
            return comparison

    if "осталь" in lower and "сколько" in lower:
        total = max(first, second)
        part = min(first, second)
        other = explain_other_from_total_and_part_word_problem(total, part)
        if other:
            return other

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

    if asks_each:
        bigger = max(first, second)
        smaller = min(first, second)
        share = explain_sharing_word_problem(bigger, smaller)
        if share:
            return share

    if scale_pairs and len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        if factor == second and "во сколько" not in lower and "это" not in lower and " что " not in f" {lower} " and " он " not in f" {lower} " and " она " not in f" {lower} ":
            if "по" not in lower and not asks_total and "сколько" in lower:
                return explain_related_quantity_times_word_problem(first, factor, mode)

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

    if contains_any_fragment(lower, ("нашел", "нашёл", "всего")) and "сколько" in lower:
        bigger = max(first, second)
        smaller = min(first, second)
        if bigger - smaller >= 0:
            return join_explanation_lines(
                "Нужно найти неизвестное слагаемое",
                f"Из суммы вычитаем известное слагаемое: {bigger} - {smaller} = {bigger - smaller}",
                f"Ответ: {bigger - smaller}",
                "Совет: неизвестное слагаемое находим вычитанием",
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
        return {"error": f"DeepSeek API error {response.status_code}", "details": response.text[:1500]}
    try:
        result = response.json()
    except Exception:
        return {"error": "DeepSeek вернул не JSON", "details": response.text[:1500]}
    if "choices" not in result or not result["choices"]:
        return {"error": "DeepSeek вернул неожиданный формат ответа", "details": str(result)[:1500]}
    message = result["choices"][0].get("message", {})
    answer = (message.get("content") or "").strip()
    if not answer:
        return {"error": "DeepSeek вернул пустой ответ", "details": str(result)[:1500]}
    return {"result": answer}


@app.options("/")
async def options():
    return {"message": "OK"}


@app.get("/")
def read_root():
    return {"message": "Proxy is running. Use POST request with 'action' and payload."}


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_fraction_word_problem_explanation(user_text)
        or try_local_motion_word_problem_explanation(user_text)
        or try_local_price_word_problem_explanation(user_text)
        or try_local_unit_rate_word_problem_explanation(user_text)
        or try_local_proportional_division_word_problem(user_text)
        or try_local_difference_unknown_word_problem(user_text)   # новый объяснитель
        or try_local_indirect_word_problem_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )
    if local_explanation:
        return {"result": shape_explanation(local_explanation, kind), "source": "local", "validated": True}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1000,
        "temperature": 0.05,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    shaped = shape_explanation(llm_result["result"], kind)
    return {"result": shaped, "source": "llm", "validated": False}


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

# --- PATCH: enhanced primary school methods ---

SYSTEM_PROMPT = """
Ты — спокойный, очень понятный и точный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Каждая строка — одна законченная полезная мысль.

Формат ответа:
Для текстовой задачи сначала дай 1–2 строки:
"Что известно: ..."
"Что нужно найти: ..."
Потом решай по действиям, лучше нумерованными шагами: 1), 2), 3)...
Не пропускай промежуточные вычисления.
Если это уравнение, после решения обязательно дай строку "Проверка: ...".
Потом строка "Ответ: ...".
Последняя строка "Совет: ...".

Общие правила:
Не называй готовый ответ в первой строке.
Не меняй числа из условия и не добавляй свои данные.
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку в одной строке "Ответ: ...; ...".
Совет должен быть коротким, школьным и полезным.

Как объяснять:
Для текстовой задачи сначала выдели условие и вопрос.
Если нельзя сразу ответить на главный вопрос, скажи, что нужно узнать сначала.
Решай задачу по действиям.
После каждого действия пиши, что именно нашли.
Каждое вычисление записывай полностью.

Используй школьные правила и методики:
Если задача в косвенной форме, сначала переведи её в прямую:
если одно число на несколько единиц больше, то другое на столько же меньше;
если одно число на несколько единиц меньше, то другое на столько же больше;
если одно число в несколько раз больше, то другое во столько же раз меньше;
если одно число в несколько раз меньше, то другое во столько же раз больше.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При движении навстречу сначала найди скорость сближения.
При движении в противоположных направлениях сначала найди скорость удаления.
Если это выражение, сначала назови порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это дроби, сначала смотри на знаменатели.
Если это геометрия, сначала назови формулу, потом подставь числа.
Если это именованные величины, сначала переведи их в одинаковые единицы.

Используй школьные приёмы:
сложение через десяток — разложи число так, чтобы сначала получить 10;
вычитание через десяток — вычитай по частям через 10;
двузначные числа раскладывай на десятки и единицы;
если числа большие, объясняй по разрядам;
для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

BODY_LIMITS = {
    "expression": 12,
    "equation": 8,
    "fraction": 10,
    "geometry": 12,
    "word": 16,
    "other": 10,
}

SMALL_NUMBER_WORDS = {
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
}
_NUMBER_WORD_PATTERN = "|".join(sorted((re.escape(word) for word in SMALL_NUMBER_WORDS), key=len, reverse=True))

_COMMON_FRACTION_PATTERNS = [
    (re.compile(r"\bполовин(?:а|у|ы|е|ой)\b", re.IGNORECASE), "1/2"),
    (re.compile(r"\bтреть\b|\bтретью\s+часть\b|\bтретьей\s+части\b", re.IGNORECASE), "1/3"),
    (re.compile(r"\bчетверть\b|\bчетвертую\s+часть\b|\bчетвертой\s+части\b", re.IGNORECASE), "1/4"),
    (re.compile(r"\bпятую\s+часть\b|\bпятой\s+части\b", re.IGNORECASE), "1/5"),
    (re.compile(r"\bшестую\s+часть\b|\bшестой\s+части\b", re.IGNORECASE), "1/6"),
    (re.compile(r"\bседьмую\s+часть\b|\bседьмой\s+части\b", re.IGNORECASE), "1/7"),
    (re.compile(r"\bвосьмую\s+часть\b|\bвосьмой\s+части\b", re.IGNORECASE), "1/8"),
    (re.compile(r"\bдевятую\s+часть\b|\bдевятой\s+части\b", re.IGNORECASE), "1/9"),
    (re.compile(r"\bдесятую\s+часть\b|\bдесятой\s+части\b", re.IGNORECASE), "1/10"),
]


def parse_number_token(token: str) -> Optional[int]:
    value = str(token or "").strip().lower().replace("ё", "е")
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return SMALL_NUMBER_WORDS.get(value)



def extract_number_values_before_units(text: str, unit_pattern: str) -> List[int]:
    values: List[int] = []
    for match in re.finditer(fr"(\d+|{_NUMBER_WORD_PATTERN})\s*(?:{unit_pattern})\b", str(text or "").lower()):
        value = parse_number_token(match.group(1))
        if value is not None:
            values.append(value)
    return values



def replace_common_fraction_words(text: str) -> str:
    cleaned = str(text or "")
    for pattern, replacement in _COMMON_FRACTION_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned



def extract_all_fraction_pairs(text: str) -> List[Tuple[int, int]]:
    return [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*/\s*(\d+)", str(text or ""))]



def extract_non_fraction_numbers(text: str) -> List[int]:
    base = re.sub(r"\d+\s*/\s*\d+", " ", str(text or ""))
    return extract_ordered_numbers(base)



def extract_condition_and_question(raw_text: str) -> Tuple[str, str]:
    cleaned = normalize_word_problem_text(raw_text)
    parts = [part.strip() for part in re.split(r"(?<=[.?!])\s+", cleaned) if part.strip()]
    condition_parts = [part.rstrip(".?!") for part in parts if "?" not in part]
    question_parts = [part.rstrip(".?!") for part in parts if "?" in part]
    condition = " ".join(condition_parts).strip()
    question = " ".join(question_parts).strip()
    if len(condition) > 240:
        condition = condition[:237].rstrip() + "..."
    if len(question) > 180:
        question = question[:177].rstrip() + "..."
    return condition, question



def add_task_context_lines(text: str, raw_text: str, kind: str) -> str:
    if kind not in {"word", "geometry"} and not (kind == "fraction" and re.search(r"[А-Яа-я]", str(raw_text or ""))):
        return text
    lines = [line.strip() for line in str(text or "").split("\n") if line.strip()]
    lowered = [line.lower() for line in lines]
    if any(line.startswith("что известно:") or line.startswith("известно:") for line in lowered):
        return text
    condition, question = extract_condition_and_question(raw_text)
    prefix: List[str] = []
    if condition:
        prefix.append(f"Что известно: {condition}")
    if question:
        prefix.append(f"Что нужно найти: {question}")
    if not prefix:
        return text
    return join_explanation_lines(*prefix, *lines)



def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value * denominator % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator if remaining_numerator != 0 else None
    if one_part is None:
        return None
    whole = remaining_value * denominator // remaining_numerator
    return join_explanation_lines(
        f"Сначала находим, какая часть денег осталась: {denominator}/{denominator} - {spent_numerator}/{denominator} = {remaining_numerator}/{denominator}",
        f"Теперь находим одну долю: {remaining_value} : {remaining_numerator} = {one_part}",
        f"Потом находим всё число: {one_part} × {denominator} = {whole}",
        f"Ответ: {whole}",
        "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
    )



def explain_fraction_part_and_remaining(total: int, numerator: int, denominator: int, remaining_label: str = "осталось") -> Optional[str]:
    if denominator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    part = one_part * numerator
    remaining = total - part
    return join_explanation_lines(
        f"Сначала находим одну долю: {total} : {denominator} = {one_part}",
        f"Потом находим {numerator}/{denominator} числа: {one_part} × {numerator} = {part}",
        f"Теперь находим, сколько {remaining_label}: {total} - {part} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: чтобы найти остаток после дробной части, сначала найди эту часть",
    )



def explain_two_fraction_parts_remaining(total: int, first_fraction: Tuple[int, int], second_fraction: Tuple[int, int]) -> Optional[str]:
    n1, d1 = first_fraction
    n2, d2 = second_fraction
    common = math.lcm(d1, d2)
    if common == 0 or total % common != 0:
        return None
    first_part = total * n1 // d1
    second_part = total * n2 // d2
    used = first_part + second_part
    remaining = total - used
    return join_explanation_lines(
        f"Сначала находим первую часть: {total} : {d1} × {n1} = {first_part}",
        f"Потом находим вторую часть: {total} : {d2} × {n2} = {second_part}",
        f"Теперь находим, сколько использовали всего: {first_part} + {second_part} = {used}",
        f"Находим остаток: {total} - {used} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если от одного и того же целого берут две части, каждую часть находят отдельно",
    )



def explain_second_part_after_fraction(total: int, numerator: int, denominator: int) -> Optional[str]:
    if denominator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    first_part = one_part * numerator
    second_part = total - first_part
    return join_explanation_lines(
        f"Сначала находим одну долю: {total} : {denominator} = {one_part}",
        f"Потом находим первую часть пути: {one_part} × {numerator} = {first_part}",
        f"Теперь находим вторую часть: {total} - {first_part} = {second_part}",
        f"Ответ: {second_part}",
        "Совет: если известна часть всего пути, сначала найди эту часть, потом остаток",
    )



def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        "Сначала вспоминаем правило: цена = стоимость : количество",
        f"Находим цену одной штуки: {total_cost} : {count} = {price}",
        f"Ответ: {price}",
        "Совет: цену одного предмета находят делением общей стоимости на количество",
    )



def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        "Сначала вспоминаем правило: стоимость = цена × количество",
        f"Находим стоимость покупки: {price} × {count} = {total}",
        f"Ответ: {total}",
        "Совет: стоимость находят умножением цены на количество",
    )



def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"Сначала находим стоимость известных цветов: {known_count} × {known_price} = {known_total}",
        f"Потом находим, сколько заплатили за остальные цветы: {total_cost} - {known_total} = {other_total}",
        f"Теперь находим цену одного цветка: {other_total} : {unknown_count} = {unit_price}",
        f"Ответ: {unit_price}",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть",
    )



def explain_sum_then_divide_word_problem(first: int, second: int, divisor: int) -> Optional[str]:
    if divisor == 0:
        return None
    total = first + second
    quotient, remainder = divmod(total, divisor)
    if remainder == 0:
        return join_explanation_lines(
            f"Сначала находим всё вместе: {first} + {second} = {total}",
            f"Потом делим общее количество на размер одной группы: {total} : {divisor} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: если предметы сначала объединяют, а потом раскладывают поровну, сначала найди общую сумму",
        )
    return join_explanation_lines(
        f"Сначала находим всё вместе: {first} + {second} = {total}",
        f"Потом делим: {total} : {divisor} = {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: сначала найди общую сумму, потом дели на размер одной группы",
    )



def explain_cages_with_two_parts(first: int, second: int, total: int) -> Optional[str]:
    in_one = first + second
    if in_one == 0 or total % in_one != 0:
        return None
    cages = total // in_one
    return join_explanation_lines(
        f"Сначала находим, сколько попугаев в одной клетке: {first} + {second} = {in_one}",
        f"Потом находим число клеток: {total} : {in_one} = {cages}",
        f"Ответ: {cages}",
        "Совет: если в каждой группе есть два вида предметов, сначала найди, сколько всего в одной группе",
    )



def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"Сначала находим общее число равных частей: {first_count} + {second_count} = {group_total}",
        f"Потом находим одну часть: {total} : {group_total} = {one_unit}",
        f"Теперь находим {first_label}: {one_unit} × {first_count} = {first_total}",
        f"И находим {second_label}: {one_unit} × {second_count} = {second_total}",
        f"Ответ: {first_total}; {second_total}",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )



def explain_piece_lengths_from_total_and_costs(total_length: int, first_cost: int, second_cost: int) -> Optional[str]:
    if total_length == 0:
        return None
    total_cost = first_cost + second_cost
    if total_cost % total_length != 0:
        return None
    unit_price = total_cost // total_length
    if unit_price == 0 or first_cost % unit_price != 0 or second_cost % unit_price != 0:
        return None
    first_length = first_cost // unit_price
    second_length = second_cost // unit_price
    return join_explanation_lines(
        f"Сначала находим общую стоимость: {first_cost} + {second_cost} = {total_cost}",
        f"Потом находим цену одного метра: {total_cost} : {total_length} = {unit_price}",
        f"Теперь находим длину первого куска: {first_cost} : {unit_price} = {first_length}",
        f"И длину второго куска: {second_cost} : {unit_price} = {second_length}",
        f"Ответ: {first_length}; {second_length}",
        "Совет: если у одинакового товара одна и та же цена за единицу, сначала находят цену одной единицы",
    )



def explain_bag_counts_from_mass_difference(first_mass: int, second_mass: int, diff_bags: int, first_name: str = "первого", second_name: str = "второго") -> Optional[str]:
    diff_mass = abs(second_mass - first_mass)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    if per_bag == 0 or first_mass % per_bag != 0 or second_mass % per_bag != 0:
        return None
    first_count = first_mass // per_bag
    second_count = second_mass // per_bag
    return join_explanation_lines(
        f"Сначала находим разность масс: {max(first_mass, second_mass)} - {min(first_mass, second_mass)} = {diff_mass}",
        f"Эта разность приходится на {diff_bags} мешков, значит в одном мешке: {diff_mass} : {diff_bags} = {per_bag}",
        f"Теперь находим количество мешков {first_name} урожая: {first_mass} : {per_bag} = {first_count}",
        f"И количество мешков {second_name} урожая: {second_mass} : {per_bag} = {second_count}",
        f"Ответ: {first_count}; {second_count}",
        "Совет: в задачах по двум разностям сначала находят, чему соответствует одна равная часть",
    )



def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"Сначала находим, на сколько мешков отличаются участки: {max(first_bags, second_bags)} - {min(first_bags, second_bags)} = {diff_bags}",
        f"Этим {diff_bags} мешкам соответствуют {diff_mass} кг, значит в одном мешке: {diff_mass} : {diff_bags} = {per_bag}",
        f"Теперь находим массу первого участка: {first_bags} × {per_bag} = {first_mass}",
        f"И массу второго участка: {second_bags} × {per_bag} = {second_mass}",
        f"Ответ: {first_mass}; {second_mass}",
        "Совет: если известна разность по мешкам и по килограммам, сначала найди массу одного мешка",
    )



def explain_water_buckets_difference(big_bucket: int, small_bucket: int, diff_total: int) -> Optional[str]:
    step_diff = abs(big_bucket - small_bucket)
    if step_diff == 0 or diff_total % step_diff != 0:
        return None
    trips = diff_total // step_diff
    big_total = big_bucket * trips
    small_total = small_bucket * trips
    return join_explanation_lines(
        f"Сначала находим, на сколько литров за один раз больше приносили воды: {big_bucket} - {small_bucket} = {step_diff}",
        f"Потом находим число одинаковых ходок: {diff_total} : {step_diff} = {trips}",
        f"Теперь находим, сколько воды принёс первый: {big_bucket} × {trips} = {big_total}",
        f"И сколько воды принёс второй: {small_bucket} × {trips} = {small_total}",
        f"Ответ: {big_total}; {small_total}",
        "Совет: если число ходок одинаковое, сначала сравни, на сколько отличаются результаты за одну ходку",
    )



def explain_costs_from_length_difference(first_length: int, second_length: int, diff_cost: int) -> Optional[str]:
    diff_length = abs(second_length - first_length)
    if diff_length == 0 or diff_cost % diff_length != 0:
        return None
    price_per_meter = diff_cost // diff_length
    first_cost = first_length * price_per_meter
    second_cost = second_length * price_per_meter
    return join_explanation_lines(
        f"Сначала находим разность длин: {max(first_length, second_length)} - {min(first_length, second_length)} = {diff_length}",
        f"Потом находим цену одного метра: {diff_cost} : {diff_length} = {price_per_meter}",
        f"Теперь находим стоимость первого куска: {first_length} × {price_per_meter} = {first_cost}",
        f"И стоимость второго куска: {second_length} × {price_per_meter} = {second_cost}",
        f"Ответ: {first_cost}; {second_cost}",
        "Совет: если цена зависит от длины одинаково, сначала найди цену одной единицы длины",
    )



def explain_trip_time_for_same_distance(speed1: int, time1: int, speed2: int) -> Optional[str]:
    distance = speed1 * time1
    if speed2 == 0 or distance % speed2 != 0:
        return None
    time2 = distance // speed2
    return join_explanation_lines(
        f"Сначала находим расстояние между пунктами: {speed1} × {time1} = {distance}",
        f"Потом находим время для второго участника: {distance} : {speed2} = {time2}",
        f"Ответ: {time2}",
        "Совет: если путь один и тот же, сначала найди расстояние, потом дели его на новую скорость",
    )



def explain_second_day_motion_time(total_distance: int, first_speed: int, first_time: int, second_speed: int) -> Optional[str]:
    first_distance = first_speed * first_time
    second_distance = total_distance - first_distance
    if second_speed == 0 or second_distance < 0 or second_distance % second_speed != 0:
        return None
    second_time = second_distance // second_speed
    total_time = first_time + second_time
    return join_explanation_lines(
        f"Сначала находим путь в первый день: {first_speed} × {first_time} = {first_distance}",
        f"Потом находим путь во второй день: {total_distance} - {first_distance} = {second_distance}",
        f"Теперь находим время во второй день: {second_distance} : {second_speed} = {second_time}",
        f"И находим всё время: {first_time} + {second_time} = {total_time}",
        f"Ответ: во второй день — {second_time}; всего — {total_time}",
        "Совет: в составной задаче на движение сначала находят путь, потом время",
    )



def explain_remaining_part_speed(total_distance: int, first_speed: int, first_time: int, second_time: int) -> Optional[str]:
    first_distance = first_speed * first_time
    remaining_distance = total_distance - first_distance
    if second_time == 0 or remaining_distance < 0 or remaining_distance % second_time != 0:
        return None
    second_speed = remaining_distance // second_time
    return join_explanation_lines(
        f"Сначала находим первую часть пути: {first_speed} × {first_time} = {first_distance}",
        f"Потом находим оставшийся путь: {total_distance} - {first_distance} = {remaining_distance}",
        f"Теперь находим скорость на оставшейся части пути: {remaining_distance} : {second_time} = {second_speed}",
        f"Ответ: {second_speed}",
        "Совет: если известны оставшийся путь и время, скорость находят делением",
    )



def explain_return_trip_time_by_faster_speed(distance: int, speed: int, factor: int) -> Optional[str]:
    if speed == 0 or factor == 0 or distance % speed != 0:
        return None
    first_time = distance // speed
    faster_speed = speed * factor
    if faster_speed == 0 or distance % faster_speed != 0:
        return None
    return_time = distance // faster_speed
    return join_explanation_lines(
        f"Сначала находим время в одну сторону: {distance} : {speed} = {first_time}",
        f"Потом находим скорость на обратном пути: {speed} × {factor} = {faster_speed}",
        f"Теперь находим время на обратный путь: {distance} : {faster_speed} = {return_time}",
        f"Ответ: {return_time}",
        "Совет: если на обратном пути скорость увеличилась в несколько раз, сначала найди новую скорость",
    )



def try_local_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower()
    fracs = extract_all_fraction_pairs(lower)
    values = extract_non_fraction_numbers(lower)
    if not fracs:
        return None

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower):
        total = max(values) if values else None
        if total is not None:
            solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
            if solved:
                return solved

    if len(fracs) == 1:
        numerator, denominator = fracs[0]

        if ("израсход" in lower or "потрат" in lower) and "остал" in lower and values:
            remaining_value = max(values)
            solved = explain_whole_by_remaining_fraction(remaining_value, numerator, denominator)
            if solved:
                return solved

        if re.search(r"это\s+\d+\s*/\s*\d+\s+(?:всего\s+)?", lower) and values:
            part_value = max(values)
            return explain_number_by_fraction_word_problem(part_value, numerator, denominator)

        if ("во 2 день" in lower or "во второй день" in lower or "остал" in lower) and values:
            total = max(values)
            solved = explain_second_part_after_fraction(total, numerator, denominator)
            if solved:
                return solved

        if contains_any_fragment(lower, ("сколько потрат", "сколько выпил", "сколько израсход", "сколько взяли", "сколько состав", "сколько железа")) and values:
            total = max(values)
            return explain_fraction_of_number_word_problem(total, numerator, denominator, ask_remaining=False)

        if "остал" in lower and values:
            total = max(values)
            solved = explain_fraction_part_and_remaining(total, numerator, denominator)
            if solved:
                return solved

        if "сколько" in lower and values:
            total = max(values)
            if contains_any_fragment(lower, ("всего", "какое расстояние", "какова длина", "какое число")) and re.search(r"это\s+\d+\s*/\s*\d+", lower):
                return explain_number_by_fraction_word_problem(total, numerator, denominator)
            return explain_fraction_of_number_word_problem(total, numerator, denominator, ask_remaining=False)
    return None



def try_local_motion_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 1 and not re.search(_NUMBER_WORD_PATTERN, lower):
        return None

    distance_unit = "км" if "км" in lower else "м" if re.search(r"\bм\b", lower) else ""
    time_unit = "ч" if re.search(r"\bч\b|час", lower) else "мин" if "мин" in lower else ""
    speed_unit = "км/ч" if "км/ч" in lower else "м/с" if "м/с" in lower else ("м/мин" if "м/мин" in lower else ("км/ч" if distance_unit == "км" and time_unit == "ч" else ""))

    speed_values = [int(v) for v in re.findall(r"(\d+)\s*(?:км/ч|м/с|м/мин)", lower)] or [int(v) for v in re.findall(r"скорост[ьяию][^\d]{0,20}(\d+)", lower)]
    distance_values = [int(v) for v in re.findall(r"(\d+)\s*(?:км|м)(?!/)", lower)]
    time_values = extract_number_values_before_units(lower, r"ч|час(?:а|ов)?|мин(?:ут[аы]?)?")

    through_match = re.search(fr"через\s+(\d+|{_NUMBER_WORD_PATTERN})\s*(?:ч|час(?:а|ов)?|мин(?:ут[аы]?)?)", lower)
    through_value = parse_number_token(through_match.group(1)) if through_match else None
    speed_delta_match = re.search(r"на\s+(\d+)\s*км/ч\s+(больше|меньше)", lower)

    if "навстречу" in lower and "расстояние между" in lower and "до встречи" in lower:
        total_match = re.search(r"расстояние между[^\d]{0,40}(\d+)", lower)
        path_match = re.search(r"прош[её]л[^\d]{0,20}(\d+)\s*(?:км|м)", lower)
        if total_match and path_match and speed_values:
            total_distance = int(total_match.group(1))
            first_path = int(path_match.group(1))
            solved = explain_meeting_other_speed_word_problem(total_distance, speed_values[0], first_path, distance_unit, speed_unit)
            if solved:
                return solved

    if "в противоположных направлениях" in lower and through_value is not None and "расстояние между" in lower:
        distance_match = re.search(r"расстояние между[^\d]{0,40}(\d+)", lower)
        first_speed_match = re.search(r"скорост[ьяию] первого[^\d]{0,20}(\d+)", lower)
        first_speed = int(first_speed_match.group(1)) if first_speed_match else (speed_values[0] if speed_values else None)
        if distance_match and first_speed is not None:
            solved = explain_opposite_other_speed_word_problem(int(distance_match.group(1)), through_value, first_speed, speed_unit)
            if solved:
                return solved

    if "навстречу" in lower and through_value is not None and speed_delta_match and speed_values:
        delta = int(speed_delta_match.group(1))
        mode = speed_delta_match.group(2)
        solved = explain_meeting_distance_with_related_speed_word_problem(through_value, speed_values[0], delta, mode, distance_unit)
        if solved:
            return solved

    if "навстречу" in lower and len(speed_values) >= 2 and through_value is not None and not speed_delta_match:
        return explain_meeting_motion(speed_values[0], speed_values[1], through_value, distance_unit)
    if "в противоположных направлениях" in lower and len(speed_values) >= 2 and through_value is not None and not speed_delta_match:
        return explain_opposite_motion(speed_values[0], speed_values[1], through_value, distance_unit)
    if contains_any_fragment(lower, ("догонит", "догонку")) and len(nums) >= 2:
        return explain_catch_up_motion(nums[0], nums[1], time_unit or "ч")

    asks_distance = contains_any_fragment(lower, ("какое расстояние", "сколько километров", "какое расстояние пройдет", "какое расстояние он пройдет"))
    asks_speed = contains_any_fragment(lower, ("с какой скоростью", "какова скорость"))
    asks_time = contains_any_fragment(lower, ("сколько часов", "сколько времени", "за какое время"))

    if asks_time and len(speed_values) >= 2 and time_values:
        solved = explain_trip_time_for_same_distance(speed_values[0], time_values[0], speed_values[1])
        if solved and contains_any_fragment(lower, ("велосипедист", "тот же путь", "этот путь", "до посёлка", "до поселка")):
            return solved

    if asks_time and len(distance_values) >= 1 and len(speed_values) >= 2 and time_values and ("за два дня" in lower or "во второй" in lower):
        total_distance = max(distance_values)
        solved = explain_second_day_motion_time(total_distance, speed_values[0], time_values[0], speed_values[1])
        if solved:
            return solved

    if asks_speed and len(distance_values) >= 1 and speed_values and len(time_values) >= 2 and "остальную часть пути" in lower:
        total_distance = max(distance_values)
        solved = explain_remaining_part_speed(total_distance, speed_values[0], time_values[0], time_values[1])
        if solved:
            return solved

    faster_match = re.search(r"в\s+(\d+)\s+раз(?:а)?\s+быстре[её]", lower)
    if asks_time and faster_match and distance_values and speed_values and "обратно" in lower:
        factor = int(faster_match.group(1))
        solved = explain_return_trip_time_by_faster_speed(distance_values[0], speed_values[0], factor)
        if solved:
            return solved

    if asks_distance and speed_values and time_values:
        return explain_simple_motion_distance(speed_values[0], time_values[0], distance_unit)
    if asks_speed and distance_values and time_values:
        return explain_simple_motion_speed(distance_values[0], time_values[0], speed_unit)
    if asks_time and distance_values and speed_values:
        return explain_simple_motion_time(distance_values[0], speed_values[0], time_unit or "ч")
    return None



def try_local_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)

    if len(nums) >= 4 and "за всю покупку заплатили" in lower and "по" in lower and contains_any_fragment(lower, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        solved = explain_unknown_red_price(nums[0], nums[1], nums[2], nums[3])
        if solved:
            return solved

    if len(nums) == 2 and contains_any_fragment(lower, ("сколько стоит 1", "сколько стоит одна", "сколько стоит один", "сколько стоит 1 ")):
        solved = explain_simple_price_per_item(nums[0], nums[1])
        if solved:
            return solved

    if len(nums) == 2 and contains_any_fragment(lower, ("сколько стоят", "сколько стоила вся покупка", "сколько стоит вся покупка")):
        return explain_simple_total_cost(nums[0], nums[1])

    if len(nums) < 3:
        return None
    if contains_any_fragment(lower, ("за столько же", "на сколько пакет", "на сколько дороже", "на сколько дешевле")):
        return explain_price_difference_problem(nums[0], nums[1], nums[2])
    if contains_any_fragment(lower, ("сколько таких коробок", "сколько можно купить", "сколько коробок можно купить")):
        return explain_price_quantity_cost_problem(nums[0], nums[1], nums[2])
    return None



def try_local_sum_and_divide_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None

    if "в каждой клетке" in lower and "всего" in lower:
        solved = explain_cages_with_two_parts(nums[0], nums[1], nums[-1])
        if solved:
            return solved

    if contains_any_fragment(lower, ("сколько корзин", "сколько пакетов", "сколько булочек", "сколько клеток", "сколько потребуется", "сколько потребовалось")):
        if "по" in lower or "стоит" in lower or "поровну" in lower:
            solved = explain_sum_then_divide_word_problem(nums[0], nums[1], nums[2])
            if solved:
                return solved
    return None



def try_local_proportional_division_word_problem(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None

    if contains_any_fragment(lower, ("цена наборов одинаковая", "цена одинаковая", "если цена наборов одинаковая", "если цена одинаковая")):
        counts = nums[:2]
        total = nums[-1]
        solved = explain_equal_rate_distribution(total, counts[0], counts[1], "первую часть", "вторую часть")
        if solved:
            return solved

    if "бригада" in lower and contains_any_fragment(lower, ("сколько деталей изготовила каждая", "сколько деталей изготовила каждая бригада")):
        total = max(nums)
        counts = [n for n in nums if n != total]
        if len(counts) >= 2:
            solved = explain_equal_rate_distribution(total, counts[0], counts[1], "первая бригада", "вторая бригада")
            if solved:
                return solved

    if re.search(r"в двух кусках\s+\d+\s*м", lower) and contains_any_fragment(lower, ("сколько метров", "сколько м")):
        total_length_match = re.search(r"в двух кусках\s+(\d+)\s*м", lower)
        if total_length_match and len(nums) >= 3:
            total_length = int(total_length_match.group(1))
            costs = [n for n in nums if n != total_length]
            if len(costs) >= 2:
                solved = explain_piece_lengths_from_total_and_costs(total_length, costs[0], costs[1])
                if solved:
                    return solved
    return None



def try_local_difference_unknown_word_problem(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None

    if contains_any_fragment(lower, ("мешков больше", "мешков меньше")) and "кг" in lower and len(nums) >= 3:
        first_name = "моркови" if "морков" in lower else "первого"
        second_name = "картофеля" if "картоф" in lower else "второго"
        solved = explain_bag_counts_from_mass_difference(nums[0], nums[1], nums[2], first_name, second_name)
        if solved:
            return solved

    if contains_any_fragment(lower, ("на 360 кг меньше", "на 360 кг больше", "на 240 рублей дороже", "на 240 руб", "на 240 долларов дороже")) and "мешков" in lower:
        solved = explain_masses_from_bag_difference(nums[0], nums[1], nums[2])
        if solved:
            return solved

    if "ведром" in lower and contains_any_fragment(lower, ("одинаковое количество ходок", "одинаковое количество", "одинаковое число ходок")):
        big_bucket = max(nums[0], nums[1])
        small_bucket = min(nums[0], nums[1])
        diff_total = nums[2]
        solved = explain_water_buckets_difference(big_bucket, small_bucket, diff_total)
        if solved:
            return solved

    if "кус" in lower and contains_any_fragment(lower, ("дороже", "дешевле")) and len(nums) >= 3:
        solved = explain_costs_from_length_difference(nums[0], nums[1], nums[2])
        if solved:
            return solved
    return None



def try_local_measurement_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    window_match = re.search(r"высота окна\s+(\d+)\s*м[^\d]{0,30}ширина\s+(\d+)\s*м\s*(\d+)\s*дм", lower)
    if window_match and "площад" in lower:
        height_m = int(window_match.group(1))
        width_m = int(window_match.group(2))
        width_dm = int(window_match.group(3))
        height_in_dm = height_m * 10
        width_in_dm = width_m * 10 + width_dm
        area = height_in_dm * width_in_dm
        return join_explanation_lines(
            f"Сначала переводим высоту в дециметры: {height_m} м = {height_in_dm} дм",
            f"Потом переводим ширину в дециметры: {width_m} м {width_dm} дм = {width_in_dm} дм",
            f"Теперь находим площадь окна: {height_in_dm} × {width_in_dm} = {area}",
            f"Ответ: {area} дм²",
            "Совет: перед вычислением площади переводи длину и ширину в одинаковые единицы",
        )

    thickness_match = re.search(r"толщина стены\s+(\d+)\s*см", lower)
    frame_match = re.search(r"рама[^\d]{0,40}в\s+(\d+)\s+раз(?:а)?\s+тоньше", lower)
    glass_match = re.search(r"стекл[^\d]{0,40}в\s+(\d+)\s+раз(?:а)?\s+тоньше", lower)
    if thickness_match and frame_match and glass_match and "мм" in lower:
        wall_cm = int(thickness_match.group(1))
        frame_factor = int(frame_match.group(1))
        glass_factor = int(glass_match.group(1))
        if frame_factor != 0 and wall_cm % frame_factor == 0:
            frame_cm = wall_cm // frame_factor
            frame_mm = frame_cm * 10
            if glass_factor != 0 and frame_mm % glass_factor == 0:
                glass_mm = frame_mm // glass_factor
                return join_explanation_lines(
                    f"Сначала находим толщину рамы: {wall_cm} : {frame_factor} = {frame_cm} см",
                    f"Потом переводим толщину рамы в миллиметры: {frame_cm} см = {frame_mm} мм",
                    f"Теперь находим толщину стекла: {frame_mm} : {glass_factor} = {glass_mm} мм",
                    f"Ответ: {glass_mm} мм",
                    "Совет: если в ответе нужна другая единица длины, сначала сделай перевод единиц",
                )
    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_local_fraction_word_problem_explanation(user_text)
        or try_local_motion_word_problem_explanation(user_text)
        or try_local_price_word_problem_explanation(user_text)
        or try_local_unit_rate_word_problem_explanation(user_text)
        or try_local_sum_and_divide_word_problem_explanation(user_text)
        or try_local_proportional_division_word_problem(user_text)
        or try_local_difference_unknown_word_problem(user_text)
        or try_local_indirect_word_problem_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        prepared = add_task_context_lines(local_explanation, user_text, kind)
        return {"result": shape_explanation(prepared, kind), "source": "local", "validated": True}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1400,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    prepared = add_task_context_lines(llm_result["result"], user_text, kind)
    shaped = shape_explanation(prepared, kind)
    return {"result": shaped, "source": "llm", "validated": False}


# --- PATCH: detail fixes ---

def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        "Сначала вспоминаем правило: цена = стоимость : количество",
        f"Находим цену одной штуки: {total_cost} : {count} = {price}",
        f"Ответ: {price} руб.",
        "Совет: цену одного предмета находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        "Сначала вспоминаем правило: стоимость = цена × количество",
        f"Находим стоимость покупки: {price} × {count} = {total}",
        f"Ответ: {total} руб.",
        "Совет: стоимость находят умножением цены на количество",
    )


def explain_trip_time_for_same_distance(speed1: int, time1: int, speed2: int) -> Optional[str]:
    distance = speed1 * time1
    if speed2 == 0 or distance % speed2 != 0:
        return None
    time2 = distance // speed2
    return join_explanation_lines(
        f"Сначала находим расстояние между пунктами: {speed1} × {time1} = {distance}",
        f"Потом находим время для второго участника: {distance} : {speed2} = {time2}",
        f"Ответ: {time2} ч",
        "Совет: если путь один и тот же, сначала найди расстояние, потом дели его на новую скорость",
    )


def explain_second_day_motion_time(total_distance: int, first_speed: int, first_time: int, second_speed: int) -> Optional[str]:
    first_distance = first_speed * first_time
    second_distance = total_distance - first_distance
    if second_speed == 0 or second_distance < 0 or second_distance % second_speed != 0:
        return None
    second_time = second_distance // second_speed
    total_time = first_time + second_time
    return join_explanation_lines(
        f"Сначала находим путь в первый день: {first_speed} × {first_time} = {first_distance}",
        f"Потом находим путь во второй день: {total_distance} - {first_distance} = {second_distance}",
        f"Теперь находим время во второй день: {second_distance} : {second_speed} = {second_time}",
        f"И находим всё время: {first_time} + {second_time} = {total_time}",
        f"Ответ: во второй день — {second_time} ч; всего — {total_time} ч",
        "Совет: в составной задаче на движение сначала находят путь, потом время",
    )


def explain_remaining_part_speed(total_distance: int, first_speed: int, first_time: int, second_time: int) -> Optional[str]:
    first_distance = first_speed * first_time
    remaining_distance = total_distance - first_distance
    if second_time == 0 or remaining_distance < 0 or remaining_distance % second_time != 0:
        return None
    second_speed = remaining_distance // second_time
    return join_explanation_lines(
        f"Сначала находим первую часть пути: {first_speed} × {first_time} = {first_distance}",
        f"Потом находим оставшийся путь: {total_distance} - {first_distance} = {remaining_distance}",
        f"Теперь находим скорость на оставшейся части пути: {remaining_distance} : {second_time} = {second_speed}",
        f"Ответ: {second_speed} км/ч",
        "Совет: если известны оставшийся путь и время, скорость находят делением",
    )


def explain_return_trip_time_by_faster_speed(distance: int, speed: int, factor: int) -> Optional[str]:
    if speed == 0 or factor == 0 or distance % speed != 0:
        return None
    first_time = distance // speed
    faster_speed = speed * factor
    if faster_speed == 0 or distance % faster_speed != 0:
        return None
    return_time = distance // faster_speed
    return join_explanation_lines(
        f"Сначала находим время в одну сторону: {distance} : {speed} = {first_time}",
        f"Потом находим скорость на обратном пути: {speed} × {factor} = {faster_speed}",
        f"Теперь находим время на обратный путь: {distance} : {faster_speed} = {return_time}",
        f"Ответ: {return_time} ч",
        "Совет: если на обратном пути скорость увеличилась в несколько раз, сначала найди новую скорость",
    )


def try_local_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)

    if len(nums) >= 4 and "за всю покупку заплатили" in lower and "по" in lower and contains_any_fragment(lower, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        solved = explain_unknown_red_price(nums[0], nums[1], nums[2], nums[3])
        if solved:
            return solved

    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоит 1", "сколько стоит одна", "сколько стоит один", "сколько стоит 1 ")):
        solved = explain_simple_price_per_item(nums[0], nums[1])
        if solved:
            return solved

    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоят", "сколько стоила вся покупка", "сколько стоит вся покупка")):
        return explain_simple_total_cost(nums[0], nums[1])

    if len(nums) < 3:
        return None
    if contains_any_fragment(lower, ("за столько же", "на сколько пакет", "на сколько дороже", "на сколько дешевле")):
        return explain_price_difference_problem(nums[0], nums[1], nums[2])
    if contains_any_fragment(lower, ("сколько таких коробок", "сколько можно купить", "сколько коробок можно купить")):
        return explain_price_quantity_cost_problem(nums[0], nums[1], nums[2])
    return None


# --- PATCH: context extraction fixes ---

def extract_condition_and_question(raw_text: str) -> Tuple[str, str]:
    cleaned = normalize_word_problem_text(raw_text)
    parts = [part.strip() for part in re.split(r"(?<=[.?!])\s+", cleaned) if part.strip()]
    if not parts:
        return "", ""

    question_parts = [part.rstrip(".?!") for part in parts if "?" in part]
    condition_parts = [part.rstrip(".?!") for part in parts if "?" not in part]

    if not question_parts and parts:
        last = parts[-1].rstrip(".?!")
        if re.match(r"^(?:сколько|каков|какова|какое|какая|чему|найти|найдите|узнай|узнайте)", last.lower()):
            question_parts = [last]
            condition_parts = [part.rstrip(".?!") for part in parts[:-1]]

    condition = " ".join(condition_parts).strip()
    question = " ".join(question_parts).strip()
    if len(condition) > 240:
        condition = condition[:237].rstrip() + "..."
    if len(question) > 180:
        question = question[:177].rstrip() + "..."
    return condition, question
