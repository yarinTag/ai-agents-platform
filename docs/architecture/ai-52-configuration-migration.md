# AI-52: configuration snapshot migration and PostgreSQL operations

Status: source implementation, 2026-11-20. No source database was read, PostgreSQL
connection opened, migration applied, tests/imports/builds/server executed.
Only source inspection, whitespace and file-size checks were performed.

## Boundary

This slice migrates one organization's configuration into a dedicated PostgreSQL
namespace. It does not switch DatabaseManager, start workflows or run the Runner.
It is not a complete database backup or production cutover. Exported active flags,
tokens, grants and history are preserved, not rewritten to make migration pass.
Nothing consumes those flags automatically in the new namespace.

configuration_migration_spec.py is an explicit 15-table schema inventory:

| Group | Tables |
| --- | --- |
| Identity and department configuration | organizations, departments, users, department_members |
| Connector governance | mcp_connectors, mcp_tools, department_mcp_access |
| Workflows and history | workflows, workflow_revisions, workflow_secrets |
| Capability policy | capability_policies, capability_policy_revisions |
| Organization runtime configuration | organization_runtime_settings, organization_provider_credentials, organization_provider_credential_events |

All source columns in these tables must match the inventory exactly. Missing,
legacy and newly added columns stop extraction; none are silently dropped. Explicit
SQLite TEXT/INTEGER/REAL/BLOB fields map to PostgreSQL TEXT/BIGINT/DOUBLE PRECISION/
BYTEA. Timestamps remain their original strings in this compatibility stage; JSON
strings remain strings, preserving exact snapshot/grant content and checksums.
No generic SQL rewriting, implicit timestamp conversion, plaintext decryption,
credential backfill or default organization inference occurs.

## Preview and extraction

configuration_snapshot.extract_configuration(source_path, organization_id,
max_rows=100000) opens an explicit existing SQLite file in mode=ro, enables
query_only, and reads all supported tables in one BEGIN snapshot. It never imports
persistence or application singletons. Source row/schema writes are not performed;
normal SQLite WAL coordination may still require accessible sidecar files.

Selection includes rows on either side of department/user/connector relationships
so cross-tenant memberships/grants/workflows are rejected rather than quietly
filtered. Unowned legacy rows outside the selected organization are not claimed;
this is an explicitly owned configuration slice, not proof every source row has
valid ownership. Parent references must resolve inside the selected organization.
Every current workflow requires its saved revision and matching snapshot; current
policy must match the latest immutable revision. Existing historical actor IDs
may reference deleted users and are preserved without fabricated foreign keys.

Rows are type/required-field/uniqueness checked, canonically sorted and hashed.
The snapshot hash binds format version, organization and the full row inventory.
Report output includes only scope, organization, counts and SHA-256 digests, with
cutover_ready=false. The in-memory snapshot itself includes password hashes,
connector tokens/configuration, workflow inputs, encrypted bytes and history:
never log or serialize the payload as a support report. repr omits rows.

## Explicit import and rollback

ConfigurationMigration(connect, namespace).apply(snapshot, expected_sha256=...)
requires the preview hash. It copies and validates data again before opening a
transaction. A schema-wide advisory lock serializes configuration imports. Namespace
must be dedicated (not public/pg_*); no application search_path fallback is used.

The target creates typed tables with source uniqueness, required columns,
tenant-composite primary/foreign keys and deferred relational checks. Child tables
without source organization_id receive that trusted migration context explicitly.
Organization identity is checked against organizations.id. All customer tables
and migration receipts ENABLE/FORCE RLS with transaction-local app.current_org_id.
Migration role owns DDL; an application role must not be superuser/BYPASSRLS and
needs separate explicit grants. No role provisioning or audit immutability claim.

configuration_schema_version holds version=1 and a signature of the inventory,
types, keys and references. A populated unrelated namespace or incompatible
signature is rejected, rather than modifying unknown pre-existing tables.
configuration_migration_runs records organization, format_version=1, source_sha256,
safe report_json and imported_at. Target rows are read back, validated and hashed
before commit. Constraint, checksum or history mismatch rolls back the transaction,
including DDL created in it. PostgreSQL errors are sanitized to avoid printing rows.

An identical retry verifies target rows and returns the same report. A different
snapshot, pre-populated organization or modified target is rejected; import is not
an upsert/merge or synchronization service. Global source uniqueness is retained,
so colliding IDs/email/slug across independently sourced organizations fail closed.

No source quiescence is imposed by preview. The operator must freeze or coordinate
writes for a final accepted snapshot and eventual cutover; a hash only binds the
captured snapshot, not the current state of a still-changing source database.

## CLI, not executed

The default command only reads the source and prints the safe preview report:

```sh
uv run python poc/migrate_configuration.py \
  --source /explicit/offline-snapshot.sqlite --organization org-id
```

Import additionally requires --apply, --schema and --expected-sha256 from that
preview. The DSN is read only from explicitly configured CONFIGURATION_MIGRATION_DSN,
not command-line arguments, DATABASE_URL or default production settings. Install
the existing optional postgres dependency separately in the intended environment.
No command above was executed in this task. The environment variable carries a
secret; do not print it, pass it through workflow prompts or put it in source.

## PostgreSQL configuration operations

postgres_configuration_store.PostgresConfigurationStore validates the same schema
signature and sets tenant context/search_path on a fresh transaction. It exposes:

- get_workflow(org, workflow_id): tenant-scoped internal raw row; not a public DTO.
- update_workflow(org, id, expected_revision, changes, actor_id, actor_label,
  validator): locks the current row, validates current authority via a mandatory
  callback on the same cursor, detects JSON-equivalent no-ops and appends exactly
  one immutable revision atomically for an effective change. Organization cannot
  be reassigned. Only known fields can change. Flags normalize bool or 0/1 to BIGINT.
- save_policy(org, scope_type, scope_id, document, expected_revision, actor_id,
  validator): locks the organization parent even on the first policy write, then
  validates current scope/state and invokes a mandatory callback. CAS/no-op/history
  behavior matches the existing governance store's revision contract.
- capture_policies(org, department_id): locks the existing department for sharing
  and reads organization and department layers together in one SQL MVCC snapshot.
  Missing explicit policy returns virtual revision0/inherit, as in the SQLite path.

The repository is not an authorization service. Workflow callback signature is
(cursor, current_row, proposed_changes); policy callback is (cursor, previous,
proposed_document). Production callbacks must enforce current identity/membership,
resource grants and manager restriction rules in PostgreSQL, not trust JWT role
claims or perform a separate SQLite read. No route or adapter is switched here.
Actor fields record the supplied trusted actor; they do not prove authentication.

## Evidence and remaining gates

test_configuration_migration.py constructs real SQLite tables using the existing
schema initializers and uses the real disposable PostgreSQL fixture. Source cases
cover scoped preview, missing source, cross-tenant references, schema drift,
missing history, exact roundtrip including encrypted bytes, immutable retry,
target constraint rollback, workflow CAS/no-op/revocation, and competing first
policy saves. These tests were not executed and are not yet in CI.

Before cutover: migrate agents/skills/projects and exact execution resources,
execution/frozen contexts, approval/callback receipts, channel/identity state,
budget reservations/usage, runtime sessions and event/audit history. Reconcile live
effects and Runner ownership; preserve backup encryption keys and prove decryption,
not merely ciphertext byte equality. Provide a final freeze/delta plan, verified
backup/restore and single-authority startup configuration. Until then the active
platform remains SQLite and this configuration backend remains isolated.
