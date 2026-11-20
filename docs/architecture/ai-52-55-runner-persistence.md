# AI-52/55: opt-in PostgreSQL Runner persistence

Status: initial source implementation, 2026-11-20. No tests, DB connections,
migrations, imports, builds, startup or provider operations were executed.
This does not complete platform PostgreSQL migration, HA, or AI-52/55 acceptance.

## Source inventory and reuse

DatabaseManager in poc/persistence.py composes repositories through the SQLite
ConnectionStore. Its PRAGMA configuration and sqlite3.Row are not PostgreSQL
compatible. Workflow revision writes in storage/workflows.py, governance/store.py
and storage/dag_approvals.py use BEGIN IMMEDIATE. Organization and approval schema
migrations inspect PRAGMA table_info. The PostgreSQL RLS adapter under backend/db
is separate and does not switch these repositories when DATABASE_URL is set.
The backend/db guide's earlier dual-engine activation claim is corrected below.

The inactive AI-56 branch supplies the immutable RunnerPlan/OwnedResource models.
They are reused verbatim here as poc/runner/models.py. Its SQLite RunnerJournal
is not copied or activated. PostgreSQL uses the same sandbox_runner_attempts
identity and lifecycle vocabulary, extending it with ownership and logical effects.
This is an alternative persistence backend, never a second source of truth running
beside the SQLite journal. AI-56 integration must select exactly one backend.

## Explicit bootstrap and connections

storage.runner_postgres.initialize(connection) executes the companion SQL within
the caller's migration transaction. It creates a fresh optional Runner schema;
it is idempotent for this same schema version, not an upgrader for unknown legacy
PostgreSQL tables and not an importer of existing SQLite rows. No bootstrap is
registered in DatabaseManager, application lifespan or CLI startup.

connection_factory(dsn) requires an explicit trusted PostgreSQL DSN, opens a new
psycopg2 RealDictCursor connection per transaction, commits/rolls back and closes.
No environment or credential fallback. Optional dependency: project extra postgres.
The operator owns TLS/CA/DSN/search_path and separate restricted application and
migration roles. No driver was installed. Each journal transaction sets
app.current_org_id transaction-locally. All four tables ENABLE and FORCE RLS;
the application role must not be superuser or BYPASSRLS. Explicit tenant predicates
remain in repository queries. RLS does not validate a caller's chosen organization;
trusted admission must derive it from current authenticated identity.

## Tables and keys

| Table | Keys and stored fields |
| --- | --- |
| sandbox_runner_installations | organization_id/installation_id PK; recovery_epoch starts at 1 |
| sandbox_runner_attempts | organization_id/attempt_id PK; installation composite FK; execution_id, recovery_epoch, immutable plan_json/plan_sha256/deadline_at; state, revision, revoked; owner_epoch, claim_token, lease_until; operation/operation_state/resources_json/reason/updated_at |
| sandbox_runner_effects | organization_id/execution_id/effect_id PK; composite attempt FK; request_sha256, owner_epoch/recovery_epoch, state, receipt_json, revision, updated_at |
| sandbox_runner_history | identity id; organization_id, attempt_id, categorical event, optional effect_id, owner_epoch, recorded_at |

No FK to the still-SQLite workflow/user/organization tables is invented. Admission
must check those references before integration. No cascade deletes cleanup or
publication receipts. History is written atomically with mutations, but database
grant provisioning/immutable retention is not implemented; this is not a claim of
tamper-proof audit. Full plans and internal claim tokens are never public DTOs.

## Ownership API and locking

PostgresRunnerJournal exposes register_installation, create(plan, installation_id,
execution_id), get(org, attempt), claim(org, attempt, revision, lease_seconds),
renew(org, attempt, token, epoch, lease_seconds), revoke(org, attempt), and explicit
rotate_recovery_epoch(org, installation). There is no arbitrary SQL/HTTP endpoint.

