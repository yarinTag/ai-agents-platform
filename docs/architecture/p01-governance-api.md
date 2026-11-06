# P01 governance API and persistence reference (AI-18)

This records existing source contracts, not deployment or live-provider verification.
[Policy algebra/roles](p01-policy-algebra.md) · [configuration guide](../governance-policy-guide.md).
Implementation owners: [router](../../poc/backend/api/governance.py),
[models](../../poc/governance/models.py), [validation](../../poc/governance/validation.py),
[store](../../poc/governance/store.py), [schema](../../poc/storage/governance_schema.py).

## Authentication, scope and routes

The required router is registered under `/api/v1/governance`. Use the existing
authenticated platform transport. A token identifies a session; current database
account status, role and capped department membership authorize it. X-Department-ID
is checked against that scope; a department path cannot escape the selected department.
Organization routes derive the organization from the authenticated actor, not a body
organization_id. No token, API key or authority goes into query parameters.

Paths below are relative to `/api/v1/governance`:

| Method | Path | Current personal-user access | Response |
| --- | --- | --- | --- |
| GET | `/capabilities` | Org admin or org reader with membership | `{schema_version:1,capabilities:[descriptor]}` |
| GET | `/organization/policy` | ORG_ADMIN | PolicyRecord + resource_options |
| PUT | `/organization/policy` | ORG_ADMIN | PolicyRecord |
| GET | `/departments/{department_id}/policy` | Effective dept MANAGER or org admin | PolicyRecord + resource_options |
| PUT | `/departments/{department_id}/policy` | Effective dept MANAGER or org admin; restrictions below | PolicyRecord |
| GET | `/departments/{department_id}/policy/history` | Effective dept MANAGER or org admin | `{revisions:[PolicyRecord...]}`, newest first, max100 |
| GET | `/departments/{department_id}/catalog` | Current dept reader | CapabilityCatalog |
| POST | `/departments/{department_id}/decisions` | Current dept reader | CapabilityDecision; does not execute |

Existing service authentication is handled separately by Actor; it is not a user role
or client-selectable principal. Policy writes additionally require a personal user.
There is no policy DELETE, organization-history HTTP route, grant-all endpoint, registry
installation endpoint, execution token endpoint or approval field in this API.

## PolicyDocument and PolicyUpdate

Models forbid extra fields and use strict typed fields. PolicyDocument contains
schema_version=1, default=inherit|deny (default inherit), rules (default [], max200).
Rule IDs must be unique. PUT sends the **complete** desired PolicyDocument plus required
expected_revision integer >=0; it is not a patch. Retain every unrelated rule. Never
copy the hypothetical revision0 examples over an existing policy without first reading it.

PolicyRule fields:

| Field | Contract |
| --- | --- |
| id | Required; `^[A-Za-z][A-Za-z0-9_-]{0,79}$` |
| capability_id | Required; provider.operation pattern `^[a-z][a-z0-9_-]*\.[a-z][a-z0-9_]*$`, max150 |
| capability_version | Integer1; default1; other versions rejected |
| connector_id | Required string, 1..200 characters |
| resource_type | Required; `^[a-z][a-z0-9_]{0,49}$`; must match implemented descriptor |
| resource_ids | Required list, 1..100 exact currently configured resource IDs |
| effect | Required allow|deny|require_approval |
| user_ids / agent_ids / workflow_ids | Optional lists, default[], max100 each; validate own org and applicable dept |
| branches | Optional list, default[], max30; only GitHub clone_repository/open_pull_request |
| not_before / expires_at | Optional nullable ISO strings, max40; timezone required; start must precede end |

Each resource/subject/branch list rejects duplicates, blank or padded values, NUL,
wildcards containing `*`, and values longer than300 characters. Current user selectors
must belong to the organization and, for department policy, its membership (own-org
administrators excepted). Agent/workflow selectors must be own-org and, for department
policy, in that department or the accepted unassigned scope. These selectors cannot
introduce external identity, subject delegation or a generic service principal.

Managers may preserve the existing default/rules and append only deny/require_approval
rules on connectors actively granted to their department. They cannot modify/remove
any saved rule, add allow, or change the default. Full-document validation is inside the
locked compare-and-swap save. Administrators may edit either layer, but all retained
rules must still reference valid implemented capabilities/configured resources.

## Records, editor options and descriptors

PolicyRecord contains organization_id, scope_type (organization|department), scope_id,
revision, document, updated_by (actual actor ID or null for virtual baseline), updated_at
(UTC ISO timestamp or null). Unset policies are virtual revision0 inherit/empty rules;
no table row is inserted by reading them. History projections additionally include
document_json:null for compatibility; the parsed document is the supported payload.

Only policy GET adds resource_options, each with capability_id, connector_id,
connector_name, resource_type and resource_ids. This projection includes typed-policy-denied
configured resources so an administrator can repair a restriction. Department options
require an active department connector grant; organization options remain own-org only.
It does not claim CONNECTED state, credentials, per-operation legacy grants or provider
verification. Unsupported descriptors, foreign data and configuration/credential objects
are excluded. PUT/history do not include options. Options are never executable grants.

Descriptors contain id, provider, operation, effect (read|write|destructive), resource_type,
description, version, server_only, approval_required, implemented, input_schema and
verification=implementation_metadata_only. Non-server implemented tools expose their
existing strict input schema; server-only/unimplemented descriptors have input_schema:null.
The registry is implementation-owned; persisted arbitrary tool metadata cannot add code.

## Catalog and decision contracts

