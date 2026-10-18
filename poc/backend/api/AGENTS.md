# AGENTS.md - REST API Routers Architecture & Contracts

## 1. Module Identity & Mission
The **REST API Layer** (`poc/backend/api/`) exposes the public and authenticated HTTP surface of the AI Agents Platform. Operating under FastAPI with Pydantic v2 schemas, it enforces enterprise multi-tenancy, department budget guardrails, Model Context Protocol (MCP) integrations, zero-clone plugin scanning, and DAG workflow execution.

---

## 2. Router Directory & Endpoint Specifications

### 1. Multi-Tenant Organizations & Governance (`organizations.py`)
Mounted at `/api/v1`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/auth/org-register` | Register a new tenant organization and its initial `ORG_ADMIN` user. Enforces domain matching and returns signed HS256 JWT. |
| `POST` | `/auth/login` | Authenticate an enterprise user via email/password. Returns scoped JWT token containing `org_id` and `departments`. |
| `GET` | `/auth/me` | Fetch active user profile, organization, and department roles. Includes **self-healing** database recovery and triggers `claim_orphaned_records`. |
| `POST` | `/organizations` | Create an enterprise organization. |
| `GET` | `/organizations` | List all organizations. |
| `GET` | `/organizations/{org_id}` | Retrieve specific organization configuration. |
| `PUT` | `/organizations/{org_id}` | Update organization settings, including plugin source modes (`plugins_source_mode`, `plugins_local_path`, `plugins_git_repo`). |
| `POST` | `/departments` | Create a department with `monthly_budget_usd`, alert thresholds (`alert_threshold_pct`), and `budget_action="HARD_STOP"`. |
| `GET` | `/departments` | List departments (scoped to user's organization). |
| `GET` | `/departments/{dept_id}` | Retrieve department details and budget spend metrics. |
| `PUT` | `/departments/{dept_id}` | Update department budgets, alert thresholds, or name. |
| `DELETE` | `/departments/{dept_id}` | Remove department. |
| `POST` | `/departments/{dept_id}/members/bulk-invite` | Bulk invite users by email with corporate domain validation and single-use JIT onboarding tokens. |
| `GET` | `/departments/{dept_id}/members` | List all users assigned to a department. |
| `DELETE` | `/departments/{dept_id}/members/{user_id}` | Remove a user from a department. |
| `POST` | `/invitations/accept` | Accept an invitation token to onboard or attach to an organization/department. |
| `GET` | `/organizations/{org_id}/users` | List all users registered within an organization. |
| `GET` | `/departments/{dept_id}/mcp-access` | List active MCP connector grants and tool whitelists for a department. |
| `GET` | `/departments/{dept_id}/mcp-access/{connector_id}` | Get specific MCP grant details. |
| `DELETE` | `/departments/{dept_id}/mcp-access/{connector_id}` | Revoke department's access to an MCP connector. |
| `GET` | `/departments/{dept_id}/mcp-access/{connector_id}/check` | Verify whether a department is permitted to execute a specific MCP tool. |

---

### 2. Model Context Protocol Hub (`mcp.py`)
Mounted at `/api/v1/mcp`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/catalog` | Returns pre-configured standard MCP servers (`CATALOG_MCP_SERVERS`: GitHub, Trello, Telegram, Slack, Postgres, Brave Search, Filesystem). |
| `GET` | `/connectors` | List installed connectors with sensitive credentials masked. |
| `GET` | `/connectors/{connector_id}` | Retrieve connector configuration and operational status. |
| `POST` | `/connectors` | Install and configure a new MCP connector. |
| `PUT` | `/connectors/{connector_id}` | Update connector configuration or multi-channel arrays (`allowed_channels`). |
| `DELETE` | `/connectors/{connector_id}` | Delete connector. |
| `POST` | `/connectors/{connector_id}/test` | Perform live connection handshake to verify external credentials. |
| `GET` | `/connectors/{connector_id}/tools` | List all tools discovered and exposed by the connector. |
| `GET` | `/permissions` | List agent- and department-level MCP permission grants. |
| `POST` | `/permissions/grant` | Grant tool permissions to an agent or department. |
| `POST` | `/permissions/revoke` | Revoke tool permissions. |
| `POST` | `/discover-resources` | **Live Remote Discovery**: Queries GitHub/GitLab REST APIs with provided PAT to discover all accessible public and private repositories without disk cloning. |
| `POST` | `/test-channel-message` | **Live Channel Dispatch**: Sends a test verification message to configured Slack or Telegram channels listed in `allowed_channels`. |

