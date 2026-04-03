import os
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

APP_TITLE = "Reshayka AI Proxy"
API_KEY_ENV = "myapp_ai_math_1_4_API_key"
DEFAULT_ALLOWED_ORIGINS = [
    "https://wolandvp-beep.github.io",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

SYSTEM_PROMPT = """
Ты — очень сильный школьный учитель математики для детей 7–10 лет.

Отвечай только на русском языке.
Объясняй спокойно, коротко, по-школьному и без лишних вступлений.
Всегда используй слово «Совет».
Никогда не используй слова «Запомни» и «Памятка».
Не используй markdown, списки со звёздочками, LaTeX и длинные шаблоны.

Сначала определи тип задания, потом объясняй именно этим способом:
- текстовая задача;
- обычный пример на вычисление;
- выражение со скобками;
- уравнение;
- дроби;
- геометрия;
- задача на несколько действий;
- сравнение чисел.

Для уравнений:
- оставь неизвестное отдельно;
- объясни перенос через знак равно;
- обязательно скажи, что действие меняется;
- покажи новое уравнение;
- реши его;
- сделай короткую проверку.

Для текстовых задач:
- коротко скажи, что известно;
- объясни, стало больше, меньше или нужно узнать часть, сумму, остаток;
- объясни выбор действия по смыслу.

Для примеров на вычисление:
- объясняй по делу;
- если удобно, покажи вычисление по частям.

Очень важное дополнительное правило:
если это сложение, вычитание, умножение или деление, и хотя бы одно число двузначное или многозначное,
обязательно добавь отдельный короткий блок «Решение в строку:».
Само решение в столбик не расписывай текстом и не озвучивай. Его приложение покажет отдельно на экране.

Формат ответа:
- короткое объяснение метода;
- решение простыми фразами;
- если подходит правило про многозначные числа, добавь блок «Решение в строку:»;
- ответ;
- короткий совет.
""".strip()


def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if raw.strip():
        return [item.strip() for item in raw.split(",") if item.strip()]
    return DEFAULT_ALLOWED_ORIGINS


app = FastAPI(title=APP_TITLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


async def call_deepseek(payload: dict[str, Any], timeout_seconds: float = 45.0) -> dict[str, Any]:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        return {"error": f"Переменная окружения {API_KEY_ENV} не установлена"}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
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

    choices = result.get("choices") or []
    if not choices:
        return {
            "error": "DeepSeek вернул неожиданный формат ответа",
            "details": str(result)[:1500],
        }

    message = choices[0].get("message", {})
    answer = (message.get("content") or "").strip()
    if not answer:
        return {
            "error": "DeepSeek вернул пустой ответ",
            "details": str(result)[:1500],
        }

    return {"result": answer}


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Proxy is running. Use POST / with action=explain."}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.options("/")
async def options() -> dict[str, str]:
    return {"message": "OK"}


@app.post("/")
async def proxy(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        action = data.get("action")
        if action != "explain":
            return JSONResponse({"error": "Invalid action"}, status_code=400)

        user_text = str(data.get("text") or "").strip()
        if not user_text:
            return JSONResponse({"error": "Пустой текст задачи"}, status_code=400)

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Сначала определи тип задания. "
                        "Потом объясни решение простыми школьными фразами. "
                        "Для уравнений обязательно объясни перенос через знак равно, смену действия и проверку. "
                        "Для текстовых задач объясняй выбор действия по смыслу. "
                        "Если это вычислительный пример с двузначным или многозначным числом, обязательно добавь блок 'Решение в строку:'.\n\n"
                        f"{user_text}"
                    ),
                },
            ],
            "max_tokens": 1000,
            "temperature": 0.1,
        }

        result = await call_deepseek(payload, timeout_seconds=45.0)
        status_code = 200 if "result" in result else 502
        return JSONResponse(result, status_code=status_code)

    except httpx.ReadTimeout:
        return JSONResponse({"error": "DeepSeek timeout: сервер не дождался ответа от API"}, status_code=504)
    except httpx.ConnectTimeout:
        return JSONResponse({"error": "DeepSeek connect timeout: сервер не смог подключиться к API"}, status_code=504)
    except httpx.ConnectError as exc:
        return JSONResponse({"error": f"DeepSeek connect error: {exc}"}, status_code=502)
    except Exception as exc:
        return JSONResponse({"error": f"Server exception: {exc}"}, status_code=500)