create revalidates RunnerPlan and atomically conflicts on changed plan/installation/
execution. Initial lifetime must be current. Existing identical records are returned
without revival. Lock order is installation SHARE, attempt UPDATE, effect UPDATE.
Restore rotation obtains installation UPDATE before touching attempts. Row locks
plus revision checks serialize ownership; database clock governs leases (1..300
seconds) capped at the immutable deadline. Takeover increments owner_epoch and
replaces the private random token. Unresolved IN_FLIGHT/UNKNOWN effects or AI-56
STARTED/UNKNOWN lifecycle operations block takeover even after lease expiration.
Renewal is only allowed before expiration with the current token and epoch.
Revocation is sticky, moves to Stopping, preserves tokens/receipts and proves no
physical termination. Recovery rotation increments the installation epoch and
revokes all its existing attempts; no restore is performed by this method.

## Effect API and transitions

PostgresRunnerEffects shares the journal's transaction and locking authority:

- reserve(org, attempt, token, epoch, effect_id, request_sha256) records INTENT.
  A logical effect ID is stable for the same request across attempts in an execution.
  Changed digest conflicts. An existing row is returned without rebinding ownership
  and must never be interpreted as permission to dispatch.
- begin changes only the exact owner's INTENT to IN_FLIGHT and commits before
  external dispatch. Every later begin is rejected, including attempts to reuse
  the same effect from another retry. A crash before the actual request can thus
  leave conservative uncertainty; no automatic replay is provided.
- settle permits IN_FLIGHT -> SUCCEEDED|FAILED|UNKNOWN and UNKNOWN -> terminal
  from the exact retained original claim. Terminal states require a trusted broker
  receipt dict, bounded to 16KiB canonical JSON. FAILED means definitive rejection,
  not timeout. Terminal receipt repeats are idempotent only if identical.
  Late evidence is accepted after lease expiration, revocation or recovery rotation;
  it never creates new authority, clears revocation or starts another request.
  UNKNOWN atomically revokes the attempt and moves it to Stopping; a later receipt
  cannot revive it. A crash without settlement remains IN_FLIGHT and fences takeover.

No reset to INTENT, automatic retry, cross-owner receipt adoption or manual repair
API exists. The trusted broker must validate request digest and receipt provenance,
current policy/budget and downstream idempotency at actual effect boundaries.
Local commit and remote effect are not a distributed transaction: revoke after
begin cannot recall a request already sent. Models must never call settle directly.
Response payloads must be minimized/sanitized before receipt storage; this generic
storage boundary does not recognize arbitrary provider secrets or prove receipts.

## Remaining migration and integration gates

1. Inventory remaining repositories and define PostgreSQL-compatible transactions
   for workflows/revisions, current/frozen grants, approvals, ingress and budgets.
2. Introduce versioned migration tooling plus verified snapshot export/import;
   compare row counts, tenant ownership, constraints and encrypted key usability.
3. Import AI-56 plans/resources/UNKNOWN claims with conservative revocation; do not
   manufacture execution IDs or reset ambiguous operations. Backup epoch and
   post-backup provider reconciliation need operator evidence before activation.
4. Complete lifecycle persistence compatibility and trusted effect broker wiring.
   Keep this backend opt-in and inactive until one authoritative production path
   replaces the SQLite ownership/policy dependencies.
5. Verify PostgreSQL races, denial, role isolation and rollback, then real cluster
   and provider behavior. HA database alone does not provide platform HA.

Test source test_runner_postgres.py uses an explicit disposable PostgreSQL DSN
and a unique temporary schema, real connections and no mocks. Cases include two
claimants, unresolved effect takeover, cross-attempt dedup, payload immutability,
revocation, restore invalidation, late receipt retention, transaction rollback and
RLS for a restricted test role. Tests are not in CI and were not executed.

References: PostgreSQL row locking
https://www.postgresql.org/docs/18/explicit-locking.html and psycopg2 transactions
https://www.psycopg.org/docs/usage.html .
