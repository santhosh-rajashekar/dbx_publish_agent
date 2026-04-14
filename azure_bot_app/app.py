import json
import os
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)


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


def call_mcp(question: str) -> str:
    host = load_setting("DATABRICKS_HOST").rstrip("/")
    token = load_setting("DATABRICKS_TOKEN")
    space = load_setting("GENIE_SPACE_ID")

    if not (host and token and space):
        return "Bot is running, but Databricks settings are incomplete."

    url = f"{host}/api/2.0/mcp/genie/{space}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    rid = 0

    def mcp(method: str, params: dict | None = None) -> dict:
        nonlocal rid
        rid += 1
        payload = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        body = r.text
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return r.json()

    tools = mcp("tools/list").get("result", {}).get("tools", [])
    q_tool = next((t.get("name") for t in tools if (t.get("name") or "").startswith("query_space_")), None)
    p_tool = next((t.get("name") for t in tools if (t.get("name") or "").startswith("poll_response_")), None)
    if not q_tool:
        return "Databricks MCP is reachable, but query tool was not found."

    q = mcp("tools/call", {"name": q_tool, "arguments": {"query": question}})
    result = q.get("result", {})
    cid = result.get("conversationId")
    mid = result.get("messageId")

    if cid and mid and p_tool:
        for _ in range(15):
            pr = mcp("tools/call", {"name": p_tool, "arguments": {"conversation_id": cid, "message_id": mid}})
            presult = pr.get("result", {})
            status = presult.get("status")
            if status in {"COMPLETED", "FAILED", "CANCELLED"}:
                content = presult.get("content", [])
                if isinstance(content, list):
                    texts = [x.get("text", "") for x in content if isinstance(x, dict) and x.get("text")]
                    if texts:
                        return "\n\n".join(texts)[:3500]
                return json.dumps(presult)[:3500]
            time.sleep(2)
        return "Query accepted, but timed out waiting for completion."

    content = result.get("content", [])
    if isinstance(content, list):
        texts = [x.get("text", "") for x in content if isinstance(x, dict) and x.get("text")]
        if texts:
            return "\n\n".join(texts)[:3500]

    return "Query submitted, but no text response was returned."


def get_bot_access_token() -> str:
    app_id = load_setting("MicrosoftAppId")
    app_password = load_setting("MicrosoftAppPassword")
    tenant_id = load_setting("MicrosoftAppTenantId")

    if not (app_id and app_password and tenant_id):
        return ""

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": app_id,
        "client_secret": app_password,
        "scope": "https://api.botframework.com/.default",
    }
    resp = requests.post(token_url, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json().get("access_token", "")


def send_botframework_reply(activity: dict, text: str) -> tuple[bool, str]:
    service_url = (activity.get("serviceUrl") or "").strip()
    conversation = activity.get("conversation") or {}
    conversation_id = (conversation.get("id") or "").strip()

    if not (service_url and conversation_id):
        return False, "missing serviceUrl or conversation id"

    token = get_bot_access_token()
    if not token:
        return False, "missing bot auth settings (MicrosoftAppId/MicrosoftAppPassword/MicrosoftAppTenantId)"

    reply = {
        "type": "message",
        "text": text,
        "from": activity.get("recipient"),
        "recipient": activity.get("from"),
        "conversation": conversation,
        "replyToId": activity.get("id"),
    }

    endpoint = urljoin(service_url.rstrip("/") + "/", f"v3/conversations/{conversation_id}/activities")
    resp = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=reply,
        timeout=30,
    )
    if resp.status_code not in (200, 201, 202):
        return False, f"connector post failed: {resp.status_code}"

    return True, "ok"


@app.get("/")
def root():
    return jsonify({"status": "ok", "service": "dbx-genie-bot-backend"}), 200


@app.post("/api/messages")
def messages():
    activity = request.get_json(silent=True) or {}
    text = (activity.get("text") or "").strip()

    if not text:
        reply_text = "Send a message and I will query Databricks Genie."
    else:
        try:
            reply_text = call_mcp(text)
        except Exception as exc:
            reply_text = f"Backend error while querying Databricks: {type(exc).__name__}"

    # If this request came from Bot Framework channel, post reply via connector.
    if activity.get("serviceUrl") and (activity.get("conversation") or {}).get("id"):
        ok, detail = send_botframework_reply(activity, reply_text)
        code = 202 if ok else 500
        return jsonify({"status": "accepted" if ok else "failed", "detail": detail}), code

    return jsonify({"type": "message", "text": reply_text}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
