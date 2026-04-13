Databricks workspace provisioning details are environment-specific.
Store these values in a local `.env` file (recommended):

- DATABRICKS_HOST=https://adb-xxxx.x.azuredatabricks.net
- GENIE_SPACE_ID=<your_genie_space_id>
- DATABRICKS_TOKEN=<your_pat>

Optional Azure context values:
- AZURE_SUBSCRIPTION_ID=<your_subscription_id>
- AZURE_RESOURCE_GROUP=<your_resource_group>

The MCP endpoint format is:
https://<databricks-host>/api/2.0/mcp/genie/<genie-space-id>

This is the blog on Medium which has the details on how to configure the services within Azure and Databricks
https://medium.com/@ryan-bates/microsoft-teams-meets-databricks-genie-api-a-complete-setup-guide-81f629ace634

Follow the instructions in this Microsoft Documentation to provision the resources needed within Azure and Databricks so that Agents & MCP server can be used outside Azure and Databricsk workspace
Link to Microsoft documentation 
https://learn.microsoft.com/en-us/azure/databricks/generative-ai/agent-framework/teams-agent

Reference GitHub repo which is doing similar things is here
https://github.com/nkvuong/DatabricksGenieBOT
Additionally, this includes the logic of generating the zip folder which needs to be imported in Team apps

You can consider my token from az login to provision the resource needed, and make sure i have access to those resources.

Databricks PAT
<store securely — use environment variable DATABRICKS_TOKEN, never commit to git>

---

## Automated Provisioning For C-Level Agent Artifacts

This repository now includes automation to generate and validate Databricks workspace artifacts for executive Q&A use cases.

### 1. Set environment variables

Use a local `.env` file (see `.env.example`):

DATABRICKS_HOST=https://adb-xxxx.x.azuredatabricks.net
DATABRICKS_TOKEN=<your_pat>
GENIE_SPACE_ID=<your_genie_space_id>

Optional:
AZURE_SUBSCRIPTION_ID=<your_subscription_id>
AZURE_RESOURCE_GROUP=<your_resource_group>

### 2. Run provisioning

python provision_clevel_artifacts.py

Optional flags:
- --workspace-dir /Shared/C_Level_Agent
- --host https://adb-xxxx.x.azuredatabricks.net
- --genie-space-id <your_genie_space_id>
- --skip-mcp-test

### 3. What gets created in Databricks workspace

Under /Shared/C_Level_Agent:
- 01_exec_kpi_framework
- 02_exec_question_bank
- 03_exec_response_template

### 4. Validation performed

- Confirms each artifact exists with workspace/get-status.
- Runs MCP initialize and tools/list against Genie MCP endpoint.

### 5. Workspace chat agent definition

A dedicated VS Code workspace agent is added at:
.github/agents/c-level-databricks.agent.md

Use this agent profile to answer executive-level questions in a decision-ready format.