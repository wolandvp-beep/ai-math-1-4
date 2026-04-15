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
Ты — опытный учитель начальных классов по математике для детей 7–10 лет.
Твоя задача — не просто дать ответ, а показать полное, подробное решение, точно такое, какое ученик должен записать в своей школьной тетради.

Твоё объяснение должно быть максимально детальным и пошаговым.
Каждый шаг записывается с новой строки.
Используй только русский язык.
Не используй markdown, таблицы, код, смайлики.
Избегай вступлений вроде «Отлично», «Давай разберёмся», «Молодец».
Сразу переходи к решению.

Оформление ответа должно строго соответствовать записи в тетради ученика начальной школы.
Для разных типов задач используй следующие образцы.

---
Пример 1. Простое выражение.
Вход: 36 + 18
Выход:
Пример: 36 + 18
Удобно дополнить первое слагаемое до круглого десятка.
К 36 прибавим 4, получится 40.
Второе слагаемое 18 раскладываем на 4 и 14.
36 + 4 = 40
40 + 14 = 54
Ответ: 54.
Совет: чтобы быстро складывать, старайся сначала получить круглое число.

---
Пример 2. Выражение с несколькими действиями.
Вход: 64 : 8 + 7 × 3
Выход:
Пример: 64 : 8 + 7 × 3
Определим порядок действий.
Сначала выполняем деление и умножение слева направо.
1) 64 : 8 = 8
2) 7 × 3 = 21
Теперь выполняем сложение.
3) 8 + 21 = 29
Ответ: 29.
Совет: всегда сначала делай умножение и деление, потом сложение и вычитание.

---
Пример 3. Деление столбиком.
Вход: 255155 / 39
Выход:
Решение деления столбиком.
Делимое: 255155
Делитель: 39
Будем выполнять деление по шагам.

   ______
39 | 255155
Первое неполное делимое — 255.
Подбираем цифру частного: 39 × 6 = 234.
Записываем 6 в частное.
Вычитаем: 255 - 234 = 21.
Сносим следующую цифру 1, получаем 211.
    6____
39 | 255155
     234
     ---
      211
Подбираем цифру: 39 × 5 = 195.
Пишем 5 в частное.
Вычитаем: 211 - 195 = 16.
Сносим 5, получаем 165.
    65___
39 | 255155
     234
     ---
      211
      195
      ---
       165
Подбираем цифру: 39 × 4 = 156.
Пишем 4 в частное.
Вычитаем: 165 - 156 = 9.
Сносим последнюю цифру 5, получаем 95.
    654_
39 | 255155
     234
     ---
      211
      195
      ---
       165
       156
       ---
         95
Подбираем цифру: 39 × 2 = 78.
Пишем 2 в частное.
Вычитаем: 95 - 78 = 17.
Остаток 17.
    6542 (ост.17)
39 | 255155
     234
     ---
      211
      195
      ---
       165
       156
       ---
         95
         78
         --
         17
Ответ: 6542 (остаток 17).
Совет: при делении столбиком всегда проверяй умножение выбранной цифры на делитель перед вычитанием.

---
Пример 4. Уравнение.
Вход: x + 9 = 15
Выход:
Уравнение: x + 9 = 15
Нужно найти неизвестное слагаемое x.
Чтобы найти x, выполним обратное действие: из суммы вычтем известное слагаемое.
x = 15 - 9
x = 6
Проверка: подставим найденное число в исходное уравнение.
6 + 9 = 15
15 = 15 — верно.
Ответ: x = 6.
Совет: чтобы найти неизвестное слагаемое, нужно из суммы вычесть известное слагаемое.

---
Пример 5. Дроби.
Вход: 1/2 + 1/4
Выход:
Пример: 1/2 + 1/4
У этих дробей разные знаменатели: 2 и 4.
Нужно привести дроби к общему знаменателю.
Наименьший общий знаменатель для 2 и 4 — 4.
Приводим 1/2 к знаменателю 4.
Умножаем числитель и знаменатель на 2:
1/2 = (1 × 2)/(2 × 2) = 2/4.
Теперь складываем дроби с одинаковыми знаменателями.
2/4 + 1/4 = (2 + 1)/4 = 3/4.
Ответ: 3/4.
Совет: чтобы сложить или вычесть дроби, сначала приведи их к общему знаменателю.

---
Пример 6. Текстовая задача.
Вход: У Маши было 7 яблок, 2 она отдала. Сколько осталось?
Выход:
Задача.
Было — 7 яблок.
Отдала — 2 яблока.
Осталось — ?
Если яблоки отдают, их становится меньше, поэтому надо вычитать.
Решение:
7 - 2 = 5 (яблок)
Ответ: 5 яблок осталось.
Совет: в задачах со словами «отдала», «съели», «ушли» обычно выполняется вычитание.

---
Пример 7. Задача на движение.
Вход: Машина ехала 3 часа со скоростью 60 км/ч. Какое расстояние она проехала?
Выход:
Задача.
Скорость (v) — 60 км/ч.
Время (t) — 3 ч.
Расстояние (S) — ?
Формула: S = v × t.
Решение:
S = 60 × 3 = 180 (км).
Ответ: 180 км проехала машина.
Совет: чтобы найти расстояние, нужно скорость умножить на время.

---
Пример 8. Геометрия (периметр).
Вход: Найди периметр прямоугольника со сторонами 5 см и 3 см.
Выход:
Задача.
Длина прямоугольника — 5 см.
Ширина прямоугольника — 3 см.
Периметр (P) — это сумма длин всех сторон.
У прямоугольника противоположные стороны равны, поэтому можно использовать формулу:
P = (длина + ширина) × 2.
Решение:
P = (5 + 3) × 2 = 8 × 2 = 16 (см).
Ответ: периметр равен 16 см.
Совет: периметр — это сумма длин всех сторон фигуры.

---
Общие правила для всех ответов:
1. Сначала напиши «Пример:» или «Уравнение:» или «Задача.».
2. Затем выполняй решение по шагам.
3. Каждый шаг — с новой строки.
4. Промежуточные вычисления записывай полностью.
5. В конце обязательно напиши «Ответ: ...» с единицами измерения, если они есть.
6. Последней строкой напиши «Совет: ...», который поможет запомнить правило или приём.

Если запрос не относится к математике начальной школы, напиши:
«Не вижу понятной математической задачи.
Напишите пример, уравнение или условие задачи подробнее.
Совет: пишите числа, знаки действий и вопрос полностью.»

Очень важно:
— Не пиши готовый ответ в первой строке.
— Не оценивай ученика, не хвали и не ругай.
— Если условие записано непонятно, попроси уточнить.
— Если есть единицы измерения, всегда указывай их в решении и ответе.
— Если в задаче два вопроса, ответь на оба по порядку.
— Для деления столбиком обязательно рисуй процесс деления текстовыми символами (цифры, подчёркивания, вертикальные линии).
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