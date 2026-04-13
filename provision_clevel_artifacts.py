"""
Provision and validate Databricks workspace artifacts for a C-level Q&A agent.

What this script does:
1. Creates a workspace folder in Databricks.
2. Publishes three notebook artifacts used for executive analytics prompts.
3. Verifies the artifacts exist.
4. Validates Genie MCP connectivity by running initialize + tools/list.

Usage:
  python provision_clevel_artifacts.py
  python provision_clevel_artifacts.py --workspace-dir /Shared/C_Level_Agent
  python provision_clevel_artifacts.py --skip-mcp-test

Auth:
- Uses DATABRICKS_TOKEN from environment or .env file.
- Uses DATABRICKS_HOST and GENIE_SPACE_ID from environment or .env file.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_WORKSPACE_DIR = "/Shared/C_Level_Agent"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def load_setting(name: str, env_file_values: dict[str, str], default: str = "") -> str:
    return os.environ.get(name, env_file_values.get(name, default)).strip().strip('"')


class DatabricksClient:
    def __init__(self, host: str, token: str):
        self.host = host.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.host}{path}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            method=method,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if not body:
                    return {}
                return json.loads(body)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {err.code} for {path}: {body}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(f"Network error for {path}: {err}") from err

    def mkdirs(self, workspace_path: str) -> None:
        self._request("POST", "/api/2.0/workspace/mkdirs", {"path": workspace_path})

    def import_notebook(self, workspace_path: str, source: str, language: str = "PYTHON") -> None:
        content = base64.b64encode(source.encode("utf-8")).decode("ascii")
        self._request(
            "POST",
            "/api/2.0/workspace/import",
            {
                "path": workspace_path,
                "format": "SOURCE",
                "language": language,
                "content": content,
                "overwrite": True,
            },
        )

    def list_dir(self, workspace_path: str) -> list[dict[str, Any]]:
        response = self._request("GET", f"/api/2.0/workspace/list?path={workspace_path}")
        return response.get("objects", [])

    def get_status(self, workspace_path: str) -> dict[str, Any]:
        return self._request("GET", f"/api/2.0/workspace/get-status?path={workspace_path}")

    def mcp_request(self, server_url: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        req = urllib.request.Request(
            server_url,
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                for line in body.splitlines():
                    if line.startswith("data:"):
                        return json.loads(line[5:].strip())
                return json.loads(body)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MCP HTTP {err.code}: {body}") from err


def build_notebooks() -> dict[str, str]:
    return {
        "01_exec_kpi_framework": """# Databricks notebook source
# MAGIC %md
# MAGIC # Executive KPI Framework
# MAGIC
# MAGIC Use this notebook as the canonical KPI dictionary and logic spec for C-level reporting.

kpi_framework = {
    \"financial\": [
        \"Revenue growth (MoM, QoQ, YoY)\",
        \"Gross margin trend\",
        \"Cost-to-serve by segment\",
    ],
    \"operational\": [
        \"Incident volume trend\",
        \"SLA attainment\",
        \"Mean time to resolution\",
    ],
    \"customer\": [
        \"NPS trend\",
        \"Customer churn risk\",
        \"Top recurring customer pain points\",
    ],
    \"risk\": [
        \"High-severity incidents\",
        \"Regulatory exposure signals\",
        \"Control breach indicators\",
    ],
}

print(\"KPI dimensions loaded:\")
for pillar, metrics in kpi_framework.items():
    print(f\"- {pillar}: {len(metrics)} metrics\")
""",
        "02_exec_question_bank": """# Databricks notebook source
# MAGIC %md
# MAGIC # C-Level Question Bank
# MAGIC
# MAGIC Prompt bank for CEO, CFO, COO, and CRO style questions.

question_bank = {
    \"CEO\": [
        \"What are the top 3 business risks this month and their revenue impact?\",
        \"Which strategic accounts show early warning signals?\",
    ],
    \"CFO\": [
        \"How are incident trends affecting cost and margin?\",
        \"Which business units are over budget on service operations?\",
    ],
    \"COO\": [
        \"Where are SLA breaches concentrated and why?\",
        \"What operational bottlenecks are recurring quarter over quarter?\",
    ],
    \"CRO\": [
        \"What are the most material control and compliance risks by region?\",
        \"Which unresolved incidents have potential regulatory impact?\",
    ],
}

