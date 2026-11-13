# AGENTS.md - Root AI Agents Platform Architecture & Directory Index

[AI-22 channel registry](docs/channel-bindings.md) adds tenant-scoped Telegram/Slack configuration, independent use flags, and audited administrator changes. Verified ingress, identity and runtime use remain separate stages.

## 1. Platform Identity & Architectural Mission
The **AI Agents Platform** is an enterprise multi-tenant autonomous agent orchestration and governance platform. It blends agent hierarchy management, visual DAG workflow execution, real-time collaboration war rooms, scheduled background cron execution, and a virtual pixel office with enterprise multi-tenancy, per-department monthly spending limits, and tool-level Model Context Protocol (MCP) governance.

---

## 2. Platform Architecture Overview

```
                                  [ Enterprise Organization ]
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
    [ Department A (Budget Cap) ]                                   [ Department B (Budget Cap) ]
               │                                                               │
    ┌──────────┴──────────┐                                         ┌──────────┴──────────┐
    ▼                     ▼                                         ▼                     ▼
[ Members / Roles ] [ Autonomous Agents ]                       [ Members / Roles ] [ Autonomous Agents ]
(ORG_ADMIN,          (Hierarchies,                               (ORG_ADMIN,          (Hierarchies,
 MANAGER,             Dedicated `wf-agent-{id}`)                  MANAGER,             Dedicated `wf-agent-{id}`)
 OPERATOR, MEMBER)                                                OPERATOR, MEMBER)
    │                     │                                         │                     │
    └──────────┬──────────┘                                         └──────────┬──────────┘
               │                                                               │
               ▼                                                               ▼
    [ Department MCP Access ] ──── (Tool-Level Whitelisting) ──── [ MCP Hub & Servers ]
```

### Core Architecture Pillars
1. **Multi-Tenant Enterprise Hierarchy**:
   * **Organizations**: Root tenant domain with separate administrative control, plugin configuration (`plugins_source_mode`, `plugins_local_path`, `plugins_git_repo`), and member directories.
   * **Departments**: Logical operational units with monthly budget limits (`monthly_budget_usd`), alert thresholds (`alert_threshold_pct`), and `HARD_STOP` policy enforcement.
   * **Members & Roles**: Enterprise RBAC hierarchy (`ORG_ADMIN` ➔ `MANAGER` ➔ `OPERATOR` ➔ `MEMBER`) governing system administration, task approval, and workflow execution.
   * **Autonomous Agents**: Org- and department-scoped AI workers organized into reporting chains (`parent_id`, `allowed_child_ids`) with specialized skills and tool access.
2. **Model Context Protocol (MCP) Hub**:
   * Pre-configured connector catalog (`CATALOG_MCP_SERVERS`: GitHub, Trello, Telegram, Slack, PostgreSQL, Brave Search, Filesystem).
   * Live remote repository discovery (`/api/v1/mcp/discover-resources`) via GitHub/GitLab personal access tokens across public and private repositories without disk cloning.
   * Multi-channel destination arrays (`allowed_channels`) for Telegram chats and Slack channels with live verification dispatch (`/api/v1/mcp/test-channel-message`).
   * Department MCP governance (`department_mcp_access`) enforcing granular tool whitelisting and blocking unapproved tool invocations.
3. **Plugins & Skills Hub**:
   * Strict separation between **Local Directory Mode** and **Git Repository Mode**.
   * Optional empty paths support ("Clear Path" / "Clear Repo") that safely return 0 plugins without falling back to unintended system folders.
   * 100% in-memory zero-clone GitHub REST API scanner (`_scan_git_repo_via_api`) that parses remote repository trees and blobs into plugin skill definitions.
4. **Workflows Execution Engine**:
   * Declarative YAML/JSON playbooks with bidirectional format conversion (`/api/v1/workflows/convert-format`).
   * AI-powered natural language playbook generator (`/api/v1/workflows/generate`).
   * Dedicated **Workflows Hub** (`/workflows` under `OPERATIONS` in `AppSidebar`).
   * Automated provisioning of dedicated execution runner agents (`wf-agent-{id}`).
   * RabbitMQ distributed queue dispatching (`platform.workflows.execution`) with SHA-256 payload deduplication, smart caching, and Concurrency group serialization.
   * Topological DAG execution, parallel multi-agent stages, conditional triggers, maker-checker human evaluations, and multi-channel notification bindings.
5. **Modern Dashboard & UI Toolkit**:
   * `OrganizationPage` (`/organization` under `ORGANIZATION & GOVERNANCE` in `AppSidebar`).
   * Reusable `Robotic` component kit (`RoboticHeader`, `RoboticCard`, `RoboticButton`, `RoboticBadge`, etc.).
   * Curated unified `MODEL_CATALOG` across Anthropic, OpenAI, Google Gemini, and Local Ollama.
   * Complete English (`en.ts`) and Hebrew (`he.ts`) internationalization with RTL support.

