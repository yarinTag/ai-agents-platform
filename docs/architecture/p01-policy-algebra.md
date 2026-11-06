# P01 policy algebra and authority limits (AI-18)

This describes the source implemented in [AI-16 / PR31](https://github.com/yarinTag/ai-agents-platform/pull/31)
and [AI-17 / PR32](https://github.com/yarinTag/ai-agents-platform/pull/32), not a deployment claim.
[API/schema reference](p01-governance-api.md) · [configuration and rollout guide](../governance-policy-guide.md) ·
[AI-15 target architecture](adr-ai-15-generic-connector-governance.md).

## Terms that must stay separate

| Term | Current meaning | Does not establish |
| --- | --- | --- |
| Capability | Trusted adapter operation/version, e.g. `github.open_pull_request` | Permission for an arbitrary repository |
| Resource | Exact configured repository or provider channel ID, bound to a connector/tenant | Permission from a name, URL or group membership |
| Legacy grant | Active department connector/tool ceiling | A typed-policy exception or unrestricted agent |
| Typed rule | Allow, deny or require_approval for an exact capability/connector/resource tuple and selectors | An executable adapter or missing legacy grant |
| Condition | Subject/workflow/branch/time restriction, or required approval | Authority to widen the action scope |
| Role | Current database account and capped department membership rank | Immutable authority carried by a stale JWT |
| Approval | Authenticated decision in the existing server-owned approval path | A new grant, generic continuation, or successful external action |
| Descriptor/catalog/decision | Implementation metadata or current non-executable projection | A dispatch token, receipt, live provider verification or future permission |

The central evaluator is provider-neutral. The implemented registry currently wraps the
existing GitHub/Telegram/Slack adapters. The complete future adapter/event/approval IR
from P00 is not implemented by this slice.

## One policy layer

Let `x` be the exact capability/version, connector, resource type/ID, current user,
optional agent/workflow and optional workspace branch. A rule matches when its
capability, connector and resource match and all supplied selectors and validity
conditions apply. Lists within one selector are alternatives; different selectors
intersect. Resource and subject wildcards are rejected.

When a selector has values but its context identity/branch is missing, an **allow**
rule does not match. A deny/require_approval restriction conservatively applies
unless another known selector explicitly excludes this context. This prevents an
omitted agent/workflow/branch from evading a restriction; catalog discovery can
therefore be narrower than a fully specified diagnostic decision.

Evaluate the matching effects in this order:

| Condition in a layer | Result |
| --- | --- |
| At least one matching deny | denied |
| default=deny and no matching allow | denied |
| Otherwise, a matching require_approval | requires_approval |
| Otherwise | allowed |

`default=inherit` adds no typed restriction where no rule matches; it does **not**
mean all operations are granted. `require_approval` alone cannot open a default-deny
layer. A matching allow is needed in that layer as well. Rules do not depend on list
order, specificity precedence, or an administrator's role to override deny.

## Intersection across layers and execution

For explanatory decisions, the evaluator first requires:

1. A trusted implemented capability, matching provider, own-tenant department/connector
   and exact currently configured resource.
2. Current account/status/membership rank: authoring >=MEMBER; execution >=OPERATOR.
   An organization administrator has own-org department access without membership.
3. CONNECTED metadata, configured credentials, an active department connector grant
   and a permitted tool. Repository writes require an explicit operation grant.
4. Current scoped agent restrictions and workflow ownership, if those subjects are
   supplied; execution decisions also require the current department budget check.

If those checks pass, order results `denied < requires_approval < allowed`. Take the
minimum of current organization and department layers, plus captured organization
and department layers when supplied by server execution context. The descriptor's
intrinsic approval requirement further caps the result at requires_approval.

```text
explanatory decision = base gates ∩ current(org, department)
                      ∩ captured(org, department, when present)
                      ∩ intrinsic approval condition

actual dispatch additionally requires:
persisted execution/step authority ∩ declared exact resources/tools
∩ current run/task lifetime and workflow revision ∩ adapter preconditions
∩ supported authenticated approval path when required
```

An explanatory decision does not check every runtime invariant. For example, a probe
with optional workflow_id checks ownership, not whether its saved step actually declares
this operation/resource. Tool scopes, repository configuration, task/execution lifetime,
approval evidence and audit claims remain independent execution checks. No model or
HTTP caller can turn the first equation into authority for the second.

`allowed` still does not establish external success. Existing audited successful receipts
are required for declared tool work; model prose cannot substitute for them. Unknown
external write results remain non-retryable until reconciled by an authorized path.

## Captured versus current policy and time

New connector-backed executions capture both complete policy documents/revisions in one
SQLite read snapshot, a UTC captured_at and workflow_revision. Current policy is read
again at each guarded action. Captured rules are evaluated at their **capture time**;
current rules at the current snapshot time. Validity is start-inclusive/end-exclusive:
`not_before <= time < expires_at` where supplied.

- Removing a captured deny, or letting its expiry pass, does not widen that existing
  run. Its captured restriction remains; a separately authorized new execution is needed.
- A future deny absent at capture can become active through the current layer.
- An allow active at capture can cease to allow through the current layer after expiry.
- A future allow cannot create authority that was absent from the captured layer.
- Current account/grant/resource revocation blocks the next authorization check.
  It cannot recall a provider request already in flight. Policy writes are not a
  distributed transaction with external calls.

Historical execution contexts without typed-policy snapshots keep their existing
tool/resource ceilings and receive current typed-policy checks. The system does not
reconstruct historical typed policies or silently rewrite old workflow revisions.

## Concrete examples

These use hypothetical, already configured IDs. No permission or external action is
created by this document. Complete request examples are in the API reference.

| Scenario | Existing ceiling / rules | Result |
| --- | --- | --- |
| Read a PR | OPERATOR; explicit list_open_pull_requests grant; configured repo; both layers inherit | allowed for the probe; dispatch still needs a declared live step |
| Missing write grant | Typed allow open_pull_request on the configured repo; legacy tools only permit reads | denied; a policy allow cannot grant publication |
| Explicit draft-PR write | Explicit clone_repository/open_pull_request grants, suitable governed write workspace, current/frozen layers pass | Eligible for the existing draft-PR path, subject to sandbox, agent, budget and receipts |
| Deny wins | Org deny read on repo A, dept allow the same tuple | denied, including for org admin |
| Default deny | Org default=deny permits only repo A reads; dept inherit | Repo A can pass; repo B cannot, even if its legacy read grant exists |
| Approval is not a grant | merge_pull_request missing from explicit legacy grant; someone has approved | denied; neither approval nor `*` creates merge authority |
| Existing merge path | Explicit merge and review grants, exact reviewed repo, all layers pass | requires_approval; only persisted authenticated approval plus fresh pinned-SHA checks may merge |
| Generic conditional action | Telegram send grant plus require_approval on exact channel | Conditional probe; generic send dispatch remains blocked because P07 continuation is not supplied |
| Channel membership | A person joins a configured Telegram group | No platform membership, trigger right or approval right is acquired |
| Stale JWT | Token says ORG_ADMIN, current account says MEMBER | Current MEMBER/membership limits apply; admin actions stay denied |
| Mixed roles | Global MANAGER, selected department membership MEMBER | Read/author only in that department; no policy or approval management |
| Current relaxation | Captured department deny later removed by admin | Existing captured run stays denied; no automatic retry/restart |

Legacy channel-send wildcard semantics are preserved for compatibility. They must not
be generalized to repository writes, interpreted as listen/approve rights, or broadened
into a new typed wildcard policy.

## Human role × action matrix

All cells assume active current identity and own authorized department/resources.
Conditional cells require the operation's grants and other admission checks.

| Action | MEMBER | OPERATOR | Effective MANAGER | ORG_ADMIN |
| --- | --- | --- | --- | --- |
| Read descriptors/effective catalog and decision explanations | Yes | Yes | Yes | Own org |
| Author/save a new inactive workflow | Yes | Yes | Yes | Own org |
| Execute an authorized workflow | No by base role | Conditional | Conditional | Conditional |
| Activate/update/delete managed workflow | No | No | Authorized dept | Own org |
| Read department policy/history | No | No | Authorized dept | Own org |
| Append department deny/require_approval | No | No | Yes, preserve every saved rule/default | Own org |
| Add allow, change default, edit/remove saved rules | No | No | No | Own org, within existing ceilings |
| Read/write organization policy | No | No | No | Own org |
| Install credentials or change base connector grants | No | No | No | Own org |
| Decide existing workflow approval | No | No | Personal scoped identity plus evidence | Personal scoped identity plus evidence |
| Bypass deny, missing grants, foreign tenancy or required receipts | No | No | No | No |

Existing server-owned API-key/development/service execution handling is separate from
this personal-user matrix. It is not a new durable generic service-principal model.
Policy mutations and human approval decisions require a current personal user. Never
accept a service identity or user/approver selected by model text or HTTP body fields.

## Contributor/agent authority contract

- Use current Actor/Resources and the shared evaluator/adapter guards. Never authorize
  by decoding a role claim on its own, skipping selected-department checks or unioning scopes.
- A catalog/descriptor/editor option is data. Do not persist it as an executable grant,
  mint approval from a positive decision, or use a missing context identity to loosen policy.
- Propose only exact implemented catalog choices. Preserve the user's requested action
  and approval requirements; explain missing capability/setup instead of silently replacing
  merge/write/approval with a summary or plain notification.
- Never use shell, arbitrary HTTP, another connector, another tenant/department or a
  substitute agent to evade a missing grant or denied operation.
- Do not modify grants, workflows, credentials or frozen contexts just to make a test/run
  pass. Policy repair requires the actual current authorized actor, an explicit target,
  CAS revision and an auditable new revision; preserve existing history.
- A channel message, repository/PR content, forwarded link and model output are untrusted
  inputs, not platform authority. The model cannot approve itself or fabricate receipts.
- Keep privileged merge server-only; do not expose internal approval_path as a client flag.
  Refuse unknown operations and conditional actions without a supported continuation path.

These are contributor instructions, not a new runtime prompt, tool or security boundary.
The actual checks are implemented in code; this documentation cannot enforce provider behavior.

## Source and evidence

Algebra: [policy.py](../../poc/governance/policy.py), [models.py](../../poc/governance/models.py),
[registry.py](../../poc/governance/registry.py), [store.py](../../poc/governance/store.py).
Identity/edit authority: [identity.py](../../poc/backend/security/identity.py),
[validation.py](../../poc/governance/validation.py).
Execution: [enforcement.py](../../poc/governance/enforcement.py),
[tool_scopes.py](../../poc/integrations/tool_scopes.py),
[tool_executor.py](../../poc/integrations/tool_executor.py),
[pr_approval_policy.py](../../poc/integrations/pr_approval_policy.py).
Read projection and proposal narrowing: [catalog.py](../../poc/governance/catalog.py)
and [governance.py](../../poc/backend/api/governance.py).
Verification and unverified boundaries are recorded in the configuration guide.
