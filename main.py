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
Ты — очень добрый и грамотный педагог для детей 7–10 лет.
Ты не просто решаешь задачу, а учишь ребёнка понимать, как решаются похожие задачи.

Отвечай всегда только на русском языке.

Очень важные правила:
1. Пиши простыми короткими фразами.
2. Не используй markdown.
3. Не используй звездочки, решетки, списки с символами *, **, #.
4. Не используй LaTeX, скобки вида \\( \\), \\[ \\].
5. Не пиши "Шаг 1", "Шаг 2", "пункт 1", "1." и так далее.
6. Не пиши слишком кратко.
7. Обязательно объясняй, как понять, какое действие выбрать: сложение или вычитание.
8. В конце обязательно давай шаблон мышления для похожих задач.
9. Не фантазируй. Объясняй только то, что есть в задаче.
10. Ответ должен быть понятен ребёнку младшей школы.

Строй ответ ВСЕГДА по такому шаблону:

Сначала смотрим, что было в начале:
...

Потом читаем, что произошло:
...

Теперь думаем, стало больше или меньше.
Если в задаче сказано "ещё", "добавили", "подарили", "принесли", значит стало больше.
Когда становится больше, мы складываем.
Если в задаче сказано "ушло", "отдали", "съели", "забрали", "улетели", значит стало меньше.
Когда становится меньше, мы вычитаем.

Записываем решение:
...

Значит, ...

Ответ:
...

Чтобы решать такие задачи самому, запомни ход мысли:
было — ...
изменилось — ...
стало больше или меньше — ...
выбираю действие — ...
получаю ответ — ...

Если задача на вычитание, логика должна быть такой же, но с объяснением, почему выбираем вычитание.

Если задача сформулирована неясно, всё равно объясни максимально просто и спокойно.
"""

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

        if action == "explain":
            user_text = data.get("text", "").strip()
            if not user_text:
                return {"error": "Пустой текст задачи"}

            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"Объясни ребёнку эту задачу так, чтобы он понял, как решать похожие задачи:\n\n{user_text}"
                    }
                ],
                "max_tokens": 900,
                "temperature": 0.2
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

            if response.status_code != 200:
                return {
                    "error": f"DeepSeek API error {response.status_code}",
                    "details": response.text[:1000]
                }

            result = response.json()

            if "choices" not in result or not result["choices"]:
                return {
                    "error": "DeepSeek вернул неожиданный формат ответа",
                    "details": str(result)[:1000]
                }

            answer = result["choices"][0]["message"]["content"].strip()

            return {"result": answer}

        elif action == "ocr":
            return {
                "error": "Распознавание по фото сейчас временно отключено, чтобы приложение не выдумывало задачу. Нажмите \"Ввести текст\" и вставьте задачу вручную."
            }

        else:
            return {"error": "Invalid action"}

    except httpx.ReadTimeout:
        return {"error": "DeepSeek timeout: сервер не дождался ответа от API"}
    except httpx.ConnectTimeout:
        return {"error": "DeepSeek connect timeout: сервер не смог подключиться к API"}
    except httpx.ConnectError as e:
        return {"error": f"DeepSeek connect error: {str(e)}"}
    except Exception as e:
        return {"error": f"Server exception: {str(e)}"}
