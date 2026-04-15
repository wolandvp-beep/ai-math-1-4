import json
import os
import re
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI()

# Для фронтенда этого приложения cookies не используются, поэтому открытый CORS
# упрощает локальное тестирование и публикацию статического клиента.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


DEEPSEEK_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY")
    or os.environ.get("myapp_ai_math_1_4_API_key")
    or ""
).strip()
DEEPSEEK_BASE_URL = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = (os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat").strip()


SYSTEM_PROMPT = """
Ты — сильный учитель начальных классов по математике для детей 7–10 лет.
Твоя задача — объяснять решение очень понятно, спокойно, по-школьному и по шагам.

Работай только на русском языке.
Работай только с математикой начальной школы: примеры, выражения, порядок действий, деление столбиком, дроби, уравнения с одной переменной, текстовые задачи, геометрия, величины, цена-количество-стоимость, движение.
Если запрос не относится к математике или запись непонятная, вежливо попроси переписать задачу понятнее. На другие темы не переключайся.

Главная цель:
не просто дать ответ, а объяснить так, чтобы ребёнок понял ход решения.

Стиль ответа:
— детальная запись решения и полного ответа ученика отличника в школьной тетради.
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
    "Не вижу понятной математической задачи.\n"
    "Напишите пример, уравнение или условие задачи подробнее.\n"
    "Совет: пишите числа, знаки действий и вопрос полностью."
)

DEFAULT_ADVICE = {
    "expression": "сначала определяй порядок действий и не пропускай промежуточные вычисления",
    "equation": "оставляй неизвестное одно и всегда делай проверку",
    "fraction": "сначала смотри на знаменатели, потом выполняй действие",
    "geometry": "сначала называй правило, потом подставляй числа",
    "word": "сначала пойми, что известно и что нужно найти",
    "other": "решай по шагам и записывай каждое действие отдельно",
}


def normalize_user_input(text: Any) -> str:
    cleaned = str(text or "").replace("\r", "")
    cleaned = re.sub(r"[\t ]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()[:4000]


def normalize_section_label(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return ""
    return SECTION_PREFIX_RE.sub(lambda m: f"{m.group(1).capitalize()}: ", text)


def infer_task_kind(text: str) -> str:
    cleaned = normalize_user_input(text).lower()
    if not cleaned:
        return "other"
    if re.search(r"=", cleaned) and re.search(r"[a-zа-я]", cleaned):
        return "equation"
    if re.search(r"\d+\s*/\s*\d+\s*[+\-]\s*\d+\s*/\s*\d+", cleaned) or "дроб" in cleaned:
        return "fraction"
    if re.search(r"периметр|площад|прямоугольник|квадрат|треугольник|см\b|дм\b|м\b|км\b", cleaned):
        return "geometry"
    if "?" in cleaned or re.search(r"сколько|найди|найти|было|осталось|стоит|цена|скорость|время|расстояние", cleaned):
        return "word"
    if re.search(r"\d", cleaned) and re.search(r"[+\-×÷*/:=()]", cleaned):
        return "expression"
    return "other"


def default_advice(kind: str) -> str:
    return DEFAULT_ADVICE.get(kind, DEFAULT_ADVICE["other"])


def looks_like_math_input(text: str) -> bool:
    cleaned = normalize_user_input(text)
    if not cleaned:
        return False
    return bool(
        re.search(r"\d|[+\-×÷*/:=()]|\b(задача|пример|уравнение|дроб|периметр|площад|скорость|цена|стоимость)\b", cleaned, re.IGNORECASE)
        or cleaned
    )


def sanitize_model_text(text: str, kind: str = "other") -> str:
    cleaned = str(text or "").replace("\r", "")
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    cleaned = cleaned.replace("\\", "")
    cleaned = re.sub(r"^\s*(\d+)\.\s+", r"\1) ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*Шаг\s*(\d+)\s*:?\s*", r"\1) ", cleaned, flags=re.MULTILINE | re.IGNORECASE)
    cleaned = re.sub(r"\s*(Ответ\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(Совет\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(Проверка\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    while True:
        updated = LEADING_FILLER_SENTENCE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated

    lines = []
    seen = set()
    for raw in cleaned.split("\n"):
        line = normalize_section_label(raw)
        if not line:
            continue
        if BANNED_OPENERS.match(line):
            continue
        dedupe_key = line.lower().rstrip(".!?")
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        lines.append(line)

    body_lines = []
    answer_line = ""
    advice_line = ""
    check_line = ""

    for line in lines:
        if re.match(r"^Ответ:", line, flags=re.IGNORECASE):
            value = re.sub(r"^Ответ:\s*", "", line, flags=re.IGNORECASE).strip()
            if value:
                answer_line = f"Ответ: {value}"
            continue
        if re.match(r"^Совет:", line, flags=re.IGNORECASE):
            value = re.sub(r"^Совет:\s*", "", line, flags=re.IGNORECASE).strip()
            if value:
                advice_line = f"Совет: {value}"
            continue
        if re.match(r"^Проверка:", line, flags=re.IGNORECASE):
            value = re.sub(r"^Проверка:\s*", "", line, flags=re.IGNORECASE).strip()
            if value and not check_line:
                check_line = f"Проверка: {value}"
            continue
        body_lines.append(line)

    if not answer_line and body_lines:
        last_line = body_lines[-1]
        match = re.search(r"=\s*([^=]+?)[.!?]?$", last_line)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                answer_line = f"Ответ: {candidate}"

    if not advice_line:
        advice_line = f"Совет: {default_advice(kind)}"

    parts = [*body_lines]
    if check_line:
        parts.append(check_line)
    if answer_line:
        parts.append(answer_line)
    parts.append(advice_line)
    return "\n".join(part for part in parts if part).strip()


def shape_explanation(text: str, kind: str) -> str:
    return sanitize_model_text(text, kind=kind)


async def call_deepseek(payload: Dict[str, Any], timeout_seconds: float = 60.0) -> Dict[str, Any]:
    if not DEEPSEEK_API_KEY:
        return {"error": "Не найден ключ DeepSeek API. Добавьте переменную окружения DEEPSEEK_API_KEY или myapp_ai_math_1_4_API_key."}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        details = response.text[:2000]
        try:
            payload_json = response.json()
            if isinstance(payload_json, dict):
                details = json.dumps(payload_json, ensure_ascii=False)[:2000]
        except Exception:
            pass
        return {"error": f"DeepSeek API error {response.status_code}", "details": details}

    try:
        result = response.json()
    except Exception:
        return {"error": "DeepSeek вернул не JSON", "details": response.text[:2000]}

    choices = result.get("choices") or []
    if not choices:
        return {"error": "DeepSeek вернул неожиданный формат ответа", "details": str(result)[:2000]}

    message = choices[0].get("message") or {}
    answer = str(message.get("content") or "").strip()
    if not answer:
        return {"error": "DeepSeek вернул пустой ответ", "details": str(result)[:2000]}

    return {"result": answer}


async def build_explanation(user_text: str) -> Dict[str, Any]:
    normalized = normalize_user_input(user_text)
    if not normalized:
        return {"result": NON_MATH_REPLY, "source": "guard", "validated": True}

    kind = infer_task_kind(normalized)
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": normalized},
        ],
        "temperature": 0.15,
        "max_tokens": 2200,
        "stream": False,
    }
    llm_result = await call_deepseek(payload, timeout_seconds=60.0)
    if llm_result.get("error"):
        return llm_result

    shaped = shape_explanation(llm_result["result"], kind)
    return {
        "result": shaped,
        "source": "llm",
        "validated": False,
        "kind": kind,
    }


async def extract_user_text(request: Request) -> str:
    raw_body = await request.body()
    if not raw_body:
        return ""

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return normalize_user_input(raw_body.decode("utf-8", errors="ignore"))

    if isinstance(payload, str):
        return normalize_user_input(payload)

    if isinstance(payload, dict):
        direct_text = payload.get("text") or payload.get("query") or payload.get("message") or ""
        if isinstance(direct_text, str) and direct_text.strip():
            return normalize_user_input(direct_text)

        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            nested_text = nested_data.get("text") or nested_data.get("query") or ""
            if isinstance(nested_text, str) and nested_text.strip():
                return normalize_user_input(nested_text)

    return ""


@app.options("/")
async def options() -> Dict[str, str]:
    return {"message": "OK"}


@app.get("/")
def read_root() -> Dict[str, str]:
    return {"message": "Math explanation proxy is running. Use POST with JSON {\"action\": \"explain\", \"text\": \"...\"}."}


@app.post("/")
async def proxy(request: Request):
    try:
        user_text = await extract_user_text(request)
        result = await build_explanation(user_text)
        if result.get("error"):
            return JSONResponse(status_code=502, content=result)
        return result
    except httpx.ReadTimeout:
        return JSONResponse(status_code=504, content={"error": "DeepSeek timeout: сервер не дождался ответа от API"})
    except httpx.ConnectTimeout:
        return JSONResponse(status_code=504, content={"error": "DeepSeek connect timeout: сервер не смог подключиться к API"})
    except httpx.ConnectError as exc:
        return JSONResponse(status_code=502, content={"error": f"DeepSeek connect error: {str(exc)}"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(exc)}"})
