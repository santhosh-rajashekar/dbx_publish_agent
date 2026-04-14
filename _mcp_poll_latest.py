import json
import os
import time
from pathlib import Path

import requests

HOST = "https://adb-7405616457611961.1.azuredatabricks.net"
SPACE = "01f12d64b7151a668a8a031bf5807560"
CID = "01f13794b0401fa3880349048a1eac54"
MID = "01f13794b09b1a75ab319d258de21483"
POLL_TOOL = "poll_response_01f12d64b7151a668a8a031bf5807560"
URL = f"{HOST}/api/2.0/mcp/genie/{SPACE}"


def load_token() -> str:
    token = os.environ.get("DATABRICKS_TOKEN", "").strip().strip('"')
    if token:
        return token

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("DATABRICKS_TOKEN="):
                return s.split("=", 1)[1].strip().strip('"')

    raise RuntimeError("Missing DATABRICKS_TOKEN in environment or .env")


def parse_response_text(body: str) -> dict:
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(body)


def extract_status(result: dict) -> str | None:
    status = result.get("status")
    if status:
        return status

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        status = structured.get("status")
        if status:
            return status

    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            txt = first.get("text")
            if isinstance(txt, str) and txt.strip().startswith("{"):
                try:
                    status = json.loads(txt).get("status")
                    if status:
                        return status
                except Exception:
                    return None

    return None


def main() -> None:
    token = load_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    rid = 0
    for i in range(1, 121):
        rid += 1
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {
                "name": POLL_TOOL,
                "arguments": {"conversation_id": CID, "message_id": MID},
            },
        }
        resp = requests.post(URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()

        obj = parse_response_text(resp.text)
        result = obj.get("result", {})
        status = extract_status(result)

        print(f"poll {i}: status={status}")
        if status in {"COMPLETED", "FAILED", "CANCELLED"}:
            print("FINAL_START")
            print(json.dumps(result, indent=2))
            print("FINAL_END")
            return

        time.sleep(5)

    print("TIMEOUT")


if __name__ == "__main__":
    main()