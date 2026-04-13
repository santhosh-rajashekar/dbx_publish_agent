"""
Connectivity and query test for the Databricks Genie MCP server.
Run: python test_mcp_connection.py
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_QUERY = "What is the monthly trend of total incidents reported at Allianz?"


def load_setting(name: str) -> str:
    """Prefer process env var, fallback to .env."""
    value = os.environ.get(name, "").strip().strip('"')
    if value:
        return value

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith(f"{name}="):
                return stripped.split("=", 1)[1].strip().strip('"')

    return ""

def load_token() -> str:
    """Prefer process env var, fallback to .env, then prompt."""
    token = os.environ.get("DATABRICKS_TOKEN", "").strip().strip('"')
    if token:
        return token

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("DATABRICKS_TOKEN="):
                return stripped.split("=", 1)[1].strip().strip('"')

    return input("Enter your Databricks PAT: ").strip()


TOKEN = load_token()
WORKSPACE = load_setting("DATABRICKS_HOST").rstrip("/")
GENIE_SPACE_ID = load_setting("GENIE_SPACE_ID")
if not WORKSPACE:
    raise RuntimeError("Missing DATABRICKS_HOST. Set env var or .env entry.")
if not GENIE_SPACE_ID:
    raise RuntimeError("Missing GENIE_SPACE_ID. Set env var or .env entry.")
MCP_URL = f"{WORKSPACE}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
REQUEST_ID = 0


def next_request_id() -> int:
    global REQUEST_ID
    REQUEST_ID += 1
    return REQUEST_ID


def mcp_request(method: str, params: dict | None = None):
    payload = {
        "jsonrpc": "2.0",
        "id": next_request_id(),
        "method": method,
    }
    if params is not None:
        payload["params"] = params

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        MCP_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "text/event-stream" in content_type:
                # Return the first SSE payload and avoid blocking on long-lived streams.
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data:"):
                        return json.loads(line[5:].strip())
                return None

            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def find_string_param_name(input_schema: dict) -> str | None:
    properties = input_schema.get("properties", {})
    preferred = ["question", "prompt", "query", "message", "text"]

    for key in preferred:
        if key in properties and properties[key].get("type") == "string":
            return key

    for key, value in properties.items():
        if value.get("type") == "string":
            return key

    return None


def extract_text_from_tool_response(tool_result: dict) -> str:
    result = tool_result.get("result", {})
    content = result.get("content")

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        if parts:
            return "\n\n".join(parts)

    return json.dumps(result, indent=2)


def extract_status(result: dict) -> str | None:
    status = result.get("status")
    if status:
        return status

    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                try:
                    parsed = json.loads(item["text"])
                    status = parsed.get("status")
                    if status:
                        return status
                except Exception:
                    continue
    return None


def poll_until_complete(poll_tool_name: str, conversation_id: str, message_id: str) -> dict | None:
    terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED"}
    for attempt in range(1, 41):
        response = mcp_request(
            "tools/call",
            {
                "name": poll_tool_name,
                "arguments": {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                },
            },
        )
        if not response or "error" in response:
            print(f"   Poll {attempt}: transient error, retrying...")
            time.sleep(2)
            continue

        result = response.get("result", {})
        status = extract_status(result) or "UNKNOWN"
        print(f"   Poll {attempt}: status={status}")

        if status in terminal_statuses:
            return response

        time.sleep(2)

    return None


def run_question(tools: list[dict], question: str) -> bool:
    if not tools:
        print("\n3. Query skipped - no tools available.")
        return False

    # Prefer a Genie-like tool name when present; otherwise try all tools.
    ordered_tools = sorted(
        tools,
        key=lambda t: 0 if "genie" in t.get("name", "").lower() else 1,
    )

    print(f"\n3. Running query:\n   {question}")

    poll_tool_name = next(
        (t.get("name") for t in tools if t.get("name", "").startswith("poll_response_")),
        None,
    )

    for tool in ordered_tools:
        tool_name = tool.get("name")
        if not tool_name or tool_name.startswith("poll_response_"):
            continue

        input_schema = tool.get("inputSchema") or {}
        arg_name = find_string_param_name(input_schema)
        if not arg_name:
            continue

        print(f"   Trying tool '{tool_name}' using argument '{arg_name}'...")
        response = mcp_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": {arg_name: question},
            },
        )

        if not response:
            continue

        if "error" in response:
            print(f"   Tool returned error: {json.dumps(response['error'])}")
            continue

        result = response.get("result", {})
        conversation_id = result.get("conversationId")
        message_id = result.get("messageId")
        if conversation_id and message_id and poll_tool_name:
            print("   Query accepted asynchronously; polling for completion...")
            final_response = poll_until_complete(poll_tool_name, conversation_id, message_id)
            if not final_response:
                print("\nQuery timed out while waiting for completion.")
                return False

            final_text = extract_text_from_tool_response(final_response)
            print("\nQuery response:\n")
            print(final_text)
            return True

        text = extract_text_from_tool_response(response)
        print("\nQuery response:\n")
        print(text)
        return True

    print("\nQuery failed: couldn't call any tool with a compatible text parameter.")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=DEFAULT_QUERY)
    args = parser.parse_args()

    print(f"\nTarget MCP URL:\n  {MCP_URL}\n")

    print("1. Sending 'initialize' handshake...")
    result = mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "0.1"}
    })
    if result:
        print(f"   OK — server responded: {json.dumps(result, indent=2)[:300]}")
    else:
        print("   FAILED — see error above.")
        return

    print("\n2. Listing available tools...")
    result = mcp_request("tools/list")
    tools = []
    if result and "result" in result:
        tools = result["result"].get("tools", [])
        if tools:
            print(f"   Found {len(tools)} tool(s):")
            for t in tools:
                print(f"     - {t['name']}: {t.get('description', '')[:80]}")
        else:
            print("   No tools returned (space may be empty).")
    else:
        print(f"   Response: {result}")
        return

    run_question(tools, args.query)

    print("\nDone. Connection test complete.")


if __name__ == "__main__":
    main()
