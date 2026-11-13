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

The first implementation supports Telegram via optional `params.dag_approval.channel_binding_id`. Choose a Telegram department binding with send and approve enabled, an active connector grant, webhook callback_query delivery and a configured HTTPS dashboard origin. Captured and current send policy must allow the destination. The card lists expiry in UTC. The worker edits the original message to reflect quorum and terminal decisions, including dashboard votes. An ambiguous initial send is not retried. Use the dashboard if delivery or editing fails. Slack cards and the visual configuration preview remain follow-up work.
