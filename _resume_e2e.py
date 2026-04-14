import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

WORKDIR = Path(__file__).resolve().parent
REPORT = WORKDIR / "_resume_e2e_report.txt"
QUERY = "What is the monthly trend of total incidents reported at Allianz?"
WEBAPP_BASE = "https://dbx-genie-e8ekeqh7eae9htet.francecentral-01.azurewebsites.net"
AZ_CMD = Path(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd")


def load_setting(name: str) -> str:
    value = os.environ.get(name, "").strip().strip('"')
    if value:
        return value

    env_path = WORKDIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            if k.strip() == name:
                return v.strip().strip('"')
    return ""


def mcp_call(url: str, headers: dict, rid: int, method: str, params: dict | None = None) -> tuple[int, dict]:
    payload = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        payload["params"] = params

    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()

    for line in resp.text.splitlines():
        if line.startswith("data:"):
            return rid + 1, json.loads(line[5:].strip())
    return rid + 1, resp.json()


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


def run_mcp_sequence(lines: list[str]) -> None:
    host = load_setting("DATABRICKS_HOST").rstrip("/")
    token = load_setting("DATABRICKS_TOKEN")
    space = load_setting("GENIE_SPACE_ID")

    lines.append("## MCP")
    if not (host and token and space):
        lines.append("MCP: SKIPPED (missing DATABRICKS_HOST/DATABRICKS_TOKEN/GENIE_SPACE_ID)")
        lines.append("")
        return

    url = f"{host}/api/2.0/mcp/genie/{space}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    rid = 1
    try:
        rid, init = mcp_call(
            url,
            headers,
            rid,
            "initialize",
            {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "resume-e2e", "version": "0.1"}},
        )
        lines.append(f"initialize: ok ({init.get('jsonrpc', 'unknown')})")

        rid, tools = mcp_call(url, headers, rid, "tools/list")
        tool_list = tools.get("result", {}).get("tools", [])
        q_tool = next((t.get("name") for t in tool_list if (t.get("name") or "").startswith("query_space_")), None)
        p_tool = next((t.get("name") for t in tool_list if (t.get("name") or "").startswith("poll_response_")), None)
        lines.append(f"tools: {len(tool_list)}")
        lines.append(f"query_tool: {q_tool}")
        lines.append(f"poll_tool: {p_tool}")

        if not q_tool:
            lines.append("MCP query: FAILED (query tool missing)")
            lines.append("")
            return

        rid, q_res = mcp_call(url, headers, rid, "tools/call", {"name": q_tool, "arguments": {"query": QUERY}})
        q_result = q_res.get("result", {})
        cid = q_result.get("conversationId")
        mid = q_result.get("messageId")
        lines.append(f"query_conversation_id: {cid}")
        lines.append(f"query_message_id: {mid}")

        final_result = q_result
        if cid and mid and p_tool:
            for i in range(1, 46):
                rid, p_res = mcp_call(
                    url,
                    headers,
                    rid,
                    "tools/call",
                    {"name": p_tool, "arguments": {"conversation_id": cid, "message_id": mid}},
                )
                final_result = p_res.get("result", {})
                status = extract_status(final_result)
                lines.append(f"poll_{i}: {status}")
                if status in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
                time.sleep(4)

        final_status = extract_status(final_result)
        lines.append(f"final_status: {final_status}")

        text_preview = ""
        structured = final_result.get("structuredContent")
        if isinstance(structured, dict):
            content = structured.get("content", {})
            attachments = content.get("textAttachments", []) if isinstance(content, dict) else []
            if attachments:
                text_preview = str(attachments[0])
        if not text_preview:
            content = final_result.get("content")
            if isinstance(content, list) and content and isinstance(content[0], dict):
                text_preview = str(content[0].get("text", ""))

        if text_preview:
            lines.append("final_text_preview:")
            lines.append(text_preview[:900])

    except Exception as exc:
        lines.append(f"MCP: FAILED ({type(exc).__name__}: {exc})")

    lines.append("")


def run_webapp_probes(lines: list[str]) -> None:
    lines.append("## Webapp")

    try:
        r = requests.get(f"{WEBAPP_BASE}/", timeout=30)
        lines.append(f"GET /: {r.status_code}")
        lines.append(f"GET / body: {r.text[:300]}")
    except Exception as exc:
        lines.append(f"GET / failed: {type(exc).__name__}: {exc}")

    try:
        r = requests.post(
            f"{WEBAPP_BASE}/api/messages",
            json={"text": QUERY},
            timeout=120,
        )
        lines.append(f"POST /api/messages: {r.status_code}")
        lines.append(f"POST /api/messages body: {r.text[:700]}")
    except Exception as exc:
        lines.append(f"POST /api/messages failed: {type(exc).__name__}: {exc}")

    lines.append("")


def run_optional_deploy(lines: list[str]) -> None:
    lines.append("## Deploy")
    if not AZ_CMD.exists():
        lines.append(f"zipdeploy: SKIPPED (Azure CLI not found at {AZ_CMD})")
        lines.append("")
        return

    try:
        proc = subprocess.run(
            [sys.executable, "_zipdeploy.py"],
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        lines.append(f"zipdeploy exit_code: {proc.returncode}")
        out = (proc.stdout or "")[-1500:]
        err = (proc.stderr or "")[-800:]
        if out:
            lines.append("zipdeploy stdout tail:")
            lines.append(out)
        if err:
            lines.append("zipdeploy stderr tail:")
            lines.append(err)
    except Exception as exc:
        lines.append(f"zipdeploy failed: {type(exc).__name__}: {exc}")

    lines.append("")


def main() -> None:
    lines: list[str] = []
    lines.append("# Resume E2E Report")
    lines.append(time.strftime("generated_at=%Y-%m-%d %H:%M:%S"))
    lines.append("")

    run_mcp_sequence(lines)
    run_webapp_probes(lines)
    run_optional_deploy(lines)

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report_written={REPORT}")


if __name__ == "__main__":
    main()