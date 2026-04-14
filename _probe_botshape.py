from pathlib import Path

import requests

OUT = Path("_probe_botshape.out")
URL = "https://dbx-genie-e8ekeqh7eae9htet.francecentral-01.azurewebsites.net/api/messages"


def main() -> None:
    payload = {
        "type": "message",
        "id": "abc123",
        "text": "ping",
        "serviceUrl": "https://directline.botframework.com/",
        "conversation": {"id": "test-conv"},
        "from": {"id": "user1"},
        "recipient": {"id": "bot1"},
    }

    try:
        resp = requests.post(URL, json=payload, timeout=90)
        text = f"status={resp.status_code}\nbody={resp.text[:1000]}\n"
    except Exception as exc:
        text = f"error={type(exc).__name__}: {exc}\n"

    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()