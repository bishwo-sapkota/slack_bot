import os
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

@app.get("/")
async def home():
    return {"status": "ok", "message": "Slack bot running"}

@app.get("/greet")
async def greet():
    text = "Good morning everyone ☀️"

    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        return JSONResponse(
            {"ok": False, "error": "Missing SLACK_BOT_TOKEN or SLACK_CHANNEL_ID"},
            status_code=500
        )

    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    payload = {"channel": SLACK_CHANNEL_ID, "text": text}

    r = requests.post(url, headers=headers, json=payload)
    data = r.json()

    return {"ok": data.get("ok"), "slack_response": data}
