from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI()

@app.get("/")
async def home():
    return {"status": "ok", "message": "Slack bot running"}

@app.post("/slack/events")
async def slack_events(request: Request):
    data = await request.json()

    # Slack URL verification (required when you set Events API Request URL)
    if data.get("type") == "url_verification":
        return JSONResponse({"challenge": data.get("challenge")})

    # Your Slack event handling here
    # Example: print event
    print("Slack Event:", data)

    return JSONResponse({"ok": True})
