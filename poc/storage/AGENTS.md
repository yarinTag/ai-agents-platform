# SQLite storage components

This package owns SQLite persistence implementation. `poc/persistence.py` is the compatibility facade/composition entry point. It retains `DatabaseManager(db_path=None)`, `db_manager`, canonical record exports, `POC_ROOT`, `DEFAULT_DB_PATH`, `db_path` mutation, `max_agents`, `_get_connection()`, schema initialization and seed hooks.

## Boundaries and composition

Repositories receive a connection factory and only the cross-repository callbacks they actually call. They never import the facade, dependency container, HTTP routers, or concrete runtime implementation. `composition.py` is the sole collaborator wiring location. It wires agent/session lookup, invitation/user operations, department lookup for governance, maintenance seed hooks, and a live max-agent getter. Callbacks resolve through the facade so its override hooks remain usable at those boundaries.

`legacy_api.py:METHOD_OWNERS` explicitly maps legacy method names to their owning repository. `DatabaseManager.__getattr__` returns the repository's bound method directly, preserving its callable signature rather than duplicating methods or wrapping everything in `*args/**kwargs`. `dir(instance)` includes these names. Unknown names raise `AttributeError`.

Compatibility limit: delegated methods are instance attributes, not `DatabaseManager.__dict__` class methods. Code that introspects or patches methods on the class must use the repository class or migrate to an explicit repository interface. Source inspection found no `DatabaseManager.method` class-level consumers in `poc`, including test source. No tests or import execution were performed. Normal existing API consumers continue to call `db.method(...)`. Repositories use their own methods for internal same-domain calls; overriding a facade method does not override those internal repository calls.

This is storage decomposition, not service/process isolation. Existing cross-table transactions and SQL remain intact. `agents.delete_agent`, maintenance cleanup, budget joins and invitation workflows intentionally still touch several tables; they must be treated as coordinated operations before any future separate database migration.

## Connection and initialization contract

- `connection.py:ConnectionStore` owns `db_path`, `_initializing_db`, connection acquisition, rollback, commit and close. Missing DB files recreate parent directories and schema before returning a connection.
- Each connection retains `foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout=5000`, and `sqlite3.Row`. Normal context exit commits; `BaseException` rolls back; the connection always closes.
- `paths.py` resolves the PoC root from package location, retaining `poc/data/agents_platform.db` as the default and `poc/backend/config/agents.json` as the baseline agent seed source.
- The facade executes ordered schema initializers inside one connection context, then seeds templates and agents, then commits. Existing `ALTER TABLE` compatibility handling and creation order are preserved; no migrations, columns or enum values were intentionally changed.
- `seeds.py` contains the single implementations of `_seed_default_templates(conn)` and `_seed_default_agents(conn)`. Callers own the transaction. Baselines are inserted only when their tables are empty.

## Schema ownership and preserved order

| Initializer | Tables |
|---|---|
| execution_schema.py | agents, projects, skills, task_runs and associated additive columns/indexes |
| event_schema.py | event_log, agent_templates, audit_logs |
| collaboration_schema.py | cron_jobs, agent_interactions, agent_conversations, chat_messages, project_memories, war_room_sessions, war_room_messages, agent_messages, super_agent_configs |
| integration_schema.py | mcp_connectors, mcp_tools, mcp_tool_calls, mcp_agent_permissions, agent_teams, team_members, platform_settings |
| organization_schema.py | organizations, departments, department_mcp_access, users, department_members, org_invitations |
| workflow_schema.py | workflows, workflow_executions, workflow_step_runs, run_evaluations |

The current master integration includes workflow revisions and isolated workflow-assistant draft/generation/tool-call tables in workflow_schema.py. Their additive migrations preserve existing rows and write one current-state Legacy baseline for workflows without history.

## Repository operation ownership

Method names/signatures remain those of the legacy API; `legacy_api.py` is the exhaustive ownership index.

| Repository module | Responsibility |
|---|---|
| settings.py | get/set/delete platform settings |
| agents.py | agent mapping, CRUD, hierarchy, configured capacity and default session request |
| templates.py | template mapping and CRUD |
| maintenance.py | orphan tenant claiming and destructive explicit cleanup/reseeding |
| projects.py, skills.py | project and skill CRUD |
| tasks.py | AgentRun mapping, save/update/list/delete, parent/root trees and active-child counts |
| events.py, audit.py | event sequence allocation/persistence/queries and audit entries/queries |
| schedules.py | cron job CRUD and due-job queries |
| interactions.py | pending interactions and resolution persistence |
| sessions.py | conversations, activation, channels and runtime session continuation |
| chat.py | messages, history, task-message lookup and clearing |
| memory.py | shared project memory CRUD |
| war_room.py | deliberation session/message persistence |
| messages.py | typed agent-to-agent message persistence and updates |
| super_agents.py | SuperAgentConfig persistence and mapping |
| connectors.py | MCP connector/tool CRUD |
| tool_calls.py | MCP call history and status updates |
| agent_permissions.py | agent MCP grants and effective permission checks |
| teams.py | team CRUD and membership |
| departments.py | department CRUD, monthly spend and budget decision |
| organizations.py | organization mapping/settings and CRUD |
| department_permissions.py | department MCP grants and allowed-tools policy |
| users.py | users and department membership |
| invitations.py | invitations, acceptance, bulk issue and email onboarding coordination |
| workflows.py | workflow CRUD, executions and evaluations; one `_row_to_workflow` mapper for ID/token lookup preserves common defaults and boolean conversion |

