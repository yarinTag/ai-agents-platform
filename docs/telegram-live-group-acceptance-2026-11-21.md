# Telegram live-group input acceptance — 2026-11-21

## Scope and provenance

The user created a private test group, platform_trigger_group, added the existing
platform bot and sent explicitly addressed test commands. Its invitation preview
showed JOIN GROUP. Actual getChatMember acknowledged the bot as member.
No invitation URL, bot credential, personal identity or raw update is published.

The user explicitly approved a maximum of ten getUpdates requests of at most100
updates per request within20 minutes, because Telegram cannot prefilter by group.
Only two requests were needed. Both used the active installation's exclusive
polling lock; no competing poller, webhook replacement or cursor advancement.
Only this exact group's updates were retained; others were not displayed/processed.
The bounded window was closed after verification. Earlier discovery attempts
against a broadcast-channel destination received no usable test-group input.

The positive sample was actual Telegram provider update140871828/message6.
The negative/capacity samples were actual updates140871829/message7 and
140871830/message8. Their sender matched an existing ACTIVE verified platform
identity belonging to the configured connector organization. No model text or
caller-supplied display name was used to establish that identity.

## Execution environment

Authenticated provider input was passed unchanged through the real polling ingress
entry, current connector/version validation, SQLite inbox/outbox, authenticated
FastAPI rule configuration, trigger consumer and WorkflowEngine. Backend state was
an isolated disposable database, using only the exact test-group connector scope
and a copy of the already-proven personal identity. A fixture manager was the
fixed execution principal; the independent verified administrator was the reviewer.
These identities/permissions exist only in the disposable lab; production grants,
bindings, workflows, identity links and account status were not modified.

The lab held no organization model key and started no application lifespan or
global background worker. An audit hook rejected network/DNS/subprocess operations
during execution. Its workflow contained one approval checkpoint, no model/action
step. The observed approval in this run used the authenticated lab dashboard API,
not a new Telegram callback. The previous card49 record separately proves a real
Telegram callback on the active installation.

## Observed results

| Actual provider sample / recovery check | Result |
| --- | --- |
| Addressed matching command, message6 | One ingress event, one dispatch, one CHANNEL execution reaching WAITING_APPROVAL |
| Repeat admission of the identical provider update | Duplicate acknowledgement200; no second event/run |
| New DatabaseManager and real consumer after the first run | No repeat work or execution |
| Independent authenticated lab approval and real continuation | One personal vote; COMPLETED; second resume claim denied |
| Addressed unrelated command, message7 | No new dispatch/execution |
| Second actual matching command, message8 | Persisted max_runs_per_hour=1 prevented a second dispatch |
| Repeat admission of messages7/8 and another database reopen | No duplicate events or work |

Final totals: **3 ingress events, 1 dispatch, 1 execution, 1 vote, 0 model tasks**.
The sole execution was COMPLETED with **0 input tokens, 0 output tokens, cost0**.
The credential was removed from the disposable connector after each phase and the
connector left DISCONNECTED. The lab/evidence directory is private; raw updates,
state and temporary scripts were not committed. Private receipts:
/private/tmp/ai49-group-live/result.json and negative-result.json.

## What this closes and what remains

This supplies real Telegram group/message/sender evidence for deterministic
match/nonmatch, the persisted capacity limit and input-to-engine integration,
complementing the 65 direct cases in telegram-direct-acceptance-2026-11-21.md and
the actual active-installation card49 approval in the Chrome acceptance record.

It does not prove that the active installation has a configured/enabled trigger
binding, a running trigger worker or successful admission of this group in its
production database. No production activation was requested/performed. Reopening
SQLite and the consumer is durable recovery evidence, not a live process kill test.
Optional live model relevance quality remains unverified. Slack is user-deferred
and tracked separately at https://trello.com/c/DCmFqHZG . AI-47 still has its
remaining Chrome journeys; Firefox is user-deferred. AI-48 final sign-off and
AI-12 completion therefore remain open. Do not move these complete-scope tickets
to Done solely on the basis of this isolated acceptance record.