CapabilityCatalog contains schema_version:1, department_id, entries, non_executable:true.
Each entry has connector_id, capability descriptor, resources, provider_verified:false,
readiness:configuration_and_policy_only. Each resource has resource_id and separate
authoring/execution CapabilityDecision values for the **current caller**. Resources with
denied authoring decisions are omitted; an empty catalog is not a complete denial audit
or proof that credentials, connectivity or membership alone caused the omission.

DecisionRequest:

| Field | Contract |
| --- | --- |
| capability_id | Required string 1..150 |
| capability_version | Integer1, default1 |
| connector_id | Required string 1..200 |
| resource_id | Required string 1..300; must be exact configured resource to pass |
| purpose | authoring|execution, default execution |
| agent_id / workflow_id / execution_id | Optional nullable string 1..200 |
| branch | Optional nullable string 1..200 |

Referenced objects require current resource access. execution_id requires its exact
stored workflow_id and department; its frozen policy is loaded on the server. The
probe still uses the **requesting caller's** current identity, not a user_id/initiator
chosen from the request. It is not a replay of all execution authority or step checks.
Client actor_id, approved, frozen and unknown fields are rejected.

CapabilityDecision is `{decision,reason,non_executable:true,policy_revisions}`. Decision
is allowed|denied|requires_approval. Each revision entry has source=current|frozen,
scope_type=organization|department and revision. Short-circuit denials may contain
no or partial revision entries; do not treat them as a complete evaluation trace.

Current reason strings (first applicable guard wins):
CAPABILITY_NOT_IMPLEMENTED, RESOURCE_OUTSIDE_SCOPE, CURRENT_ROLE_REQUIRED,
CONNECTOR_UNAVAILABLE, RESOURCE_NOT_CONFIGURED, CREDENTIALS_NOT_CONFIGURED,
LEGACY_CEILING_DENIED, EXPLICIT_CAPABILITY_GRANT_REQUIRED, AGENT_OUTSIDE_SCOPE,
AGENT_CAPABILITY_DENIED, WORKFLOW_OUTSIDE_SCOPE, DEPARTMENT_BUDGET_DENIED,
FROZEN_SCOPE_MISMATCH, POLICY_DENIED, APPROVAL_REQUIRED,
WITHIN_CURRENT_AND_CAPTURED_SCOPE. Resource admission can reject a request with HTTP404
before a reason is returned. Unknown future codes must not render as success.

## Illustrative payloads, not commands

An administrator opening a hypothetical empty default-deny department layer for one
already granted read operation sends this complete PUT body:

```json
{
  "schema_version": 1,
  "expected_revision": 0,
  "default": "deny",
  "rules": [{
    "id": "read_repo_a",
    "capability_id": "github.list_open_pull_requests",
    "capability_version": 1,
    "connector_id": "connector_example",
    "resource_type": "repository",
    "resource_ids": ["example/repo-a"],
    "effect": "allow"
  }]
}
```

A manager on an empty inherit layer can instead append this restriction while retaining
the same default and all existing rules in the full PUT document:

```json
{
  "schema_version": 1,
  "expected_revision": 0,
  "default": "inherit",
  "rules": [{
    "id": "block_channel_send",
    "capability_id": "telegram.send_message",
    "connector_id": "telegram_example",
    "resource_type": "channel",
    "resource_ids": ["-1001234567890"],
    "effect": "deny"
  }]
}
```

A current department reader can request an explanatory probe with this POST body:

```json
{
  "capability_id": "github.list_open_pull_requests",
  "connector_id": "connector_example",
  "resource_id": "example/repo-a",
  "purpose": "authoring"
}
```

No result is promised for those invented IDs, and the POST never reads a provider or
runs a workflow. Actual results depend on current tenant, grants, policies and context.

## Status and transactional semantics

| Status | Meaning/recovery |
| --- | --- |
| 200 | Successful read/explanation/save; decision can still be denied or conditional |
| 401 | Missing/invalid current authentication or disabled/mismatched user |
| 403 | Forbidden scope/role, manager expansion or non-personal policy write |
| 404 | Hidden/foreign/insufficiently managed resource; do not reveal its identity |
| 409 | expected_revision is stale; reload and explicitly review a new full document |
| 413 | Governance JSON body >262144 bytes |
| 422 | Invalid model/rule, extra authority field, wrong version or inconsistent execution reference |

A selected-department failure can return403 before resource lookup. Handler/schema
errors and central admission can have different validation envelopes; clients must
branch on status, not parse raw exception strings or treat a policy denial as success.

Saves use BEGIN IMMEDIATE. Read the locked revision; reject stale expected_revision;
validate against that locked previous document; if equivalent to an existing document,
keep its revision/history unchanged. Otherwise append a full immutable revision and
update current policy in one transaction, stamping the authenticated actor and UTC time.
Simultaneous saves against one revision have one winner. There is no force-save flag.

## Exact additive SQLite schema

Both tables have organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE
CASCADE, scope_type TEXT NOT NULL CHECK organization|department, scope_id TEXT NOT NULL,
revision INTEGER NOT NULL CHECK >0, document_json TEXT NOT NULL, updated_by TEXT NOT NULL,
updated_at TEXT NOT NULL. capability_policies primary key is
(organization_id,scope_type,scope_id); capability_policy_revisions adds revision to that
key. Scope/subject integrity beyond these checks is enforced by application admission
and validation; there is no claim of a new SQLite per-department FK or RLS policy here.

organization_schema invokes the additive initializer. No legacy grant/credential/workflow
backfill, table drop or new PostgreSQL/RLS migration is implemented. Captured typed policy
and workflow_revision live in existing workflow_execution_tool_contexts.context_json;
no separate execution snapshot table is added. See the configuration guide for rollout,
rollback constraints and evidence.