---

## 3. Master Index of Directory Documentation

### Backend & Service Guides
* [**Root Guide**](CLAUDE.md): Platform overview, verification commands, and operational rules.
* [**Root Architecture**](AGENTS.md): Monorepo architectural map, system invariants, and master documentation index.
* [**Backend Core**](poc/backend/AGENTS.md): FastAPI service architecture, lifespan startup, and dependency injection.
* [**Backend Guidelines**](poc/backend/CLAUDE.md): Backend development standards, test requirements, and conventions.
* [**REST API Routers**](poc/backend/api/AGENTS.md): Complete guide to all backend REST API routes, models, and endpoints.
* [**Security & Hardening**](poc/backend/security/AGENTS.md): HS256 JWT, PBKDF2 hashing, RateLimiterMiddleware (2000 req/min), tenant scoping.
* [**Capability Governance**](poc/governance/AGENTS.md): Versioned policies, exact resources, effective catalogs and repeated current/frozen authorization.
* [**Workflows Engine**](poc/workflows/AGENTS.md): WorkflowEngine, WorkflowParser, SandboxManager, DAG execution, and budgets.
* [**Hosted Claude SDK**](poc/runtime/claude_hosted/AGENTS.md): Isolated read-only SDK worker, private credential broker and request budgets.
* [**Runtime Abstraction**](poc/runtime/AGENTS.md): RuntimeAdapter protocol, model tiers, and curated `MODEL_CATALOG`.
* [**Orchestration & Hierarchy**](poc/orchestration/AGENTS.md): Multi-agent task trees, supervisor chain resolution, and department MCP checks.
* [**Agent-to-Agent Messaging**](poc/backend/messages/AGENTS.md): Peer communication, structured message types, and thread tracking.
* [**Multi-Agent Teams**](poc/backend/teams/AGENTS.md): Dynamic agent squads, missions, and deliverable synthesis.
* [**Project Shared Memory**](poc/backend/memory/AGENTS.md): ADRs, conventions, insights, lessons, and dynamic prompt injection.
* [**Interactive Chat**](poc/backend/chat/AGENTS.md): Agent mini-chat drawer, blocker resolution, and streaming output.
* [**Scheduler & Cron**](poc/backend/scheduler/AGENTS.md): Background cron polling loop, croniter forecasting, and scheduled tasks.
* [**Events & Streaming Bus**](poc/backend/events/AGENTS.md): In-memory EventBus pub/sub, SQLite event store, and persistent SSE stream.
* [**Approvals & HITL**](poc/backend/approvals/AGENTS.md): Human-in-the-loop permission requests, supervisor escalation, and dual-channel Telegram/Slack ChatOps callbacks.
* [**Distributed Queues**](poc/backend/queue/AGENTS.md): RabbitMQ AMQP message broker, priority task queues (1-10), durable queues, and dead-letter exchanges (DLX).
* [**Database & Postgres RLS**](poc/backend/db/AGENTS.md): Enterprise PostgreSQL schema with kernel-level Row-Level Security (RLS) tenant isolation.
* [**War Room Deliberation**](poc/backend/war_room/AGENTS.md): Multi-agent deliberation councils, debate rounds, consensus synthesis.

### Frontend & UI Guides
* [**Frontend Core**](poc/dashboard/AGENTS.md): React 18, Vite, Ant Design, TypeScript, pixel canvas integration.
* [**Frontend Guidelines**](poc/dashboard/CLAUDE.md): Build verification, component standards, strict TypeScript typing.
* [**UI Component Library**](poc/dashboard/src/components/AGENTS.md): Standardized `Robotic` UI component kit and layouts.
* [**UI Pages & Routes**](poc/dashboard/src/pages/AGENTS.md): Application route pages (Organization, Workflows, MCP, War Room, Office).
* [**UI Context & State**](poc/dashboard/src/context/AGENTS.md): React context providers (AuthContext, OfficeContext, NotificationContext).
* [**UI Custom Hooks**](poc/dashboard/src/hooks/AGENTS.md): Custom hooks (useOfficeEvents, usePermissions, useLocalStorage).
* [**UI Internationalization**](poc/dashboard/src/i18n/AGENTS.md): English (`en.ts`) and Hebrew (`he.ts`) translations, RTL handling.
* [**Pixel Canvas Engine**](poc/dashboard/src/canvas/AGENTS.md): Virtual pixel office canvas, agent sprites, desk coordinates.

---

## 4. Platform Invariant Rules & Guardrails

