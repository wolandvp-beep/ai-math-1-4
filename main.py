import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEEPSEEK_API_KEY = os.environ.get("myapp_ai_math_1_4_API_key")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("Переменная окружения myapp_ai_math_1_4_API_key не установлена")

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def build_payload(action: str, data: dict) -> dict:
    if action == "ocr":
        image = data.get("image")
        if not image:
            raise ValueError("Не передано изображение для распознавания.")

        return {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты аккуратно распознаёшь текст с изображения школьной задачи. "
                        "Верни только сам текст задачи на русском языке, без пояснений, без markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Распознай текст задачи с картинки максимально точно."},
                        {"type": "image_url", "image_url": {"url": image}},
                    ],
                },
            ],
            "max_tokens": 500,
            "temperature": 0.1,
        }

    if action == "explain":
        text = (data.get("text") or "").strip()
        if not text:
            raise ValueError("Не передан текст задачи.")

        return {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — добрый учитель начальных классов. "
                        "Объясни решение задачи для ребёнка 7–10 лет пошагово. "
                        "Пиши короткими понятными фразами. "
                        "Желательно используй формат:\n"
                        "Шаг 1: ...\n"
                        "Шаг 2: ...\n"
                        "Ответ: ..."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "max_tokens": 1000,
            "temperature": 0.5,
        }

    raise ValueError("Invalid action")


@app.options("/")
async def options():
    return {"message": "OK"}


@app.get("/")
def read_root():
    return {"message": "Proxy is running. Use POST request with 'action' and payload."}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/")
async def proxy(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Тело запроса должно быть JSON."})

    action = data.get("action")
    if not action:
        return JSONResponse(status_code=400, content={"error": "Не передан параметр action."})

    try:
        payload = build_payload(action, data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    timeout = httpx.Timeout(180.0, connect=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        response.raise_for_status()
        result = response.json()

    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        return JSONResponse(
            status_code=502,
            content={"error": f"DeepSeek вернул ошибку {exc.response.status_code}: {detail}"},
        )
    except httpx.RequestError as exc:
        return JSONResponse(
            status_code=504,
            content={"error": f"Не удалось связаться с DeepSeek: {str(exc)}"},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка прокси: {str(exc)}"},
        )

    try:
        answer = result["choices"][0]["message"]["content"]
    except Exception:
        return JSONResponse(
            status_code=502,
            content={"error": f"Неожиданный ответ от DeepSeek: {result}"},
        )

    return {"result": answer}
