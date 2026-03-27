import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Разрешаем CORS (запросы с вашего сайта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API-ключ DeepSeek (должен быть задан в переменных окружения Timeweb)
DEEPSEEK_API_KEY = os.environ.get("myapp_ai_math_1_4_API_key")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("Переменная окружения DEEPSEEK_API_KEY не установлена")

@app.post("/")
async def proxy(request: Request):
    data = await request.json()
    action = data.get("action")

    if action == "ocr":
        payload = {
            "model": "deepseek-vl",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": data["image"]},
                    {"type": "text", "text": "Извлеки текст задачи точно, без изменений. Верни только текст задачи."}
                ]
            }],
            "max_tokens": 500,
            "temperature": 0.1
        }
    elif action == "explain":
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты — учитель начальных классов. Объясни решение задачи по шагам, как у доски. Используй эмодзи."},
                {"role": "user", "content": data["text"]}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
    else:
        return {"error": "Invalid action"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        result = response.json()
        answer = result["choices"][0]["message"]["content"]

    return {"result": answer}

@app.get("/")
def read_root():
    return {"message": "Proxy is running. Use POST request with 'action' and payload."}
