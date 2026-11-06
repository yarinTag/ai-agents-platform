# AI-16: capability and resource policy v1

AI-16 implements the P01 backend slice from the AI-15 ADR. The common evaluator
is provider-neutral; trusted adapters register provider-specific operations.
Metadata and arbitrary tool names cannot install executable code. Existing
GitHub, Telegram and Slack implementations are reused, including the authenticated
reviewed-SHA merge path from PR #27 and current-identity RBAC from PR #26.

## Authority and compatibility

Effective access intersects the legacy department/tool ceiling, exact configured
resources, current user status and membership, optional agent restrictions,
workflow scope, execution budget, organization policy and department policy.
New executions capture both policy documents/revisions and workflow revision in
their server-owned execution context. Every guarded action intersects frozen
and current policy; relaxing current policy cannot broaden captured authority.
Revocation takes effect on the next authorization check, not an already in-flight
external request. Historical execution contexts retain their original tool scopes
and acquire current typed-policy checks without inventing a historical snapshot.

ORG_ADMIN can edit either policy within its organization. A MANAGER with current
manager membership can only append deny/require_approval rules to its own
department, preserving every previous rule and default. Only an administrator
can expand, remove or replace restrictions. Validation uses the locked current
document inside the optimistic-concurrency transaction. MEMBER and OPERATOR can
read the effective catalog/decision API; only manager/admin can read policy/history.
Members may author inactive workflows; execution still requires OPERATOR or above.
No authority derives from channel membership or client-supplied actor/approval data.
Service decisions use existing server-owned execution authority, never an HTTP
body-selected service identity. Policy edits require a personal user.

Policies default to inherit so deployment creates no grants and changes no saved
workflows or credentials. Typed allow cannot bypass a missing legacy grant.
Repository writes require explicit operation grants; legacy channel-send wildcard
semantics are preserved. Organization and department default-deny policies each
need a matching allow; deny overrides allow, require_approval is never a grant.

## HTTP contract

All routes are protected under `/api/v1/governance` and selected department scope:

| Method/path | Access/result |
| --- | --- |
| GET `/capabilities` | Current org reader; implementation-owned descriptors |
| GET/PUT `/organization/policy` | Organization administrator |
| GET/PUT `/departments/{department_id}/policy` | Current department manager/admin |
| GET `/departments/{department_id}/policy/history` | Manager/admin; newest 100 revisions |
| GET `/departments/{department_id}/catalog` | Department reader; exact effective resources |
| POST `/departments/{department_id}/decisions` | Department reader; explanatory decision only |

Policy PUT accepts `schema_version:1`, `default:inherit|deny`, `rules` and
`expected_revision` (integer >=0). Extra fields are forbidden. Rules contain
`id`, `capability_id`, `capability_version:1`, `connector_id`, `resource_type`,
`resource_ids`, `effect:allow|deny|require_approval`, optional exact `user_ids`,
`agent_ids`, `workflow_ids`, `branches`, `not_before` and `expires_at`.
Rules <=200; resource/subject lists <=100; branches <=30. Wildcards, duplicates,
foreign subjects/resources and unsupported implementations are rejected.
Validity timestamps must include timezone; start precedes end. Branch selectors
are supported only for GitHub clone_repository/open_pull_request, using workspace
ref; unsupported branch constraints fail validation. Missing subject/branch context
cannot evade a deny or approval restriction. Catalog discovery without branch
context is conservative and can hide branch-limited workspace actions.

Decision input: capability_id, capability_version:1, connector_id, resource_id,
purpose:authoring|execution (default execution), optional agent_id, workflow_id,
execution_id and branch. Execution probes require their exact persisted workflow
and department; frozen policy is server-loaded. Output contains
`decision:allowed|denied|requires_approval`, safe `reason`, `policy_revisions` and
`non_executable:true`. It never mints execution or approval authority. Catalog
entries contain descriptor, connector_id, exact resources with separate authoring
and execution decisions, provider_verified:false and configuration-only readiness.
Neither API performs provider discovery or verifies connectivity.

Stale revisions return409; invalid rules/extra fields422; manager expansion403;
hidden/foreign scope404; absent identity401. Bodies >262144 bytes return413.
An effective update increments revision and stores the actor; identical documents
with current expected_revision are no-ops. Policy responses include organization_id,
scope_type, scope_id, revision, document, updated_by and updated_at.

## Additive persistence and enforcement

`storage.governance_schema.initialize` is called from organization schema setup.
`capability_policies` stores organization_id, scope_type (organization|department),
scope_id, revision>0, document_json, updated_by, updated_at. Primary key is
(organization_id,scope_type,scope_id). `capability_policy_revisions` stores the
same columns with revision added to the primary key. Saves use BEGIN IMMEDIATE,
compare-and-swap and one atomic current/history update. Unset policies are virtual
revision0 inherit documents; no backfill or legacy grant mutation is performed.

`tool_scopes.prepare_execution_context` captures authority and preflights the DAG;
`prepare_scope` narrows each step before dispatch. `tool_executor.authorize`,
`repo_workspace.authorize_workspace`, `notification_guard.notification_target`
and `pr_approval_policy.authorize_subject` call the same evaluator repeatedly.
Existing receipts, initiator checks, resource ceilings and approval state claims
remain mandatory. AI catalog and proposal validation intersect per-operation,
per-resource and per-agent projections; a proposed action still rechecks at runtime.

Merge remains server-only and requires persisted authenticated approval plus fresh
checks; generic conditional read/write actions fail closed pending P07 continuation.
PR edit/rerun and channel listen/approve descriptors explicitly say implemented:false
and cannot be granted. New connectors require reviewed adapter implementations.
AI-17 owns the settings UI, AI-18 the broader P01 guide/rollout, later tickets own
provider action/event transports and generic human approval. This slice does not
implement Telegram approval callbacks or event-trigger installation.

## Verification boundary

The isolated API audit uses real FastAPI routes and temporary SQLite, no service
mocks, network, agent/model execution, workflow dispatch or live messages. It covers
roles, two organizations/three departments each, supported/unsupported capabilities,
resource/subject isolation, provider-independent channel rules, legacy ceiling,
frozen/current intersections, time windows, optimistic concurrency and AI catalog
narrowing. It does not establish live provider or worker integration success.

AI-17 additive read projection: organization/department policy GET responses now include resource_options (capability_id, connector_id, connector_name, resource_type, resource_ids), including typed-policy-denied configured resources. Department options require active legacy connector grants; organization options remain admin-only. Only implemented trusted descriptors appear; no configuration/credentials or foreign resources. PUT/history contracts are unchanged. See ../design/capability-policy-editor.md.
