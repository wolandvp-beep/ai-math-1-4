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
Короткие предложения лучше длинных.

Формат ответа всегда такой:
сначала 2–5 коротких строк объяснения;
потом строка "Ответ: ...";
последняя строка "Совет: ...".

Правила по типам задач:
Если это текстовая задача, коротко скажи, что известно, что нужно найти и почему выбирается это действие.
Если это обычный пример, объясни способ кратко и по делу. Не дублируй подробные внутренние шаги столбика.
Если это выражение со скобками, сначала считай в скобках, потом остальное.
Если это уравнение, оставь x отдельно, обязательно объясни смену действия и сделай короткую проверку.
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



def infer_task_kind(text: str) -> str:
    base = strip_known_prefix(text)
    lowered = normalize_cyrillic_x(base).lower()

    if re.search(r"\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+", lowered):
        return "fraction"
    if "x" in lowered and "=" in lowered:
        return "equation"
    if re.search(r"периметр|площадь|прямоугольник|квадрат|сторон", lowered):
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

    max_body_lines = 4 if check_line else 5
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
            f"{operator_word.capitalize()} числители: {a} {action_symbol} {c} = {top_result}",
            f"Получаем: {top_result}/{b}",
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
        f"Сначала приводим дроби к общему знаменателю {common}",
        f"{a}/{b} = {a_scaled}/{common}",
        f"{c}/{d} = {c_scaled}/{common}",
        f"Теперь {operator_word}: {a_scaled}/{common} {action_symbol} {c_scaled}/{common} = {top_result}/{common}",
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
                "Нужно оставить x отдельно",
                f"Число {format_fraction(number)} переносим вправо",
                "При переносе через знак равно плюс меняется на минус",
                f"Получаем: x = {format_fraction(rhs_value)} - {format_fraction(number)}",
                f"x = {format_fraction(answer)}",
                format_equation_check(f"x + {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: в уравнении оставляй x отдельно, а число переноси со сменой действия",
            )

        if kind == "x_minus":
            answer = rhs_value + number
            return join_explanation_lines(
                "Нужно оставить x отдельно",
                f"Число {format_fraction(number)} переносим вправо",
                "При переносе через знак равно минус меняется на плюс",
                f"Получаем: x = {format_fraction(rhs_value)} + {format_fraction(number)}",
                f"x = {format_fraction(answer)}",
                format_equation_check(f"x - {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если число ушло через знак равно, действие меняется на обратное",
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
                "Нужно оставить x отдельно",
                f"Число {format_fraction(number)} переносим вправо",
                "При переносе через знак равно умножение меняется на деление",
                f"Получаем: x = {format_fraction(rhs_value)} : {format_fraction(number)}",
                f"x = {format_fraction(answer)}",
                format_equation_check(f"x × {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: при переносе множителя вправо выполняем деление",
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
                "Нужно оставить x отдельно",
                f"Число {format_fraction(number)} переносим вправо",
                "При переносе через знак равно деление меняется на умножение",
                f"Получаем: x = {format_fraction(rhs_value)} × {format_fraction(number)}",
                f"x = {format_fraction(answer)}",
                format_equation_check(f"x : {format_fraction(number)}", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: если x делят на число, справа нужно умножить",
            )

        if kind == "plus_x":
            answer = rhs_value - number
            return join_explanation_lines(
                "Нужно оставить x отдельно",
                f"Число {format_fraction(number)} переносим вправо",
                "При переносе через знак равно плюс меняется на минус",
                f"Получаем: x = {format_fraction(rhs_value)} - {format_fraction(number)}",
                f"x = {format_fraction(answer)}",
                format_equation_check(f"{format_fraction(number)} + x", format_fraction(answer), format_fraction(rhs_value)),
                f"Ответ: {format_fraction(answer)}",
                "Совет: сначала оставь x одно, а потом сделай проверку",
            )

        if kind == "minus_x":
            answer = number - rhs_value
            return join_explanation_lines(
                "Неизвестное стоит после минуса",
                f"Нужно узнать, сколько вычли из {format_fraction(number)}, чтобы получить {format_fraction(rhs_value)}",
                f"Получаем: x = {format_fraction(number)} - {format_fraction(rhs_value)}",
                f"x = {format_fraction(answer)}",
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
                "Нужно оставить x отдельно",
                f"Число {format_fraction(number)} переносим вправо",
                "При переносе через знак равно умножение меняется на деление",
                f"Получаем: x = {format_fraction(rhs_value)} : {format_fraction(number)}",
                f"x = {format_fraction(answer)}",
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
                "Неизвестное стоит в делителе",
                f"Нужно понять, на какое число делили {format_fraction(number)}, чтобы получить {format_fraction(rhs_value)}",
                f"Получаем: x = {format_fraction(number)} : {format_fraction(rhs_value)}",
                f"x = {format_fraction(answer)}",
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
    )

    if local_explanation:
        kind = infer_task_kind(user_text)
        return {
            "result": shape_explanation(local_explanation, kind),
            "source": "local",
            "validated": True,
        }

    kind = infer_task_kind(user_text)
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
                    f"{user_text}"
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