1. **Zero Mocks Invariant**: All automated integration tests run against real SQLite databases and real FastAPI instances.
2. **Provider-Agnostic Intelligence**: Orchestration and APIs depend on the `RuntimeAdapter` protocol and `ModelPolicyResolver` tiers rather than vendor-specific model strings.
3. **Resumable Execution**: Every agent run captures `session_id` allowing seamless continuation via `resume_task` without loss of execution history.
4. **Self-Healing Persistence**: Database connections automatically recreate directories and schema if the database file is removed at runtime (`poc/persistence.py`).
5. **Multi-Tier Clarification**: Ambiguous tasks invoke `ask_supervisor` (Tier 1: Shared Memory ➔ Tier 2: Manager ➔ Tier 3: Human Operator) and never falsely conclude as `COMPLETED`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **MANDATORY POLICY FOR ALL DEVELOPERS AND AGENTS**:
> Whenever ANY code, logic, endpoint, database schema, orchestration flow, or UI component/page/state/i18n is created, modified, or deleted, you **MUST** update the corresponding directory's `AGENTS.md` (and `CLAUDE.md` where applicable) within the **SAME task/commit**.
>
> * **No Out-of-Sync Code**: Submitting code modifications without corresponding updates to the relevant `AGENTS.md` files is strictly prohibited.
> * **Precise Technical Contracts**: Document exact routes, request/response models, database columns, enum values, and state transition rules.
> * **Master Directory Registration**: If a new submodule or directory is created with an `AGENTS.md`, immediately register its link in this root table of contents.

## Modular refactor source policy
Owned source files must remain at most 500 physical lines, including comments and blank lines. Split by responsibility and preserve public contracts. Third-party dependencies and generated build outputs are excluded. See [refactor roadmap](docs/refactor-roadmap.md) and [SQLite storage components](poc/storage/AGENTS.md), which owns composed repositories, records, connections and the legacy persistence facade. Runtime verification is not authorized in the current task.

## Refactor implementation index
* [Plugin discovery](poc/plugins/AGENTS.md): HTTP-independent metadata, local and Git adapters.
* [External channel adapters](poc/integrations/AGENTS.md): acknowledged Telegram/Slack delivery, no simulated success.
* [Test source organization](poc/tests/AGENTS.md): existing cases/fixtures split by responsibility; not executed.
* [Implementation and code review ledger](docs/refactor-implementation.md): ownership, source evidence, intentional corrections and unverified runtime requirements.

Demo registration is implemented once in poc/demo_data.py and imported by both explicit demo/setup entry points. No demo registration was executed during this refactor.
## Internal Workflow Playground (2026-10-24)
`POST /api/v1/workflows/{workflow_id}/playground` runs the existing DAG with fresh tool-free model inference. Runs use `PLAYGROUND`, `pg_exec_` execution IDs, `pg_task_` task IDs, and a separate deduplication hash namespace. No channel notifications, automatic reviewer tasks, supervisor escalation, or production completion callbacks run. This is a prompt/data exercise, not a full container security boundary or live integration test. See workflows and runtime guides. Contract tests: `poc/tests/test_workflow_playground.py` use real SQLite and FastAPI; run with `--noconftest` to avoid the shared default-database reset fixture.

`DatabaseManager.update_workflow_execution` accepts `sandbox_path` so pre-created QUEUED execution records capture their workspace when execution starts.

Per-workflow run diagnostics are available at `/workflows/:workflowId/logs?execution=<executionId>`, using scoped execution details and persisted runtime events. The Workflows table exposes a Logs link per workflow.

## Workflow/office execution visibility and catalog caching
Workflow task origin is resolved through workflow_step_runs and task parent/root lineage, without changing shared agent definitions or adding schema columns. Office and Live Flow request office-scoped task/activity snapshots and ignore workflow-tagged SSE events; the global Tasks view still shows all runs. See backend API/events and dashboard guides. Plugins use a bounded session-memory client cache with explicit invalidation and manual refresh; the application shell uses independent navigation/content scrolling.

## Workflow editing and revision history
Existing workflows can be edited in the shared visual/YAML builder and inspected through History. SQLite workflows.revision starts at 1; workflow_revisions stores full configuration snapshots and actor/change metadata. Each effective update appends a revision in the same BEGIN IMMEDIATE transaction; expected_revision provides optimistic concurrency. Existing records receive one Legacy baseline; earlier edits cannot be reconstructed. See backend API and workflow guides. Execution deduplication includes the saved revision so edits cannot reuse outputs from an older definition.

## Shared workflow authoring foundation
The protected `/api/v1/workflow-assistant` service reads current database user/membership/role policy, returns a sanitized organization/department resource catalog, validates strict proposals and stores non-executable drafts separately from workflows. Invalid proposals return structured errors; explicitly opted-in blocked proposals remain authoring records, never active workflows. Draft revisions/idempotency and current-policy revalidation are transactional. Chat generation and internal MCP authoring are implemented; external OAuth/MCP installation, publication and activation remain future work. Details and schema are in the module guide.

