import os
import time
import hmac
import hashlib
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()

# Railway Variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")              # xoxb-...
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")    # from Slack App settings
DEFAULT_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")          # optional fallback


# ----------------------------
# Slack Security Verification
# ----------------------------
def verify_slack_signature(request: Request, raw_body: bytes):
    """
    Verifies Slack request signature using Signing Secret.
    Required to avoid fake requests hitting your endpoint.
    """
    if not SLACK_SIGNING_SECRET:
        # If you didn't set signing secret, we skip verification
        # (Not recommended for production)
        return

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    slack_signature = request.headers.get("X-Slack-Signature")

    if not timestamp or not slack_signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    # prevent replay attacks (5 minutes window)
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
# Slack Message Sender
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


# Manual endpoint trigger (for testing)
@app.get("/greet")
async def greet():
    if not DEFAULT_CHANNEL_ID:
        return JSONResponse(
            {"ok": False, "error": "Missing SLACK_CHANNEL_ID variable"},
            status_code=500,
        )

    text = "Good morning everyone ☀️"
    data = post_message(DEFAULT_CHANNEL_ID, text)
    return {"ok": True, "sent": True, "slack": data}


# Slack Events API endpoint
@app.post("/slack/events")
async def slack_events(request: Request):
    raw = await request.body()
    verify_slack_signature(request, raw)

    data = await request.json()

    # Slack URL verification challenge
    if data.get("type") == "url_verification":
        return JSONResponse({"challenge": data.get("challenge")})

    # You can handle events here if you want
    # example: print
    print("EVENT:", data)

    return JSONResponse({"ok": True})


# Slash command endpoint
# In Slack App -> Slash Commands -> Request URL:
# https://your-domain.up.railway.app/slack/commands
@app.post("/slack/commands")
async def slack_commands(request: Request):
    raw = await request.body()
    verify_slack_signature(request, raw)

    form = await request.form()

    command = form.get("command")            # "/greet"
    user_id = form.get("user_id")            # Uxxxx
    user_name = form.get("user_name")        # "bishwo"
    channel_id = form.get("channel_id")      # Cxxxx
    text_arg = (form.get("text") or "").strip()  # optional args after command

    if command != "/greet":
        return PlainTextResponse("Unknown command", status_code=200)

    # Customize message
    # You can do: /greet hello -> sends hello
    if text_arg:
        msg = f"☀️ {text_arg}\n— from <@{user_id}>"
    else:
        msg = f"Good morning everyone ☀️\n— from <@{user_id}>"

    # post in same channel user typed command
    post_message(channel_id, msg)

    # reply privately to user (ephemeral)
    return PlainTextResponse(f"✅ Sent greeting to channel as requested by @{user_name}", status_code=200)
