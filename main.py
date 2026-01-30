import os
import time
import hmac
import hashlib
import urllib.parse
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

from db import init_db, save_user_token, get_user_token

app = FastAPI()

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL")  # https://xxxx.up.railway.app

if not APP_BASE_URL:
    APP_BASE_URL = ""


# ----------------------------
# Startup
# ----------------------------
@app.on_event("startup")
def startup():
    init_db()


# ----------------------------
# Slack signature verification
# ----------------------------
def verify_slack_signature(request: Request, raw_body: bytes):
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Missing SLACK_SIGNING_SECRET")

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    slack_signature = request.headers.get("X-Slack-Signature")

    if not timestamp or not slack_signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    # Replay protection
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
# Helpers
# ----------------------------
def slack_post_as_user(user_token: str, channel_id: str, text: str):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {user_token}"}
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


# ----------------------------
# Install button page
# ----------------------------
@app.get("/slack/install")
async def slack_install():
    """
    User opens this link, clicks install, authorizes app.
    """
    if not SLACK_CLIENT_ID or not APP_BASE_URL:
        return PlainTextResponse("Missing SLACK_CLIENT_ID or APP_BASE_URL", status_code=500)

    redirect_uri = f"{APP_BASE_URL}/slack/oauth_redirect"

    params = {
        "client_id": SLACK_CLIENT_ID,
        "scope": "",  # bot scopes not needed for this approach
        "user_scope": "chat:write",
        "redirect_uri": redirect_uri,
    }

    install_url = "https://slack.com/oauth/v2/authorize?" + urllib.parse.urlencode(params)

    html = f"""
    <html>
      <body style="font-family:Arial;padding:30px;">
        <h2>Install Slack Greeting App</h2>
        <p>Click below to authorize. This allows the app to post messages as YOU.</p>
        <a href="{install_url}" style="display:inline-block;padding:12px 18px;background:#4A154B;color:white;text-decoration:none;border-radius:8px;">
          Authorize Slack
        </a>
      </body>
    </html>
    """
    return HTMLResponse(html)


# ----------------------------
# OAuth Redirect
# ----------------------------
@app.get("/slack/oauth_redirect")
async def slack_oauth_redirect(code: str = None, error: str = None):
    if error:
        return HTMLResponse(f"<h3>OAuth failed: {error}</h3>")

    if not code:
        return HTMLResponse("<h3>Missing code</h3>", status_code=400)

    if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET or not APP_BASE_URL:
        return HTMLResponse("<h3>Server missing Slack OAuth env vars</h3>", status_code=500)

    redirect_uri = f"{APP_BASE_URL}/slack/oauth_redirect"

    # Exchange code for token
    token_url = "https://slack.com/api/oauth.v2.access"
    payload = {
        "client_id": SLACK_CLIENT_ID,
        "client_secret": SLACK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    r = requests.post(token_url, data=payload, timeout=20)
    data = r.json()

    if not data.get("ok"):
        return HTMLResponse(f"<pre>OAuth error: {data}</pre>", status_code=400)

    # This is the IMPORTANT part: user token
    authed_user = data.get("authed_user", {})
    user_id = authed_user.get("id")
    user_token = authed_user.get("access_token")

    if not user_id or not user_token:
        return HTMLResponse(f"<pre>Missing authed_user token: {data}</pre>", status_code=400)

    save_user_token(user_id, user_token)

    return HTMLResponse("""
        <h2>✅ Authorized Successfully</h2>
        <p>You can now use <b>/greet</b> in Slack and it will post as YOU.</p>
    """)


# ----------------------------
# Slash Command endpoint
# Request URL for /greet -> https://YOURAPP.up.railway.app/greet
# ----------------------------
@app.post("/greet")
async def greet_slash_command(request: Request):
    raw = await request.body()
    verify_slack_signature(request, raw)

    form = await request.form()

    user_id = form.get("user_id")
    channel_id = form.get("channel_id")
    text_arg = (form.get("text") or "").strip()

    if not user_id or not channel_id:
        return PlainTextResponse("Invalid request", status_code=400)

    # get token for THIS user
    user_token = get_user_token(user_id)
    if not user_token:
        # send install link to that user
        return PlainTextResponse(
            f"❌ You are not authorized.\nPlease open: {APP_BASE_URL}/slack/install",
            status_code=200,
        )

    msg = text_arg if text_arg else "Good morning everyone ☀️"

    # post as the actual user
    slack_post_as_user(user_token, channel_id, msg)

    return PlainTextResponse("✅ Sent!", status_code=200)
