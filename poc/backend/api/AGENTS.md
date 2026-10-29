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

## Modular source ownership
The original agents.py, tasks.py, organizations.py, mcp.py, skills.py and workflows.py retain compatibility exports and router composition. Endpoint bodies now belong to sibling modules; no HTTP paths, methods or request/response models are intentionally changed.

| Prefix | Responsibilities |
|---|---|
| agents_ | models/provider validation; mapping/scope; queries; commands |
| tasks_ | models; response mapping; CRUD/cancel; SSE/logs; delegation/trees |
| organizations_ | models; organization/department CRUD/budget; governance; auth; members/invitations |
| mcp_ | catalog; models; connectors; permissions; resource discovery; channels |
| skills_ | models; metadata; scoped credentials; remote tree/blob scanner/cache; plugin settings; source scan/content; CRUD |
| workflows_ | models; scope/mapping; generation/conversion; CRUD; channels; executions/webhooks/evaluations |

Route modules own routers and explicitly import shared models/helpers. Facades assemble subrouters; static plugin routes precede dynamic skill IDs. Metadata parsing and Git scanning do not import router facades or the dependency container. Compatibility exports reference the sole implementation. Source files stay at most 500 physical lines. No tests/build/lint/startup were run.

### Scoped credential and execution access

Organization-scoped plugin discovery uses only that organization's connector credentials. `_find_git_token(db, org_id)` never falls back to all-organizations connectors or host `gh` credentials when `org_id` is supplied. Unscoped local/API-key legacy requests retain the prior host-token discovery path. A scoped organization ID that no longer resolves returns HTTP 404 rather than selecting another organization's plugin settings.

GET `/api/v1/workflows/executions/{execution_id}` and POST `/api/v1/workflows/executions/{execution_id}/evaluate` inject the current Request and authorize the execution through its parent workflow. A scoped tenant must exactly match the workflow organization; missing parent or mismatched tenant returns 404. Non-admin scoped callers need membership in both the workflow's current department and the execution's recorded department when those are set, including denial for an empty authorized-department set. Existing workflow scope checks also apply. Evaluation creates no row until authorization succeeds. Legacy unscoped/API-key access retains the existing authorization mode. Response payloads and HTTP methods are unchanged.

### Reviewed behavioral corrections
Task GET collection/detail use an optional live runtime and continue serving persisted authorized data when runtime is unavailable. Workflow execution responses share one mapping helper. Manual execution scope lookup uses engine.db. GET /api/v1/workflows/executions/{execution_id} and POST /api/v1/workflows/executions/{execution_id}/evaluate now authorize parent workflow tenant and both current/historical department membership; scoped empty membership cannot bypass a department gate.

Skill discovery's reusable implementation lives in poc/plugins. Org-scoped credential lookup cannot fall back to all-org connectors or host gh auth. GET /skills/plugins/content (under /api/v1) revalidates GitHub content under current credentials and restricts local paths to the current configured source root. It does not return globally cached private remote content. MCP POST /api/v1/mcp/test-channel-message uses the shared channel adapter: 503 missing connector; 400 delivery/configuration failure; success/delivery=delivered only after provider acknowledgement. No new schema is introduced.

Compatibility router facades bootstrap the single legacy import bridge before domain exports, preserving direct package imports. Audit uses relative container/security imports, avoiding a second backend dependency namespace. Task SSE callbacks marshal messages onto the request event loop via call_soon_threadsafe and a bounded queue. Stored logs/chat history and monitoring remain readable with an unavailable inference runtime.

Capability guards treat persisted DISABLED states as unavailable as well as current disabled configuration. This does not implement hot enabling or uninstalling capabilities.
