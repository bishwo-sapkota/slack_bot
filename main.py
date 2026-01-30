from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
async def home():
    return {"status": "ok", "message": "Slack bot running"}

@app.get("/greet")
async def greet():
    return {"message": "Good morning everyone"}

@app.post("/slack/events")
async def slack_events(request: Request):
    data = await request.json()

    if data.get("type") == "url_verification":
        return JSONResponse({"challenge": data.get("challenge")})

    print("Slack Event:", data)
    return JSONResponse({"ok": True})
