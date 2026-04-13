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

DEEPSEEK_API_KEY = (os.environ.get("myapp_ai_math_1_4_API_key") or "").strip()


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
        if not looks_like_math_input(user_text):
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




# --- FINAL PATCH: detailed school-style formatting, safer fallback, richer step output ---

DEEPSEEK_API_KEY = (os.environ.get("myapp_ai_math_1_4_API_key") or "").strip()

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать очень подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой содержательной строке пиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, пиши строку:
Порядок действий:
Потом сам пример и над знаками действий цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши строку:
Решение по действиям:
4. Ниже обязательно пиши:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. По возможности используй школьную форму:
Если ..., то ...
6. После каждого действия коротко говори, что нашли.
7. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()

BODY_LIMITS = {
    "expression": 40,
    "equation": 20,
    "fraction": 24,
    "geometry": 30,
    "word": 40,
    "other": 20,
}

_ORIGINAL_try_local_expression_explanation = try_local_expression_explanation
_ORIGINAL_try_local_equation_explanation = try_local_equation_explanation
_ORIGINAL_try_local_fraction_explanation = try_local_fraction_explanation
_ORIGINAL_try_local_geometry_explanation = try_local_geometry_explanation
_ORIGINAL_try_local_fraction_word_problem_explanation = try_local_fraction_word_problem_explanation
_ORIGINAL_try_local_motion_word_problem_explanation = try_local_motion_word_problem_explanation
_ORIGINAL_try_local_price_word_problem_explanation = try_local_price_word_problem_explanation
_ORIGINAL_try_local_unit_rate_word_problem_explanation = try_local_unit_rate_word_problem_explanation
_ORIGINAL_try_local_sum_and_divide_word_problem_explanation = try_local_sum_and_divide_word_problem_explanation
_ORIGINAL_try_local_proportional_division_word_problem = try_local_proportional_division_word_problem
_ORIGINAL_try_local_difference_unknown_word_problem = try_local_difference_unknown_word_problem
_ORIGINAL_try_local_indirect_word_problem_explanation = try_local_indirect_word_problem_explanation
_ORIGINAL_try_local_compound_word_problem_explanation = try_local_compound_word_problem_explanation
_ORIGINAL_try_local_word_problem_explanation = try_local_word_problem_explanation


def _detailed_split_sections(text: str) -> dict:
    cleaned = sanitize_model_text(text)
    body: List[str] = []
    answer = ""
    advice = ""
    check = ""
    for raw in cleaned.split("\n"):
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("ответ:"):
            value = line.split(":", 1)[1].strip().rstrip(".!?").strip()
            if value and not answer:
                answer = value
            continue
        if lower.startswith("совет:"):
            value = line.split(":", 1)[1].strip().rstrip(".!?").strip()
            if value and not advice:
                advice = value
            continue
        if lower.startswith("проверка:"):
            value = line.split(":", 1)[1].strip()
            if value and not check:
                check = f"Проверка: {value}"
            continue
        body.append(line)
    return {"body": body, "answer": answer, "advice": advice, "check": check}


def _detailed_finalize_line(line: str) -> str:
    raw = str(line or "").rstrip()
    if not raw:
        return ""
    stripped = raw.strip()
    if re.fullmatch(r"[ 0-9()+\-×:=/]+", raw):
        return raw
    if re.match(r"^(?:Пример|Порядок действий|Решение по действиям|Решение|Задача|Уравнение)\b", stripped, flags=re.IGNORECASE):
        return stripped
    if stripped[-1] not in ".!?":
        stripped += "."
    return stripped


def _detailed_finalize_text(lines: List[str]) -> str:
    finalized = []
    for line in lines:
        fixed = _detailed_finalize_line(line)
        if fixed:
            finalized.append(fixed)
    return "\n".join(finalized).strip()


def _detailed_strip_sequence_prefix(line: str) -> str:
    text = str(line or "").strip()
    text = re.sub(r"^(?:сначала|потом|теперь|дальше)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^и\s+", "", text, flags=re.IGNORECASE)
    if text:
        text = text[0].upper() + text[1:]
    return text


def _detailed_number_lines(lines: List[str]) -> List[str]:
    result: List[str] = []
    counter = 1
    for raw in lines:
        line = str(raw or "").strip()
        if not line:
            continue
        if re.match(r"^\d+\)", line):
            result.append(line)
            counter += 1
            continue
        line = _detailed_strip_sequence_prefix(line)
        result.append(f"{counter}) {line}")
        counter += 1
    return result


def _detailed_statement_text(raw_text: str) -> str:
    text = strip_known_prefix(str(raw_text or "").replace("\r", " ").replace("\n", " "))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detailed_is_column_like(body_lines: List[str]) -> bool:
    joined = " ".join(body_lines).lower()
    markers = (
        "столбик",
        "неполное делимое",
        "неполное произведение",
        "скорость сближения",
        "скорость удаления",
    )
    return any(marker in joined for marker in markers)


def _detailed_find_operator_position(source: str, node: ast.AST) -> Optional[int]:
    if not isinstance(node, ast.BinOp):
        return None
    try:
        left_end = node.left.end_col_offset
        right_start = node.right.col_offset
        segment = source[left_end:right_start]
        for offset, char in enumerate(segment):
            if char in "+-*/":
                return left_end + offset
        for index in range(node.col_offset, node.end_col_offset):
            if 0 <= index < len(source) and source[index] in "+-*/":
                return index
    except Exception:
        return None
    return None


def _detailed_collect_expression_steps(node: ast.AST, source: str) -> List[dict]:
    if is_int_literal_node(node):
        return []
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return []
    if not isinstance(node, ast.BinOp):
        return []
    left_steps = _detailed_collect_expression_steps(node.left, source)
    right_steps = _detailed_collect_expression_steps(node.right, source)
    try:
        left_value = format_fraction(eval_fraction_node(node.left))
        right_value = format_fraction(eval_fraction_node(node.right))
        result_value = format_fraction(eval_fraction_node(node))
    except Exception:
        return left_steps + right_steps
    position = _detailed_find_operator_position(source, node)
    return left_steps + right_steps + [{
        "left": left_value,
        "right": right_value,
        "operator": OPERATOR_SYMBOLS[type(node.op)],
        "result": result_value,
        "pos": position,
    }]


def _detailed_compact_expression(source: str) -> str:
    return source.replace("*", "×").replace("/", ":")


def _detailed_build_order_block(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return []
    expr = _detailed_compact_expression(source)
    marks = [" "] * len(expr)
    for index, step in enumerate(steps, start=1):
        pos = step.get("pos")
        if pos is None or pos < 0 or pos >= len(marks):
            continue
        label = str(index)
        for offset, char in enumerate(reversed(label)):
            target = pos - offset
            if target < 0:
                break
            marks[target] = char
    mark_line = "".join(marks).rstrip()
    if not mark_line:
        return []
    return ["Порядок действий:", mark_line, expr]


def _detailed_expression_answer(source: str) -> str:
    node = parse_expression_ast(source)
    if node is None:
        return ""
    try:
        return format_fraction(eval_fraction_node(node))
    except Exception:
        return ""


def _detailed_pretty_equation(source: str) -> str:
    text = re.sub(r"([+\-*/=])", r" \1 ", source)
    text = text.replace("*", "×").replace("/", ":")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detailed_pretty_fraction_expression(source: str) -> str:
    text = re.sub(r"\s+", "", source)
    text = text.replace("+", " + ").replace("-", " - ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    lower = str(raw_text or "").lower().replace("ё", "е")
    if "руб" in lower or "денег" in lower:
        return f"{value} руб."
    return value


def _detailed_build_generic_steps_from_expression(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _detailed_collect_expression_steps(node, source)
    result = []
    for index, step in enumerate(steps, start=1):
        result.append(f"{index}) {step['left']} {step['operator']} {step['right']} = {step['result']}")
    return result


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")
    node = parse_expression_ast(source)
    pretty_expression = render_node(node) if node is not None else _detailed_compact_expression(source)
    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("что известно:", "что нужно найти:"))]
    if not body_lines:
        body_lines = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]
    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block and not _detailed_is_column_like(body_lines):
        lines.extend(order_block)
        lines.append("Решение по действиям:")
    else:
        lines.append("Решение.")
    lines.extend(_detailed_number_lines(body_lines))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_equation_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_equation_source(raw_text) or normalize_cyrillic_x(strip_known_prefix(raw_text))
    pretty = _detailed_pretty_equation(source)
    answer = parts["answer"] or "проверь запись"
    if re.fullmatch(r"-?\d+(?:/\d+)?", answer):
        answer = f"x = {answer}"
    lines: List[str] = [f"Уравнение: {pretty}", "Решение."]
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("equation")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_fraction_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_fraction_source(raw_text) or strip_known_prefix(raw_text)
    pretty = _detailed_pretty_fraction_expression(source)
    answer = parts["answer"] or "проверь запись"
    lines: List[str] = [f"Пример: {pretty} = {answer}", "Решение"]
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("fraction")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_word_like_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    info_lines: List[str] = []
    body_lines: List[str] = []
    for line in parts["body"]:
        lower = line.lower()
        if lower.startswith("что известно:") or lower.startswith("что нужно найти:"):
            info_lines.append(line)
        else:
            body_lines.append(line)
    if not info_lines:
        condition, question = extract_condition_and_question(raw_text)
        if condition:
            info_lines.append(f"Что известно: {condition}")
        if question:
            info_lines.append(f"Что нужно найти: {question}")
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines: List[str] = []
    if statement:
        lines.append("Задача.")
        lines.append(statement)
    lines.append("Решение.")
    lines.extend(info_lines)
    lines.extend(_detailed_number_lines(body_lines))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind if kind in DEFAULT_ADVICE else "other")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    lines: List[str] = []
    statement = _detailed_statement_text(raw_text)
    if statement and kind in {"word", "geometry"}:
        lines.append("Задача.")
        lines.append(statement)
        lines.append("Решение.")
    else:
        lines.append("Решение.")
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind)
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_solution(raw_text: str, text: str, kind: str) -> str:
    if kind == "expression" and to_expression_source(raw_text):
        return _detailed_format_expression_solution(raw_text, text)
    if kind == "equation" and to_equation_source(raw_text):
        return _detailed_format_equation_solution(raw_text, text)
    if kind == "fraction" and to_fraction_source(raw_text) and not re.search(r"[А-Яа-я]", raw_text):
        return _detailed_format_fraction_solution(raw_text, text)
    if kind in {"word", "geometry"} or re.search(r"[А-Яа-я]", raw_text):
        return _detailed_format_word_like_solution(raw_text, text, kind)
    return _detailed_format_generic_solution(raw_text, text, kind)


def shape_explanation(text: str, kind: str, forced_answer: Optional[str] = None, forced_advice: Optional[str] = None) -> str:
    parts = _detailed_split_sections(text)
    answer = forced_answer or parts["answer"] or "проверь запись"
    advice = forced_advice or parts["advice"] or default_advice(kind)
    lines = list(parts["body"])
    if kind == "equation" and parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def explain_sum_then_subtract_word_problem(first: int, second: int, removed: int) -> Optional[str]:
    total = first + second
    remaining = total - removed
    if remaining < 0:
        return None
    return join_explanation_lines(
        f"Сначала находим, сколько было всего: {first} + {second} = {total}",
        f"Потом находим, сколько осталось: {total} - {removed} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если сначала объединяют две группы, а потом часть убирают, сначала находят сумму",
    )


def try_local_sum_then_subtract_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3:
        return None
    asks_left = bool(re.search(r"сколько[^.?!]*\b(осталось|останется)\b", lower))
    loss_markers = WORD_LOSS_HINTS + ("уехал", "уехала", "уехали", "уехало", "ушел", "ушла", "ушли", "ушло", "забрали")
    has_loss = contains_any_fragment(lower, loss_markers)
    if asks_left and has_loss:
        return explain_sum_then_subtract_word_problem(nums[0], nums[1], nums[2])
    return None


def try_local_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower or ("заплат" not in lower and "стоил" not in lower and "стоят" not in lower and "стоимость" not in lower):
        return None

    matches = list(re.finditer(r"(\d+)\s+([^?.!,]{1,30}?)\s+по\s+(\d+)", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_name = matches[0].group(2).strip()
    first_price = int(matches[0].group(3))
    second_count = int(matches[1].group(1))
    second_name = matches[1].group(2).strip()
    second_price = int(matches[1].group(3))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"Если купили {first_count} {first_name} по {first_price} руб., то стоимость первой покупки равна {first_count} × {first_price} = {first_total} руб",
        f"Если купили {second_count} {second_name} по {second_price} руб., то стоимость второй покупки равна {second_count} × {second_price} = {second_total} руб",
        f"Если стоимость первой покупки {first_total} руб., а стоимость второй покупки {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала найди стоимость каждой покупки отдельно",
    )


def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_expression_explanation(raw_text)


def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_equation_explanation(raw_text)


def try_local_fraction_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_fraction_explanation(raw_text)


def try_local_geometry_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_geometry_explanation(raw_text)


def try_local_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_fraction_word_problem_explanation(raw_text)


def try_local_motion_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_motion_word_problem_explanation(raw_text)


def try_local_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_price_word_problem_explanation(raw_text)


def try_local_unit_rate_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_unit_rate_word_problem_explanation(raw_text)


def try_local_sum_and_divide_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_sum_and_divide_word_problem_explanation(raw_text)


def try_local_proportional_division_word_problem(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_proportional_division_word_problem(raw_text)


def try_local_difference_unknown_word_problem(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_difference_unknown_word_problem(raw_text)


def try_local_indirect_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_indirect_word_problem_explanation(raw_text)


def try_local_compound_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_compound_word_problem_explanation(raw_text)


def try_local_word_problem_explanation(raw_text: str) -> Optional[str]:
    return _ORIGINAL_try_local_word_problem_explanation(raw_text)


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
        or try_local_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_local_sum_then_subtract_word_problem_explanation(user_text)
        or try_local_proportional_division_word_problem(user_text)
        or try_local_difference_unknown_word_problem(user_text)
        or try_local_indirect_word_problem_explanation(user_text)
        or try_local_compound_word_problem_explanation(user_text)
        or try_local_word_problem_explanation(user_text)
    )


async def call_deepseek(payload: dict, timeout_seconds: float = 45.0):
    if not DEEPSEEK_API_KEY:
        return {"error": "DeepSeek API key is not configured"}
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


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": fallback, "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1800,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}



# --- FINAL SCHOOL PATCH: textbook-style word problems, clearer order marks, bug fixes ---

_PREVIOUS_build_explanation_local_first = build_explanation_local_first


def _question_text_only(raw_text: str) -> str:
    _, question = extract_condition_and_question(raw_text)
    return question.lower()


def _has_total_like_question(raw_text: str) -> bool:
    return asks_total_like(normalize_word_problem_text(raw_text).lower()) or "сколько всего" in normalize_word_problem_text(raw_text).lower()


def _has_group_count_question(text_lower: str) -> bool:
    return contains_any_fragment(
        text_lower,
        ("сколько короб", "сколько пакетов", "сколько корзин", "сколько клеток", "сколько сеток", "сколько потребуется", "сколько потребовалось", "сколько ведер", "сколько вёдер"),
    )


def _first_po_pair(text_lower: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d+)\s+[^\d?.!]{0,40}?\bпо\s+(\d+)\b", text_lower)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _fraction_numbers_and_text(raw_text: str):
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower()
    fracs = extract_all_fraction_pairs(lower)
    values = extract_non_fraction_numbers(lower)
    return text, lower, fracs, values


def _detailed_build_order_block(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return []

    pretty_parts: List[str] = []
    raw_to_pretty_op_pos: dict = {}
    current_len = 0
    for index, ch in enumerate(source):
        if ch in "+-*/":
            symbol = "×" if ch == "*" else ":" if ch == "/" else ch
            token = f" {symbol} "
            raw_to_pretty_op_pos[index] = current_len + 1
            pretty_parts.append(token)
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    pretty_expr = "".join(pretty_parts)

    marks = [" "] * len(pretty_expr)
    for step_index, step in enumerate(steps, start=1):
        raw_pos = step.get("pos")
        if raw_pos is None or raw_pos not in raw_to_pretty_op_pos:
            continue
        pretty_pos = raw_to_pretty_op_pos[raw_pos]
        label = str(step_index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, char in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = char

    return ["Порядок действий:", "".join(marks).rstrip(), pretty_expr]


def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part}",
        f"3) Если одна доля равна {one_part}, то все деньги равны {one_part} × {denominator} = {whole}",
        f"Ответ: всего было {whole}",
        "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
    )


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если сначала было {first}, а потом осталось {second}, то убрали {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько осталось или сколько убрали, обычно нужно вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если одно число равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        f"1) Если осталось {remaining}, а убрали {removed}, то сначала было {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находят сложением",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если стало {final_total}, а прибавили {added}, то сначала было {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают то, что прибавили",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {smaller}, а потом стало {bigger}, то добавили {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {bigger}, а потом осталось {smaller}, то убрали {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: проверь, на сколько частей делят")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов разделили на {groups} равные части, то {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        f"1) Если {total} разделить на {groups}, то получится {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов", "Ответ: запись задачи неверная", "Совет: проверь размер одной группы")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то групп будет {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"1) Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}",
            f"2) Так как предметы ещё остались, нужна ещё одна группа, всего {quotient + 1}",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления ещё есть остаток, иногда нужна ещё одна коробка или место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            f"1) Если {total} разделить на группы по {per_group}, то получится {quotient}, остаток {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {sign} {delta} = {related}",
        f"2) Если первое количество {base}, а второе количество {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
        f"2) Если первое количество {base}, а второе количество {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: сначала найди число, которое дано через отношение, потом считай общее количество",
    )


def explain_indirect_plus_minus_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        result = base - delta
        if result < 0:
            return None
        relation_text = "значит, другое число на столько же меньше"
        op = "-"
    else:
        result = base + delta
        relation_text = "значит, другое число на столько же больше"
        op = "+"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число на {delta} {relation}, то {relation_text}",
        f"2) Находим искомое число: {base} {op} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )


def explain_indirect_times_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        result = base // factor
        op = ":"
        relation_text = "значит, другое число во столько же раз меньше"
    else:
        result = base * factor
        op = "×"
        relation_text = "значит, другое число во столько же раз больше"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {relation_text}",
        f"2) Находим искомое число: {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} группах {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}",
        f"2) Если в одной группе {one_group}, то в {target_groups} группах {one_group} × {target_groups} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    relation = "дороже" if price_a > price_b else "дешевле"
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a}, то цена одного товара равна {total_a} : {quantity} = {price_a}",
        f"2) Если за {quantity} таких же товаров заплатили {total_b}, то цена одного товара равна {total_b} : {quantity} = {price_b}",
        f"3) Если одна цена {price_a}, а другая {price_b}, то разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff}",
        f"Ответ: на {diff} руб. {relation}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых коробок заплатили {total_cost}, то цена одной коробки равна {total_cost} : {quantity} = {price}",
        f"2) Если одна коробка стоит {price}, то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result}",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находят цену одной коробки",
    )


def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если известные цветы купили {known_count} раза по {known_price} руб., то за них заплатили {known_count} × {known_price} = {known_total} руб",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за известные цветы {known_total} руб., то за остальные цветы заплатили {total_cost} - {known_total} = {other_total} руб",
        f"3) Если за {unknown_count} остальных цветов заплатили {other_total} руб., то одна штука стоит {other_total} : {unknown_count} = {unit_price} руб",
        f"Ответ: одна красная гвоздика стоила {unit_price} руб",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть",
    )


def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        f"1) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб",
        f"Ответ: один предмет стоит {price} руб",
        "Совет: цену одной штуки находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        f"1) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб",
        f"Ответ: вся покупка стоит {total} руб",
        "Совет: стоимость находят умножением цены на количество",
    )


def try_high_priority_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower or ("заплат" not in lower and "стоил" not in lower and "стоимость" not in lower):
        return None

    matches = list(re.finditer(r"(\d+)\s+([^?.!,]{1,30}?)\s+по\s+(\d+)", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_name = matches[0].group(2).strip()
    first_price = int(matches[0].group(3))
    second_count = int(matches[1].group(1))
    second_name = matches[1].group(2).strip()
    second_price = int(matches[1].group(3))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если купили {first_count} {first_name} по {first_price} руб., то за {first_name} заплатили {first_count} × {first_price} = {first_total} руб",
        f"2) Если купили {second_count} {second_name} по {second_price} руб., то за {second_name} заплатили {second_count} × {second_price} = {second_total} руб",
        f"3) Если за первую покупку заплатили {first_total} руб., а за вторую {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def try_high_priority_unknown_addend_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None

    if re.search(r"(?:на двух|на обеих|на обоих|за два дня|всего|из них|на всем теле|на всём теле)", lower) and not _has_total_like_question(raw_text):
        total, known = nums[0], nums[1]
        if total < known:
            return None
        result = total - known
        return join_explanation_lines(
            f"1) Если всего было {total}, а одна часть равна {known}, то другая часть равна {total} - {known} = {result}",
            f"Ответ: {result}",
            "Совет: чтобы найти неизвестную часть, из целого вычитают известную часть",
        )
    return None


def try_high_priority_added_removed_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None

    if re.search(r"\b(стало|их стало|теперь стало|получилось)\b", lower) and contains_any_fragment(lower, WORD_GAIN_HINTS + ("постав", "добав", "приех", "вошло", "прибав")):
        before, after = nums[0], nums[1]
        if after < before:
            return None
        added = after - before
        return join_explanation_lines(
            f"1) Если сначала было {before}, а потом стало {after}, то добавили {after} - {before} = {added}",
            f"Ответ: {added}",
            "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
        )

    if re.search(r"\b(осталось|осталось прочитать|пришло|осталось расфасовать)\b", lower) and contains_any_fragment(lower, WORD_LOSS_HINTS + ("забрали", "сняли", "вышло", "заболело", "заболели", "заболел")):
        before, after = nums[0], nums[1]
        if before < after:
            return None
        removed = before - after
        return join_explanation_lines(
            f"1) Если сначала было {before}, а потом осталось {after}, то убрали {before} - {after} = {removed}",
            f"Ответ: {removed}",
            "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
        )

    if ("сколько было" in lower or "сколько было сначала" in lower) and re.search(r"\b(осталось|осталось на|осталось в)\b", lower):
        removed, left = nums[0], nums[1]
        result = removed + left
        return join_explanation_lines(
            f"1) Если убрали {removed}, а осталось {left}, то сначала было {removed} + {left} = {result}",
            f"Ответ: {result}",
            "Совет: неизвестное уменьшаемое находят сложением",
        )
    return None


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower:
        return None
    if _has_group_count_question(lower) or "поровну" in lower or "кажд" in lower:
        return None
    if not (asks_total_like(lower) or contains_any_fragment(lower, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько огурцов", "сколько конфет"))):
        return None

    pair = _first_po_pair(lower)
    if not pair:
        return None
    groups, per_group = pair
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {groups * per_group}",
        f"Ответ: {groups * per_group}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    total_like_match = re.search(r"\b(?:было|всего|масса|длина|путь|прошли|прошёл|прошла|прошли за|на складе было|у мальчика было|у мамы было|у туристов было|листов было|руды)\b", lower)
    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)

    # Известно всё число, нужно найти часть или остаток.
    if values and (total_like_match or not remain_match):
        total = max(values)
        if ("остал" in lower or "во 2 день" in lower or "во второй день" in lower):
            if total % denominator != 0:
                return None
            one_part = total // denominator
            part = one_part * numerator
            remaining = total - part
            if "во 2 день" in lower or "во второй день" in lower:
                return join_explanation_lines(
                    f"1) Если весь путь равен {total}, то одна доля равна {total} : {denominator} = {one_part}",
                    f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part}",
                    f"3) Если весь путь {total}, а в первый день прошли {part}, то во второй день прошли {total} - {part} = {remaining}",
                    f"Ответ: во второй день прошли {remaining}",
                    "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
                )
            return join_explanation_lines(
                f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part}",
                f"3) Если всего было {total}, а израсходовали {part}, то осталось {total} - {part} = {remaining}",
                f"Ответ: осталось {remaining}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        if total % denominator == 0:
            one_part = total // denominator
            part = one_part * numerator
            return join_explanation_lines(
                f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
                f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part}",
                f"Ответ: {part}",
                "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
            )

    # Известно, сколько осталось после расхода части.
    if remain_match:
        remaining_value = int(remain_match.group(1))
        solved = explain_whole_by_remaining_fraction(remaining_value, numerator, denominator)
        if solved:
            return solved

    return None


def try_high_priority_unknown_price_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) >= 4 and "за всю покупку заплатили" in lower and "по" in lower and contains_any_fragment(lower, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        return explain_unknown_red_price(nums[0], nums[1], nums[2], nums[3])
    return None


def try_high_priority_total_cost_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоит 1", "сколько стоит одна", "сколько стоит один", "сколько стоит 1 ")):
        return explain_simple_price_per_item(nums[0], nums[1])
    if len(nums) >= 2 and contains_any_fragment(lower, ("сколько стоят", "сколько стоила вся покупка", "сколько стоит вся покупка")):
        return explain_simple_total_cost(nums[0], nums[1])
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_unknown_price_word_problem_explanation(user_text)
        or try_high_priority_total_cost_word_problem_explanation(user_text)
        or try_high_priority_fraction_word_problem_explanation(user_text)
        or try_high_priority_unknown_addend_word_problem_explanation(user_text)
        or try_high_priority_added_removed_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PREVIOUS_build_explanation_local_first(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1800,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}



# --- FINAL SCHOOL PATCH 2: units, group totals, cleaner purchase wording ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower = normalize_word_problem_text(raw_text).lower()
    if "скорост" in question:
        if "км/ч" in lower:
            return "км/ч"
        if "м/мин" in lower:
            return "м/мин"
        if "м/с" in lower:
            return "м/с"
    for unit in ("руб.", "руб", "кг", "г", "км", "м", "см", "дм", "мм", "л", "ч", "мин"):
        if unit in question:
            return unit.replace(".", "")
    if "деньг" in question or "денег" in question:
        return "руб"
    return ""


def _append_unit_to_number_text(value: int, raw_text: str) -> str:
    unit = _detect_question_unit(raw_text)
    if not unit:
        return str(value)
    return f"{value} {unit}"


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}"
        lower = str(raw_text or "").lower().replace("ё", "е")
        if "руб" in lower or "денег" in lower:
            return f"{value} руб."
    return value


def try_high_priority_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower or ("заплат" not in lower and "стоил" not in lower and "стоимость" not in lower):
        return None

    matches = list(re.finditer(r"(\d+)\s+([^?.!,]{1,30}?)\s+по\s+(\d+)", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_price = int(matches[0].group(3))
    second_count = int(matches[1].group(1))
    second_price = int(matches[1].group(3))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если первая покупка состоит из {first_count} предметов по {first_price} руб., то её стоимость равна {first_count} × {first_price} = {first_total} руб",
        f"2) Если вторая покупка состоит из {second_count} предметов по {second_price} руб., то её стоимость равна {second_count} × {second_price} = {second_total} руб",
        f"3) Если первая покупка стоит {first_total} руб., а вторая {second_total} руб., то вся покупка стоит {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    if "сколько" not in lower:
        return None
    if _has_group_count_question(lower) or "поровну" in lower:
        return None
    if not (asks_total_like(lower) or contains_any_fragment(lower, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько огурцов", "сколько конфет"))):
        return None

    pair = _first_po_pair(lower)
    if not pair:
        return None
    groups, per_group = pair
    total = groups * per_group
    answer_value = _append_unit_to_number_text(total, raw_text)
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {total}",
        f"Ответ: {answer_value}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    unit = _detect_question_unit(raw_text)

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    total_like_match = re.search(r"\b(?:было|всего|масса|длина|путь|прошли|прошёл|прошла|прошли за|на складе было|у мальчика было|у мамы было|листов было|руды)\b", lower)
    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)

    if values and (total_like_match or not remain_match):
        total = max(values)
        if ("остал" in lower or "во 2 день" in lower or "во второй день" in lower):
            if total % denominator != 0:
                return None
            one_part = total // denominator
            part = one_part * numerator
            remaining = total - part
            remaining_text = f"{remaining} {unit}".strip()
            total_text = f"{total} {unit}".strip()
            one_part_text = f"{one_part} {unit}".strip()
            part_text = f"{part} {unit}".strip()
            if "во 2 день" in lower or "во второй день" in lower:
                return join_explanation_lines(
                    f"1) Если весь путь равен {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                    f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part_text}",
                    f"3) Если весь путь {total_text}, а в первый день прошли {part_text}, то во второй день прошли {total} - {part} = {remaining_text}",
                    f"Ответ: во второй день прошли {remaining_text}",
                    "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
                )
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"3) Если всего было {total_text}, а израсходовали {part_text}, то осталось {total} - {part} = {remaining_text}",
                f"Ответ: осталось {remaining_text}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        if total % denominator == 0:
            one_part = total // denominator
            part = one_part * numerator
            total_text = f"{total} {unit}".strip()
            one_part_text = f"{one_part} {unit}".strip()
            part_text = f"{part} {unit}".strip()
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"Ответ: {part_text}",
                "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
            )

    if remain_match:
        remaining_value = int(remain_match.group(1))
        solved = explain_whole_by_remaining_fraction(remaining_value, numerator, denominator)
        if solved:
            if unit:
                solved = solved.replace(f"равны {remaining_value}", f"равны {remaining_value} {unit}")
                solved = re.sub(rf"Ответ:\s*всего было (\d+)([.!?])", rf"Ответ: всего было \1 {unit}\2", solved)
            return solved

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_unknown_price_word_problem_explanation(user_text)
        or try_high_priority_total_cost_word_problem_explanation(user_text)
        or try_high_priority_fraction_word_problem_explanation(user_text)
        or try_high_priority_unknown_addend_word_problem_explanation(user_text)
        or try_high_priority_added_removed_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PREVIOUS_build_explanation_local_first(user_text, kind)
    )



# --- FINAL SCHOOL PATCH 3: safer unit detection ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower()

    if "скорост" in question:
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"руб|денег", question) or ("руб" in lower_full and re.search(r"сколько|каков|какова|чему", question)):
        return "руб"
    if re.search(r"килограмм|кг", question):
        return "кг"
    if re.search(r"\bграмм|\bг\b", question):
        return "г"
    if re.search(r"километр|км", question):
        return "км"
    if re.search(r"\bметр|\bм\b", question):
        return "м"
    if re.search(r"сантиметр|см", question):
        return "см"
    if re.search(r"дециметр|дм", question):
        return "дм"
    if re.search(r"миллиметр|мм", question):
        return "мм"
    if re.search(r"литр|\bл\b", question):
        return "л"
    if re.search(r"час|сколько времени|за какое время", question):
        return "ч"
    if re.search(r"минут|мин", question):
        return "мин"
    return ""



# --- FINAL SCHOOL PATCH 4: reliable fraction routing for total-known vs remaining-known cases ---

def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    unit = _detect_question_unit(raw_text)

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
    explicit_total_match = re.search(r"(?:\bбыло\b|\bвсего\b|\bмасса\b|\bдлина\b|\bпуть\b|\bпрошли\b|\bпрошёл\b|\bпрошла\b|\bлистов\b|\bруды\b)[^\d]{0,40}(\d+)", lower)

    # 1) Случай: известен остаток после расхода дробной части, а всё число неизвестно.
    if remain_match and (not explicit_total_match or explicit_total_match.start() > remain_match.start()):
        remaining_value = int(remain_match.group(1))
        remaining_numerator = denominator - numerator
        if remaining_numerator <= 0 or remaining_value % remaining_numerator != 0:
            return None
        one_part = remaining_value // remaining_numerator
        whole = one_part * denominator
        remaining_text = f"{remaining_value} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        whole_text = f"{whole} {unit}".strip()
        return join_explanation_lines(
            f"1) Если израсходовали {numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
            f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_text}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part_text}",
            f"3) Если одна доля равна {one_part_text}, то все деньги равны {one_part} × {denominator} = {whole_text}",
            f"Ответ: всего было {whole_text}",
            "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
        )

    # 2) Случай: всё число известно, нужно найти часть или остаток.
    if values:
        total = max(values)
        if total % denominator != 0:
            return None
        one_part = total // denominator
        part = one_part * numerator
        remaining = total - part
        total_text = f"{total} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        part_text = f"{part} {unit}".strip()
        remaining_text = f"{remaining} {unit}".strip()

        if "во 2 день" in lower or "во второй день" in lower:
            return join_explanation_lines(
                f"1) Если весь путь равен {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part_text}",
                f"3) Если весь путь {total_text}, а в первый день прошли {part_text}, то во второй день прошли {total} - {part} = {remaining_text}",
                f"Ответ: во второй день прошли {remaining_text}",
                "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
            )

        if "остал" in lower:
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"3) Если всего было {total_text}, а израсходовали {part_text}, то осталось {total} - {part} = {remaining_text}",
                f"Ответ: осталось {remaining_text}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        return join_explanation_lines(
            f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
            f"Ответ: {part_text}",
            "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
        )

    return None



# --- FINAL SCHOOL PATCH 5: only attach units when the question itself asks for that unit ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower()

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:килограмм|кг)\b", question):
        return "кг"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:сколько|какова|какое расстояние|какой путь|чему равно расстояние)[^?.!]{0,25}(?:километр|км)\b", question):
        return "км"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:сантиметр|см)\b", question):
        return "см"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:дециметр|дм)\b", question):
        return "дм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:миллиметр|мм)\b", question):
        return "мм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"

    if "сколько денег" in question or ("руб" in lower_full and "сколько сто" in question):
        return "руб"
    return ""



# --- FINAL SCHOOL PATCH 6: fix "килограммов" vs "граммов" distinction ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower()

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:сколько|какова|какое расстояние|какой путь|чему равно расстояние)[^?.!]{0,25}(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:миллиметр|мм)", question):
        return "мм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"

    if "сколько денег" in question or ("руб" in lower_full and "сколько сто" in question):
        return "руб"
    return ""


# --- OPENAI FINAL PATCH 2026-04-10: routing fixes, textbook-style compound tasks, safer answer units, ASCII columns ---

_PATCH8_PREVIOUS_build_explanation_local_first = build_explanation_local_first
_PATCH8_PREVIOUS_explain_column_addition = explain_column_addition
_PATCH8_PREVIOUS_explain_column_subtraction = explain_column_subtraction
_PATCH8_PREVIOUS_explain_long_multiplication = explain_long_multiplication
_PATCH8_PREVIOUS_explain_long_division = explain_long_division

_PREFIX_NUMBER_MAP = {
    "одн": 1,
    "одно": 1,
    "двух": 2,
    "трех": 3,
    "трёх": 3,
    "четырех": 4,
    "четырёх": 4,
    "пяти": 5,
    "шести": 6,
    "семи": 7,
    "восьми": 8,
    "девяти": 9,
    "десяти": 10,
}


def _remove_one_value(seq: List[int], value: int) -> List[int]:
    data = list(seq)
    try:
        data.remove(value)
    except ValueError:
        pass
    return data


def _word_multiplier_value(word: str) -> Optional[int]:
    token = str(word or "").lower().replace("ё", "е")
    for prefix, value in _PREFIX_NUMBER_MAP.items():
        if token.startswith(prefix):
            return value
    return None


def _find_group_pair_any(text_lower: str) -> Optional[dict]:
    text = str(text_lower or "").lower().replace("ё", "е")
    match = re.search(r"(\d+)\s+[^\d?.!]{0,40}?\bпо\s+(\d+)\b", text)
    if match:
        return {
            "groups": int(match.group(1)),
            "per_group": int(match.group(2)),
            "start": match.start(),
            "end": match.end(),
            "kind": "po",
        }

    for match in re.finditer(r"(\d+)\s+([а-яa-z-]+)", text):
        groups = int(match.group(1))
        word = match.group(2)
        per_group = _word_multiplier_value(word)
        if per_group is None:
            continue
        if any(fragment in word for fragment in ("литр", "комнат", "местн", "ярус", "тонн", "метр")):
            return {
                "groups": groups,
                "per_group": per_group,
                "start": match.start(),
                "end": match.end(),
                "kind": "compound",
            }
    return None


def _numbers_before_after(text_lower: str, start: int, end: int) -> Tuple[Optional[int], Optional[int]]:
    before_matches = [int(m.group()) for m in re.finditer(r"\d+", str(text_lower or "")) if m.start() < start]
    after_matches = [int(m.group()) for m in re.finditer(r"\d+", str(text_lower or "")) if m.start() >= end]
    before = before_matches[0] if before_matches else None
    after = after_matches[0] if after_matches else None
    return before, after


def _ascii_rule(width: int) -> str:
    return "-" * max(3, width)


def _render_column_addition_ascii(numbers: List[int]) -> List[str]:
    ordered = sorted(numbers, key=lambda x: (len(str(abs(x))), abs(x)), reverse=True)
    width = max(len(str(abs(n))) for n in ordered) + 1
    lines = ["Запись столбиком:"]
    for index, number in enumerate(ordered):
        sign = "+" if index > 0 else " "
        lines.append(f"{sign}{str(number).rjust(width - 1)}")
    lines.append(_ascii_rule(width))
    lines.append(f" {str(sum(ordered)).rjust(width - 1)}")
    return lines


def _render_column_subtraction_ascii(minuend: int, subtrahend: int) -> List[str]:
    width = max(len(str(abs(minuend))), len(str(abs(subtrahend)))) + 1
    result = minuend - subtrahend
    return [
        "Запись столбиком:",
        f" {str(minuend).rjust(width - 1)}",
        f"-{str(subtrahend).rjust(width - 1)}",
        _ascii_rule(width),
        f" {str(result).rjust(width - 1)}",
    ]


def _render_long_multiplication_ascii(left: int, right: int) -> List[str]:
    a, b = left, right
    if len(str(abs(a))) < len(str(abs(b))):
        a, b = b, a
    width = max(len(str(abs(a))), len(str(abs(b))) + 1, len(str(abs(a * b)))) + 1
    lines = ["Запись столбиком:", f" {str(a).rjust(width - 1)}", f"×{str(b).rjust(width - 1)}", _ascii_rule(width)]
    digits_b = list(reversed(str(abs(b))))
    partials = []
    for index, digit in enumerate(digits_b):
        if digit == "0":
            continue
        partials.append(a * int(digit) * (10 ** index))
    if len(partials) <= 1:
        lines.append(f" {str(a * b).rjust(width - 1)}")
        return lines
    for partial in partials:
        lines.append(f" {str(partial).rjust(width - 1)}")
    lines.append(_ascii_rule(width))
    lines.append(f" {str(a * b).rjust(width - 1)}")
    return lines


def _render_long_division_ascii(dividend: int, divisor: int) -> List[str]:
    if divisor == 0:
        return ["Запись столбиком:", "Деление на ноль невозможно"]
    quotient, remainder = divmod(dividend, divisor)
    lines = ["Запись столбиком:", f"{divisor}) {dividend}", f"Частное: {quotient}"]
    if remainder:
        lines.append(f"Остаток: {remainder}")
    return lines


def explain_column_addition(numbers: List[int]) -> str:
    base = _PATCH8_PREVIOUS_explain_column_addition(numbers)
    parts = _detailed_split_sections(base)
    lines = _render_column_addition_ascii(numbers) + parts["body"] + [
        f"Ответ: {parts['answer'] or sum(numbers)}",
        f"Совет: {parts['advice'] or 'в столбике всегда начинай с младшего разряда'}",
    ]
    return _detailed_finalize_text(lines)


def explain_column_subtraction(minuend: int, subtrahend: int) -> str:
    base = _PATCH8_PREVIOUS_explain_column_subtraction(minuend, subtrahend)
    parts = _detailed_split_sections(base)
    lines = _render_column_subtraction_ascii(minuend, subtrahend) + parts["body"] + [
        f"Ответ: {parts['answer'] or (minuend - subtrahend)}",
        f"Совет: {parts['advice'] or 'если разряда не хватает, занимаем 1 из соседнего старшего разряда'}",
    ]
    return _detailed_finalize_text(lines)


def explain_long_multiplication(left: int, right: int) -> str:
    base = _PATCH8_PREVIOUS_explain_long_multiplication(left, right)
    parts = _detailed_split_sections(base)
    lines = _render_long_multiplication_ascii(left, right) + parts["body"] + [
        f"Ответ: {parts['answer'] or (left * right)}",
        f"Совет: {parts['advice'] or 'в умножении столбиком сначала находят неполные произведения, потом их складывают'}",
    ]
    return _detailed_finalize_text(lines)


def explain_long_division(dividend: int, divisor: int) -> str:
    base = _PATCH8_PREVIOUS_explain_long_division(dividend, divisor)
    parts = _detailed_split_sections(base)
    answer_value = parts["answer"] or (f"{dividend // divisor}, остаток {dividend % divisor}" if divisor else "деление невозможно")
    lines = _render_long_division_ascii(dividend, divisor) + parts["body"] + [
        f"Ответ: {answer_value}",
        f"Совет: {parts['advice'] or 'в столбике повторяй шаги: взял, подобрал, умножил, вычел, снес цифру'}",
    ]
    return _detailed_finalize_text(lines)


def _is_ascii_math_layout_line(line: str) -> bool:
    stripped = str(line or "").rstrip()
    if not stripped:
        return False
    return bool(re.fullmatch(r"[ 0-9+\-×:=()/]+", stripped))


def _split_ascii_layout_block(body_lines: List[str]) -> Tuple[List[str], List[str]]:
    lines = [str(line or "") for line in body_lines]
    if not lines or not lines[0].lower().startswith("запись столбиком"):
        return [], lines
    block = [lines[0]]
    index = 1
    while index < len(lines) and _is_ascii_math_layout_line(lines[index]):
        block.append(lines[index])
        index += 1
    return block, lines[index:]


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")
    node = parse_expression_ast(source)
    pretty_expression = render_node(node) if node is not None else _detailed_compact_expression(source)
    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("что известно:", "что нужно найти:"))]
    column_block, remaining_body = _split_ascii_layout_block(body_lines)
    if not remaining_body and not column_block:
        remaining_body = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]
    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block and not column_block:
        lines.extend(order_block)
        lines.append("Решение по действиям:")
    else:
        lines.append("Решение.")
    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_word_like_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    info_lines: List[str] = []
    body_lines: List[str] = []
    for line in parts["body"]:
        lower = line.lower()
        if lower.startswith("что известно:") or lower.startswith("что нужно найти:"):
            info_lines.append(line)
        else:
            body_lines.append(line)
    if not info_lines:
        condition, question = extract_condition_and_question(raw_text)
        if condition:
            info_lines.append(f"Что известно: {condition}")
        if question:
            info_lines.append(f"Что нужно найти: {question}")
    column_block, remaining_body = _split_ascii_layout_block(body_lines)
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines: List[str] = []
    if statement:
        lines.append("Задача.")
        lines.append(statement)
    lines.append("Решение.")
    lines.extend(info_lines)
    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind if kind in DEFAULT_ADVICE else "other")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    column_block, remaining_body = _split_ascii_layout_block(parts["body"])
    lines: List[str] = []
    if statement and kind in {"word", "geometry"}:
        lines.append("Задача.")
        lines.append(statement)
        lines.append("Решение.")
    else:
        lines.append("Решение.")
    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    if parts["check"]:
        lines.append(parts["check"])
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind)
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:сколько|какова|какое расстояние|какой путь|чему равно расстояние)[^?.!]{0,25}(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:миллиметр|мм)", question):
        return "мм"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:сколько|какова|какое|чему равна?)[^?.!]{0,25}(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}"
    return value


def try_priority_fraction_by_given_part_explanation(raw_text: str) -> Optional[str]:
    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if len(fracs) != 1 or not values:
        return None
    numerator, denominator = fracs[0]
    if denominator == 0:
        return None
    if "составляет" in lower or re.search(rf"это\s+{numerator}\s*/\s*{denominator}\s+(?:всего\s+)?", lower):
        value_match = re.search(r"(?:составляет|равна|равен)[^\d]{0,20}(\d+)", lower)
        part_value = int(value_match.group(1)) if value_match else max(values)
        return explain_number_by_fraction_word_problem(part_value, numerator, denominator)
    return None


def try_high_priority_fraction_word_problem_explanation(raw_text: str) -> Optional[str]:
    explicit = try_priority_fraction_by_given_part_explanation(raw_text)
    if explicit:
        return explicit

    text, lower, fracs, values = _fraction_numbers_and_text(raw_text)
    if not fracs:
        return None

    unit = _detect_question_unit(raw_text)

    if len(fracs) >= 2 and ("остал" in lower or "сколько" in lower) and values:
        total = max(values)
        solved = explain_two_fraction_parts_remaining(total, fracs[0], fracs[1])
        if solved:
            return solved

    if len(fracs) != 1:
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None

    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
    explicit_total_match = re.search(r"(?:\bбыло\b|\bвсего\b|\bмасса\b|\bдлина\b|\bпуть\b|\bпрошли\b|\bпрошел\b|\bпрошла\b|\bлистов\b|\bруды\b)[^\d]{0,40}(\d+)", lower)

    if remain_match and (not explicit_total_match or explicit_total_match.start() > remain_match.start()):
        remaining_value = int(remain_match.group(1))
        remaining_numerator = denominator - numerator
        if remaining_numerator <= 0 or remaining_value % remaining_numerator != 0:
            return None
        one_part = remaining_value // remaining_numerator
        whole = one_part * denominator
        remaining_text = f"{remaining_value} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        whole_text = f"{whole} {unit}".strip()
        return join_explanation_lines(
            f"1) Если израсходовали {numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
            f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_text}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part_text}",
            f"3) Если одна доля равна {one_part_text}, то все деньги равны {one_part} × {denominator} = {whole_text}",
            f"Ответ: всего было {whole_text}",
            "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
        )

    if values:
        total = max(values)
        if total % denominator != 0:
            return None
        one_part = total // denominator
        part = one_part * numerator
        remaining = total - part
        total_text = f"{total} {unit}".strip()
        one_part_text = f"{one_part} {unit}".strip()
        part_text = f"{part} {unit}".strip()
        remaining_text = f"{remaining} {unit}".strip()

        if "во 2 день" in lower or "во второй день" in lower:
            return join_explanation_lines(
                f"1) Если весь путь равен {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если в первый день прошли {numerator}/{denominator} пути, то в первый день прошли {one_part} × {numerator} = {part_text}",
                f"3) Если весь путь {total_text}, а в первый день прошли {part_text}, то во второй день прошли {total} - {part} = {remaining_text}",
                f"Ответ: во второй день прошли {remaining_text}",
                "Совет: чтобы найти другую часть пути, сначала найди известную часть, потом вычти её из всего пути",
            )

        if "остал" in lower:
            return join_explanation_lines(
                f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
                f"2) Если требуется найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
                f"3) Если всего было {total_text}, а израсходовали {part_text}, то осталось {total} - {part} = {remaining_text}",
                f"Ответ: осталось {remaining_text}",
                "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
            )

        return join_explanation_lines(
            f"1) Если всё число равно {total_text}, то одна доля равна {total} : {denominator} = {one_part_text}",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {part_text}",
            f"Ответ: {part_text}",
            "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
        )
    return None


def try_priority_relation_then_compare_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_text_only(raw_text).lower().replace("ё", "е") or lower
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None

    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)

    if len(relation_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        base = nums[0]
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        if "во сколько" in question:
            bigger, smaller = max(base, related), min(base, related)
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "+" if mode == "больше" else "-"
            return join_explanation_lines(
                f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = abs(related - base)
        op = "+" if mode == "больше" else "-"
        return join_explanation_lines(
            f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {max(base, related)}, а другое равно {min(base, related)}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
            f"Ответ: {diff}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        base = nums[0]
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        if "во сколько" in question:
            bigger, smaller = max(base, related), min(base, related)
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "×" if mode == "больше" else ":"
            return join_explanation_lines(
                f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = abs(related - base)
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {max(base, related)}, а другое равно {min(base, related)}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
            f"Ответ: {diff}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )
    return None


def try_priority_group_change_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_text_only(raw_text).lower().replace("ё", "е") or lower

    if len(re.findall(r"\bпо\s+\d+", lower)) > 1:
        return None

    pair = _find_group_pair_any(lower)
    if not pair:
        return None
    groups = pair["groups"]
    per_group = pair["per_group"]
    pair_total = groups * per_group
    before_number, after_number = _numbers_before_after(lower, pair["start"], pair["end"])

    if ("стало" in question or asks_total_like(question)) and contains_any_fragment(lower, WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")):
        extra = after_number
        if extra is not None:
            result = pair_total + extra
            return join_explanation_lines(
                f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {per_group} × {groups} = {pair_total}",
                f"2) Если было {pair_total}, а потом добавили ещё {extra}, то стало {pair_total} + {extra} = {result}",
                f"Ответ: {result}",
                "Совет: если сначала находят одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
            )

    if "осталось" in question or "осталось расфасовать" in question or "осталось проехать" in question:
        if before_number is not None and before_number >= pair_total:
            result = before_number - pair_total
            return join_explanation_lines(
                f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
                f"2) Если всего было {before_number}, а одна часть равна {pair_total}, то другая часть равна {before_number} - {pair_total} = {result}",
                f"Ответ: {result}",
                "Совет: в составной задаче сначала найди часть, а потом вычти её из целого",
            )
        if after_number is not None and pair_total >= after_number:
            result = pair_total - after_number
            return join_explanation_lines(
                f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {pair_total}",
                f"2) Если было {pair_total}, а убрали {after_number}, то осталось {pair_total} - {after_number} = {result}",
                f"Ответ: {result}",
                "Совет: если сначала находят одинаковые группы, а потом часть убирают, сначала выполняют умножение",
            )

    if re.search(r"сколько[^.?!]*(?:привезли|было)\b", question):
        remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
        remain = int(remain_match.group(1)) if remain_match else after_number
        if remain is not None:
            result = pair_total + remain
            return join_explanation_lines(
                f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
                f"2) Если одна часть равна {pair_total}, а другая часть равна {remain}, то всего было {pair_total} + {remain} = {result}",
                f"Ответ: {result}",
                "Совет: если известны израсходованная часть и остаток, то всё число находят сложением",
            )

    if re.search(r"сколько[^.?!]*(?:отремонтировали|продали|расфасовали)\b", question) and before_number is not None and before_number >= pair_total:
        result = before_number - pair_total
        return join_explanation_lines(
            f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
            f"2) Если всего было {before_number}, а эта часть равна {pair_total}, то другая часть равна {before_number} - {pair_total} = {result}",
            f"Ответ: {result}",
            "Совет: если известно всё число и одна часть, другую часть находят вычитанием",
        )

    return None


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if "сколько" not in lower:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS + ("остал", "расфас", "продал", "подарил", "добавил", "вошло", "приехало")):
        return None
    if _has_group_count_question(lower) or "поровну" in lower or "кажд" in lower:
        return None
    pair = _find_group_pair_any(lower)
    if not pair:
        return None
    if not (asks_total_like(lower) or contains_any_fragment(lower, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько огурцов", "сколько конфет"))):
        return None
    groups = pair["groups"]
    per_group = pair["per_group"]
    total = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {total}",
        f"Ответ: {total}",
        "Совет: слова «по ... в каждой» или составные слова вроде «двухлитровых» подсказывают умножение",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_priority_fraction_by_given_part_explanation(user_text)
        or try_priority_relation_then_compare_explanation(user_text)
        or try_priority_group_change_word_problem_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_unknown_price_word_problem_explanation(user_text)
        or try_high_priority_total_cost_word_problem_explanation(user_text)
        or try_high_priority_fraction_word_problem_explanation(user_text)
        or try_high_priority_unknown_addend_word_problem_explanation(user_text)
        or try_high_priority_added_removed_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PATCH8_PREVIOUS_build_explanation_local_first(user_text, kind)
    )


# --- OPENAI FINAL PATCH 2026-04-10B: remaining/added routing order, unit tolerance, heading colons ---


def _detailed_finalize_line(line: str) -> str:
    raw = str(line or "").rstrip()
    if not raw:
        return ""
    stripped = raw.strip()
    if not stripped:
        return ""
    if re.fullmatch(r"[ 0-9()+\-×:=/]+", raw):
        return raw
    if stripped.endswith(":"):
        return stripped
    if re.match(r"^(?:Пример|Порядок действий|Решение по действиям|Решение|Задача|Уравнение|Запись столбиком|Пояснение)\b", stripped, flags=re.IGNORECASE):
        return stripped
    if stripped[-1] not in ".!?":
        stripped += "."
    return stripped


def _detect_question_unit(raw_text: str) -> str:
    question = _question_text_only(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    # Сначала более длинные и более специфичные единицы.
    if "мм" in question or "миллиметр" in question:
        return "мм"
    if "см²" in question or "кв. см" in question or ("площад" in question and ("см" in question or "сантиметр" in question)):
        return "см²"
    if "дм²" in question or "кв. дм" in question or ("площад" in question and ("дм" in question or "дециметр" in question)):
        return "дм²"
    if "м²" in question or "кв. м" in question or ("площад" in question and ("м " in question or question.endswith(" м") or "метр" in question)):
        return "м²"
    if re.search(r"(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def try_priority_group_change_word_problem_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_text_only(raw_text).lower().replace("ё", "е") or lower

    if len(re.findall(r"\bпо\s+\d+", lower)) > 1:
        return None

    pair = _find_group_pair_any(lower)
    if not pair:
        return None
    groups = pair["groups"]
    per_group = pair["per_group"]
    pair_total = groups * per_group
    before_number, after_number = _numbers_before_after(lower, pair["start"], pair["end"])

    # 1. Если известен общий объём и одна часть вида n × k, находим другую часть.
    if ("осталось" in question or "осталось расфасовать" in question or "осталось проехать" in question or re.search(r"сколько[^.?!]*(?:отремонтировали|продали|расфасовали)\b", question)) and before_number is not None and before_number >= pair_total:
        result = before_number - pair_total
        return join_explanation_lines(
            f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
            f"2) Если всего было {before_number}, а эта часть равна {pair_total}, то другая часть равна {before_number} - {pair_total} = {result}",
            f"Ответ: {result}",
            "Совет: если известно всё число и одна часть, другую часть находят вычитанием",
        )

    # 2. Если сначала есть группы, а потом часть убрали, находим остаток.
    if ("осталось" in question or "осталось в магазине" in question) and after_number is not None and pair_total >= after_number:
        result = pair_total - after_number
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {pair_total}",
            f"2) Если было {pair_total}, а убрали {after_number}, то осталось {pair_total} - {after_number} = {result}",
            f"Ответ: {result}",
            "Совет: если сначала находят одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    # 3. Если известны израсходованная часть и остаток, находим всё число.
    if re.search(r"сколько[^.?!]*(?:привезли|было)\b", question):
        remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)", lower)
        remain = int(remain_match.group(1)) if remain_match else after_number
        if remain is not None:
            result = pair_total + remain
            return join_explanation_lines(
                f"1) Если {groups} групп по {per_group} в каждой, то эта часть равна {groups} × {per_group} = {pair_total}",
                f"2) Если одна часть равна {pair_total}, а другая часть равна {remain}, то всего было {pair_total} + {remain} = {result}",
                f"Ответ: {result}",
                "Совет: если известны израсходованная часть и остаток, то всё число находят сложением",
            )

    # 4. Если сначала есть группы, а потом что-то добавили, находим итог.
    if ("стало" in question or "всего" in question) and contains_any_fragment(lower, WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")):
        extra = after_number
        if extra is not None:
            result = pair_total + extra
            return join_explanation_lines(
                f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {per_group} × {groups} = {pair_total}",
                f"2) Если было {pair_total}, а потом добавили ещё {extra}, то стало {pair_total} + {extra} = {result}",
                f"Ответ: {result}",
                "Совет: если сначала находят одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
            )

    return None


# --- OPENAI FINAL PATCH 2026-04-10C: protect subtraction/division layout lines from sanitizer ---


def _render_column_subtraction_ascii(minuend: int, subtrahend: int) -> List[str]:
    width = max(len(str(abs(minuend))), len(str(abs(subtrahend)))) + 1
    result = minuend - subtrahend
    return [
        "Запись столбиком:",
        f" {str(minuend).rjust(width - 1)}",
        f"–{str(subtrahend).rjust(width - 1)}",
        _ascii_rule(width),
        f" {str(result).rjust(width - 1)}",
    ]


def _render_long_division_ascii(dividend: int, divisor: int) -> List[str]:
    if divisor == 0:
        return ["Запись столбиком:", "Деление на ноль невозможно"]
    quotient, remainder = divmod(dividend, divisor)
    lines = ["Запись столбиком:", f"{divisor} | {dividend}", f"Частное: {quotient}"]
    if remainder:
        lines.append(f"Остаток: {remainder}")
    return lines


def _is_ascii_math_layout_line(line: str) -> bool:
    stripped = str(line or "").rstrip()
    if not stripped:
        return False
    return bool(re.fullmatch(r"[ 0-9+\-–×:=/|()]+", stripped))


def _detailed_finalize_line(line: str) -> str:
    raw = str(line or "").rstrip()
    if not raw:
        return ""
    stripped = raw.strip()
    if not stripped:
        return ""
    if re.fullmatch(r"[ 0-9()+\-–×:=/|]+", raw):
        return raw
    if stripped.endswith(":"):
        return stripped
    if re.match(r"^(?:Пример|Порядок действий|Решение по действиям|Решение|Задача|Уравнение|Запись столбиком|Пояснение)\b", stripped, flags=re.IGNORECASE):
        return stripped
    if stripped[-1] not in ".!?":
        stripped += "."
    return stripped


# --- OPENAI CONSOLIDATION PATCH 2026-04-11: routing fixes, richer school templates, safer high-priority handlers ---

_PREV_20260411_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _question_lower_text(raw_text: str) -> str:
    try:
        return _question_text_only(raw_text).lower().replace("ё", "е")
    except Exception:
        return normalize_word_problem_text(raw_text).lower().replace("ё", "е")


def _statement_lower_text(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text).lower().replace("ё", "е")


def _po_product_matches(raw_text: str) -> List[dict]:
    lower = _statement_lower_text(raw_text)
    matches = []
    pattern = re.compile(r"(\d+)\s+([^?.!,]{1,40}?)\s+по\s+(\d+)\s*([а-яёa-z/²\.]+)?", re.IGNORECASE)
    for match in pattern.finditer(lower):
        count = int(match.group(1))
        name = re.sub(r"\s+", " ", match.group(2).strip())
        value = int(match.group(3))
        unit = (match.group(4) or "").strip().rstrip(".,")
        matches.append({"count": count, "name": name, "value": value, "unit": unit})
    return matches


def _answer_number_with_unit(value: int, raw_text: str, fallback_unit: str = "") -> str:
    unit = ""
    try:
        unit = _detect_question_unit(raw_text) or ""
    except Exception:
        unit = ""
    if not unit:
        unit = (fallback_unit or "").strip().rstrip(".")
    return f"{value} {unit}".strip()


def try_priority_simple_two_part_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} " or "поровну" in lower or "кажд" in lower:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS + ("остал", "стало", "теперь", "отдали", "вышло", "вошло", "приехало")):
        return None
    if not (_has_total_like_question(raw_text) or contains_any_fragment(question, ("сколько всего", "сколько вместе", "на обеих", "на обоих", "на двух"))):
        return None

    first, second = nums
    total = first + second
    answer_text = _answer_number_with_unit(total, raw_text)
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе количество равно {second}, то всего {first} + {second} = {total}",
        f"Ответ: {answer_text}",
        "Совет: если спрашивают, сколько всего или сколько вместе, обычно нужно сложение",
    )


def try_priority_relation_then_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2 or "сколько" not in lower:
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    if len(relation_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if "во сколько" in question:
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "+" if mode == "больше" else "-"
            return join_explanation_lines(
                f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        answer_text = _answer_number_with_unit(diff, raw_text)
        return join_explanation_lines(
            f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {answer_text}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )

    scale_pairs = extract_scale_pairs(lower)
    if len(scale_pairs) == 1 and ("во сколько" in question or "на сколько" in question):
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if "во сколько" in question:
            if smaller == 0 or bigger % smaller != 0:
                return None
            result = bigger // smaller
            op = "×" if mode == "больше" else ":"
            return join_explanation_lines(
                f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
                f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
                f"Ответ: {result} {plural_form(result, 'раз', 'раза', 'раз')}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )
        diff = bigger - smaller
        op = "×" if mode == "больше" else ":"
        answer_text = _answer_number_with_unit(diff, raw_text)
        return join_explanation_lines(
            f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {answer_text}",
            "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
        )
    return None


def try_high_priority_named_sum_of_two_products_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None

    # Не перехватываем случаи, где спрашивают цену одной штуки и общая стоимость уже дана.
    if contains_any_fragment(question, ("сколько стоила 1", "сколько стоит 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total

    money_question = contains_any_fragment(lower, ("заплат", "стоим")) or contains_any_fragment(question, ("сколько денег", "сколько заплатили", "сколько стоила"))
    answer_unit = ""
    if money_question:
        answer_unit = "руб"
        return join_explanation_lines(
            f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то первая часть равна {first['count']} × {first['value']} = {first_total} руб",
            f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то вторая часть равна {second['count']} × {second['value']} = {second_total} руб",
            f"3) Если первая часть равна {first_total} руб., а вторая часть равна {second_total} руб., то всего {first_total} + {second_total} = {total} руб",
            f"Ответ: за всю покупку заплатили {total} руб",
            "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
        )

    # Общий случай: сумма двух произведений по массе/количеству/литрам и т. п.
    unit = _detect_question_unit(raw_text) or first["unit"] or second["unit"]
    answer_text = _answer_number_with_unit(total, raw_text, unit)
    unit_tail = f" {unit}".rstrip() if unit else ""
    return join_explanation_lines(
        f"1) Если было {first['count']} {first['name']} по {first['value']}{unit_tail}, то первая часть равна {first['count']} × {first['value']} = {first_total}{unit_tail}",
        f"2) Если было {second['count']} {second['name']} по {second['value']}{unit_tail}, то вторая часть равна {second['count']} × {second['value']} = {second_total}{unit_tail}",
        f"3) Если первая часть равна {first_total}{unit_tail}, а вторая часть равна {second_total}{unit_tail}, то всего {first_total} + {second_total} = {total}{unit_tail}",
        f"Ответ: {answer_text}",
        "Совет: если в задаче есть две группы вида «по столько-то», сначала находят каждую группу отдельно, потом складывают",
    )


def try_high_priority_simple_group_total_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS + ("остал", "расфас", "продал", "подарил", "добавил", "вошло", "приехало")):
        return None
    if _has_group_count_question(lower) or "поровну" in lower or "кажд" in lower:
        return None

    products = _po_product_matches(raw_text)
    if len(products) != 1:
        return None
    if not (_has_total_like_question(raw_text) or contains_any_fragment(question, ("сколько килограммов", "сколько книг", "сколько карандашей", "сколько литров", "сколько всего"))):
        return None

    product = products[0]
    total = product["count"] * product["value"]
    unit = _detect_question_unit(raw_text) or product["unit"]
    answer_text = _answer_number_with_unit(total, raw_text, unit)
    unit_tail = f" {unit}".rstrip() if unit else ""
    return join_explanation_lines(
        f"1) Если есть {product['count']} одинаковых групп по {product['value']}{unit_tail} в каждой, то всего {product['count']} × {product['value']} = {total}{unit_tail}",
        f"Ответ: {answer_text}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or "сколько" not in lower:
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    # Тип 1: "В 3 пачках 12 фломастеров. Сколько фломастеров в 2 пачках?"
    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    # Тип 2: "В 2 вёдрах 16 кг. В скольких вёдрах 24 кг?"
    if "в скольких" in question or _has_group_count_question(question):
        solved = explain_unit_rate_boxes_problem(first_groups, total_amount, target_value)
        if solved:
            return solved
    return None


def try_priority_unit_rate_compare_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2:
        return None

    match = re.search(r"за\s+(\d+)\s+дн", lower)
    if match and "чем за один" in question and "на сколько" in question:
        days = int(match.group(1))
        total_amount = nums[1] if len(nums) >= 2 else None
        if total_amount is None or days == 0 or total_amount % days != 0:
            return None
        one_day = total_amount // days
        diff = total_amount - one_day
        answer_text = _answer_number_with_unit(diff, raw_text)
        total_text = _answer_number_with_unit(total_amount, raw_text)
        one_day_text = _answer_number_with_unit(one_day, raw_text)
        return join_explanation_lines(
            f"1) Если за {days} дней расходуется {total_text}, то за один день расходуется {total_amount} : {days} = {one_day_text}",
            f"2) Если за {days} дней расходуется {total_text}, а за один день {one_day_text}, то разность равна {total_amount} - {one_day} = {answer_text}",
            f"Ответ: {answer_text}",
            "Совет: в такой задаче сначала находят одну одинаковую часть, потом сравнивают",
        )
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_priority_relation_then_compare_explanation(user_text)
        or try_priority_simple_two_part_total_word_problem_explanation(user_text)
        or try_priority_bring_to_unit_word_problem_explanation(user_text)
        or try_priority_unit_rate_compare_word_problem_explanation(user_text)
        or try_high_priority_named_sum_of_two_products_word_problem_explanation(user_text)
        or try_high_priority_simple_group_total_word_problem_explanation(user_text)
        or _PREV_20260411_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )



# --- OPENAI HOTFIX 2026-04-11A: relation pairs with measurement words ---

def extract_relation_pairs(text: str):
    pairs = []
    pattern = re.compile(r"на\s+(\d+)(?:\s+[а-яёa-z]+)?\s+(больше|меньше)", re.IGNORECASE)
    for match in pattern.finditer(str(text or "").lower().replace("ё", "е")):
        pairs.append((int(match.group(1)), match.group(2)))
    return pairs



# --- OPENAI HOTFIX 2026-04-11B: "скольких" in bring-to-unit tasks ---

def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or not ("сколько" in lower or "скольких" in lower):
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    if "в скольких" in question or "скольких" in question or _has_group_count_question(question):
        solved = explain_unit_rate_boxes_problem(first_groups, total_amount, target_value)
        if solved:
            return solved
    return None



# --- OPENAI HOTFIX 2026-04-11C: correct answer noun for "в скольких ..." tasks ---

def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or not ("сколько" in lower or "скольких" in lower):
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    if "в скольких" in question or "скольких" in question or _has_group_count_question(question):
        if first_groups == 0 or total_amount % first_groups != 0:
            return None
        per_group = total_amount // first_groups
        if per_group == 0 or target_value % per_group != 0:
            return None
        result = target_value // per_group
        noun_match = re.search(r"в\s+скольких\s+([а-яё]+)", question)
        noun = noun_match.group(1) if noun_match else ""
        noun = noun.strip().rstrip("?.!,")
        answer_tail = f" {noun}" if noun else ""
        return join_explanation_lines(
            f"1) Если в {first_groups} группах {total_amount}, то в одной группе {total_amount} : {first_groups} = {per_group}",
            f"2) Если в одной группе {per_group}, то {target_value} : {per_group} = {result}",
            f"Ответ: {result}{answer_tail}",
            "Совет: в задачах на приведение к единице сначала находят значение одной группы",
        )
    return None



# --- OPENAI HOTFIX 2026-04-11D: no metric unit for "в скольких" questions ---

def _detect_question_unit(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    lower_full = _statement_lower_text(raw_text)

    if "в скольких" in question:
        return ""

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if "мм" in question or "миллиметр" in question:
        return "мм"
    if "см²" in question or "кв. см" in question or ("площад" in question and ("см" in question or "сантиметр" in question)):
        return "см²"
    if "дм²" in question or "кв. дм" in question or ("площад" in question and ("дм" in question or "дециметр" in question)):
        return "дм²"
    if "м²" in question or "кв. м" in question or ("площад" in question and ("м " in question or question.endswith(" м") or "метр" in question)):
        return "м²"
    if re.search(r"(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def try_priority_bring_to_unit_word_problem_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or not ("сколько" in lower or "скольких" in lower):
        return None
    if extract_relation_pairs(lower) or extract_scale_pairs(lower):
        return None
    if " по " in f" {lower} ":
        return None

    first_groups = nums[0]
    total_amount = nums[1]
    target_value = nums[2]

    if "таких же" in lower or re.search(r"(?:сколько[^.?!]*\bв\s+\d+\s+[а-яё]+\b)", question):
        solved = explain_bring_to_unit_total_word_problem(first_groups, total_amount, target_value)
        if solved:
            return solved

    if "в скольких" in question or "скольких" in question or _has_group_count_question(question):
        if first_groups == 0 or total_amount % first_groups != 0:
            return None
        per_group = total_amount // first_groups
        if per_group == 0 or target_value % per_group != 0:
            return None
        result = target_value // per_group
        return join_explanation_lines(
            f"1) Если в {first_groups} группах {total_amount}, то в одной группе {total_amount} : {first_groups} = {per_group}",
            f"2) Если в одной группе {per_group}, то {target_value} : {per_group} = {result}",
            f"Ответ: {result}",
            "Совет: в задачах на приведение к единице сначала находят значение одной группы",
        )
    return None



# --- OPENAI FINAL PATCH 2026-04-11E: cleaner expression formatting, fuller answers, stronger oral methods ---

_PREV_FINAL_PATCH_explain_simple_addition = explain_simple_addition
_PREV_FINAL_PATCH_explain_simple_subtraction = explain_simple_subtraction
_PREV_FINAL_PATCH_explain_simple_multiplication = explain_simple_multiplication


def _schoolify_expression_source(source: str) -> str:
    text = str(source or "").strip()
    if not text:
        return ""
    out = []
    for i, ch in enumerate(text):
        prev = text[i - 1] if i > 0 else ""
        if ch in "*/+":
            symbol = "×" if ch == "*" else ":" if ch == "/" else ch
            out.append(f" {symbol} ")
        elif ch == "-":
            if i == 0 or prev in "(+-*/":
                out.append("-")
            else:
                out.append(" - ")
        else:
            out.append(ch)
    pretty = re.sub(r"\s+", " ", "".join(out)).strip()
    pretty = pretty.replace("( ", "(").replace(" )", ")")
    return pretty


def _build_pretty_expression_and_operator_map(source: str) -> Tuple[str, dict]:
    raw = str(source or "")
    pretty_parts: List[str] = []
    raw_to_pretty: dict = {}
    current_len = 0
    for i, ch in enumerate(raw):
        prev = raw[i - 1] if i > 0 else ""
        if ch in "*/+":
            token = f" {'×' if ch == '*' else ':' if ch == '/' else ch} "
            raw_to_pretty[i] = current_len + 1
            pretty_parts.append(token)
            current_len += len(token)
        elif ch == "-" and not (i == 0 or prev in "(+-*/"):
            token = " - "
            raw_to_pretty[i] = current_len + 1
            pretty_parts.append(token)
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    pretty = re.sub(r"\s+", " ", "".join(pretty_parts)).strip()
    pretty = pretty.replace("( ", "(").replace(" )", ")")
    # after whitespace normalization, rebuild exact operator positions in pretty string
    rebuilt_map: dict = {}
    pi = 0
    ri = 0
    raw_no_space = raw
    while ri < len(raw_no_space) and pi < len(pretty):
        rc = raw_no_space[ri]
        pc = pretty[pi]
        if rc in "*/+" or (rc == "-" and not (ri == 0 or raw_no_space[ri - 1] in "(+-*/")):
            symbol = '×' if rc == '*' else ':' if rc == '/' else rc
            # move to symbol in pretty
            while pi < len(pretty) and pretty[pi] != symbol:
                pi += 1
            if pi < len(pretty):
                rebuilt_map[ri] = pi
                pi += 1
            ri += 1
            continue
        if rc == pc:
            ri += 1
            pi += 1
        else:
            pi += 1
    return pretty, rebuilt_map


# override: preserve parentheses in the first line of expressions and in the order block

def _detailed_build_order_block(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return []

    pretty_expr, raw_to_pretty = _build_pretty_expression_and_operator_map(source)
    marks = [" "] * len(pretty_expr)

    for step_index, step in enumerate(steps, start=1):
        raw_pos = step.get("pos")
        if raw_pos is None or raw_pos not in raw_to_pretty:
            continue
        pretty_pos = raw_to_pretty[raw_pos]
        label = str(step_index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, char in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = char

    return ["Порядок действий:", "".join(marks).rstrip(), pretty_expr]


def _extract_question_noun(raw_text: str) -> str:
    try:
        _, question = extract_condition_and_question(raw_text)
    except Exception:
        question = str(raw_text or "")
    q = question.strip().rstrip("?.!").replace("ё", "е")
    if not q:
        return ""
    ql = q.lower()
    if "во сколько раз" in ql:
        return "раз"
    # Сколько книг..., Сколько было клеток..., Сколько осталось страниц...
    match = re.search(
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|понадобится\s+|потребовалось\s+|можно\s+купить\s+)?([а-яё]+)",
        ql,
    )
    if match:
        noun = match.group(1).strip()
        if noun not in {"всего", "вместе", "на", "во", "по", "также", "денег"}:
            return noun
    # Какова длина..., Какова ширина..., Какова площадь...
    match = re.search(r"^каков[ао]?\s+([а-яё]+)", ql)
    if match:
        return match.group(1).strip()
    return ""


# override: fuller numeric answers for text tasks

def _detect_question_unit(raw_text: str) -> str:
    try:
        question = _question_lower_text(raw_text)
    except Exception:
        question = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if "в скольких" in question:
        return ""
    if "во сколько раз" in question:
        return "раз"

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        if "км/ч" in lower_full:
            return "км/ч"
        if "м/мин" in lower_full:
            return "м/мин"
        if "м/с" in lower_full:
            return "м/с"

    if "мм" in question or "миллиметр" in question:
        return "мм"
    if "см²" in question or "кв. см" in question or ("площад" in question and ("см" in question or "сантиметр" in question)):
        return "см²"
    if "дм²" in question or "кв. дм" in question or ("площад" in question and ("дм" in question or "дециметр" in question)):
        return "дм²"
    if "м²" in question or "кв. м" in question or ("площад" in question and ("метр" in question or re.search(r"\bм\b", question))):
        return "м²"
    if re.search(r"(?:руб|рубл|денег)", question):
        return "руб"
    if re.search(r"(?:килограмм|кг)", question):
        return "кг"
    if re.search(r"(?:(?<!кило)грамм|\bг\b)", question):
        return "г"
    if re.search(r"(?:километр|км)", question):
        return "км"
    if re.search(r"(?:сантиметр|см)", question):
        return "см"
    if re.search(r"(?:дециметр|дм)", question):
        return "дм"
    if re.search(r"(?:метр|\bм\b)", question):
        return "м"
    if re.search(r"(?:литр|\bл\b)", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}".strip()
        noun = _extract_question_noun(raw_text)
        if noun:
            return f"{value} {noun}".strip()
    return value


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")

    pretty_expression = _schoolify_expression_source(source)
    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("что известно:", "что нужно найти:"))]
    column_block, remaining_body = _split_ascii_layout_block(body_lines)
    if not remaining_body and not column_block:
        remaining_body = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block and not column_block:
        lines.extend(order_block)
        lines.append("Решение по действиям:")
    else:
        lines.append("Решение.")

    if column_block:
        lines.extend(column_block)
        if remaining_body:
            lines.append("Пояснение:")
    lines.extend(_detailed_number_lines(remaining_body))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


# stronger mental methods for crossing a ten

def explain_simple_addition(left: int, right: int) -> str:
    total = left + right

    if 0 <= left < 10 and 0 <= right < 10 and total > 10:
        return explain_addition_via_ten(left, right)

    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and 1 <= small <= 9 and (big % 10) + small >= 10 and big % 10 != 0:
        to_next_ten = 10 - (big % 10)
        rest = small - to_next_ten
        next_ten_value = big + to_next_ten
        return join_explanation_lines(
            "Ищем сумму",
            f"Чтобы получить следующий десяток, к {big} нужно прибавить {to_next_ten}",
            f"Разложим {small} на {to_next_ten} и {rest}",
            f"{big} + {to_next_ten} = {next_ten_value}",
            f"{next_ten_value} + {rest} = {total}",
            f"Ответ: {total}",
            "Совет: при сложении через десяток удобно сначала дойти до круглого десятка",
        )

    return _PREV_FINAL_PATCH_explain_simple_addition(left, right)


def explain_simple_subtraction(left: int, right: int) -> str:
    if left >= 20 and left % 10 == 0 and 0 < right < 10:
        first_part = left - 10
        second_part = 10 - right
        result = left - right
        return join_explanation_lines(
            "Ищем разность",
            f"Представим {left} как {first_part} + 10",
            f"Сначала вычтем {right} из 10: 10 - {right} = {second_part}",
            f"Потом прибавим оставшиеся десятки: {first_part} + {second_part} = {result}",
            f"Ответ: {result}",
            "Совет: из круглого десятка удобно вычитать через 10",
        )
    return _PREV_FINAL_PATCH_explain_simple_subtraction(left, right)


def explain_simple_multiplication(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and big % 10 == 0 and 1 <= small <= 9:
        tens = big // 10
        result = big * small
        return join_explanation_lines(
            "Ищем произведение",
            f"Число {big} — это {tens} десятков",
            f"Умножаем десятки: {tens} × {small} = {tens * small} десятков",
            f"{tens * small} десятков = {result}",
            f"Ответ: {result}",
            "Совет: круглое число удобно воспринимать как десятки",
        )
    return _PREV_FINAL_PATCH_explain_simple_multiplication(left, right)


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 1800,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- OPENAI FINAL PATCH 2026-04-11F: safer noun enrichment and better tens wording ---

def _can_use_raw_plural_noun_with_count(count_value: int) -> bool:
    value = abs(int(count_value)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return True
    return tail == 0 or tail >= 5


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value):
        unit = _detect_question_unit(raw_text)
        if unit:
            return f"{value} {unit}".strip()
        noun = _extract_question_noun(raw_text)
        if noun:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                count_value = None
            if noun == "раз":
                return f"{value} раз"
            if count_value is not None and _can_use_raw_plural_noun_with_count(count_value):
                return f"{value} {noun}".strip()
    return value


def explain_simple_multiplication(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and big % 10 == 0 and 1 <= small <= 9:
        tens = big // 10
        tens_word = plural_form(tens, 'десяток', 'десятка', 'десятков')
        product_tens = tens * small
        product_tens_word = plural_form(product_tens, 'десяток', 'десятка', 'десятков')
        result = big * small
        return join_explanation_lines(
            "Ищем произведение",
            f"Число {big} — это {tens} {tens_word}",
            f"Умножаем десятки: {tens} × {small} = {product_tens} {product_tens_word}",
            f"{product_tens} {product_tens_word} = {result}",
            f"Ответ: {result}",
            "Совет: круглое число удобно воспринимать как десятки",
        )
    return _PREV_FINAL_PATCH_explain_simple_multiplication(left, right)


# --- FINAL PATCH 2026-04-11G: textbook fixes, fuller answers, better compound tasks ---

_PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже обязательно:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. По возможности используй школьную форму:
Если ..., то ...
6. Если сразу нельзя ответить на главный вопрос, сначала найди то, что нужно для ответа.
7. После каждого действия коротко говори, что нашли.
8. В конце:
Ответ: ...
Ответ лучше писать полной фразой, а не только числом.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
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


def _patch_answer_with_question_noun(value: int, raw_text: str) -> str:
    unit = _detect_question_unit(raw_text) or ""
    if unit:
        return f"{value} {unit}".strip()
    noun = _extract_question_noun(raw_text)
    if noun:
        try:
            count = int(value)
        except Exception:
            count = None
        if noun == "раз":
            return f"{value} раз"
        if count is not None and _can_use_raw_plural_noun_with_count(count):
            return f"{value} {noun}".strip()
    return str(value)



def _patch_number_phrase(raw_text: str, number: int, occurrence: int = 0) -> str:
    lower = _statement_lower_text(raw_text)
    matches = re.findall(rf"{number}\s+[а-яё]+", lower)
    if matches:
        return matches[min(occurrence, len(matches) - 1)]
    return str(number)



def _patch_singular_unit(word: str) -> str:
    value = str(word or "").strip().lower().replace("ё", "е").strip(".,;:!?")
    mapping = {
        "пакетов": "пакет",
        "пакета": "пакет",
        "коробок": "коробка",
        "коробки": "коробка",
        "наборов": "набор",
        "набора": "набор",
        "ящиков": "ящик",
        "ведер": "ведро",
        "вёдер": "ведро",
        "книг": "книга",
        "ручек": "ручка",
        "тетрадей": "тетрадь",
        "бутылок": "бутылка",
        "банок": "банка",
    }
    return mapping.get(value, value)



def _patch_pick_compare_names_from_question(raw_text: str) -> Tuple[str, str]:
    question = _question_lower_text(raw_text)
    match = re.search(r"на\s+сколько\s+(?:[а-яё]+\s+)?([а-яё]+)\s+(?:больше|меньше),?\s+чем\s+([а-яё]+)", question)
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"во\s+сколько\s+раз\s+(?:[а-яё]+\s+)?([а-яё]+)\s+(?:больше|меньше),?\s+чем\s+([а-яё]+)", question)
    if match:
        return match.group(1), match.group(2)
    return "", ""



def try_patch_unknown_minuend_simple_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in question:
        return None
    if not ("было" in question or "сначала" in question):
        return None
    if "остал" not in lower:
        return None
    if not contains_any_fragment(lower, WORD_LOSS_HINTS + ("сняли", "взяли", "убрали", "забрали", "отдали", "продали")):
        return None

    removed, remaining = nums[0], nums[1]
    total = removed + remaining
    removed_phrase = _patch_number_phrase(raw_text, removed, 0)
    remaining_phrase = _patch_number_phrase(raw_text, remaining, 0)
    answer = _patch_answer_with_question_noun(total, raw_text)
    return join_explanation_lines(
        f"1) Если сняли {removed_phrase} и осталось {remaining_phrase}, то сначала было {removed} + {remaining} = {answer}",
        f"Ответ: {answer}",
        "Совет: чтобы найти, сколько было сначала, к оставшемуся прибавляют то, что убрали",
    )



def try_patch_implicit_total_with_relation_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in question:
        return None
    if not (("в первый день" in lower and "во второй" in lower) or ("в первый" in lower and "во второй" in lower)):
        return None
    if "во второй" in question or "в первый" in question:
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    noun_matches = re.findall(rf"{base}\s+([а-яё]+)", lower)
    noun = noun_matches[0] if noun_matches else ""

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        if delta != nums[1]:
            return None
        second = apply_more_less(base, delta, mode)
        if second is None:
            return None
        op = "+" if mode == "больше" else "-"
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        second_text = f"{second} {noun}".strip()
        return join_explanation_lines(
            f"1) Если в первый день было {base} {noun}, а во второй на {delta} {mode}, то во второй день было {base} {op} {delta} = {second_text}",
            f"2) Если в первый день было {base} {noun}, а во второй день {second_text}, то всего {base} + {second} = {answer}",
            f"Ответ: {answer}",
            "Совет: если сразу нельзя ответить на главный вопрос, сначала найди неизвестное количество, потом сумму",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        if factor != nums[1]:
            return None
        second = apply_times_relation(base, factor, mode)
        if second is None:
            return None
        op = "×" if mode == "больше" else ":"
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        second_text = f"{second} {noun}".strip()
        return join_explanation_lines(
            f"1) Если во второй день в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то во второй день было {base} {op} {factor} = {second_text}",
            f"2) Если в первый день было {base} {noun}, а во второй день {second_text}, то всего {base} + {second} = {answer}",
            f"Ответ: {answer}",
            "Совет: сначала найди число, которое дано через отношение, потом считай всё вместе",
        )
    return None



def try_patch_part_then_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "из них" not in lower or "осталь" not in lower:
        return None
    if not ("на сколько" in question or "во сколько" in question):
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None

    total, known = nums[0], nums[1]
    if known > total:
        return None
    other = total - known

    pattern = re.search(r"из\s+них\s+(\d+)\s+([а-яё]+).*?остальн[а-яё]*\s*[—-]?\s*([а-яё]+)", lower)
    known_name = pattern.group(2) if pattern else "известной части"
    other_name = pattern.group(3) if pattern else "другой части"
    q_left, q_right = _patch_pick_compare_names_from_question(raw_text)
    if q_left:
        known_name = q_left if q_left in lower else known_name
        other_name = q_right if q_right in lower else other_name

    if "во сколько" in question:
        bigger = max(known, other)
        smaller = min(known, other)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        return join_explanation_lines(
            f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
        )

    bigger = max(known, other)
    smaller = min(known, other)
    diff = bigger - smaller
    if known >= other:
        answer_line = f"Ответ: {known_name} на {diff} больше, чем {other_name}"
    else:
        answer_line = f"Ответ: {other_name} на {diff} больше, чем {known_name}"
    return join_explanation_lines(
        f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
        f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
        answer_line,
        "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
    )



def try_patch_same_quantity_price_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "за столько же" not in lower or not ("дороже" in question or "дешевле" in question):
        return None

    first = re.search(r"за\s+(\d+)\s+([а-яё]+)\s+([а-яё]+)\s+заплатил\w*\s+(\d+)\s*руб", lower)
    second = re.search(r"за\s+столько\s+же\s+([а-яё]+)\s+([а-яё]+)\s+\w+\s+заплатил\w*\s+(\d+)\s*руб", lower)
    if not first or not second:
        return None

    count = int(first.group(1))
    unit_plural = first.group(2)
    item1 = first.group(3)
    cost1 = int(first.group(4))
    item2 = second.group(2)
    cost2 = int(second.group(3))
    if count == 0 or cost1 % count != 0 or cost2 % count != 0:
        return None

    price1 = cost1 // count
    price2 = cost2 // count
    diff = abs(price1 - price2)
    unit_singular = _patch_singular_unit(unit_plural)

    asked = re.search(rf"{unit_singular}\s+([а-яё]+).*?чем\s+{unit_singular}\s+([а-яё]+)", question)
    left_item = asked.group(1) if asked else item2
    right_item = asked.group(2) if asked else item1
    price_by_item = {item1: price1, item2: price2}
    if left_item not in price_by_item or right_item not in price_by_item:
        return None

    left_price = price_by_item[left_item]
    right_price = price_by_item[right_item]
    if left_price > right_price:
        answer_line = f"Ответ: один {unit_singular} {left_item} на {diff} руб. дороже, чем один {unit_singular} {right_item}"
    elif left_price < right_price:
        answer_line = f"Ответ: один {unit_singular} {left_item} на {diff} руб. дешевле, чем один {unit_singular} {right_item}"
    else:
        answer_line = f"Ответ: один {unit_singular} {left_item} стоит столько же, сколько и один {unit_singular} {right_item}"

    return join_explanation_lines(
        f"1) Если за {count} {unit_plural} {item1} заплатили {cost1} руб., то один {unit_singular} {item1} стоит {cost1} : {count} = {price1} руб",
        f"2) Если за {count} {unit_plural} {item2} заплатили {cost2} руб., то один {unit_singular} {item2} стоит {cost2} : {count} = {price2} руб",
        f"3) Сравниваем цены: {max(price1, price2)} - {min(price1, price2)} = {diff} руб",
        answer_line,
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )



def try_patch_named_sum_of_two_products_money_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if not (contains_any_fragment(lower, ("заплат", "стоим")) or contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила", "сколько стоит"))):
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None
    if contains_any_fragment(question, ("сколько стоит 1", "сколько стоила 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то за {first['name']} заплатили {first['count']} × {first['value']} = {first_total} руб",
        f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то за {second['name']} заплатили {second['count']} × {second['value']} = {second_total} руб",
        f"3) Если за {first['name']} заплатили {first_total} руб., а за {second['name']} {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )



def try_patch_labeled_proportional_division_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if not contains_any_fragment(lower, ("цена наборов одинаковая", "цена одинаковая", "если цена наборов одинаковая", "если цена одинаковая")):
        return None
    if not ("сколько" in question and contains_any_fragment(question, ("каждого", "каждая", "каждой"))):
        return None

    match = re.search(r"(\d+)\s+([^.,;]+?)\s+и\s+(\d+)\s+([^.,;]+?)\.\s*за\s+всю\s+покупку\s+заплатил[аи]?\s+(\d+)\s*руб", lower)
    if not match:
        return None

    count1 = int(match.group(1))
    label1 = match.group(2).strip()
    count2 = int(match.group(3))
    label2 = match.group(4).strip()
    total_cost = int(match.group(5))

    total_count = count1 + count2
    if total_count == 0 or total_cost % total_count != 0:
        return None
    one_price = total_cost // total_count
    first_cost = one_price * count1
    second_cost = one_price * count2

    return join_explanation_lines(
        f"1) Если купили {count1} {label1} и {count2} {label2}, то всего купили {count1} + {count2} = {total_count} наборов",
        f"2) Если за {total_count} наборов заплатили {total_cost} руб., то один набор стоит {total_cost} : {total_count} = {one_price} руб",
        f"3) Если один набор стоит {one_price} руб., то за {count1} {label1} заплатили {one_price} × {count1} = {first_cost} руб",
        f"4) Если один набор стоит {one_price} руб., то за {count2} {label2} заплатили {one_price} × {count2} = {second_cost} руб",
        f"Ответ: за {count1} {label1} заплатили {first_cost} руб.; за {count2} {label2} — {second_cost} руб",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )



def try_patch_labeled_two_differences_bag_counts_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or "мешк" not in question:
        return None
    if not ("морков" in lower and "картоф" in lower):
        return None

    carrot_mass, potato_mass, diff_bags = nums
    diff_mass = potato_mass - carrot_mass
    if diff_bags == 0 or diff_mass <= 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    if carrot_mass % per_bag != 0 or potato_mass % per_bag != 0:
        return None
    carrot_bags = carrot_mass // per_bag
    potato_bags = potato_mass // per_bag

    return join_explanation_lines(
        f"1) Если картофеля собрали {potato_mass} кг, а моркови {carrot_mass} кг, то разность масс равна {potato_mass} - {carrot_mass} = {diff_mass} кг",
        f"2) Если эти {diff_mass} кг составляют {diff_bags} мешков, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг",
        f"3) Если моркови {carrot_mass} кг, а в одном мешке {per_bag} кг, то мешков моркови {carrot_mass} : {per_bag} = {carrot_bags}",
        f"4) Если картофеля {potato_mass} кг, а в одном мешке {per_bag} кг, то мешков картофеля {potato_mass} : {per_bag} = {potato_bags}",
        f"Ответ: моркови было {carrot_bags} мешков, картофеля — {potato_bags} мешков",
        "Совет: в задачах по двум разностям сначала находят, чему соответствует одна равная часть",
    )



def try_patch_labeled_indirect_two_question_total_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "?" not in raw_text:
        return None
    if not (("во втором" in question or "на второй" in question) and ("в двух" in question or "в двух кружках" in question or "всего" in question or "обоих" in question)):
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)

    if len(relation_pairs) == 1 and "это" in lower:
        delta, relation = relation_pairs[0]
        if relation == "больше":
            second = base - delta
            op = "-"
            relation_text = "на столько же меньше"
        else:
            second = base + delta
            op = "+"
            relation_text = "на столько же больше"
        if second < 0:
            return None
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь на {delta} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {delta} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer}",
            f"Ответ: во втором количестве — {second}; всего — {answer}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )

    if len(scale_pairs) == 1 and "это" in lower:
        factor, relation = scale_pairs[0]
        if relation == "больше":
            if factor == 0 or base % factor != 0:
                return None
            second = base // factor
            op = ":"
            relation_text = "во столько же раз меньше"
        else:
            second = base * factor
            op = "×"
            relation_text = "во столько же раз больше"
        total = base + second
        answer = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {factor} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer}",
            f"Ответ: во втором количестве — {second}; всего — {answer}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )
    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_patch_same_quantity_price_compare_explanation(user_text)
        or try_patch_named_sum_of_two_products_money_explanation(user_text)
        or try_patch_unknown_minuend_simple_explanation(user_text)
        or try_patch_part_then_compare_explanation(user_text)
        or try_patch_implicit_total_with_relation_explanation(user_text)
        or try_patch_labeled_proportional_division_explanation(user_text)
        or try_patch_labeled_two_differences_bag_counts_explanation(user_text)
        or try_patch_labeled_indirect_two_question_total_explanation(user_text)
        or _PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11H: grammar polishing for named tasks ---


def _patch_after_za_name(name: str) -> str:
    text = re.sub(r"\s+", " ", str(name or "").strip())
    parts = text.split()
    if not parts:
        return text
    mapping = {
        "тетрадей": "тетради",
        "книг": "книги",
        "ручек": "ручки",
        "карандашей": "карандаши",
        "цветов": "цветы",
        "яблок": "яблоки",
        "груш": "груши",
        "роз": "розы",
        "гвоздик": "гвоздики",
        "фломастеров": "фломастеры",
        "альбомов": "альбомы",
        "карандашей": "карандаши",
        "пакетов": "пакеты",
        "наборов": "наборы",
    }
    parts[-1] = mapping.get(parts[-1], parts[-1])
    return " ".join(parts)



def try_patch_named_sum_of_two_products_money_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if not (contains_any_fragment(lower, ("заплат", "стоим")) or contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила", "сколько стоит"))):
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None
    if contains_any_fragment(question, ("сколько стоит 1", "сколько стоила 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total
    first_name = _patch_after_za_name(first["name"])
    second_name = _patch_after_za_name(second["name"])

    return join_explanation_lines(
        f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то за {first_name} заплатили {first['count']} × {first['value']} = {first_total} руб",
        f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то за {second_name} заплатили {second['count']} × {second['value']} = {second_total} руб",
        f"3) Если за {first_name} заплатили {first_total} руб., а за {second_name} {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )



def try_patch_part_then_compare_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "из них" not in lower or "осталь" not in lower:
        return None
    if not ("на сколько" in question or "во сколько" in question):
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None

    total, known = nums[0], nums[1]
    if known > total:
        return None
    other = total - known

    pattern = re.search(r"из\s+них\s+(\d+)\s+([а-яё]+).*?остальн[а-яё]*\s*[—-]?\s*([а-яё]+)", lower)
    known_name = pattern.group(2) if pattern else "известной части"
    other_name = pattern.group(3) if pattern else "другой части"
    q_left, q_right = _patch_pick_compare_names_from_question(raw_text)
    if q_left:
        known_name = q_left
    if q_right:
        other_name = q_right

    if "во сколько" in question:
        bigger = max(known, other)
        smaller = min(known, other)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        return join_explanation_lines(
            f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
        )

    bigger = max(known, other)
    smaller = min(known, other)
    diff = bigger - smaller
    if known >= other:
        answer_line = f"Ответ: {known_name} на {diff} больше, чем {other_name}"
    else:
        answer_line = f"Ответ: {other_name} на {diff} больше, чем {known_name}"
    return join_explanation_lines(
        f"1) Если всего было {total}, а {known_name} было {known}, то {other_name} было {total} - {known} = {other}",
        f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
        answer_line,
        "Совет: если сначала нужно найти неизвестную часть, а потом сравнить, выполняй действия по порядку",
    )



def try_patch_labeled_indirect_two_question_total_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "?" not in raw_text:
        return None
    if not (("во втором" in question or "на второй" in question) and ("в двух" in question or "в двух кружках" in question or "всего" in question or "обоих" in question)):
        return None

    base = nums[0]
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    has_indirect_marker = ("это" in lower) or ("что" in lower)
    if not has_indirect_marker:
        return None

    second_label = "во втором кружке" if "кружке" in question else "во втором"
    if "полке" in question:
        second_label = "на второй полке"
    total_label = "всего"
    answer_total = ""

    if len(relation_pairs) == 1:
        delta, relation = relation_pairs[0]
        if relation == "больше":
            second = base - delta
            op = "-"
            relation_text = "на столько же меньше"
        else:
            second = base + delta
            op = "+"
            relation_text = "на столько же больше"
        if second < 0:
            return None
        total = base + second
        answer_total = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь на {delta} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {delta} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer_total}",
            f"Ответ: {second_label} — {second}; {total_label} — {answer_total}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )

    if len(scale_pairs) == 1:
        factor, relation = scale_pairs[0]
        if relation == "больше":
            if factor == 0 or base % factor != 0:
                return None
            second = base // factor
            op = ":"
            relation_text = "во столько же раз меньше"
        else:
            second = base * factor
            op = "×"
            relation_text = "во столько же раз больше"
        total = base + second
        answer_total = _patch_answer_with_question_noun(total, raw_text)
        return join_explanation_lines(
            f"1) Это косвенная форма: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то другое число {relation_text}",
            f"2) Находим второе количество: {base} {op} {factor} = {second}",
            f"3) Находим всё вместе: {base} + {second} = {answer_total}",
            f"Ответ: {second_label} — {second}; {total_label} — {answer_total}",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму",
        )
    return None


# --- FINAL PATCH 2026-04-11I: question compare noun extraction fix ---

def _patch_pick_compare_names_from_question(raw_text: str) -> Tuple[str, str]:
    question = _question_lower_text(raw_text)
    match = re.search(r"на\s+сколько\s+больше\s+([а-яё]+),?\s+чем\s+([а-яё]+)", question)
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"на\s+сколько\s+меньше\s+([а-яё]+),?\s+чем\s+([а-яё]+)", question)
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"во\s+сколько\s+раз\s+больше\s+([а-яё]+),?\s+чем\s+([а-яё]+)", question)
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"во\s+сколько\s+раз\s+меньше\s+([а-яё]+),?\s+чем\s+([а-яё]+)", question)
    if match:
        return match.group(1), match.group(2)
    return "", ""


# --- FINAL PATCH 2026-04-11J: two-question relation-and-compare tasks ---

def _patch_secondary_place_label(raw_text: str) -> str:
    lower = _statement_lower_text(raw_text)
    for pattern in [r"во\s+второй\s+[а-яё]+", r"во\s+втором\s+[а-яё]+", r"на\s+второй\s+[а-яё]+", r"на\s+втором\s+[а-яё]+"]:
        match = re.search(pattern, lower)
        if match:
            return match.group(0)
    return "во второй части"



def try_patch_relation_then_compare_two_question_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    if raw_text.count("?") < 2:
        return None
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    base = nums[0]
    second_label = _patch_secondary_place_label(raw_text)

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        if mode == "больше":
            compare_line = f"Ответ: {second_label} было {related}; в первом месте было на {diff} больше"
        else:
            compare_line = f"Ответ: {second_label} было {related}; в первом месте было на {diff} больше"
        return join_explanation_lines(
            f"1) Если во втором месте на {delta} {mode}, то {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            compare_line,
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если во втором месте в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: {second_label} было {related}; отличие — в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )
    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_patch_same_quantity_price_compare_explanation(user_text)
        or try_patch_named_sum_of_two_products_money_explanation(user_text)
        or try_patch_unknown_minuend_simple_explanation(user_text)
        or try_patch_relation_then_compare_two_question_explanation(user_text)
        or try_patch_part_then_compare_explanation(user_text)
        or try_patch_implicit_total_with_relation_explanation(user_text)
        or try_patch_labeled_proportional_division_explanation(user_text)
        or try_patch_labeled_two_differences_bag_counts_explanation(user_text)
        or try_patch_labeled_indirect_two_question_total_explanation(user_text)
        or _PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11K: support mixed-question punctuation in two-question tasks ---

def try_patch_relation_then_compare_two_question_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    has_find_second = bool(re.search(r"сколько[^?.!]*?(?:во\s+второй|во\s+втором|на\s+второй|на\s+втором)", lower))
    has_compare = ("на сколько" in lower) or ("во сколько" in lower)
    if not (has_find_second and has_compare):
        return None

    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    base = nums[0]
    second_label = _patch_secondary_place_label(raw_text)
    first_label = second_label.replace("второй", "первой").replace("втором", "первом")

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        relation_text = "больше" if base >= related else "меньше"
        return join_explanation_lines(
            f"1) Если {second_label} на {delta} {mode}, то {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {second_label} было {related}; {first_label} было на {diff} {relation_text}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если {second_label} в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: {second_label} было {related}; отличие — в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )
    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_local_equation_explanation(user_text)
        or try_local_fraction_explanation(user_text)
        or try_local_expression_explanation(user_text)
        or try_local_measurement_word_problem_explanation(user_text)
        or try_local_geometry_explanation(user_text)
        or try_patch_same_quantity_price_compare_explanation(user_text)
        or try_patch_named_sum_of_two_products_money_explanation(user_text)
        or try_patch_unknown_minuend_simple_explanation(user_text)
        or try_patch_relation_then_compare_two_question_explanation(user_text)
        or try_patch_part_then_compare_explanation(user_text)
        or try_patch_implicit_total_with_relation_explanation(user_text)
        or try_patch_labeled_proportional_division_explanation(user_text)
        or try_patch_labeled_two_differences_bag_counts_explanation(user_text)
        or try_patch_labeled_indirect_two_question_total_explanation(user_text)
        or _PATCH20260411G_PREVIOUS_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11L: better place labels for two-question tasks ---

def _patch_secondary_place_label(raw_text: str) -> str:
    normalized = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    match = re.search(r"сколько[^?.!]*?(во\s+второй\s+[а-яё]+|во\s+втором\s+[а-яё]+|на\s+второй\s+[а-яё]+|на\s+втором\s+[а-яё]+)", normalized)
    if match:
        return match.group(1)
    for label in ("во второй вазе", "на второй полке", "во втором кружке", "во второй день", "на второй стоянке"):
        if label in normalized:
            return label
    return "во второй части"



def _patch_first_place_label(second_label: str) -> str:
    text = str(second_label or "").strip()
    text = text.replace("во второй", "в первой")
    text = text.replace("во втором", "в первом")
    text = text.replace("на второй", "на первой")
    text = text.replace("на втором", "на первом")
    return text



def try_patch_relation_then_compare_two_question_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    has_find_second = bool(re.search(r"сколько[^?.!]*?(?:во\s+второй|во\s+втором|на\s+второй|на\s+втором)", lower))
    has_compare = ("на сколько" in lower) or ("во сколько" in lower)
    if not (has_find_second and has_compare):
        return None

    relation_pairs = extract_relation_pairs(lower)
    scale_pairs = extract_scale_pairs(lower)
    base = nums[0]
    second_label = _patch_secondary_place_label(raw_text)
    first_label = _patch_first_place_label(second_label)

    if len(relation_pairs) == 1:
        delta, mode = relation_pairs[0]
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        diff = bigger - smaller
        op = "+" if mode == "больше" else "-"
        return join_explanation_lines(
            f"1) Если {second_label} на {delta} {mode}, чем {first_label}, то {base} {op} {delta} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то разность равна {bigger} - {smaller} = {diff}",
            f"Ответ: {second_label} было {related}; {first_label} было на {diff} больше",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )

    if len(scale_pairs) == 1:
        factor, mode = scale_pairs[0]
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None
        bigger = max(base, related)
        smaller = min(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        result = bigger // smaller
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если {second_label} в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем {first_label}, то {base} {op} {factor} = {related}",
            f"2) Если одно количество равно {bigger}, а другое равно {smaller}, то {bigger} : {smaller} = {result}",
            f"Ответ: {second_label} было {related}; отличие — в {result} {plural_form(result, 'раз', 'раза', 'раз')}",
            "Совет: если после нахождения второго числа нужно ещё сравнить числа, выполняй действия по порядку",
        )
    return None


# --- FINAL PATCH 2026-04-11M: safer count answers, missing simple templates, cleaner fraction remainder ---

_PREVIOUS_20260411M_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_PREVIOUS_20260411M_DETECT_QUESTION_UNIT = _detect_question_unit

QUESTION_NOUN_FORMS = {
    "книга": ("книга", "книги", "книг"),
    "книги": ("книга", "книги", "книг"),
    "книг": ("книга", "книги", "книг"),
    "полка": ("полка", "полки", "полок"),
    "полки": ("полка", "полки", "полок"),
    "полок": ("полка", "полки", "полок"),
    "коробка": ("коробка", "коробки", "коробок"),
    "коробки": ("коробка", "коробки", "коробок"),
    "коробок": ("коробка", "коробки", "коробок"),
    "сетка": ("сетка", "сетки", "сеток"),
    "сетки": ("сетка", "сетки", "сеток"),
    "сеток": ("сетка", "сетки", "сеток"),
    "клетка": ("клетка", "клетки", "клеток"),
    "клетки": ("клетка", "клетки", "клеток"),
    "клеток": ("клетка", "клетки", "клеток"),
    "пакет": ("пакет", "пакета", "пакетов"),
    "пакета": ("пакет", "пакета", "пакетов"),
    "пакетов": ("пакет", "пакета", "пакетов"),
    "мешок": ("мешок", "мешка", "мешков"),
    "мешка": ("мешок", "мешка", "мешков"),
    "мешков": ("мешок", "мешка", "мешков"),
    "карандаш": ("карандаш", "карандаша", "карандашей"),
    "карандаша": ("карандаш", "карандаша", "карандашей"),
    "карандашей": ("карандаш", "карандаша", "карандашей"),
    "ручка": ("ручка", "ручки", "ручек"),
    "ручки": ("ручка", "ручки", "ручек"),
    "ручек": ("ручка", "ручки", "ручек"),
    "тетрадь": ("тетрадь", "тетради", "тетрадей"),
    "тетради": ("тетрадь", "тетради", "тетрадей"),
    "тетрадей": ("тетрадь", "тетради", "тетрадей"),
    "страница": ("страница", "страницы", "страниц"),
    "страницы": ("страница", "страницы", "страниц"),
    "страниц": ("страница", "страницы", "страниц"),
    "машина": ("машина", "машины", "машин"),
    "машины": ("машина", "машины", "машин"),
    "машин": ("машина", "машины", "машин"),
    "дерево": ("дерево", "дерева", "деревьев"),
    "дерева": ("дерево", "дерева", "деревьев"),
    "деревьев": ("дерево", "дерева", "деревьев"),
    "яблоко": ("яблоко", "яблока", "яблок"),
    "яблока": ("яблоко", "яблока", "яблок"),
    "яблок": ("яблоко", "яблока", "яблок"),
    "груша": ("груша", "груши", "груш"),
    "груши": ("груша", "груши", "груш"),
    "груш": ("груша", "груши", "груш"),
    "человек": ("человек", "человека", "человек"),
    "пассажир": ("пассажир", "пассажира", "пассажиров"),
    "пассажира": ("пассажир", "пассажира", "пассажиров"),
    "пассажиров": ("пассажир", "пассажира", "пассажиров"),
    "ученик": ("ученик", "ученика", "учеников"),
    "ученика": ("ученик", "ученика", "учеников"),
    "учеников": ("ученик", "ученика", "учеников"),
    "мальчик": ("мальчик", "мальчика", "мальчиков"),
    "мальчика": ("мальчик", "мальчика", "мальчиков"),
    "мальчиков": ("мальчик", "мальчика", "мальчиков"),
    "фломастер": ("фломастер", "фломастера", "фломастеров"),
    "фломастера": ("фломастер", "фломастера", "фломастеров"),
    "фломастеров": ("фломастер", "фломастера", "фломастеров"),
    "цветок": ("цветок", "цветка", "цветов"),
    "цветка": ("цветок", "цветка", "цветов"),
    "цветов": ("цветок", "цветка", "цветов"),
    "птица": ("птица", "птицы", "птиц"),
    "птицы": ("птица", "птицы", "птиц"),
    "птиц": ("птица", "птицы", "птиц"),
    "рыба": ("рыба", "рыбы", "рыб"),
    "рыбы": ("рыба", "рыбы", "рыб"),
    "рыб": ("рыба", "рыбы", "рыб"),
    "попугай": ("попугай", "попугая", "попугаев"),
    "попугая": ("попугай", "попугая", "попугаев"),
    "попугаев": ("попугай", "попугая", "попугаев"),
    "набор": ("набор", "набора", "наборов"),
    "набора": ("набор", "набора", "наборов"),
    "наборов": ("набор", "набора", "наборов"),
    "банка": ("банка", "банки", "банок"),
    "банки": ("банка", "банки", "банок"),
    "банок": ("банка", "банки", "банок"),
    "булочка": ("булочка", "булочки", "булочек"),
    "булочки": ("булочка", "булочки", "булочек"),
    "булочек": ("булочка", "булочки", "булочек"),
    "гвоздика": ("гвоздика", "гвоздики", "гвоздик"),
    "гвоздики": ("гвоздика", "гвоздики", "гвоздик"),
    "гвоздик": ("гвоздика", "гвоздики", "гвоздик"),
    "куст": ("куст", "куста", "кустов"),
    "куста": ("куст", "куста", "кустов"),
    "кустов": ("куст", "куста", "кустов"),
    "корзина": ("корзина", "корзины", "корзин"),
    "корзины": ("корзина", "корзины", "корзин"),
    "корзин": ("корзина", "корзины", "корзин"),
    "ягода": ("ягода", "ягоды", "ягод"),
    "ягоды": ("ягода", "ягоды", "ягод"),
    "ягод": ("ягода", "ягоды", "ягод"),
    "пельмень": ("пельмень", "пельменя", "пельменей"),
    "пельменя": ("пельмень", "пельменя", "пельменей"),
    "пельменей": ("пельмень", "пельменя", "пельменей"),
}

MEASURE_QUESTION_NOUNS = {
    "руб", "рубль", "рубля", "рублей", "деньги", "денег",
    "кг", "килограмм", "килограмма", "килограммов",
    "г", "грамм", "грамма", "граммов",
    "км", "километр", "километра", "километров",
    "м", "метр", "метра", "метров",
    "см", "сантиметр", "сантиметра", "сантиметров",
    "дм", "дециметр", "дециметра", "дециметров",
    "мм", "миллиметр", "миллиметра", "миллиметров",
    "л", "литр", "литра", "литров",
    "ч", "час", "часа", "часов",
    "мин", "минута", "минуты", "минут",
    "скорость", "длина", "ширина", "площадь", "периметр", "масса", "расстояние",
}


def _lookup_question_noun_forms(noun: str) -> Optional[Tuple[str, str, str]]:
    key = str(noun or "").strip().lower().replace("ё", "е")
    if not key:
        return None
    return QUESTION_NOUN_FORMS.get(key)



def _select_plural_by_count(count_value: int, forms: Tuple[str, str, str]) -> str:
    one, few, many = forms
    value = abs(int(count_value)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return many
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many



def _question_requests_object_count(raw_text: str) -> bool:
    question = _question_lower_text(raw_text)
    match = re.search(
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|понадобится\s+|понадобилось\s+|потребовалось\s+|можно\s+купить\s+)?([а-яё]+)",
        question,
    )
    if not match:
        return False
    noun = match.group(1).strip().lower().replace("ё", "е")
    return noun not in MEASURE_QUESTION_NOUNS



def _detect_question_unit(raw_text: str) -> str:
    if _question_requests_object_count(raw_text):
        return ""
    return _PREVIOUS_20260411M_DETECT_QUESTION_UNIT(raw_text)



def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value

    is_numeric = re.fullmatch(r"-?\d+(?:/\d+)?", value) is not None
    if not is_numeric:
        return value

    if _question_requests_object_count(raw_text):
        noun = _extract_question_noun(raw_text)
        forms = _lookup_question_noun_forms(noun)
        if forms:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                return value
            return f"{value} {_select_plural_by_count(count_value, forms)}"
        return value

    unit = _detect_question_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()
    return value



def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_numerator == 1:
        whole = remaining_value * denominator
        return join_explanation_lines(
            f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось 1/{denominator} всех денег",
            f"2) Если 1/{denominator} всех денег равна {remaining_value} руб., то одна доля равна {remaining_value} руб.",
            f"3) Если одна доля равна {remaining_value} руб., то все деньги равны {remaining_value} × {denominator} = {whole} руб.",
            f"Ответ: всего было {whole} руб.",
            "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
        )
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value} руб., то одна доля равна {remaining_value} : {remaining_numerator} = {one_part} руб.",
        f"3) Если одна доля равна {one_part} руб., то все деньги равны {one_part} × {denominator} = {whole} руб.",
        f"Ответ: всего было {whole} руб.",
        "Совет: если известен остаток после расхода части, сначала найди оставшуюся долю",
    )



def try_patch_single_group_total_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    if "сколько" not in question:
        return None
    if _has_group_count_question(question) or "кажд" in question or "поровну" in lower:
        return None
    if not re.search(r"\b(?:в\s+одной|в\s+одном|на\s+одной|на\s+одном)\b", lower):
        return None
    if not re.search(r"\b(?:в|на)\s+\d+\s+[а-яё]+", question):
        return None

    per_group, groups = nums[0], nums[1]
    total = per_group * groups
    return join_explanation_lines(
        f"1) Если в одной группе {per_group} предметов, а таких групп {groups}, то всего {per_group} × {groups} = {total}",
        f"Ответ: {total}",
        "Совет: если одинаковое количество повторяется несколько раз, используют умножение",
    )



def try_patch_unknown_multiplier_by_content_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2:
        return None
    if "сколько" not in question:
        return None
    if not contains_any_fragment(question, ("сеток", "пакетов", "коробок", "клеток", "корзин", "групп", "потребовалось", "понадобилось", "понадобится")):
        return None
    po_match = re.search(r"по\s+(\d+)\s+[а-яё]+", lower)
    if not po_match:
        return None

    total = max(nums)
    per_group = int(po_match.group(1))
    if per_group == 0 or total % per_group != 0:
        return None
    groups = total // per_group
    return join_explanation_lines(
        f"1) Если по {per_group} предметов брали несколько раз и получили {total} предметов, то число групп равно {total} : {per_group} = {groups}",
        f"Ответ: {groups}",
        "Совет: чтобы найти неизвестный множитель, произведение делят на известный множитель",
    )



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_patch_unknown_multiplier_by_content_explanation(user_text)
        or try_patch_single_group_total_explanation(user_text)
        or _PREVIOUS_20260411M_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-11N: better noun extraction in count questions ---


def _extract_count_question_noun(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    patterns = [
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|потребуется\s+|потребовалось\s+|понадобится\s+|понадобилось\s+|можно\s+купить\s+)?(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
        r"^сколько\s+(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            noun = match.group(1).strip().lower().replace("ё", "е")
            if noun:
                return noun
    return ""



def _question_requests_object_count(raw_text: str) -> bool:
    noun = _extract_count_question_noun(raw_text)
    return bool(noun) and noun not in MEASURE_QUESTION_NOUNS



def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value

    is_numeric = re.fullmatch(r"-?\d+(?:/\d+)?", value) is not None
    if not is_numeric:
        return value

    noun = _extract_count_question_noun(raw_text)
    if noun and noun not in MEASURE_QUESTION_NOUNS:
        forms = _lookup_question_noun_forms(noun)
        if forms:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                return value
            return f"{value} {_select_plural_by_count(count_value, forms)}"
        return value

    unit = _detect_question_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()
    return value


# --- USER CONSOLIDATION PATCH 2026-04-11Z: cleaner final answers, textbook priority cases, stronger prompt ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже обязательно:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. Если можно, используй школьную форму:
Если ..., то ...
6. Если сразу нельзя ответить на главный вопрос, сначала найди то, что нужно для ответа.
7. После каждого действия коротко говори, что нашли.
8. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER = _detailed_maybe_enrich_answer


def _user_patch_pick_measure_unit(raw_text: str) -> str:
    try:
        question = _question_lower_text(raw_text)
    except Exception:
        question = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    statement = _statement_lower_text(raw_text)

    existing = ""
    try:
        existing = _detect_question_unit(raw_text) or ""
    except Exception:
        existing = ""
    if existing:
        return existing

    if contains_any_fragment(question, ("сколько весит", "какова масса", "чему равна масса")):
        for unit in ("т", "кг", "г"):
            if re.search(rf"(?<!/)\b{re.escape(unit)}\b", statement):
                return unit

    if contains_any_fragment(question, ("сколько литров", "сколько л", "каков объем", "каков объём", "чему равен объем", "чему равен объём")):
        for unit in ("л", "мл"):
            if re.search(rf"(?<!/)\b{re.escape(unit)}\b", statement):
                return unit

    if contains_any_fragment(question, ("какова скорость", "с какой скоростью")):
        for unit in ("км/ч", "м/с", "м/мин"):
            if unit in statement:
                return unit

    if contains_any_fragment(question, ("каково расстояние", "сколько километров", "сколько метров", "какова длина", "какова ширина", "какова сторона")):
        for unit in ("км", "м", "дм", "см", "мм"):
            if re.search(rf"(?<!/)\b{re.escape(unit)}\b", statement):
                return unit

    return ""


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value

    if re.search(r"[;]|, остаток", value):
        return value

    if re.fullmatch(r"-?\d+(?:/\d+)?", value) is None:
        return value

    unit = _user_patch_pick_measure_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()

    try:
        patched = _patch_answer_with_question_noun(int(value.split("/", 1)[0]) if "/" not in value else value, raw_text)
        patched = str(patched).strip()
        if patched and patched != value:
            return patched
    except Exception:
        pass

    try:
        return _USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER(answer, raw_text, kind)
    except Exception:
        return value


def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"1) Если в первой части {first_count} равных долей, а во второй {second_count} равных долей, то всего долей {first_count} + {second_count} = {group_total}",
        f"2) Если всего долей {group_total}, а общее количество равно {total}, то одна доля равна {total} : {group_total} = {one_unit}",
        f"3) Если одна доля равна {one_unit}, то {first_label} равна {one_unit} × {first_count} = {first_total}",
        f"4) Если одна доля равна {one_unit}, то {second_label} равна {one_unit} × {second_count} = {second_total}",
        f"Ответ: {first_label} — {first_total}; {second_label} — {second_total}",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )


def try_user_patch_fraction_measure_explanation(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower()
    fracs = extract_all_fraction_pairs(lower)
    values = extract_non_fraction_numbers(lower)
    if len(fracs) != 1 or not values:
        return None

    question = _question_lower_text(raw_text)
    if not contains_any_fragment(question, ("сколько весит", "сколько кг", "сколько г", "сколько литров", "сколько л")):
        return None

    numerator, denominator = fracs[0]
    if denominator == 0:
        return None
    total = max(values)
    unit = _user_patch_pick_measure_unit(raw_text)

    if total % denominator != 0:
        return None

    one_part = total // denominator
    part_value = one_part * numerator

    if numerator == 1:
        return join_explanation_lines(
            f"1) Если целое равно {total}{(' ' + unit) if unit else ''}, то одна доля равна {total} : {denominator} = {one_part}{(' ' + unit) if unit else ''}",
            f"Ответ: {part_value}{(' ' + unit) if unit else ''}",
            "Совет: чтобы найти одну долю числа, делят число на знаменатель",
        )

    return join_explanation_lines(
        f"1) Если целое равно {total}{(' ' + unit) if unit else ''}, то одна доля равна {total} : {denominator} = {one_part}{(' ' + unit) if unit else ''}",
        f"2) Если нужна дробь {numerator}/{denominator}, то берём {numerator} такие доли: {one_part} × {numerator} = {part_value}{(' ' + unit) if unit else ''}",
        f"Ответ: {part_value}{(' ' + unit) if unit else ''}",
        "Совет: чтобы найти долю от числа, сначала делят на знаменатель, потом умножают на числитель",
    )


def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if not remaining:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало", "купили")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали")

    if contains_any_fragment(lower, gain_words) and contains_any_fragment(question, ("сколько", "сколько стало", "сколько всего")):
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and contains_any_fragment(question, ("сколько", "сколько осталось", "сколько останется")):
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_fraction_measure_explanation(user_text)
        or try_user_patch_groups_then_change_explanation(user_text)
        or _USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )



# --- USER HOTFIX 2026-04-11Z1: narrow grouped-plus-change rule ---

def _user_patch_group_word(value: int) -> str:
    return plural_form(value, "одинаковая группа", "одинаковые группы", "одинаковых групп")


def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали")

    if contains_any_fragment(lower, gain_words) and contains_any_fragment(question, ("сколько", "сколько стало", "сколько всего")):
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} {_user_patch_group_word(groups)} по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and contains_any_fragment(question, ("сколько", "сколько осталось", "сколько останется")):
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} {_user_patch_group_word(groups)} по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None



# --- USER HOTFIX 2026-04-11Z2: do not steal "total then packed" remainder tasks ---

def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали")

    asks_gain_total = contains_any_fragment(question, ("сколько стало", "сколько всего", "сколько теперь"))
    asks_loss_total = contains_any_fragment(question, ("сколько осталось", "сколько останется"))

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None



# --- USER HOTFIX 2026-04-11Z3: broader question patterns for "стало/осталось" ---

def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    change_value = remaining[0]
    base_total = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали")

    asks_gain_total = ("стало" in question) or ("всего" in question) or ("теперь" in question)
    asks_loss_total = ("остал" in question)

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        result = base_total + change_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом добавили ещё {change_value}, то стало {base_total} + {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        result = base_total - change_value
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {base_total}",
            f"2) Если было {base_total}, а потом убрали {change_value}, то осталось {base_total} - {change_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом часть убирают, сначала выполняют умножение",
        )

    return None



# --- USER HOTFIX 2026-04-11Z4: word-boundary question detection and better remainder handling ---

def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    other_value = remaining[0]
    group_value = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали", "упаковали")

    asks_gain_total = bool(re.search(r"\bстало\b|\bвсего\b|\bтеперь\b", question))
    asks_loss_total = "остал" in question

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        start_amount = min(group_value, other_value)
        added_amount = max(group_value, other_value) if min(group_value, other_value) == group_value else group_value
        # Для конструкций типа "на полках по 2 книги. Подарили ещё 10 книг" стартовым количеством является group_value.
        start_amount = group_value
        added_amount = other_value
        result = start_amount + added_amount
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {group_value}",
            f"2) Если было {group_value}, а потом добавили ещё {other_value}, то стало {group_value} + {other_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        total_before = max(group_value, other_value)
        removed_amount = min(group_value, other_value)
        result = total_before - removed_amount
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {groups} одинаковые группы по {per_group} в каждой, то сначала находим величину этой части: {groups} × {per_group} = {group_value}",
            f"2) Если всего было {total_before}, а эта часть равна {removed_amount}, то осталось {total_before} - {removed_amount} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если известны всё число и одна часть, другую часть находят вычитанием",
        )

    return None



# --- USER HOTFIX 2026-04-11Z5: correct group phrase agreement ---

def _user_patch_group_phrase(count: int) -> str:
    value = abs(int(count)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return f"{count} одинаковых групп"
    if tail == 1:
        return f"{count} одинаковая группа"
    if 2 <= tail <= 4:
        return f"{count} одинаковые группы"
    return f"{count} одинаковых групп"


def try_user_patch_groups_then_change_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "по" not in lower:
        return None

    po_matches = list(re.finditer(r"\bпо\s+\d+\b", lower))
    if len(po_matches) != 1:
        return None

    pair = None
    try:
        pair = _first_po_pair(lower)
    except Exception:
        pair = None
    if not pair:
        return None

    groups, per_group = pair
    nums = extract_ordered_numbers(lower)
    remaining = list(nums)
    for value in (groups, per_group):
        if value in remaining:
            remaining.remove(value)
    if len(remaining) != 1:
        return None

    other_value = remaining[0]
    group_value = groups * per_group

    gain_words = WORD_GAIN_HINTS + ("подарили", "добавили", "поставили", "вошло", "приехало")
    loss_words = WORD_LOSS_HINTS + ("уехали", "вышли", "забрали", "сняли", "продали", "расфасовали", "упаковали")

    asks_gain_total = bool(re.search(r"\bстало\b|\bвсего\b|\bтеперь\b", question))
    asks_loss_total = "остал" in question

    group_phrase = _user_patch_group_phrase(groups)

    if contains_any_fragment(lower, gain_words) and asks_gain_total:
        result = group_value + other_value
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {group_phrase} по {per_group} в каждой, то сначала находим, сколько было всего: {groups} × {per_group} = {group_value}",
            f"2) Если было {group_value}, а потом добавили ещё {other_value}, то стало {group_value} + {other_value} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если сначала есть одинаковые группы, а потом что-то прибавляют, сначала выполняют умножение",
        )

    if contains_any_fragment(lower, loss_words) and asks_loss_total:
        total_before = max(group_value, other_value)
        removed_amount = min(group_value, other_value)
        result = total_before - removed_amount
        if result < 0:
            return None
        answer_text = _detailed_maybe_enrich_answer(str(result), raw_text, "word")
        return join_explanation_lines(
            f"1) Если есть {group_phrase} по {per_group} в каждой, то сначала находим величину этой части: {groups} × {per_group} = {group_value}",
            f"2) Если всего было {total_before}, а эта часть равна {removed_amount}, то осталось {total_before} - {removed_amount} = {result}",
            f"Ответ: {answer_text}",
            "Совет: если известны всё число и одна часть, другую часть находят вычитанием",
        )

    return None


# --- FINAL CONSOLIDATION PATCH 2026-04-11Z6: safer units, compound word numbers, fuller textbook cases ---

_FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_FINAL_PATCH_PREV_NORMALIZE_WORD_PROBLEM_TEXT = normalize_word_problem_text

_COMPOUND_PREFIX_TO_DIGIT = {
    "двух": "2",
    "трех": "3",
    "трёх": "3",
    "четырех": "4",
    "четырёх": "4",
    "пяти": "5",
    "шести": "6",
    "семи": "7",
    "восьми": "8",
    "девяти": "9",
    "десяти": "10",
}

_COMPOUND_NUMERAL_RE = re.compile(
    r"\b(" + "|".join(map(re.escape, _COMPOUND_PREFIX_TO_DIGIT.keys())) + r")(литров[а-яё-]*|комнатн[а-яё-]*)",
    flags=re.IGNORECASE,
)


def normalize_word_problem_text(text: str) -> str:
    cleaned = _FINAL_PATCH_PREV_NORMALIZE_WORD_PROBLEM_TEXT(text)

    def _replace_compound(match: re.Match) -> str:
        stem = match.group(1).lower()
        tail = match.group(2)
        return f"{_COMPOUND_PREFIX_TO_DIGIT[stem]}-{tail}"

    cleaned = _COMPOUND_NUMERAL_RE.sub(_replace_compound, cleaned)
    return cleaned


QUESTION_NOUN_FORMS.update({
    "ведро": ("ведро", "ведра", "ведер"),
    "ведра": ("ведро", "ведра", "ведер"),
    "ведер": ("ведро", "ведра", "ведер"),
    "ведрах": ("ведро", "ведра", "ведер"),
    "вёдра": ("ведро", "ведра", "ведер"),
    "вёдер": ("ведро", "ведра", "ведер"),
    "вёдрах": ("ведро", "ведра", "ведер"),
    "ящик": ("ящик", "ящика", "ящиков"),
    "ящика": ("ящик", "ящика", "ящиков"),
    "ящиков": ("ящик", "ящика", "ящиков"),
    "ящиках": ("ящик", "ящика", "ящиков"),
    "клетках": ("клетка", "клетки", "клеток"),
    "банках": ("банка", "банки", "банок"),
    "квартира": ("квартира", "квартиры", "квартир"),
    "квартиры": ("квартира", "квартиры", "квартир"),
    "квартир": ("квартира", "квартиры", "квартир"),
    "комната": ("комната", "комнаты", "комнат"),
    "комнаты": ("комната", "комнаты", "комнат"),
    "комнат": ("комната", "комнаты", "комнат"),
    "раз": ("раз", "раза", "раз"),
})

MEASURE_QUESTION_NOUNS.update({"времени", "день", "дня", "дней", "секунда", "секунды", "секунд"})


def _extract_count_question_noun(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    patterns = [
        r"^(?:в|во|на)\s+скольких\s+([а-яё]+)",
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|понадобится\s+|понадобилось\s+|потребуется\s+|потребовалось\s+|можно\s+купить\s+|нужно\s+|нужно\s+купить\s+|всего\s+)?(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
        r"^сколько\s+(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)",
        r"^во\s+сколько\s+([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            noun = match.group(1).strip().lower().replace("ё", "е")
            if noun:
                return noun
    return ""



def _question_requests_object_count(raw_text: str) -> bool:
    noun = _extract_count_question_noun(raw_text)
    return bool(noun) and noun not in MEASURE_QUESTION_NOUNS



def _detect_question_unit(raw_text: str) -> str:
    try:
        question = _question_lower_text(raw_text)
    except Exception:
        question = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if _question_requests_object_count(raw_text):
        return ""
    if re.search(r"\bв\s+скольких\b", question):
        return ""
    if re.search(r"\bво\s+сколько\s+раз\b", question):
        return "раз"

    if re.search(r"(?:с какой скоростью|какова скорость)", question):
        for unit in ("км/ч", "м/мин", "м/с"):
            if unit in lower_full:
                return unit

    if re.search(r"\b(?:мм|миллиметр(?:а|ов|ы)?)\b", question):
        return "мм"
    if re.search(r"(?:см²|кв\.?\s*см|квадратн[а-яё]*\s+сантиметр)", question) or (
        "площад" in question and re.search(r"\b(?:см|сантиметр(?:а|ов|ы)?)\b", question)
    ):
        return "см²"
    if re.search(r"(?:дм²|кв\.?\s*дм|квадратн[а-яё]*\s+дециметр)", question) or (
        "площад" in question and re.search(r"\b(?:дм|дециметр(?:а|ов|ы)?)\b", question)
    ):
        return "дм²"
    if re.search(r"(?:м²|кв\.?\s*м\b|квадратн[а-яё]*\s+метр)", question) or (
        "площад" in question and re.search(r"\b(?:метр(?:а|ов|ы)?|м)\b", question)
    ):
        return "м²"

    if re.search(r"\b(?:руб|рубл(?:ь|я|ей)?|денег)\b", question):
        return "руб"
    if re.search(r"\b(?:кг|килограмм(?:а|ов|ы)?)\b", question):
        return "кг"
    if re.search(r"\b(?:г|грамм(?:а|ов|ы)?)\b", question):
        return "г"
    if re.search(r"\b(?:км|километр(?:а|ов|ы)?)\b", question):
        return "км"
    if re.search(r"\b(?:см|сантиметр(?:а|ов|ы)?)\b", question):
        return "см"
    if re.search(r"\b(?:дм|дециметр(?:а|ов|ы)?)\b", question):
        return "дм"
    if re.search(r"\b(?:м|метр(?:а|ов|ы)?)\b", question):
        return "м"
    if re.search(r"\b(?:л|литр(?:а|ов|ы)?)\b", question):
        return "л"
    if re.search(r"(?:сколько часов|сколько времени|за какое время|сколько час)", question):
        return "ч"
    if re.search(r"(?:сколько минут|сколько мин)", question):
        return "мин"
    return ""



def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip()
    if not value:
        return value
    if re.search(r"[А-Яа-я]", value):
        return value
    if re.fullmatch(r"-?\d+(?:/\d+)?", value) is None:
        return value

    noun = _extract_count_question_noun(raw_text)
    if noun and noun not in MEASURE_QUESTION_NOUNS:
        forms = _lookup_question_noun_forms(noun)
        if forms:
            try:
                count_value = int(value.split("/", 1)[0])
            except Exception:
                return value
            return f"{value} {_select_plural_by_count(count_value, forms)}"
        if noun == "раз":
            return f"{value} раз"

    unit = _detect_question_unit(raw_text)
    if unit:
        return f"{value} {unit}".strip()
    return value



def _final_patch_group_phrase(count: int) -> str:
    value = abs(int(count)) % 100
    tail = value % 10
    if 11 <= value <= 14:
        return f"{count} одинаковых групп"
    if tail == 1:
        return f"{count} одинаковая группа"
    if 2 <= tail <= 4:
        return f"{count} одинаковые группы"
    return f"{count} одинаковых групп"



def _final_patch_plural(count_value: int, forms: Tuple[str, str, str]) -> str:
    return _select_plural_by_count(count_value, forms)



def try_final_patch_simple_group_total_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if "сколько" not in question:
        return None
    if len(nums) != 2:
        return None
    if any(fragment in question for fragment in (
        "в скольких",
        "сколько потребуется",
        "сколько потребовалось",
        "сколько понадобится",
        "сколько понадобилось",
        "сколько осталось",
        "сколько останется",
        "сколько стало",
        "сколько заплатила",
        "сколько заплатил",
        "сколько стоила",
        "сколько стоит",
    )):
        return None
    if "поровну" in lower or "кажд" in question:
        return None
    if contains_any_fragment(lower, WORD_GAIN_HINTS + WORD_LOSS_HINTS):
        return None

    groups = None
    per_group = None
    unit = _detect_question_unit(raw_text)

    if len(re.findall(r"\bпо\s+\d+\b", lower)) == 1:
        pair = _first_po_pair(lower)
        if pair:
            groups, per_group = pair
    else:
        match = re.search(r"\b(\d+)\s+(\d+)-литров[а-я-]*\s+[а-я]+\b", lower)
        if match:
            groups, per_group = int(match.group(1)), int(match.group(2))
            unit = unit or "л"

    if groups is None or per_group is None:
        return None

    total = groups * per_group
    group_phrase = _final_patch_group_phrase(groups)
    if unit:
        return join_explanation_lines(
            f"1) Если есть {group_phrase} по {per_group} {unit} в каждой, то всего {groups} × {per_group} = {total} {unit}",
            f"Ответ: всего было {total} {unit}",
            "Совет: если одинаковая величина повторяется несколько раз, используют умножение",
        )
    answer_text = _detailed_maybe_enrich_answer(str(total), raw_text, "word")
    return join_explanation_lines(
        f"1) Если есть {group_phrase} по {per_group} в каждой, то всего {groups} × {per_group} = {total}",
        f"Ответ: всего было {answer_text}",
        "Совет: если одинаковое количество повторяется несколько раз, используют умножение",
    )



def try_final_patch_school_boxes_equal_price_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "школ" not in lower or "ящик" not in lower:
        return None
    if "сколько должна заплатить" not in question and "каждая школа" not in question:
        return None

    total_match = re.search(r"на\s+(\d+)\s+руб", lower)
    count_matches = [int(value) for value in re.findall(r"(\d+)\s+ящик", lower)]
    if not total_match or len(count_matches) < 2:
        return None

    total_cost = int(total_match.group(1))
    first_count, second_count = count_matches[:2]
    total_boxes = first_count + second_count
    if total_boxes == 0 or total_cost % total_boxes != 0:
        return None

    box_price = total_cost // total_boxes
    first_cost = box_price * first_count
    second_cost = box_price * second_count
    return join_explanation_lines(
        f"1) Если одна школа взяла {first_count} ящика, а другая {second_count} ящиков, то всего взяли {first_count} + {second_count} = {total_boxes} ящиков",
        f"2) Если за {total_boxes} ящиков заплатили {total_cost} руб., то один ящик стоит {total_cost} : {total_boxes} = {box_price} руб.",
        f"3) Если первая школа взяла {first_count} ящика по {box_price} руб., то она должна заплатить {box_price} × {first_count} = {first_cost} руб.",
        f"4) Если вторая школа взяла {second_count} ящиков по {box_price} руб., то она должна заплатить {box_price} × {second_count} = {second_cost} руб.",
        f"Ответ: первая школа должна заплатить {first_cost} руб., вторая — {second_cost} руб.",
        "Совет: в задачах на пропорциональное деление сначала находят общую цену одной равной части",
    )



def try_final_patch_water_bucket_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "ведр" not in lower or "одинаков" not in lower or "сколько литров" not in question:
        return None

    sizes = [int(value) for value in re.findall(r"(\d+)-литров", lower)]
    diff_match = re.search(r"на\s+(\d+)\s+литр", lower)
    if len(sizes) < 2 or not diff_match:
        return None

    big_bucket = max(sizes[0], sizes[1])
    small_bucket = min(sizes[0], sizes[1])
    diff_total = int(diff_match.group(1))
    step_diff = big_bucket - small_bucket
    if step_diff <= 0 or diff_total % step_diff != 0:
        return None

    trips = diff_total // step_diff
    big_total = big_bucket * trips
    small_total = small_bucket * trips

    if "мальчик" in lower and "девоч" in lower:
        first_label = "мальчик"
        second_label = "девочка"
        second_verb = "делала"
        second_result_verb = "принесла"
    else:
        first_label = "первый"
        second_label = "второй"
        second_verb = "делал"
        second_result_verb = "принёс"

    return join_explanation_lines(
        f"1) Если {first_label} за один раз приносил {big_bucket} л, а {second_label} {small_bucket} л, то за один раз {first_label} приносил на {big_bucket} - {small_bucket} = {step_diff} л больше",
        f"2) Если всего {first_label} принёс на {diff_total} л больше, а за один раз разница была {step_diff} л, то одинаковых ходок было {diff_total} : {step_diff} = {trips}",
        f"3) Если {first_label} делал {trips} ходок по {big_bucket} л, то он принёс {big_bucket} × {trips} = {big_total} л",
        f"4) Если {second_label} {second_verb} {trips} ходок по {small_bucket} л, то она {second_result_verb} {small_bucket} × {trips} = {small_total} л",
        f"Ответ: {first_label} принёс {big_total} л воды, {second_label} — {small_total} л.",
        "Совет: если число ходок одинаковое, сначала находят разницу за одну ходку",
    )



def try_final_patch_remaining_rooms_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "комнат" not in lower or "квартир" not in lower or "остал" not in lower:
        return None
    if "отремонт" not in question:
        return None

    total_match = re.search(r"(\d+)\s+комнат", lower)
    remain_match = re.search(r"остал[аоись]*[^0-9]{0,40}(\d+)\s+(\d+)-комнатн", lower)
    if not total_match or not remain_match:
        return None

    total_rooms = int(total_match.group(1))
    flats = int(remain_match.group(1))
    rooms_per_flat = int(remain_match.group(2))
    remaining_rooms = flats * rooms_per_flat
    repaired_rooms = total_rooms - remaining_rooms
    if repaired_rooms < 0:
        return None

    flat_word = _final_patch_plural(flats, ("квартира", "квартиры", "квартир"))
    room_word = _final_patch_plural(rooms_per_flat, ("комната", "комнаты", "комнат"))
    return join_explanation_lines(
        f"1) Если осталось отремонтировать {flats} {flat_word} по {rooms_per_flat} {room_word} в каждой, то осталось отремонтировать {flats} × {rooms_per_flat} = {remaining_rooms} комнат",
        f"2) Если всего надо было отремонтировать {total_rooms} комнаты, а осталось {remaining_rooms} комнат, то отремонтировали {total_rooms} - {remaining_rooms} = {repaired_rooms} комнат",
        f"Ответ: отремонтировали {repaired_rooms} комнат.",
        "Совет: если известны всё число и оставшаяся часть, выполненную часть находят вычитанием",
    )



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_final_patch_school_boxes_equal_price_explanation(user_text)
        or try_final_patch_water_bucket_explanation(user_text)
        or try_final_patch_remaining_rooms_explanation(user_text)
        or try_final_patch_simple_group_total_explanation(user_text)
        or _FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI FINAL CONSOLIDATION PATCH 2026-04-11N: punctuation, order marks, missing textbook templates ---

_OAI_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def extract_condition_and_question(raw_text: str) -> Tuple[str, str]:
    cleaned = normalize_word_problem_text(raw_text)
    if not cleaned:
        return "", ""

    parts = [part.strip() for part in re.findall(r"[^?.!]+[?.!]??", cleaned) if part.strip()]
    condition_parts: List[str] = []
    question_parts: List[str] = []

    for part in parts:
        lowered = part.lower().replace("ё", "е").strip()
        is_question = part.endswith("?") or bool(
            re.match(r"^(?:сколько|каков|какова|какое|какая|чему|найти|найдите|узнай|узнайте|во\s+сколько|на\s+сколько)", lowered)
        )
        if is_question:
            question_parts.append(part.rstrip())
        else:
            condition_parts.append(part.rstrip())

    if not question_parts and condition_parts:
        last = condition_parts[-1]
        lowered_last = last.lower().replace("ё", "е")
        if re.match(r"^(?:сколько|каков|какова|какое|какая|чему|найти|найдите|узнай|узнайте|во\s+сколько|на\s+сколько)", lowered_last):
            question_parts = [last.rstrip(".?!") + "?"]
            condition_parts = condition_parts[:-1]

    def _join_sentences(items: List[str], question: bool = False) -> str:
        prepared: List[str] = []
        for item in items:
            text = item.strip()
            if not text:
                continue
            if question:
                if text[-1] != "?":
                    text = text.rstrip(".!") + "?"
            else:
                if text[-1] not in ".!?":
                    text += "."
            prepared.append(text)
        joined = " ".join(prepared).strip()
        return joined

    condition = _join_sentences(condition_parts, question=False)
    question = _join_sentences(question_parts, question=True)
    if len(condition) > 280:
        condition = condition[:277].rstrip() + "..."
    if len(question) > 220:
        question = question[:217].rstrip() + "..."
    return condition, question



def _detailed_build_order_block(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return []

    pretty_parts: List[str] = []
    raw_to_pretty_op_pos: dict = {}
    current_len = 0
    for index, ch in enumerate(source):
        if ch in "+-*/":
            symbol = "×" if ch == "*" else ":" if ch == "/" else ch
            token = f" {symbol} "
            raw_to_pretty_op_pos[index] = current_len + 1
            pretty_parts.append(token)
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    pretty_expr = "".join(pretty_parts)

    marks = [" "] * len(pretty_expr)
    for step_index, step in enumerate(steps, start=1):
        raw_pos = step.get("pos")
        if raw_pos is None:
            continue
        pretty_pos = raw_to_pretty_op_pos.get(raw_pos)
        if pretty_pos is None:
            continue
        label = str(step_index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, char in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = char

    return ["Порядок действий:", "".join(marks).rstrip(), pretty_expr]



def _oai_final_question_lower(raw_text: str) -> str:
    return _question_lower_text(raw_text).lower().replace("ё", "е")



def try_oai_final_combined_rate_pump_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _oai_final_question_lower(raw_text)
    if "насос" not in lower:
        return None
    if not contains_any_fragment(question, ("за сколько", "сколько минут", "сколько мин", "за какое время")):
        return None

    first_match = re.search(r"перв(?:ый|ого)?\s+насос[^\d]{0,40}(\d+)\s+в(?:е|ё)дер[^\d]{0,40}за\s+(\d+)\s+мин", lower)
    second_time_match = re.search(r"втор(?:ой|ого)?[^\d]{0,60}за\s+(\d+)\s+мин", lower)
    nums = extract_ordered_numbers(lower)
    if not first_match or not second_time_match or len(nums) < 4:
        return None

    amount = int(first_match.group(1))
    time1 = int(first_match.group(2))
    time2 = int(second_time_match.group(1))
    target = nums[-1]
    if amount <= 0 or time1 <= 0 or time2 <= 0 or target <= 0:
        return None

    rate1 = Fraction(amount, time1)
    rate2 = Fraction(amount, time2)
    total_rate = rate1 + rate2
    if total_rate == 0:
        return None
    total_time = Fraction(target, 1) / total_rate

    rate1_text = format_fraction(rate1)
    rate2_text = format_fraction(rate2)
    total_rate_text = format_fraction(total_rate)
    total_time_text = format_fraction(total_time)

    return join_explanation_lines(
        f"1) Если первый насос выкачивает {amount} вёдер за {time1} мин, то за 1 мин он выкачивает {amount} : {time1} = {rate1_text} вёдер",
        f"2) Если второй насос выкачивает {amount} вёдер за {time2} мин, то за 1 мин он выкачивает {amount} : {time2} = {rate2_text} вёдер",
        f"3) Если оба насоса работают вместе, то за 1 мин они выкачивают {rate1_text} + {rate2_text} = {total_rate_text} вёдер",
        f"4) Если нужно выкачать {target} вёдер, а за 1 мин выкачивают {total_rate_text} вёдер, то время равно {target} : {total_rate_text} = {total_time_text} мин",
        f"Ответ: оба насоса выкачают {target} вёдер за {total_time_text} мин",
        "Совет: в задачах на совместную работу сначала находят, сколько каждый делает за 1 минуту",
    )



def try_oai_final_advanced_brigade_unit_rate_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _oai_final_question_lower(raw_text)
    if "бригада" not in lower:
        return None
    if not contains_any_fragment(question, ("сколько метров", "сколько м", "сколько километров", "сколько км")):
        return None

    source_match = re.search(r"за\s+(\d+)\s+дн(?:я|ей)[^\d]{0,60}бригада[^\d]{0,60}(\d+)\s*(м|км)", lower)
    question_match = re.search(r"(\d+)\s+бригад[^\d]{0,60}за\s+(\d+)\s+дн(?:я|ей)", lower)
    if not source_match or not question_match:
        return None

    days1 = int(source_match.group(1))
    total_amount = int(source_match.group(2))
    unit = source_match.group(3)
    brigades = int(question_match.group(1))
    days2 = int(question_match.group(2))
    if days1 <= 0 or brigades <= 0 or days2 <= 0 or total_amount <= 0:
        return None

    one_brigade_one_day = Fraction(total_amount, days1)
    many_brigades_one_day = one_brigade_one_day * brigades
    final_amount = many_brigades_one_day * days2

    d1_text = format_fraction(one_brigade_one_day)
    d2_text = format_fraction(many_brigades_one_day)
    answer_text = format_fraction(final_amount)

    return join_explanation_lines(
        f"1) Если одна бригада проложила {total_amount} {unit} за {days1} дней, то за 1 день одна бригада проложит {total_amount} : {days1} = {d1_text} {unit}",
        f"2) Если одна бригада за 1 день прокладывает {d1_text} {unit}, то {brigades} бригады за 1 день проложат {d1_text} × {brigades} = {d2_text} {unit}",
        f"3) Если {brigades} бригады за 1 день прокладывают {d2_text} {unit}, то за {days2} дней они проложат {d2_text} × {days2} = {answer_text} {unit}",
        f"Ответ: {brigades} бригады за {days2} дней проложат {answer_text} {unit}",
        "Совет: в усложнённых задачах на приведение к единице сначала находят работу одной бригады за 1 день",
    )



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_oai_final_combined_rate_pump_explanation(user_text)
        or try_oai_final_advanced_brigade_unit_rate_explanation(user_text)
        or _OAI_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI HOTFIX 2026-04-11P: reliable sentence split + combined-rate matching ---

def extract_condition_and_question(raw_text: str) -> Tuple[str, str]:
    cleaned = normalize_word_problem_text(raw_text)
    if not cleaned:
        return "", ""

    parts = [part.strip() for part in re.split(r"(?<=[.?!])\s+", cleaned) if part.strip()]
    if not parts:
        return "", ""

    condition_parts: List[str] = []
    question_parts: List[str] = []
    starter_re = re.compile(r"^(?:сколько|каков|какова|какое|какая|чему|найти|найдите|узнай|узнайте|во\s+сколько|на\s+сколько)", re.IGNORECASE)

    for part in parts:
        stripped = part.strip()
        is_question = stripped.endswith("?") or bool(starter_re.match(stripped))
        if is_question:
            question_parts.append(stripped)
        else:
            condition_parts.append(stripped)

    if not question_parts and condition_parts:
        last = condition_parts[-1]
        if starter_re.match(last):
            question_parts = [last.rstrip(".?!") + "?"]
            condition_parts = condition_parts[:-1]

    def _join(items: List[str], as_question: bool) -> str:
        out = []
        for item in items:
            text = item.strip()
            if not text:
                continue
            if as_question:
                text = text.rstrip(".!")
                if not text.endswith("?"):
                    text += "?"
            else:
                if text[-1] not in ".!?":
                    text += "."
            out.append(text)
        return " ".join(out).strip()

    condition = _join(condition_parts, False)
    question = _join(question_parts, True)
    return condition, question



def _question_lower_text(raw_text: str) -> str:
    try:
        return _question_text_only(raw_text).lower().replace("ё", "е")
    except Exception:
        _, question = extract_condition_and_question(raw_text)
        return question.lower().replace("ё", "е")



def try_oai_final_combined_rate_pump_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    if "насос" not in lower:
        return None
    if not contains_any_fragment(lower, ("за сколько", "сколько минут", "сколько мин", "за какое время", "оба насоса", "работать одновременно")):
        return None

    first_match = re.search(r"перв(?:ый|ого)?\s+насос[^\d]{0,40}(\d+)\s+в(?:е|ё)дер[^\d]{0,40}за\s+(\d+)\s+мин", lower)
    second_time_match = re.search(r"втор(?:ой|ого)?[^\d]{0,60}за\s+(\d+)\s+мин", lower)
    nums = extract_ordered_numbers(lower)
    if not first_match or not second_time_match or len(nums) < 4:
        return None

    amount = int(first_match.group(1))
    time1 = int(first_match.group(2))
    time2 = int(second_time_match.group(1))
    target = nums[-1]
    if amount <= 0 or time1 <= 0 or time2 <= 0 or target <= 0:
        return None

    rate1 = Fraction(amount, time1)
    rate2 = Fraction(amount, time2)
    total_rate = rate1 + rate2
    if total_rate == 0:
        return None
    total_time = Fraction(target, 1) / total_rate

    rate1_text = format_fraction(rate1)
    rate2_text = format_fraction(rate2)
    total_rate_text = format_fraction(total_rate)
    total_time_text = format_fraction(total_time)

    return join_explanation_lines(
        f"1) Если первый насос выкачивает {amount} вёдер за {time1} мин, то за 1 мин он выкачивает {amount} : {time1} = {rate1_text} вёдер",
        f"2) Если второй насос выкачивает {amount} вёдер за {time2} мин, то за 1 мин он выкачивает {amount} : {time2} = {rate2_text} вёдер",
        f"3) Если оба насоса работают одновременно, то за 1 мин они выкачивают {rate1_text} + {rate2_text} = {total_rate_text} вёдер",
        f"4) Если нужно выкачать {target} вёдер, а за 1 мин выкачивают {total_rate_text} вёдер, то время равно {target} : {total_rate_text} = {total_time_text} мин",
        f"Ответ: оба насоса выкачают {target} вёдер за {total_time_text} мин",
        "Совет: в задачах на совместную работу сначала находят, сколько каждый делает за 1 минуту",
    )


# --- USER PATCH 2026-04-11Z: stricter equation detection, expression with "=" support,
# --- fuller question noun extraction, and textbook-style remainder wording.

_OAI_USER_PREV_TO_EXPRESSION_SOURCE = to_expression_source
_OAI_USER_PREV_TO_EQUATION_SOURCE = to_equation_source
_OAI_USER_PREV_INFER_TASK_KIND = infer_task_kind
_OAI_USER_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_OAI_USER_PREV_EXTRACT_COUNT_QUESTION_NOUN = _extract_count_question_noun

_USER_ADJECTIVE_ENDINGS = (
    "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие",
    "ого", "его", "ому", "ему", "ым", "им", "ую", "юю",
    "ых", "их", "ыми", "ими",
)


def _user_has_standalone_x(text: str) -> bool:
    return bool(re.search(r"(?<![\d)])\s*[xXхХ]\s*(?![\d(])", str(text or "")))


def _user_has_mul_x_between_numbers(text: str) -> bool:
    return bool(re.search(r"(?<=[\d)])\s*[xXхХ]\s*(?=[\d(])", str(text or "")))


def to_equation_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")

    # Если x/х стоит между числами, это знак умножения, а не неизвестное.
    if _user_has_mul_x_between_numbers(text):
        return None

    # Разрешаем латинскую и кириллическую x только как отдельную неизвестную.
    text = re.sub(r"(?<![\d)])\s*[xXхХ]\s*(?![\d(])", "x", text)
    text = re.sub(r"\s+", "", text)

    if text.count("=") != 1 or text.count("x") != 1:
        return None
    if not re.fullmatch(r"[\dx=+\-*/]+", text):
        return None
    return text


def to_expression_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None

    text = normalize_dashes(text)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")

    # x/х между числами понимаем как умножение.
    text = re.sub(r"(?<=[\d)])\s*[xXхХ]\s*(?=[\d(])", " * ", text)

    # Если запись вида «25 х 4 = 100» или «6 + 7 = ?», берём только левую часть как пример.
    if "=" in text:
        left, right = text.split("=", 1)
        left = left.strip()
        right = right.strip()

        if not _user_has_standalone_x(left) and not _user_has_standalone_x(right):
            if not re.search(r"[A-Za-zА-Яа-я]", left.replace("х", "").replace("Х", "")):
                if right in {"", "?", "=?", "= ?"} or re.fullmatch(r"[\d\s()+\-*/.,]+", right):
                    text = left
                else:
                    return None
            else:
                return None
        else:
            return None

    text = re.sub(r"\s*\?\s*$", "", text).strip()
    if re.search(r"[A-Za-zА-Яа-я]", text):
        return None
    if not re.fullmatch(r"[\d\s()+\-*/]+", text):
        return None

    compact = re.sub(r"\s+", "", text)
    if not compact or not re.search(r"[+\-*/]", compact):
        return None
    return compact


def infer_task_kind(text: str) -> str:
    base = strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()

    if re.search(r"\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+", lowered):
        return "fraction"
    if to_equation_source(text):
        return "equation"
    if re.search(r"периметр|площадь|прямоугольник|квадрат|треугольник|сторон|длина|ширина", lowered):
        return "geometry"
    if re.search(r"[а-я]", lowered):
        return "word"
    if to_expression_source(text):
        return "expression"
    if re.search(r"[+\-*/()×÷:=]", lowered):
        return "expression"
    return "other"


def _extract_count_question_noun(raw_text: str) -> str:
    noun = _OAI_USER_PREV_EXTRACT_COUNT_QUESTION_NOUN(raw_text)
    if noun in QUESTION_NOUN_FORMS or noun in MEASURE_QUESTION_NOUNS or noun == "раз":
        return noun

    question = _question_lower_text(raw_text)
    patterns = [
        r"^сколько\s+(?:было\s+|будет\s+|стало\s+|осталось\s+|получилось\s+|понадобится\s+|понадобилось\s+|потребуется\s+|потребовалось\s+|можно\s+купить\s+|нужно\s+|нужно\s+купить\s+|всего\s+)?(?:таких\s+|этих\s+|эти\s+)?([а-яё]+)\s+([а-яё]+)",
        r"^во\s+сколько\s+раз\s+([а-яё]+)\s+([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if not match:
            continue
        first = match.group(1).strip().lower().replace("ё", "е")
        second = match.group(2).strip().lower().replace("ё", "е")

        if second in QUESTION_NOUN_FORMS:
            if first.endswith(_USER_ADJECTIVE_ENDINGS) or first not in QUESTION_NOUN_FORMS:
                return second

    return noun


def _user_question_asks_remaining(raw_text: str) -> bool:
    question = _question_lower_text(raw_text)
    return bool(
        re.search(
            r"(?:сколько|какое|какова?|чему)\b[^.?!]*\b(остал(?:ось|ось|ся|ись|ись)|останется|осталось\s+прочитать|осталось\s+проехать|осталось\s+расфасовать)\b",
            question,
        )
    )


def _user_remaining_question_phrase(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    if "прочитать" in question:
        return "осталось прочитать"
    if "проехать" in question:
        return "осталось проехать"
    if "расфасовать" in question:
        return "осталось расфасовать"
    return "осталось"


def try_user_patch_simple_remaining_explanation(raw_text: str) -> Optional[str]:
    lower = _statement_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 2 or "сколько" not in lower:
        return None
    if not _user_question_asks_remaining(raw_text):
        return None

    first, second = nums[0], nums[1]
    if first < second:
        return None

    answer_text = _patch_answer_with_question_noun(first - second, raw_text)
    phrase = _user_remaining_question_phrase(raw_text)

    return join_explanation_lines(
        f"1) Если всего было {first}, а использовали {second}, то {phrase} {first} - {second} = {answer_text}",
        f"Ответ: {phrase} {answer_text}",
        "Совет: чтобы найти остаток, из всего вычитают использованную часть",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_simple_remaining_explanation(user_text)
        or _OAI_USER_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )



# --- USER PATCH 2026-04-11ZA: fuller counted answers like "4 яблока", "3 страницы".

_OAI_USER_PREV_PATCH_ANSWER_WITH_QUESTION_NOUN = _patch_answer_with_question_noun

def _patch_answer_with_question_noun(value: int, raw_text: str) -> str:
    unit = _detect_question_unit(raw_text) or ""
    if unit:
        return f"{value} {unit}".strip()

    noun = _extract_count_question_noun(raw_text) or _extract_question_noun(raw_text)
    if noun:
        if noun == "раз":
            return f"{value} раз"
        forms = _lookup_question_noun_forms(noun)
        if forms:
            try:
                count_value = int(value)
            except Exception:
                return f"{value} {noun}".strip()
            return f"{value} {_select_plural_by_count(count_value, forms)}"
        try:
            count_value = int(value)
        except Exception:
            count_value = None
        if count_value is not None and _can_use_raw_plural_noun_with_count(count_value):
            return f"{value} {noun}".strip()
    return str(value)



# --- OPENAI USER PATCH 2026-04-11R: textbook priority fixes from uploaded books ---

_OAI_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_R = build_explanation_local_first
_OAI_PATCH_PREV_EXTRACT_COUNT_QUESTION_NOUN_R = _extract_count_question_noun
_OAI_PATCH_PREV_DETECT_QUESTION_UNIT_R = _detect_question_unit

QUESTION_NOUN_FORMS.update({
    "фруктов": ("фрукт", "фрукта", "фруктов"),
    "листов": ("лист", "листа", "листов"),
    "перьев": ("перо", "пера", "перьев"),
    "мешков": ("мешок", "мешка", "мешков"),
    "кустов": ("куст", "куста", "кустов"),
    "цветов": ("цветок", "цветка", "цветов"),
    "глазков": ("глазок", "глазка", "глазков"),
    "пакетов": ("пакет", "пакета", "пакетов"),
    "наборов": ("набор", "набора", "наборов"),
    "деталей": ("деталь", "детали", "деталей"),
    "фломастеров": ("фломастер", "фломастера", "фломастеров"),
    "персиков": ("персик", "персика", "персиков"),
    "груш": ("груша", "груши", "груш"),
    "магнитофонов": ("магнитофон", "магнитофона", "магнитофонов"),
    "видеоплееров": ("видеоплеер", "видеоплеера", "видеоплееров"),
})

_OAI_PATCH_STOP_QUESTION_WORDS_R = {
    "всего", "вместе", "нужно", "можно", "будет", "было", "стало", "останется",
    "осталось", "получилось", "понадобится", "понадобилось", "потребуется",
    "потребовалось", "такой", "таких", "такие", "этих", "эти", "этой", "этом",
}
_OAI_PATCH_ADJECTIVE_ENDINGS_R = (
    "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие",
    "ого", "его", "ому", "ему", "ым", "им", "ую", "юю",
    "ых", "их", "ыми", "ими", "ой", "ей",
)


def _oai_patch_is_likely_adjective_r(word: str) -> bool:
    value = str(word or "").strip().lower().replace("ё", "е")
    return bool(value) and value.endswith(_OAI_PATCH_ADJECTIVE_ENDINGS_R)


def _extract_count_question_noun(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    if question:
        if re.search(r"\bво\s+сколько\s+раз\b", question):
            return "раз"

        patterns = [
            r"^сколько\s+(?:было\s+|будет\s+|стало\s+|останется\s+|осталось\s+|осталось\s+\w+\s+|получилось\s+|понадобится\s+|понадобилось\s+|потребуется\s+|потребовалось\s+|можно\s+купить\s+|нужно\s+|нужно\s+купить\s+|всего\s+)?([а-яё]+)",
            r"^на\s+сколько\s+([а-яё]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if not match:
                continue
            noun = match.group(1).strip().lower().replace("ё", "е")
            if noun and noun not in _OAI_PATCH_STOP_QUESTION_WORDS_R and not _oai_patch_is_likely_adjective_r(noun):
                return noun

    prev_noun = _OAI_PATCH_PREV_EXTRACT_COUNT_QUESTION_NOUN_R(raw_text)
    return prev_noun or ""


def _detect_question_unit(raw_text: str) -> str:
    unit = _OAI_PATCH_PREV_DETECT_QUESTION_UNIT_R(raw_text)
    if unit:
        return unit

    question = _question_lower_text(raw_text)
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if re.search(r"(?:какое|какова?|сколько)\s+врем(?:я|ени)", question):
        if "м/с" in lower_full or re.search(r"\bсек\b|секунд|секунда|секунды|\bс\b", lower_full):
            return "с"
        if "м/мин" in lower_full or re.search(r"\bмин\b|минут|минута|минуты", lower_full):
            return "мин"
        return "ч"

    if re.search(r"\bна\s+сколько\b", question) and re.search(r"\bдороже\b|\bдешевле\b", question):
        if "руб" in lower_full or "коп" in lower_full:
            return "руб."

    return ""


def _oai_patch_extract_question_item_r(raw_text: str) -> str:
    question = _question_lower_text(raw_text)
    patterns = [
        r"сколько\s+стоил(?:а|о|и)?\s+([а-яё]+)",
        r"сколько\s+стоит\s+([а-яё]+)",
        r"сколько\s+книг\s+было\s+на\s+([а-яё]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1).strip()
    return ""


def _oai_patch_text_has_fraction_r(text: str) -> bool:
    return bool(re.search(r"\d+\s*/\s*\d+", str(text or "")))


def try_oai_patch_unknown_addend_rest_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 2:
        return None
    if "из них" not in lower or "осталь" not in lower:
        return None
    if "на сколько" in question or "во сколько" in question:
        return None
    if "сколько" not in question:
        return None

    total, known = nums[0], nums[1]
    if total < known:
        return None

    result = total - known
    answer_text = _patch_answer_with_question_noun(result, raw_text)
    return join_explanation_lines(
        f"1) Если всего было {total}, а известная часть равна {known}, то другая часть равна {total} - {known} = {answer_text}",
        f"Ответ: {answer_text}",
        "Совет: чтобы найти неизвестную часть, из целого вычитают известную часть",
    )


def try_oai_patch_simple_total_minus_part_money_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 2:
        return None
    if not contains_any_fragment(lower, ("заплатил", "заплатила", "заплатили", "стоил", "стоила", "стоило")):
        return None
    if not contains_any_fragment(question, ("сколько стоила", "сколько стоил", "сколько стоило", "сколько стоит")):
        return None
    if "по" in lower:
        return None

    total_cost, known_cost = nums[0], nums[1]
    if total_cost < known_cost:
        return None

    result = total_cost - known_cost
    item = _oai_patch_extract_question_item_r(raw_text) or "неизвестная часть"
    return join_explanation_lines(
        f"1) Если за всю покупку заплатили {total_cost} руб., а известная часть стоила {known_cost} руб., то {item} стоил{'' if item.endswith('о') else 'а' if item.endswith('а') else ''} {total_cost} - {known_cost} = {result} руб.",
        f"Ответ: {item} стоил{'' if item.endswith('о') else 'а' if item.endswith('а') else ''} {result} руб.",
        "Совет: если известна общая стоимость и одна часть, другую часть находят вычитанием",
    )


def try_oai_patch_simple_motion_time_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)

    if not re.search(r"(?:какое|какова?|сколько)\s+врем(?:я|ени)|сколько\s+час", question):
        return None

    distance_values = [int(v) for v in re.findall(r"(\d+)\s*(?:км|м)(?!/)", lower)]
    speed_values = [int(v) for v in re.findall(r"(\d+)\s*(?:км/ч|м/мин|м/с)", lower)] or [int(v) for v in re.findall(r"скорост[ьяию][^\d]{0,20}(\d+)", lower)]

    if len(distance_values) != 1 or len(speed_values) != 1:
        return None
    if len(re.findall(r"\d+\s*(?:км|м)(?!/)", lower)) != 1:
        return None

    distance = distance_values[0]
    speed = speed_values[0]
    if speed <= 0 or distance < 0 or distance % speed != 0:
        return None

    time_value = distance // speed
    distance_unit = "км" if re.search(r"\d+\s*км(?!/)", lower) else "м"
    speed_unit = "км/ч" if "км/ч" in lower else "м/мин" if "м/мин" in lower else "м/с" if "м/с" in lower else "ед./ч"
    time_unit = "ч"
    if speed_unit == "м/мин":
        time_unit = "мин"
    elif speed_unit == "м/с":
        time_unit = "с"

    return join_explanation_lines(
        f"1) Если путь равен {distance} {distance_unit}, а скорость равна {speed} {speed_unit}, то время равно {distance} : {speed} = {time_value} {time_unit}",
        f"Ответ: время в пути равно {time_value} {time_unit}",
        "Совет: чтобы найти время, расстояние делят на скорость",
    )


def try_oai_patch_price_compare_logic_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 3:
        return None
    if "за столько же" not in lower:
        return None
    if not (contains_any_fragment(question, ("на сколько", "дороже")) or contains_any_fragment(question, ("на сколько", "дешевле"))):
        return None

    quantity, cost_first, cost_second = nums
    if quantity <= 0 or cost_first % quantity != 0 or cost_second % quantity != 0:
        return None

    price_first = cost_first // quantity
    price_second = cost_second // quantity
    diff = abs(price_first - price_second)

    package_items = re.findall(r"пакет(?:ов|а)?\s+([а-яё]+)", lower)
    if len(package_items) >= 2:
        first_name = f"пакет {package_items[0]}"
        second_name = f"пакет {package_items[1]}"
    else:
        first_name = "первый товар"
        second_name = "второй товар"

    if price_first > price_second:
        relation_text = f"{first_name} дороже {second_name} на {diff} руб."
    elif price_second > price_first:
        relation_text = f"{second_name} дороже {first_name} на {diff} руб."
    else:
        relation_text = "цены одинаковые"

    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых пакетов первого товара заплатили {cost_first} руб., то один пакет стоит {cost_first} : {quantity} = {price_first} руб.",
        f"2) Если за {quantity} таких же пакетов второго товара заплатили {cost_second} руб., то один пакет стоит {cost_second} : {quantity} = {price_second} руб.",
        f"3) Если одна цена равна {price_first} руб., а другая {price_second} руб., то разность цен равна {max(price_first, price_second)} - {min(price_first, price_second)} = {diff} руб.",
        f"Ответ: разность в цене равна {diff} руб.; {relation_text}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_oai_patch_unknown_addend_rest_explanation_r(user_text)
        or try_oai_patch_simple_total_minus_part_money_explanation_r(user_text)
        or try_oai_patch_simple_motion_time_explanation_r(user_text)
        or try_oai_patch_price_compare_logic_explanation_r(user_text)
        or _OAI_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_R(user_text, kind)
    )



# --- OPENAI HOTFIX 2026-04-11S: "на сколько" answers and cleaner price comparison wording ---

_OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_S = _detailed_maybe_enrich_answer

def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_S(answer, raw_text, kind)
    question = _question_lower_text(raw_text)
    if question.startswith("на сколько") and value and not re.search(r"[А-Яа-я].*[А-Яа-я].*[А-Яа-я]", value):
        if not value.startswith("на "):
            return f"на {value}"
    return value


def try_oai_patch_price_compare_logic_explanation_r(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)

    if len(nums) != 3:
        return None
    if "за столько же" not in lower:
        return None
    if not (contains_any_fragment(question, ("на сколько", "дороже")) or contains_any_fragment(question, ("на сколько", "дешевле"))):
        return None

    quantity, cost_first, cost_second = nums
    if quantity <= 0 or cost_first % quantity != 0 or cost_second % quantity != 0:
        return None

    price_first = cost_first // quantity
    price_second = cost_second // quantity
    diff = abs(price_first - price_second)

    package_items = re.findall(r"пакет(?:ов|а)?\s+([а-яё]+)", lower)
    if len(package_items) >= 2:
        first_name = f"пакет {package_items[0]}"
        second_name = f"пакет {package_items[1]}"
        first_name_gen = f"пакета {package_items[0]}"
        second_name_gen = f"пакета {package_items[1]}"
    else:
        first_name = "первый товар"
        second_name = "второй товар"
        first_name_gen = "первого товара"
        second_name_gen = "второго товара"

    if price_first > price_second:
        relation_text = f"{first_name} дороже {second_name_gen} на {diff} руб."
    elif price_second > price_first:
        relation_text = f"{second_name} дороже {first_name_gen} на {diff} руб."
    else:
        relation_text = "цены одинаковые"

    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых пакетов первого товара заплатили {cost_first} руб., то один пакет стоит {cost_first} : {quantity} = {price_first} руб.",
        f"2) Если за {quantity} таких же пакетов второго товара заплатили {cost_second} руб., то один пакет стоит {cost_second} : {quantity} = {price_second} руб.",
        f"3) Если одна цена равна {price_first} руб., а другая {price_second} руб., то разность цен равна {max(price_first, price_second)} - {min(price_first, price_second)} = {diff} руб.",
        f"Ответ: разность в цене равна {diff} руб.; {relation_text}",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )



# --- OPENAI HOTFIX 2026-04-11T: prefix "на" for direct comparison numeric answers ---

_OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_T = _detailed_maybe_enrich_answer

def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _OAI_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_T(answer, raw_text, kind)
    question = _question_lower_text(raw_text)
    if question.startswith("на сколько") and re.fullmatch(r"-?\d+(?:/\d+)?(?:\s+[А-Яа-я./²]+)?", value or ""):
        if not value.startswith("на "):
            return f"на {value}"
    return value



# --- CHATGPT FINAL PATCH 2026-04-11U: stronger textbook routing, missing unit-rate cases, safer compare logic ---

_CHATGPT_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST_U = build_explanation_local_first
_CHATGPT_FINAL_PREV_EXPLAIN_SIMPLE_ADDITION_U = explain_simple_addition

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши строку:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. По возможности используй школьную форму:
Если ..., то ...
8. После каждого действия коротко говори, что нашли.
9. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это выражение, сначала назови порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это дроби, сначала смотри на знаменатели.
Если это геометрия, сначала назови формулу, потом подставь числа.
Если это именованные величины, сначала переведи их в одинаковые единицы.

Используй школьные приёмы:
сложение через десяток — разложи число так, чтобы сначала получить 10 или следующее круглое число;
вычитание через десяток — вычитай по частям через 10;
двузначные числа раскладывай на десятки и единицы;
если числа большие, объясняй по разрядам;
если в сумме больше двух двузначных чисел или есть хотя бы одно трёхзначное число, можно показывать вычисление в столбик;
для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()


def explain_simple_addition(left: int, right: int) -> str:
    big = max(left, right)
    small = min(left, right)
    if 10 <= big <= 99 and 1 <= small <= 99:
        jump = (10 - (big % 10)) % 10
        if jump == 0:
            jump = 10
        if 0 < jump < small:
            rounded = big + jump
            rest = small - jump
            total = left + right
            return join_explanation_lines(
                "Ищем сумму",
                f"Сначала удобно дойти от {big} до следующего круглого числа {rounded}",
                f"Для этого нужно прибавить {jump}",
                f"Разложим {small} на {jump} и {rest}",
                f"{big} + {jump} = {rounded}",
                f"{rounded} + {rest} = {total}",
                f"Ответ: {total}",
                "Совет: если сумма переходит через десяток, удобно сначала дойти до круглого числа",
            )
    return _CHATGPT_FINAL_PREV_EXPLAIN_SIMPLE_ADDITION_U(left, right)


def try_chatgpt_final_relation_then_compare_explanation_u(raw_text: str) -> Optional[str]:
    try:
        return try_priority_relation_then_compare_explanation(raw_text)
    except Exception:
        return None


def try_chatgpt_final_beam_weight_explanation_u(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "сколько" not in question or not contains_any_fragment(question, ("сколько весит", "какова масса", "чему равна масса")):
        return None

    pattern = re.compile(
        r"(?:длиной|длина)\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)[^?.!]{0,80}?весит\s*(\d+)\s*(кг|г|т)[^?.!]{0,160}?(?:длиной|длина)\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)",
        re.IGNORECASE,
    )
    match = pattern.search(lower)
    if not match:
        pattern2 = re.compile(
            r"(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)[^?.!]{0,60}?весит\s*(\d+)\s*(кг|г|т)[^?.!]{0,160}?(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)",
            re.IGNORECASE,
        )
        match = pattern2.search(lower)
        if not match:
            return None

    base_len = int(match.group(1))
    len_unit_1 = match.group(2)
    total_weight = int(match.group(3))
    weight_unit = match.group(4)
    target_len = int(match.group(5))
    len_unit_2 = match.group(6)

    if base_len <= 0 or total_weight < 0:
        return None
    if len_unit_1[0] != len_unit_2[0]:
        return None
    if total_weight % base_len != 0:
        return None

    per_unit = total_weight // base_len
    result = per_unit * target_len
    length_name = "метр"
    if len_unit_1.startswith("д"):
        length_name = "дециметр"
    elif len_unit_1.startswith("с"):
        length_name = "сантиметр"
    elif len_unit_1.startswith("к"):
        length_name = "километр"

    return join_explanation_lines(
        f"1) Если {base_len} {len_unit_1} этой же балки весят {total_weight} {weight_unit}, то один {length_name} весит {total_weight} : {base_len} = {per_unit} {weight_unit}",
        f"2) Если один {length_name} весит {per_unit} {weight_unit}, то {target_len} {len_unit_2} весят {per_unit} × {target_len} = {result} {weight_unit}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну одинаковую часть",
    )


def try_chatgpt_final_sum_then_relation_to_sum_explanation_u(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    nums = extract_ordered_numbers(lower)
    if len(nums) != 3 or "сколько" not in question:
        return None
    if has_multiple_questions(raw_text):
        return None
    if "вместе" not in lower:
        return None

    first, second, third_number = nums[0], nums[1], nums[2]
    together = first + second

    same_match = re.search(r"столько(?:\s+же)?[, ]+сколько[^?.!]{0,120}?вместе", lower)
    delta_match = re.search(r"на\s+(\d+)[^?.!]{0,20}?(больше|меньше)[^?.!]{0,120}?вместе", lower)
    scale_match = re.search(r"в\s+(\d+)\s+раз(?:а)?\s+(больше|меньше)[^?.!]{0,120}?вместе", lower)

    if same_match:
        result = together
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то вместе {first} + {second} = {together}",
            f"2) Если искомое количество столько же, сколько эти два количества вместе, то оно равно {together}",
            f"Ответ: {result}",
            "Совет: если искомое число сравнивают с суммой двух чисел, сначала находят эту сумму",
        )

    if delta_match:
        delta = int(delta_match.group(1))
        mode = delta_match.group(2)
        if delta != third_number:
            return None
        result = apply_more_less(together, delta, mode)
        if result is None:
            return None
        op = "+" if mode == "больше" else "-"
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то вместе {first} + {second} = {together}",
            f"2) Если искомое количество на {delta} {mode}, чем эти два количества вместе, то {together} {op} {delta} = {result}",
            f"Ответ: {result}",
            "Совет: если искомое число сравнивают с суммой двух чисел, сначала находят эту сумму",
        )

    if scale_match:
        factor = int(scale_match.group(1))
        mode = scale_match.group(2)
        if factor != third_number:
            return None
        result = apply_times_relation(together, factor, mode)
        if result is None:
            return None
        op = "×" if mode == "больше" else ":"
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то вместе {first} + {second} = {together}",
            f"2) Если искомое количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем эти два количества вместе, то {together} {op} {factor} = {result}",
            f"Ответ: {result}",
            "Совет: если искомое число сравнивают с суммой двух чисел, сначала находят эту сумму",
        )

    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_chatgpt_final_relation_then_compare_explanation_u(user_text)
        or try_chatgpt_final_beam_weight_explanation_u(user_text)
        or try_chatgpt_final_sum_then_relation_to_sum_explanation_u(user_text)
        or _CHATGPT_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST_U(user_text, kind)
    )


# --- CHATGPT HOTFIX 2026-04-11V: beam unit-rate and fuller ratio answers ---

_CHATGPT_HOTFIX_PREV_RELATION_COMPARE_V = try_chatgpt_final_relation_then_compare_explanation_u
_CHATGPT_HOTFIX_PREV_BEAM_EXPLANATION_V = try_chatgpt_final_beam_weight_explanation_u
_CHATGPT_HOTFIX_PREV_BUILD_EXPLANATION_LOCAL_FIRST_V = build_explanation_local_first


def try_chatgpt_final_relation_then_compare_explanation_u(raw_text: str) -> Optional[str]:
    text = _CHATGPT_HOTFIX_PREV_RELATION_COMPARE_V(raw_text)
    if not text:
        return text
    text = re.sub(r"^Ответ:\s*(\d+)\s+(раз|раза)\b", r"Ответ: в \1 \2", text, flags=re.MULTILINE)
    return text


def try_chatgpt_final_beam_weight_explanation_u(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "сколько" not in question or "вес" not in question:
        return None

    patterns = [
        re.compile(r"балк[а-я]*\s+длиной\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км).*?весит\s*(\d+)\s*(кг|г|т).*?длиной\s*(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)", re.IGNORECASE),
        re.compile(r"(\d+)\s*(м|метр(?:а|ов)?|дм|см|км).*?весит\s*(\d+)\s*(кг|г|т).*?(\d+)\s*(м|метр(?:а|ов)?|дм|см|км)", re.IGNORECASE),
    ]

    match = None
    for pattern in patterns:
        match = pattern.search(lower)
        if match:
            break
    if not match:
        return None

    base_len = int(match.group(1))
    len_unit_1 = match.group(2)
    total_weight = int(match.group(3))
    weight_unit = match.group(4)
    target_len = int(match.group(5))
    len_unit_2 = match.group(6)

    unit_key_1 = len_unit_1[0]
    unit_key_2 = len_unit_2[0]
    if base_len <= 0 or total_weight < 0 or unit_key_1 != unit_key_2:
        return None
    if total_weight % base_len != 0:
        return None

    per_unit = total_weight // base_len
    result = per_unit * target_len
    length_name = "метр"
    if unit_key_1 == "д":
        length_name = "дециметр"
    elif unit_key_1 == "с":
        length_name = "сантиметр"
    elif unit_key_1 == "к":
        length_name = "километр"

    return join_explanation_lines(
        f"1) Если {base_len} {len_unit_1} такой же балки весят {total_weight} {weight_unit}, то один {length_name} весит {total_weight} : {base_len} = {per_unit} {weight_unit}",
        f"2) Если один {length_name} весит {per_unit} {weight_unit}, то {target_len} {len_unit_2} весят {per_unit} × {target_len} = {result} {weight_unit}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну одинаковую часть",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_chatgpt_final_relation_then_compare_explanation_u(user_text)
        or try_chatgpt_final_beam_weight_explanation_u(user_text)
        or try_chatgpt_final_sum_then_relation_to_sum_explanation_u(user_text)
        or _CHATGPT_HOTFIX_PREV_BUILD_EXPLANATION_LOCAL_FIRST_V(user_text, kind)
    )


# --- CHATGPT HOTFIX 2026-04-11W: better unit detection from the question ---

_CHATGPT_HOTFIX_PREV_DETECT_QUESTION_UNIT_W = _detect_question_unit


def _detect_question_unit(raw_text: str) -> str:
    unit = _CHATGPT_HOTFIX_PREV_DETECT_QUESTION_UNIT_W(raw_text)
    if unit:
        return unit

    question = _question_lower_text(raw_text)
    statement = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    if contains_any_fragment(question, ("сколько весит", "какова масса", "чему равна масса")):
        for candidate in ("т", "кг", "г"):
            if re.search(rf"(?<!/)\b{re.escape(candidate)}\b", statement):
                return candidate

    if contains_any_fragment(question, ("сколько метров", "сколько километров", "какова длина", "чему равна длина", "сколько м", "сколько км", "сколько см", "сколько дм")):
        for candidate in ("км", "м", "дм", "см", "мм"):
            if re.search(rf"(?<!/)\b{re.escape(candidate)}\b", statement):
                return candidate

    if contains_any_fragment(question, ("сколько литров", "сколько л", "каков объем", "каков объём", "чему равен объем", "чему равен объём")):
        for candidate in ("л", "мл"):
            if re.search(rf"(?<!/)\b{re.escape(candidate)}\b", statement):
                return candidate

    return ""


# --- OPENAI CONSOLIDATION PATCH 2026-04-11Z: restore textbook cases lost in late patch chain ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. По возможности используй школьную форму:
Если ..., то ...
8. После каждого действия коротко говори, что нашли.
9. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Если задача дана с именованными величинами, сначала переведи их в удобные одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Сохраняй вычисления в столбик и пояснения.
Если в вычислении больше двух двузначных чисел или есть хотя бы одно трёхзначное число, можно показывать вычисление в столбик.
Для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

_CONSOLIDATION_PREV_BUILD_EXPLANATION_LOCAL_FIRST_Z = build_explanation_local_first

_CONSOLIDATION_EXTRA_QUESTION_NOUN_FORMS_Z = {
    "тюльпанов": ("тюльпан", "тюльпана", "тюльпанов"),
    "километров": ("километр", "километра", "километров"),
    "метров": ("метр", "метра", "метров"),
    "сантиметров": ("сантиметр", "сантиметра", "сантиметров"),
    "дециметров": ("дециметр", "дециметра", "дециметров"),
    "миллиметров": ("миллиметр", "миллиметра", "миллиметров"),
    "килограммов": ("килограмм", "килограмма", "килограммов"),
    "граммов": ("грамм", "грамма", "граммов"),
    "литров": ("литр", "литра", "литров"),
    "рублей": ("рубль", "рубля", "рублей"),
    "руб": ("рубль", "рубля", "рублей"),
    "часов": ("час", "часа", "часов"),
    "минут": ("минута", "минуты", "минут"),
    "тетрадей": ("тетрадь", "тетради", "тетрадей"),
    "ручек": ("ручка", "ручки", "ручек"),
    "машин": ("машина", "машины", "машин"),
    "страниц": ("страница", "страницы", "страниц"),
    "цветов": ("цветок", "цветка", "цветов"),
    "яблок": ("яблоко", "яблока", "яблок"),
    "груш": ("груша", "груши", "груш"),
    "булочек": ("булочка", "булочки", "булочек"),
    "кг": ("килограмм", "килограмма", "килограммов"),
    "л": ("литр", "литра", "литров"),
}


def _consolidation_normalize_noun_key_z(noun: str) -> str:
    return str(noun or "").strip().lower().replace("ё", "е")


def _consolidation_lookup_forms_z(noun: str) -> Optional[Tuple[str, str, str]]:
    key = _consolidation_normalize_noun_key_z(noun)
    if not key:
        return None
    forms = None
    try:
        forms = _lookup_question_noun_forms(key)
    except Exception:
        forms = None
    if forms:
        return forms
    return _CONSOLIDATION_EXTRA_QUESTION_NOUN_FORMS_Z.get(key)


def _consolidation_phrase_with_noun_z(count_value: int, noun: str) -> str:
    forms = _consolidation_lookup_forms_z(noun)
    if forms:
        return f"{count_value} {_select_plural_by_count(int(count_value), forms)}"
    return str(count_value)


def _consolidation_capitalize_z(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return value
    return value[:1].upper() + value[1:]


def _consolidation_split_question_parts_z(raw_text: str) -> List[str]:
    try:
        _, question = extract_condition_and_question(raw_text)
    except Exception:
        question = str(raw_text or "")
    return [part.strip() for part in re.split(r"\?", question) if part.strip()]


def _consolidation_answer_from_first_question_z(question_text: str, value: int, noun_hint: str = "") -> str:
    q = str(question_text or "").strip().rstrip("?.!").lower().replace("ё", "е")

    match = re.match(
        r"сколько\s+([а-яё]+)\s+(было|стало|будет|осталось|останется|получилось|оказалось|росло|лежало|ехало|шло|стоит|стоило|нужно|надо)\s+(.+)$",
        q,
    )
    if match:
        noun, verb, tail = match.groups()
        return f"{_consolidation_capitalize_z(tail)} {verb} {_consolidation_phrase_with_noun_z(value, noun)}"

    match = re.match(r"сколько\s+([а-яё]+)\s+(.+)$", q)
    if match:
        noun, tail = match.groups()
        first_word = tail.split()[0] if tail.split() else ""
        if first_word in {"в", "во", "на", "у", "из", "до", "после", "под", "над", "около"}:
            return f"{_consolidation_capitalize_z(tail)} было {_consolidation_phrase_with_noun_z(value, noun)}"
        return f"{_consolidation_capitalize_z(tail)} — {_consolidation_phrase_with_noun_z(value, noun)}"

    return _consolidation_phrase_with_noun_z(value, noun_hint)


def _consolidation_answer_from_compare_question_z(question_text: str, value: int, noun_hint: str = "") -> str:
    q = str(question_text or "").strip().rstrip("?.!").lower().replace("ё", "е")

    match = re.match(r"на\s+сколько\s+([а-яё]+)\s+(.+?)\s+(больше|меньше)(?:,?\s+чем\s+.+)?$", q)
    if match:
        noun, tail, mode = match.groups()
        return f"{_consolidation_capitalize_z(tail)} на {_consolidation_phrase_with_noun_z(value, noun)} {mode}"

    match = re.match(r"во\s+сколько\s+раз\s+([а-яё]+)\s+(.+?)\s+(больше|меньше)(?:,?\s+чем\s+.+)?$", q)
    if match:
        _, tail, mode = match.groups()
        return f"{_consolidation_capitalize_z(tail)} в {value} {plural_form(int(value), 'раз', 'раза', 'раз')} {mode}"

    if q.startswith("на сколько"):
        return f"Разность равна {_consolidation_phrase_with_noun_z(value, noun_hint)}"
    if q.startswith("во сколько"):
        return f"Отношение равно {value} {plural_form(int(value), 'раз', 'раза', 'раз')}"

    return _consolidation_phrase_with_noun_z(value, noun_hint)


def try_consolidation_direct_relation_multianswer_explanation_z(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if not has_multiple_questions(raw_text):
        return None
    if "на сколько" not in question and "во сколько" not in question:
        return None

    if re.search(r"\b(?:это|что|он|она)\b[^?.!]{0,40}(?:на\s+\d+|в\s+\d+\s+раз(?:а)?)", lower):
        return None

    numbers = extract_ordered_numbers(lower)
    if len(numbers) != 2:
        return None

    question_parts = _consolidation_split_question_parts_z(raw_text)
    first_question = question_parts[0] if question_parts else ""
    second_question = question_parts[1] if len(question_parts) > 1 else ""
    noun_hint = ""
    try:
        noun_hint = _extract_count_question_noun(raw_text) or _extract_question_noun(raw_text)
    except Exception:
        noun_hint = ""

    relation_pairs = extract_relation_pairs(lower)
    if len(relation_pairs) == 1:
        base = numbers[0]
        delta, mode = relation_pairs[0]
        if numbers[1] != delta:
            return None
        related = apply_more_less(base, delta, mode)
        if related is None:
            return None

        first_answer = _consolidation_answer_from_first_question_z(first_question, related, noun_hint)

        if "на сколько" in question:
            diff = abs(base - related)
            second_answer = _consolidation_answer_from_compare_question_z(second_question, diff, noun_hint)
            return join_explanation_lines(
                f"1) Если первое количество равно {base}, а второе на {delta} {mode}, то второе количество равно {base} {'+' if mode == 'больше' else '-'} {delta} = {related}",
                f"2) Если первое количество равно {base}, а второе равно {related}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
                f"Ответ: {first_answer}; {second_answer}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )

        smaller = min(base, related)
        bigger = max(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        second_answer = _consolidation_answer_from_compare_question_z(second_question, ratio, noun_hint)
        return join_explanation_lines(
            f"1) Если первое количество равно {base}, а второе на {delta} {mode}, то второе количество равно {base} {'+' if mode == 'больше' else '-'} {delta} = {related}",
            f"2) Если первое количество равно {base}, а второе равно {related}, то большее число делим на меньшее: {bigger} : {smaller} = {ratio}",
            f"Ответ: {first_answer}; {second_answer}",
            "Совет: если нужно сначала найти второе число, а потом узнать во сколько раз одно больше другого, выполняй действия по порядку",
        )

    scale_pairs = extract_scale_pairs(lower)
    if len(scale_pairs) == 1:
        base = numbers[0]
        factor, mode = scale_pairs[0]
        if numbers[1] != factor:
            return None
        related = apply_times_relation(base, factor, mode)
        if related is None:
            return None

        first_answer = _consolidation_answer_from_first_question_z(first_question, related, noun_hint)

        if "на сколько" in question:
            diff = abs(base - related)
            second_answer = _consolidation_answer_from_compare_question_z(second_question, diff, noun_hint)
            return join_explanation_lines(
                f"1) Если первое количество равно {base}, а второе в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} {mode}, то второе количество равно {base} {'×' if mode == 'больше' else ':'} {factor} = {related}",
                f"2) Если первое количество равно {base}, а второе равно {related}, то разность равна {max(base, related)} - {min(base, related)} = {diff}",
                f"Ответ: {first_answer}; {second_answer}",
                "Совет: если сначала нужно найти второе число, а потом сравнить, выполняй действия по порядку",
            )

        smaller = min(base, related)
        bigger = max(base, related)
        if smaller == 0 or bigger % smaller != 0:
            return None
        ratio = bigger // smaller
        second_answer = _consolidation_answer_from_compare_question_z(second_question, ratio, noun_hint)
        return join_explanation_lines(
            f"1) Если первое количество равно {base}, а второе в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} {mode}, то второе количество равно {base} {'×' if mode == 'больше' else ':'} {factor} = {related}",
            f"2) Если первое количество равно {base}, а второе равно {related}, то большее число делим на меньшее: {bigger} : {smaller} = {ratio}",
            f"Ответ: {first_answer}; {second_answer}",
            "Совет: если сначала нужно найти второе число, а потом узнать во сколько раз одно больше другого, выполняй действия по порядку",
        )

    return None


def try_consolidation_fraction_named_unit_explanation_z(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    fractions = extract_all_fraction_pairs(lower)
    if len(fractions) != 1 or "сколько" not in question:
        return None

    numerator, denominator = fractions[0]
    if denominator == 0:
        return None

    total_value = None
    answer_unit = ""
    lines: List[str] = []
    step_no = 1

    ton_match = re.search(r"\b(\d+)\s*т\b", lower)
    if ton_match:
        tons = int(ton_match.group(1))
        total_value = tons * 1000
        answer_unit = "кг"
        lines.append(f"1) Сначала переводим тонны в килограммы: {tons} т = {total_value} кг")
        step_no = 2
    else:
        for unit in ("кг", "г", "л", "м", "см", "дм", "км"):
            unit_match = re.search(rf"\b(\d+)\s*{re.escape(unit)}\b", lower)
            if unit_match:
                total_value = int(unit_match.group(1))
                answer_unit = unit
                break

    if total_value is None:
        values = extract_non_fraction_numbers(lower)
        if not values:
            return None
        total_value = max(values)

    if total_value % denominator != 0:
        return None

    one_part = total_value // denominator
    part_value = one_part * numerator

    unit_suffix = f" {answer_unit}" if answer_unit else ""
    lines.append(f"{step_no}) Если всё число равно {total_value}{unit_suffix}, то одна доля равна {total_value} : {denominator} = {one_part}{unit_suffix}")
    step_no += 1

    if numerator == 1:
        lines.append(f"{step_no}) Если нужно найти 1/{denominator} числа, то ответ равен {one_part}{unit_suffix}")
    else:
        lines.append(f"{step_no}) Если нужно найти {numerator}/{denominator} числа, то берём {numerator} такие доли: {one_part} × {numerator} = {part_value}{unit_suffix}")

    lines.append(f"Ответ: {part_value}{unit_suffix}")
    lines.append("Совет: если задача с дробью дана в тоннах, метрах или других единицах, сначала переводи величину в удобные одинаковые единицы")
    return join_explanation_lines(*lines)


def try_consolidation_return_trip_faster_explanation_z(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    if "обратно" not in lower or "быстр" not in lower or "сколько" not in question:
        return None

    factor_match = re.search(r"в\s+(\d+)\s+раз(?:а)?\s+быстр", lower)
    if not factor_match:
        return None
    factor = int(factor_match.group(1))
    if factor <= 0:
        return None

    distance_match = re.search(r"\b(\d+)\s*(км|м)\b", lower)
    speed_match = re.search(r"скорост[ьяию][^\d]{0,20}(\d+)\s*(км/ч|м/с|м/мин)?", lower)
    if not distance_match or not speed_match:
        return None

    distance_value = int(distance_match.group(1))
    distance_unit = distance_match.group(2)
    speed_value = int(speed_match.group(1))
    speed_unit = speed_match.group(2) or ("км/ч" if distance_unit == "км" else "")
    if speed_value <= 0 or distance_value % speed_value != 0:
        return None

    one_way_time = distance_value // speed_value
    time_unit = "ч" if "/ч" in speed_unit or "час" in question else "мин" if "/мин" in speed_unit or "мин" in question else ""

    if one_way_time % factor == 0:
        return_time = one_way_time // factor
        return join_explanation_lines(
            f"1) Если путь до пункта равен {distance_value} {distance_unit}, а скорость была {speed_value} {speed_unit}, то время в одну сторону равно {distance_value} : {speed_value} = {one_way_time}{(' ' + time_unit) if time_unit else ''}",
            f"2) Если обратно ехали в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} быстрее, то время в обратную сторону в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} меньше: {one_way_time} : {factor} = {return_time}{(' ' + time_unit) if time_unit else ''}",
            f"Ответ: {return_time}{(' ' + time_unit) if time_unit else ''}",
            "Совет: если скорость на том же пути увеличилась в несколько раз, то время уменьшается во столько же раз",
        )

    faster_speed = speed_value * factor
    if distance_value % faster_speed != 0:
        return None
    return_time = distance_value // faster_speed

    return join_explanation_lines(
        f"1) Если скорость на обратном пути в {factor} {plural_form(int(factor), 'раз', 'раза', 'раз')} больше, то новая скорость равна {speed_value} × {factor} = {faster_speed}{(' ' + speed_unit) if speed_unit else ''}",
        f"2) Если расстояние равно {distance_value} {distance_unit}, а новая скорость равна {faster_speed}{(' ' + speed_unit) if speed_unit else ''}, то время обратно равно {distance_value} : {faster_speed} = {return_time}{(' ' + time_unit) if time_unit else ''}",
        f"Ответ: {return_time}{(' ' + time_unit) if time_unit else ''}",
        "Совет: для одного и того же пути время находят делением расстояния на скорость",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_consolidation_direct_relation_multianswer_explanation_z(user_text)
        or try_consolidation_fraction_named_unit_explanation_z(user_text)
        or try_consolidation_return_trip_faster_explanation_z(user_text)
        or _CONSOLIDATION_PREV_BUILD_EXPLANATION_LOCAL_FIRST_Z(user_text, kind)
    )



# --- OPENAI HOTFIX 2026-04-11ZA: narrow named-unit fraction patch to real conversion cases ---

def try_consolidation_fraction_named_unit_explanation_z(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    fractions = extract_all_fraction_pairs(lower)
    if len(fractions) != 1 or "сколько" not in question:
        return None

    # Этот локальный обработчик нужен именно для задач, где требуется перевод единиц,
    # в первую очередь для тонн -> килограммы. Остальные дробные текстовые задачи
    # лучше оставлять более ранним специализированным объяснителям.
    ton_match = re.search(r"\b(\d+)\s*т\b", lower)
    if not ton_match:
        return None

    numerator, denominator = fractions[0]
    if denominator == 0:
        return None

    tons = int(ton_match.group(1))
    total_value = tons * 1000
    if total_value % denominator != 0:
        return None

    one_part = total_value // denominator
    part_value = one_part * numerator

    return join_explanation_lines(
        f"1) Сначала переводим тонны в килограммы: {tons} т = {total_value} кг",
        f"2) Если всё число равно {total_value} кг, то одна доля равна {total_value} : {denominator} = {one_part} кг",
        f"3) Если нужно найти {numerator}/{denominator} числа, то берём {numerator} такие доли: {one_part} × {numerator} = {part_value} кг",
        f"Ответ: {part_value} кг",
        "Совет: если задача с дробью дана в тоннах, сначала переведи тонны в килограммы",
    )



# --- CONSOLIDATION PATCH 2026-04-11AA: named measurement expressions from textbook ---

_PREV_20260411AA_INFER_TASK_KIND = infer_task_kind
_PREV_20260411AA_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_PREV_20260411AA_DETAILED_FORMAT_SOLUTION = _detailed_format_solution

_MEASURE_BASE_UNITS_20260411AA = {
    "length": [("км", 1_000_000), ("м", 1_000), ("дм", 100), ("см", 10), ("мм", 1)],
    "mass": [("т", 1_000_000), ("ц", 100_000), ("кг", 1_000), ("г", 1)],
    "time": [("ч", 3_600), ("мин", 60), ("с", 1)],
    "volume": [("л", 1_000), ("мл", 1)],
}

_MEASURE_UNIT_ALIASES_20260411AA = {
    "км": "км",
    "м": "м",
    "дм": "дм",
    "см": "см",
    "мм": "мм",
    "т": "т",
    "ц": "ц",
    "кг": "кг",
    "г": "г",
    "ч": "ч",
    "час": "ч",
    "часа": "ч",
    "часов": "ч",
    "мин": "мин",
    "минута": "мин",
    "минуты": "мин",
    "минут": "мин",
    "с": "с",
    "сек": "с",
    "секунда": "с",
    "секунды": "с",
    "секунд": "с",
    "л": "л",
    "мл": "мл",
}

_MEASURE_UNIT_PATTERN_20260411AA = "|".join(
    sorted((re.escape(unit) for unit in _MEASURE_UNIT_ALIASES_20260411AA), key=len, reverse=True)
)
_MEASURE_TOKEN_RE_20260411AA = re.compile(rf"(\d+)\s*({_MEASURE_UNIT_PATTERN_20260411AA})\b", re.IGNORECASE)


def _measure_canon_20260411AA(unit_text: str) -> str:
    return _MEASURE_UNIT_ALIASES_20260411AA.get(str(unit_text or "").strip().lower().replace("ё", "е"), "")



def _measure_family_20260411AA(unit_text: str) -> str:
    unit = _measure_canon_20260411AA(unit_text)
    for family, items in _MEASURE_BASE_UNITS_20260411AA.items():
        if any(name == unit for name, _ in items):
            return family
    return ""



def _measure_factor_20260411AA(family: str, unit_text: str) -> int:
    unit = _measure_canon_20260411AA(unit_text)
    for name, factor in _MEASURE_BASE_UNITS_20260411AA.get(family, []):
        if name == unit:
            return factor
    raise KeyError(unit)



def _measure_parse_value_20260411AA(text: str) -> Optional[dict]:
    raw = re.sub(r"\s+", " ", str(text or "").strip().lower().replace("ё", "е"))
    if not raw:
        return None
    matches = list(_MEASURE_TOKEN_RE_20260411AA.finditer(raw))
    if not matches:
        return None

    rebuilt_parts = []
    family = ""
    total = 0
    units_used = []
    normalized_tokens = []
    for match in matches:
        value = int(match.group(1))
        unit = _measure_canon_20260411AA(match.group(2))
        token_family = _measure_family_20260411AA(unit)
        if not token_family:
            return None
        if family and family != token_family:
            return None
        family = token_family
        rebuilt_parts.append(f"{value} {unit}")
        factor = _measure_factor_20260411AA(family, unit)
        total += value * factor
        if unit not in units_used:
            units_used.append(unit)
        normalized_tokens.append((value, unit))

    normalized = " ".join(rebuilt_parts)
    if re.sub(r"\s+", " ", normalized) != raw:
        return None

    preferred_units = sorted(units_used, key=lambda u: _measure_factor_20260411AA(family, u), reverse=True)
    return {
        "text": normalized,
        "family": family,
        "total": total,
        "units": preferred_units,
        "tokens": normalized_tokens,
    }



def _measure_format_from_base_20260411AA(total: int, family: str, preferred_units: List[str]) -> str:
    units = [u for u in preferred_units if _measure_family_20260411AA(u) == family]
    if not units:
        units = [name for name, _ in _MEASURE_BASE_UNITS_20260411AA[family]]
    units = sorted(units, key=lambda u: _measure_factor_20260411AA(family, u), reverse=True)

    if len(units) >= 2:
        first, second = units[0], units[1]
        first_factor = _measure_factor_20260411AA(family, first)
        second_factor = _measure_factor_20260411AA(family, second)
        first_value = total // first_factor
        remainder = total % first_factor
        second_value = remainder // second_factor
        parts = []
        if first_value:
            parts.append(f"{first_value} {first}")
        if second_value or not parts:
            parts.append(f"{second_value} {second}")
        return " ".join(parts)

    unit = units[0]
    factor = _measure_factor_20260411AA(family, unit)
    value = total // factor
    return f"{value} {unit}"



def _measure_base_unit_name_20260411AA(family: str) -> str:
    return _MEASURE_BASE_UNITS_20260411AA[family][-1][0]



def _parse_named_measurement_expression_20260411AA(raw_text: str) -> Optional[dict]:
    text = normalize_dashes(str(raw_text or "")).replace("×", " * ").replace(":", " / ").replace("÷", " / ")
    text = re.sub(r"\s+", " ", text).strip().lower().replace("ё", "е")
    if not text:
        return None

    measure_pattern = rf"(?:\d+\s*(?:{_MEASURE_UNIT_PATTERN_20260411AA})(?:\s+\d+\s*(?:{_MEASURE_UNIT_PATTERN_20260411AA}))*)"

    patterns = [
        (re.compile(rf"^({measure_pattern})\s*([+\-])\s*({measure_pattern})$", re.IGNORECASE), "measure_measure"),
        (re.compile(rf"^({measure_pattern})\s*([*/])\s*(\d+)$", re.IGNORECASE), "measure_number"),
        (re.compile(rf"^(\d+)\s*([*])\s*({measure_pattern})$", re.IGNORECASE), "number_measure"),
    ]

    for pattern, mode in patterns:
        match = pattern.fullmatch(text)
        if not match:
            continue
        if mode == "measure_measure":
            left = _measure_parse_value_20260411AA(match.group(1))
            right = _measure_parse_value_20260411AA(match.group(3))
            operator = "+" if match.group(2) == "+" else "-"
            if not left or not right or left["family"] != right["family"]:
                return None
            preferred = sorted(list(dict.fromkeys(left["units"] + right["units"])), key=lambda u: _measure_factor_20260411AA(left["family"], u), reverse=True)
            return {"mode": mode, "left": left, "right": right, "operator": operator, "family": left["family"], "preferred_units": preferred}
        if mode == "measure_number":
            left = _measure_parse_value_20260411AA(match.group(1))
            operator = "×" if match.group(2) == "*" else ":"
            number = int(match.group(3))
            if not left:
                return None
            return {"mode": mode, "left": left, "number": number, "operator": operator, "family": left["family"], "preferred_units": left["units"]}
        if mode == "number_measure":
            number = int(match.group(1))
            right = _measure_parse_value_20260411AA(match.group(3))
            if not right:
                return None
            return {"mode": mode, "left_number": number, "right": right, "number": number, "operator": "×", "family": right["family"], "preferred_units": right["units"]}
    return None



def _pretty_named_measurement_expression_20260411AA(parsed: dict) -> str:
    if parsed["mode"] == "measure_measure":
        return f"{parsed['left']['text']} {parsed['operator']} {parsed['right']['text']}"
    if parsed["mode"] == "measure_number":
        return f"{parsed['left']['text']} {parsed['operator']} {parsed['number']}"
    return f"{parsed['left_number']} × {parsed['right']['text']}"



def _build_named_measurement_expression_explanation_20260411AA(raw_text: str) -> Optional[str]:
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    if not parsed:
        return None

    family = parsed["family"]
    base_unit = _measure_base_unit_name_20260411AA(family)
    pretty = _pretty_named_measurement_expression_20260411AA(parsed)

    if parsed["mode"] == "measure_measure":
        left = parsed["left"]
        right = parsed["right"]
        if parsed["operator"] == "-" and left["total"] < right["total"]:
            return None
        result_total = left["total"] + right["total"] if parsed["operator"] == "+" else left["total"] - right["total"]
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        verb = "Складываем" if parsed["operator"] == "+" else "Вычитаем"
        return join_explanation_lines(
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим первое именованное число в {base_unit}: {left['text']} = {left['total']} {base_unit}",
            f"2) Переводим второе именованное число в {base_unit}: {right['text']} = {right['total']} {base_unit}",
            f"3) {verb}: {left['total']} {'+' if parsed['operator'] == '+' else '-'} {right['total']} = {result_total} {base_unit}",
            f"4) Переводим ответ обратно: {result_total} {base_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при сложении и вычитании именованных чисел сначала переводи их в одинаковые единицы",
        )

    if parsed["mode"] == "measure_number":
        left = parsed["left"]
        number = parsed["number"]
        if parsed["operator"] == ":":
            if number == 0 or left["total"] % number != 0:
                return None
            result_total = left["total"] // number
            action_line = f"2) Делим: {left['total']} : {number} = {result_total} {base_unit}"
        else:
            result_total = left["total"] * number
            action_line = f"2) Умножаем: {left['total']} × {number} = {result_total} {base_unit}"
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        return join_explanation_lines(
            f"Пример: {pretty} = {answer}",
            "Решение.",
            f"1) Переводим составное именованное число в {base_unit}: {left['text']} = {left['total']} {base_unit}",
            action_line,
            f"3) Переводим ответ обратно: {result_total} {base_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при умножении и делении составные именованные числа сначала заменяют простыми, а потом выполняют вычисление",
        )

    right = parsed["right"]
    number = parsed["left_number"]
    result_total = right["total"] * number
    answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
    return join_explanation_lines(
        f"Пример: {pretty} = {answer}",
        "Решение.",
        f"1) Переводим составное именованное число в {base_unit}: {right['text']} = {right['total']} {base_unit}",
        f"2) Умножаем: {number} × {right['total']} = {result_total} {base_unit}",
        f"3) Переводим ответ обратно: {result_total} {base_unit} = {answer}",
        f"Ответ: {answer}",
        "Совет: при умножении составного именованного числа сначала переводи его в простое именованное число",
    )



def infer_task_kind(text: str) -> str:
    if _parse_named_measurement_expression_20260411AA(text):
        return "expression"
    return _PREV_20260411AA_INFER_TASK_KIND(text)



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return _build_named_measurement_expression_explanation_20260411AA(user_text) or _PREV_20260411AA_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)



def _format_named_measurement_expression_solution_20260411AA(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    pretty = _pretty_named_measurement_expression_20260411AA(parsed) if parsed else strip_known_prefix(raw_text)
    answer = parts["answer"] or "проверь запись"
    body_lines = [line for line in parts["body"] if not line.lower().startswith(("пример:", "решение"))]
    lines: List[str] = [f"Пример: {pretty} = {answer}", "Решение."]
    lines.extend(_detailed_number_lines(body_lines))
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or "сначала переводи составное именованное число в простое, потом выполняй вычисление"
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)



def _detailed_format_solution(raw_text: str, text: str, kind: str) -> str:
    if _parse_named_measurement_expression_20260411AA(raw_text):
        return _format_named_measurement_expression_solution_20260411AA(raw_text, text)
    return _PREV_20260411AA_DETAILED_FORMAT_SOLUTION(raw_text, text, kind)


# --- HOTFIX 2026-04-11AB: use the smallest unit from the expression, not always family base ---


def _measure_conversion_unit_20260411AB(units: List[str], family: str) -> str:
    relevant = [u for u in units if _measure_family_20260411AA(u) == family]
    if not relevant:
        return _measure_base_unit_name_20260411AA(family)
    return min(relevant, key=lambda u: _measure_factor_20260411AA(family, u))



def _build_named_measurement_expression_explanation_20260411AA(raw_text: str) -> Optional[str]:
    parsed = _parse_named_measurement_expression_20260411AA(raw_text)
    if not parsed:
        return None

    family = parsed["family"]
    if parsed["mode"] == "measure_measure":
        left = parsed["left"]
        right = parsed["right"]
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        if parsed["operator"] == "-" and left["total"] < right["total"]:
            return None
        result_total = left["total"] + right["total"] if parsed["operator"] == "+" else left["total"] - right["total"]
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        left_simple = left["total"] // _measure_factor_20260411AA(family, conversion_unit)
        right_simple = right["total"] // _measure_factor_20260411AA(family, conversion_unit)
        result_simple = result_total // _measure_factor_20260411AA(family, conversion_unit)
        verb = "Складываем" if parsed["operator"] == "+" else "Вычитаем"
        return join_explanation_lines(
            f"Пример: {_pretty_named_measurement_expression_20260411AA(parsed)} = {answer}",
            "Решение.",
            f"1) Переводим первое именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            f"2) Переводим второе именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
            f"3) {verb}: {left_simple} {'+' if parsed['operator'] == '+' else '-'} {right_simple} = {result_simple} {conversion_unit}",
            f"4) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при сложении и вычитании именованных чисел сначала переводи их в одинаковые единицы",
        )

    if parsed["mode"] == "measure_number":
        left = parsed["left"]
        number = parsed["number"]
        conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
        left_simple = left["total"] // _measure_factor_20260411AA(family, conversion_unit)
        if parsed["operator"] == ":":
            if number == 0 or left_simple % number != 0:
                return None
            result_simple = left_simple // number
            action_line = f"2) Делим: {left_simple} : {number} = {result_simple} {conversion_unit}"
        else:
            result_simple = left_simple * number
            action_line = f"2) Умножаем: {left_simple} × {number} = {result_simple} {conversion_unit}"
        result_total = result_simple * _measure_factor_20260411AA(family, conversion_unit)
        answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
        return join_explanation_lines(
            f"Пример: {_pretty_named_measurement_expression_20260411AA(parsed)} = {answer}",
            "Решение.",
            f"1) Переводим составное именованное число в {conversion_unit}: {left['text']} = {left_simple} {conversion_unit}",
            action_line,
            f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
            f"Ответ: {answer}",
            "Совет: при умножении и делении составные именованные числа сначала заменяют простыми, а потом выполняют вычисление",
        )

    right = parsed["right"]
    number = parsed["left_number"]
    conversion_unit = _measure_conversion_unit_20260411AB(parsed["preferred_units"], family)
    right_simple = right["total"] // _measure_factor_20260411AA(family, conversion_unit)
    result_simple = right_simple * number
    result_total = result_simple * _measure_factor_20260411AA(family, conversion_unit)
    answer = _measure_format_from_base_20260411AA(result_total, family, parsed["preferred_units"])
    return join_explanation_lines(
        f"Пример: {_pretty_named_measurement_expression_20260411AA(parsed)} = {answer}",
        "Решение.",
        f"1) Переводим составное именованное число в {conversion_unit}: {right['text']} = {right_simple} {conversion_unit}",
        f"2) Умножаем: {number} × {right_simple} = {result_simple} {conversion_unit}",
        f"3) Переводим ответ обратно: {result_simple} {conversion_unit} = {answer}",
        f"Ответ: {answer}",
        "Совет: при умножении составного именованного числа сначала переводи его в простое именованное число",
    )


# --- USER FINAL CONSOLIDATION PATCH 2026-04-11: generic equations + clearer textbook answers ---

_PATCH_USER_FINAL_PREV_INFER_TASK_KIND = infer_task_kind
_PATCH_USER_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _user_final_equation_variable_name(source: str) -> str:
    match = re.search(r"[A-Za-zА-Яа-я]", str(source or ""))
    return match.group(0) if match else "x"



def to_equation_source(raw_text: str) -> Optional[str]:
    text = strip_known_prefix(raw_text)
    if not text:
        return None
    text = normalize_dashes(text)
    text = normalize_cyrillic_x(text)
    text = text.replace("X", "x").replace("×", "*").replace("·", "*").replace("÷", "/").replace(":", "/")
    text = re.sub(r"\s+", "", text)
    if text.count("=") != 1:
        return None
    if not re.fullmatch(r"[\dA-Za-zА-Яа-я=+\-*/]+", text):
        return None
    letters = re.findall(r"[A-Za-zА-Яа-я]", text)
    if not letters:
        return None
    unique_letters = {letter.lower() for letter in letters}
    if len(unique_letters) != 1:
        return None
    variable = letters[0]
    if text.count(variable) + text.lower().count(variable.lower()) < 1:
        return None
    return text



def infer_task_kind(text: str) -> str:
    if to_equation_source(text):
        return "equation"
    return _PATCH_USER_FINAL_PREV_INFER_TASK_KIND(text)



def _user_final_format_equation_check(template: str, variable_name: str, value_text: str, expected_text: str) -> str:
    expression = template.replace(variable_name, value_text)
    return f"Проверка: {expression} = {expected_text}"



def try_local_equation_explanation(raw_text: str) -> Optional[str]:
    source = to_equation_source(raw_text)
    if not source:
        return None

    variable_name = _user_final_equation_variable_name(source)
    lhs, rhs = source.split("=", 1)
    if variable_name not in lhs and variable_name in rhs:
        lhs, rhs = rhs, lhs

    try:
        rhs_value = Fraction(int(rhs), 1)
    except ValueError:
        return None

    variable_re = re.escape(variable_name)
    patterns = [
        (rf"^{variable_re}\+(\d+)$", "var_plus"),
        (rf"^{variable_re}-(\d+)$", "var_minus"),
        (rf"^{variable_re}\*(\d+)$", "var_mul"),
        (rf"^{variable_re}/(\d+)$", "var_div"),
        (rf"^(\d+)\+{variable_re}$", "plus_var"),
        (rf"^(\d+)-{variable_re}$", "minus_var"),
        (rf"^(\d+)\*{variable_re}$", "mul_var"),
        (rf"^(\d+)/{variable_re}$", "div_var"),
    ]

    for pattern, kind in patterns:
        match = re.fullmatch(pattern, lhs)
        if not match:
            continue

        number = Fraction(int(match.group(1)), 1)
        number_text = format_fraction(number)
        rhs_text = format_fraction(rhs_value)

        if kind in {"var_plus", "plus_var"}:
            answer = rhs_value - number
            check_template = f"{variable_name} + {number_text}" if kind == "var_plus" else f"{number_text} + {variable_name}"
            return join_explanation_lines(
                "Ищем неизвестное слагаемое",
                f"Чтобы найти неизвестное слагаемое, из суммы вычитаем известное: {rhs_text} - {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(check_template, variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное слагаемое находим вычитанием",
            )

        if kind == "var_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Ищем неизвестное уменьшаемое",
                f"Чтобы найти неизвестное уменьшаемое, к разности прибавляем вычитаемое: {rhs_text} + {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{variable_name} - {number_text}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное уменьшаемое находим сложением",
            )

        if kind == "minus_var":
            answer = number - rhs_value
            return join_explanation_lines(
                "Ищем неизвестное вычитаемое",
                f"Чтобы найти неизвестное вычитаемое, из уменьшаемого вычитаем разность: {number_text} - {rhs_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{number_text} - {variable_name}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное вычитаемое находим вычитанием",
            )

        if kind in {"var_mul", "mul_var"}:
            if number == 0:
                if rhs_value == 0:
                    return join_explanation_lines(
                        "При умножении на 0 всегда получается 0",
                        "Значит, подходит любое число",
                        "Ответ: подходит любое число",
                        "Совет: 0 × любое число = 0",
                    )
                return join_explanation_lines(
                    "При умножении на 0 нельзя получить другое число",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = rhs_value / number
            check_template = f"{variable_name} × {number_text}" if kind == "var_mul" else f"{number_text} × {variable_name}"
            return join_explanation_lines(
                "Ищем неизвестный множитель",
                f"Чтобы найти неизвестный множитель, произведение делим на известный множитель: {rhs_text} : {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(check_template, variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестный множитель находим делением",
            )

        if kind == "var_div":
            if number == 0:
                return join_explanation_lines(
                    "На ноль делить нельзя",
                    "Ответ: решения нет",
                    "Совет: проверь делитель",
                )
            answer = rhs_value * number
            return join_explanation_lines(
                "Ищем неизвестное делимое",
                f"Чтобы найти неизвестное делимое, делитель умножаем на частное: {rhs_text} × {number_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{variable_name} : {number_text}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестное делимое находим умножением",
            )

        if kind == "div_var":
            if rhs_value == 0:
                return join_explanation_lines(
                    "На ноль делить нельзя, а частное здесь равно 0",
                    "Ответ: решения нет",
                    "Совет: проверь уравнение ещё раз",
                )
            answer = number / rhs_value
            return join_explanation_lines(
                "Ищем неизвестный делитель",
                f"Чтобы найти неизвестный делитель, делимое делим на частное: {number_text} : {rhs_text} = {format_fraction(answer)}",
                _user_final_format_equation_check(f"{number_text} : {variable_name}", variable_name, format_fraction(answer), rhs_text),
                f"Ответ: {format_fraction(answer)}",
                "Совет: неизвестный делитель находим делением",
            )
    return None



def _detailed_format_equation_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_equation_source(raw_text) or normalize_cyrillic_x(strip_known_prefix(raw_text))
    variable_name = _user_final_equation_variable_name(source)
    pretty = _detailed_pretty_equation(source)
    answer = parts["answer"] or "проверь запись"
    if re.fullmatch(r"-?\d+(?:/\d+)?", answer):
        answer = f"{variable_name} = {answer}"
    lines: List[str] = [f"Уравнение: {pretty}", "Решение."]
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("equation")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)



def _user_final_question_text(raw_text: str) -> str:
    try:
        _, question = extract_condition_and_question(raw_text)
    except Exception:
        question = ""
    return str(question or "").lower().replace("ё", "е")



def try_patch_textbook_two_products_money_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _user_final_question_text(raw_text)
    if "сколько" not in lower:
        return None
    if not contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила вся покупка", "сколько стоит вся покупка", "сколько стоила покупка", "сколько стоит покупка")):
        return None

    matches = list(re.finditer(r"(\d+)\s+[^?.!,]{1,40}?\s+по\s+(\d+)\s*(?:руб|руб\.|рубля|рублей)?", lower))
    if len(matches) < 2:
        return None

    first_count = int(matches[0].group(1))
    first_price = int(matches[0].group(2))
    second_count = int(matches[1].group(1))
    second_price = int(matches[1].group(2))

    first_total = first_count * first_price
    second_total = second_count * second_price
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если первая покупка состоит из {first_count} предметов по {first_price} руб., то её стоимость равна {first_count} × {first_price} = {first_total} руб.",
        f"2) Если вторая покупка состоит из {second_count} предметов по {second_price} руб., то её стоимость равна {second_count} × {second_price} = {second_total} руб.",
        f"3) Если первая покупка стоит {first_total} руб., а вторая {second_total} руб., то вся покупка стоит {first_total} + {second_total} = {total} руб.",
        f"Ответ: за всю покупку заплатили {total} руб.",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно.",
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
        f"1) Если один кусок стоит {first_cost}, а другой {second_cost}, то общая стоимость равна {first_cost} + {second_cost} = {total_cost}.",
        f"2) Если за {total_length} м заплатили {total_cost}, то один метр стоит {total_cost} : {total_length} = {unit_price}.",
        f"3) Если первый кусок стоит {first_cost}, а один метр стоит {unit_price}, то длина первого куска равна {first_cost} : {unit_price} = {first_length} м.",
        f"4) Если второй кусок стоит {second_cost}, а один метр стоит {unit_price}, то длина второго куска равна {second_cost} : {unit_price} = {second_length} м.",
        f"Ответ: в первом куске {first_length} м, во втором — {second_length} м.",
        "Совет: если у одинакового товара одна и та же цена за единицу, сначала находят цену одной единицы.",
    )



def explain_costs_from_length_difference(first_length: int, second_length: int, diff_cost: int) -> Optional[str]:
    diff_length = abs(second_length - first_length)
    if diff_length == 0 or diff_cost % diff_length != 0:
        return None
    price_per_meter = diff_cost // diff_length
    first_cost = first_length * price_per_meter
    second_cost = second_length * price_per_meter
    return join_explanation_lines(
        f"1) Если во втором куске {second_length} м ткани, а в первом {first_length} м ткани, то разность длин равна {second_length} - {first_length} = {diff_length} м.",
        f"2) Если второй кусок дороже на {diff_cost} руб. и длиннее на {diff_length} м, то один метр ткани стоит {diff_cost} : {diff_length} = {price_per_meter} руб.",
        f"3) Если в первом куске {first_length} м, а один метр стоит {price_per_meter} руб., то первый кусок стоит {first_length} × {price_per_meter} = {first_cost} руб.",
        f"4) Если во втором куске {second_length} м, а один метр стоит {price_per_meter} руб., то второй кусок стоит {second_length} × {price_per_meter} = {second_cost} руб.",
        f"Ответ: первый кусок стоит {first_cost} руб., второй — {second_cost} руб.",
        "Совет: если цена зависит от длины одинаково, сначала найди цену одной единицы длины.",
    )



def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"1) Если с одного участка собрали {first_bags} мешков, а с другого {second_bags} мешков, то разность мешков равна {first_bags} - {second_bags} = {diff_bags}.",
        f"2) Если {diff_bags} мешков составляют {diff_mass} кг, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг.",
        f"3) Если на первом участке {first_bags} мешков по {per_bag} кг, то всего собрали {first_bags} × {per_bag} = {first_mass} кг.",
        f"4) Если на втором участке {second_bags} мешков по {per_bag} кг, то всего собрали {second_bags} × {per_bag} = {second_mass} кг.",
        f"Ответ: с первого участка собрали {first_mass} кг, со второго — {second_mass} кг.",
        "Совет: если известна разность по мешкам и по килограммам, сначала найди массу одного мешка.",
    )



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_patch_textbook_two_products_money_explanation(user_text)
        or _PATCH_USER_FINAL_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )

# --- USER CONSOLIDATION PATCH 2026-04-11: textbook wording, safer precedence, preserved architecture ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку «Порядок действий:».
3. Ниже пиши тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
4. Потом пиши строку «Решение по действиям:».
5. Ниже пиши действия по порядку: 1) ... 2) ... 3) ...
6. В конце пиши строку «Ответ: ...».

Для текстовых задач:
1. Сначала пиши «Задача.» и само условие без изменения чисел.
2. Потом пиши «Решение.»
3. Затем обязательно пиши «Что известно: ...» и «Что нужно найти: ...».
4. Дальше решай по действиям.
5. После каждого действия коротко говори, что нашли.
6. По возможности используй школьную форму «Если ..., то ...».
7. В конце пиши «Ответ: ...».

Для уравнений:
1. Пиши строку «Уравнение: ...».
2. Потом «Решение.»
3. Решай по шагам.
4. Обязательно пиши «Проверка: ...».
5. Потом «Ответ: ...».

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии и величин:
1. Сначала назови правило или формулу.
2. Если нужно, сначала переведи величины в одинаковые единицы.
3. Потом решай по действиям.
4. В ответе обязательно пиши единицы измерения.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Сохраняй вычисления в столбик и подробные пояснения.
Сложение или вычитание в столбик особенно уместно, если в вычислениях больше двух двузначных чисел или есть хотя бы одно трёхзначное число.
""".strip()


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        "Нужно узнать, сколько всего или сколько стало.",
        f"Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )



def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько осталось или сколько стало меньше.",
        f"Если сначала было {first}, а потом убрали {second}, то осталось {first} - {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если что-то убрали, отдали или потратили, обычно нужно вычитание",
    )



def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, на сколько одно число больше или меньше другого.",
        f"Для этого из большего числа вычитаем меньшее: {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием",
    )



def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала.",
        f"Если осталось {remaining}, а убрали {removed}, то сначала было {remaining} + {removed} = {result}.",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находят сложением",
    )



def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        "Нужно узнать, сколько было сначала.",
        f"Если стало {final_total} после того, как прибавили {added}, то сначала было {final_total} - {added} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают то, что прибавили",
    )



def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько добавили.",
        f"Сравниваем, сколько было и сколько стало: {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )



def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        "Нужно узнать, сколько убрали.",
        f"Из того, что было, вычитаем то, что осталось: {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )



def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        "Нужно узнать, сколько всего предметов в одинаковых группах.",
        f"Если есть {groups} одинаковых групп по {per_group} в каждой, то всего {groups} × {per_group} = {result}.",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )



def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя", "Ответ: деление на ноль невозможно", "Совет: проверь, на сколько частей делят")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько получит каждый.",
            f"Если {total} предметов разделили на {groups} равные части, то {total} : {groups} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        "Нужно разделить поровну.",
        f"Делим: {total} : {groups} = {quotient}, остаток {remainder}.",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )



def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов", "Ответ: запись задачи неверная", "Совет: проверь размер одной группы")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            "Нужно узнать, сколько групп получится.",
            f"Если всего {total} предметов, а в одной группе по {per_group}, то групп будет {total} : {per_group} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"Сначала находим, сколько полных групп получится: {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Так как предметы ещё остались, нужна ещё одна группа, всего {quotient + 1}.",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления ещё есть остаток, иногда нужна ещё одна коробка или место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            "Нужно узнать, сколько полных групп получится.",
            f"Делим: {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None



def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        "Сначала нужно найти второе количество.",
        f"Если второе количество на {delta} {mode}, то считаем так: {base} {sign} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )



def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {sign} {delta} = {related}.",
        f"Потом находим всё вместе: {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму",
    )



def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        "Сначала нужно найти второе количество.",
        f"Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то считаем так: {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )



def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"Сначала находим второе количество: {base} {op} {factor} = {related}.",
        f"Потом находим всё вместе: {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: сначала найди число, которое дано через отношение, потом считай общее количество",
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
        f"Это задача в косвенной форме: если здесь на {delta} {relation}, то {relation_text}.",
        f"Значит, искомое число равно {base} {op} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
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
        f"Это задача в косвенной форме: если здесь в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {relation_text}.",
        f"Значит, искомое число равно {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переведи условие в прямую форму",
    )



def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} группах {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}.",
        f"2) Если в одной группе {one_group}, то в {target_groups} таких же группах {one_group} × {target_groups} = {result}.",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )



def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти расстояние.",
        "Пользуемся правилом: расстояние равно скорости, умноженной на время.",
        f"Считаем: {speed} × {time_value} = {result}.",
        f"Ответ: {answer}",
        "Совет: чтобы найти расстояние, скорость умножают на время",
    )



def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти скорость.",
        "Пользуемся правилом: скорость равна расстоянию, делённому на время.",
        f"Считаем: {distance} : {time_value} = {result}.",
        f"Ответ: {answer}",
        "Совет: чтобы найти скорость, расстояние делят на время",
    )



def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "Нужно найти время.",
        "Пользуемся правилом: время равно расстоянию, делённому на скорость.",
        f"Считаем: {distance} : {speed} = {result}.",
        f"Ответ: {answer}",
        "Совет: чтобы найти время, расстояние делят на скорость",
    )



def try_local_expression_explanation(raw_text: str) -> Optional[str]:
    source = to_expression_source(raw_text)
    if not source:
        return None
    node = parse_expression_ast(source)
    if node is None:
        return None

    # Важно: цепочку сложения упрощаем только без скобок, чтобы не ломать школьный порядок действий.
    if "(" not in source and ")" not in source:
        add_chain = flatten_add_chain(node)
        if add_chain and all(n >= 0 for n in add_chain):
            if should_use_column_for_sum(add_chain):
                return explain_column_addition(add_chain)
            if len(add_chain) == 2:
                return explain_simple_addition(add_chain[0], add_chain[1])
            current = add_chain[0]
            lines = ["Нужно найти сумму нескольких чисел."]
            for idx, n in enumerate(add_chain[1:], start=1):
                new_total = current + n
                if idx == 1:
                    lines.append(f"Сначала складываем: {current} + {n} = {new_total}.")
                elif idx == 2:
                    lines.append(f"Потом складываем: {current} + {n} = {new_total}.")
                else:
                    lines.append(f"Дальше складываем: {current} + {n} = {new_total}.")
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

    body_lines = []
    has_brackets = "(" in source or ")" in source
    for index, step in enumerate(steps, start=1):
        text = f"{step['left']} {step['operator']} {step['right']} = {step['result']}"
        if index == 1 and has_brackets and len(steps) > 1:
            body_lines.append(f"{index}) Сначала выполняем действие в скобках: {text}")
        elif index == 1:
            body_lines.append(f"{index}) Сначала {step['verb']}: {text}")
        elif index == 2:
            body_lines.append(f"{index}) Потом {step['verb']}: {text}")
        else:
            body_lines.append(f"{index}) Дальше {step['verb']}: {text}")

    answer = format_fraction(value)
    advice = "сначала выполняй умножение и деление, потом сложение и вычитание" if re.search(r"[+\-].*[*/]|[*/].*[+\-]", source) else default_advice("expression")
    return join_explanation_lines(*body_lines, f"Ответ: {answer}", f"Совет: {advice}")


# --- USER TEXTBOOK PATCH 2026-04-11B: shelf/book templates from the uploaded methodology ---


def _user_patch_lower_text_20260411b(raw_text: str) -> str:
    return normalize_word_problem_text(raw_text).lower().replace("ё", "е")





def _user_patch_books_word_20260411b(count: int) -> str:
    return plural_form(count, "книга", "книги", "книг")

def try_user_patch_shelf_total_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*(обеих|двух) полк", lower):
        return None
    match = re.search(r"на первой полке(?: было)?\s*(\d+)\s*книг[^\d]{0,40}на второй(?: полке)?(?: было)?\s*(\d+)\b", lower)
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2))
    total = first + second
    return join_explanation_lines(
        f"1) Если на первой полке было {first} {_user_patch_books_word_20260411b(first)}, а на второй {second} {_user_patch_books_word_20260411b(second)}, то на обеих полках было {first} + {second} = {total} книг.",
        f"Ответ: на двух полках было {total} книг.",
        "Совет: если спрашивают, сколько на обеих полках, складывают количества на первой и второй полке.",
    )



def try_user_patch_shelf_more_less_total_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*(обеих|двух) полк", lower):
        return None
    match = re.search(r"на первой полке(?: было)?\s*(\d+)\s*книг[^\d]{0,40}на второй(?: полке)?\s*на\s*(\d+)\s*(больше|меньше)", lower)
    if not match:
        return None
    first = int(match.group(1))
    delta = int(match.group(2))
    mode = match.group(3)
    second = first + delta if mode == "больше" else first - delta
    if second < 0:
        return None
    total = first + second
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если на первой полке {first} {_user_patch_books_word_20260411b(first)}, а на второй на {delta} {mode}, то на второй полке было {first} {sign} {delta} = {second} {_user_patch_books_word_20260411b(second)}.",
        f"2) Если на первой полке {first} {_user_patch_books_word_20260411b(first)}, а на второй {second} {_user_patch_books_word_20260411b(second)}, то на двух полках было {first} + {second} = {total} книг.",
        f"Ответ: на двух полках было {total} книг.",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму.",
    )



def try_user_patch_shelf_unknown_second_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*второй полке", lower):
        return None
    match = re.search(r"на двух полках(?: было)?\s*(\d+)\s*книг[^\d]{0,80}на первой полке(?: было)?\s*(\d+)\s*книг", lower)
    if not match:
        return None
    total = int(match.group(1))
    first = int(match.group(2))
    second = total - first
    if second < 0:
        return None
    return join_explanation_lines(
        f"1) Если на двух полках было {total} книг, а на первой полке было {first} {_user_patch_books_word_20260411b(first)}, то на второй полке было {total} - {first} = {second} {_user_patch_books_word_20260411b(second)}.",
        f"Ответ: на второй полке было {second} {_user_patch_books_word_20260411b(second)}.",
        "Совет: чтобы найти, сколько было на второй полке, из общего количества вычитают количество на первой полке.",
    )



def try_user_patch_shelf_indirect_explanation_20260411b(raw_text: str) -> Optional[str]:
    lower = _user_patch_lower_text_20260411b(raw_text)
    if not ("полке" in lower and "книг" in lower):
        return None
    if not re.search(r"сколько[^.?!]*второй полке", lower):
        return None
    match = re.search(r"на первой полке(?: было)?\s*(\d+)\s*книг[^\d]{0,30}это\s+на\s*(\d+)\s*книг[^\d]{0,20}(больше|меньше),?\s+чем\s+на\s+второй", lower)
    if match:
        first = int(match.group(1))
        delta = int(match.group(2))
        relation = match.group(3)
        if relation == "больше":
            second = first - delta
            if second < 0:
                return None
            return join_explanation_lines(
                f"1) Если на первой полке книг на {delta} больше, чем на второй, то на второй полке книг на {delta} меньше, чем на первой.",
                f"2) Если на первой полке {first} книг, а на второй на {delta} меньше, то на второй полке было {first} - {delta} = {second} {_user_patch_books_word_20260411b(second)}.",
                f"Ответ: на второй полке было {second} {_user_patch_books_word_20260411b(second)}.",
                "Совет: в косвенной задаче сначала переведи условие в прямую форму.",
            )
        second = first + delta
        return join_explanation_lines(
            f"1) Если на первой полке книг на {delta} меньше, чем на второй, то на второй полке книг на {delta} больше, чем на первой.",
            f"2) Если на первой полке {first} книг, а на второй на {delta} больше, то на второй полке было {first} + {delta} = {second} {_user_patch_books_word_20260411b(second)}.",
            f"Ответ: на второй полке было {second} книг.",
            "Совет: в косвенной задаче сначала переведи условие в прямую форму.",
        )

    match = re.search(r"на второй полке(?: было)?\s*(\d+)\s*книг[^\d]{0,30}это\s+в\s*(\d+)\s*раз(?:а)?\s*больше,?\s+чем\s+на\s+первой", lower)
    if match:
        second = int(match.group(1))
        factor = int(match.group(2))
        if factor == 0 or second % factor != 0:
            return None
        first = second // factor
        return join_explanation_lines(
            f"1) Если на второй полке книг в {factor} раза больше, чем на первой, то на первой полке книг в {factor} раза меньше, чем на второй.",
            f"2) Если на второй полке {second} книг, а на первой в {factor} раза меньше, то на первой полке было {second} : {factor} = {first} {_user_patch_books_word_20260411b(first)}.",
            f"Ответ: на первой полке было {first} {_user_patch_books_word_20260411b(first)}.",
            "Совет: если сказано «в несколько раз больше» в косвенной форме, сначала переведи это в «в несколько раз меньше».",
        )
    return None



__OAI_20260411_USER_PREV_BUILD_LOCAL_SAFE = build_explanation_local_first


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_shelf_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_more_less_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_unknown_second_explanation_20260411b(user_text)
        or try_user_patch_shelf_indirect_explanation_20260411b(user_text)
        or __OAI_20260411_USER_PREV_BUILD_LOCAL_SAFE(user_text, kind)
    )


# --- OAI FINAL CLEAN PATCH 2026-04-11C: formatting cleanup, stable compare answers, textbook polish ---

_OAI_20260411C_PREV_EXPLAIN_PRICE_DIFFERENCE = explain_price_difference_problem
_OAI_20260411C_PREV_DETAILED_FORMAT_EXPRESSION = _detailed_format_expression_solution
_OAI_20260411C_PREV_DETAILED_FORMAT_SOLUTION = _detailed_format_solution


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a} руб., то цена одного товара равна {total_a} : {quantity} = {price_a} руб",
        f"2) Если за {quantity} таких же товаров заплатили {total_b} руб., то цена одного товара равна {total_b} : {quantity} = {price_b} руб",
        f"3) Сравниваем цены: {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб",
        f"Ответ: цены отличаются на {diff} руб",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )



def _oai_20260411c_expression_body_lines(body_lines: List[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for raw in body_lines:
        line = str(raw or "").strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("частное:"):
            continue
        if lower.startswith("пример:"):
            continue
        key = lower.rstrip(". ")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return cleaned



def _oai_20260411c_pretty_expr_with_map(source: str) -> Tuple[str, dict]:
    pretty_parts: List[str] = []
    op_map = {}
    current_len = 0
    for index, ch in enumerate(source):
        if ch in "+-*/":
            symbol = "×" if ch == "*" else ":" if ch == "/" else ch
            token = f" {symbol} "
            pretty_parts.append(token)
            op_map[index] = current_len + 1
            current_len += len(token)
        else:
            pretty_parts.append(ch)
            current_len += 1
    return "".join(pretty_parts), op_map



def _detailed_build_order_block(source: str) -> List[str]:
    node = parse_expression_ast(source)
    if node is None:
        return []
    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return []

    pretty_expr, op_map = _oai_20260411c_pretty_expr_with_map(source)
    marks = [" "] * len(pretty_expr)

    for step_index, step in enumerate(steps, start=1):
        raw_pos = step.get("pos")
        if raw_pos is None or raw_pos not in op_map:
            continue
        pretty_pos = op_map[raw_pos]
        label = str(step_index)
        start = max(0, pretty_pos - (len(label) - 1) // 2)
        for offset, char in enumerate(label):
            target = start + offset
            if 0 <= target < len(marks):
                marks[target] = char

    mark_line = "".join(marks).rstrip()
    return ["Порядок действий:", mark_line, pretty_expr]



def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")

    node = parse_expression_ast(source)
    if node is not None:
        pretty_expression = render_node(node)
    else:
        pretty_expression, _ = _oai_20260411c_pretty_expr_with_map(source)

    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = _oai_20260411c_expression_body_lines(parts["body"])
    if not body_lines:
        body_lines = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]

    if _detailed_is_column_like(body_lines) or any("столбик" in line.lower() for line in body_lines):
        lines.append("Решение.")
        before_expl: List[str] = []
        expl: List[str] = []
        in_expl = False
        for line in body_lines:
            low = line.lower()
            if low.startswith("пояснение"):
                in_expl = True
                continue
            if not in_expl:
                before_expl.append(line)
            else:
                expl.append(line)
        if before_expl:
            lines.extend(before_expl)
        if expl:
            lines.append("Пояснение по шагам:")
            lines.extend(_detailed_number_lines(expl))
        else:
            remaining = [line for line in body_lines if not line.lower().startswith("запись столбиком")]
            lines.extend(_detailed_number_lines(remaining))
    else:
        order_block = _detailed_build_order_block(source)
        if order_block:
            lines.extend(order_block)
            lines.append("Решение по действиям:")
        else:
            lines.append("Решение.")
        lines.extend(_detailed_number_lines(body_lines))

    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)



def _detailed_format_solution(raw_text: str, text: str, kind: str) -> str:
    if kind == "expression" and to_expression_source(raw_text):
        return _detailed_format_expression_solution(raw_text, text)
    return _OAI_20260411C_PREV_DETAILED_FORMAT_SOLUTION(raw_text, text, kind)


# --- OAI FINAL CLEAN PATCH 2026-04-11D: preferred routing for price tasks and cleaner column formatting ---

_OAI_20260411D_PREV_BUILD_LOCAL = build_explanation_local_first


def _oai_20260411d_is_visual_column_line(line: str) -> bool:
    value = str(line or "").strip()
    if not value:
        return False
    if re.search(r"[А-Яа-яЁё]", value):
        return False
    return True



def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    parts = _detailed_split_sections(base_text)
    source = to_expression_source(raw_text)
    if not source:
        return _detailed_format_generic_solution(raw_text, base_text, "expression")

    node = parse_expression_ast(source)
    if node is not None:
        pretty_expression = render_node(node)
    else:
        pretty_expression, _ = _oai_20260411c_pretty_expr_with_map(source)

    answer = parts["answer"] or _detailed_expression_answer(source) or "проверь запись"
    body_lines = _oai_20260411c_expression_body_lines(parts["body"])
    if not body_lines:
        body_lines = [re.sub(r"^\d+\)\s*", "", line) for line in _detailed_build_generic_steps_from_expression(source)]

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]

    if body_lines and body_lines[0].lower().startswith("запись столбиком"):
        lines.append("Решение.")
        lines.append("Запись столбиком:")
        visual_lines: List[str] = []
        idx = 1
        while idx < len(body_lines):
            current = body_lines[idx]
            lower = current.lower()
            if lower.startswith("частное:"):
                idx += 1
                continue
            if _oai_20260411d_is_visual_column_line(current):
                visual_lines.append(current)
                idx += 1
                continue
            break
        lines.extend(visual_lines)
        expl_lines = [line for line in body_lines[idx:] if not line.lower().startswith("частное:")]
        if expl_lines:
            lines.append("Пояснение по шагам:")
            lines.extend(_detailed_number_lines(expl_lines))
    elif _detailed_is_column_like(body_lines) or any("столбик" in line.lower() for line in body_lines):
        lines.append("Решение.")
        lines.extend(_detailed_number_lines(body_lines))
    else:
        order_block = _detailed_build_order_block(source)
        if order_block:
            lines.extend(order_block)
            lines.append("Решение по действиям:")
        else:
            lines.append("Решение.")
        lines.extend(_detailed_number_lines(body_lines))

    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice("expression")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)



def try_oai_20260411d_price_difference_first(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3:
        return None
    if contains_any_fragment(lower, ("за столько же", "на сколько пакет", "на сколько дороже", "на сколько дешевле")):
        return explain_price_difference_problem(nums[0], nums[1], nums[2])
    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        try_user_patch_shelf_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_more_less_total_explanation_20260411b(user_text)
        or try_user_patch_shelf_unknown_second_explanation_20260411b(user_text)
        or try_user_patch_shelf_indirect_explanation_20260411b(user_text)
        or try_oai_20260411d_price_difference_first(user_text)
        or try_local_price_word_problem_explanation(user_text)
        or _OAI_20260411D_PREV_BUILD_LOCAL(user_text, kind)
    )


# --- FINAL USER PATCH 2026-04-11ZZ: fuller counted answers + mixed-unit same-time motion + cleaner fraction-whole wording ---

_FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZZ = build_explanation_local_first
_FINAL_USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_ZZ = _detailed_maybe_enrich_answer

QUESTION_NOUN_FORMS.update({
    "детей": ("ребёнок", "ребёнка", "детей"),
    "ребенок": ("ребёнок", "ребёнка", "детей"),
    "ребёнок": ("ребёнок", "ребёнка", "детей"),
    "человек": ("человек", "человека", "человек"),
    "червячок": ("червячок", "червячка", "червячков"),
    "червячка": ("червячок", "червячка", "червячков"),
    "червячков": ("червячок", "червячка", "червячков"),
    "ручка": ("ручка", "ручки", "ручек"),
    "ручки": ("ручка", "ручки", "ручек"),
    "ручек": ("ручка", "ручки", "ручек"),
    "тетрадь": ("тетрадь", "тетради", "тетрадей"),
    "тетради": ("тетрадь", "тетради", "тетрадей"),
    "тетрадей": ("тетрадь", "тетради", "тетрадей"),
    "булочка": ("булочка", "булочки", "булочек"),
    "булочки": ("булочка", "булочки", "булочек"),
    "булочек": ("булочка", "булочки", "булочек"),
    "птица": ("птица", "птицы", "птиц"),
    "птицы": ("птица", "птицы", "птиц"),
    "птиц": ("птица", "птицы", "птиц"),
    "корзина": ("корзина", "корзины", "корзин"),
    "корзины": ("корзина", "корзины", "корзин"),
    "корзин": ("корзина", "корзины", "корзин"),
    "клетка": ("клетка", "клетки", "клеток"),
    "клетки": ("клетка", "клетки", "клеток"),
    "клеток": ("клетка", "клетки", "клеток"),
    "ягода": ("ягода", "ягоды", "ягод"),
    "ягоды": ("ягода", "ягоды", "ягод"),
    "ягод": ("ягода", "ягоды", "ягод"),
    "гриб": ("гриб", "гриба", "грибов"),
    "гриба": ("гриб", "гриба", "грибов"),
    "грибов": ("гриб", "гриба", "грибов"),
    "орешек": ("орешек", "орешка", "орешков"),
    "орешка": ("орешек", "орешка", "орешков"),
    "орешков": ("орешек", "орешка", "орешков"),
    "марка": ("марка", "марки", "марок"),
    "марки": ("марка", "марки", "марок"),
    "марок": ("марка", "марки", "марок"),
    "ложка": ("ложка", "ложки", "ложек"),
    "ложки": ("ложка", "ложки", "ложек"),
    "ложек": ("ложка", "ложки", "ложек"),
    "ириска": ("ириска", "ириски", "ирисок"),
    "ириски": ("ириска", "ириски", "ирисок"),
    "ирисок": ("ириска", "ириски", "ирисок"),
    "карамелька": ("карамелька", "карамельки", "карамелек"),
    "карамельки": ("карамелька", "карамельки", "карамелек"),
    "карамелек": ("карамелька", "карамельки", "карамелек"),
    "лимон": ("лимон", "лимона", "лимонов"),
    "лимона": ("лимон", "лимона", "лимонов"),
    "лимонов": ("лимон", "лимона", "лимонов"),
    "сетка": ("сетка", "сетки", "сеток"),
    "сетки": ("сетка", "сетки", "сеток"),
    "сеток": ("сетка", "сетки", "сеток"),
    "ведро": ("ведро", "ведра", "ведер"),
    "ведра": ("ведро", "ведра", "ведер"),
    "вёдер": ("ведро", "ведра", "ведер"),
    "ведер": ("ведро", "ведра", "ведер"),
    "пассажир": ("пассажир", "пассажира", "пассажиров"),
    "пассажира": ("пассажир", "пассажира", "пассажиров"),
    "пассажиров": ("пассажир", "пассажира", "пассажиров"),
})


def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None

    if remaining_numerator == 1:
        whole = remaining_value * denominator
        return join_explanation_lines(
            f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось 1/{denominator} всех денег",
            f"2) Если 1/{denominator} всех денег равна {remaining_value} руб., то все деньги равны {remaining_value} × {denominator} = {whole} руб.",
            f"Ответ: у мамы было {whole} руб.",
            "Совет: если известна оставшаяся доля, всё число находят умножением значения одной доли на число долей",
        )

    if remaining_value % remaining_numerator != 0:
        return None

    one_share = remaining_value // remaining_numerator
    whole = one_share * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value} руб., то 1/{denominator} всех денег равна {remaining_value} : {remaining_numerator} = {one_share} руб.",
        f"3) Если 1/{denominator} всех денег равна {one_share} руб., то все деньги равны {one_share} × {denominator} = {whole} руб.",
        f"Ответ: у мамы было {whole} руб.",
        "Совет: если известна оставшаяся часть, сначала найди одну долю, потом всё число",
    )


_FINAL_PATCH_DISTANCE_TO_BASE_ZZ = {
    "мм": 1,
    "см": 10,
    "дм": 100,
    "м": 1000,
    "км": 1000000,
}


def _final_patch_normalize_time_unit_zz(unit: str) -> str:
    value = str(unit or "").strip().lower().replace("ё", "е")
    if value in {"ч", "час", "часа", "часов"}:
        return "ч"
    if value in {"мин", "минута", "минуты", "минут"}:
        return "мин"
    if value in {"с", "сек", "секунда", "секунды", "секунд"}:
        return "с"
    return value


def _final_patch_split_speed_unit_zz(speed_unit: str) -> Optional[Tuple[str, str]]:
    value = str(speed_unit or "").strip().lower()
    if "/" not in value:
        return None
    dist_unit, time_unit = value.split("/", 1)
    dist_unit = dist_unit.strip()
    time_unit = _final_patch_normalize_time_unit_zz(time_unit)
    if dist_unit not in _FINAL_PATCH_DISTANCE_TO_BASE_ZZ or time_unit not in {"ч", "мин", "с"}:
        return None
    return dist_unit, time_unit


def _final_patch_parse_same_time_motion_zz(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")

    if not ("за это же время" in lower or "за то же время" in lower):
        return None
    if not contains_any_fragment(lower, ("с какой скоростью", "какова скорость")):
        return None

    unit_group = r"(?:км|м|дм|см|мм)"
    speed_group = r"(?:км|м|дм|см|мм)/(?:ч|мин|с)"

    first_match = re.search(
        rf"(\d+)\s*({unit_group})\b[^.?!]{{0,100}}?со\s+скорост(?:ью|и)\s*(\d+)\s*({speed_group})",
        lower,
    )
    if not first_match:
        first_match = re.search(
            rf"со\s+скорост(?:ью|и)\s*(\d+)\s*({speed_group})[^.?!]{{0,100}}?(\d+)\s*({unit_group})\b",
            lower,
        )
        if first_match:
            speed_value = int(first_match.group(1))
            speed_unit = first_match.group(2)
            first_distance_value = int(first_match.group(3))
            first_distance_unit = first_match.group(4)
        else:
            return None
    else:
        first_distance_value = int(first_match.group(1))
        first_distance_unit = first_match.group(2)
        speed_value = int(first_match.group(3))
        speed_unit = first_match.group(4)

    second_match = re.search(
        rf"(?:за это же время|за то же время)[^.?!]{{0,120}}?(\d+)\s*({unit_group})\b",
        lower,
    )
    if not second_match:
        return None

    second_distance_value = int(second_match.group(1))
    second_distance_unit = second_match.group(2)

    split_speed = _final_patch_split_speed_unit_zz(speed_unit)
    if not split_speed:
        return None
    speed_distance_unit, time_unit = split_speed

    first_distance_base = first_distance_value * _FINAL_PATCH_DISTANCE_TO_BASE_ZZ[first_distance_unit]
    speed_distance_base = _FINAL_PATCH_DISTANCE_TO_BASE_ZZ[speed_distance_unit]
    if first_distance_base % speed_distance_base != 0:
        return None

    first_distance_in_speed_units = first_distance_base // speed_distance_base
    if speed_value == 0 or first_distance_in_speed_units % speed_value != 0:
        return None

    same_time = first_distance_in_speed_units // speed_value
    if same_time == 0 or second_distance_value % same_time != 0:
        return None

    second_speed = second_distance_value // same_time
    answer_unit = f"{second_distance_unit}/{time_unit}"

    return join_explanation_lines(
        f"1) Если первый участник прошёл {first_distance_in_speed_units} {speed_distance_unit} со скоростью {speed_value} {speed_unit}, то он был в пути {first_distance_in_speed_units} : {speed_value} = {same_time} {time_unit}",
        f"2) Если второй участник прошёл {second_distance_value} {second_distance_unit} за {same_time} {time_unit}, то его скорость равна {second_distance_value} : {same_time} = {second_speed} {answer_unit}",
        f"Ответ: скорость второго участника равна {second_speed} {answer_unit}",
        "Совет: если время у двух участников одинаковое, сначала найди это время, потом скорость второго участника",
    )


def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _FINAL_USER_PATCH_PREV_DETAILED_MAYBE_ENRICH_ANSWER_ZZ(answer, raw_text, kind)
    stripped = str(value or "").strip()
    if not stripped:
        return stripped

    if re.fullmatch(r"-?\d+", stripped):
        try:
            stripped = _patch_answer_with_question_noun(int(stripped), raw_text)
        except Exception:
            pass

    if _question_lower_text(raw_text).startswith("на сколько") and re.fullmatch(r"-?\d+(?:/\d+)?(?:\s+[A-Za-zА-Яа-я./²]+)?", stripped):
        if not stripped.startswith("на "):
            stripped = f"на {stripped}"

    return stripped


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_patch_parse_same_time_motion_zz(user_text)
        or _FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZZ(user_text, kind)
    )



# --- FINAL USER PATCH 2026-04-11ZX: cleaner special case for fraction of money left after spending ---

_FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZX = build_explanation_local_first

def _final_patch_fraction_money_whole_zz(raw_text: str) -> Optional[str]:
    text = replace_common_fraction_words(normalize_word_problem_text(raw_text))
    lower = text.lower().replace("ё", "е")

    if not contains_any_fragment(lower, ("израсходовал", "израсходовала", "израсходовали")):
        return None
    if "остал" not in lower or "руб" not in lower:
        return None

    frac_match = re.search(r"(\d+)\s*/\s*(\d+)", lower)
    remain_match = re.search(r"остал[аоись]*[^\d]{0,20}(\d+)\s*руб", lower)
    if not frac_match or not remain_match:
        return None

    spent_numerator = int(frac_match.group(1))
    denominator = int(frac_match.group(2))
    remaining_value = int(remain_match.group(1))
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None

    if remaining_numerator == 1:
        whole = remaining_value * denominator
        return join_explanation_lines(
            f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось 1/{denominator} всех денег",
            f"2) Если 1/{denominator} всех денег равна {remaining_value} руб., то все деньги равны {remaining_value} × {denominator} = {whole} руб.",
            f"Ответ: всего было {whole} руб.",
            "Совет: если известна одна доля, всё число находят умножением значения доли на число долей",
        )

    if remaining_value % remaining_numerator != 0:
        return None

    one_share = remaining_value // remaining_numerator
    whole = one_share * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value} руб., то 1/{denominator} всех денег равна {remaining_value} : {remaining_numerator} = {one_share} руб.",
        f"3) Если 1/{denominator} всех денег равна {one_share} руб., то все деньги равны {one_share} × {denominator} = {whole} руб.",
        f"Ответ: всего было {whole} руб.",
        "Совет: если известна оставшаяся часть, сначала находят одну долю, потом всё число",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_patch_fraction_money_whole_zz(user_text)
        or _FINAL_USER_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST_ZX(user_text, kind)
    )




# --- OPENAI FINAL CONSOLIDATION PATCH 2026-04-11B: textbook priority, named purchase tasks, stable final prompt ---

_OPENAI_FINAL_20260411B_PREV_BUILD_LOCAL = build_explanation_local_first

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...
6. Если пример удобнее решать в столбик, сохрани запись столбиком и подробное пояснение по шагам.
7. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом перепиши само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. Для школьного стиля по возможности используй форму:
Если ..., то ...
6. После каждого действия коротко говори, что нашли.
7. Если в задаче несколько вопросов, отвечай на все вопросы по порядку.
8. В конце обязательно пиши:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это именованные величины, сначала переведи их в одинаковые единицы.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()


def _openai_final_20260411b_named_sum_of_two_products_money_explanation(raw_text: str) -> Optional[str]:
    try:
        direct = try_patch_named_sum_of_two_products_money_explanation(raw_text)
        if direct:
            return direct
    except Exception:
        pass

    lower = _statement_lower_text(raw_text)
    question = _question_lower_text(raw_text)
    if "сколько" not in lower:
        return None
    if not (contains_any_fragment(lower, ("заплат", "стоим", "стоил", "стоит")) or contains_any_fragment(question, ("сколько денег", "сколько заплат", "сколько стоила", "сколько стоит"))):
        return None

    products = _po_product_matches(raw_text)
    if len(products) < 2:
        return None
    if contains_any_fragment(question, ("сколько стоит 1", "сколько стоила 1", "сколько стоила одна", "сколько стоит одна")):
        return None

    first = products[0]
    second = products[1]
    first_total = first["count"] * first["value"]
    second_total = second["count"] * second["value"]
    total = first_total + second_total

    return join_explanation_lines(
        f"1) Если купили {first['count']} {first['name']} по {first['value']} руб., то за {first['name']} заплатили {first['count']} × {first['value']} = {first_total} руб",
        f"2) Если купили {second['count']} {second['name']} по {second['value']} руб., то за {second['name']} заплатили {second['count']} × {second['value']} = {second_total} руб",
        f"3) Если за {first['name']} заплатили {first_total} руб., а за {second['name']} {second_total} руб., то за всю покупку заплатили {first_total} + {second_total} = {total} руб",
        f"Ответ: за всю покупку заплатили {total} руб",
        "Совет: если в задаче есть две покупки вида «по столько-то», сначала находят стоимость каждой покупки отдельно",
    )


def _openai_final_20260411b_unknown_price_with_names_explanation(raw_text: str) -> Optional[str]:
    try:
        direct = try_high_priority_unknown_price_word_problem_explanation(raw_text)
        if direct:
            return direct
    except Exception:
        return None
    return None


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _openai_final_20260411b_named_sum_of_two_products_money_explanation(user_text)
        or _openai_final_20260411b_unknown_price_with_names_explanation(user_text)
        or _OPENAI_FINAL_20260411B_PREV_BUILD_LOCAL(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи",
            "Запишите пример или задачу полнее и без сокращений",
            "Ответ: пока нужен более понятный ввод",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2200,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- USER FINAL PATCH 2026-04-11ZZ: preserve architecture, stabilize final output ---

_USER_FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_USER_FINAL_PATCH_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом, сохраняя скобки и исходную запись.
2. Если действий несколько, обязательно пиши строку «Порядок действий:» и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши «Решение по действиям:» и ниже все вычисления по действиям: 1), 2), 3)...
4. Если пример удобнее решать в столбик, сохраняй запись столбиком и подробное пояснение по шагам.
5. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.
6. В конце пиши строку «Ответ: ...».

Для текстовых задач:
1. Сначала пиши «Задача.» и переписывай условие без изменения чисел.
2. Потом пиши «Решение.»
3. Затем обязательно пиши «Что известно: ...» и «Что нужно найти: ...».
4. Если сразу нельзя ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера: 1), 2), 3)...
7. Для школьного стиля по возможности используй форму «Если..., то ...».
8. После каждого действия коротко говори, что нашли.
9. Если в задаче несколько вопросов, ответь на все вопросы по порядку.
10. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку «Уравнение: ...».
2. Потом «Решение.»
3. Решай по шагам.
4. Обязательно пиши «Проверка: ...».
5. Потом «Ответ: ...».

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи дроби к общему знаменателю.
4. Если задача дана с величинами, сначала переведи величины в удобные одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.
5. В ответе обязательно пиши единицы измерения.

Школьные методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Сохраняй вычисления в столбик и подробные пояснения.
Для деления столбиком называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()


def _user_final_patch_pretty_expression_from_source(source: str) -> str:
    text = str(source or "")
    text = text.replace("*", "×").replace("/", ":")
    text = re.sub(r"([()+\-×:])", r" \1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("( ", "(").replace(" )", ")")
    return text



def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _USER_FINAL_PATCH_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    formatted = _USER_FINAL_PATCH_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)
    lines = [line for line in str(formatted or "").split("\n")]
    if not lines:
        return formatted

    answer = ""
    match = re.match(r"^Пример:\s*.*?=\s*(.+)$", lines[0].strip())
    if match:
        answer = match.group(1).strip().rstrip(".")
    if not answer:
        answer = _detailed_expression_answer(source) or "проверь запись"

    lines[0] = f"Пример: {_user_final_patch_pretty_expression_from_source(source)} = {answer}"
    return _detailed_finalize_text(lines)



def explain_long_division(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала смотри на делитель",
        )

    quotient, remainder = divmod(dividend, divisor)
    digits = list(str(dividend))
    lines: List[str] = [
        "Пишем деление столбиком",
        "Находим первое неполное делимое",
    ]

    current = 0
    started = False

    for index, digit_char in enumerate(digits):
        current = current * 10 + int(digit_char)

        if not started and current < divisor:
            continue

        if not started:
            started = True
            lines.append(f"Первое неполное делимое — {current}")

        if current < divisor:
            if index < len(digits) - 1:
                lines.append(f"Число {current} меньше {divisor}, поэтому в частном пишем 0 и сносим следующую цифру")
            else:
                lines.append(f"Число {current} меньше {divisor}, поэтому в частном пишем 0. Деление закончено")
            continue

        q_digit = current // divisor
        product = q_digit * divisor
        remainder_here = current - product
        next_try = (q_digit + 1) * divisor

        if index < len(digits) - 1:
            next_number = remainder_here * 10 + int(digits[index + 1])
            lines.append(
                f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше. Вычитаем: {current} - {product} = {remainder_here}. Сносим следующую цифру и получаем {next_number}"
            )
        else:
            if remainder_here == 0:
                lines.append(
                    f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше. Вычитаем: {current} - {product} = 0. Деление закончено"
                )
            else:
                lines.append(
                    f"Подбираем {q_digit}, потому что {q_digit} × {divisor} = {product}, а {q_digit + 1} × {divisor} = {next_try}, это уже больше. Вычитаем: {current} - {product} = {remainder_here}. Это остаток"
                )

        current = remainder_here

    if not started:
        lines.append(f"{dividend} меньше {divisor}, значит в частном будет 0")
        if remainder:
            lines.append(f"Остаток равен {remainder}")
            return join_explanation_lines(*lines, f"Ответ: 0, остаток {remainder}", "Совет: остаток всегда должен быть меньше делителя")
        return join_explanation_lines(*lines, "Ответ: 0", "Совет: если делимое меньше делителя, частное равно нулю")

    if remainder == 0:
        lines.append(f"Читаем ответ: частное равно {quotient}")
        return join_explanation_lines(*lines, f"Ответ: {quotient}", "Совет: в столбике повторяй шаги: взял, подобрал, умножил, вычел, снес цифру")

    lines.append(f"Читаем ответ: частное равно {quotient}, остаток {remainder}")
    return join_explanation_lines(*lines, f"Ответ: {quotient}, остаток {remainder}", "Совет: остаток всегда должен быть меньше делителя")



def _user_final_patch_try_geometry_formula_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    question = _question_lower_text(raw_text)
    unit = geometry_unit(lower)
    nums = extract_ordered_numbers(lower)

    asks_area = "площад" in question or "найти площадь" in lower or "узнайте площадь" in lower
    asks_perimeter = "периметр" in question or "найти периметр" in lower or "узнайте периметр" in lower

    if "прямоугольник" in lower and "со сторонами" in lower and len(nums) >= 2 and (asks_area or asks_perimeter):
        a, b = nums[0], nums[1]
        area = a * b
        perimeter = 2 * (a + b)
        lines: List[str] = []
        if asks_area:
            lines.append("1) Формула площади прямоугольника: S = a × b")
            lines.append(f"2) Подставляем числа: S = {a} × {b} = {with_unit(area, unit, square=True)}")
        if asks_perimeter:
            start_index = 3 if asks_area else 1
            lines.append(f"{start_index}) Формула периметра прямоугольника: P = 2 × (a + b)")
            lines.append(f"{start_index + 1}) Подставляем числа: P = 2 × ({a} + {b}) = {with_unit(perimeter, unit)}")
        if asks_area and asks_perimeter:
            lines.append(f"Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}")
        elif asks_area:
            lines.append(f"Ответ: {with_unit(area, unit, square=True)}")
        else:
            lines.append(f"Ответ: {with_unit(perimeter, unit)}")
        lines.append("Совет: у прямоугольника сначала называют формулу, потом подставляют числа")
        return join_explanation_lines(*lines)

    if "квадрат" in lower and len(nums) >= 1 and ("сторон" in lower or "сторона" in lower) and (asks_area or asks_perimeter):
        side = nums[0]
        area = side * side
        perimeter = side * 4
        lines = []
        if asks_area:
            lines.append("1) Формула площади квадрата: S = a × a")
            lines.append(f"2) Подставляем числа: S = {side} × {side} = {with_unit(area, unit, square=True)}")
        if asks_perimeter:
            start_index = 3 if asks_area else 1
            lines.append(f"{start_index}) Формула периметра квадрата: P = 4 × a")
            lines.append(f"{start_index + 1}) Подставляем числа: P = 4 × {side} = {with_unit(perimeter, unit)}")
        if asks_area and asks_perimeter:
            lines.append(f"Ответ: площадь — {with_unit(area, unit, square=True)}; периметр — {with_unit(perimeter, unit)}")
        elif asks_area:
            lines.append(f"Ответ: {with_unit(area, unit, square=True)}")
        else:
            lines.append(f"Ответ: {with_unit(perimeter, unit)}")
        lines.append("Совет: у квадрата площадь и периметр находят по стороне")
        return join_explanation_lines(*lines)

    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _user_final_patch_try_geometry_formula_explanation(user_text)
        or _USER_FINAL_PATCH_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- USER FINAL PATCH 2026-04-11ZZ2: restore explicit column block for long division ---

_USER_FINAL_PATCH_ZZ2_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _USER_FINAL_PATCH_ZZ2_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    node = parse_expression_ast(source)
    simple = try_simple_binary_int_expression(node) if node is not None else None
    parts = _detailed_split_sections(base_text)
    body_lines = [
        line for line in parts.get("body", [])
        if not line.lower().startswith(("что известно:", "что нужно найти:"))
    ]

    if simple and simple["operator"] is ast.Div and any("столбик" in line.lower() for line in body_lines):
        pretty_expr = _user_final_patch_pretty_expression_from_source(source)
        answer = parts.get("answer") or _detailed_expression_answer(source) or "проверь запись"
        advice = parts.get("advice") or default_advice("expression")
        lines = [
            f"Пример: {pretty_expr} = {answer}",
            "Решение.",
            "Запись столбиком:",
            f"{simple['right']} | {simple['left']}",
            "Пояснение по шагам:",
        ]
        lines.extend(_detailed_number_lines(body_lines))
        lines.append(f"Ответ: {answer}")
        lines.append(f"Совет: {advice}")
        return _detailed_finalize_text(lines)

    return _USER_FINAL_PATCH_ZZ2_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)


# --- OPENAI FINAL PATCH 2026-04-11C: textbook-style compound wording + bucket-word detection ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. В конце пиши:
Ответ: ...
6. Если пример удобнее решать в столбик, сохрани запись столбиком и подробное пояснение по шагам.
7. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие задачи без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Если задача составная, решай только по действиям.
5. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
6. В каждом действии, где это возможно, используй школьную форму:
Если ..., то ...
7. После каждого действия коротко говори, что нашли.
8. В конце пиши:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()


_BUCKET_STEM_TO_NUM = {
    "одн": 1,
    "одно": 1,
    "двух": 2,
    "трех": 3,
    "трёх": 3,
    "четырех": 4,
    "четырёх": 4,
    "пяти": 5,
    "шести": 6,
    "семи": 7,
    "восьми": 8,
    "девяти": 9,
    "десяти": 10,
}


def _extract_bucket_sizes_from_text(text: str) -> List[int]:
    lower = str(text or "").lower()
    values: List[int] = []

    for match in re.finditer(r"(\d+)\s*-\s*литров", lower):
        values.append(int(match.group(1)))

    for match in re.finditer(r"\b(\d+)литров", lower):
        values.append(int(match.group(1)))

    for match in re.finditer(r"\b([а-яё]+)литров", lower):
        stem = match.group(1)
        value = _BUCKET_STEM_TO_NUM.get(stem)
        if value is not None:
            values.append(value)

    unique_values: List[int] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values


def explain_sum_then_divide_word_problem(first: int, second: int, divisor: int) -> Optional[str]:
    if divisor == 0:
        return None
    total = first + second
    quotient, remainder = divmod(total, divisor)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {total}",
            f"2) Если всего {total}, а одна группа равна {divisor}, то {total} : {divisor} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: если сначала объединяют две части, а потом делят на равные группы, сначала находят сумму",
        )
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе равно {second}, то всего {first} + {second} = {total}",
        f"2) Если {total} разделить на группы по {divisor}, то получится {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: сначала находят общую сумму, а потом делят её на группы",
    )


def explain_cages_with_two_parts(first: int, second: int, total: int) -> Optional[str]:
    in_one = first + second
    if in_one == 0 or total % in_one != 0:
        return None
    cages = total // in_one
    return join_explanation_lines(
        f"1) Если в каждой клетке сидело {first} синих и {second} зелёных попугая, то в одной клетке было {first} + {second} = {in_one} попугаев",
        f"2) Если всего было {total} попугаев, а в одной клетке {in_one} попугаев, то клеток было {total} : {in_one} = {cages}",
        f"Ответ: {cages}",
        "Совет: если в каждой группе есть два вида предметов, сначала находят, сколько всего в одной группе",
    )


def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"1) Если в первой группе {first_count} равных частей, а во второй {second_count} равных частей, то всего {first_count} + {second_count} = {group_total} равных частей",
        f"2) Если всё количество равно {total}, а равных частей {group_total}, то одна часть равна {total} : {group_total} = {one_unit}",
        f"3) Если одна часть равна {one_unit}, а в первой группе {first_count} частей, то {first_label} равна {one_unit} × {first_count} = {first_total}",
        f"4) Если одна часть равна {one_unit}, а во второй группе {second_count} частей, то {second_label} равна {one_unit} × {second_count} = {second_total}",
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
        f"1) Если один кусок стоит {first_cost}, а другой {second_cost}, то общая стоимость равна {first_cost} + {second_cost} = {total_cost}",
        f"2) Если за {total_length} м ткани заплатили {total_cost}, то один метр стоит {total_cost} : {total_length} = {unit_price}",
        f"3) Если первый кусок стоит {first_cost}, а один метр стоит {unit_price}, то длина первого куска равна {first_cost} : {unit_price} = {first_length} м",
        f"4) Если второй кусок стоит {second_cost}, а один метр стоит {unit_price}, то длина второго куска равна {second_cost} : {unit_price} = {second_length} м",
        f"Ответ: в первом куске {first_length} м, во втором — {second_length} м",
        "Совет: если цена за единицу одинаковая, сначала находят цену одной единицы",
    )


def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"1) Если на одном участке {first_bags} мешков, а на другом {second_bags} мешков, то разность равна {max(first_bags, second_bags)} - {min(first_bags, second_bags)} = {diff_bags} мешков",
        f"2) Если этим {diff_bags} мешкам соответствуют {diff_mass} кг, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг",
        f"3) Если на первом участке {first_bags} мешков по {per_bag} кг, то всего собрали {first_bags} × {per_bag} = {first_mass} кг",
        f"4) Если на втором участке {second_bags} мешков по {per_bag} кг, то всего собрали {second_bags} × {per_bag} = {second_mass} кг",
        f"Ответ: {first_mass}; {second_mass}",
        "Совет: если известны разности по количеству и по массе, сначала находят массу одной равной части",
    )


def explain_water_buckets_difference(big_bucket: int, small_bucket: int, diff_total: int) -> Optional[str]:
    step_diff = abs(big_bucket - small_bucket)
    if step_diff == 0 or diff_total % step_diff != 0:
        return None
    trips = diff_total // step_diff
    big_total = big_bucket * trips
    small_total = small_bucket * trips
    return join_explanation_lines(
        f"1) Если мальчик носил воду {big_bucket}-литровым ведром, а девочка {small_bucket}-литровым, то мальчик за один раз приносил на {big_bucket} - {small_bucket} = {step_diff} л больше",
        f"2) Если всего мальчик принёс на {diff_total} л больше, а за один раз он приносил на {step_diff} л больше, то ходок было {diff_total} : {step_diff} = {trips}",
        f"3) Если девочка носила по {small_bucket} л и сделала {trips} ходок, то она принесла {small_bucket} × {trips} = {small_total} л",
        f"4) Если мальчик носил по {big_bucket} л и сделал {trips} ходок, то он принёс {big_bucket} × {trips} = {big_total} л",
        f"Ответ: мальчик принёс {big_total} л, девочка — {small_total} л",
        "Совет: если число ходок одинаковое, сначала находят разность за одну ходку",
    )


def explain_costs_from_length_difference(first_length: int, second_length: int, diff_cost: int) -> Optional[str]:
    diff_length = abs(second_length - first_length)
    if diff_length == 0 or diff_cost % diff_length != 0:
        return None
    price_per_meter = diff_cost // diff_length
    first_cost = first_length * price_per_meter
    second_cost = second_length * price_per_meter
    return join_explanation_lines(
        f"1) Если один кусок имеет длину {first_length} м, а другой {second_length} м, то разность длин равна {max(first_length, second_length)} - {min(first_length, second_length)} = {diff_length} м",
        f"2) Если разность стоимости равна {diff_cost} руб., а разность длин {diff_length} м, то один метр стоит {diff_cost} : {diff_length} = {price_per_meter} руб.",
        f"3) Если первый кусок имеет длину {first_length} м, а один метр стоит {price_per_meter} руб., то первый кусок стоит {first_length} × {price_per_meter} = {first_cost} руб.",
        f"4) Если второй кусок имеет длину {second_length} м, а один метр стоит {price_per_meter} руб., то второй кусок стоит {second_length} × {price_per_meter} = {second_cost} руб.",
        f"Ответ: первый кусок стоит {first_cost} руб., второй — {second_cost} руб.",
        "Совет: если цена ткани за метр одинаковая, сначала находят цену одного метра",
    )


_USER_20260411C_PREV_TRY_LOCAL_DIFFERENCE_UNKNOWN = try_local_difference_unknown_word_problem


def try_local_difference_unknown_word_problem(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower()

    bucket_sizes = _extract_bucket_sizes_from_text(lower)
    if len(bucket_sizes) >= 2 and ("ведр" in lower or "бочк" in lower):
        diff_match = re.search(r"на\s+(\d+)\s+литр", lower)
        if diff_match:
            diff_total = int(diff_match.group(1))
            big_bucket = max(bucket_sizes[0], bucket_sizes[1])
            small_bucket = min(bucket_sizes[0], bucket_sizes[1])
            solved = explain_water_buckets_difference(big_bucket, small_bucket, diff_total)
            if solved:
                return solved

    return _USER_20260411C_PREV_TRY_LOCAL_DIFFERENCE_UNKNOWN(raw_text)


# --- OPENAI FINAL PATCH 2026-04-11D: labelled answers for proportional and two-difference tasks ---

def explain_equal_rate_distribution(total: int, first_count: int, second_count: int, first_label: str = "первая группа", second_label: str = "вторая группа") -> Optional[str]:
    group_total = first_count + second_count
    if group_total == 0 or total % group_total != 0:
        return None
    one_unit = total // group_total
    first_total = first_count * one_unit
    second_total = second_count * one_unit
    return join_explanation_lines(
        f"1) Если в первой группе {first_count} равных частей, а во второй {second_count} равных частей, то всего {first_count} + {second_count} = {group_total} равных частей",
        f"2) Если всё количество равно {total}, а равных частей {group_total}, то одна часть равна {total} : {group_total} = {one_unit}",
        f"3) Если одна часть равна {one_unit}, а в первой группе {first_count} частей, то {first_label} выполнила {one_unit} × {first_count} = {first_total}",
        f"4) Если одна часть равна {one_unit}, а во второй группе {second_count} частей, то {second_label} выполнила {one_unit} × {second_count} = {second_total}",
        f"Ответ: {first_label} — {first_total}; {second_label} — {second_total}",
        "Совет: в задачах на пропорциональное деление сначала находят одну равную часть",
    )


def explain_masses_from_bag_difference(first_bags: int, second_bags: int, diff_mass: int) -> Optional[str]:
    diff_bags = abs(first_bags - second_bags)
    if diff_bags == 0 or diff_mass % diff_bags != 0:
        return None
    per_bag = diff_mass // diff_bags
    first_mass = first_bags * per_bag
    second_mass = second_bags * per_bag
    return join_explanation_lines(
        f"1) Если на одном участке {first_bags} мешков, а на другом {second_bags} мешков, то разность равна {max(first_bags, second_bags)} - {min(first_bags, second_bags)} = {diff_bags} мешков",
        f"2) Если этим {diff_bags} мешкам соответствуют {diff_mass} кг, то в одном мешке {diff_mass} : {diff_bags} = {per_bag} кг",
        f"3) Если на первом участке {first_bags} мешков по {per_bag} кг, то всего собрали {first_bags} × {per_bag} = {first_mass} кг",
        f"4) Если на втором участке {second_bags} мешков по {per_bag} кг, то всего собрали {second_bags} × {per_bag} = {second_mass} кг",
        f"Ответ: с первого участка — {first_mass} кг, со второго — {second_mass} кг",
        "Совет: если известны разности по количеству и по массе, сначала находят массу одной равной части",
    )


# --- FINAL PATCH 2026-04-12: clearer column division + noun-aware price wording + explicit sum/divide tasks ---

_FINAL_20260412_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first
_FINAL_20260412_PREV_DETECT_QUESTION_UNIT = _detect_question_unit
_FINAL_20260412_PREV_EXTRACT_COUNT_QUESTION_NOUN = _extract_count_question_noun
_FINAL_20260412_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution


def _final_20260412_question_lower(raw_text: str) -> str:
    return _question_text_only(raw_text).lower().replace("ё", "е").strip()



def _final_20260412_extract_price_subject(raw_text: str) -> Tuple[str, str]:
    question = _question_text_only(raw_text).strip().rstrip("?.!")
    lower = question.lower().replace("ё", "е")
    patterns = [
        (r"^сколько\s+стоит\s+(.+)$", "стоит"),
        (r"^сколько\s+стоят\s+(.+)$", "стоят"),
        (r"^сколько\s+стоила\s+(.+)$", "стоила"),
        (r"^сколько\s+стоили\s+(.+)$", "стоили"),
    ]
    for pattern, verb in patterns:
        match = re.match(pattern, lower)
        if match:
            subject = question[match.start(1):match.end(1)].strip()
            return subject, verb
    return "", ""



def _extract_count_question_noun(raw_text: str) -> str:
    question = _final_20260412_question_lower(raw_text)
    if question.startswith("сколько стоит") or question.startswith("сколько стоят"):
        return ""
    return _FINAL_20260412_PREV_EXTRACT_COUNT_QUESTION_NOUN(raw_text)



def _detect_question_unit(raw_text: str) -> str:
    unit = _FINAL_20260412_PREV_DETECT_QUESTION_UNIT(raw_text)
    if unit:
        return unit
    lower_full = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    question = _final_20260412_question_lower(raw_text)
    if ("сколько стоит" in question or "сколько стоят" in question or "сколько стоила" in question or "сколько стоили" in question) and ("руб" in lower_full or "денег" in lower_full):
        return "руб."
    return ""



def _final_20260412_named_simple_price_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    subject, verb = _final_20260412_extract_price_subject(raw_text)

    # 6 ручек стоят 18 руб. Сколько стоит 1 ручка?
    cond_total_match = re.search(r"(\d+)\s+([а-яё-]+)\s+стоят\s+(\d+)\s*руб", lower)
    if cond_total_match and verb in {"стоит", "стоила"}:
        count = int(cond_total_match.group(1))
        item_phrase = cond_total_match.group(2)
        total_cost = int(cond_total_match.group(3))
        if count > 0 and total_cost % count == 0:
            price = total_cost // count
            answer_subject = subject or "1 предмет"
            return join_explanation_lines(
                f"1) Если {count} {item_phrase} стоят {total_cost} руб., то цена одной штуки равна {total_cost} : {count} = {price} руб",
                f"Ответ: {answer_subject} стоит {price} руб",
                "Совет: цену одной штуки находят делением общей стоимости на количество",
            )

    # Книга стоит 50 рублей. Сколько стоят 6 таких книг?
    cond_one_match = re.search(r"([а-яё-]+)\s+стоит\s+(\d+)\s*(?:руб|рубля|рублей)", lower)
    qty_match = re.search(r"сколько\s+стоят\s+(\d+|один|одна|одно|две|два|три|четыре|пять|шесть|семь|восемь|девять|десять)", lower)
    if cond_one_match and qty_match and verb in {"стоят", "стоили"}:
        item_phrase = cond_one_match.group(1)
        price = int(cond_one_match.group(2))
        quantity = parse_number_token(qty_match.group(1))
        if quantity is not None:
            total_cost = price * quantity
            answer_subject = subject or f"{quantity} {item_phrase}"
            return join_explanation_lines(
                f"1) Если одна {item_phrase} стоит {price} руб., а купили {quantity}, то вся покупка стоит {price} × {quantity} = {total_cost} руб",
                f"Ответ: {answer_subject} стоят {total_cost} руб",
                "Совет: стоимость находят умножением цены на количество",
            )

    return None



def _final_20260412_named_sum_then_divide_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    nums = extract_ordered_numbers(lower)
    if len(nums) < 3 or "сколько" not in lower:
        return None

    if ("грядк" in lower or "сняли" in lower) and ("корзин" in lower or "корзины" in lower or "корзина" in lower) and re.search(r"по\s+\d+\s*кг", lower):
        first, second, per_group = nums[0], nums[1], nums[2]
        total = first + second
        quotient, remainder = divmod(total, per_group)
        if remainder == 0:
            return join_explanation_lines(
                f"1) Если с одной грядки сняли {first} кг, а с другой {second} кг, то всего сняли {first} + {second} = {total} кг",
                f"2) Если всего собрали {total} кг моркови и раскладывали по {per_group} кг в каждую корзину, то потребовалось {total} : {per_group} = {quotient} корзин",
                f"Ответ: потребовалось {quotient} корзин",
                "Совет: если сначала объединяют две части, а потом раскладывают по равным группам, сначала находят общую массу",
            )
    return None



def _final_20260412_render_long_division_block(dividend: int, divisor: int) -> str:
    if divisor == 0:
        return ""
    model = build_long_division_steps(dividend, divisor)
    steps = model.get("steps", [])
    quotient = model.get("quotient")
    divisor_str = str(divisor)
    dividend_str = str(dividend)
    header_indent = len(divisor_str) + 3
    lines = [
        f"{' ' * header_indent}{quotient}",
        f"{divisor_str} ) {dividend_str}",
    ]
    if not steps:
        return "\n".join(lines)

    for index, step in enumerate(steps):
        current = str(step["current"])
        product = str(step["product"])
        remainder = str(step["remainder"])
        width = max(len(current), len(product), 1)
        start_col = step["index"] - len(current) + 1
        indent = header_indent + max(0, start_col)
        if index > 0:
            lines.append(" " * indent + current)
        lines.append(" " * (indent + width - len(product)) + product)
        lines.append(" " * indent + "-" * width)
        if index == len(steps) - 1:
            lines.append(" " * (indent + width - len(remainder)) + remainder)
    return "\n".join(lines)



def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _FINAL_20260412_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    node = parse_expression_ast(source)
    simple = try_simple_binary_int_expression(node) if node is not None else None
    parts = _detailed_split_sections(base_text)
    body_lines = [
        line for line in parts.get("body", [])
        if not line.lower().startswith(("что известно:", "что нужно найти:"))
    ]

    if simple and simple["operator"] is ast.Div and any("пишем деление столбиком" in line.lower() for line in body_lines):
        pretty_expr = _user_final_patch_pretty_expression_from_source(source)
        answer = parts.get("answer") or _detailed_expression_answer(source) or "проверь запись"
        advice = parts.get("advice") or default_advice("expression")
        block = _final_20260412_render_long_division_block(simple["left"], simple["right"])
        lines = [
            f"Пример: {pretty_expr} = {answer}",
            "Решение.",
            "Запись столбиком:",
        ]
        lines.extend(block.splitlines())
        lines.append("Пояснение по шагам:")
        lines.extend(_detailed_number_lines(body_lines))
        lines.append(f"Ответ: {answer}")
        lines.append(f"Совет: {advice}")
        return _detailed_finalize_text(lines)

    return _FINAL_20260412_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_20260412_named_simple_price_explanation(user_text)
        or _final_20260412_named_sum_then_divide_explanation(user_text)
        or _FINAL_20260412_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- FINAL PATCH 2026-04-12B: support singular "стоит" in count-price wording ---

_FINAL_20260412B_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _final_20260412_named_simple_price_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    subject, verb = _final_20260412_extract_price_subject(raw_text)

    # 6 ручек стоит 18 руб. Сколько стоит 1 ручка?
    cond_total_match = re.search(r"(\d+)\s+([а-яё-]+)\s+стои(?:т|ли|ло|ла)\s+(\d+)\s*руб", lower)
    if cond_total_match and verb in {"стоит", "стоила"}:
        count = int(cond_total_match.group(1))
        item_phrase = cond_total_match.group(2)
        total_cost = int(cond_total_match.group(3))
        if count > 0 and total_cost % count == 0:
            price = total_cost // count
            answer_subject = subject or "1 предмет"
            return join_explanation_lines(
                f"1) Если {count} {item_phrase} стоят {total_cost} руб., то цена одной штуки равна {total_cost} : {count} = {price} руб",
                f"Ответ: {answer_subject} стоит {price} руб",
                "Совет: цену одной штуки находят делением общей стоимости на количество",
            )

    # Книга стоит 50 рублей. Сколько стоят 6 таких книг?
    cond_one_match = re.search(r"([а-яё-]+)\s+стоит\s+(\d+)\s*(?:руб|рубля|рублей)", lower)
    qty_match = re.search(r"сколько\s+стоят\s+(\d+|один|одна|одно|две|два|три|четыре|пять|шесть|семь|восемь|девять|десять)", lower)
    if cond_one_match and qty_match and verb in {"стоят", "стоили"}:
        item_phrase = cond_one_match.group(1)
        price = int(cond_one_match.group(2))
        quantity = parse_number_token(qty_match.group(1))
        if quantity is not None:
            total_cost = price * quantity
            answer_subject = subject or f"{quantity} {item_phrase}"
            return join_explanation_lines(
                f"1) Если одна {item_phrase} стоит {price} руб., а купили {quantity}, то вся покупка стоит {price} × {quantity} = {total_cost} руб",
                f"Ответ: {answer_subject} стоят {total_cost} руб",
                "Совет: стоимость находят умножением цены на количество",
            )

    return None



def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_20260412_named_simple_price_explanation(user_text)
        or _final_20260412_named_sum_then_divide_explanation(user_text)
        or _FINAL_20260412B_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


# --- OPENAI PATCH 2026-04-12: strict school order for mixed expressions ---

def _oai_20260412_flatten_add_sub_chain(node: ast.AST) -> Tuple[List[ast.AST], List[ast.BinOp]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        operands, ops = _oai_20260412_flatten_add_sub_chain(node.left)
        return operands + [node.right], ops + [node]
    return [node], []


def _oai_20260412_flatten_mul_div_chain(node: ast.AST) -> Tuple[List[ast.AST], List[ast.BinOp]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
        operands, ops = _oai_20260412_flatten_mul_div_chain(node.left)
        return operands + [node.right], ops + [node]
    return [node], []


def _oai_20260412_apply_operator(op: ast.operator, left: Fraction, right: Fraction) -> Fraction:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        if right == 0:
            raise ZeroDivisionError("division by zero")
        return left / right
    raise ValueError("Unsupported operator")


def _oai_20260412_eval_expression_school(node: ast.AST, source: Optional[str] = None):
    if is_int_literal_node(node):
        return eval_fraction_node(node), []
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return eval_fraction_node(node), []
    if not isinstance(node, ast.BinOp):
        return eval_fraction_node(node), []

    if isinstance(node.op, (ast.Mult, ast.Div)):
        operands, op_nodes = _oai_20260412_flatten_mul_div_chain(node)
    else:
        operands, op_nodes = _oai_20260412_flatten_add_sub_chain(node)

    operand_values: List[Fraction] = []
    steps: List[dict] = []

    for operand in operands:
        value, child_steps = _oai_20260412_eval_expression_school(operand, source)
        steps.extend(child_steps)
        operand_values.append(value)

    current_value = operand_values[0]
    for op_node, next_value in zip(op_nodes, operand_values[1:]):
        result_value = _oai_20260412_apply_operator(op_node.op, current_value, next_value)
        step = {
            "verb": OPERATOR_VERBS[type(op_node.op)],
            "left": format_fraction(current_value),
            "operator": OPERATOR_SYMBOLS[type(op_node.op)],
            "right": format_fraction(next_value),
            "result": format_fraction(result_value),
        }
        if source is not None:
            step["pos"] = _detailed_find_operator_position(source, op_node)
        steps.append(step)
        current_value = result_value

    return current_value, steps


def build_eval_steps(node: ast.AST):
    return _oai_20260412_eval_expression_school(node, None)


def _detailed_collect_expression_steps(node: ast.AST, source: str) -> List[dict]:
    return _oai_20260412_eval_expression_school(node, source)[1]


def format_step_lines(steps, raw_source: str):
    lines = []
    has_brackets = "(" in raw_source or ")" in raw_source
    for index, step in enumerate(steps):
        text = f"{step['left']} {step['operator']} {step['right']} = {step['result']}"
        prefix = "Сначала" if index == 0 else "Потом" if index == 1 else "Дальше"
        if index == 0 and has_brackets and len(steps) > 1:
            lines.append(f"Сначала выполняем действие в скобках: {text}")
        else:
            lines.append(f"{prefix} {step['verb']}: {text}")
    return lines


SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. В выражениях без скобок, где есть только + и -, выполняй действия слева направо.
4. В выражениях без скобок, где есть только × и :, выполняй действия слева направо.
5. В выражениях со скобками первым выполняй действие в скобках.
6. В выражениях, где есть +, -, ×, :, сначала по порядку выполняй все умножения и деления, а потом по порядку сложения и вычитания.
7. Потом пиши:
Решение по действиям:
8. Ниже пиши все вычисления по действиям:
1) ...
2) ...
3) ...
9. Если пример удобнее решать в столбик, сохрани запись столбиком и подробное пояснение по шагам.
10. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.
11. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом само условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай только по действиям.
5. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
6. По возможности используй школьную форму:
Если ..., то ...
7. После каждого действия коротко говори, что нашли.
8. Если задача составная, не перескакивай к ответу: сначала найди промежуточные величины.
9. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.

Важные требования:
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
Если в задаче два вопроса, ответь на оба по порядку.
Для многодейственных задач не перескакивай сразу к ответу.
Сначала действие, потом пояснение, потом следующее действие.
""".strip()



# --- FINAL PATCH 2026-04-12C: column steps inside mixed multi-step expressions ---

_PATCH_20260412C_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION = _detailed_format_expression_solution

_PATCH_20260412C_ORDINAL_WORDS = {
    1: "Первое",
    2: "Второе",
    3: "Третье",
    4: "Четвертое",
    5: "Пятое",
    6: "Шестое",
    7: "Седьмое",
    8: "Восьмое",
}


def _patch_20260412c_parse_int_text(value: str) -> Optional[int]:
    text = str(value or "").strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return None


def _patch_20260412c_global_column_flag(source: str) -> bool:
    numbers = [int(token) for token in re.findall(r"\d+", str(source or ""))]
    return any(abs(number) >= 100 for number in numbers) or count_two_digit_numbers(numbers) > 2


def _patch_20260412c_should_use_column_for_step(step: dict, source: str) -> bool:
    left = _patch_20260412c_parse_int_text(step.get("left", ""))
    right = _patch_20260412c_parse_int_text(step.get("right", ""))
    operator = step.get("operator")

    if left is None or right is None:
        return False

    global_flag = _patch_20260412c_global_column_flag(source)

    if operator == "+":
        return abs(left) >= 100 or abs(right) >= 100 or global_flag
    if operator == "-":
        if left < 0 or right < 0 or left < right:
            return False
        return abs(left) >= 100 or abs(right) >= 100 or global_flag
    if operator == "×":
        return abs(left) >= 100 or abs(right) >= 100
    if operator == ":":
        if right == 0:
            return False
        return abs(left) >= 100 or abs(right) >= 100
    return False


def _patch_20260412c_step_explanation_text(step: dict) -> Optional[str]:
    left = _patch_20260412c_parse_int_text(step.get("left", ""))
    right = _patch_20260412c_parse_int_text(step.get("right", ""))
    operator = step.get("operator")

    if left is None or right is None:
        return None

    if operator == "+":
        return explain_column_addition([left, right])
    if operator == "-":
        if left < 0 or right < 0 or left < right:
            return None
        return explain_column_subtraction(left, right)
    if operator == "×":
        return explain_long_multiplication(left, right)
    if operator == ":":
        if right == 0:
            return None
        return explain_long_division(left, right)
    return None


def _patch_20260412c_clean_body_lines(lines: List[str]) -> List[str]:
    cleaned: List[str] = []
    for raw in lines:
        line = re.sub(r"^\d+\)\s*", "", str(raw or "").strip())
        lower = line.lower()
        if not line:
            continue
        if lower.startswith("запись столбиком"):
            continue
        if lower.startswith("читаем ответ:"):
            continue
        cleaned.append(line)
    return cleaned


def _patch_20260412c_step_header(index: int, operator: str, left: str, right: str, use_column: bool) -> str:
    ordinal = _PATCH_20260412C_ORDINAL_WORDS.get(index, f"{index}-е")
    action_name = {
        "+": "сложение",
        "-": "вычитание",
        "×": "умножение",
        ":": "деление",
    }.get(operator, "действие")
    if use_column:
        return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right}. Выполним это действие в столбик"
    return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right} = {step_result_placeholder}"


def _patch_20260412c_render_mixed_expression_solution(source: str) -> Optional[str]:
    node = parse_expression_ast(source)
    if node is None:
        return None

    steps = _detailed_collect_expression_steps(node, source)
    if len(steps) <= 1:
        return None

    pretty_expression = _user_final_patch_pretty_expression_from_source(source)
    answer = _detailed_expression_answer(source) or "проверь запись"
    advice = (
        "сначала выполняй действия по порядку: в скобках, потом умножение и деление, потом сложение и вычитание"
        if "(" in source or ")" in source or re.search(r"[+\-].*[*/]|[*/].*[+\-]", source)
        else default_advice("expression")
    )

    lines: List[str] = [f"Пример: {pretty_expression} = {answer}"]
    order_block = _detailed_build_order_block(source)
    if order_block:
        lines.extend(order_block)
    lines.append("Решение по действиям:")

    for index, step in enumerate(steps, start=1):
        left = str(step.get("left", "")).strip()
        right = str(step.get("right", "")).strip()
        operator = str(step.get("operator", "")).strip()
        result = str(step.get("result", "")).strip()

        use_column = _patch_20260412c_should_use_column_for_step(step, source)
        if not use_column:
            ordinal = _PATCH_20260412C_ORDINAL_WORDS.get(index, f"{index}-е")
            action_name = {
                "+": "сложение",
                "-": "вычитание",
                "×": "умножение",
                ":": "деление",
            }.get(operator, "действие")
            lines.append(f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right} = {result}")
            continue

        lines.append(
            f"{index}) {_PATCH_20260412C_ORDINAL_WORDS.get(index, f'{index}-е')} действие: {left} {operator} {right}"
        )
        detailed = _patch_20260412c_step_explanation_text(step)
        if not detailed:
            lines.append(f"{left} {operator} {right} = {result}")
            continue

        parts = _detailed_split_sections(detailed)
        column_block, remaining_body = _split_ascii_layout_block(parts.get("body", []))
        cleaned_body = _patch_20260412c_clean_body_lines(remaining_body)

        if column_block:
            lines.extend(column_block)
        if cleaned_body:
            lines.append("Пояснение к действию:")
            lines.extend(cleaned_body)
        lines.append(f"Значит, {left} {operator} {right} = {result}")

    lines.append(f"Ответ: {answer}")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_expression_solution(raw_text: str, base_text: str) -> str:
    source = to_expression_source(raw_text)
    if not source:
        return _PATCH_20260412C_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)

    rendered = _patch_20260412c_render_mixed_expression_solution(source)
    if rendered:
        return rendered

    return _PATCH_20260412C_PREV_DETAILED_FORMAT_EXPRESSION_SOLUTION(raw_text, base_text)


# --- FINAL PATCH 2026-04-12C.1: safe helper text ---

def _patch_20260412c_step_header(index: int, operator: str, left: str, right: str, result: str, use_column: bool) -> str:
    ordinal = _PATCH_20260412C_ORDINAL_WORDS.get(index, f"{index}-е")
    action_name = {
        "+": "сложение",
        "-": "вычитание",
        "×": "умножение",
        ":": "деление",
    }.get(operator, "действие")
    if use_column:
        return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right}. Выполним это действие в столбик"
    return f"{index}) {ordinal} действие — {action_name}: {left} {operator} {right} = {result}"

# --- USER CONSOLIDATION PATCH 2026-04-12: fuller school-style wording without changing architecture ---


def explain_sum_then_subtract_word_problem(first: int, second: int, removed: int) -> Optional[str]:
    total = first + second
    remaining = total - removed
    if remaining < 0:
        return None
    return join_explanation_lines(
        f"1) Если сначала было {first} и ещё {second}, то всего было {first} + {second} = {total}",
        f"2) Если всего было {total}, а потом убрали {removed}, то осталось {total} - {removed} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если сначала объединяют две части, а потом часть убирают, сначала находят сумму",
    )



def explain_initial_from_taken_and_left_word_problem(first_taken: int, second_taken: int, left: int) -> Optional[str]:
    taken = first_taken + second_taken
    total = taken + left
    return join_explanation_lines(
        f"1) Если взяли {first_taken} и ещё {second_taken}, то всего взяли {first_taken} + {second_taken} = {taken}",
        f"2) Если взяли {taken}, а осталось {left}, то сначала было {taken} + {left} = {total}",
        f"Ответ: {total}",
        "Совет: если известны взяли и осталось, начальное число находят сложением",
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
        f"1) Если второе количество на {delta1} {mode1}, чем первое, то второе количество равно {base} {sign1} {delta1} = {second}",
        f"2) Если третье количество на {delta2} {mode2}, чем второе, то третье количество равно {second} {sign2} {delta2} = {third}",
        f"3) Если первое количество {base}, второе {second}, а третье {third}, то всего {base} + {second} + {third} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят все неизвестные количества, потом общее число",
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
        f"1) Если второе количество в {factor1} {plural_form(factor1, 'раз', 'раза', 'раз')} {mode1}, чем первое, то второе количество равно {base} {op1} {factor1} = {second}",
        f"2) Если третье количество в {factor2} {plural_form(factor2, 'раз', 'раза', 'раз')} {mode2}, чем второе, то третье количество равно {second} {op2} {factor2} = {third}",
        f"3) Если первое количество {base}, второе {second}, а третье {third}, то всего {base} + {second} + {third} = {total}",
        f"Ответ: {total}",
        "Совет: если числа связаны словами «в несколько раз», сначала находят каждое зависимое число отдельно",
    )



def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти расстояние, нужно скорость умножить на время",
        f"2) Если скорость равна {speed}, а время равно {time_value}, то расстояние равно {speed} × {time_value} = {result}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом S = v × t",
    )



def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти скорость, нужно расстояние разделить на время",
        f"2) Если расстояние равно {distance}, а время равно {time_value}, то скорость равна {distance} : {time_value} = {result}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом v = S : t",
    )



def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти время, нужно расстояние разделить на скорость",
        f"2) Если расстояние равно {distance}, а скорость равна {speed}, то время равно {distance} : {speed} = {result}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом t = S : v",
    )



def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2}, то скорость сближения равна {v1} + {v2} = {closing_speed}",
        f"2) Если скорость сближения равна {closing_speed}, а время равно {time_value}, то расстояние между пунктами равно {closing_speed} × {time_value} = {distance}",
        f"Ответ: {answer}",
        "Совет: при движении навстречу сначала находят скорость сближения",
    )



def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2} в противоположных направлениях, то скорость удаления равна {v1} + {v2} = {removal_speed}",
        f"2) Если скорость удаления равна {removal_speed}, а время равно {time_value}, то расстояние между ними равно {removal_speed} × {time_value} = {distance}",
        f"Ответ: {answer}",
        "Совет: при движении в противоположных направлениях сначала находят скорость удаления",
    )



def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        "1) Чтобы найти цену одного предмета, нужно стоимость разделить на количество",
        f"2) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб.",
        f"Ответ: {price} руб.",
        "Совет: пользуйся правилом Ц = С : К",
    )



def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        "1) Чтобы найти стоимость, нужно цену умножить на количество",
        f"2) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб.",
        f"Ответ: {total} руб.",
        "Совет: пользуйся правилом С = Ц × К",
    )



def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если купили {known_count} цветка по {known_price} руб., то за них заплатили {known_count} × {known_price} = {known_total} руб.",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за известные цветы заплатили {known_total} руб., то за остальные цветы заплатили {total_cost} - {known_total} = {other_total} руб.",
        f"3) Если за {unknown_count} остальных цветов заплатили {other_total} руб., то одна штука стоит {other_total} : {unknown_count} = {unit_price} руб.",
        f"Ответ: одна красная гвоздика стоила {unit_price} руб.",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть, а потом раздели на количество",
    )



def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_cost} руб., то один товар стоит {total_cost} : {quantity} = {price} руб.",
        f"2) Если один товар стоит {price} руб., то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на цену, количество и стоимость сначала находят цену одной штуки",
    )



def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    relation = "дороже" if price_a > price_b else "дешевле"
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a} руб., то цена одного товара равна {total_a} : {quantity} = {price_a} руб.",
        f"2) Если за {quantity} таких же товаров заплатили {total_b} руб., то цена одного товара равна {total_b} : {quantity} = {price_b} руб.",
        f"3) Если одна цена {price_a} руб., а другая {price_b} руб., то разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб.",
        f"Ответ: на {diff} руб. {relation}.",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


# --- FINAL CONSOLIDATED PATCH: textbook-style priorities and multi-question fixes ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень понятный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно и по-школьному.
Не используй markdown, таблицы, смайлики, лишние вступления и похвалу.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна полезная мысль.

Главные правила объяснения:
1. Объясняй подробно, по действиям и по шагам.
2. Не пропускай промежуточные вычисления.
3. Для текстовых задач по возможности используй форму:
Если ..., то ...
4. Сначала находи то, что нужно для главного вопроса, потом отвечай на главный вопрос.
5. Если вопросов два, ответь на оба по порядку.
6. Если запись непонятная, попроси записать задачу понятнее.

Для выражений:
1. Сначала напиши полный пример с ответом:
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, напиши:
Порядок действий:
и ниже тот же пример с цифрами 1, 2, 3 над знаками действий.
3. Потом напиши:
Решение по действиям:
4. Ниже:
1) ...
2) ...
3) ...
5. В конце:
Ответ: ...
6. Если пример удобно считать в столбик, сохрани столбик и подробное пояснение.

Для текстовых задач:
1. Сначала:
Задача.
2. Потом без изменения чисел запиши условие.
3. Потом:
Решение.
4. Затем обязательно:
Что известно: ...
Что нужно найти: ...
5. Дальше решай по действиям:
1) ...
2) ...
3) ...
6. После каждого действия коротко говори, что нашли.
7. В конце:
Ответ: ...

Для уравнений:
1. Сначала:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом считай по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если единицы разные, сначала переведи их в одинаковые единицы.
4. Потом решай по действиям.

Школьные методики:
Если задача в косвенной форме, сначала переведи её в прямую.
Если задача на приведение к единице, сначала найди одну группу, потом нужное количество групп.
Если задача на цену, количество и стоимость, используй связи:
стоимость = цена × количество;
цена = стоимость : количество;
количество = стоимость : цена.
Если задача на движение, используй связи:
S = v × t;
v = S : t;
t = S : v.
При встречном движении называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
""".strip()


_FINAL_CONSOLIDATED_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first


def _final_consolidated_questions(raw_text: str) -> List[str]:
    text = normalize_word_problem_text(raw_text)
    parts = [part.strip() for part in re.split(r"[?]", text) if part.strip()]
    return parts


def _final_consolidated_try_second_quantity_and_difference_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if lower.count("?") < 2:
        return None
    if "на сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None:
        return None

    diff = abs(base - second)
    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если первое количество равно {base}, а второе равно {second}, то разность равна {max(base, second)} - {min(base, second)} = {diff}",
        f"Ответ: второе количество — {second}{tail}; разность — {diff}{tail}",
        "Совет: если в задаче два вопроса, сначала находят второе число, потом сравнивают числа",
    )


def _final_consolidated_try_second_quantity_and_ratio_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if lower.count("?") < 2:
        return None
    if "во сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None or min(base, second) == 0:
        return None

    bigger = max(base, second)
    smaller = min(base, second)
    if bigger % smaller != 0:
        return None
    ratio = bigger // smaller

    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если большее количество равно {bigger}, а меньшее равно {smaller}, то кратное сравнение равно {bigger} : {smaller} = {ratio}",
        f"Ответ: второе количество — {second}{tail}; в {ratio} {plural_form(ratio, 'раз', 'раза', 'раз')}",
        "Совет: если нужно сначала найти второе число, а потом узнать, во сколько раз одно число больше другого, выполняй действия по порядку",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_consolidated_try_second_quantity_and_difference_explanation(user_text)
        or _final_consolidated_try_second_quantity_and_ratio_explanation(user_text)
        or _FINAL_CONSOLIDATED_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )



# --- FINAL CONSOLIDATED PATCH 2: detect second question even without second "?" ---

def _final_consolidated_has_two_question_clauses(raw_text: str) -> bool:
    text = normalize_word_problem_text(raw_text).strip()
    clauses = [part.strip() for part in re.split(r"[?.!]", text) if part.strip()]
    question_like = 0
    for clause in clauses:
        lower = clause.lower().replace("ё", "е")
        if re.match(r"^(сколько|на сколько|во сколько|какова|какой|какое|чему|найдите|узнайте)\b", lower):
            question_like += 1
    return question_like >= 2 or text.count("?") >= 2


def _final_consolidated_try_second_quantity_and_difference_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not _final_consolidated_has_two_question_clauses(raw_text):
        return None
    if "на сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None:
        return None

    diff = abs(base - second)
    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если первое количество равно {base}, а второе равно {second}, то разность равна {max(base, second)} - {min(base, second)} = {diff}",
        f"Ответ: второе количество — {second}{tail}; разность — {diff}{tail}",
        "Совет: если в задаче два вопроса, сначала находят второе число, потом сравнивают числа",
    )


def _final_consolidated_try_second_quantity_and_ratio_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if not _final_consolidated_has_two_question_clauses(raw_text):
        return None
    if "во сколько" not in lower:
        return None

    relation_pairs = extract_relation_pairs(lower)
    numbers = extract_ordered_numbers(lower)
    if len(relation_pairs) != 1 or len(numbers) != 2:
        return None

    base = numbers[0]
    delta_num = numbers[1]
    delta, mode = relation_pairs[0]
    if delta != delta_num:
        return None

    second = apply_more_less(base, delta, mode)
    if second is None or min(base, second) == 0:
        return None

    bigger = max(base, second)
    smaller = min(base, second)
    if bigger % smaller != 0:
        return None
    ratio = bigger // smaller

    answer_unit = _detect_question_unit(raw_text)
    if answer_unit == "руб":
        tail = " руб."
    elif answer_unit:
        tail = f" {answer_unit}"
    else:
        tail = ""

    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {'+' if mode == 'больше' else '-'} {delta} = {second}",
        f"2) Если большее количество равно {bigger}, а меньшее равно {smaller}, то кратное сравнение равно {bigger} : {smaller} = {ratio}",
        f"Ответ: второе количество — {second}{tail}; в {ratio} {plural_form(ratio, 'раз', 'раза', 'раз')}",
        "Совет: если нужно сначала найти второе число, а потом узнать, во сколько раз одно число больше другого, выполняй действия по порядку",
    )


def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_consolidated_try_second_quantity_and_difference_explanation(user_text)
        or _final_consolidated_try_second_quantity_and_ratio_explanation(user_text)
        or _FINAL_CONSOLIDATED_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )



# --- CONSOLIDATED FINAL PATCH 2026-04-12: textbook wording, stable final prompt, user-requested detail ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать развёрнутое решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
Пример: 6 × 5 + 40 : 2 = 50
2. Если действий несколько, обязательно пиши:
Порядок действий:
и ниже тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. Если пример удобно считать в столбик, сохрани запись столбиком и подробные пояснения.
6. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом условие задачи без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно:
Что известно: ...
Что нужно найти: ...
4. Дальше решай по действиям.
Каждое действие начинай с номера:
1) ...
2) ...
3) ...
5. По возможности используй школьную форму:
Если ..., то ...
6. После каждого действия коротко говори, что нашли.
7. В конце:
Ответ: ...

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если решение записывается по действиям, в каждом действии, кроме последнего, полезно писать пояснение, что именно нашли.
""".strip()


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе количество равно {second}, то всего будет {first} + {second} = {result}",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )



def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если сначала было {first}, а потом стало {second}, то разность равна {first} - {second} = {result}",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько осталось или на сколько уменьшилось, используют вычитание",
    )



def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если одно количество равно {bigger}, а другое равно {smaller}, то чтобы узнать, на сколько одно больше другого, нужно вычислить {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием: из большего числа вычитают меньшее",
    )



def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        f"1) Если после того как убрали {removed}, осталось {remaining}, то сначала было {remaining} + {removed} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы найти, сколько было сначала, к остатку прибавляют то, что убрали",
    )



def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если стало {final_total}, а прибавили {added}, то сначала было {final_total} - {added} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают прибавленную часть",
    )



def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {smaller}, а потом стало {bigger}, то добавили {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )



def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {bigger}, а потом осталось {smaller}, то убрали {bigger} - {smaller} = {result}",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )



def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего будет {groups} × {per_group} = {result}",
        f"Ответ: {result}",
        "Совет: если одинаковое количество повторяется несколько раз, используют умножение",
    )



def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines(
            "На ноль делить нельзя",
            "Ответ: деление на ноль невозможно",
            "Совет: сначала проверь, на сколько частей делят",
        )
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если {total} предметов разделили на {groups} равные части, то каждая часть равна {total} : {groups} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        f"1) Если {total} разделить на {groups}, то получится {quotient}, остаток {remainder}",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
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
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то групп будет {total} : {per_group} = {quotient}",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"1) Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}",
            f"2) Так как предметы ещё остались, нужна ещё одна группа, всего {quotient + 1}",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления что-то осталось, иногда нужна ещё одна коробка или ещё одно место",
        )
    if explicit_remainder:
        return join_explanation_lines(
            f"1) Если {total} разделить на группы по {per_group}, то получится {quotient}, остаток {remainder}",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None



def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, чем первое, то второе количество равно {base} {sign} {delta} = {result}",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )



def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, чем первое, то сначала найдём его: {base} {sign} {delta} = {related}",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: в составной задаче сначала находят неизвестное количество, потом сумму",
    )



def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем первое, то оно равно {base} {op} {factor} = {result}",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )



def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, чем первое, то сначала найдём его: {base} {op} {factor} = {related}",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего {base} + {related} = {total}",
        f"Ответ: {total}",
        "Совет: сначала находят число, которое дано через кратное отношение, а потом сумму",
    )



def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} группах {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}",
        f"2) Если в одной группе {one_group}, то в {target_groups} таких же группах {one_group} × {target_groups} = {result}",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )



def explain_find_third_addend_word_problem(total: int, first: int, second: int) -> Optional[str]:
    known = first + second
    result = total - known
    if result < 0:
        return None
    return join_explanation_lines(
        f"1) Если первая известная часть равна {first}, а вторая известная часть равна {second}, то вместе они составляют {first} + {second} = {known}",
        f"2) Если всего было {total}, а две известные части составляют {known}, то неизвестная часть равна {total} - {known} = {result}",
        f"Ответ: {result}",
        "Совет: неизвестную часть находят вычитанием суммы известных частей из целого",
    )



def explain_initial_from_taken_and_left_word_problem(first_taken: int, second_taken: int, left: int) -> Optional[str]:
    taken = first_taken + second_taken
    total = taken + left
    return join_explanation_lines(
        f"1) Если взяли {first_taken} и ещё {second_taken}, то всего взяли {first_taken} + {second_taken} = {taken}",
        f"2) Если взяли {taken}, а осталось {left}, то сначала было {taken} + {left} = {total}",
        f"Ответ: {total}",
        "Совет: если известно, сколько взяли и сколько осталось, начальное количество находят сложением",
    )



def explain_compare_from_total_and_part_word_problem(total: int, known_part: int) -> Optional[str]:
    other = total - known_part
    if other < 0:
        return None
    bigger = max(known_part, other)
    smaller = min(known_part, other)
    diff = bigger - smaller
    return join_explanation_lines(
        f"1) Если всего было {total}, а известная часть равна {known_part}, то другая часть равна {total} - {known_part} = {other}",
        f"2) Если одна часть равна {bigger}, а другая равна {smaller}, то разность равна {bigger} - {smaller} = {diff}",
        f"Ответ: {diff}",
        "Совет: если сначала нужно найти неизвестную часть, а потом сравнить части, действия выполняют по порядку",
    )



def explain_sum_of_two_products_word_problem(first_count: int, first_value: int, second_count: int, second_value: int) -> str:
    first_total = first_count * first_value
    second_total = second_count * second_value
    total = first_total + second_total
    return join_explanation_lines(
        f"1) Если первая покупка состоит из {first_count} предметов по {first_value}, то её стоимость равна {first_count} × {first_value} = {first_total}",
        f"2) Если вторая покупка состоит из {second_count} предметов по {second_value}, то её стоимость равна {second_count} × {second_value} = {second_total}",
        f"3) Если первая покупка стоит {first_total}, а вторая стоит {second_total}, то вся покупка стоит {first_total} + {second_total} = {total}",
        f"Ответ: {total}",
        "Совет: если в задаче есть две группы вида «по столько-то», сначала находят каждую группу отдельно",
    )



def explain_groups_plus_extra_word_problem(groups: int, per_group: int, extra: int) -> str:
    grouped_total = groups * per_group
    result = grouped_total + extra
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group}, то сначала находим, сколько предметов в этих группах: {groups} × {per_group} = {grouped_total}",
        f"2) Если в одинаковых группах {grouped_total}, а потом добавили ещё {extra}, то стало {grouped_total} + {extra} = {result}",
        f"Ответ: {result}",
        "Совет: если сначала считают одинаковые группы, а потом что-то добавляют, сначала выполняют умножение",
    )



def explain_sum_then_subtract_word_problem(first: int, second: int, removed: int) -> Optional[str]:
    total = first + second
    remaining = total - removed
    if remaining < 0:
        return None
    return join_explanation_lines(
        f"1) Если сначала было {first} и ещё {second}, то всего было {first} + {second} = {total}",
        f"2) Если всего было {total}, а потом убрали {removed}, то осталось {total} - {removed} = {remaining}",
        f"Ответ: {remaining}",
        "Совет: если сначала объединяют две группы, а потом часть убирают, сначала находят сумму",
    )



def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        f"1) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб.",
        f"Ответ: один предмет стоит {price} руб.",
        "Совет: цену одной штуки находят делением общей стоимости на количество",
    )



def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        f"1) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб.",
        f"Ответ: вся покупка стоит {total} руб.",
        "Совет: стоимость находят умножением цены на количество",
    )



def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если купили {known_count} известных предметов по {known_price} руб., то за них заплатили {known_count} × {known_price} = {known_total} руб.",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за известную часть {known_total} руб., то за вторую часть заплатили {total_cost} - {known_total} = {other_total} руб.",
        f"3) Если за {unknown_count} предметов заплатили {other_total} руб., то один предмет стоит {other_total} : {unknown_count} = {unit_price} руб.",
        f"Ответ: один предмет стоит {unit_price} руб.",
        "Совет: если известна общая стоимость покупки, сначала вычитают известную часть",
    )



def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    relation = "дороже" if price_a > price_b else "дешевле"
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых товаров заплатили {total_a} руб., то цена одного товара равна {total_a} : {quantity} = {price_a} руб.",
        f"2) Если за {quantity} таких же товаров заплатили {total_b} руб., то цена одного товара равна {total_b} : {quantity} = {price_b} руб.",
        f"3) Если одна цена {price_a} руб., а другая {price_b} руб., то разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб.",
        f"Ответ: на {diff} руб. {relation}.",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )



def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых коробок заплатили {total_cost} руб., то цена одной коробки равна {total_cost} : {quantity} = {price} руб.",
        f"2) Если одна коробка стоит {price} руб., то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result} коробок.",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находят цену одной коробки",
    )



def explain_fraction_of_number_word_problem(total: int, numerator: int, denominator: int, ask_remaining: bool = False) -> Optional[str]:
    if denominator == 0 or numerator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    taken = one_part * numerator
    if ask_remaining:
        remaining = total - taken
        return join_explanation_lines(
            f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}",
            f"3) Если всего было {total}, а использовали {taken}, то осталось {total} - {taken} = {remaining}",
            f"Ответ: {remaining}",
            "Совет: чтобы найти остаток после дробной части, сначала находят эту дробную часть",
        )
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}",
        f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}",
        f"Ответ: {taken}",
        "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
    )



def explain_number_by_fraction_word_problem(part_value: int, numerator: int, denominator: int) -> Optional[str]:
    if numerator == 0 or part_value % numerator != 0:
        return None
    one_part = part_value // numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если {numerator}/{denominator} числа равны {part_value}, то сначала найдём одну долю: {part_value} : {numerator} = {one_part}",
        f"2) Если одна доля равна {one_part}, то всё число равно {one_part} × {denominator} = {whole}",
        f"Ответ: {whole}",
        "Совет: чтобы найти всё число по его доле, сначала находят одну долю",
    )



def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег.",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part}.",
        f"3) Если одна доля равна {one_part}, то все деньги равны {one_part} × {denominator} = {whole}.",
        f"Ответ: {whole}",
        "Совет: если известен остаток после расхода части, сначала находят оставшуюся долю",
    )



def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти расстояние, нужно скорость умножить на время.",
        f"2) Если скорость равна {speed}, а время равно {time_value}, то расстояние равно {speed} × {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом S = v × t",
    )



def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти скорость, нужно расстояние разделить на время.",
        f"2) Если расстояние равно {distance}, а время равно {time_value}, то скорость равна {distance} : {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом v = S : t",
    )



def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти время, нужно расстояние разделить на скорость.",
        f"2) Если расстояние равно {distance}, а скорость равна {speed}, то время равно {distance} : {speed} = {answer}",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом t = S : v",
    )



def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2}, то скорость сближения равна {v1} + {v2} = {closing_speed}",
        f"2) Если скорость сближения равна {closing_speed}, а время равно {time_value}, то расстояние равно {closing_speed} × {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: при встречном движении сначала находят скорость сближения",
    )



def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2} в противоположных направлениях, то скорость удаления равна {v1} + {v2} = {removal_speed}",
        f"2) Если скорость удаления равна {removal_speed}, а время равно {time_value}, то расстояние между ними равно {removal_speed} × {time_value} = {answer}",
        f"Ответ: {answer}",
        "Совет: при движении в противоположных направлениях сначала находят скорость удаления",
    )



def explain_trip_time_for_same_distance(speed1: int, time1: int, speed2: int) -> Optional[str]:
    distance = speed1 * time1
    if speed2 == 0 or distance % speed2 != 0:
        return None
    time2 = distance // speed2
    return join_explanation_lines(
        f"1) Если первый участник ехал со скоростью {speed1} и был в пути {time1}, то расстояние равно {speed1} × {time1} = {distance}",
        f"2) Если это же расстояние равно {distance}, а скорость второго участника {speed2}, то ему понадобится {distance} : {speed2} = {time2} ч.",
        f"Ответ: {time2} ч.",
        "Совет: если путь один и тот же, сначала находят расстояние, потом новое время",
    )



def explain_second_day_motion_time(total_distance: int, first_speed: int, first_time: int, second_speed: int) -> Optional[str]:
    first_distance = first_speed * first_time
    second_distance = total_distance - first_distance
    if second_speed == 0 or second_distance < 0 or second_distance % second_speed != 0:
        return None
    second_time = second_distance // second_speed
    total_time = first_time + second_time
    return join_explanation_lines(
        f"1) Если в первый день скорость была {first_speed}, а время в пути {first_time}, то в первый день проехали {first_speed} × {first_time} = {first_distance} км.",
        f"2) Если всего нужно проехать {total_distance} км, а в первый день проехали {first_distance} км, то во второй день осталось {total_distance} - {first_distance} = {second_distance} км.",
        f"3) Если во второй день проехали {second_distance} км со скоростью {second_speed}, то время во второй день равно {second_distance} : {second_speed} = {second_time} ч.",
        f"4) Если в первый день были в пути {first_time} ч., а во второй день {second_time} ч., то всего были в пути {first_time} + {second_time} = {total_time} ч.",
        f"Ответ: во второй день — {second_time} ч.; всего — {total_time} ч.",
        "Совет: в составной задаче на движение сначала находят путь, потом время",
    )



def explain_remaining_part_speed(total_distance: int, first_speed: int, first_time: int, second_time: int) -> Optional[str]:
    first_distance = first_speed * first_time
    remaining_distance = total_distance - first_distance
    if second_time == 0 or remaining_distance < 0 or remaining_distance % second_time != 0:
        return None
    second_speed = remaining_distance // second_time
    return join_explanation_lines(
        f"1) Если сначала ехали со скоростью {first_speed} {first_time} ч., то первая часть пути равна {first_speed} × {first_time} = {first_distance} км.",
        f"2) Если весь путь равен {total_distance} км, а первая часть пути равна {first_distance} км, то оставшаяся часть пути равна {total_distance} - {first_distance} = {remaining_distance} км.",
        f"3) Если оставшаяся часть пути равна {remaining_distance} км, а прошли её за {second_time} ч., то скорость равна {remaining_distance} : {second_time} = {second_speed} км/ч.",
        f"Ответ: {second_speed} км/ч.",
        "Совет: если известны путь и время, скорость находят делением",
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
        f"1) Если расстояние равно {distance} км, а скорость в одну сторону {speed} км/ч, то время в одну сторону равно {distance} : {speed} = {first_time} ч.",
        f"2) Если обратно едут в {factor} раза быстрее, то скорость обратно равна {speed} × {factor} = {faster_speed} км/ч.",
        f"3) Если расстояние равно {distance} км, а скорость обратно {faster_speed} км/ч, то время на обратный путь равно {distance} : {faster_speed} = {return_time} ч.",
        f"Ответ: {return_time} ч.",
        "Совет: если на обратном пути скорость увеличилась в несколько раз, сначала находят новую скорость",
    )



# --- FINAL USER CONSOLIDATION PATCH 2026-04-12D: extra textbook motion case, fuller count nouns, stable final routing ---

# Добавляем несколько часто встречающихся школьных существительных,
# чтобы ответы чаще были полными, а не только числом.
try:
    QUESTION_NOUN_FORMS.update({
        "шарик": ("шарик", "шарика", "шариков"),
        "шарика": ("шарик", "шарика", "шариков"),
        "шариков": ("шарик", "шарика", "шариков"),
        "утенок": ("утёнок", "утёнка", "утят"),
        "утёнок": ("утёнок", "утёнка", "утят"),
        "утёнка": ("утёнок", "утёнка", "утят"),
        "утят": ("утёнок", "утёнка", "утят"),
        "гусенок": ("гусёнок", "гусёнка", "гусят"),
        "гусёнок": ("гусёнок", "гусёнка", "гусят"),
        "гусёнка": ("гусёнок", "гусёнка", "гусят"),
        "гусят": ("гусёнок", "гусёнка", "гусят"),
        "тюльпан": ("тюльпан", "тюльпана", "тюльпанов"),
        "тюльпана": ("тюльпан", "тюльпана", "тюльпанов"),
        "тюльпанов": ("тюльпан", "тюльпана", "тюльпанов"),
        "орешек": ("орешек", "орешка", "орешков"),
        "орешка": ("орешек", "орешка", "орешков"),
        "орешков": ("орешек", "орешка", "орешков"),
        "гостинец": ("гостинец", "гостинца", "гостинцев"),
        "гостинца": ("гостинец", "гостинца", "гостинцев"),
        "гостинцев": ("гостинец", "гостинца", "гостинцев"),
        "тетрадка": ("тетрадка", "тетрадки", "тетрадок"),
        "тетрадки": ("тетрадка", "тетрадки", "тетрадок"),
        "тетрадок": ("тетрадка", "тетрадки", "тетрадок"),
    })
except Exception:
    pass


def _final_user_20260412d_equal_speed_head_start_meeting_explanation(raw_text: str) -> Optional[str]:
    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    # Шаблон из книги:
    # "скорости одинаковые", "встретились через ... часов",
    # "первый ... выехал на ... часа раньше", "проехал на ... км больше".
    if "навстречу" not in lower:
        return None
    if "одинаков" not in lower:
        return None
    if "раньше" not in lower or "больше" not in lower:
        return None

    hour_pattern = fr"(\d+|{_NUMBER_WORD_PATTERN})\s*(?:ч|час(?:а|ов)?)"
    meet_match = re.search(fr"встретил(?:ся|ась|ось|ись)?\s+через\s+{hour_pattern}", lower)
    head_start_match = re.search(fr"на\s+{hour_pattern}\s+раньше", lower)
    extra_distance_match = re.search(r"на\s+(\d+)\s*(км|м)\s+больше", lower)

    if not meet_match or not head_start_match or not extra_distance_match:
        return None

    meet_time = parse_number_token(meet_match.group(1))
    head_start_time = parse_number_token(head_start_match.group(1))
    extra_distance = int(extra_distance_match.group(1))
    distance_unit = extra_distance_match.group(2)

    if meet_time is None or head_start_time is None:
        return None
    if head_start_time == 0 or extra_distance % head_start_time != 0:
        return None

    speed = extra_distance // head_start_time
    second_path = speed * meet_time
    first_time = meet_time + head_start_time
    first_path = speed * first_time
    total_distance = first_path + second_path
    speed_unit = f"{distance_unit}/ч"

    return join_explanation_lines(
        f"1) Если скорости одинаковые, а первый участник выехал на {head_start_time} ч. раньше и поэтому прошёл на {extra_distance} {distance_unit} больше, то скорость каждого равна {extra_distance} : {head_start_time} = {speed} {speed_unit}",
        f"2) Так как скорости одинаковые, скорость второго участника тоже равна {speed} {speed_unit}",
        f"3) Если второй участник ехал {meet_time} ч. со скоростью {speed} {speed_unit}, то он прошёл {speed} × {meet_time} = {second_path} {distance_unit}",
        f"4) Если первый участник выехал на {head_start_time} ч. раньше, то он был в пути {meet_time} + {head_start_time} = {first_time} ч.",
        f"5) Если первый участник ехал {first_time} ч. со скоростью {speed} {speed_unit}, то он прошёл {speed} × {first_time} = {first_path} {distance_unit}",
        f"6) Если один участник прошёл {second_path} {distance_unit}, а другой {first_path} {distance_unit}, то расстояние между пунктами равно {second_path} + {first_path} = {total_distance} {distance_unit}",
        f"Ответ: расстояние между пунктами равно {total_distance} {distance_unit}",
        "Совет: если скорости одинаковые, а один участник выехал раньше, его лишний путь помогает найти общую скорость",
    )


_FINAL_USER_20260412D_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_user_20260412d_equal_speed_head_start_meeting_explanation(user_text)
        or _FINAL_USER_20260412D_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )





# --- FINAL USER PATCH 2026-04-12E: fuller school wording, stable final prompt, preserved architecture ---

SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown-таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку «Порядок действий:».
3. Ниже пиши тот же пример, где над знаками действий стоят цифры 1, 2, 3... в порядке выполнения.
4. Потом пиши строку «Решение по действиям:».
5. Ниже пиши все вычисления по действиям:
1) ...
2) ...
3) ...
6. Если вычисление удобно выполнять в столбик, сохраняй запись столбиком и подробное пояснение по шагам.
7. Вычисления в столбик используй, когда в примере больше двух двузначных чисел или когда есть число из трёх и более цифр.
8. В конце пиши строку «Ответ: ...».

Для текстовых задач:
1. Сначала пиши «Задача.» и без изменения чисел переписывай условие.
2. Потом пиши «Решение.»
3. Затем обязательно пиши строки:
«Что известно: ...»
«Что нужно найти: ...»
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай только по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. Для школьного стиля по возможности используй форму «Если..., то ...».
8. После каждого действия коротко говори, что нашли.
9. Если в задаче несколько вопросов, отвечай на все вопросы по порядку.
10. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку «Уравнение: ...».
2. Потом «Решение.»
3. Решай по шагам.
4. Обязательно пиши строку «Проверка: ...».
5. Потом пиши «Ответ: ...».

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, скажи это отдельно.
3. Если знаменатели разные, сначала приведи дроби к общему знаменателю.
4. Если задача дана с величинами, сначала переведи величины в одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.
5. В ответе обязательно пиши единицы измерения.

Школьные правила и методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Сохраняй вычисления в столбик и подробные пояснения.
Для деления столбиком обязательно называй неполное делимое, подбор цифры, умножение, вычитание и снос следующей цифры.
""".strip()

try:
    QUESTION_NOUN_FORMS.update({
        "год": ("год", "года", "лет"),
        "года": ("год", "года", "лет"),
        "лет": ("год", "года", "лет"),
        "книга": ("книга", "книги", "книг"),
        "книги": ("книга", "книги", "книг"),
        "книг": ("книга", "книги", "книг"),
        "машина": ("машина", "машины", "машин"),
        "машины": ("машина", "машины", "машин"),
        "машин": ("машина", "машины", "машин"),
        "дерево": ("дерево", "дерева", "деревьев"),
        "дерева": ("дерево", "дерева", "деревьев"),
        "деревьев": ("дерево", "дерева", "деревьев"),
        "глазок": ("глазок", "глазка", "глазков"),
        "глазка": ("глазок", "глазка", "глазков"),
        "глазков": ("глазок", "глазка", "глазков"),
        "страница": ("страница", "страницы", "страниц"),
        "страницы": ("страница", "страницы", "страниц"),
        "страниц": ("страница", "страницы", "страниц"),
        "перо": ("перо", "пера", "перьев"),
        "пера": ("перо", "пера", "перьев"),
        "перьев": ("перо", "пера", "перьев"),
        "яблоко": ("яблоко", "яблока", "яблок"),
        "яблока": ("яблоко", "яблока", "яблок"),
        "яблок": ("яблоко", "яблока", "яблок"),
        "гвоздика": ("гвоздика", "гвоздики", "гвоздик"),
        "гвоздики": ("гвоздика", "гвоздики", "гвоздик"),
        "гвоздик": ("гвоздика", "гвоздики", "гвоздик"),
        "ягода": ("ягода", "ягоды", "ягод"),
        "ягоды": ("ягода", "ягоды", "ягод"),
        "ягод": ("ягода", "ягоды", "ягод"),
        "ложка": ("ложка", "ложки", "ложек"),
        "ложки": ("ложка", "ложки", "ложек"),
        "ложек": ("ложка", "ложки", "ложек"),
        "куст": ("куст", "куста", "кустов"),
        "куста": ("куст", "куста", "кустов"),
        "кустов": ("куст", "куста", "кустов"),
        "цветок": ("цветок", "цветка", "цветов"),
        "цветка": ("цветок", "цветка", "цветов"),
        "цветов": ("цветок", "цветка", "цветов"),
        "мешок": ("мешок", "мешка", "мешков"),
        "мешка": ("мешок", "мешка", "мешков"),
        "мешков": ("мешок", "мешка", "мешков"),
        "клетка": ("клетка", "клетки", "клеток"),
        "клетки": ("клетка", "клетки", "клеток"),
        "клеток": ("клетка", "клетки", "клеток"),
        "полка": ("полка", "полки", "полок"),
        "полки": ("полка", "полки", "полок"),
        "полок": ("полка", "полки", "полок"),
        "ведро": ("ведро", "ведра", "вёдер"),
        "ведра": ("ведро", "ведра", "вёдер"),
        "вёдер": ("ведро", "ведра", "вёдер"),
        "корзина": ("корзина", "корзины", "корзин"),
        "корзины": ("корзина", "корзины", "корзин"),
        "корзин": ("корзина", "корзины", "корзин"),
        "сетка": ("сетка", "сетки", "сеток"),
        "сетки": ("сетка", "сетки", "сеток"),
        "сеток": ("сетка", "сетки", "сеток"),
        "попугай": ("попугай", "попугая", "попугаев"),
        "попугая": ("попугай", "попугая", "попугаев"),
        "попугаев": ("попугай", "попугая", "попугаев"),
        "ученик": ("ученик", "ученика", "учеников"),
        "ученика": ("ученик", "ученика", "учеников"),
        "учеников": ("ученик", "ученика", "учеников"),
        "пассажир": ("пассажир", "пассажира", "пассажиров"),
        "пассажира": ("пассажир", "пассажира", "пассажиров"),
        "пассажиров": ("пассажир", "пассажира", "пассажиров"),
        "участок": ("участок", "участка", "участков"),
        "участка": ("участок", "участка", "участков"),
        "участков": ("участок", "участка", "участков"),
        "рыба": ("рыба", "рыбы", "рыб"),
        "рыбы": ("рыба", "рыбы", "рыб"),
        "рыб": ("рыба", "рыбы", "рыб"),
        "булочка": ("булочка", "булочки", "булочек"),
        "булочки": ("булочка", "булочки", "булочек"),
        "булочек": ("булочка", "булочки", "булочек"),
        "карандаш": ("карандаш", "карандаша", "карандашей"),
        "карандаша": ("карандаш", "карандаша", "карандашей"),
        "карандашей": ("карандаш", "карандаша", "карандашей"),
    })
except Exception:
    pass

_FINAL_20260412E_PREV_DETAILED_MAYBE_ENRICH_ANSWER = _detailed_maybe_enrich_answer

def _detailed_maybe_enrich_answer(answer: str, raw_text: str, kind: str) -> str:
    value = _FINAL_20260412E_PREV_DETAILED_MAYBE_ENRICH_ANSWER(answer, raw_text, kind)
    stripped = str(value or "").strip()
    if not stripped:
        return stripped
    if re.fullmatch(r"-?\d+(?:/\d+)?", stripped):
        try:
            return _patch_answer_with_question_noun(int(Fraction(stripped)), raw_text)
        except Exception:
            return stripped
    return stripped


def explain_addition_word_problem(first: int, second: int) -> str:
    result = first + second
    return join_explanation_lines(
        f"1) Если первое количество равно {first}, а второе количество равно {second}, то всего будет {first} + {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если спрашивают, сколько всего или сколько стало, обычно нужно сложение",
    )


def explain_subtraction_word_problem(first: int, second: int) -> str:
    result = first - second
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если сначала было {first}, а потом убрали {second}, то осталось {first} - {second} = {result}.",
        f"Ответ: {result}",
        "Совет: если нужно узнать, сколько осталось, обычно используют вычитание",
    )


def explain_comparison_word_problem(first: int, second: int) -> str:
    bigger = max(first, second)
    smaller = min(first, second)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если одно количество равно {bigger}, а другое равно {smaller}, то чтобы узнать, на сколько одно больше другого, нужно вычислить {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: вопрос «на сколько» решают вычитанием: из большего числа вычитают меньшее",
    )


def explain_find_initial_after_loss_problem(remaining: int, removed: int) -> str:
    result = remaining + removed
    return join_explanation_lines(
        f"1) Если после того, как убрали {removed}, осталось {remaining}, то сначала было {remaining} + {removed} = {result}.",
        f"Ответ: {result}",
        "Совет: неизвестное уменьшаемое находят сложением",
    )


def explain_find_initial_after_gain_problem(final_total: int, added: int) -> str:
    result = final_total - added
    if result < 0:
        return ""
    return join_explanation_lines(
        f"1) Если стало {final_total}, а прибавили {added}, то сначала было {final_total} - {added} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы найти число до прибавления, из нового числа вычитают то, что прибавили",
    )


def explain_find_added_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {smaller}, а потом стало {bigger}, то добавили {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько добавили, из нового числа вычитают старое",
    )


def explain_find_removed_problem(before: int, after: int) -> str:
    bigger = max(before, after)
    smaller = min(before, after)
    result = bigger - smaller
    return join_explanation_lines(
        f"1) Если сначала было {bigger}, а потом осталось {smaller}, то убрали {bigger} - {smaller} = {result}.",
        f"Ответ: {result}",
        "Совет: чтобы узнать, сколько убрали, из того, что было, вычитают то, что осталось",
    )


def explain_multiplication_word_problem(groups: int, per_group: int) -> str:
    result = groups * per_group
    return join_explanation_lines(
        f"1) Если есть {groups} одинаковых групп по {per_group} в каждой, то всего будет {groups} × {per_group} = {result}.",
        f"Ответ: {result}",
        "Совет: слова «по ... в каждой» подсказывают умножение",
    )


def explain_sharing_word_problem(total: int, groups: int) -> Optional[str]:
    if groups == 0:
        return join_explanation_lines("На ноль делить нельзя.", "Ответ: деление на ноль невозможно", "Совет: сначала проверь делитель")
    quotient, remainder = divmod(total, groups)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если {total} предметов разделили на {groups} равные части, то в каждой части будет {total} : {groups} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: слова «поровну» и «каждый» подсказывают деление",
        )
    return join_explanation_lines(
        f"1) Если {total} разделить на {groups}, то получится {quotient}, остаток {remainder}.",
        f"Ответ: {quotient}, остаток {remainder}",
        "Совет: остаток всегда должен быть меньше делителя",
    )


def explain_group_count_word_problem(total: int, per_group: int, needs_extra_group: bool = False, explicit_remainder: bool = False) -> Optional[str]:
    if per_group == 0:
        return join_explanation_lines("В одной группе не может быть 0 предметов.", "Ответ: запись задачи неверная", "Совет: проверь размер одной группы")
    quotient, remainder = divmod(total, per_group)
    if remainder == 0:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то число групп равно {total} : {per_group} = {quotient}.",
            f"Ответ: {quotient}",
            "Совет: число групп находят делением",
        )
    if needs_extra_group:
        return join_explanation_lines(
            f"1) Полных групп получится {quotient}, потому что {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"2) Так как предметы ещё остались, нужна ещё одна группа. Всего групп будет {quotient + 1}.",
            f"Ответ: {quotient + 1}",
            "Совет: если после деления ещё есть остаток, иногда нужна ещё одна коробка или корзина",
        )
    if explicit_remainder:
        return join_explanation_lines(
            f"1) Если всего {total} предметов, а в одной группе по {per_group}, то {total} : {per_group} = {quotient}, остаток {remainder}.",
            f"Ответ: {quotient}, остаток {remainder}",
            "Совет: остаток всегда должен быть меньше размера одной группы",
        )
    return None


def explain_related_quantity_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    result = apply_more_less(base, delta, mode)
    if result is None:
        return None
    sign = "+" if mode == "больше" else "-"
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то его находим так: {base} {sign} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: если число на несколько единиц больше, прибавляют; если меньше, вычитают",
    )


def explain_related_total_word_problem(base: int, delta: int, mode: str) -> Optional[str]:
    related = apply_more_less(base, delta, mode)
    if related is None:
        return None
    sign = "+" if mode == "больше" else "-"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {sign} {delta} = {related}.",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего будет {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: если нельзя сразу ответить на главный вопрос, сначала находят неизвестное количество",
    )


def explain_related_quantity_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    result = apply_times_relation(base, factor, mode)
    if result is None:
        return None
    op = "×" if mode == "больше" else ":"
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то его находим так: {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: если число в несколько раз больше, умножают; если в несколько раз меньше, делят",
    )


def explain_related_total_times_word_problem(base: int, factor: int, mode: str) -> Optional[str]:
    related = apply_times_relation(base, factor, mode)
    if related is None:
        return None
    op = "×" if mode == "больше" else ":"
    total = base + related
    return join_explanation_lines(
        f"1) Если второе количество в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {mode}, то сначала находим его: {base} {op} {factor} = {related}.",
        f"2) Если первое количество равно {base}, а второе равно {related}, то всего будет {base} + {related} = {total}.",
        f"Ответ: {total}",
        "Совет: сначала найди число, которое дано через отношение, потом считай общее количество",
    )


def explain_indirect_plus_minus_problem(base: int, delta: int, relation: str) -> Optional[str]:
    if relation in {"старше", "больше"}:
        result = base - delta
        if result < 0:
            return None
        transformed = "значит, другое число на столько же меньше"
        op = "-"
    else:
        result = base + delta
        transformed = "значит, другое число на столько же больше"
        op = "+"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число на {delta} {relation}, то {transformed}.",
        f"2) Тогда искомое число равно {base} {op} {delta} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переводят условие в прямую форму",
    )


def explain_indirect_times_problem(base: int, factor: int, relation: str) -> Optional[str]:
    if relation == "больше":
        if factor == 0 or base % factor != 0:
            return None
        result = base // factor
        transformed = "значит, другое число во столько же раз меньше"
        op = ":"
    else:
        result = base * factor
        transformed = "значит, другое число во столько же раз больше"
        op = "×"
    return join_explanation_lines(
        f"1) Это задача в косвенной форме: если одно число в {factor} {plural_form(factor, 'раз', 'раза', 'раз')} {relation}, то {transformed}.",
        f"2) Тогда искомое число равно {base} {op} {factor} = {result}.",
        f"Ответ: {result}",
        "Совет: в косвенной задаче сначала переводят условие в прямую форму",
    )


def explain_bring_to_unit_total_word_problem(groups: int, total_amount: int, target_groups: int) -> Optional[str]:
    if groups == 0 or total_amount % groups != 0:
        return None
    one_group = total_amount // groups
    result = one_group * target_groups
    return join_explanation_lines(
        f"1) Если в {groups} одинаковых группах всего {total_amount}, то в одной группе {total_amount} : {groups} = {one_group}.",
        f"2) Если в одной группе {one_group}, то в {target_groups} таких же группах {one_group} × {target_groups} = {result}.",
        f"Ответ: {result}",
        "Совет: в задачах на приведение к единице сначала находят одну группу",
    )


def explain_price_difference_problem(quantity: int, total_a: int, total_b: int) -> Optional[str]:
    if quantity == 0 or total_a % quantity != 0 or total_b % quantity != 0:
        return None
    price_a = total_a // quantity
    price_b = total_b // quantity
    diff = abs(price_a - price_b)
    return join_explanation_lines(
        f"1) Если {quantity} одинаковых товаров стоят {total_a} руб., то один товар стоит {total_a} : {quantity} = {price_a} руб.",
        f"2) Если такие же {quantity} товаров стоят {total_b} руб., то один товар стоит {total_b} : {quantity} = {price_b} руб.",
        f"3) Тогда разность цен равна {max(price_a, price_b)} - {min(price_a, price_b)} = {diff} руб.",
        f"Ответ: {diff} руб.",
        "Совет: чтобы сравнить цену одинакового количества товаров, сначала находят цену одной штуки",
    )


def explain_price_quantity_cost_problem(quantity: int, total_cost: int, wanted_cost: int) -> Optional[str]:
    if quantity == 0 or total_cost % quantity != 0:
        return None
    price = total_cost // quantity
    if price == 0 or wanted_cost % price != 0:
        return None
    result = wanted_cost // price
    return join_explanation_lines(
        f"1) Если за {quantity} одинаковых коробок заплатили {total_cost} руб., то одна коробка стоит {total_cost} : {quantity} = {price} руб.",
        f"2) Если одна коробка стоит {price} руб., то на {wanted_cost} руб. можно купить {wanted_cost} : {price} = {result}.",
        f"Ответ: {result}",
        "Совет: если цена одинаковая, сначала находят цену одной коробки",
    )


def explain_simple_price_per_item(count: int, total_cost: int) -> Optional[str]:
    if count == 0 or total_cost % count != 0:
        return None
    price = total_cost // count
    return join_explanation_lines(
        f"1) Если {count} одинаковых предметов стоят {total_cost} руб., то один предмет стоит {total_cost} : {count} = {price} руб.",
        f"Ответ: один предмет стоит {price} руб.",
        "Совет: цену одной штуки находят делением общей стоимости на количество",
    )


def explain_simple_total_cost(price: int, count: int) -> str:
    total = price * count
    return join_explanation_lines(
        f"1) Если один предмет стоит {price} руб., а купили {count} предметов, то вся покупка стоит {price} × {count} = {total} руб.",
        f"Ответ: вся покупка стоит {total} руб.",
        "Совет: стоимость находят умножением цены на количество",
    )


def explain_unknown_red_price(known_count: int, known_price: int, unknown_count: int, total_cost: int) -> Optional[str]:
    known_total = known_count * known_price
    other_total = total_cost - known_total
    if unknown_count == 0 or other_total < 0 or other_total % unknown_count != 0:
        return None
    unit_price = other_total // unknown_count
    return join_explanation_lines(
        f"1) Если купили {known_count} белых гвоздики по {known_price} руб., то за белые гвоздики заплатили {known_count} × {known_price} = {known_total} руб.",
        f"2) Если за всю покупку заплатили {total_cost} руб., а за белые гвоздики {known_total} руб., то за красные гвоздики заплатили {total_cost} - {known_total} = {other_total} руб.",
        f"3) Если за {unknown_count} красных гвоздик заплатили {other_total} руб., то одна красная гвоздика стоила {other_total} : {unknown_count} = {unit_price} руб.",
        f"Ответ: одна красная гвоздика стоила {unit_price} руб.",
        "Совет: если известна общая стоимость покупки, сначала вычти известную часть",
    )


def explain_whole_by_remaining_fraction(remaining_value: int, spent_numerator: int, denominator: int) -> Optional[str]:
    remaining_numerator = denominator - spent_numerator
    if denominator == 0 or remaining_numerator <= 0:
        return None
    if remaining_value % remaining_numerator != 0:
        return None
    one_part = remaining_value // remaining_numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если израсходовали {spent_numerator}/{denominator} всех денег, то осталось {remaining_numerator}/{denominator} всех денег.",
        f"2) Если {remaining_numerator}/{denominator} всех денег равны {remaining_value}, то одна доля равна {remaining_value} : {remaining_numerator} = {one_part}.",
        f"3) Если одна доля равна {one_part}, то все деньги равны {one_part} × {denominator} = {whole}.",
        f"Ответ: всего было {whole}",
        "Совет: если известен остаток после расхода части, сначала находят оставшуюся долю",
    )


def explain_fraction_of_number_word_problem(total: int, numerator: int, denominator: int, ask_remaining: bool = False) -> Optional[str]:
    if denominator == 0 or numerator == 0 or total % denominator != 0:
        return None
    one_part = total // denominator
    taken = one_part * numerator
    if ask_remaining:
        remaining = total - taken
        return join_explanation_lines(
            f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}.",
            f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}.",
            f"3) Если всего было {total}, а использовали {taken}, то осталось {total} - {taken} = {remaining}.",
            f"Ответ: {remaining}",
            "Совет: чтобы найти остаток после дробной части, сначала находят эту часть",
        )
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}.",
        f"2) Если нужно найти {numerator}/{denominator} числа, то эта часть равна {one_part} × {numerator} = {taken}.",
        f"Ответ: {taken}",
        "Совет: чтобы найти часть от числа, сначала делят на знаменатель, потом умножают на числитель",
    )


def explain_number_by_fraction_word_problem(part_value: int, numerator: int, denominator: int) -> Optional[str]:
    if numerator == 0 or part_value % numerator != 0:
        return None
    one_part = part_value // numerator
    whole = one_part * denominator
    return join_explanation_lines(
        f"1) Если {numerator}/{denominator} числа равны {part_value}, то сначала найдём одну долю: {part_value} : {numerator} = {one_part}.",
        f"2) Если одна доля равна {one_part}, то всё число равно {one_part} × {denominator} = {whole}.",
        f"Ответ: {whole}",
        "Совет: чтобы найти всё число по его доле, сначала находят одну долю",
    )


def explain_two_fraction_parts_remaining(total: int, first_fraction: Tuple[int, int], second_fraction: Tuple[int, int]) -> Optional[str]:
    n1, d1 = first_fraction
    n2, d2 = second_fraction
    if d1 == 0 or d2 == 0 or total % math.lcm(d1, d2) != 0:
        return None
    first_part = total * n1 // d1
    second_part = total * n2 // d2
    used = first_part + second_part
    remaining = total - used
    return join_explanation_lines(
        f"1) Если всё число равно {total}, то первая часть равна {total} : {d1} × {n1} = {first_part}.",
        f"2) Если всё число равно {total}, то вторая часть равна {total} : {d2} × {n2} = {second_part}.",
        f"3) Если использовали {first_part} и {second_part}, то всего использовали {first_part} + {second_part} = {used}.",
        f"4) Тогда осталось {total} - {used} = {remaining}.",
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
        f"1) Если всё число равно {total}, то одна доля равна {total} : {denominator} = {one_part}.",
        f"2) Если первая часть составляет {numerator}/{denominator}, то первая часть равна {one_part} × {numerator} = {first_part}.",
        f"3) Тогда вторая часть равна {total} - {first_part} = {second_part}.",
        f"Ответ: {second_part}",
        "Совет: чтобы найти другую часть, сначала находят известную часть, потом вычитают её из целого",
    )


def explain_simple_motion_distance(speed: int, time_value: int, unit: str = "") -> str:
    result = speed * time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти расстояние, нужно скорость умножить на время.",
        f"2) Если скорость равна {speed}, а время равно {time_value}, то расстояние равно {speed} × {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом S = v × t",
    )


def explain_simple_motion_speed(distance: int, time_value: int, unit: str = "") -> Optional[str]:
    if time_value == 0 or distance % time_value != 0:
        return None
    result = distance // time_value
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти скорость, нужно расстояние разделить на время.",
        f"2) Если расстояние равно {distance}, а время равно {time_value}, то скорость равна {distance} : {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом v = S : t",
    )


def explain_simple_motion_time(distance: int, speed: int, unit: str = "") -> Optional[str]:
    if speed == 0 or distance % speed != 0:
        return None
    result = distance // speed
    answer = f"{result} {unit}".strip() if unit else str(result)
    return join_explanation_lines(
        "1) Чтобы найти время, нужно расстояние разделить на скорость.",
        f"2) Если расстояние равно {distance}, а скорость равна {speed}, то время равно {distance} : {speed} = {answer}.",
        f"Ответ: {answer}",
        "Совет: пользуйся правилом t = S : v",
    )


def explain_meeting_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    closing_speed = v1 + v2
    distance = closing_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2}, то скорость сближения равна {v1} + {v2} = {closing_speed}.",
        f"2) Если скорость сближения равна {closing_speed}, а время равно {time_value}, то расстояние равно {closing_speed} × {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: при встречном движении сначала находят скорость сближения",
    )


def explain_opposite_motion(v1: int, v2: int, time_value: int, unit: str = "") -> str:
    removal_speed = v1 + v2
    distance = removal_speed * time_value
    answer = f"{distance} {unit}".strip() if unit else str(distance)
    return join_explanation_lines(
        f"1) Если один участник движется со скоростью {v1}, а другой со скоростью {v2} в противоположных направлениях, то скорость удаления равна {v1} + {v2} = {removal_speed}.",
        f"2) Если скорость удаления равна {removal_speed}, а время равно {time_value}, то расстояние между ними равно {removal_speed} × {time_value} = {answer}.",
        f"Ответ: {answer}",
        "Совет: при движении в противоположных направлениях сначала находят скорость удаления",
    )


def _final_20260412e_together_as_much_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    if "столько, сколько" not in lower:
        return None
    if not has_multiple_questions(text):
        return None
    relation_pairs = extract_relation_pairs(lower)
    nums = extract_ordered_numbers(lower)
    if len(nums) < 2 or not relation_pairs:
        return None
    base = nums[0]
    delta, mode = relation_pairs[0]
    second = apply_more_less(base, delta, mode)
    if second is None:
        return None
    third = base + second
    total = base + second + third
    sign = "+" if mode == "больше" else "-"
    third_name = ""
    m = re.search(r"а\s+([а-яё]+)\s+столько,\s+сколько", lower)
    if m:
        third_name = m.group(1)
    all_name = ""
    if "цвет" in lower:
        all_name = "цветов"
    answer_third = f"{third_name} было {third}" if third_name else f"третье количество равно {third}"
    answer_total = f"всего было {total} {all_name}".strip()
    return join_explanation_lines(
        f"1) Если второе количество на {delta} {mode}, то сначала находим его: {base} {sign} {delta} = {second}.",
        f"2) Если третье количество равно первому и второму вместе, то оно равно {base} + {second} = {third}.",
        f"3) Если первое количество равно {base}, второе равно {second}, а третье равно {third}, то всего {base} + {second} + {third} = {total}.",
        f"Ответ: {answer_third}; {answer_total}",
        "Совет: если сказано «столько, сколько вместе», сначала находят сумму этих частей",
    )


_FINAL_20260412E_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_20260412e_together_as_much_explanation(user_text)
        or _FINAL_20260412E_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи.",
            "Запишите пример или задачу полнее и без сокращений.",
            "Ответ: пока нужен более понятный ввод.",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2400,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- FINAL CONSOLIDATION PATCH 2026-04-12F: broader math guard + tasks with letters ---

MATH_INPUT_HINTS = (
    "сколько", "сколько всего", "сколько стало", "сколько осталось", "на сколько", "во сколько",
    "больше", "меньше", "поровну", "по ", "стоимость", "цена", "количество", "купили",
    "скорость", "расстояние", "время", "площадь", "периметр", "доля", "часть",
    "уравнение", "пример", "выражение", "реши", "найди", "найдите",
)

def looks_like_math_input(text: str) -> bool:
    base = normalize_word_problem_text(text).lower()
    if re.search(r"\d|x|х|[+\-*/=×÷:]", base):
        return True
    if re.search(r"\b[a-z]\b", base) and any(hint in base for hint in MATH_INPUT_HINTS):
        return True
    # допускаем словесные задачи без цифр, если в них есть школьные математические маркеры
    if any(hint in base for hint in MATH_INPUT_HINTS):
        return True
    return False


def _final_letter_task_shelf_more_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"на первой полке\s+([a-z])\s+книг[^.?!]*на\s+([a-z])\s+больше[^.?!]*на второй",
        lower,
    )
    if not match:
        return None
    total_symbol = match.group(1)
    delta_symbol = match.group(2)
    return join_explanation_lines(
        f"1) Если на первой полке {total_symbol} книг и это на {delta_symbol} больше, чем на второй, то на второй полке на {delta_symbol} книг меньше.",
        f"2) Если на первой полке {total_symbol} книг, а на второй на {delta_symbol} книг меньше, то на второй полке {total_symbol} - {delta_symbol} книг.",
        f"Ответ: на второй полке {total_symbol} - {delta_symbol} книг.",
        "Совет: в задаче с буквами действуй так же, как в задаче с числами: сначала переведи косвенную форму в прямую.",
    )


def _final_letter_task_tourist_remaining_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"турист должен пройти\s+([a-z])\s+км[^.?!]*в первый день[^.?!]*прош[её]л\s+([a-z])\s+км[^.?!]*во второй\s+([a-z])\s+км",
        lower,
    )
    if not match:
        return None
    total_symbol, first_symbol, second_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если в первый день турист прошёл {first_symbol} км, а во второй {second_symbol} км, то за два дня он прошёл {first_symbol} + {second_symbol} км.",
        f"2) Если турист должен пройти {total_symbol} км, а уже прошёл {first_symbol} + {second_symbol} км, то ему осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        f"Ответ: туристу осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        "Совет: в буквенной задаче сначала находят уже пройденный путь, потом вычитают его из всего пути.",
    )


def _final_letter_task_trains_passengers_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"прибыл[ао]?|прибыло", lower
    )
    if not match:
        return None
    match = re.search(
        r"на вокзал прибыл[ао]?\s+([a-z])\s+поезд[ао]в?\s+по\s+([a-z])\s+пассажир",
        lower,
    )
    if not match:
        return None
    trains_symbol, passengers_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если на вокзал прибыло {trains_symbol} поездов по {passengers_symbol} пассажиров в каждом, то всего прибыло {trains_symbol} × {passengers_symbol} пассажиров.",
        f"Ответ: прибыло {trains_symbol} × {passengers_symbol} пассажиров.",
        "Совет: если одно и то же количество повторяется несколько раз, используют умножение.",
    )


def _final_letter_task_garland_ratio_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"гирлянде\s+([a-z])\s+красных лампочек\s+и\s+([a-z])\s+зеленых|гирлянде\s+([a-z])\s+красных лампочек\s+и\s+([a-z])\s+зелёных",
        lower,
    )
    if not match:
        return None
    groups = [g for g in match.groups() if g]
    if len(groups) != 2:
        return None
    red_symbol, green_symbol = groups
    return join_explanation_lines(
        f"1) Чтобы узнать, во сколько раз зелёных лампочек больше, чем красных, нужно количество зелёных разделить на количество красных.",
        f"2) Значит, нужно вычислить {green_symbol} : {red_symbol}.",
        f"Ответ: в {green_symbol} : {red_symbol} раза.",
        "Совет: вопрос «во сколько раз» решают делением большего количества на меньшее.",
    )


def _final_letter_task_factories_total_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"один завод выпустил\s+([a-z])\s+станков[^.?!]*в\s+([a-z])\s+раз\s+меньше",
        lower,
    )
    if not match:
        return None
    first_symbol, factor_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если один завод выпустил {first_symbol} станков, а второй в {factor_symbol} раз меньше, то второй завод выпустил {first_symbol} : {factor_symbol} станков.",
        f"2) Если первый завод выпустил {first_symbol} станков, а второй {first_symbol} : {factor_symbol} станков, то вместе они выпустили {first_symbol} + {first_symbol} : {factor_symbol} станков.",
        f"Ответ: вместе заводы выпустили {first_symbol} + {first_symbol} : {factor_symbol} станков.",
        "Совет: если число дано через «в несколько раз меньше», сначала делят, а потом находят сумму.",
    )


def _final_letter_word_problem_explanation(raw_text: str) -> Optional[str]:
    return (
        _final_letter_task_shelf_more_explanation(raw_text)
        or _final_letter_task_tourist_remaining_explanation(raw_text)
        or _final_letter_task_trains_passengers_explanation(raw_text)
        or _final_letter_task_garland_ratio_explanation(raw_text)
        or _final_letter_task_factories_total_explanation(raw_text)
    )


SYSTEM_PROMPT = SYSTEM_PROMPT + "\nЕсли в задаче вместо чисел стоят буквы, решай её теми же школьными методами и давай ответ буквенным выражением."

_FINAL_20260412F_PREV_BUILD_EXPLANATION_LOCAL_FIRST = build_explanation_local_first

def build_explanation_local_first(user_text: str, kind: str) -> Optional[str]:
    return (
        _final_letter_word_problem_explanation(user_text)
        or _FINAL_20260412F_PREV_BUILD_EXPLANATION_LOCAL_FIRST(user_text, kind)
    )


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи.",
            "Запишите пример или задачу полнее и без сокращений.",
            "Ответ: пока нужен более понятный ввод.",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2400,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}


# --- PATCH 2026-04-12F1: robust tourist-letter task ---

def _final_letter_task_tourist_remaining_explanation(raw_text: str) -> Optional[str]:
    text = normalize_word_problem_text(raw_text)
    lower = text.lower().replace("ё", "е")
    match = re.search(
        r"турист должен пройти\s+([a-z])\s+км[\s\S]*?в первый день[\s\S]*?прош[её]л\s+([a-z])\s+км[\s\S]*?во второй[\s\S]*?([a-z])\s+км",
        lower,
    )
    if not match:
        return None
    total_symbol, first_symbol, second_symbol = match.groups()
    return join_explanation_lines(
        f"1) Если в первый день турист прошёл {first_symbol} км, а во второй {second_symbol} км, то за два дня он прошёл {first_symbol} + {second_symbol} км.",
        f"2) Если турист должен пройти {total_symbol} км, а уже прошёл {first_symbol} + {second_symbol} км, то ему осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        f"Ответ: туристу осталось пройти {total_symbol} - ({first_symbol} + {second_symbol}) км.",
        "Совет: в буквенной задаче сначала находят уже пройденный путь, потом вычитают его из всего пути.",
    )



# --- USER FINAL CONSOLIDATION PATCH 2026-04-12G: fuller textbook answers, better known/question extraction ---

_USER_FINAL_20260412G_PREV_EXTRACT_CONDITION_AND_QUESTION = extract_condition_and_question


SYSTEM_PROMPT = """
Ты — спокойный, точный и очень подробный учитель математики для детей 7–10 лет.
Пиши только по-русски.
Пиши просто, ясно, по-школьному.
Не используй markdown, таблицы, смайлики, похвалу и лишние вступления.
Не меняй числа из условия и не придумывай новые данные.
Каждая строка — одна законченная полезная мысль.

Главная цель:
давать подробное решение по действиям и по шагам;
не пропускать промежуточные вычисления;
объяснять так, как это делают в начальной школе в тетради и в учебнике.

Для выражений и примеров:
1. В первой строке пиши полный пример с ответом.
2. Если действий несколько, обязательно пиши строку:
Порядок действий:
и ниже тот же пример, где над математическими знаками стоят цифры 1, 2, 3... в порядке выполнения.
3. Потом пиши строку:
Решение по действиям:
4. Ниже пиши вычисления по действиям:
1) ...
2) ...
3) ...
5. Если пример удобнее решать в столбик, сохраняй запись столбиком и подробное пояснение по шагам.
6. Вычисления в столбик используй, когда в выражении больше двух двузначных чисел или когда есть число из трёх и более цифр.
7. В конце пиши:
Ответ: ...

Для текстовых задач:
1. Сначала пиши:
Задача.
Потом перепиши условие без изменения чисел.
2. Потом пиши:
Решение.
3. Затем обязательно пиши:
Что известно: ...
Что нужно найти: ...
4. Если нельзя сразу ответить на главный вопрос, сначала найди то, что нужно для ответа.
5. Решай по действиям.
6. Каждое действие начинай с номера:
1) ...
2) ...
3) ...
7. В каждом действии, где это уместно, используй школьную форму:
Если ..., то ...
8. После каждого действия коротко говори, что нашли.
9. Если решение записывается по действиям, то в каждом действии, кроме последнего, полезно писать пояснение, что именно нашли.
10. В конце пиши полный ответ, а не только число.

Для уравнений:
1. Пиши строку:
Уравнение: ...
2. Потом:
Решение.
3. Дальше шаги с номерами.
4. Обязательно пиши:
Проверка: ...
5. Потом:
Ответ: ...

Для дробей:
1. Сначала смотри на знаменатели.
2. Если знаменатели одинаковые, объясни это отдельно.
3. Если знаменатели разные, сначала приведи к общему знаменателю.
4. Если задача дана с именованными величинами, сначала переведи их в удобные одинаковые единицы.
5. Потом выполни действие по шагам.

Для геометрии:
1. Сначала назови правило или формулу.
2. Потом подставь числа.
3. Если нужно, сначала переведи величины в одинаковые единицы.
4. Дальше решай по действиям.

Школьные методики:
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
При движении навстречу называй скорость сближения.
При движении в противоположных направлениях называй скорость удаления.
Если это выражение, сначала назови порядок действий.
Если это уравнение, оставляй x отдельно и объясняй обратное действие.
Если это геометрия, сначала назови формулу, потом подставь числа.
Если запись непонятная или это не задача по математике, попроси записать задачу понятнее.
""".strip()


def extract_condition_and_question(raw_text: str) -> Tuple[str, str]:
    condition, question = _USER_FINAL_20260412G_PREV_EXTRACT_CONDITION_AND_QUESTION(raw_text)
    if condition or not raw_text:
        return condition, question

    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")
    pretty = normalize_word_problem_text(raw_text).strip().rstrip(".?!")

    direct_rect = re.search(
        r"прямоугольник\s+со\s+сторонами\s+(\d+\s*[а-яa-z/²]+)\s+и\s+(\d+\s*[а-яa-z/²]+)",
        lower,
    )
    if direct_rect:
        return f"Стороны прямоугольника {direct_rect.group(1)} и {direct_rect.group(2)}", question

    square_side = re.search(r"сторона\s+квадрата\s+(\d+\s*[а-яa-z/²]+)", lower)
    if square_side:
        return f"Сторона квадрата {square_side.group(1)}", question

    triangle_side = re.search(r"сторона\s+равностороннего\s+треугольника\s+(\d+\s*[а-яa-z/²]+)", lower)
    if triangle_side:
        return f"Сторона равностороннего треугольника {triangle_side.group(1)}", question

    if pretty and re.match(r"^(найти|найдите|узнай|узнайте)\b", lower):
        return "", pretty

    return condition, question


def _user_final_is_short_answer_value(text: str) -> bool:
    value = str(text or "").strip().rstrip(".")
    if not value:
        return False
    return bool(re.fullmatch(r"-?\d+(?:/\d+)?(?:\s+[A-Za-zА-Яа-яЁё./²%-]+){0,3}", value))


def _user_final_answer_phrase_from_question(answer: str, raw_text: str, kind: str) -> str:
    value = str(answer or "").strip().rstrip(".")
    if not value:
        return value
    if not _user_final_is_short_answer_value(value):
        return value

    question = _question_lower_text(raw_text).lower().replace("ё", "е")

    if question.startswith("во сколько раз"):
        return value if value.startswith("в ") else f"в {value}"

    if re.search(r"\bсколько[^.?!]*\bзабрали\b", question):
        return f"забрали {value}"
    if re.search(r"\bсколько[^.?!]*\bотдали\b", question):
        return f"отдали {value}"
    if re.search(r"\bсколько[^.?!]*\bсъели\b", question):
        return f"съели {value}"
    if re.search(r"\bсколько[^.?!]*\bпродали\b", question):
        return f"продали {value}"
    if re.search(r"\bсколько[^.?!]*\bдобавили\b", question):
        return f"добавили {value}"
    if re.search(r"\bсколько[^.?!]*\bзаболел[аои]?\b", question):
        return f"заболело {value}"
    if re.search(r"\bсколько[^.?!]*\bостал(?:ось|ись|ся)\b", question):
        return f"осталось {value}"
    if re.search(r"\bсколько[^.?!]*\bстал(?:о|и)\b", question):
        return f"стало {value}"
    if re.search(r"\bсколько[^.?!]*\bпотребуется\b", question) or re.search(r"\bсколько[^.?!]*\bпотребовалось\b", question):
        return f"потребуется {value}"
    if re.search(r"\bсколько[^.?!]*\bможно купить\b", question):
        return f"можно купить {value}"

    price_one = re.search(r"\bсколько\s+стоит\s+(?:1|один|одна|одно)\s+([а-яё-]+)", question)
    if price_one:
        return f"{price_one.group(1)} стоит {value}"

    price_many = re.search(r"\bсколько\s+стоят\s+(.+)$", question)
    if price_many:
        subject = price_many.group(1).strip(" ?")
        if subject:
            return f"{subject} стоят {value}"

    if re.search(r"\bс какой скоростью\b|\bкакова скорость\b|\bчему равна скорость\b", question):
        return f"скорость равна {value}"
    if re.search(r"\bкакое расстояние\b|\bкаково расстояние\b|\bчему равно расстояние\b", question):
        return f"расстояние равно {value}"
    if re.search(r"\bсколько времени\b|\bза какое время\b|\bсколько часов\b", question):
        return f"время равно {value}"
    if re.search(r"\bчему равна площадь\b|\bнайти площадь\b|\bузнайте площадь\b", question):
        return f"площадь равна {value}"
    if re.search(r"\bчему равен периметр\b|\bнайти периметр\b|\bузнайте периметр\b", question):
        return f"периметр равен {value}"

    shelf_match = re.search(r"\bсколько[^.?!]*\bна\s+(первой|второй|третьей)\s+полке\b", question)
    if shelf_match:
        return f"на {shelf_match.group(1)} полке было {value}"

    day_match = re.search(r"\bсколько[^.?!]*\bво\s+(первый|второй|третий)\s+день\b", question)
    if day_match:
        return f"в {day_match.group(1)} день {value}"

    if question.startswith("сколько денег"):
        return f"заплатили {value}"

    return value


def _detailed_format_word_like_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    statement = _detailed_statement_text(raw_text)
    info_lines: List[str] = []
    body_lines: List[str] = []

    for line in parts["body"]:
        lower = line.lower()
        if lower.startswith("что известно:") or lower.startswith("что нужно найти:"):
            info_lines.append(line)
        else:
            body_lines.append(line)

    if not info_lines:
        condition, question = extract_condition_and_question(raw_text)
        if condition:
            info_lines.append(f"Что известно: {condition}")
        if question:
            info_lines.append(f"Что нужно найти: {question}")

    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    answer = _user_final_answer_phrase_from_question(answer, raw_text, kind)

    lines: List[str] = []
    if statement:
        lines.append("Задача.")
        lines.append(statement)
    lines.append("Решение.")
    lines.extend(info_lines)
    lines.extend(_detailed_number_lines(body_lines))
    if parts["check"]:
        lines.append(parts["check"])
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind if kind in DEFAULT_ADVICE else "other")
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


def _detailed_format_generic_solution(raw_text: str, base_text: str, kind: str) -> str:
    parts = _detailed_split_sections(base_text)
    lines: List[str] = []
    statement = _detailed_statement_text(raw_text)
    if statement and kind in {"word", "geometry"}:
        lines.append("Задача.")
        lines.append(statement)
        lines.append("Решение.")
    else:
        lines.append("Решение.")
    lines.extend(_detailed_number_lines(parts["body"]))
    if parts["check"]:
        lines.append(parts["check"])
    answer = _detailed_maybe_enrich_answer(parts["answer"], raw_text, kind) or "проверь запись"
    answer = _user_final_answer_phrase_from_question(answer, raw_text, kind)
    lines.append(f"Ответ: {answer}")
    advice = parts["advice"] or default_advice(kind)
    lines.append(f"Совет: {advice}")
    return _detailed_finalize_text(lines)


async def build_explanation(user_text: str) -> dict:
    kind = infer_task_kind(user_text)
    local_explanation = build_explanation_local_first(user_text, kind)
    if local_explanation:
        formatted = _detailed_format_solution(user_text, local_explanation, kind)
        return {"result": formatted, "source": "local", "validated": True}

    if not DEEPSEEK_API_KEY:
        fallback = join_explanation_lines(
            "Не удалось подобрать готовый локальный шаблон для этой записи.",
            "Запишите пример или задачу полнее и без сокращений.",
            "Ответ: пока нужен более понятный ввод.",
            "Совет: пишите условие полностью, со всеми числами и вопросом",
        )
        return {"result": _detailed_format_solution(user_text, fallback, kind), "source": "fallback", "validated": False}

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 2600,
        "temperature": 0.03,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=45.0)
    if llm_result.get("error"):
        return llm_result
    formatted = _detailed_format_solution(user_text, llm_result["result"], kind)
    return {"result": formatted, "source": "llm", "validated": False}



# --- USER FINAL HOTFIX 2026-04-12H: geometry known-line extraction for "найти ..." formulations ---

_USER_FINAL_20260412H_PREV_EXTRACT_CONDITION_AND_QUESTION = extract_condition_and_question

def extract_condition_and_question(raw_text: str) -> Tuple[str, str]:
    condition, question = _USER_FINAL_20260412H_PREV_EXTRACT_CONDITION_AND_QUESTION(raw_text)
    if condition or not raw_text:
        return condition, question

    lower = normalize_word_problem_text(raw_text).lower().replace("ё", "е")

    direct_rect = re.search(
        r"прямоугольник[а]?\s+со\s+сторонами\s+(\d+\s*[а-яa-z/²]+)\s+и\s+(\d+\s*[а-яa-z/²]+)",
        lower,
    )
    if direct_rect:
        return f"Стороны прямоугольника {direct_rect.group(1)} и {direct_rect.group(2)}", question

    square_side = re.search(r"сторона\s+квадрата\s+(\d+\s*[а-яa-z/²]+)", lower)
    if square_side:
        return f"Сторона квадрата {square_side.group(1)}", question

    triangle_side = re.search(r"сторона\s+равностороннего\s+треугольника\s+(\d+\s*[а-яa-z/²]+)", lower)
    if triangle_side:
        return f"Сторона равностороннего треугольника {triangle_side.group(1)}", question

    return condition, question


# --- USER DELIVERY PATCH 2026-04-13: fuller final answers, architecture preserved ---

_PREV_USER_DELIVERY_ANSWER_PHRASE = _user_final_answer_phrase_from_question

def _user_final_answer_phrase_from_question(answer: str, raw_text: str, kind: str) -> str:
    original_value = str(answer or '').strip().rstrip('.')
    base = _PREV_USER_DELIVERY_ANSWER_PHRASE(answer, raw_text, kind)
    if not original_value:
        return base
    if not _user_final_is_short_answer_value(original_value):
        return base
    if str(base).strip().rstrip('.') != original_value:
        return base

    question = _question_lower_text(raw_text).lower().replace('ё', 'е').strip(' ?.')

    if question.startswith('сколько'):
        if ' было ' in f' {question} ' or question.endswith(' было'):
            if re.search(r'\b(кг|г|л|м|см|дм|мм|км|руб|листов|книг|клеток|деревьев|фруктов|деталей)\b', question) or 'всего' in question:
                return f'всего было {original_value}'
            return f'было {original_value}'
        if ' осталось ' in f' {question} ' or question.endswith(' осталось'):
            return f'осталось {original_value}'
        if ' стало ' in f' {question} ' or question.endswith(' стало'):
            return f'стало {original_value}'
        if re.search(r'\bсколько[^?]*\bклеток\b', question):
            return f'было {original_value}'
        if re.search(r'\bсколько[^?]*\bкоробок\b', question):
            return f'получилось {original_value}'
        if re.search(r'\bсколько[^?]*\bмешков\b', question):
            return f'было {original_value}'
        if re.search(r'\bсколько[^?]*\bкниг\b', question) and ('на полках' in question or 'на двух полках' in question or 'на трех полках' in question or 'на трёх полках' in question):
            return f'всего было {original_value}'
        if re.search(r'\bсколько[^?]*\bфруктов\b', question) and ('в ларьке' in question or 'в магазине' in question or 'было' in question):
            return f'всего было {original_value}'

    return base
