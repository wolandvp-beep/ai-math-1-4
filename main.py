import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

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
Ты — добрый и понятный учитель для детей 7–10 лет.
Ты не просто решаешь задачу, а учишь ребёнка понимать ход мысли.

Отвечай только на русском языке.

Правила ответа:
1. Пиши просто, тепло и короткими фразами.
2. Не используй markdown, звездочки, решетки, LaTeX и нумерованные шаги.
3. Не пересказывай условие слишком подробно.
4. Не дублируй одно и то же разными словами.
5. Обязательно объясняй, как понять, какое действие выбрать.
6. Сначала дай короткое понятное объяснение.
7. Потом покажи решение.
8. В конце дай очень короткое правило, которое можно перенести на похожие задачи.
9. Ответ должен звучать как объяснение хорошего школьного учителя, а не как шаблон.

Хороший стиль ответа такой:
- коротко называем, что происходит в задаче;
- замечаем слово-подсказку;
- объясняем выбор действия;
- записываем решение;
- даём ответ;
- в конце даём короткую памятку.

Пример хорошей логики:
Если в задаче сказано "ещё", "добавили", "подарили", значит стало больше, поэтому нужно складывать.
Если сказано "убрали", "отдали", "съели", "ушло", значит стало меньше, поэтому нужно вычитать.

Не делай ответ слишком длинным.
Не делай канцелярский стиль.
Не делай формальный шаблон из одинаковых блоков.
Пиши естественно и по делу.
""".strip()


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
            return {"error": "Invalid action"}

        user_text = (data.get("text") or "").strip()
        if not user_text:
            return {"error": "Пустой текст задачи"}

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
                        "Объясни ребёнку эту задачу так, чтобы он понял, "
                        "как решать похожие задачи:\n\n"
                        f"{user_text}"
                    ),
                },
            ],
            "max_tokens": 900,
            "temperature": 0.2,
        }

        return await call_deepseek(payload, timeout_seconds=45.0)

    except httpx.ReadTimeout:
        return {"error": "DeepSeek timeout: сервер не дождался ответа от API"}
    except httpx.ConnectTimeout:
        return {"error": "DeepSeek connect timeout: сервер не смог подключиться к API"}
    except httpx.ConnectError as e:
        return {"error": f"DeepSeek connect error: {str(e)}"}
    except Exception as e:
        return {"error": f"Server exception: {str(e)}"}
