# AI-19: separately governed GitHub PR operations

This extends the existing GitHub adapter under the shared P01 policy/effect/resource
model. It adds no Dependabot-specific engine or generic arbitrary HTTP executor.
GitHub is one trusted adapter; other providers still require their own implementations.
[Policy algebra](architecture/p01-policy-algebra.md) · [existing approvals](workflow-pr-approvals.md).

## Implemented operation contracts

All model tools use strict schemas with extra fields forbidden and exact scoped repository
enums. Pull numbers are integers1..2147483647; repository strings3..150. Comments/reviews
require lowercase hex head_sha of exactly40 or64 characters and body1..12000 characters.

| Operation | Effect | Input/authority | Result |
| --- | --- | --- | --- |
| get_pull_request | read | repository,pull_number | Exact metadata, immutable revisions, untrusted_external_data |
| get_pull_request_diff | read | Same; requires get_pull_request | Bounded file patches, partial/revisions_changed flags |
| get_pull_request_checks | read | Same; requires get_pull_request | Checks/statuses/reviews/base-policy evidence; files_included:false |
| get_pull_request_review | read | Same; requires all three operations above | Aggregate files and merge-readiness evidence_version:2 |
| comment_pull_request | write | Same plus head_sha,body; explicit action and department grant | One provider-confirmed PR issue comment receipt |
| review_pull_request | write | Same plus event:COMMENT|REQUEST_CHANGES; explicit action/grant | One commit-pinned review receipt; APPROVE is not a model option |
| merge_pull_request | destructive, server-only | Existing persisted human approval and subject; explicit grant | One SHA-pinned audited merge attempt |

Existing activity/open-PR reads remain available. Edit PR/rerun CI/channel approval
remain unimplemented. No new public dispatch route is added. Existing governance
descriptors expose requires_capabilities and correct read/write effects; decision denial
DEPENDENT_CAPABILITY_DENIED indicates a missing/blocked narrower read capability.
Dependency checks recursively intersect current/frozen policies, current resource, agent
and legacy grants; an aggregate cannot route around a diff/check denial.

Per-operation scopes retain only resources whose references select that operation (or
an explicitly unqualified reference). Newly added PR writes additionally require an
explicit tool declaration; old resource-only steps never automatically receive them.
Repository `*` tool grants cannot authorize writes. Typed allow, model text and approval
cannot create the missing grant. Unknown operation/schema lookup fails closed.

## Review evidence and conservative merge readiness

The adapter uses fixed api.github.com REST paths with repeated current authorization,
verified TLS, bounded JSON responses, no redirects/proxy inheritance and no retries.
PR/files/reviews/checks/statuses are bounded to three pages of100 each. File patches
are capped at60000 total characters; missing/binary patches and malformed/truncated
pages mark partial evidence. Detail/diff/check reads are separate capabilities.

For aggregate candidate_ready:true, all of these must be observable:

- The same exact PR remains open, not draft, not merged, with confirmed clean mergeability.
- All collected current HEAD/synthetic-merge checks are completed success/neutral/skipped
  and latest commit statuses are success; pending, failing and unknown checks block.
- Every named required context is present/successful, including a bound GitHub App ID
  when configured. Test-merge evidence for a context takes precedence over HEAD evidence.
  At least one named required check must be configured and actually successful. A named
  required check with neutral/skipped is conservatively blocked; unrelated optional
  skipped jobs (such as publishing disabled for PRs) do not by themselves block readiness.
- Current-head approved reviews meet the configured count (minimum1), exclude PR author
  and bots, and have a current provider-verified write/maintain/admin repository reviewer.
  Latest approved/changes-requested/dismissed state per reviewer is used; stale approvals
  do not count. A GitHub reviewer is a provider identity, not automatically a platform user.
- Comparing base SHA to HEAD confirms base is the merge base with behind_by=0. The
  current base branch commit and the PR head/base are re-read to detect changes.
- The supported branch-protection slice has classic strict required status checks and
  enforce_admins enabled. Active rules must be inspectable and understood. Ruleset-only
  protection, missing access, code-owner/last-push review requirements, merge queues,
  workflow/scanning/deployment requirements and other unsupported rules block merging.

Evidence includes files/checks/statuses/reviews, branch_policy, candidate_ready, partial,
blockers, blocker_codes, evidence_version:2, review_approved, base_up_to_date and
required_checks_satisfied. A standalone checks read omits files and cannot itself become
the source receipt for a PR approval gate. Existing get_pull_request_review is the only
eligible aggregate source operation. Legacy receipts lacking version2/proof fields do not
become new approval subjects; historical receipts/statuses are not rewritten.

New blocker codes: PR_STATE_UNKNOWN_OR_CLOSED, REVIEW_APPROVAL_MISSING,
BASE_NOT_UP_TO_DATE, BRANCH_POLICY_UNKNOWN_OR_UNSUPPORTED,
STRICT_PROTECTED_BASE_REQUIRED, REQUIRED_CHECKS_NOT_PASSING. Existing safe human-readable
blockers still describe partial/changed evidence, non-clean/draft PRs, CI failure and
requested changes. Unknown evidence never produces a successful readiness claim.