## Workflow Assistant model generation
Workflow Assistant phase two adds /workflow-assistant chat and isolated asynchronous model generation; its backend contract is documented in poc/backend/workflow_assistant/AGENTS.md. Configured runtime model/provider routing is reused without agent tasks or Office events; the internal MCP tool inventory is limited to catalog/schema/YAML validation. Draft save remains explicit and versioned; External MCP login/transport and workflow activation remain future work.

## Model-only YAML authoring and internal MCP
The Workflow Assistant now selects model_id/provider_id directly, uses an internal process-bound MCP server (catalog/schema/YAML validation only), and emits inactive native workflow YAML. Canonical governed schema: [Workflow authoring schema](poc/workflows/workflow-authoring.schema.yaml), generated from workflows.authoring_schema.WorkflowDocument. Execution agents remain per-step assignments; no planning agent is selected or persisted. The external installable OAuth MCP server remains future work.

The model returns a generation-scoped validation_id for a server-stored YAML candidate instead of regenerating the document after validation; current permissions and candidate integrity are rechecked before presenting/saving.

## Master merge composition (2026-10-29)
The refactor now includes master 523913e. Workflow revision/history, assistant/internal MCP, playground, queue, Office task-origin scoping and plugin cache remain available through extracted modules. backend/queue_lifecycle owns independent broker/worker startup; backend/workflow_wiring injects policy/output and optional human-approval delivery into workflow execution. No tests/build/application were executed during integration.

## Direct HTTP API providers and provider-scoped models (2026-10-31)
Runtime execution now uses Direct HTTP API calls (`runtime.direct_worker` across `direct_nvidia`, `direct_anthropic`, `direct_openai`, and `direct_openrouter`) instead of spawning the `claude` CLI binary. `RuntimeSetupModal` allows configuring API providers, API keys, and per-provider default models, and `GET /api/v1/models` dynamically returns only the models belonging to the configured/enabled provider(s).

## Workflow Assistant full removal (2026-10-31)
All Workflow Assistant modules, routes, and schemas (`poc/backend/workflow_assistant/`, `poc/runtime/authoring.py`, `poc/workflows/authoring_schema.py`, `poc/workflows/workflow-authoring.schema.yaml`, `poc/dashboard/src/pages/WorkflowAssistant.tsx`, `poc/dashboard/src/services/assistantApi.ts`, `poc/dashboard/src/types/assistant.ts`, `assistant.*` i18n keys, `workflow_assistant_*` SQLite tables, and `poc/tests/test_workflow_assistant*.py`) have been completely removed so all workflow creation and AI generation are consolidated in `/workflows`.

## Friendly workflow creation chat (2026-10-31)
The new workflow chat lives inside the Workflows hub (Create with AI), independently of the removed Workflow Assistant. Backend contracts, policy and strict reply models live in backend/api/workflow_chat*.py; model-only transport lives in runtime/workflow_chat.py. The configured model receives only current department-authorized resource IDs (repositories/channels/tools/agents). Human-confirmed creation revalidates the stored preview and provisions an inactive workflow through shared creation logic. See the [REST API guide](poc/backend/api/AGENTS.md) and [chat implementation notes](docs/workflow-chat.md). The removed assistant, internal MCP transport and schema are not restored. Runtime verification remains unauthorized.

Workflow chat recovery uses a private workflowChat query ID to restore stored conversation/results after refresh. Polling HTTP success is distinct from job completion; transient reconnect errors clear on success. See docs/workflow-chat.md.

Manual workflow execution now offers explicit local-server background dispatch alongside RabbitMQ dispatch. The /execute API adds background=false; use_queue=false&background=true creates a real queued record and invokes the same governed workflow engine without a broker. It is process-local, not durable, and supplies no additional MCP tools.

## Governed connector execution (2026-10-31)
Production workflow steps now use server-owned tool scopes for GitHub.com read operations and exact-ID Telegram/Slack sends through Direct API workers. Each actual call intersects its frozen step resources with current tenant/department/agent permissions, user status, budget and run lifetime. Connector-backed workflows (including analysis steps and reviews) have no shell/file/delegation tools; Playground and workflow chat receive no live connectors. Successful audited receipts are required for completion. The known exact legacy preview sentence is removed from production step input without rewriting saved workflow revisions. See [connector execution](docs/connector-execution.md) and integrations/runtime/workflow guides. No tests, live connector/model calls or message sends were executed.

Optional completion delivery is separate from required workflow work: invalid Telegram/Slack targets are blocked and surfaced as notification_error warnings, while authorized data steps can continue. Explicit channel-send steps remain required and fail closed.

