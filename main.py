import os
import time
import hmac
import hashlib
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")              # xoxb-...
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")    # from Slack App -> Basic Information
DEFAULT_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")          # for cron job / manual tests


# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(request: Request, raw_body: bytes):
    if not SLACK_SIGNING_SECRET:
        # Not recommended for production, but allowed for testing
        return

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    slack_signature = request.headers.get("X-Slack-Signature")

    if not timestamp or not slack_signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    # prevent replay attack
    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=401, detail="Slack request too old")

    basestring = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
    my_signature = (
        "v0="
        + hmac.new(
            SLACK_SIGNING_SECRET.encode("utf-8"),
            basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(my_signature, slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


# ----------------------------
# Slack API helper
# ----------------------------
def post_message(channel_id: str, text: str):
    if not SLACK_BOT_TOKEN:
        raise Exception("Missing SLACK_BOT_TOKEN")

    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    payload = {"channel": channel_id, "text": text}

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    data = r.json()

    if not data.get("ok"):
        raise Exception(f"Slack API error: {data}")

    return data


# ----------------------------
# Routes
# ----------------------------
@app.get("/")
async def home():
    return {"status": "ok", "message": "Slack bot running"}


# For browser test:
# GET https://yourapp.up.railway.app/greet
@app.get("/greet")
async def greet_get():
    if not DEFAULT_CHANNEL_ID:
        return JSONResponse(
            {"ok": False, "error": "Missing SLACK_CHANNEL_ID variable"},
            status_code=500,
        )

    msg = "Good morning everyone ☀️"
    data = post_message(DEFAULT_CHANNEL_ID, msg)
    return {"ok": True, "sent": True, "slack": data}


# Slash command handler:
# In Slack App -> Slash Commands:
# Command: /greet
# Request URL: https://yourapp.up.railway.app/greet
@app.post("/greet")
async def greet_slash_command(request: Request):
    raw = await request.body()
    verify_slack_signature(request, raw)

    form = await request.form()

    # Slack sends form-encoded data
    user_id = form.get("user_id")           # Uxxxx
    user_name = form.get("user_name")       # e.g. bishwo
    channel_id = form.get("channel_id")     # Cxxxx
    text_arg = (form.get("text") or "").strip()  # /greet hello

    # build message
    if text_arg:
        msg = f"☀️ {text_arg}\n— from <@{user_id}>"
    else:
        msg = f"Good morning everyone ☀️\n— from <@{user_id}>"

    # post into same channel where command used
    post_message(channel_id, msg)

    # reply to the command request (private confirmation)
    return PlainTextResponse(f"✅ Greeting sent by @{user_name}", status_code=200)


# Optional Slack events endpoint (only needed if you use Events API)
@app.post("/slack/events")
async def slack_events(request: Request):
    raw = await request.body()
    verify_slack_signature(request, raw)

    data = await request.json()

    if data.get("type") == "url_verification":
        return JSONResponse({"challenge": data.get("challenge")})

    print("EVENT:", data)
    return JSONResponse({"ok": True})
