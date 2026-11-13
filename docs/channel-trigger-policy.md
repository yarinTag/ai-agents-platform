# AI-33 · Channel trigger principals and input boundaries

Channel triggers operate on saved department workflows and verified ingress records. A rule references one exact channel binding by ID. The connector must still belong to the organization and its configured provider account and channel must match the event. The department must have an active connector grant and the binding must enable triggers. Organization-level bindings do not substitute for department bindings.

## Author and sender authority

A current department manager or organization administrator saves the rule against an expected workflow revision. The endpoint records that personal account as the fixed execution principal. Regular definition edits preserve the reserved fields. Workflow creation cannot set them through client YAML or JSON. A different principal must save the rule through the same authenticated endpoint.

The verified provider sender must resolve to a linked active platform user who currently has operation authority in the target department. Sender authority and principal authority are checked separately. The principal must retain department management authority and the engine enforces current workflow, agent, budget and tool policy. An anonymous, unlinked or revoked sender cannot dispatch. The caller cannot select a workflow, principal, scope, model or connector through event text. Service principals and channel-only requests require a separate explicitly governed implementation.

## Configuration and preview

Use `GET` or `PUT /api/v1/workflows/{workflow_id}/channel-trigger` to read or save the rule. The update contains `expected_revision` and a rule or null. The rule contains `binding_id`, `enabled`, `matcher`, `pattern` and an optional map of up to 16 parameter names to event fields. Rules default to disabled.

`POST` to the same path plus `/preview` accepts a rule and a synthetic event. The server replaces the synthetic channel ID with the actual binding channel ID. Preview returns `matched` and `parameters` and neither verifies a sender nor reserves an execution. The workflow builder and settings drawer share this preview.

Matchers support event type equality, exact leading command and mention tokens, a case-insensitive keyword substring, and a bounded regex subset. Parameters can project only `channel_id`, `event_type`, `message_id`, `sender_id` and `text`. Future provider slash-command adapters must map authenticated commands to the shared input contract. The existing Slack identity-link form remains reserved for proof.

## Admission, retention and audit

Only the current leased ingress consumer can reserve a run. Reservation records one execution per internal event and workflow, with the matched revision, exact binding, linked sender and fixed principal. Engine admission repeats the policy checks and atomically moves the execution from `QUEUED` to `RUNNING` under the active lease and unchanged workflow revision. A changed revision requires a fresh event. A claimed run cannot be started again by provider redelivery.

Verified message text is a short-lived, separately stored projection for opted-in channels. It is capped at 2,048 characters and control characters are removed. The claim cannot read expired text and terminal settlement removes it. An execution retains mapped input under ordinary execution access rules. Avoid mapping full text unless the workflow needs it.

The engine labels mapped channel data as untrusted task input. Channel values do not substitute into step templates or skill selectors. A model can still interpret data as instructions, so use saved tool scopes and server-side authorization as the enforcement boundary. Agents must treat message content as data, verify required fields, and report missing or invalid input rather than inventing an authorized action.

Set `PLATFORM_CHANNEL_TRIGGER_WORKER=1` to enable the consumer. Monitor ingress receipts and workflow executions separately. A failed or interrupted claimed run requires reconciliation. Automatic restart of a run that may have begun side effects would risk duplicating them.