Explicit workflow channel delivery uses params.channel_action (send_channel_message, connector_id, channel_id, source_step) and the governed tool executor rather than model-selected calls. Chat proposals expose send_output_of. See workflow/API guides; Playground performs no sends.

AI workflow chat now catalogs current organization plugin skills, validates and preserves ChatStep.skills, and shows selected skills in preview. Workflow execution resolves full skill instructions within the organization source, without global skill-cache fallback. See plugin/API/workflow guides.

Workflow Skills is now a single shared selection inherited by every AI step. Legacy step skills are promoted/deduplicated; deterministic delivery actions do not load skills. AI chat and the visual builder save shared root skills. See workflow/API/dashboard component guides.

Workflow AI chat exposes an explicit planned dedicated-runner option, materialized only during confirmed creation. It does not require an Office agent or reuse other workflow runners. Current department/resource grants still govern all steps; unknown IDs are rejected.

Local API launcher poc/start_api.py passes the repository-root .env to Uvicorn when present and defers application import until after environment loading. JWT_SECRET_KEY remains mandatory outside explicit dev mode; local keys belong only in ignored .env, never source control. No server startup was executed.

## Provider-visible reasoning logs (2026-11-01)
Direct API runs persist reasoning_summary events per completed model response, separate from final answers, with explicit not_returned status. Workflow Logs renders these through StepEventTimeline. Known Claude families request thinking; OpenAI reasoning families use stateless Responses with private continuation replay; compatible provider visible reasoning excludes encrypted fields. See runtime/component guides. No live token streaming or runtime verification performed.


## Explicit workflow/session pricing (2026-11-01)
Direct API calls now emit per-call usage/pricing provenance and run/session cumulative summaries. Private session ledgers survive resume; forks start a new spend ledger. Workflow list/detail exposes cost_summary plus per-step session totals without a schema migration. UI distinguishes confirmed free, estimated, provider-reported and unavailable prices; optional configured reference estimates are separate from charged costs. NVIDIA fixed hosted prototyping endpoints use documented free pricing, not missing-rate zero. Legacy unpriced usage stays unknown. See runtime/API/dashboard guides. No tests/build/startup/provider calls performed.


AI workflow chat now supports governed repository workspaces and explicit required PR outcomes. Current write grants are exposed separately from read-only tools; wildcard grants cannot publish. Declared PR completion requires a backend receipt; connector models return explicit completed/blocked final outcomes. Static pinned-image preflight runs before workflow steps. Existing workflow/grants were not changed or rerun. See runtime/API/integration/workflow guides. No runtime verification performed.


Visual workflow editing now supports governed repository read/write workspaces and required draft-PR outcomes, alongside the AI authoring path. Authorized catalog choices and configuration-only sandbox readiness are shared across step editors; no per-step requests, implicit write grants or execution. Pinned proxy setup is checked during preflight when network access is configured. No tests/build/typecheck/startup/Docker or external actions performed.


Workflow authoring is generic and follows the current user request: changes, deliverables, acceptance criteria, dependencies and requested notifications. No version-bump defaults, release policies or fixed notification sequence are imposed. Execution inspects real files and repository instructions, preserves unrelated work and clarifies material missing requirements. Changes sharing a checkout remain in one workspace step because separate steps use independent clones; dependencies do not transfer uncommitted files. Requested PRs use write workspaces with required PR receipts and remain drafts. Notifications report actual exposed milestones and returned URLs. Workspace repository references stay separate from connector resources. This supersedes the earlier version-bump-specific guidance. No saved workflow/grants were modified and no tests/build/typecheck/startup/model calls were performed.


Channel action configuration now requires exactly one matching step mcp_servers connector and authorized_resources destination/tool (send_message or post_chat_message), in addition to its explicit source dependency. Workflow execution preflight checks every channel action before any steps, preventing a malformed final notification from being discovered only after a PR is published. The saved Core plugin patch PR workflow notify_done scope was repaired with an immutable configuration revision; historical failed execution status/PR receipts were retained and nothing was retried. No tests/build/startup/provider calls or messages were performed. Repository workspaces still use per-step shallow clones cleaned up afterward; a shared Git-object cache is not implemented by this repair.


Repository workspaces now reuse a backend-only persistent Git object cache, scoped by tenant/connector/repository, with current remote-ref refresh and independent per-run object/filesystem copies. Locking, lazy TTL/LRU retention and oversized-entry eviction are owned by integrations/repo_cache.py. Cache provenance is recorded in existing workspace/audit JSON. No schema changes or cached authorization. See integrations/workflow guides. No tests or live operations performed.


Workflow progress notifications are now metadata.channel_binding configuration: COMPLETION_ONLY, START_AND_COMPLETE, EACH_STEP, NONE, with legacy mode compatibility. The engine sends actual lifecycle updates through governed optional delivery, with independent deterministic event audit claims and no model calls or notification DAG stages. Latest core-plugin workflow migrated to one work step plus EACH_STEP binding (revision3); no execution/messages/tests performed. See workflow/integration/API/dashboard guides.

