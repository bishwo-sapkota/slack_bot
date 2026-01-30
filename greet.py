import os
import requests

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

def main():
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        raise Exception("Missing SLACK_BOT_TOKEN or SLACK_CHANNEL_ID")

    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    payload = {"channel": SLACK_CHANNEL_ID, "text": "Good morning everyone ☀️"}

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    print(r.text)

if __name__ == "__main__":
    main()