for role, prompts in question_bank.items():
    print(f\"\\n{role} prompts:\")
    for p in prompts:
        print(f\"- {p}\")
""",
        "03_exec_response_template": """# Databricks notebook source
# MAGIC %md
# MAGIC # Executive Response Template
# MAGIC
# MAGIC Expected answer shape for concise, decision-ready summaries.

def format_exec_response(summary: str, key_drivers: list[str], risks: list[str], actions: list[str]) -> str:
    lines = [
        \"Executive Summary:\",
        summary,
        \"\",
        \"Key Drivers:\",
    ]
    lines.extend([f\"- {d}\" for d in key_drivers])
    lines.append(\"\")
    lines.append(\"Risks to Watch:\")
    lines.extend([f\"- {r}\" for r in risks])
    lines.append(\"\")
    lines.append(\"Recommended Actions (30 days):\")
    lines.extend([f\"- {a}\" for a in actions])
    return \"\\n\".join(lines)

example = format_exec_response(
    summary=\"Incident volume increased 8% MoM, concentrated in two strategic accounts.\",
    key_drivers=[
        \"Two product modules account for 62% of critical incidents\",
        \"EMEA response time drifted above SLA by 11%\",
    ],
    risks=[
        \"Potential churn in top-10 account segment\",
        \"Regulatory response-time breach in one market\",
    ],
    actions=[
        \"Deploy tiger team on high-frequency defect cluster\",
        \"Rebalance on-call staffing for EMEA peak hours\",
    ],
)

print(example)
""",
    }


def verify_artifacts(client: DatabricksClient, workspace_dir: str, expected_paths: list[str]) -> None:
    listed = client.list_dir(workspace_dir)
    listed_paths = {obj.get("path") for obj in listed}

    missing = [p for p in expected_paths if p not in listed_paths]
    if missing:
        raise RuntimeError(f"Artifacts missing after import: {missing}")

    for artifact in expected_paths:
        status = client.get_status(artifact)
        if "object_type" not in status:
            raise RuntimeError(f"No object_type in status response for {artifact}: {status}")


def test_mcp(client: DatabricksClient, host: str, genie_space_id: str) -> tuple[bool, str]:
    mcp_url = f"{host}/api/2.0/mcp/genie/{genie_space_id}"

    init_result = client.mcp_request(
        mcp_url,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "artifact-provisioner", "version": "1.0"},
        },
    )
    if "error" in init_result:
        return False, f"initialize failed: {json.dumps(init_result['error'])}"

    tools_result = client.mcp_request(mcp_url, "tools/list")
    if "error" in tools_result:
        return False, f"tools/list failed: {json.dumps(tools_result['error'])}"

    tools = tools_result.get("result", {}).get("tools", [])
    return True, f"MCP test passed. Discovered {len(tools)} tool(s)."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-dir", default=DEFAULT_WORKSPACE_DIR)
    parser.add_argument("--host", default="")
    parser.add_argument("--genie-space-id", default="")
    parser.add_argument("--skip-mcp-test", action="store_true")
    args = parser.parse_args()

    env_values = load_env_file(Path(".env"))
    token = load_setting("DATABRICKS_TOKEN", env_values)
    host = (args.host or load_setting("DATABRICKS_HOST", env_values)).rstrip("/")
    genie_space_id = args.genie_space_id or load_setting("GENIE_SPACE_ID", env_values)

    if not token:
        raise RuntimeError("Missing DATABRICKS_TOKEN. Set env var or .env entry.")
    if not host:
        raise RuntimeError("Missing DATABRICKS_HOST. Set env var or .env entry.")
    if not genie_space_id and not args.skip_mcp_test:
        raise RuntimeError("Missing GENIE_SPACE_ID. Set env var/.env entry or pass --genie-space-id.")

    client = DatabricksClient(host=host, token=token)

    print(f"Using workspace host: {host}")
    print(f"Provisioning workspace artifacts under: {args.workspace_dir}")

    client.mkdirs(args.workspace_dir)

    notebooks = build_notebooks()
    artifact_paths: list[str] = []

    for name, source in notebooks.items():
        artifact_path = f"{args.workspace_dir}/{name}"
        client.import_notebook(artifact_path, source, language="PYTHON")
        artifact_paths.append(artifact_path)
        print(f"Created/updated: {artifact_path}")

    verify_artifacts(client, args.workspace_dir, artifact_paths)
    print("Artifact verification passed.")

    if args.skip_mcp_test:
        print("Skipped MCP test (--skip-mcp-test set).")
    else:
        ok, message = test_mcp(client, host, genie_space_id)
        if not ok:
            raise RuntimeError(message)
        print(message)

    print("Provisioning complete.")


if __name__ == "__main__":
    main()