## Organization-owned model credentials (2026-11-03)
Runtime setup, model discovery, normal/Playground task execution and workflow creation chat now use organization-scoped provider settings and AES-GCM encrypted keys. No global/environment/FCC credential fallback is used for organization execution. Rotation/revocation is checked before each worker HTTP request; in-flight calls cannot be recalled. See [credential contracts and migration](docs/organization-provider-credentials.md), storage/runtime/API guides. Existing organizations must re-enter their own keys with PLATFORM_SECRETS_KEY configured. No runtime verification performed.

## Execution backend foundation (2026-11-03)
Workflow settings now separate execution_backend from model/provider: direct_api (existing), claude_code (planned Agent SDK transport), codex_cli and antigravity_cli. Step params.execution_backend overrides workflow settings. Known pending engines are authorable but blocked at whole-DAG preflight and runtime admission with no fallback; UI marks them unavailable. No CLI/SDK runtime has been activated. See [backend contracts and milestones](docs/execution-backends.md). No runtime verification performed.

The local `uv run python poc/start_api.py` launcher passes the absolute repository-root `.env` path to Uvicorn and defers application import until environment loading. This includes JWT_SECRET_KEY; shell environment values retain precedence. Direct Uvicorn invocations must provide their own environment or --env-file. No startup or tests were performed.

## Hosted Claude Agent SDK read-only slice (2026-11-03)
claude_code now has an opt-in source integration for read-only repository analysis. SDK/CLI runs inside a restricted container; a relay and private Unix socket reach the host credential/policy/budget broker. Native Linux/local Docker, pinned SDK image and explicit flag are required. Only Read/Glob/Grep; no shell/writes/PRs/connectors/secrets/resume. Separate durable hosted request reservations are included in budget checks, without claiming atomic reservations for existing Direct API calls. Disabled by default; no runtime verification or environment changes. See [hosting module](poc/runtime/claude_hosted/AGENTS.md) and [deployment/limitations](docs/claude-hosted.md).

## Saved workflow configuration repairs (2026-11-03)
Two inactive saved workflows were repaired by explicit user request with atomic revision/audit entries: t-skills activity uses its existing workflow-owned runner (revision7); PR-review Telegram resource declares its already-authorized send_message tool (revision4). No permissions expanded, histories rewritten, workflows activated/retried, PRs or messages sent. Docker startup cause remains unresolved pending permitted diagnostics. See docs/workflow-repairs.md.

By later explicit exception, read-only Docker inspection and one disposable cached-image sleep-0 diagnostic container were authorized. The minimal sandbox startup probe passed (exit0); no workflow/model/test/message execution occurred. This does not authorize subsequent runtime verification or establish the old failure cause. See docs/workflow-repairs.md.

## Connector completion schema and format recovery
Governed Direct API connector runs now expose a server-only platform_workflow_finish schema tool, require strict status/output/blocker envelopes and permit one formatting-only model pass with all connector tools removed. Current policy/required successful receipts remain mandatory; blocked/malformed outcomes never become implicit success. Sanitized bounded completion_validation diagnostics are checkpointed and shown in Workflow Logs. No historical run/config changed or retried. See docs/connector-completion.md. No tests/build/model calls executed.

## Repository CI and image publishing
[GitHub automation](.github/AGENTS.md) documents PR checks, gated GHCR image publishing, and metadata-only generic PR labeling. Deployment and branch protection are not configured. CI starts with an isolated contract subset, not the full backend suite. No local runtime verification performed.

## Initial CI failure repair
CI now selects only six contract files present on master. Dashboard Department declares optional department_id (existing API/hydration alias), grouped model filtering narrows value access, and Telegram tag titles use native spans. No checks disabled; no local runtime verification.

CI regression fixtures for event replay and missing MCP grants now supply tenant identity and configured subjects before asserting the intended policy behavior. Production security is unchanged; GitHub checks are the verification environment.

## PR CI synchronization
The organization-credentials/runtime branch incorporates master CI workflows and type/fixture repairs. Documentation-only merge conflicts retain both branch contracts and automation guidance. PR checks require a conflict-free merge; labels use metadata-only pull_request_target and can run during conflicts.

## Hardened CI coverage
[GitHub automation](.github/AGENTS.md) defines isolated core/security/runtime test groups, PR container builds, named frontend checks, immutable Action pins, weekly reviewed dependency updates and the CI required aggregate. Publishing requires CI success. Private-repository plan restrictions still prevent enforcing merge protection; no deployment/automatic merge is enabled. GitHub-only verification preserves local runtime restrictions.

