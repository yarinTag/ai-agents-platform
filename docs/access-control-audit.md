# Organization, department and role access control — 2026-11-05

## Policy

The backend is authoritative. A tenant ORG_ADMIN is **not** a platform-wide administrator.
JWTs identify the current database user; their role/department claims cannot restore removed
rights. Every protected request requires an ACTIVE current user in the signed organization.
Configured API-key/development services remain explicitly organization-bound server identities;
a user JWT cannot impersonate one by carrying a `service` claim.

For non-admins, effective department rank is the lesser of the current account role and the
current membership role. Example: a MANAGER with a MEMBER membership in Finance is read-only
there. Missing membership and unknown roles confer no department rights. Org-owned projects,
custom catalogs and plugin definitions are explicitly organization-shared; they are not
silently assigned a department that the schema does not contain.

| Capability | ORG_ADMIN | Department MANAGER | OPERATOR | MEMBER |
|---|---|---|---|---|
| Read department agents, workflows, tasks, schedules, sessions, messages | All own-organization departments | Assigned departments | Assigned departments | Assigned departments |
| Run/cancel/delegate tasks, run workflows/Playground, chat, dispatch teams | Own organization | Managed department | Assigned department | Denied |
| Create/edit/delete agents, workflow definitions and schedules | Own organization | Managed department | Denied | Denied |
| Formal approvals and workflow evaluations | Own organization | Managed department | Denied | Denied |
| Raise a clarification/approval request | Own organization | Managed department | Assigned department | Denied |
| Manage workflow settings/secrets | Own organization | Managed department | Denied | Denied |
| Configure organization/provider credentials, departments, users/invitations | Own organization | Denied | Denied | Denied |
| Install/configure connectors, grant department/agent tools, direct integration tests | Own organization | Denied | Denied | Denied |
| Read installed connectors/tools | Own organization | Current department grants | Current department grants | Current department grants |
| Create/edit organization-shared projects, custom skills and templates | Own organization | Denied | Denied | Denied |
| Instantiate an owned template into an authorized department | Own organization | Managed department | Denied | Denied |
| Read private organization catalogs/projects | Own organization | Organization-shared | Organization-shared | Organization-shared |
| Audit logs | Own-organization attributable records | Denied | Denied | Denied |
| Other organizations' IDs, lists or payload references | Denied | Denied | Denied | Denied |

The selected department reduces visible/usable department scope; it never adds permissions.
An admin's All Departments selection omits that reduction. The auth profile independently
lists all accessible departments so a revoked/deleted selection can be repaired. An unassigned
non-admin can authenticate and inspect their profile but receives no department data.

## Backend implementation

- `security/identity.py` loads current users/memberships and caps department roles. It rejects
  inactive/foreign/unknown accounts, invalid selection headers, and unrecognized service modes.
- `security/route_permissions.py` is an explicit per-domain endpoint-name inventory. Every new
  endpoint requires a reviewed permission entry; an unknown endpoint fails closed.
- `security/request_policy.py` is a router-level dependency after authentication and before
  endpoint side effects/runtime dependencies. It validates path/query/body ownership,
  department roles, nested JSON/YAML workflow step/resource references, and bounded nesting.
- Whole-DAG engine preflight validates stored step/reviewer department ownership even for admins,
  and personal queued-run user contexts against current database roles/memberships. No JWT
  department array can authorize a removed membership or a different department's agent.
- `security/resource_access.py` checks stored ownership, never an optional caller-supplied
  tenant field. Tasks/schedules inherit from agents and projects; executions from workflows;
  teams/war rooms from their leader and every participant; interactions from tasks/requesters;
  messages from their participants (human approval replies also require a scoped task).
- `security/response_policy.py` filters collections and nested trees and rebuilds scoped
  statistics. Direct IDs are rejected before reads/writes/streams. Foreign/unowned IDs return
  the same 404 result as missing IDs; role/selection failures use 403; invalid identity uses 401.
- `router_registry.py` attaches both admission dependencies and response projection to every
  loaded HTTP router, using FastAPI's own request/exit-stack wrapper. Partial policy installation
  aborts startup instead of leaving unprotected routes registered. Disabled capabilities expose
  only authenticated 503 metadata. The existing static health/capability routes contain no
  tenant records; the capabilities endpoint still authenticates current database identity.

Additional corrections:

- No automatic orphan claiming on login, profile refresh or registration. Ambiguous old records
  are not assigned to a tenant merely because it logged in first.
- Custom skills/templates use organization-prefixed IDs and `access_resource_owners`
  (`resource_type`, `resource_id` composite PK, organization_id FK). Existing unowned global
  records are quarantined from tenant reads/mutations until an explicit ownership migration.
  Project-owned skills inherit their known project owner. Template instantiation stamps the
  actual organization/department and does not copy arbitrary live child-agent IDs.
- Connector responses redact credentials without exposing prefixes; masked placeholders on
  configuration update retain the stored value. Provider keys remain organization-encrypted.
  Department grants stamp their real organization and actor. Tool IDs must match the connector.
- Plugin content must belong to the configured Git repository, or tenant-contained local source.
  Manual repository tokens now use POST request bodies and do not enter URL/cache keys.
- Department reassignment of an existing agent/workflow requires an explicit ownership/history
  migration and is rejected with409 by ordinary update routes; moving a definition cannot silently
  transfer historical data. Workflow task ownership also intersects its persisted execution scope.
- Chat conversation IDs must match the selected agent/project/task. Operators cannot use chat
  to resolve pending formal approvals; approval responses stamp the verified actor rather than
  trusting a submitted responder. Memory deletion validates the project/memory relationship.
