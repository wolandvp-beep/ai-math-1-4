import os
import re
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
9. Не фантазируй. Объясняй только то, что действительно видно в задаче.
10. Если текст на фото плохо читается или часть задачи не видна, честно скажи, что фото нужно сделать чётче.
11. Ответ должен быть понятен ребёнку младшей школы.

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

Потом объясни, почему именно здесь нужно выбрать это действие.

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
""".strip()


def extract_data_url_parts(image_value: str):
    image_value = (image_value or "").strip()
    if not image_value:
        raise ValueError("Не передано изображение")

    if image_value.startswith("data:image"):
        match = re.match(r"^data:(image/[-+.\w]+);base64,(.+)$", image_value, re.DOTALL)
        if not match:
            raise ValueError("Некорректный формат изображения")
        mime_type = match.group(1)
        base64_data = match.group(2)
        return mime_type, base64_data

    return "image/jpeg", image_value


async def call_deepseek(payload: dict, timeout_seconds: float = 60.0):
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

        if action == "explain":
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

        if action == "explain_image":
            image_value = data.get("image", "")
            try:
                mime_type, image_base64 = extract_data_url_parts(image_value)
            except ValueError as e:
                return {"error": str(e)}

            payload = {
                "model": "deepseek-vl",
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": f"data:{mime_type};base64,{image_base64}",
                            },
                            {
                                "type": "text",
                                "text": (
                                    "На фото задача из учебника. Сначала внимательно прочитай её. "
                                    "Если текст читается плохо или виден не полностью, честно скажи, "
                                    "что нужно более чёткое фото. Если текст читается хорошо, "
                                    "сразу объясни задачу ребёнку по тем же правилам, что и для текстового ввода."
                                ),
                            },
                        ],
                    },
                ],
                "max_tokens": 900,
                "temperature": 0.2,
            }

            return await call_deepseek(payload, timeout_seconds=60.0)

        return {"error": "Invalid action"}

    except httpx.ReadTimeout:
        return {"error": "DeepSeek timeout: сервер не дождался ответа от API"}
    except httpx.ConnectTimeout:
        return {"error": "DeepSeek connect timeout: сервер не смог подключиться к API"}
    except httpx.ConnectError as e:
        return {"error": f"DeepSeek connect error: {str(e)}"}
    except Exception as e:
        return {"error": f"Server exception: {str(e)}"}
