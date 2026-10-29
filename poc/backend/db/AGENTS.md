# AGENTS.md - PostgreSQL RLS & Database Infrastructure Service

## 1. Service Identity & Mission
The **PostgreSQL RLS & Database Infrastructure Service** (`poc/backend/db/`) provides enterprise-grade relational persistence and data isolation. It defines the production schema and kernel-level Row-Level Security (RLS) policies enforcing multi-tenant boundaries (`organization_id`) directly within PostgreSQL.

---

## 2. Core Capabilities & Specializations
* **Kernel-Level Row-Level Security (`init_postgres_rls.sql`)**:
  * Applies `ENABLE ROW LEVEL SECURITY` across `departments`, `users`, `agents`, `task_runs`, `interactions`, `workflows`, and `audit_logs`.
  * Evaluates `organization_id = NULLIF(current_setting('app.current_org_id', true), '')` to guarantee zero data leakage between enterprise tenants.
* **Session Scope Injection (`postgres_adapter.py`)**:
  * `PostgresRLSManager.get_scoped_connection(organization_id)` automatically injects the tenant context using `set_config('app.current_org_id', ...)`.
  * Guarantees that any query executed within the connection cannot read or write data belonging to another tenant.
* **Dual-Engine Compatibility**:
  * Preserves local SQLite support for zero-dependency development and testing.
  * Activates PostgreSQL RLS when `DATABASE_URL` is set in production or container environments.

---

## 3. Invariant Rules & Guardrails
1. **No Superuser Bypass**: Application connections must not run as the PostgreSQL superuser (e.g. `postgres`) to ensure RLS policies are strictly enforced.
2. **Mandatory Tenant Setting**: Every scoped connection must execute `set_config` with the caller's validated `organization_id`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule
Whenever any DDL script, table structure, RLS policy, or connection pooling logic in `poc/backend/db/` is modified, this file must be updated in the same commit.

## Workflow Assistant persistence
SQLite initialization in poc/persistence.py adds workflow_assistant_drafts, workflow_assistant_draft_revisions and workflow_assistant_generations. Exact columns, uniqueness, source-generation linking, CAS revisions and job transitions are documented in ../workflow_assistant/AGENTS.md. These proposal/job tables are separate from executable workflows and task runs; API_KEY generation costs count toward monthly department spend. Zero budget must remain zero. This change does not claim PostgreSQL/RLS authoring support.

## Model-only YAML authoring and internal MCP
workflow_assistant_tool_calls adds id INTEGER PK, generation_id FK to workflow_assistant_generations ON DELETE CASCADE, tool_name constrained to workflow_catalog/workflow_schema/validate_workflow_yaml, nullable proposal_hash, nullable unique validation_id, nullable proposal_json, created_at, and generation_id/id index. YAML validation stores the canonical candidate in proposal_json and returns an opaque wfc_ UUID; raw YAML tool arguments, credentials and the private context file are not recorded. Parent resolution is scoped to generation_id, verifies the candidate hash and rechecks live policy. Generations retain the old planner_agent_id column as an empty compatibility field; new selection is model_id/provider_id in request_json. No legacy records are rewritten.
