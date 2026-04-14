import json
import os
import sys
import time
from pathlib import Path

import requests


def load_setting(name: str) -> str:
    value = os.environ.get(name, "").strip().strip('"')
    if value:
        return value

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            if k.strip() == name:
                return v.strip().strip('"')
    return ""


def parse_sse_or_json(body: str) -> dict:
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
                    return json.loads(txt).get("status")
                except Exception:
                    return None
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: _mcp_poll_message.py <conversation_id> <message_id>")
        return 2

    conversation_id = sys.argv[1]
    message_id = sys.argv[2]

    host = load_setting("DATABRICKS_HOST").rstrip("/")
    token = load_setting("DATABRICKS_TOKEN")
    space = load_setting("GENIE_SPACE_ID")
    if not (host and token and space):
        print("ERROR: Missing DATABRICKS_HOST, DATABRICKS_TOKEN, or GENIE_SPACE_ID")
        return 3

    url = f"{host}/api/2.0/mcp/genie/{space}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    rid = 1
    poll_tool = f"poll_response_{space}"

    final_result = {}
    for i in range(1, 91):
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {
                "name": poll_tool,
                "arguments": {"conversation_id": conversation_id, "message_id": message_id},
            },
        }
        rid += 1

        response = requests.post(url, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        body = parse_sse_or_json(response.text)
        final_result = body.get("result", {})
        status = extract_status(final_result)
        print(f"poll {i}: status={status}")

        if status in {"COMPLETED", "FAILED", "CANCELLED"}:
            print("FINAL_START")
            print(json.dumps(final_result, indent=2))
            print("FINAL_END")
            return 0

        time.sleep(5)

    print("TIMEOUT")
    print("FINAL_START")
    print(json.dumps(final_result, indent=2))
    print("FINAL_END")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())