## Records and invariants

`row_mapping.py:decode_json_columns` is the shared JSON-cell decoder for connector configuration/capabilities, tool schema/arguments, messages, schedules, interactions, memory and war-room reads. It copies each row, attempts decoding only truthy cells, and retains null, empty and invalid legacy values unchanged on decode errors. Repositories retain their own record construction, boolean conversions and query predicates. User, invitation, department-grant, workflow and team membership records have single get/list mapping owners; team membership mapping retains the caller's active connection.

Similar-looking authorization policies are intentionally distinct: agent MCP policy supports agent configuration grants, glob-like connector grants, case-insensitive names and the legacy skip-permissions setting; department MCP policy requires an active grant and exact tool names. These policies are not interchangeable. Update SQL is also intentionally domain-specific because allowed-column sets, explicit-null handling and transaction boundaries differ; there is no generic unrestricted table mutator.

Task storage owns `claim_waiting_parent(parent_task_id) -> bool`, an atomic conditional update from `waiting_for_children` to `running`. It returns whether the compare-and-set acquired the parent; its connection context commits or rolls back exactly as the former orchestration SQL context did. Completion coordination no longer issues this SQL directly.

`records.py` owns AgentMessage, MCPConnector, MCPTool, MCPToolCall, AgentTeam, Organization, User, DepartmentMember, OrgInvitation, Department, DepartmentMCPAccess, Workflow, WorkflowExecution, WorkflowStepRun and RunEvaluation. Their fields/defaults and dictionary conversion behavior are retained, including password-hash exclusion in User.to_dict. AgentRun and TaskStatus come from provider-independent `runtime.models`, not the process adapter.

Preserved string defaults include MCP connector `DISCONNECTED`, tool call `STARTED`, team `ACTIVE`, invitation `PENDING`, user `MEMBER`/`ACTIVE`, membership `OPERATOR`, budget action `REQUIRE_APPROVAL`, workflow execution/step `PENDING`, message type `QUESTION` and message status `SENT`. Existing runtime enum and SQL/update transition behavior remain authoritative; this extraction adds no new state transitions.

Source files must remain under 500 physical lines. Add cohesive repository responsibilities rather than numbered fragments or facade mixins. Any schema, transaction, repository API or compatibility change requires this guide to be updated in the same task. Do not claim runtime compatibility, concurrency behavior or resilience as verified without execution evidence; the user currently prohibits tests/build/lint/startup.

## Final review additions
Record.to_dict owns standard dataclass serialization; specialized User projection still excludes password_hash. Shared row_mapping helpers retain each prior strict/tolerant JSON behavior. Canonical row mappers own workflow, user, invitation, connector/tool, message, department-grant, project and skill get/list projections.

Additional instance methods: save_workflow_step_run(record) writes the existing workflow_step_runs fields in one connection transaction; claim_waiting_parent(task_id) owns the existing conditional parent-state claim; retarget_interaction(interaction_id,target_approver_id) updates only the existing approver column. No table/column migration is introduced. Repository-level policy differences (agent MCP opt-out/globs versus explicit department grants) remain distinct rather than forced into an unsafe generic permission helper.


## Current master integration: revisions, authoring and workflow origin

Workflow now carries `revision: int = 1`; WorkflowExecution includes nullable `payload_hash`. `WorkflowRevisionConflict` remains publicly importable from persistence. Definition creation writes v1 history; `update_workflow` retains incoming actor_id/actor_label/change_summary/expected_revision keyword parameters and performs current-read, optimistic check, effective-change detection and snapshot append under one BEGIN IMMEDIATE transaction. No-op edits add no history. Explicit null clears description/department_id/cron_expression; other absent/null values retain upstream rules. History snapshots contain configuration fields and omit webhook tokens. Schema initialization adds revision/history and one Legacy baseline without inventing earlier changes.

Execution APIs accept payload_hash and initial status, list/filter executions, resolve active or recent completed cache entries, and update started_at/sandbox_path/hash fields as in current master. `save_workflow_step_run` is an upsert by stable step ID: callers can persist RUNNING before inference, then final/paused outcome with the same task mapping. It includes nullable error_message and updates the stored observed outcome without inserting duplicate step records.

