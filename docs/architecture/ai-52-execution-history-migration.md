# AI-52/55: execution evidence migration and replay quarantine

Status: source implementation, 2026-11-20. No tests, imports, CLI, database
extraction/import, application startup or provider actions were executed.

## Purpose and product boundary

Preserve an organization's execution history, frozen authorization, approval
sequence, human votes and external delivery receipts while PostgreSQL migration
is still incomplete. Copying an APPROVED decision, RUNNING execution, SENDING
delivery or UNKNOWN effect must never authorize another side effect.

This profile is archive-only. It has no approve/reject/resume/dispatch/retry API.
Every imported execution receives a separate replay denial. The source status,
timestamps, decisions, token digests and receipts are preserved exactly; migration
does not rewrite ambiguous writes as failures, expire old approvals or fabricate
new authorization context. Current actor/resource policy must be checked by a
future recovery service before any supported continuation can exist.

## Profile inventory

execution_migration_spec.py adds 14 tables to the 15 configuration tables, making
one 29-table SQLite read snapshot and one PostgreSQL import transaction:

| Evidence | Tables |
| --- | --- |
| Channel and identity dependencies | channel_bindings, external_identity_links |
| Observed execution | workflow_executions, workflow_step_runs, run_evaluations |
| Captured context | workflow_execution_tool_contexts, workflow_tool_scopes, workflow_repo_workspaces |
| Human decisions | workflow_approvals, workflow_dag_approvals, workflow_dag_approval_votes |
| Delivery and callback receipts | pr_channel_deliveries, dag_channel_deliveries, dag_channel_callbacks |

This is version2/execution_history, not an in-place upgrade of the configuration
version1 namespace. Import into a fresh dedicated namespace; incompatible existing
signatures are rejected. Configuration v1 remains the default CLI profile and its
hash format, schema signature and operations retain their existing contracts.
Shared extraction/import engines are parameterized by trusted code-defined profiles,
not source-supplied table names, DDL or authorization flags.

## Source checks and exact preservation

- The complete 29-table snapshot is read in one SQLite BEGIN transaction using
  the existing explicit read-only extractor. Columns, scalar types, required fields,
  keys, references and uniqueness must match the profile.
- Approval organization/department, execution, step/task and pinned workflow
  revision must agree. Multiple live terminal approvals for an execution are
  rejected. Historical revisions are validated against saved workflow history,
  not replaced by the current workflow revision.
- Frozen context and tool scopes retain their raw JSON strings. Explicit tenant,
  department, workflow or execution IDs must match their enclosing record. Frozen
  governance validates the recorded policy document/scope/revision; it does not
  substitute today's policy. Duplicate JSON keys and non-finite JSON are rejected.
  Missing legacy context is preserved as absent and diagnosed, not reconstructed.
- Existing historical users/agents/tasks/connector/binding/link references are
  looked up in the same source snapshot in bounded parameterized batches. A
  surviving foreign-organization reference is rejected. Deleted references may
  remain opaque historical IDs; no user, binding or link is recreated to satisfy
  a receipt. Null legacy task ownership is not promoted into a verified identity.
- Source ownership is rooted in explicitly owned workflows and approvals.
  Globally orphaned/unowned data with no provable organization is not claimed by
  this export. This remains a scoped evidence slice, not a complete DB backup.
- Approval config/subjects/remaining/receipts and DAG policy/checkpoint payloads
  retain original fields, including unfamiliar provider receipt fields. No model,
  webhook consumer, callback resolver or file path is invoked during extraction.

Historical task/agent IDs and workspace paths are references only. Agents/task
records and sandbox directories are not copied or provisioned by this profile.
Pending enrollment challenges, channel ingress/outbox/trigger records, actual tool
call/event logs, budget ledgers and live Runner ownership still need their own
migration contracts. Imported identity links are historical dependencies, not a
new provider identity proof or authorization to consume old callbacks.

## PostgreSQL constraints and recovery holds

ExecutionHistoryMigration reuses ConfigurationMigration's atomic apply,
preview-hash binding, exact target readback verification, typed columns, composite
tenant keys, deferred FKs and ENABLE/FORCE RLS. organization_id is injected only
for child tables whose ownership was established by the source closure.
Source uniqueness and the partial live terminal approval / exact channel identity
indexes are retained. Existing same-snapshot retries verify data, never upsert it.

The derived execution_recovery_holds table stores:

| Column | Contract |
| --- | --- |
| organization_id, execution_id | Composite PK and tenant-composite FK to imported execution |
| source_sha256 | Full version2 snapshot identity |
| reasons_json | Sorted categorical recovery reasons, no customer payload |
| replay_allowed | NOT NULL FALSE, CHECK prohibits TRUE |

Every execution includes ARCHIVE_ONLY. Additional reasons include active or
unrecognized source execution state, missing/legacy frozen context, pending
approval/advancement, unresolved STARTED/UNKNOWN effects, unclaimed/claimed DAG
continuation and QUEUED/SENDING/UNCONFIRMED delivery. These are diagnostics, never
evidence that unlisted providers succeeded. A completed execution is still held.
Holds commit in the same transaction as source evidence and migration receipt.
A missing/changed hold on an import retry is an error, not silently repaired.
There is no hold release method or automatic recovery worker.

## Read-only inspection

PostgresExecutionHistory validates the version2 schema signature and uses current
tenant context plus mandatory validator(cursor, raw_execution) for each read:

- get_execution returns bounded metadata/cost/state and recovery reasons; no
  trigger payload, private report, provider error body, token or workspace path.
- approval_history returns at most limit terminal and limit DAG records (1..100
  each); terminal summaries expose at most 20 receipt states with omitted count.
  It does not expose reports, callback tokens or provider destinations/URLs.
- load_frozen_context is a private explicit inspection method returning archived
  evidence with replay_allowed=false. It must not be used as a public DTO or live
  tool authorization input.

Raw workflow lookup, mutating workflow/policy methods and current-policy capture
are rejected. No HTTP
route or active storage adapter uses this view. A historical approver's decision
does not bypass the viewer's current status or department permissions. Production
read validators must enforce current identity and role policy in PostgreSQL.

## CLI and verification gates

The existing CLI now accepts --profile execution-history. Default remains preview;
--apply still requires explicit --schema, --expected-sha256 and the separately
configured CONFIGURATION_MIGRATION_DSN. No command was run in this task.
Preview/import reports contain table counts/digests, replay_allowed=false and
cutover_ready=false, never payloads. Raw snapshot objects remain sensitive.

test_execution_migration.py uses existing real SQLite schema fixtures and the real
disposable PostgreSQL fixture. Source cases cover raw receipt retention and safe
reporting, foreign frozen scope, duplicate JSON keys, foreign live task references,
approval/step mismatch, exact target roundtrip, replay quarantine, missing-hold
rejection and current-reader revocation. Configuration v1 regression source remains
applicable to the shared engine. None of these tests were executed or added to CI.

Next activation gates: complete resources/agents/tasks, channel ingress and identity
lifecycle, cost/budget/event/audit history and Runner ownership migration; verify
backup/key recovery and current/frozen authorization; design explicit reconciled
recovery with provider receipt evidence. Until then the application stays on SQLite
and both PostgreSQL profiles remain isolated from all execution paths.
