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

This master-based branch does not contain workflow revision or workflow-assistant draft/generation tables. Do not document later-branch schema as available here.

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