## Repository-wide CI hardening
[GitHub automation](.github/AGENTS.md) defines core/security/runtime backend groups, frontend checks, PR-only Docker build checks and CI required aggregation. External Actions are pinned to immutable SHAs and updated via weekly Dependabot PRs. Master selects 11 existing backend contract files; PR #18 adds five further contracts with its implementation. No feature branch implementation is required for master CI. Private-plan merge enforcement remains unavailable.

## Anthropic Message Threads opt-in
Direct Anthropic API sessions support organization-enabled beta create/continue with private transcript-backed recovery and session leases. Default disabled; no SDK/backend routing change, streaming or prompt caching. See docs/anthropic-message-threads.md and runtime/API/UI guides. No tests/build/startup/model calls performed.

## Frontend logic regression suite
[Dashboard logic tests](poc/dashboard/tests/AGENTS.md) documents direct Node22 tests for workflow editing, settings/secret validation, cost display, connector resource projection, shared skills, cache races, partial loading, model labels and office activity/coordinates. The standalone frontend PR contains no organization-runtime implementation. Existing master Actions discover all *.test.mjs files. No external API keys or provider calls.

## Unified repository CI
ci.yml now owns tests, PR/manual build-only validation and gated main/master/v* image publishing; images.yml is removed to avoid running tests twice per master push. One image plan owns the component matrix. Registry write access remains exclusive to the trusted publishing job. Manual runs default to build-only; publishing requires explicit opt-in on a supported ref. PR labels remain a separate privileged metadata-only workflow.

## PR #18 master synchronization (2026-11-05)
Documentation conflicts retain organization-scoped Anthropic Message Threads contracts and master frontend regression/unified-CI guidance. The unified workflow keeps the branch-specific 16-file backend suite and all frontend tests. No feature was activated; local runtime verification remains unperformed.

## Generic Connection Canvas Diagram for Organization Workflows & Skills/Plugins (2026-11-03)
`poc/dashboard/src/components/common/ConnectionCanvas/` (`ConnectionCanvasDiagram.tsx`, `ConnectionCanvasNodeCard.tsx`, `connectionCanvasTypes.ts`) provides a generic, domain-agnostic pan-and-zoom connection canvas with strict text-overflow containment (`ContainedTag`, `wordBreak: 'break-word'`, `WebkitLineClamp`). It powers both the **Workflows Canvas** tab in `OrganizationPage.tsx` / `OrgHierarchyModal.tsx` (`OrgWorkflowsCanvasTab.tsx`) and the **Skills & Plugins Canvas** tab in `SkillsCatalogTabs.tsx` (`PluginsConnectionCanvas.tsx`).

## Generic Connection Canvas & Multi-Stage Plugin Skill Flow (2026-11-03)
`poc/dashboard/src/components/common/ConnectionCanvas/` provides a domain-agnostic connection canvas engine with zero-re-render GPU pan/zoom (`translate3d` + `requestAnimationFrame`), memoized native HTML/CSS node cards (`ConnectionCanvasNodeCard`), per-group expand/collapse, multi-stage horizontal columns (`useStageColumnsLayout`), and interactive upstream/downstream hover highlighting. Mounted in `/organization` (`OrgWorkflowsCanvasTab`) for Organization ➔ Department ➔ Workflow connections and in `/skills` (`PluginsConnectionCanvas` + `pluginsFlowModel.ts` + `poc/plugins/packages.py:_enrich_skill_connections`) under the single **Skills & Plugins Canvas** tab to visualize multi-stage skill pipelines (e.g., `core` plugin routing ➔ discovery/research ➔ PRD/design ➔ architecture/review ➔ implementation ➔ QA/governance gates).


## Evidence-backed plugin skill canvas (2026-11-05)
The plugin canvas separates explicit/conditional instruction handoffs, declared lifecycle
transitions and optional ordinary references, each with source evidence. Strict package
selection clears prior focus and its pending reveals. The source audit of the configured
Git repository and limitations are in [Plugin skill flow audit](docs/plugin-skill-flow-audit.md);
projection/scanner contracts are in the plugin and dashboard component guides. No local
runtime verification performed; no plugin instructions were edited or executed.


## Tenant and role enforcement audit (2026-11-05)
[Access-control audit and role matrix](docs/access-control-audit.md) records the explicit
route inventory, current-database identity/membership checks, selected-department scope,
collection/stream filtering, credential redaction and guarded tenant workspaces. New endpoint
names fail closed until registered in backend/security/route_permissions.py. Organization
admins never acquire platform-wide access. Legacy global queue/native picker/ChatOps approval
operations are restricted as documented. Explicit isolated test data registration is owned
by demo_data.setup_access_lab, delegated to storage/access_lab.py and invoked only by
create_access_lab.py --apply. This authorized data setup does not authorize tests/startup.

