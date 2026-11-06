# AI-13: generic connector governance baseline and contract

Status: source audit plus proposed v1 contract for P00 review. This document adds no
runtime endpoint, schema migration, adapter, grant or live integration. AI-14 owns UX
journeys; AI-15 owns the cross-module ADR. Their acceptance must preserve the distinctions
below. Every later implementation updates its own AGENTS.md/CLAUDE.md in the same commit.

Ticket: [AI-13](https://trello.com/c/SZTb19BB). Parent: [AI-12](https://trello.com/c/HqVN3GDu).
Source baseline: `2a4dca8` on `codex/workflow-pr-review-approvals` (2026-11-06).
[PR26](https://github.com/yarinTag/ai-agents-platform/pull/26) and
[PR27](https://github.com/yarinTag/ai-agents-platform/pull/27) were OPEN, not merged,
at the audit. Implementation in those branches is not a master/deployment guarantee.

## 1. Scope and evidence vocabulary

- **Implemented** means source exists; it does not imply production/provider verification.
- **Partial** means a useful slice exists but the generic contract is incomplete.
- **Missing** means the required shared mechanism was not found in the owned source reviewed.
- **HTTP-verified** below means real FastAPI guarded routes, signed JWTs and disposable SQLite
  passed the named tests. No adapter was contacted and no inference/task execution occurred.
- P00 is an audit/contract phase. Do not silently implement P01–P11 or mark them complete.

## 2. Source-backed implemented/partial/missing matrix

| Concern | Status / source evidence | Existing contract and gap | Follow-up |
|---|---|---|---|
| Current human identity | Implemented: `poc/backend/security/identity.py:load_actor`, `auth.py:authenticate_request` | ACTIVE DB user/org, current role, capped membership; JWT identifies rather than grants. No external provider identity linkage. HTTP-verified. | P01/P04 |
| Route/resource authorization | Partial generic foundation: `security/{route_permissions,request_policy,resource_access,response_policy}.py` | Explicit endpoint role inventory, inherited ownership, collection projection and selected dept; no standalone versioned action/resource policy algebra. HTTP-verified boundaries. | P01 |
| Connector/tool records | Partial: `backend/api/mcp_{catalog,connectors,permissions}.py`, `storage/department_permissions.py` | Metadata is not implementation. Tool names and free-form capabilities are not sufficient executable authority. Existing string/list grants lack a typed policy/version model. | P01/P03 |
| Connectivity/readiness truth | Partial: `mcp_connectors.py:install_connector,test_connector` | Install/test can set CONNECTED without provider I/O; current test endpoint does not prove provider connectivity. `execution_supported` in authoring is configuration-only. Do not label either as live verified. | P00 acceptance finding; P02/P03/P05 |
| Executable catalog | Partial: `integrations/tool_definitions.py:OPERATIONS,input_model`, `backend/api/workflow_chat_policy.py:catalog` | Real operation inventory for GitHub/Telegram/Slack; descriptive Postgres/etc. metadata remains non-executable. Provider dispatch/resource branching is hardcoded. HTTP-verified catalog projection. | P01/P02/P09 |
| Step authority and receipts | Partial reusable core: `integrations/tool_scopes.py`, `tool_executor.py` | Server-owned frozen scope intersects current resources/grants/lifetime/budget; bounded audited calls and unknown-write no-retry semantics. No generic adapter/operation receipt protocol. Not live-executed in this audit. | P01/P02/P10 |
| PR evidence/actions | Partial provider adapter: `github_prs.py`, `repo_workspace.py`, `pr_approval_policy.py` | Bounded reads/patches/checks; workspace draft PR creation; terminal approved squash merge. No generic PR metadata editing/rerun-CI registry or arbitrary writes. GitHub is a reference adapter, not the core domain. | P02 |
| Channel destinations | Partial: `scoped_channels.py`, `workflow_chat_policy.py`, `workflows_channels.py` | Exact allowlisted outbound destinations and a workflow channel_binding; no shared department binding entity with separate send/listen/approve policy. | P03 |
| Channel trigger declaration | Partial metadata only: `workflows_models.py:ChannelBindingDto.trigger_enabled`, `workflows_channels.py` | Binding flag persists; no authenticated channel-event listener/router implementing that flag was found. Saved flags do not prove trigger delivery. | P05/P06 |
| Provider event identity | Missing shared mechanism | No proved Telegram/Slack user↔organization identity link/challenge model. No provider identity may approve merely because it is in a channel. | P04 |
| Channel event ingress | Missing governed mechanism | Legacy shared-secret ChatOps callbacks are denied by `request_policy.py`; no shared verified event ledger/outbox or channel-trigger routing. Existing HTTP execute/webhook endpoint requires platform auth. | P05/P06/P08 |
| Human approval record | Partial generic report gate: `workflows/{approval_config,human_approval,approval_runner}.py`, `storage/workflow_approvals_schema.py` | One persisted terminal gate, authenticated dashboard decision, TTL, atomic decision claim, current personal manager/admin. HTTP-verified decision/expiry/duplicate/tenant/role boundaries. | P07 |
| Approval continuation | Missing general mechanism | `validate_gates` restricts to one terminal gate; no arbitrary checkpointed DAG continuation/quorum. Interrupted RESOLVING writes require manual receipt reconciliation, not replay. | P07/P10 |
| Channel-native decisions | Missing | PR27 sends a dashboard link, not secure Telegram/Slack approval buttons. Legacy callbacks stay disabled. Public URL validates syntax/configuration, not reachability. | P04/P05/P08 |
| AI authoring | Partial: `backend/api/workflow_chat_{models,policy}.py`, `runtime/workflow_chat.py` | Current catalog capabilities, strict proposals, explicit inactive save; schemas and prompts include PR/channel specifics. No universal provider-neutral action/event/approval IR. HTTP-verified context/save portions only; no generation executed. | P09 |
| Audit/delivery/recovery | Partial: `tool_executor.py`, `notification_guard.py`, `human_approval.py` | Existing call claims, receipts and approval actor history are reusable. No unified ingress→policy→approval→action correlation/outbox/reconciliation contract. | P05/P07/P10 |
| Secret handling | Partial: response redaction and scoped worker env; organization provider encryption is separate | Connector configuration can hold credentials; no unified adapter secret-reference/vault contract. Keep credential access on server; migration must not copy secrets into plans, links or audit. HTTP redaction verified. | P03/P05/P10 |

Two legacy semantics must remain visible in the migration plan: unknown grant names can be
stored without becoming executable, and the low-level permission repository treats absent
department as unrestricted. New generic entry points must require an explicit authorized
scope; they must not reuse that legacy fallback as their security decision.

## 3. Shared v1 contract (PROPOSED, not new executable API)

### 3.1 Identity / principal

Fields: `organization_id`, `principal_id`, `kind:human|service`, `account_status`,
`department_ids`, current effective roles; optional `external_identity_id` for a verified
provider mapping. `initiator_id` and `acting_principal_id` remain separate when a trigger
uses a restricted service principal. Every identity is loaded from trusted state, never
from an AI proposal, a payload or a display name.

External mapping fields: `connector_id`, `provider_subject_id`, `platform_user_id`,
`verification_status:pending|verified|revoked`, `verified_at`, `expires_at?`, `version`.
A short-lived one-use proof links both ends. Forwarded messages, bots, anonymous group
admins and sender_chat identities are not automatically platform humans. Removal from
the organization or department invalidates future protected actions immediately.

### 3.2 Capability descriptor / adapter boundary

An implementation-owned descriptor has:

- `capability_id`, `version`, `adapter_id`, `action_name`, `implemented`;
- strict `input_schema` / `output_schema`, resource types and server-owned resource extraction;
- `effect:read|write|destructive`, execution timeout/size/rate constraints;
- `approval_requirement` references, evidence/freshness requirements;
- `idempotency_mode:none|keyed|provider`, `reconciliation_supported`;
- supported event types and event schema versions, if any.

Connector installation/capabilities JSON cannot register executable code. The trusted
adapter registry binds descriptors to implementations. Secrets are resolved separately
by connector identity. No generic arbitrary-URL/HTTP/shell action is exposed as a shortcut.

Proposed adapter methods: `describe()`, `discover_resources()` (authorized read-only),
`validate_input()`, `execute()` and `reconcile()` when supported; event adapters additionally
`verify_event()` and `normalize_event()`. Provider verification does not grant business
permission: central policy authorizes every operation before the adapter runs. Existing
GitHub, Telegram and Slack dispatch moves behind this boundary incrementally.

Adding a connector requires an adapter plus conformance tests; it must not require a new
workflow engine/approval engine. Adding unsupported features remains explicit development.

### 3.3 Resource / capability grant

`ResourceRef`: `organization_id`, `connector_id`, `resource_type`, immutable `resource_id`,
optional typed constraints (branch IDs, allowed CI definitions, allowed destinations).
Friendly names are display data. Adapters own canonicalization; aliases cannot widen scope.

`CapabilityGrant`: `policy_id`, `policy_revision`, `organization_id`, `department_id`,
subject selector, capability/version, resource selectors, constraints, approval policy,
active state and validity window. Proposed explicit deny wins over allow. Organization,
department, principal/agent, workflow and step boundaries all intersect; no union or
fallback can expand the captured run scope. Shared resources need explicit shared policy.

The central decision is `allowed|denied|requires_approval` with reason codes and provenance.
`requires_approval` is possible only when the base capability/resource permission is present.
An approval is an additional condition, never a new grant. Recheck at catalog projection,
save, start/resume and each actual external action. Write capability never follows from a
read wildcard; preserve explicit merge/publish controls during migration.

### 3.4 Connector readiness / effective catalog

Distinguish installed, credentials-configured, policy-authorized, implementation-supported
and provider-verified (with timestamp/scope). Verification can expire and cannot prove the
provider will be available later. Expose specific missing setup/permission reasons without
secrets. Never silently downgrade a requested human approval into summary-only delivery.

Catalog output contains only implemented, authorized capabilities/resource choices plus
safe explanations of unavailable requested capabilities. It is planning input, not a grant.
AI/manual/YAML authoring use one validated intermediate representation. The model never
receives credentials, callback secrets or discretionary authority to merge/approve.

### 3.5 Channel binding

Fields: `binding_id`, `organization_id`, `department_id`, `connector_id`, `provider_channel_id`,
`display_name`, explicit `uses:send|trigger|approval`, `sender_policy`, `enabled`, `version`.
The three uses are separately granted; adding an outbound destination does not enable listening.

Sender policies: `linked_authorized_users`, `explicit_subject_allowlist`, or explicit
`group_requests` with a restricted service principal and fixed workflow/resource ceiling.
Group membership alone never grants human approval rights or organization membership.

### 3.6 Trigger and event envelope

Trigger fields: binding/version, saved workflow/revision, exact event/command/mention rules,
sender policy, execution principal, strict input mapping/schema, cooldown/dedup/concurrency/
budget limits, enabled state. Begin with explicit commands/mentions. Semantic free-text
matching can later suggest routing within the same fixed policy, never alter permissions.

Normalized envelope: server-owned tenant/connector/binding, provider event ID/type/version,
provider subject, channel/message IDs, verified timestamp and bounded data. State progression:
`RECEIVED → VERIFIED → AUTHORIZED → ENQUEUED`, or `REJECTED|DUPLICATE|EXPIRED` with safe reasons.
Persist ingress receipt before acknowledgement/dispatch using an outbox and durable dedup key.

One callback endpoint per connector routes internally by binding/execution/approval identity.
No callback per agent is required. Verify vendor authenticity before interpreting data;
external sender identity is independently resolved and centrally authorized. Ignore bot
feedback loops; edits/replays/forwarding cannot create extra privileged work by accident.

### 3.7 Action intent / evidence / execution checkpoint

An immutable intent carries execution/step/action IDs, workflow revision, implementation
version, principal provenance, canonical typed input and resource scope, input digest,
evidence references/digests, policy revision and idempotency key. Secrets stay outside it.
Untrusted repository/channel content remains data; it cannot rewrite that intent.

The generic engine schedules adapter actions, typed transforms, bounded iteration/conditions
and human gates from the same IR. Dynamic resource IDs still require scope validation.
Durable checkpoints store completed outputs/receipts and pending dependencies; resume never
replays completed side effects. Callback delivery and human waiting do not hold a worker.

### 3.8 Approval policy / decision

Fields: approval/execution/step IDs, exact action-intent/evidence digests, workflow/policy
versions, approver selectors, quorum, optional separation-of-duties, expiry, rejection path,
notification bindings, decision and actual verified decision-maker. Gate policy is inherited
from central policy; AI cannot weaken it.

Proposed lifecycle: `PENDING → APPROVED|REJECTED|EXPIRED|CANCELLED|INVALIDATED`;
approved action processing has separate `CLAIMED|RUNNING|SUCCEEDED|FAILED|UNKNOWN` state.
Use compare-and-set/leases to avoid duplicate decisions/dispatch. Invalid evidence/changed
workflow requires reauthorization and, where applicable, a new approval. Quorum votes are
uniquely keyed by approval+principal; one human cannot vote twice through two channels.

Telegram/Slack interaction needs provider verification, message/binding match, short-lived
one-use action token, verified platform identity and current approver policy. A dashboard
link remains a fallback; neither the URL nor presence in a channel is authority.

### 3.9 Receipt / reconciliation / audit

A server-produced receipt includes action/idempotency IDs, organization/resource/capability,
provider request/message IDs where available, `SUCCEEDED|FAILED|UNKNOWN`, bounded output,
provider acknowledgement time and error code. Intent is persisted before writes; a provider
acknowledgement is required before success. Adapter-specific safety checks (e.g. expected
GitHub head SHA) supplement central authority, not replace it.

Unknown writes are never blindly repeated. Retry only under a proven provider idempotency or
successful reconciliation policy. Partial batches retain individual receipts and cannot be
rolled back by renaming their aggregate status. No exactly-once external-write guarantee.
Audit correlates event→trigger→principal→revision→intent→approval→receipt; retention and
redaction are tenant-scoped. Operational recovery is an explicit authorized workflow.

## 4. Existing HTTP surface and migration ownership

These are existing routes, not proposed new production endpoints:

| Surface | Current examples | Migration constraint |
|---|---|---|
| Connector metadata/admin | GET/POST `/api/v1/mcp/connectors`, GET/PUT/DELETE `/connectors/{connector_id}`, GET `/connectors/{connector_id}/tools` | Retain ownership and redaction; separate metadata/readiness from executable descriptors. |
| Department grants | GET/POST `/api/v1/departments/{dept_id}/mcp-access`, GET/DELETE `/mcp-access/{connector_id}`, GET `/mcp-access/{connector_id}/check` | Preserve effective restrictions; normalize legacy representations without widening. |
| Authoring context | GET `/api/v1/workflows/ai/context?department_id=...` | Project shared catalog; no provider-specific authority in model output. |
| Workflow definition/revisions | POST `/api/v1/workflows/`, PUT `/workflows/{workflow_id}`, GET `/workflows/{workflow_id}/revisions` | Keep explicit save, immutable revisions and optimistic concurrency. |
| Approval slice | GET/POST `/api/v1/workflows/executions/{execution_id}/approval` | Reuse stored authority/receipts; generalize terminal-only behavior under P07. |
| Legacy callbacks | POST `/api/v1/approvals/telegram-callback`, `/slack-callback` | Remain denied until verified identity/binding/policy transport exists. |

P00 chooses no speculative route names or production schema migrations. P01/P03/P04/P05/P07
must publish exact reviewed API/schema/version changes before their FE integration. New
generic persistence can coexist with legacy fields; no auto-claim, wildcard expansion,
implicit activation, provider credential copy or conversion of unknown writes to success.

## 5. Ownership and sequence

1. P01 central policy + descriptor interface (reuse Actor/Resources/frozen scope).
2. P02 provider adapters (reuse PR reads/workspaces/receipts; implement separately granted gaps).
3. P03 bindings/readiness; P04 proved external identity; P05 verified ingress/outbox.
4. P06 channel triggers with restricted principals and typed input.
5. P07 durable resumable gates/checkpoints; P08 channel-native verified decisions.
6. P09 shared AI/manual/YAML IR; P10 unified audit/recovery; P11 adversarial API/conformance
   tests and explicit staged rollout. P00 API baseline remains regression coverage throughout.

## 6. Executed HTTP baseline and limits

Run the API-only audit from the checkout:

```sh
rtk proxy python3 poc/tests/run_api_audit.py --report-dir /private/tmp/ai13-api-audit
```

The runner copies tracked source plus explicitly named audit files to a disposable directory,
omits application data/workspaces/env files and caller credentials, and uses the existing
venv. Legacy import-time DB singletons initialize only under that copy. Real temporary
repositories are injected through FastAPI dependencies; no app lifespan is started.
`api_audit_guard` disables the real runtime capability and rejects network/DNS/child-process
attempts, rather than faking provider responses. Configured credentials in fixtures are
non-working literal test data. Static agent records are authorization subjects only.

`test_generic_governance_api.py` covers provider-independent HTTP boundaries with GitHub,
Telegram, Slack and a descriptive-only Postgres connector across two organizations, three
departments, four roles, mixed memberships, unassigned/disabled users. It verifies response
redaction, department/tenant selection, current grant changes/revocation, false executable
claims from unknown metadata, explicit merge versus wildcard, inactive authoring and denied
execution, and disabled legacy callbacks. Selected existing HTTP access/approval contracts
cover fresh identity, actor stamping, duplicate decisions and expiry.

Results and verification limits are recorded in [the audit report](ai-13-api-audit.md).
This proves the tested HTTP/storage policies only: no provider connectivity, model planning,
CI rerun, real merge/send, browser behavior, inbound webhook or general DAG resume was tested.
