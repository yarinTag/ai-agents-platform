# Workflow operations and incident recovery

Start in MCP Hub → Webhook Diagnostics for ingress, Workflow Logs → Run audit timeline for dispatch and receipts, and Run approvals for the persisted decision. Correlate by execution ID. Record the affected organization, department, connector, time window, ingress ID, workflow revision, approval ID and receipt IDs. Keep raw payloads, message text, credentials and callback data out of incident notes.

## Webhooks and outbox

| Observation | Operator action |
| --- | --- |
| HTTP 200 and no new receipt | Check for deduplication, a handshake, identity proof or an ignored event. An HTTP 202 means a supported event and its outbox job committed. |
| HTTP 403 | Compare the exact connector URL and provider account, secret version, preserved body and clock. Check that all serving instances use the same authoritative configuration. |
| HTTP 429 or replay flood | Limit the affected route or pause the provider subscription. Keep verification and deduplication enabled. Check queue depth, receipt age and storage capacity before restoring delivery gradually. |
| HTTP 503 or sustained QUEUED/RETRY | Check storage permissions, free space, write contention, and that the API lifespan started the trigger worker. Preserve the queue and receipts. |
| PROCESSING remains after restart | The trigger worker can reclaim a 60-second expired lease. Check attempt count and the correlated dispatch. After the fifth unsuccessful attempt, preserve the FAILED record and diagnose the cause before authorizing new work. |
| Ingress completed but no run appeared | Check input retention, trigger match, exact channel binding, linked sender, fixed principal and current saved revision. |
| Duplicate dispatches or alternating provider verification failures | Pause affected delivery and fence divergent writers. Compare routing, account scope and database targets. Preserve a consistent snapshot of each store, reconcile dispatches and provider effects, then select one authoritative store. Do not replay the other store's jobs to catch up. |

Use [webhook ingress](webhook-ingress.md) for limits, provider-specific checks and deployment mode. For Telegram transport changes, confirm the configured webhook or polling mode and provider registration before restoring delivery.

## Approval recovery after restart

| Persisted state | Operator action |
| --- | --- |
| DAG PENDING | Check original expiry, eligible roles and revision. An eligible user can decide in the dashboard if chat delivery failed. |
| DAG APPROVED, unclaimed | Let the worker resume the checkpoint. If it cannot continue, inspect current revision, initiator authority and eligible quorum. |
| DAG CLAIMED, run interrupted | Inspect stored step results and external receipts. Reconcile possible effects before requesting a new run. A claimed continuation is not automatically replayed. |
| Card SENDING | Stacked AI-43 marks a stale claim UNCONFIRMED after five minutes. Inspect the original channel and use dashboard fallback. Never resend an initial card purely because its receipt is missing. |
| Terminal approval RESOLVING | Check the callback claim and external receipts. A queued Telegram decision can be consumed after restart. An already-consumed claim that stopped mid-resolution requires operator reconciliation. |

Disable Listen, Approve or Send on the exact binding for the affected action. For wider compromise follow [credential recovery](disaster-recovery.md). See [DAG approval recovery](dag-approvals.md) and [interactive approval failure modes](interactive-channel-approvals.md).

## Unknown GitHub merge or changed base

1. Record the exact repository, PR number, reviewed head and base SHAs, decision actor and merge receipt. Reconcile each PR separately.
2. For STARTED or UNKNOWN, inspect the provider's actual PR state and merge commit with authorized access. If merged, verify the commit against the reviewed subject and record the external evidence. If open or inconclusive, escalate with the receipt and do not retry the original claim.
3. For NOT_DISPATCHED or changed head/base, reconcile changes through the repository's normal workflow. Collect current branch-policy evidence, CI and review results and obtain a new human approval before a new governed merge.
4. Preserve prior decision and receipt records. Record confirmed and unresolved effects separately. See [GitHub governance](github-pr-governance.md) and [run audit limits](workflow-run-audit.md).

## Restoration

Confirm one authoritative receiver and database. With operational authorization, follow a new event from an approved test channel through the expected revision, run and receipt. Check dashboard access and decision history. Record the controls restored and the owner of every unresolved provider effect.
