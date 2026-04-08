import os
import re

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import explanation_engine as engine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wolandvp-beep.github.io"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DEEPSEEK_API_KEY = os.environ.get("myapp_ai_math_1_4_API_key")
SYSTEM_PROMPT = getattr(engine, "SYSTEM_PROMPT", getattr(engine, "SYSTEM_PROMPT_V10", ""))
NON_MATH_REPLY = engine.NON_MATH_REPLY
plural_form = engine.plural_form
call_deepseek = engine.call_deepseek


async def build_explanation(user_text: str) -> dict:
    original_callback = engine.call_deepseek
    llm_callback = call_deepseek
    if (not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == 'dummy') and llm_callback is original_callback:
        llm_callback = None
    try:
        if llm_callback is not None:
            engine.call_deepseek = llm_callback
        return await engine.build_explanation(user_text)
    finally:
        engine.call_deepseek = original_callback


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
            return JSONResponse(status_code=400, content={"error": "Invalid action"})

        user_text = str(data.get("text") or "").strip()
        if not user_text:
            return JSONResponse(status_code=400, content={"error": "Пустой текст задачи"})
        if len(user_text) > 2000:
            return JSONResponse(status_code=400, content={"error": "Текст задачи слишком длинный"})

        if not re.search(r"\d|x|х|[+\-*/=×÷:]", user_text):
            return {"result": NON_MATH_REPLY, "source": "guard", "validated": True}

        return await build_explanation(user_text)

    except httpx.ReadTimeout:
        return JSONResponse(status_code=504, content={"error": "DeepSeek timeout: сервер не дождался ответа от API"})
    except httpx.ConnectTimeout:
        return JSONResponse(status_code=504, content={"error": "DeepSeek connect timeout: сервер не смог подключиться к API"})
    except httpx.ConnectError as exc:
        return JSONResponse(status_code=502, content={"error": f"DeepSeek connect error: {str(exc)}"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Server exception: {str(exc)}"})