---

### 3. Skills & Plugins Hub (`skills.py`)
Mounted at `/api/v1/skills`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | List all skills available in the active workspace. |
| `POST` | `/` | Create a custom reusable skill. |
| `GET` | `/{skill_id}` | Retrieve skill details and code implementation. |
| `PUT` | `/{skill_id}` | Update skill definition or parameters. |
| `DELETE` | `/{skill_id}` | Remove custom skill. |
| `GET` | `/plugins/config` | Get organization's plugin configuration (`source_mode`, `local_path`, `git_repo`). |
| `PUT` | `/plugins/config` | Update plugin configuration between `Local Directory` and `Git Repository` modes. |
| `GET` | `/plugins/git-repos` | Discover repositories available for plugin scanning. |
| `GET` | `/plugins/scan` | **Strict Plugin Scanner**: Evaluates configured `source_mode`. If path is empty (via "Clear Path" / "Clear Repo"), cleanly returns 0 skills without fallback. In Git mode, performs 100% in-memory scanning via GitHub REST API (`_scan_git_repo_via_api`, cached in `_GIT_TREE_SCAN_CACHE`). |
| `GET` | `/plugins/content` | Retrieve raw manifest or skill definition content from remote or local storage. |

---

### 4. Workflows Engine & Playbooks (`workflows.py`)
Mounted at `/api/v1/workflows`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/generate` | **AI Playbook Generator**: Generates complete multi-step agentic workflows from natural language prompts. |
| `POST` | `/convert-format` | Bidirectional converter translating between YAML and JSON playbook definitions. |
| `POST` | `/` | Register a new workflow. Automatically provisions a dedicated background execution runner agent (`wf-agent-{id}`). |
| `GET` | `/` | List all workflows scoped to organization or department. |
| `GET` | `/{workflow_id}` | Retrieve workflow definition, steps, and channel bindings. |
| `PUT` | `/{workflow_id}` | Update workflow YAML/JSON definition or parameters. |
| `DELETE` | `/{workflow_id}` | Delete workflow and unbind associated runner agents. |
| `POST` | `/{workflow_id}/channel-binding` | Bind workflow execution updates to Telegram or Slack notification channels. |
| `DELETE` | `/{workflow_id}/channel-binding` | Remove channel binding. |
| `POST` | `/{workflow_id}/execute` | Trigger execution of workflow steps following topological DAG ordering. |
| `POST` | `/webhook/{webhook_token}` | Unauthenticated webhook endpoint triggering workflow runs via external webhooks. |
| `GET` | `/executions/{execution_id}` | Retrieve execution state, step progress, token counts, and cost breakdown. |
| `POST` | `/executions/{execution_id}/evaluate` | Maker-checker evaluation allowing humans/managers to approve, rate, and review runs. |

---

### 5. Agents, Tasks, Projects & Filesystem
* **Agents (`agents.py` mounted at `/api/v1/agents`)**: Scoped by `organization_id` and `department_id`. Endpoints: `GET /`, `POST /`, `GET /hierarchy`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`.
* **Tasks (`tasks.py` mounted at `/api/v1/tasks`)**: Manages agent execution lifecycle. Endpoints: `GET /`, `POST /`, `GET /{run_id}`, `DELETE /{run_id}`, `POST /{run_id}/resume`, `GET /{run_id}/subtasks`, `GET /{run_id}/tree`.
* **Projects (`projects.py` mounted at `/api/v1/projects`)**: Scoped to organizations. Endpoints: `GET /`, `POST /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`.
* **Filesystem (`filesystem.py` mounted at `/api/v1/fs`)**: Local directory navigation and project type detection. Endpoints: `GET /browse`, `POST /pick-folder`.

---

## 3. Invariant Rules & Guardrails

1. **Strict Organization Scoping**: Routers must extract `org_id` from claims via `get_authorized_scope(request, db_manager)` and prevent cross-tenant access.
2. **Department Budget Pre-Flight**: Workflows and task dispatches must verify that the target department has not exceeded its monthly budget cap under `HARD_STOP`.
3. **Empty Source Safety**: In `skills.py`, if the plugin path or repository URL is empty, never scan parent or root directories—return empty list immediately.
4. **Tool Permission Masking**: Sensitive connector tokens and private keys must never be returned in plaintext over the API.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any route, request model, response schema, or business rule in `poc/backend/api/` is modified, added, or removed, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.
