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
