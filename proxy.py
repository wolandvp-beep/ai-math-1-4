from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Ключ будет передан через переменную окружения в Timeweb Cloud
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("ОШИБКА: переменная DEEPSEEK_API_KEY не задана!")
    # для теста можно использовать запасной ключ, но лучше выйти с ошибкой
    raise RuntimeError("DEEPSEEK_API_KEY not set")

@app.route('/', methods=['POST', 'OPTIONS'])
def proxy():
    if request.method == 'OPTIONS':
        resp = jsonify({'ok': True})
        resp.headers.add('Access-Control-Allow-Origin', '*')
        resp.headers.add('Access-Control-Allow-Methods', 'POST')
        resp.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return resp

    data = request.get_json()
    action = data.get('action')

    if action == 'ocr':
        payload = {
            "model": "deepseek-vl",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": data['image']},
                    {"type": "text", "text": "Извлеки текст задачи точно, без изменений. Верни только текст задачи."}
                ]
            }],
            "max_tokens": 500,
            "temperature": 0.1
        }
    elif action == 'explain':
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты — учитель начальных классов. Объясни решение задачи по шагам, как у доски. Используй эмодзи."},
                {"role": "user", "content": data['text']}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
    else:
        return jsonify({"error": "Invalid action"}), 400

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        answer = result['choices'][0]['message']['content']
    except Exception as e:
        return jsonify({"error": f"DeepSeek API error: {str(e)}"}), 500

    resp = jsonify({"result": answer})
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)