TasksRepository provides `get_workflow_task_contexts`, `get_task_workflow_context`, and `list_task_runs(..., execution_scope='all')`; supported scopes are all/office/workflow. The recursive workflow-step/parent/root lineage CTE is retained. Shared agent definitions are never mutated to tag workflow origin.

Department budget conversion preserves zero as an explicit budget. Monthly spend is computed from `workflow_executions` in `departments.py` (the `workflow_assistant_*` tables and spend query were removed on 2026-10-31).

All compatibility methods and the two legacy workflow field/CTE constants are explicitly routed through legacy_api.py to their repository owners. The refactor's connection, mapping, task-claim and resource lifecycle changes were retained. No database migration or other code was executed during source merge.

## Baseline reseed tenant claiming (2026-10-31)
`MaintenanceRepository.clean_database(seed_baseline=True)` automatically calls `claim_orphaned_records` for the primary existing organization after reseeding baseline agents so reseeded agents inherit the organization and default department rather than remaining `NULL`.

## Workflow creation chat records
workflow_schema initializes new `workflow_builder_jobs`: id PK, organization_id/user_id/department_id (FK cascade), request_hash, request_json, status, result_json, error, provider_id, model_id, input_tokens/output_tokens default0, nullable cost_usd, cost_source, nullable workflow_id, created_at and deadline_at. A partial unique index on department_id WHERE status='GENERATING' serializes chat inference in a department. No removed assistant tables or modules are recreated. Each request stores its conversation and authoritative reply. Job workflow_id reserves one stable creation ID; retries recover the same workflow. Terminal records have no automatic retention cleanup in this version.
WorkflowsRepository.create_workflow adds internal is_active:bool=True and writes that value in the initial INSERT/revision. Chat passes false, avoiding a temporary active/scheduled window; existing callers keep the true default. DepartmentsRepository.get_department_monthly_spend now includes workflow_builder_jobs cost_usd with cost_source=API_KEY for the current month. Subscription chat usage is excluded.

## Trusted connector scopes and receipts
workflow_schema now initializes workflow_execution_tool_contexts(execution_id TEXT PK/FK workflow_executions ON DELETE CASCADE,context_json TEXT NOT NULL) and workflow_tool_scopes(task_id TEXT PK/FK task_runs.run_id ON DELETE CASCADE,execution_id TEXT FK workflow_executions ON DELETE CASCADE,scope_json TEXT NOT NULL). Context JSON holds org/department/initiator and a frozen channel binding; step scope JSON holds org/department/agent/workflow/initiator, finite deadline and fixed implemented tool/resource entries. No credentials are stored in these manifests and no HTTP request can supply their identity. They are created by the trusted engine/step runner, not authoring/model arguments.
Existing mcp_tools holds deterministic tool_exec_<hash> implementation metadata. mcp_tool_calls records call_exec_<hash> actual calls, call_denied_<uuid> policy failures and call_notify_<execution> notifications. STARTED is committed before external I/O; COMPLETED requires acknowledged output. Duplicate or ambiguous delivery is not replayed. Safe arguments exclude message bodies/credentials (message SHA256 only); read result projections stay in private application audit storage. No immutable external audit ledger or retention worker is introduced. Cancelled task status is persisted before further tools can be authorized.

Execution tool context JSON additionally stores nullable notification_error through a short BEGIN IMMEDIATE read/modify/write. This preserves frozen identity/binding fields and makes optional delivery failures inspectable without changing the primary execution status or creating extra notifications.

## User departments ID normalization (2026-11-01)
`UsersRepository.get_user_departments` selects `d.id as id, d.id as department_id` so returned department membership rows always populate both `id` and `department_id` keys.

## Organization runtime credential storage
`runtime_settings.py:OrganizationRuntimeSettings` scopes all reads/writes by organization_id, without global fallback. `organization_schema.initialize` adds organization_runtime_settings (organization_id,key,value,updated_at; composite PK), organization_provider_credentials (organization_id,provider,ciphertext,nonce,version,updated_by,updated_at; composite PK), and organization_provider_credential_events (id,organization_id,provider,action,actor_id,created_at). Each references organizations ON DELETE CASCADE. AES-256-GCM AAD binds organization+provider using PLATFORM_SECRETS_KEY. Atomic save validates/encrypts before writing; replace/revoke emits metadata-only REPLACE/REVOKE records in the same transaction. Versions are random positive 62-bit IDs so revoke/recreate never resets a stale worker to version 1. No legacy credentials are automatically migrated. No execution checks run.