- SSE rechecks account status, memberships and current ownership per event, honors selected
  departments and expiry, and does not retain a stale owner cache. The legacy unauthenticated
  websocket closes with code1008; authenticated SSE is the supported stream.

## Host and legacy operations that fail closed

Tenant storage defaults to `poc/workspaces/tenants/<organization>/` (override the common base
with server-owned PLATFORM_TENANT_STORAGE_ROOT). Departments use `departments/<id>/`; explicitly
shared projects/plugin files use `shared/`. Absolute paths, `..` and symlinks cannot select another
tenant/department root. Native work defaults to a tenant/department workspace, not the shared
legacy default directory. Local browsing is administrator-only and shows only the organization's
shared partition; the native host folder picker is disabled. Existing external local paths must
be explicitly migrated into tenant storage; there is no silent permissive fallback.

Organization Direct API workers do not expose host Bash, even with allowedTools or permission
bypass flags. Governed workflow container tools remain available through their existing scope
and sandbox admission. Agent skill instructions resolve through the organization's configured
plugin source or owned custom/project skills, never the global cross-organization skill cache.
These path checks are file-tool containment, not a claim of a complete OS security sandbox.

Broker-wide queue status/DLQ/retry/test-publication APIs have no tenant partition and are denied
to tenant sessions, including organization admins. Authorized workflow queue dispatch is a
separate governed route and remains available. The Tasks page explains this distinction.
Legacy global-secret Telegram/Slack approvals/dispatch do not identify a tenant approver and
are disabled until tenant-bound identity/channel mapping exists. This does not disable ordinary
governed workflow notifications. These restrictions intentionally supersede permissive legacy
behavior rather than pretend a process-wide operation is tenant-safe.

## Dashboard

All HTTP requests forward the in-memory selected department as X-Department-ID; the backend
independently validates it. Page instances remount on organization/user/department/effective-role
changes, discarding old local lists, drawers and selections. Workflow polling additionally
rejects late responses. SSE reconnects with a validated department query and resets its cursor
on scope/session disconnect. Stale 401/profile responses cannot clear/replace a newer login;
cross-tab token changes clear old page state and revalidate the new session. Profiles refresh
on window focus.

`usePermissions` uses the same account/membership cap. Primary create/edit/delete/run/chat,
hierarchy/template, calendar and integration controls are gated. Settings is admin-only;
non-admin Org & Teams shows a read-only department/access view rather than fetching the
administrative user directory. Unassigned users see an access explanation. UI controls are
presentation; manually issuing requests still encounters the backend rules above.

## Source review and validation limits

Static review covered 187 decorated HTTP route declarations (including aliases), role admission,
resource ownership and side-effect ordering, collection/tree projection, events, native tools,
credential responses and session changes. The filesystem module's registered domain is `fs`;
public onboarding/status, disabled legacy callbacks and denied global queue operations are
explicit exceptions. New real SQLite/FastAPI contracts live in `test_access_policy.py`;
`test_access_lab_setup.py` covers additive fixture creation and private credential output.
Frontend `accessPermissions.test.mjs` checks role caps and unassigned/unknown identities.
Existing workflow fixtures now supply real database identities, rather than trusting test claims.
The CI security group includes the new backend cases; frontend test discovery already includes
all *.test.mjs. Source parsing, source line limits and git diff whitespace checks are local checks.

**No local tests, application startup, lint, build, typecheck, Docker, model calls, notification
sends or workflow runs were authorized/executed.** This is source hardening with test cases
prepared for CI, not a penetration test or a verified zero-vulnerability claim. In-flight work
is not recalled just because a user's membership changes; worker/connector admission retains
its existing run-lifetime checks. PostgreSQL and production deployment behavior are not validated
by this SQLite-focused task.

## Explicit manual test lab

`poc/create_access_lab.py --database <existing-db> --credentials <private-file> --apply` delegates
registration through `demo_data.setup_access_lab` to `storage/access_lab.py`. It never imports or
starts the application/services, and is never called on startup. One BEGIN IMMEDIATE transaction
adds two unique organizations, six departments and 26 unique-password accounts: one admin,
three department managers, three operators, three members, one mixed manager, one unassigned
member and one disabled member per organization. It also adds 12 scoped agents, six inactive
single-step workflows/revision1 baselines, two shared projects, two private skills/templates,
and two explicitly offline connector fixtures with Engineering-only read grants. There are
no provider credentials, schedules, webhooks, executions, live sends or external resources.
Existing records are not updated or deleted. Passwords use the canonical PBKDF2 hasher and
are delivered in a newly created 0600 file outside the repository, never source-controlled or
printed in tool output. Setup failures roll back database writes and remove the credential file.
The test data setup itself is explicitly requested data maintenance, not runtime verification.


## Completed requested lab registration (2026-11-05)
The explicit setup was applied to the existing local poc/data/agents_platform.db with marker
10da4d25. Organizations: org_accesslab_atlas_10da4d25 (Access Lab Atlas) and
org_accesslab_boreal_10da4d25 (Access Lab Boreal), each with Engineering, Finance and Operations.
Read-only SQL confirmation found13 accounts per organization (1 ORG_ADMIN,4 MANAGER,3 OPERATOR,
5 MEMBER, including one disabled member),3 departments each, zero provider credentials,
zero workflow executions, zero enabled/scheduled/webhook workflow triggers and zero connected
connectors. The login/password file is outside the repository with mode0600; passwords are not
included in this audit or source control. Existing organizations/accounts were not updated.
This SQL/data setup check is not application login, authorization-test or runtime verification.

Queued workflow admission rechecks the current active database account and department membership before budget/run creation, including empty DAGs. Request-local department claims are refreshed from current capped memberships; signed login claims do not retain revoked privileges.
