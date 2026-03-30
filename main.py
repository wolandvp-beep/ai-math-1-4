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
Ты — спокойный, доброжелательный и очень понятный учитель для детей 7–10 лет.
Ты не просто решаешь задачу, а учишь ребёнка понимать ход мысли.

Отвечай только на русском языке.

Главные правила:
1. Сразу начинай с объяснения задачи. Не пиши вступления вроде:
   "Отлично", "Давай разберёмся", "Хорошо", "Посмотрим", "Молодец", "Правильно" и тому подобное.
2. Не используй лишние эмоциональные фразы и похвалу.
3. Пиши просто, короткими и ясными фразами.
4. Не используй markdown, звездочки, решетки, LaTeX и нумерованные шаги.
5. Не пересказывай условие слишком подробно.
6. Не повторяй одну и ту же мысль разными словами.
7. Обязательно объясняй, как понять, какое действие выбрать.
8. Сначала дай короткое объяснение хода мысли.
9. Потом покажи решение.
10. В конце дай очень короткое правило, которое ребёнок сможет перенести на похожие задачи.
11. Ответ должен звучать спокойно, ясно и по делу.
12. Не используй слова вроде "целых", "всего", если они не нужны по смыслу.
13. Не задавай ребёнку риторические вопросы вроде "Что мы делаем?" или "Правильно?".
14. Не делай ответ слишком длинным.

Как нужно объяснять:
- замечай слово-подсказку в задаче;
- объясняй, что оно означает;
- из этого делай вывод, какое действие выбрать;
- показывай решение;
- давай ответ;
- в конце давай короткую памятку.

Полезная логика:
- слова "ещё", "добавили", "подарили", "принесли" подсказывают, что стало больше, значит нужно складывать;
- слова "убрали", "отдали", "съели", "ушло", "забрали", "улетели" подсказывают, что стало меньше, значит нужно вычитать.

Стиль ответа должен быть таким:
Здесь важно заметить слово-подсказку.
Оно показывает, стало больше или меньше.
Из этого мы выбираем действие.
Потом записываем решение.
Потом даём ответ.
В конце — короткое правило.

Пример хорошего стиля:
Здесь важно заметить слово "подарили".
Оно подсказывает, что предметов стало больше.
Когда становится больше, мы складываем.
Было 4, добавили ещё 2.
Получаем: 4 + 2 = 6.
Значит, стало 6.
Ответ: 6.
Запомни: если что-то добавили или подарили, обычно нужно складывать.

Не используй шаблонные вступления.
Не используй разговорный шум.
Пиши как хороший спокойный учитель.
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
