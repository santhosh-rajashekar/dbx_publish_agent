from pathlib import Path

import requests

URL = "https://dbx-genie-e8ekeqh7eae9htet.francecentral-01.azurewebsites.net/api/messages"
OUT = Path("_probe_deployed_post.out")


def main() -> None:
    try:
        resp = requests.post(
            URL,
            json={"text": "What is the monthly trend of total incidents reported at Allianz?"},
            timeout=120,
        )
        text = f"status={resp.status_code}\nbody={resp.text[:4000]}\n"
    except Exception as exc:
        text = f"error={type(exc).__name__}: {exc}\n"

    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()