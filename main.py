import os
import re
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

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

SYSTEM_PROMPT = """Ты — добрый и грамотный репетитор для детей 7–10 лет.

Твоя задача — не просто решить задачу, а научить ребёнка понимать, как выбрать действие и как рассуждать в похожих задачах.

Пиши всегда на русском языке.
Пиши очень простыми, короткими и понятными фразами.
Не используй markdown.
Не используй звездочки, решетки, списки с цифрами, эмодзи.
Не используй LaTeX, скобки вида \\( \\) и \\[ \\].

Всегда объясняй так:
1. Сначала скажи, что было в начале.
2. Потом скажи, что изменилось.
3. Обязательно объясни, какое слово в условии подсказывает действие.
4. Обязательно объясни, почему здесь нужно сложение или вычитание.
5. Потом запиши решение обычной строкой, например: 4 + 2 = 6.
6. Потом скажи ответ.
7. В конце обязательно дай шаблон мышления, который ребёнок сможет перенести на похожие задачи.

Шаблон мышления давай в таком простом виде:
Запомни ход мысли:
было — ...
изменилось — ...
стало больше или меньше — ...
значит, выбираем ...
получаем — ...

Если задача на сложение, объясни, что словa «ещё», «добавили», «дали», «стало больше» обычно подсказывают сложение.
Если задача на вычитание, объясни, что слова «убрали», «отдали», «ушло», «осталось», «стало меньше» обычно подсказывают вычитание.

Не фантазируй и не добавляй лишних данных. Используй только то, что есть в задаче.

Строй ответ абзацами. Между смысловыми частями оставляй пустую строку."""


def cleanup_answer(text: str) -> str:
    clean = str(text or "")
    clean = clean.replace("\r", "")
    clean = re.sub(r"\*+", "", clean)
    clean = re.sub(r"`+", "", clean)
    clean = re.sub(r"#+\s*", "", clean)
    clean = clean.replace("\\(", "").replace("\\)", "")
    clean = clean.replace("\\[", "").replace("\\]", "")
    clean = clean.replace("\\", "")
    clean = re.sub(r"^[ \t]*\d+[.)]\s*", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^[ \t]*Шаг\s*\d+\s*:?\s*", "", clean, flags=re.MULTILINE | re.IGNORECASE)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


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
            user_text = str(data.get("text", "")).strip()
            if not user_text:
                return {"error": "Пустой текст задачи"}

            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "max_tokens": 900,
                "temperature": 0.2,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "details": response.text[:1000],
                }

            result = response.json()
            if "choices" not in result or not result["choices"]:
                return {
                    "error": "DeepSeek вернул неожиданный формат ответа",
                    "details": str(result)[:1000],
                }

            answer = result["choices"][0]["message"]["content"]
            return {"result": cleanup_answer(answer)}

        if action == "ocr":
            return {
                "error": "Распознавание по фото сейчас временно отключено, чтобы приложение не выдумывало задачу. Нажмите «Ввести текст» и вставьте задачу вручную."
            }

        return {"error": "Invalid action"}

    except httpx.ReadTimeout:
        return {"error": "DeepSeek timeout: сервер не дождался ответа от API"}
    except httpx.ConnectTimeout:
        return {"error": "DeepSeek connect timeout: сервер не смог подключиться к API"}
    except httpx.ConnectError as e:
        return {"error": f"DeepSeek connect error: {str(e)}"}
    except Exception as e:
        return {"error": f"Server exception: {str(e)}"}
