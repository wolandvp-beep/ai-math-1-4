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
                        "content": "Ты — добрый репетитор для детей 7–10 лет. Объясняй решение задачи пошагово, простыми словами, на русском языке."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ],
                "max_tokens": 700,
                "temperature": 0.3
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

            answer = result["choices"][0]["message"]["content"]
            return {"result": answer}

        elif action == "ocr":
            return {
                "error": "Распознавание по фото временно отключено. Пожалуйста, нажмите «Ввести текст» и введите задачу вручную."
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
