# AI-37–39 · ConduitCross interactive approvals

ConduitCross is the product name. The proposed shared activation prefix is `conduitcross`. A new message such as `@conduitcross review PR-123` selects the saved `review` workflow within the verified channel scope. A reply such as `/conduitcross review` additionally requires a provider-verified parent message ID. A plain Slack slash-command callback does not by itself establish a reply. This naming and reply convention is a follow-up to the current [channel trigger contract](channel-trigger-policy.md).

## Implementation contract

The dashboard and chat decisions must share the [DAG approval state](dag-approvals.md). An interactive delivery must be bound to the exact organization, department, connector, channel, message, approval and execution. Provider adapters handle transport verification and rendering. The shared decision service resolves a linked personal account and applies the same current role, separation-of-duties, quorum and duplicate-vote checks as the dashboard.

Use opaque action identifiers with server-owned state. The delivery record must retain action, expiry and original message identity. Verification must precede token lookup. Bind the verified provider callback to the saved delivery before applying a vote. The same callback must not create multiple votes. Multiple eligible approvers must still be able to vote on the same message, so accepting one person's vote must not consume the shared action for every other voter. Persist decision and callback receipt atomically.

| Approval state | Original chat message |
| --- | --- |
| Pending | Show the exact expiry and the current quorum count. Leave decision controls available to other eligible users. |
| Approved | Show approved and remove decision controls. Report downstream execution or merge as a separate outcome. |
| Rejected or timed out | Show the terminal state and remove decision controls. |

Edits should converge on the latest persisted state, including decisions made from the dashboard. An edit failure does not undo a vote. A stale button must resolve against the current approval state. Details can link to the authenticated dashboard, and the dashboard remains available if chat delivery or editing fails.

The approval timeout is set on `params.dag_approval.timeout_seconds`. It starts when the workflow suspends. A partial quorum does not extend it. Record delivery and edit outcomes separately from vote outcomes, without logging action identifiers, provider secrets, raw callback bodies or message content. If the downstream action is a governed PR merge, preserve its separate fresh SHA, CI and authorization checks.

## Verification before rollout

Use real FastAPI and SQLite contract tests for channel and message mismatch, revoked links and roles, duplicate callbacks, dashboard races, quorum, expiration, and failed message edits. Check the localized preview and dashboard fallback through the frontend CI. Provider delivery and edits require separate deployment verification.

The first implementation supports Telegram via optional `params.dag_approval.channel_binding_id`. Choose a Telegram department binding with send and approve enabled, an active connector grant, verified HTTPS webhook ingress and callback_query delivery. Captured and current send policy must allow the destination. The card lists expiry in UTC. The worker edits the original message to reflect quorum and terminal decisions, including dashboard votes. An ambiguous initial send is not retried. Use the dashboard if delivery or editing fails. The visual workflow builder previews Telegram cards. Slack support uses the controls described below.

Telegram DAG cards can be delivered without PLATFORM_PUBLIC_URL. A valid dashboard URL adds an optional Details button. Set summary_step under params.dag_approval to a direct dependency that produces a short report suitable for the configured channel. The card includes up to 1,000 characters of that output. Terminal human_approval requests without an interactive binding use the dashboard link path and require its URL.

Create with AI uses eligible Telegram bindings for report-only approvals and compiles those steps into the interactive DAG path. Pinned PR merge gates retain the terminal approval record and use the matching Telegram binding for delivery and decisions.

Pinned PR gates generated with a matching Telegram binding reuse workflow_approvals and persist the callback claim before running the existing resolver. They require no dashboard URL. The resolver still requires fresh protected-branch evidence and exact permissions. An interrupted consumed claim requires operator reconciliation.

A terminal Telegram decision pins the exact identity link record. If that link is removed, the original decision loses merge authority even if the user links an account again.

## Telegram action and verification

The callback data format is `dga:<action>:<token>:<tag>`. The action is `a` or `r`. The 40-character hexadecimal token derives from HMAC-SHA256 of the approval ID with the configured bot token. The 12-character hexadecimal tag authenticates the token and action with the connector’s proof secret. Delivery storage retains the SHA-256 digest of the token. The database owns the approval ID, exact binding and expiry.

Ingress first verifies the connector’s webhook and parses the Telegram callback. The verifier checks the action tag, a non-bot sender and the original bot or channel post. Storage then checks the token digest, connector, channel, message, bot, current connector secret version and current destination eligibility. It resolves the sender to an active linked user before entering the persisted decision path. PR gates still require fresh review evidence and merge authorization after acceptance.

## Failure and recovery

| Condition | Recorded outcome and recovery |
| --- | --- |
| Expired interaction | The current approval deadline controls whether a vote can be accepted. Review the expiry in the dashboard and start a fresh approval if required. |
| Lost role or revoked identity | The current role/link check rejects the action. Review the link and role in Organization settings. A new link cannot restore an already-claimed PR decision tied to the removed link. |
| Duplicate callback or competing dashboard decision | The DAG callback receipt and vote share a transaction. A terminal claim is fenced by status. Inspect the approval and existing receipts before taking another action. |
| Initial send times out | An unconfirmed send is never assumed delivered or retried. Use the dashboard to inspect and decide. |
| Original-message edit times out | The persisted vote is authoritative. The worker reconciles edits toward the current state, and a stale button still goes through validation. |
| PR resolution stops after acceptance | Inspect persisted PR receipts and review the provider’s actual PR state before starting new work. |

To contain a compromised channel, disable Approve on the exact department binding, revoke affected external identity links, and rotate the affected connector secret or bot credential. Review pending decisions and reconcile any accepted PR action against its receipts. Decisions already sent to an external provider may require reconciliation.

DAG callback receipts record approval ID, provider callback ID, actor, action and time. Terminal delivery records retain the claim callback, action and exact identity link, with actor and outcome on the approval. Workflow views display a derived decision source without callback data, token digests or credentials. Agents should request an approval through a saved gate, reference only the scoped run and persisted approval, and treat a chat confirmation as evidence only after the platform records the decision.

## Dashboard configuration

In the workflow builder, choose Dashboard only or a Telegram department binding with Send and Approve enabled. Listen remains independent in channel settings. A direct dependency may provide the findings excerpt. The preview uses sample values and sends no message. Administrator readiness checks report configured HTTPS and webhook secret presence, and the identity indicator reflects the signed-in user. These checks do not verify provider delivery.

Slack HTTPS interactive cards are now implemented in source using the same exact Send+Approve binding, identity link, dashboard fallback and persisted gate. Point Slack Interactivity to the connector-specific HTTPS ingress, configure the app/team/signing secret, and give its bot posting rights in the selected channel. Slack Socket Mode is also available through the outbound worker. Live Slack verification remains pending.

## Explicit checkpoint decision mode

Checkpoint cards display their frozen [approval policy](explicit-approval-policy.md):
CONTINUATION permits eligible initiators/authors, while INDEPENDENT (legacy default)
requires another eligible person. Telegram/Slack callbacks, dashboard decisions and
resume use the same current-role/quorum checks. A click cannot override the mode.
Existing cards/requests are not migrated; select the policy before a new run.
