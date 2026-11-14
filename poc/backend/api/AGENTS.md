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
| `POST` | `/{workflow_id}/execute` | Trigger execution of workflow steps with transparent background queue dispatching (`use_queue=True`), `force_rerun`, and SHA-256 deduplication. |
| `POST` | `/webhook/{webhook_token}` | Unauthenticated webhook endpoint triggering workflow runs via background queue with deduplication. |
| `GET` | `/executions` | List recent workflow executions with filtering by `workflow_id`, `department_id`, `status`, and `limit`. |
| `GET` | `/executions/{execution_id}` | Retrieve execution state, step progress, token counts, and cost breakdown. |
| `POST` | `/executions/{execution_id}/evaluate` | Maker-checker evaluation allowing humans/managers to approve, rate, and review runs. |

---

### 5. Agents, Tasks, Projects & Filesystem
* **Agents (`agents.py` mounted at `/api/v1/agents`)**: Scoped by `organization_id` and `department_id`. Endpoints: `GET /`, `POST /`, `GET /hierarchy`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`.
* **Tasks (`tasks.py` mounted at `/api/v1/tasks`)**: Manages agent execution lifecycle. Supports `use_queue: bool` and `priority: int` (1-10) for RabbitMQ distributed dispatching. Endpoints: `GET /`, `POST /`, `GET /{run_id}`, `DELETE /{run_id}`, `POST /{run_id}/resume`, `GET /{run_id}/subtasks`, `GET /{run_id}/tree`.
* **Distributed Queue & Broker (`poc/backend/queue/router.py` mounted at `/api/v1/queue`)**: Manages distributed task queues, health metrics, and DLQ. Endpoints: `GET /status`, `GET /dlq`, `POST /retry/{message_id}`, `POST /publish-test`.
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
## Playground API and scoped execution inspection
* `POST /api/v1/workflows/{workflow_id}/playground`: required JSON object body (workflow variables); returns HTTP 202 with WorkflowExecutionResponse and QUEUED status. Checks workflow scope, runtime tool-free capability (409 when unavailable), definition and configured agents (422), and agent organization (403). Missing workflows return 404. Always creates a fresh `PLAYGROUND` run with `pg_exec_` ID; no cache lookup. Hashes are namespaced separately from production. Executes via FastAPI BackgroundTasks on the same engine; exceptions persist FAILED with an error and completion time. This initial path is process-local and not durable across API restarts.
* `GET /api/v1/workflows/executions/{execution_id}` now checks workflow tenant/department scope and includes `step_runs` (persisted step IDs, status, input/output, tokens/cost, timestamps). WorkflowExecutionResponse defaults step_runs to an empty list for list/launch responses.
* `GET /api/v1/workflows/executions` filters records by authorized workflow scope. A non-admin with no authorized departments cannot inspect department workflows; inspection returns 403, foreign organizations return 404.

### Runtime diagnostics in execution detail
`GET /api/v1/workflows/executions/{execution_id}` enriches each step_runs entry with `events` (last 500 persisted task events), `error` (task error or null), and `task_status` (runtime enum value or null), joined through task_run_id after workflow scope checks. Missing/legacy task records return empty events/null metadata. The existing workflow_id list filter powers the per-workflow logs page; no new logs API route is introduced.

## Task origin and plugin refresh contracts
* `GET /api/v1/tasks/` accepts `execution_scope=all|office|workflow` (default all; invalid values return 422). Database filtering occurs before LIMIT, and merged live runtime records use the same origin classification. List responses include nullable workflow_execution_id and workflow_id. Origin includes direct step task IDs and recursive parent/root descendants; configured agent identity is unchanged.
* `GET /api/v1/skills/plugins/scan` accepts `refresh: bool=false`; true bypasses the existing Git tree scan-result cache. `_scan_git_repo_via_api(..., force_refresh=False)` retains the current tree-SHA lookup behavior unless refresh is requested. Empty source behavior remains unchanged.

## Workflow editing, lossless conversion and history
* WorkflowResponse adds `revision: int` (initial 1) to create/list/get/update/channel responses.
* `PUT /api/v1/workflows/{workflow_id}` accepts existing settings plus optional expected_revision (integer >=1) and change_summary (<=500 chars). It preserves omitted settings, accepts explicit null for nullable fields, rejects blank names and organization reassignment, and checks target department access. JSON/YAML definitions are checked for duplicate keys, unknown dependencies/flow endpoints and cycles. Unknown definition fields and metadata are preserved; workflow ID and original runner_agent_id remain stable. Conflicts return 409 and invalid definitions 400 without updating state/history. The endpoint uses engine.db for normal execution access consistently with WorkflowEngine.
* `GET /api/v1/workflows/{workflow_id}/revisions?limit=50&before_revision=N` returns newest-first revision snapshots with actor_id, actor_label, change_summary, changed_fields and created_at. limit is 1..100; before_revision is exclusive and >=1. The same workflow tenant/department scope applies; foreign organizations return 404. History is separate from execution logs.
* Creation records the requesting actor in v1. Channel binding add/remove records the actor and a summary, with expected current revision checked atomically. Canvas step removal uses the regular update endpoint and records a revision.
* `/convert-format` validates and serializes raw mappings with safe YAML, preserving extension fields rather than rebuilding a reduced parser representation. New workflow IDs are injected into the saved definition. Manual/webhook/playground execution hashes include the saved revision, preventing cache reuse after edits.

## Shared Workflow Assistant HTTP adapter
The service router lives in [workflow_assistant](../workflow_assistant/AGENTS.md), mounted with authentication at `/api/v1/workflow-assistant`. Routes: GET /context, GET /catalog?department_id, GET /proposal-schema, POST /validate, POST/GET /drafts, GET/PUT /drafts/{id}, GET /drafts/{id}/revisions. Strict inputs reject model-supplied organization/actor/provenance/execution parameters. Save validation errors return 422 unless save_blocked=true explicitly retains a non-executable proposal; current-user/department errors remain 401/403/404. Idempotency and optimistic version conflicts return 409. Existing workflow generation/execution routes remain separate; chat and MCP adapters are not delivered by this phase.

## Workflow Assistant model generation
Workflow Assistant adds POST /api/v1/workflow-assistant/generations (202, GenerationRequest, optional Idempotency-Key), GET /generations/{id}, POST /generations/{id}/cancel, POST /generations/{id}/save-draft ({save_blocked:false}). Context adds supports_generation. Creator-only chats reload current permissions; save uses authoritative stored output and captured draft revision. Exact DTOs/statuses are in ../workflow_assistant/AGENTS.md.

## Model-only YAML authoring and internal MCP
Workflow Assistant GET /context now includes authoring_models [{model_id,provider_id,name}]. POST /generations requires model_id/provider_id and rejects planner_agent_id; legacy stored jobs remain readable. GET /workflow-schema returns workflow_schema_version/schema/yaml_schema. POST /validate-yaml accepts {department_id,yaml_content} and returns proposal/validation/native artifact; malformed native YAML ->422 WORKFLOW_YAML_INVALID. Generation responses include tool_calls (name/time only); exact DTOs are in ../workflow_assistant/AGENTS.md. workflows.py delegates its existing graph validator to workflows.parser.validate_workflow_definition, preserving legacy extension fields.

The internal model reply uses validation_id for a canonical candidate stored through MCP; the HTTP generation result retains this ID for provenance. It is not a grant or a public lookup endpoint. The server resolves only candidates attached to the authenticated generation, verifies their hashes and revalidates current policy.

## Refactored master integration contracts
Workflow models now include revision/expected_revision/change_summary, payload_hash/is_deduplicated/message/step_runs. workflows_crud owns CRUD and GET /{workflow_id}/revisions; workflows_queries owns execution list/detail/evaluation; workflows_playground owns POST /{workflow_id}/playground; workflows_execution owns queued/manual/webhook dispatch. All execution reads enforce current and historical department plus exact tenant access. Queue publication failure marks the execution FAILED and returns 503. Static routes are composed before /{workflow_id}. Tasks accept use_queue and priority1–10, expose workflow origin, and list execution_scope=all|office|workflow. Queued tasks are persisted before publication, with failed dispatch marked FAILED. Plugin scan refresh=true bypasses the Git-tree cache. Masked MCP token placeholders are ignored; credentials remain organization scoped.

## Empty-path route composition correction (2026-10-30)
Agents, Tasks and Workflows facades use router_composition.compose_routers for their route-only child modules. Both empty-path and slash aliases are retained until router_registry mounts the aggregate under its nonempty /api/v1 domain prefix. Calling include_router(child) without a prefix at the facade stage rejects empty aliases with FastAPIError and caused these capabilities to register unavailable. Child modules must not define router-level lifecycle hooks/dependencies; per-route metadata and application authentication/availability guards remain applied by the final include. Isolated import diagnostics captured the exception without starting services or accessing the live database. No tests/build were run.

GET /api/v1/queue/status reports disconnected transport without depending on queue readiness; the queue-api descriptor guards module availability separately. Retry/publish operations still require queue dispatch availability and return503 when unavailable.

## Fine-grained GitHub PAT repository scoping (2026-10-31)
`POST /api/v1/mcp/discover-resources`, `GET /api/v1/skills/plugins/git-repos`, and `_find_git_token` strictly use the provided or tenant-stored token without falling back to or overriding with host `gh auth token`. When a Fine-Grained GitHub token (`github_pat_...`) is used, `/user/repos` results are filtered to explicitly scoped repositories (`private=true` or explicit `push`/`maintain`/`admin`/`triage` permissions) so unselected public repositories are excluded whenever scoped repositories exist.

## Execution method and direct API setup
`GET /api/v1/runtimes` (and trailing slash) and `POST /api/v1/runtimes/detect` include `direct_anthropic`, `direct_openai`, `direct_nvidia`, with configuration-only availability, missing-key/price diagnostics, and `config.model_id`. No key values are returned. `PUT /api/v1/runtimes/selection` adds optional `model_id` (<=200 chars), required as an explicit provider ID for direct mode; aliases/tiers/flag-like strings are rejected with 400. It saves `runtime_model_<provider_id>`, runtime_provider and runtime_setup_completed. JWT callers must be ORG_ADMIN (403 otherwise); legacy authenticated API-key/local access retains the existing host configuration path. A conflicting PLATFORM_RUNTIME_PROVIDER override returns 409 instead of pretending the saved default is effective. CLI selections remain compatible. `GET /api/v1/models` adds the configured direct model and labels its default accordingly; context_window=0 means unspecified, not a verified context limit. Detection performs no paid inference.

## Workflow Assistant route removal & provider-scoped models (2026-10-31)
The `/api/v1/workflow-assistant` router registration has been removed from `poc/backend/router_registry.py`.
`GET /api/v1/runtimes` and `PUT /api/v1/runtimes/selection` support `direct_nvidia`, `direct_anthropic`, `direct_openai`, and `direct_openrouter`, returning per-provider curated `models`, `model_id`, `has_api_key`, and `enabled` flags, and accepting optional `api_key`, `enabled_providers`, `provider_models`, and `provider_keys`.
`GET /api/v1/models` (with optional `?provider=<provider_id>`) dynamically returns only the models belonging to the active and enabled API provider(s) configured in Runtime Settings.

## Friendly workflow chat API (new, independent implementation)
The workflows router now composes workflow_chat.router. Endpoints under `/api/v1/workflows`:
- `GET /ai/context?department_id=...`: current writable departments, configured model/provider/cost source, optional approved catalog. Requires an active persisted organization user; ORG_ADMIN or current MANAGER/OPERATOR membership grants creation scope. Unavailable inference yields selection=null without fabricating models.
- `POST /ai/chat` (202): strict `{request_id,department_id,messages,previous_workflow?,locale=en|he}`. Request ID is 16–80 alphanumeric/underscore/hyphen characters; messages are 1–20 user/assistant items, 1–8000 chars each, <=40000 total, last=user. Previous workflow uses the strict reply workflow schema. Provider/model are captured from runtime settings, never client-selected. Same ID/body/owner is idempotent; changed body returns 409, private foreign IDs 404. One generating job per department; stale jobs expire after 180s. BackgroundTasks run bounded real inference; no synthetic reply.
- `GET /ai/chat/{job_id}`: creator/org/department-scoped job, current status/result/model/provider/error and created workflow ID only after CREATED. Generation expiry becomes FAILED.
- `POST /ai/chat/{job_id}/cancel`: changes GENERATING to CANCELLED; the inference loop checks cancellation and current rights.
- `POST /ai/chat/{job_id}/create`: requires a stored complete preview, rechecks current permissions/DAG/cron, and calls shared workflow creation with stable reserved workflow ID and initially_active=false. Replay returns the same workflow. Existing/moved/deleted workflows remain scope checked. No client-supplied edited definition is accepted by this endpoint. Creation provisions the usual dedicated runner; webhook is disabled and channel triggers are off. Activation remains separate.
`workflow_chat_models` rejects extra fields; model reply is `{message,workflow?}`. Workflow has name/description/steps/destination?/cron_expression?; each step has key/name/agent_id/prompt_template/depends_on/resources/timeout_seconds. A resource reference contains connector_id plus repository/channel_id/tool_name. Catalog reads connected organization connectors with active department grants and tool-level whitelist checks. Explicit configured repo/channel allowlists override legacy single defaults; no host credentials, live public-repository discovery or raw connector config is included. Unknown IDs are rejected. Resource constraints are carried into step params/instructions; prompt text is not an OS security boundary.
Jobs: GENERATING → READY/FAILED/CANCELLED; valid stored previews READY → CREATING → CREATED. Clarification replies remain READY with ready=false. Creation retries recover a stable workflow ID after an interrupted response. Config/schema/graph errors remain visible; permission failures do not create workflows. Prompt bound=160000 chars, inference timeout=120s, no automatic paid retries. Model costs/usage are persisted and API_KEY costs contribute to department spend even if publication loses a cancellation race. Background execution is process-local, not a durable queue or global spend reservation. Generic workflow creation remains compatible through persist_workflow; its default activation remains unchanged.

Workflow chat recovery: private job responses additionally include the stored request messages and previous_workflow, enabling refresh recovery without regenerating. These fields use the same creator/org/current-department checks as the result; no public listing or anonymous lookup is added.

Workflow chat candidate validation rejects step prompts containing the known authoring-only markers inactive preview / do not claim execution / you have no tools, both after generation and before creation. This prevents the draft planning boundary from leaking into executable instructions. Existing saved workflows are not rewritten.

## Explicit local production dispatch
POST /api/v1/workflows/{workflow_id}/execute adds background:bool=false. Existing use_queue=true still requires the broker and has no silent fallback. use_queue=false&background=true persists a QUEUED MANUAL execution and schedules the existing real workflow engine with that same execution ID through FastAPI BackgroundTasks; the response is immediate (HTTP200, existing WorkflowExecutionResponse). Tenant/department scope and revision-aware dedup still run before dispatch; engine permission, budget and MCP/runtime checks still apply. workflows_local_dispatch catches early background exceptions and marks still-active records FAILED. Process-local work is not durable across server restarts. use_queue=false&background=false preserves existing synchronous behavior. No automatic retry of external effects is introduced.

## Executable connector catalog and safe chat discovery
Workflow chat catalog now lists only implemented tools allowed by current department policy and adds connectors[].execution_supported plus agents[].connector_tools (connector ID→canonical tool names after explicit agent restrictions). Known unsupported catalog placeholders no longer imply runnable actions. Repository values are exact owner/name IDs; channel values are real Telegram numeric/@username or Slack channel IDs. Candidate validation additionally checks execution_supported, assigned agent tool access, explicit repository/channel references and granted delivery tools. GitHub get_repository_activity is available alongside individual read tools in the MCP installation catalog; no write tools are implemented by the governed executor.
ResourceDiscoveryRequest adds optional connector_id. POST /api/v1/mcp/discover-resources with provider=telegram requires a current ACTIVE persisted ORG_ADMIN in the JWT organization, binds saved credentials to that tenant's exact connector (or unambiguous tenant bot), and reads Telegram getUpdates(timeout=0,limit=100) without offset, no update acknowledgement/message sending/webhook removal. Response includes only chat IDs/titles and valid configured IDs, never message text/user content/bot credentials. Placeholder chats and implicit destination selection are removed. Webhook conflicts/no recent updates are reported; discovery is not an access grant. Multiple bots require an explicit connector or supplied unsaved configuration.
Slack discovery now returns only valid configured IDs from the current administrator's organization (and exact connector when supplied); no cross-tenant lookup or fabricated #general/#dev-team defaults remain. This is configuration inspection, not live Slack channel discovery. Other repository discovery contracts remain unchanged. No live discovery or external sends were performed by the agent.

WorkflowExecutionResponse adds nullable notification_error. Authenticated/scoped GET /api/v1/workflows/executions and /executions/{execution_id} project it from the frozen execution context. It reports blocked/failed optional delivery separately from the primary run status/error_message; a successful summary may have a delivery warning without claiming a message was sent. No connector credentials are exposed.

Manual channel test contract: POST /api/v1/mcp/test-channel-message accepts provider (telegram|slack), optional connector_id, exact channel_id and message (1..3500). It requires current persisted ACTIVE ORG_ADMIN with matching JWT tenant. Missing connector_id resolves only one tenant connector; ambiguity fails. Only CONNECTED, same-tenant/provider connectors and saved exact allowlisted destinations pass. Uses scoped_channels acknowledgement receipts (delivery, delivered_channel_id, provider_message_id), no alias fallback, redirect or automatic retry. Message audits hash content; no agent means no synthetic audit actor. Telegram discovery returns private first/last names where no title/username exists, and configured channel_labels as presentation only.

Manual channel-test errors now preserve fixed safe Telegram rejection hints from provider_http instead of only HTTP status; unknown descriptions remain generic. No automatic retry or target migration is performed.

Workflow chat ChatStep adds optional send_output_of (1..80-character source key).
It requires that source in depends_on and exactly one channel-only resource.
Native conversion emits params.channel_action for governed server delivery; this
field is excluded from the native step top level. Current catalog/grant checks
still apply and user-confirmed creation remains required.

Workflow chat catalog connectors add channel_labels mapping only currently authorized channel IDs to bounded configured display labels (<=200 chars, ID fallback). Native destination metadata carries channel_name from this map and preserves channel_id unchanged. Names do not affect authorization or transport.

Workflow chat catalog now includes organization-scoped configured plugin skills
(id = canonical source path/URI, key, name, plugin, bounded description). ChatStep
adds skills:string[] (default [], max20). Validation checks all IDs against the
current plugin catalog during generation and confirmed creation; native conversion
preserves per-step skills. Server-only channel actions reject analysis skills.
No skill contents or credentials are included in the model's authoring catalog.

Workflow chat adds ChatWorkflow.skills:string[] (default[], max20), the shared
selection for every AI step. ChatStep.skills remains accepted solely for existing
jobs/clients. Validation checks both against the current plugin catalog. Native
conversion deduplicates/promotes all legacy step skills into root skills and omits
per-step skills. Global skills are allowed alongside channel delivery actions,
which do not use a model or load these instructions.

## Explicit planned workflow runner
Workflow chat catalog agents includes reserved `__workflow_runner__`, named
Dedicated workflow runner, with provision_on_create=true. This is a provisioning
option, not a persisted/executing agent. Its connector_tools are exactly the current
department's catalog tool grants; it grants no new connector/resource access.
Ordinary same-org/department agents remain selectable; other workflow runners
remain excluded. Unknown model-generated IDs continue to fail validation.
On confirmed /ai/chat/{job_id}/create, native_definition maps only this reserved
ID to wf-agent-{new_workflow_id}; shared persist_workflow creates that real scoped
runner before saving the inactive workflow. Provisioning failure now returns503
instead of saving a workflow without its runner. Existing user/grant/resource
revalidation and idempotency checks remain. Generation with validation errors uses
a server-owned corrective message instead of a model's misleading ready claim.

Manual POST workflow creation also resolves explicit __workflow_runner__ step assignments to its own generated wf-agent-{workflow_id} before persistence/provisioning. It creates no arbitrary role-based agent from dropdown labels. Other agent API behavior is unchanged.

## Workflow settings and secrets (`workflows_settings.py`)
Composed into the workflows router. GET /{workflow_id}/settings (workflow scope) returns revision, validated settings (or defaults plus settings_error), secret metadata {name, kind, external_ref, created_by, updated_at}, can_manage, machine_sizes and max_allowed_hosts. PUT /{workflow_id}/settings {settings, expected_revision, change_summary?} saves a revision through db.update_workflow (409 on conflict, 400 on invalid input). PUT /{workflow_id}/secrets/{name} {value | external_ref} returns 400 on validation and 503 when PLATFORM_SECRETS_KEY or the ARN prefixes are unset. DELETE /{workflow_id}/secrets/{name} returns 204 or 404. Every mutation requires a current-DB ACTIVE ORG_ADMIN of the workflow org, or a MANAGER of its department, and writes audit_logs (workflow.settings.update / workflow.secret.set / workflow.secret.delete) without secret values.


## Workflow cost projections (2026-11-01)
Authorized GET /api/v1/workflows/executions and /executions/{id} add optional cost_summary to WorkflowExecutionResponse. workflow_costs.py reads step-linked task usage events after existing execution authorization, derives aggregate known/unknown/free/estimated/reported/no_usage state and reference_cost_usd without mutating historical rows. Detail step_runs additionally include cost_summary and session_cost_summary from the latest recorded session snapshot. Legacy positive cost remains estimated; zero with token usage and no pricing evidence is unavailable. Numeric total_cost_usd/cost_usd remain compatible accounting fields; clients must use cost_summary for display. No schema changes, session-store access, global session lookup or permission expansion. Usage events remain in scoped JSON exports. No runtime verification performed.


## AI-authored repository workspaces and required PR outcomes (2026-11-01)
ChatStep adds workspace:RepositoryWorkspace|null (connector_id,repository,ref?,mode read|write,pr_title?) and required_outcome:analysis|pull_request (default analysis). workflow_chat_workspace.py projects existing current department/agent workspace permissions into catalog connectors.workspace_operations and agents.workspace_operations[connector_id]. Only connected scoped GitHub repositories with credentials are candidates. open_pull_request requires explicit department permission; a wildcard grant is excluded exactly as in execution. Metadata registration does not grant access. Candidate validation rejects unavailable operations/repositories/agents, mixed workspace+resources/delivery, and PR outcomes without write workspaces. Native conversion writes params.workspace and params.required_outcome, keeps step mcp_servers empty, registers the workspace connector at root, and resolves planned runners as before. No permissions, external resources or saved workflows are automatically changed. Existing runtime authorization remains authoritative. No tests/provider/Docker calls executed.


Workflow chat catalog adds workspace_readiness {configured,errors,verification:configuration_only} from repo_sandbox.configuration_status. It checks POSIX/docker binary existence and pinned sandbox image syntax only, without daemon/network calls. Missing setup is shown as a warning; a saved inactive definition does not prove execution readiness. Workspace operation metadata is registered for permission discoverability even when not granted; it never becomes a callable model tool or an implicit grant. No runtime checks performed.


ChannelBindingDto.notify_mode accepts COMPLETION_ONLY (new default), START_AND_COMPLETE, EACH_STEP, NONE and legacy ON_COMPLETE/ON_FAILURE/ALWAYS at POST /api/v1/workflows/{id}/channel-binding. Chat Destination adds notify_mode:COMPLETION_ONLY|START_AND_COMPLETE|EACH_STEP|NONE (default COMPLETION_ONLY), serialized directly into metadata.channel_binding by native_definition. Progress updates are workflow configuration, not generated chat stages. Existing routes/auth/revision semantics remain unchanged. No runtime checks performed.

## Organization runtime configuration (2026-11-03)
GET /api/v1/runtimes[/], POST /api/v1/runtimes/detect and GET /api/v1/models now resolve only the authenticated organization's runtime settings/credential presence. GET /models returns [] without an organization provider key. PUT /api/v1/runtimes/selection retains provider_id/model_id/api_key/provider_keys/provider_models/enabled_providers but stores keys encrypted and settings scoped in one transaction; only direct_* providers are supported for organization execution. DELETE /api/v1/runtimes/credentials/{provider_id} revokes the caller organization's key and returns SetupStateResponse. Current DB ACTIVE user/org and ORG_ADMIN role govern writes; explicit org-bound service auth remains supported. Keys are write-only SecretStr; runtime routes replace validation errors with generic 422 to avoid echoing inputs. Invalid configuration is 400, unauthorized is 403, encrypted storage failure is sanitized 503. available/has_api_key is presence only, not live verification. Workflow chat selection receives the verified user's organization; generation reconstructs organization_id from its stored job. No client organization ID or global fallback. Full schema/migration: docs/organization-provider-credentials.md. No runtime verification.

## Workflow backend capability metadata
GET /api/v1/workflows/{id}/settings adds settings.execution_backend and execution_backends descriptors {id,name,transport,implemented,requires_container,supports_playground,supports_governed_connectors,credential_provider,unavailable_reason,verification=source_contract_only}. PUT retains current manager authorization/optimistic revision contracts, accepts known backend IDs and records execution_backend in workflow.settings.update audit. Pending backends are authorable but blocked at execution, never treated as installed/live-verified. No route or credential changes. See docs/execution-backends.md. No runtime verification.

Hosted backend descriptors now include configured:boolean, configuration_error:null|string and supports_session_resume:boolean alongside source implementation metadata. Claude read-only SDK support is opt-in and configuration-only diagnostics check Linux/flag/pinned image; no live readiness claim. Budget policy results can add reserved_usd distinct from current_spend_usd. No new public broker endpoint: hosted broker is private Unix HTTP only. No tests/startup/paid calls.

Saved workflow maintenance: user-requested repairs to missing runner reference and Telegram tool_name were recorded as revisions7/4 with full snapshots and configuration.repair audit metadata. This was data maintenance, not a route/schema change, activation or retry. See docs/workflow-repairs.md; runtime outcome remains unverified.

## Anthropic thread opt-in
GET /api/v1/runtimes includes providers[].config.message_threads_enabled (true only for direct_anthropic). PUT /api/v1/runtimes/selection accepts optional message_threads_enabled:boolean, persisted atomically as organization_runtime_settings key runtime_message_threads_enabled with values true/false; omission preserves the value. Existing current-DB ORG_ADMIN and credential/model validation remain mandatory. Default is disabled. No schema migration or API secrets returned.


## Evidence-backed plugin scan metadata (2026-11-05)
GET /api/v1/skills/plugins/scan retains request/auth/source behavior and adds optional
per-skill skill_connections:[{source,target,kind,conditional?,evidence:{path,line?,node_id?,
text,section?,revision?}}], connection_warnings:string[], and Git source_revision (tree SHA).
Kinds: handoff, conditional_handoff, declared_transition, reference. connected_skills remains
compatibility reference metadata, not authoritative execution flow. Projection lives in
plugins/connections.py; declared DAG files and immutable Git blobs are read by adapters.
There is no new route, execution, grant or credential handling. See plugin guide and
[the source audit](../../../docs/plugin-skill-flow-audit.md). Runtime checks were not run.


## Session department visibility (2026-11-05)
`organizations_auth._session_departments` projects `departments` in POST /auth/login,
POST /auth/org-register and GET /auth/me. Current DB ORG_ADMIN users receive all departments
inside their organization, with both id and department_id; real membership department_role
and joined_at are retained where present, without fabricated membership roles. Other roles
retain get_user_departments membership-only results. JWT departments claims continue to
contain actual memberships only. No memberships or grants are inserted during projection.
This fixes the header missing newly created departments: OrganizationPage already calls
refreshUserProfile after creation, but /auth/me previously returned only memberships.
No local tests/build/application execution performed.


## Tenant-wide endpoint hardening (2026-11-05)
All registered API modules now pass security.request_policy before endpoint effects and
security.response_policy before JSON release. Explicit endpoint-name rules are in
security/route_permissions.py; resource ownership/path/query/body references are server-owned,
not optional tenant hints. Roles and current memberships are reread from the DB. The full
route/role/ownership contracts are in ../../../docs/access-control-audit.md.

Login/profile/registration no longer claim orphaned records. Inactive login status is disclosed
only after password verification. Skills/templates create safe tenant-prefixed IDs and ownership
records; instantiation stamps real organization/department, caps capacity per tenant and omits
inherited live child-agent IDs. Connector configuration reads redact credentials; updates retain
masked saved values. Department grants stamp current actor and tenant; tools must match connector.
Workflow settings/secret can_manage uses the same capped current membership policy. Filesystem
browse defaults to own shared tenant root and never Home/cwd, refuses symlink escapes and foreign
roots, and exposes only the tenant quick-access location. Native OS picker is denied. Plugin
reads stay inside the configured source; non-admin scans cannot persist query source changes.
No local test/build/typecheck/startup/provider operations were performed for verification.

Auth profile/login/onboarding department lists are filtered to the current organization even if legacy membership rows are inconsistent. Project/detail and task agent lookup prefer persisted DB records over stale global config copies.

All active recognized-role department members may create workflows, use AI context/chat/recovery/cancel/confirmed creation and generate definitions. Catalog grants, current membership and draft ownership still apply. Shared persistence forces newly authored workflows inactive below effective department MANAGER; activation/edit/delete remain management and execution remains operation permissions. No local runtime verification performed.


workflow_chat ChatStep adds optional human_approval {source_step,connector_id,channel_id,kind:report|pull_requests,merge_after_approval:false,expires_hours:1..72(default24)}. Catalog exposes human_approval readiness, connector tool_capabilities/server_operations and per-agent server_operations; missing tools/grants/public URL are proposal errors. Native human gates are terminal. GET /api/v1/workflows/executions/{execution_id}/approval returns null or scoped gate/report/subjects/receipts; POST same path {approve:boolean} requires a current signed-in department manager/admin, atomically claims PENDING->RESOLVING and records the actual user, then runs server-only resolution. No submitted responder identity, tokenized approval URL or model-callable merge action. WAITING_APPROVAL is active for execute/webhook dedup.


AI-13 source/HTTP baseline is docs/architecture/connector-governance-contract.md. Its v1 entities are proposals for later tickets, not newly registered endpoints. Current catalog execution_supported is configuration-only; CONNECTED/test_connector is not verified provider connectivity, and saved trigger_enabled does not establish an inbound listener. API-only audit exercises real registered guards without application lifespan or external actions.

## AI-16 governance API
governance.py: GET /api/v1/governance/capabilities; GET/PUT /organization/policy (admin); GET/PUT /departments/{department_id}/policy and GET /policy/history (current department manager/admin); GET /departments/{department_id}/catalog and POST /decisions (department readers). Strict PolicyUpdate includes expected_revision; stale409, invalid422, manager expansion403, hidden scope404. DecisionRequest accepts no actor/approval/frozen authority and returns non_executable:true. Managers append deny/require_approval only; admin may expand within legacy ceiling. AI context/proposal validation uses per-operation/resource and agent capability_resources, including repository-specific merge checks. Full models/storage/bounds: docs/architecture/capability-policy-v1.md.

AI-16 destination regression: workflow chat validates channel-only Destination objects without repository/tool fields, then checks exact channel delivery policy and notification-agent permissions. API-only saved-preview tests cover allowed and denied channels on the same connector, with zero executions or sends.

## AI-17 safe editor options
GET /api/v1/governance/organization/policy and GET /departments/{department_id}/policy add resource_options: [{capability_id,connector_id,connector_name,resource_type,resource_ids}]. Only implemented descriptors and exact configured own-org resources appear; department options additionally require active department connector grants. Typed-policy-denied resources remain selectable for editing; options do not grant authority. No configuration/credential object is serialized. Existing role guards, PUT/CAS and history shapes remain unchanged. Contracts: docs/design/capability-policy-editor.md.

## AI-18 consolidated API reference
../../../docs/architecture/p01-governance-api.md records all governance routes, model bounds/defaults, PolicyRecord/resource_options/catalog/decision shapes, reasons, status codes, CAS and exact additive SQLite keys. Decision probes use the current caller even with execution_id; frozen policy is server-loaded, and the result is not step authority or a complete execution replay. Do not add client actor/approved/frozen authority fields, infer grants from options or bypass current DB checks. See ../../../docs/architecture/p01-policy-algebra.md for roles/algebra and ../../../docs/governance-policy-guide.md for operations. No executable contract changed in AI-18.

## AI-19 shared governance projection
Existing /api/v1/governance/capabilities adds descriptor requires_capabilities for aggregate/narrow PR reads, correct write effects and strict head/body/event schemas. /decisions can return DEPENDENT_CAPABILITY_DENIED; catalog/AI authoring prune missing or denied dependencies and keep writes behind explicit grants. Existing approval reads expose richer audit receipts through unchanged scoped receipts JSON; no new execution/approval endpoint or caller authority field. Exact adapter/audit contracts: ../../../docs/github-pr-governance.md.

## AI-20 PR scopes and evidence
AI-20: authorized GET /api/v1/workflows/executions/{execution_id} adds step_runs[].pr_evidence, a bounded (32 per task) historical audit projection from workflow_pr_evidence.py. It intersects task/agent/connector organization, permits fixed GitHub PR operations, and allowlists scalar result fields, PR head/base identities, bounded blockers/reviewer summaries, audit ID/status/timestamps. Draft-PR receipts map pull_request_number/commit to pull_number/head_sha. No arguments, bodies, patches, arbitrary URLs/configuration or credentials are released. Existing execution scope checks precede projection; no execution or grant changes. Missing/deleted/malformed audit dependencies are omitted, not reconstructed. Approval endpoint and merge receipts remain unchanged.

Checks-only diagnostics preserve files_included=false and explicitly remain incomplete approval proof even when their CI facts pass; the UI never displays a full-review readiness badge for that result. API contracts assert this field survives the safe projection.

## AI-22 channel bindings

Under `/api/v1/governance/channel-bindings`, GET lists one exact org/department scope with `after`/`limit` pagination. POST creates a Telegram/Slack binding from `department_id?`, `connector_id`, `provider`, `channel_id` and `uses?`. PUT `/{binding_id}/uses` replaces the three independent booleans with `expected_revision`; DELETE `/{binding_id}` uses query `expected_revision`. Supply query `department_id` for department reads/updates/deletes. Current signed-in org admins own writes; authorized members can read their selected department. See [the contract](../../../docs/channel-bindings.md) for scope, strict schemas, response fields and errors.

AI-23 opens department binding list reads to authorized members of the selected department. Organization reads and all mutations keep their existing administrator requirements.

GET /api/v1/governance/channel-bindings/catalog returns providers (label, configurable_uses, runtime_supported_uses) and scoped connectors (id, name, provider, status, channel_ids). Only org admins receive selectable configured channel IDs. POST requires a currently configured exact ID.

Channel binding catalog connectors also return channel_labels keyed by selectable channel ID. Blank, non-string and unconfigured labels are excluded.

GET channel bindings adds nullable channel_name from the exact binding connector and channel ID within the current organization. It does not expose other configured labels to members.

AI-25 external-identities exposes personal list, issue, status, confirm and unlink plus admin secret rotation. Exact routes and schemas are in [external identities](../../../docs/external-identities.md).

AI-26 adds GET /api/v1/governance/external-identities/connectors (configured, authorized {id,name,provider} records), and GET/DELETE /departments/{department_id}/links[/{link_id}] under the same base. Management GET accepts after (idl_ cursor) and limit (1–100, default 50), and returns {links,next_after}; each row contains id, connector_id, provider, subject, created_at (Unix seconds), member_name and can_revoke. DELETE returns 204 and requires current manager authority and exact row scope.

AI-28 POST /api/v1/channel-ingress/{connector_id} accepts verified Telegram/Slack events. Org-admin GET /api/v1/governance/channel-ingress/{connector_id}/diagnostics and POST /test provide bounded diagnostics and optional explicit TLS checks. See [verified channel ingress](../../../docs/channel-ingress.md).

Ingress diagnostics recognize provider IDs from INGRESS_ADAPTERS rather than a separate API allowlist.

Channel catalog provider descriptors include ingress_supported, derived from the trusted ingress adapter registry.

AI-31 exposes GET and PUT /api/v1/workflows/{workflow_id}/channel-trigger and POST /preview below that path. Reads are scoped to the saved workflow. Managers save a strict rule or null using expected_revision and simulate a rule against its authorized department binding. Preview returns matched and parameters and has no execution side effects.

Workflow create rejects reserved trigger metadata and normal definition edits preserve the saved rule and principal. Only the dedicated trigger route changes these fields.

GET /api/v1/workflows/dag-approvals?department_id= returns a scoped pending inbox of up to 50 items and a next_after cursor. POST /dag-approvals/{approval_id}/decision?department_id= accepts strict {approve:boolean}, rechecks a personal eligible voter, and returns the decision status.

Verified Telegram callback_query updates on POST /api/v1/channel-ingress/{connector_id} apply a shared DAG decision and return a generic answerCallbackQuery acknowledgment. Raw callback bodies are not stored.

Workflow chat exposes interactive_approval_bindings for eligible Telegram department bindings. A matching report-only approval compiles to params.dag_approval with channel_binding_id, summary_step and timeout_seconds. Pull-request approval retains its pinned terminal gate.

Workflow chat can select an exact interactive Telegram binding for pinned PR gates even without a public dashboard origin. GitHub review and merge grant validation remains required.

Workflow chat approval readiness distinguishes configured (any supported path) from dashboard_configured. Interactive availability is checked for the selected exact connector and channel.
Workflow chat accepts a strict reply object or JSON document with optional Markdown fences and a leading think block. Rejected replies log bounded validation error types without model output.
Workflow chat persists reply-validation diagnostics in workflow_builder_jobs.result_json for FAILED jobs. The owner-scoped job response exposes diagnostics separately from result, including the stage, up to ten issue paths/codes, total issue count and token usage. Raw replies, validation inputs, and unknown field names are excluded.
Workflow chat accepts discover_open_prs_author and open_pr_source for governed PR discovery and review. It validates the explicit dependency, matching connector/repository and exact tool declarations before compiling both fields into step params.
GitHub connector configuration accepts department_default_tools as an explicit list of implemented operations. Omission gives departments the supported GitHub operation set; an empty list disables inheritance. Existing department MCP access routes replace the inherited list or revoke it for one department. Tenant repository scope, execution authority and server-side approval remain required.
POST /departments/{dept_id}/mcp-access accepts inherit_github_defaults=true to restore enabled same-organization GitHub defaults. Access responses expose inherited for effective grants.
Telegram connectors support configuration.ingress_mode webhook (default) or polling. In polling mode ingress diagnostics do not require a public HTTPS origin. The authenticated local worker rechecks the current connector mode and credentials before dispatching updates through the shared validation path.

AI-6: GET /api/v1/skills/plugins/config, /scan and /content accept optional department_id. PUT /api/v1/skills/plugins/settings (also /config) accepts department_id and source_mode=git with git_repo, or source_mode=inherit. Config includes inherited and source_department_id. Department creation under /api/v1/organizations/departments accepts parent_department_id within the same organization. AI-7: custom skills use organization-scoped SQLite CRUD, require project authorization when applicable, and return 409 for a conflicting create. Shared system skills are read-only. AI-10: GET /api/v1/workflows/metrics/reliability accepts window=24h|7d|30d (default 7d) and returns UTC trend buckets and per-workflow terminal outcome counts, rates, average duration/cost, latest failed run, failure categories and recurring-pattern suggestions. Playground executions are excluded.

Department plugin writes infer git only when git_repo is supplied. Clearing an override requires explicit source_mode=inherit. Reliability uses UTC filters and buckets, converting legacy local ISO timestamps.
