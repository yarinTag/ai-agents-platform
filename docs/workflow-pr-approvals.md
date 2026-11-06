# PR review and human-controlled merging

This adds capabilities rather than a Dependabot-specific workflow template. The creation
assistant sees current executable tools, their descriptions, exact resource allowlists,
server-only operations and readiness. It must clarify missing permissions or capabilities.
It cannot create arbitrary integrations from a prompt.

## Example prompt

> Monitor open PRs authored by dependabot[bot] in yarinTag/ai-agents-platform. Read each
> candidate's actual patches, current CI results and review/mergeability state. Explain
> risks and unknowns. For candidates with complete clean evidence, send the review to
> platform_summary_test and wait for my human approval. After approval, recheck current
> permissions, the exact reviewed commits and current CI/reviews, then squash-merge only
> unchanged eligible PRs. Ask for my schedule/timezone before scheduling.

## Setup and permissions

- Configure the existing GitHub connector's exact repository allowlist and credentials
  with PR/content/check/status read access and PR/content merge permissions at GitHub.
- Grant the department `list_open_pull_requests` and `get_pull_request_review` (or existing
  read wildcard). `merge_pull_request` must be explicitly granted; write wildcard grants
  are rejected. Agent restrictions further intersect this grant. Metadata registration
  does not grant permissions.
- Grant `send_message` for the exact Telegram connector/channel (or Slack equivalent).
- Set server `PLATFORM_PUBLIC_URL` to the reachable HTTPS dashboard URL. Link recipients
  must sign in as an active organization admin or department manager. Forwarding a message
  does not grant approval rights. Bot-reply/inline Telegram callbacks remain disabled.
- Create and activate the workflow using existing authoring/management permissions.
  No existing grants, saved workflows, keys or destinations are automatically changed.

## Contracts

`list_open_pull_requests(repository, author?)` returns at most300 open PRs with exact author
filtering, labels, branches and URLs; no recent-update window hides old open PRs. Partial
results are explicit. `get_pull_request_review(repository,pull_number)` returns head/base
SHAs, file patches, latest review states, checks on HEAD/test merge commit and commit statuses.
Missing/unknown/pending/failed/truncated data blocks candidate readiness. Patches are untrusted
repository data and never executed. Readiness is evidence, not proof that code is correct.

A ChatStep can specify `human_approval`:

```json
{"source_step":"review","connector_id":"telegram-id","channel_id":"exact-chat-id",
 "kind":"pull_requests","merge_after_approval":true,"expires_hours":24}
```

The step must explicitly depend on the source, declare one matching delivery tool resource,
and be the single terminal gate depending transitively on all other work. The source must
explicitly request `get_pull_request_review`. The source's successful tool receipts, never
model-produced PR IDs/SHAs, pin up to10 ready subjects. If none are ready, the step completes
without notifying an approval or merging. Report-only gates can use `kind:report` and cannot
merge. Playground rejects gates before sending; deterministic gates never start a model.

The gate sends an audited report and authenticated Logs link, persists `WAITING_APPROVAL`,
and releases its worker/sandbox. GET `/api/v1/workflows/executions/{id}/approval` reads it;
POST the same path with `{approve:true|false}` atomically claims the decision. Current
account/membership controls approval, not JWT role claims or request-supplied actor IDs.

Approval resolves only the original workflow revision. Before merging, the backend rechecks
original initiator, approver, current repository/agent/department grants, deadline, clean CI,
review state and exact head/base SHAs. The REST merge sends an atomic expected-head `sha` and
requires `merged=true` plus a returned commit SHA. GitHub branch rules remain authoritative;
GitHub REST provides no atomic expected-base precondition. There is a residual race between
reads and the provider write; no application-level check replaces GitHub branch protection.

## Limits and operational recovery

- One terminal gate only; arbitrary DAG continuation after approval is not implemented.
- PR batch bound10. A successful merge can advance the base branch, invalidating approval
  of later PRs; those need a fresh review/run. Earlier successful merges cannot roll back.
- Merge intent is persisted before each write; acknowledged receipts are saved individually.
  Failed/unknown requests are never automatically repeated. An interrupted RESOLVING gate
  requires an administrator to reconcile GitHub state against receipts; no recovery worker
  or exactly-once external-write claim exists.
- Expired gates cannot approve; reads mark them EXPIRED and new execution dedup excludes them.
- No CI reruns, arbitrary GitHub writes, merge bypass, new bot webhook, live sends or model
  calls were performed during implementation. Local runtime verification remains restricted.
  CI contracts use pure policies and real temporary SQLite/FastAPI without provider mocks.

## AI-19 strict merge evidence and audit
The existing gate now requires version2 complete aggregate evidence and a fresh current-head approved review, exact required CI and up-to-date strictly protected base. The merge adapter separately verifies the actual persisted personal RESOLVING claim and subject, reserves an immutable call_merge_ audit intent and records approver/agent/SHA/time receipts before completion. Historical evidence is not rewritten or silently promoted. See [exact contract, prerequisites and limitations](github-pr-governance.md); ruleset-only/unknown branches and unsupported requirements fail closed. No live merge was executed.
