import json
import subprocess
import time

import requests

AZ_CMD = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
RG = "rg-mslearn-dbricks-2026"
BOT = "dbx_genie_bot"
TEST_TEXT = "What is the monthly trend of total incidents reported at Allianz?"


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def get_directline_secret() -> str:
    query = "setting.sites[0].key"
    value = run([AZ_CMD, "bot", "directline", "show", "--name", BOT, "--resource-group", RG, "--with-secrets", "true", "--query", query, "--output", "tsv"])
    if not value:
        raise RuntimeError("Direct Line secret is empty")
    return value


def main() -> None:
    secret = get_directline_secret()
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}

    start = requests.post("https://directline.botframework.com/v3/directline/conversations", headers=headers, timeout=30)
    start.raise_for_status()
    c = start.json()
    conversation_id = c["conversationId"]
    token = c.get("token", "")

    print("conversation_started", bool(conversation_id), flush=True)

    post_headers = {"Authorization": f"Bearer {token or secret}", "Content-Type": "application/json"}
    activity = {
        "type": "message",
        "from": {"id": "user1"},
        "text": TEST_TEXT,
    }
    send = requests.post(
        f"https://directline.botframework.com/v3/directline/conversations/{conversation_id}/activities",
        headers=post_headers,
        json=activity,
        timeout=30,
    )
    send.raise_for_status()
    print("activity_post_status", send.status_code, flush=True)

    watermark = None
    bot_reply = None
    for _ in range(4):
        params = {"watermark": watermark} if watermark else None
        poll = requests.get(
            f"https://directline.botframework.com/v3/directline/conversations/{conversation_id}/activities",
            headers={"Authorization": f"Bearer {token or secret}"},
            params=params,
            timeout=30,
        )
        poll.raise_for_status()
        body = poll.json()
        watermark = body.get("watermark")
        activities = body.get("activities", [])

        for a in activities:
            frm = (a.get("from") or {}).get("id", "")
            if frm != "user1" and a.get("type") == "message" and a.get("text"):
                bot_reply = a.get("text")
                break
        if bot_reply:
            break
        time.sleep(2)

    print("bot_reply_found", bool(bot_reply), flush=True)
    if bot_reply:
        print("bot_reply_preview", bot_reply[:500], flush=True)
    else:
        print("bot_reply_preview", "", flush=True)


if __name__ == "__main__":
    main()