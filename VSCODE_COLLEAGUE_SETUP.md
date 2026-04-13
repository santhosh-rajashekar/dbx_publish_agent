# VS Code Setup Guide for Databricks Genie MCP

This guide helps colleagues set up and use the Databricks Genie MCP workflow from VS Code.

## 0. Quick Start In VS Code

1. Open this workspace in VS Code.
2. Create a local `.env` file from `.env.example` and set `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, and `GENIE_SPACE_ID`.
3. Run the task `Run MCP connectivity test`.
4. Open Copilot Chat and select the `c-level-databricks` agent profile.
5. Ask a scoped business question with metric, time range, and segment.

Question template:

- Metric: incidents, MTTR, RTO, cost
- Time range: last 12 months, QTD, YTD
- Segment: business unit, region, product line
- Output style: executive summary, table, recommended actions

Expected answer structure:

1. Executive Summary
2. Trend / Result Highlights
3. Risks / Caveats
4. 30-day Actions
5. Confidence Level

## 1. Prerequisites

- VS Code with GitHub Copilot Chat enabled.
- Python 3.12 or newer.
- Node.js installed (needed for MCP bridge tools in some clients).
- Access to the Databricks workspace and Genie space.
- A Databricks Personal Access Token (PAT) with required permissions.

## 2. Clone and Open

1. Clone this repository.
2. Open the repository folder in VS Code.
3. Ensure the Python interpreter points to your project environment.

## 3. Environment Variables

Set these in your local `.env` file before running tests/scripts:

- `DATABRICKS_HOST` (example: `https://adb-xxxx.x.azuredatabricks.net`)
- `DATABRICKS_TOKEN` (your PAT)
- `GENIE_SPACE_ID` (required)
- `AZURE_SUBSCRIPTION_ID` (optional)
- `AZURE_RESOURCE_GROUP` (optional)

### Example (PowerShell)

```powershell
$env:DATABRICKS_HOST="https://adb-xxxx.x.azuredatabricks.net"
$env:DATABRICKS_TOKEN="<your_pat>"
$env:GENIE_SPACE_ID="<your_genie_space_id>"
```

### Example (.env)

```dotenv
DATABRICKS_HOST=https://adb-xxxx.x.azuredatabricks.net
DATABRICKS_TOKEN=<your_pat>
GENIE_SPACE_ID=<your_genie_space_id>
AZURE_SUBSCRIPTION_ID=<your_subscription_id>
AZURE_RESOURCE_GROUP=<your_resource_group>
```

## 4. Required First Validation

Run the VS Code task:

- `Run MCP connectivity test`

Expected outcome:

1. `initialize` succeeds.
2. `tools/list` returns Genie tools.
3. test query is accepted by `query_space_*`.

If query status is in progress (`ASKING_AI` or `EXECUTING_QUERY`), that is expected. The MCP flow is asynchronous and requires polling (`poll_response_*`) until status is `COMPLETED`.

## 5. Daily Usage in VS Code

1. Open Copilot Chat in this workspace.
2. Use the dedicated C-level agent profile.
3. Ask business questions in natural language.
4. For best results, include scope in the prompt:
   - time range
   - business unit or product line
   - KPI focus (incidents, MTTR, RTO/RPO, uptime)

## 6. Response Pattern to Expect

- Initial response may indicate processing.
- Follow-up polling returns completed result.
- Final output usually includes:
  - generated SQL
  - result rows
  - summarized narrative

## 7. Troubleshooting

## Connectivity failures

- Verify `DATABRICKS_HOST` and `GENIE_SPACE_ID` are correct.
- Verify PAT is valid and not expired.
- Re-run `Run MCP connectivity test`.

## Slow responses

- Check SQL Warehouse warm state (cold starts add latency).
- Increase warehouse size/concurrency for demo windows.
- Use a dedicated warehouse for Genie workloads when possible.

## Windows command issues

If an MCP bridge command fails with path/quoting errors (for example around `Program Files`), use a no-space command path or explicit cmd wrapper according to client requirements.

## 8. Security Requirements

- Never commit PATs to source control.
- Use environment variables for secrets.
- Rotate PATs immediately if exposed in logs/screenshots.
- Avoid sharing raw logs that include Authorization headers.

## 9. Demo Checklist

1. Environment variables set.
2. MCP connectivity task passes.
3. Warehouse is warm.
4. One smoke-test question returns a completed answer.
5. PAT is rotated after external demos if it was exposed.

## 10. Recommended Smoke-Test Prompt

`What is the monthly trend of total incidents reported at Allianz?`