Readiness is evidence, not proof of code correctness. The stricter supported slice can
block repositories that GitHub would allow a privileged user to merge manually. No branch
protection, credentials or plan settings were changed to make these prerequisites pass.

## Comments/reviews and audit

The PR must be open at the requested head before writing. Reviews POST commit_id plus
COMMENT/REQUEST_CHANGES; a model cannot submit APPROVE or resolve platform human approval.
PR comments use the issues/comments API only after confirming that number identifies a PR.
Their body includes the exact head SHA because GitHub cannot conditionally pin a comment.
A head can advance between preflight and POST; a comment remains explicitly about the
named revision, and a review is attached to its supplied commit_id.

The shared executor reserves a deterministic call_exec_ record before I/O, bound to
task/operation/repository/PR/head and review event where applicable. Audit arguments retain
body_sha256, not the body. A changed body at the same action identity is not resent.
The provider ID, expected echoed content and review state/commit must be confirmed before
COMPLETED. Receipt fields: repository, pull_number, head_sha, operation, status, provider_id,
provider_actor, canonical url, UTC completed_at, untrusted_external_data:true.
The audit row additionally records the actual execution agent/task identity. A successful
acknowledgement is stored before later completion checks can fail; revocation does not
erase a known external write. Ambiguous/failed attempts never automatically retry.

## Server-only merge claim and receipts

The existing approval POST still accepts only approve:boolean, requires a current personal
department manager/admin and atomically claims PENDING→RESOLVING. Before each write,
pr_merge.require_claim loads that actual stored claim, checks expiry/current personal
approver authority, merge_after_approval:true and exact membership in persisted subjects.
It cannot use a model/body-supplied actor, approval flag or substitute subject. Every
evidence HTTP request rechecks approver/claim authority in addition to initiator/resource
policy. Immediately before PUT it rechecks again.

Fresh aggregate evidence must still pass and match both originally reviewed SHAs. Each
subject then reserves an immutable one-attempt call_merge_ audit ID derived from approval
and exact connector/repository/PR/head/base. The same transaction stores STARTED intent in
workflow_approvals.receipts_json before any external PUT. Duplicate claims do not send.
GitHub receives sha:<reviewed head> and merge_method:squash. A confirmed merged:true plus
valid merge SHA is required; raw response bodies/messages never become audit errors.

Receipt fields are operation, approval_id, audit_id, connector_id, repository, pull_number,
head_sha, base_sha, status, approved_by (verified platform user ID), agent_id, UTC started_at
and completed_at; confirmed success additionally has merge_commit_sha. approved_by is not
a claim about the GitHub account behind the connector credential. Existing approval read
responses and step output expose these receipts through their already scoped JSON fields.
No schema columns or grants are added.

Receipt status STARTED becomes COMPLETED on acknowledgement; errors before dispatch use
NOT_DISPATCHED, and ambiguous dispatched attempts use UNKNOWN. Existing mcp_tool_calls
status is COMPLETED or FAILED respectively, with the finer state in result JSON. A crash
can leave STARTED; it is not permission to resend. Earlier successful batch receipts survive
a later failure. Approval completion and external write acknowledgement are separate facts.

GitHub's merge SHA condition pins HEAD, not a platform-local transaction with branch/policy
updates. The adapter requires strict protected-base/admin enforcement and rechecks the
base immediately during fresh evidence collection; provider enforcement covers the remaining
base race. Protection/permission changes or server crashes remain distributed-system limits;
no local check can recall a dispatched provider call or guarantee exactly-once recovery.

## Compatibility and verification

No existing workflow, grant, credential, approval history or branch protection was changed
or rerun. Explicit aggregate-read grants now need their separately granted read dependencies;
administrators must review and add those deliberately if intended. Read wildcards retain
their existing trusted-read semantics; write wildcards remain forbidden. Old scopes without
new declared actions cannot acquire new PR writes. All repairs still require current scope
and policy, not a fallback or automatic backfill.

The API-only audit uses real guarded FastAPI/SQLite to verify descriptor/input-schema
contracts, effects/dependencies, write wildcard denial, exact resource/current-role policy,
inactive authoring, no grant backfill and revoked-merge resolution blocked before provider
I/O. It runs without agents, service doubles or external network. Existing CI approval
fixtures carry explicit version2 evidence as persisted test subjects, not fabricated live
provider responses. No live PR reads, comments, reviews, merges, models, workflow runs or
provider-backed success-path integration was executed. Provider parsing/remote-write paths
remain unverified against live GitHub and need separately authorized validation before rollout.

Primary provider contracts: [PR endpoints](https://docs.github.com/en/rest/pulls/pulls),
[review endpoints](https://docs.github.com/en/rest/pulls/reviews),
[branch protection](https://docs.github.com/en/rest/branches/branch-protection),
[active branch rules](https://docs.github.com/en/rest/repos/rules),
[check runs](https://docs.github.com/en/rest/checks/runs),
[required-check behavior](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
AI-20 owns richer UI evidence presentation; AI-21 owns the broader P02 operational contract.