## Hosted request budget ledger
hosted_budget.py is initialized by organization_schema. hosted_model_requests columns: id PK; organization_id/department_id FKs cascade; execution_id/task_id/model; reserved_micros INTEGER>=0; charged_micros nullable; state RESERVED/SETTLED/UNKNOWN; pricing_json,usage_json,created_at; department/date index. reserve uses BEGIN IMMEDIATE plus current spend and held reservations; settle is repeat-safe from RESERVED only. UNKNOWN/crash reservations never expire automatically. Settled configured-rate estimates not yet booked by workflow totals add to monthly spend; unsettled reservations are separate reserved_usd in check_department_budget and never shown as actual spend. No prompts, provider keys or response bodies are stored. Existing Direct API calls do not yet reserve per call; global mixed-backend race-free budgeting is not claimed. No migration/runtime executed.


## Catalog ownership and explicit access lab (2026-11-05)
organization_schema adds access_resource_owners(resource_type TEXT,resource_id TEXT,
organization_id TEXT NOT NULL FK organizations ON DELETE CASCADE; composite PK type/id).
Only new explicit tenant-owned custom skills/templates receive rows; legacy globals are not
automatically assigned. Project skills inherit their existing project's owner. Catalog ID
namespacing prevents new cross-tenant collision/upsert. No auth action auto-claims orphaned data.

access_lab.create_access_lab(existing_database, new_credentials_path) uses one BEGIN IMMEDIATE
transaction, INSERT-only unique fixture IDs, canonical password hashing loaded without backend
startup and a private O_EXCL0600 credential file outside the checkout. It creates2 orgs,6 depts,
26 users,12 agents,6 inactive workflows/revision1 snapshots,2 shared projects,2 private skills,
2 templates and2 disconnected connector fixtures with Engineering-only read grants. No existing
rows/grants are modified. No provider keys, cron, webhooks, executions or sends. Entry is the
single demo_data.setup_access_lab registration function via create_access_lab.py --apply.
See ../../docs/access-control-audit.md. The user explicitly authorized this additive data setup;
local runtime verification remains prohibited.

The user-requested lab data was explicitly inserted with marker10da4d25; read-only SQL confirmed
2 new organizations,3 departments/13 users each and no model keys, connected connectors or runs.
The private credential file is outside source control. No application/tests were started.


workflow_approvals_schema initializes workflow_approvals: id PK, execution_id UNIQUE FK, step_run_id,task_id,organization_id,department_id,workflow_revision,status,config_json,subjects_json,report,created_at,expires_at,resolved_at,resolved_by,error,receipts_json(default[]). States NOTIFYING/PENDING/RESOLVING/APPROVED/REJECTED/EXPIRED/EXPIRING/FAILED. API GET lazily resolves expired pending gates. Execution dedup includes unexpired PENDING/RESOLVING WAITING_APPROVAL records; expired approvals do not block new runs. No live migration/database initialization executed in this task.


AI-15 migration decision: preserve existing workflow revisions, approval/call receipts and denials while adding versioned policy/bindings/checkpoints in later owning tickets. P00 performs no schema/migration/data writes. Unknown grants remain inert and read wildcard cannot become write authority. No auto-claim, identity link, credential copy or replay of completed/unknown external writes.

## AI-16 additive capability policies
organization_schema invokes governance_schema.initialize. capability_policies columns: organization_id, scope_type organization|department, scope_id, revision>0, document_json, updated_by, updated_at; primary key organization_id/scope_type/scope_id. capability_policy_revisions adds revision to that primary key. governance.store uses BEGIN IMMEDIATE CAS and one atomic current/history update; validation reads locked previous document. Unset policy is virtual revision0 inherit; no legacy grants/backfill/credentials change. Execution captures both policies in one SQLite read snapshot. See docs/architecture/capability-policy-v1.md.

## AI-18 policy retention/rollback limits
See ../../docs/architecture/p01-governance-api.md for exact table columns/keys and ../../docs/governance-policy-guide.md for rollout. Policy repair is a newly validated CAS revision by an authorized personal administrator, not SQL mutation/deletion of history or frozen contexts. New typed snapshots are stored in existing workflow_execution_tool_contexts.context_json; historical missing snapshots are not reconstructed. Additive SQLite tables do not imply a PostgreSQL/RLS migration or safe downgrade to a binary that ignores typed policy. No working DB migration or retention change was performed for AI-18.

## AI-19 audit JSON additions
No schema columns/tables change. Existing mcp_tool_calls records hold deterministic call_merge_ intent/acknowledgement; arguments/result include approval/actor/agent/resource/SHA/time evidence. workflow_approvals.receipts_json retains STARTED/COMPLETED/NOT_DISPATCHED/UNKNOWN detail. Existing call status FAILED can contain UNKNOWN in result; do not treat it as proof that no external write occurred. Preserve ambiguous claims and prior receipts across recovery. See ../../docs/github-pr-governance.md.