The two isolated Access Lab organizations were explicitly registered by user request (marker
10da4d25): Engineering/Finance/Operations and13 role/edge-case accounts each. No existing records,
model keys, live sends or executions were changed/created. See the access-control audit.


## Governed PR review and terminal human approval
New read tools list_open_pull_requests and get_pull_request_review expose bounded PR identity/diffs/checks/reviews with incomplete evidence blocking readiness. AI authors explicit terminal human_approval steps; approvals persist WAITING_APPROVAL and are resolved in Workflow Logs by authenticated managers/admins. Optional server-only SHA-pinned squash merges require explicit merge_pull_request grants (wildcards denied), fresh evidence/current authority, and durable per-PR receipts. Telegram/Slack deliver authenticated links; bot callbacks remain disabled. See docs/workflow-pr-approvals.md. No saved workflows/grants/provider keys changed; no runtime/live actions performed.


## AI-13 generic connector governance baseline (2026-11-06)
[Shared contract and source audit](docs/architecture/connector-governance-contract.md) distinguishes implemented, partial and missing capabilities across identity, action/resource policy, adapters, channels, triggers, approvals and receipts. It is a proposed provider-neutral contract, not new executable APIs/schema. [API audit evidence](docs/architecture/ai-13-api-audit.md) records isolated HTTP verification. By explicit user authorization on November6, local API-only tests against disposable real FastAPI/SQLite are allowed; agent/model/provider execution, server startup and unrelated runtime verification remain restricted. Tests must not touch the working database.


## AI-14 governance UX baseline (P00)
[UX specification and role journeys](docs/design/governance-ux.md) and [static wireframes](docs/design/governance-wireframes.png) map the generic AI-13 contract to proposed department capabilities, channel triggers, workflow preview and human decisions. No production FE changes or new capabilities are introduced; AI-15 records the cross-module architecture decisions.


## AI-15 P00 generic governance decision record
[Governance ADR](docs/architecture/adr-ai-15-generic-connector-governance.md) records the shared engine/trusted-adapter boundary, central current policy, separate channel uses, verified identity/ingress, exact-action human approvals, checkpointed continuation and receipts/reconciliation. This is a planning decision with P01–P11 release gates, not shipped future capability. [AI-14 UX](docs/design/governance-ux.md) is the FE integration contract; [AI-13](docs/architecture/connector-governance-contract.md) remains the source-backed baseline. All three form P00; implementing tickets publish exact new APIs/schema before FE integration.

## AI-16 capability policy backend
[Capability governance](poc/governance/AGENTS.md) owns provider-neutral versioned policy and repeated authorization. [Exact P01 contracts](docs/architecture/capability-policy-v1.md) document additive policy/history tables, protected governance APIs, admin expansion versus restrictive manager edits, frozen/current policy intersections and implementation-only descriptors. AI catalogs and existing tool/workspace/notification/merge adapters share the evaluator. Existing grants/credentials/workflows are not migrated or broadened. Only isolated HTTP/SQLite API verification was performed; no local agents/providers/messages. AI-17 UI and later event/generic approval phases remain separate.

## AI-17 capability policy interface
The /organization route now presents capabilities/resources to all department readers and policy editors according to effective role, reusing AI-16 APIs. Admins can edit organization/department policy; managers append department restrictions only. Protected policy GET adds credential-free resource_options for exact configured resources, never grants. See docs/design/capability-policy-editor.md. Local verification is API-only; UI validation is through GitHub CI, without local startup/browser/provider execution.

## AI-18 P01 documentation and authority instructions
[Policy algebra/role matrix](docs/architecture/p01-policy-algebra.md), [exact API/schema](docs/architecture/p01-governance-api.md) and [configuration/rollout guide](docs/governance-policy-guide.md) consolidate the AI-16/17 implementation. Contributor agents MUST use current DB Actor/Resources plus current/captured policy and existing adapter guards; never authorize from stale JWT roles, model text, channel membership or editor options. Approval never creates a missing grant. Do not widen scope, rewrite frozen context/history or fall back to shell/another connector to satisfy a blocked request. P01 source/CI evidence is not deployment or provider/browser verification. AI-18 changes documentation only; no credentials/grants/workflows, runtime prompts, schema or executable code changed.

## AI-19 governed PR adapter operations
The existing generic policy/descriptor layer now exposes separate GitHub PR metadata/diff/check reads and explicit head-pinned comment/review writes. Aggregate read dependencies intersect policy; no write wildcard or legacy resource-only step acquires new writes. Server-only merge requires version2 evidence, a persisted personal approval claim, strict protected-base enforcement and one-attempt audit receipts. Exact contracts/compatibility and unverified live paths: docs/github-pr-governance.md. No saved grants/credentials/workflows or branch protection changed; API-only local verification, no agents/live providers.
