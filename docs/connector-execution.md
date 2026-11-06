# Governed workflow connector execution

The workflow runtime now has a backend execution path for GitHub.com activity
reads and Telegram/Slack plain-text sends. Connector IDs in a prompt are no longer
the execution mechanism: the backend supplies real function tools with a fixed,
permission-checked resource scope.

## Use it

1. Select a Direct API provider/model that supports tool calling.
2. In MCP Hub, configure the GitHub connector's token and explicit allowed repos.
3. Grant the department `get_repository_activity` (or appropriate individual read
   tools). An existing `*` grant covers newly registered implemented tools;
   explicit whitelists must include each requested tool.
4. Create/refine the workflow in **Workflows → Create with AI**. The resource list
   shows which connectors have implemented, granted tools. Assigned agents with
   explicit MCP restrictions must also permit the operation.
5. For delivery, configure a real numeric Telegram chat ID/public `@channel`
   username or Slack channel ID, add it to the allowed channels and grant
   `send_message`/`post_chat_message` respectively.
6. Start a fresh production execution with **Run on this server** or an available
   queue. **Playground remains tool-free** and cannot fetch live repository data.

The exact legacy sentence “This is an inactive preview; do not claim execution.”
is removed from production step input for compatibility with earlier generated
workflows. Saved configuration/revision history and Playground input are not
rewritten. Other unsupported or ambiguous instructions still need correction.

## Find the forgotten Telegram ID

`Hermes_test` is a display label, not a numeric ID or `@channel` username. The
runtime will not guess or redirect it to a different recipient.

An active organization administrator can edit the Telegram connector in MCP Hub
and use **Find chats**. It now reads recent bot updates and displays actual
chat IDs/titles, with no fabricated defaults or automatic selection. Select the
intended ID, replace the old display-name entry, and save the allowlist. Discovery
does not grant a workflow permission or send a test message.

Only recent updates known to that bot can reveal chats. Telegram's `getUpdates`
cannot work while that bot has an outgoing webhook. The implementation does not
remove webhooks or advance the update offset. If discovery is empty/unavailable,
the exact ID or public `@channel` username must be obtained through the bot's
existing integration or Telegram administration. [Telegram API](https://core.telegram.org/bots/api#getupdates)

## Supported tools

| Provider | Implemented canonical tools | Scope |
| --- | --- | --- |
| GitHub.com | `get_repository_activity`, `list_commits`, `list_issues`, `list_pull_requests`, `list_releases` | Exact approved `owner/repo`; 1–90-day lookback |
| Telegram | `send_message` | Exact allowed numeric ID or public `@channel`; plain text |
| Slack | `post_chat_message` | Exact allowed C/G channel ID; plain text |

GitHub activity projects commit messages, issue/PR titles and states, and release
names/dates. Issues/PRs are selected by update time; releases by publication time.
The adapter caps each category at three pages of 50 and projected content at
45,000 characters. It reports `partial=true` on limits, so the summary must not
claim complete coverage when truncated. Ordinary tags are not releases.
[GitHub commits](https://docs.github.com/en/rest/commits/commits#list-commits),
[pull requests](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests),
[releases](https://docs.github.com/en/rest/releases/releases#list-releases).

GitHub writes, arbitrary MCP servers, GitLab, Trello, SQL, filesystem tools and a
CLI-MCP execution bridge are outside this implementation. A descriptive catalog
entry for an unsupported operation does not make it executable.

## Security boundaries

- The trusted backend snapshots org/department/workflow/execution/agent/initiator
  and each step's declared connector/resource/tool scope. Models cannot provide
  or change that identity.
- Each call rechecks the live task/execution, expiry, initiator status and current
  department role, tenant/agent identity, connector status, department and agent
  tool grants, budget and current resource allowlists. Grants that grow during a
  run do not widen the captured scope. Skip-permission flags do not bypass it.
- Connector-backed workflows, their analysis steps and reviews have no local
  shell/file/delegation tools. Connector credentials stay in backend request
  headers/paths and never enter model prompts, tool schemas or audit arguments.
- Managed transcripts are private and task-bound as well as provider/model/agent
  bound. Start a new execution when moving from an old unscoped session.
- Requests use verified HTTPS to fixed vendor hosts, with no redirects,
  environment proxies, arbitrary request URLs or automatic retries. Inputs and
  response sizes are bounded; each step admits at most 32 new connector calls.
- Repository data is untrusted. It cannot become a supervisor/permission command
  through runtime text heuristics. Link previews and Slack control markup are
  disabled for governed sends.
- Receipt checks in both worker and parent prevent a prose-only “done” from
  completing work that requires real repository access or channel delivery.

Backend processes and their database/filesystem permissions are trusted; this is
not an OS sandbox against arbitrary backend code. Permission checks cannot undo
requests already dispatched to a provider. Cancellation stops new calls and late
model results cannot overwrite the cancelled task state.

## Audit and delivery semantics

Actual I/O is preceded by an atomic `STARTED` audit claim, followed by `COMPLETED`
or `FAILED`. A duplicate read can return its authorized successful receipt.
Channel sends have one attempted logical report per task/connector/channel; changed
text, timeout or unknown outcome does not automatically resend. Message audit
arguments contain a content hash rather than the body. Known denied tool attempts
are also recorded without hostile arguments.

Completion notifications are optional. An invalid or denied target is recorded
as `notification_error` and no message is sent; authorized data work can continue.
An explicit message-send step is required work and still fails on an invalid
target. Completion notifications use the frozen exact connector/channel binding, current
policy checks, and a real execution audit actor. A successful explicit send step
suppresses a duplicate completion notification to that destination. Provider
acknowledgement is required; notification failures remain best-effort delivery
failures rather than turning them into fabricated success. The audit is local
application storage, not a tamper-proof ledger or cross-system exactly-once
transaction. [Telegram sends](https://core.telegram.org/bots/api#sendmessage),
[Slack sends](https://docs.slack.dev/reference/methods/chat.postMessage/).

## Verification status

The implementation and whitespace were reviewed statically. Security cases were
added using real SQLite, FastAPI/JWT authorization and runtime objects, with no
mock successful provider responses. Tests, builds, type checks, live discovery,
GitHub/model calls and message sends were **not run**, following the repository's
current verification restriction. These changes are not a completed security
certification or a verified live integration.

When execution is authorized, use `--noconftest` for the connector security and
workflow chat/local-dispatch/Playground cases to avoid the shared database reset
fixture. Then verify an isolated read-only repository run before any live channel
delivery, with real permissions and acknowledgement/audit inspection.

## Simple Telegram delivery check
Open MCP Hub → Installed Connectors → Telegram settings. Start the configured bot
in your private chat, or add it to your group/channel with permission to post.
Use **Find chats**, choose the intended name and save. Names are presentation
metadata (`configuration.channel_labels`); `allowed_channels` retains exact IDs.
Public channel @usernames can be entered directly. Arbitrary titles cannot be
resolved safely and are never guessed. Recent-update discovery can be unavailable
when another consumer has already confirmed updates or a webhook is active.
Back on Installed Connectors click **Send test message** beside the saved name.
**Check connection** is separate and does not prove message delivery. The send
requires an active organization administrator, exact tenant connector and saved
allowlist. Success requires Telegram's message receipt; failure displays safe
setup guidance. No test is sent automatically or retried after an uncertain result.
No runtime checks or outbound tests were performed during this change.

Telegram HTTP rejection bodies now produce fixed allowlisted setup hints when recognized. Unknown reasons remain generic; no raw Telegram response or credentials are exposed. Migrated group IDs require explicit rediscovery/save. This diagnostic change was source-reviewed only.

## Deterministic channel action steps
`channel_action.py` owns explicit `params.channel_action` with strict fields:
`action: send_channel_message`, `connector_id`, `channel_id`, `source_step`.
The source must be in depends_on. Only its nonempty output is delivered; output
up to60,000 characters is preserved and delivered as numbered bounded parts; larger reports fail explicitly without truncation.
No prompt parsing or model decision triggers sends. After saving RUNNING task/step
and prepare_scope, step_runner dispatches this action through WorkflowToolExecutor
instead of model inference. Exactly one scoped delivery tool and one destination
are required. All live tenant/initiator/agent/department/resource checks, atomic
no-retry call claims and provider acknowledgements remain mandatory. The task
becomes COMPLETED only after receipt verification and a still-RUNNING check.
Failure follows normal failed-step recording; Playground rejects delivery actions
without invoking tools. Native definition validation checks action structure and
source dependency. Existing tool-calling model steps retain their behavior unless
explicitly converted. No tests, application or provider calls were executed.

Repair applied locally: the two inspected workflows now reference the previously
acknowledged channel -1004464346735 rather than its username; connector allowlist
was updated consistently. The AndroidApp send step is explicitly deterministic.
Workflow revisions were appended (6 and2), retaining prior definitions and run
records. No new send or execution was triggered. Numeric IDs avoid username
resolution changes but still require the current bot's access/posting rights.

Channel presentation: configured channel_labels feed workflow selectors, chat previews and diagrams. The name is displayed while the exact ID remains the saved/submitted option value. channel_name is presentation metadata; no provider operation or policy lookup uses it. Telegram discovery suggestions show the name with ID on hover. Missing names fall back to the ID rather than inventing a channel. Source review only; no tests/build/live sends executed.

## Lossless multipart reports
message_parts.py splits plain-text reports up to60000 Unicode characters into
parts <=3500 UTF-16 units, including [i/n] headers when multipart. Content and
whitespace are preserved, with preferred newline/space boundaries; no ellipsis.
scoped_channels sends sequential parts with3.1-second spacing between parts of
this report and reauthorizes each part. Pacing is not a global rate-limit guarantee.
A logical report is one existing atomic audit claim, not a claim per part. All
parts must return verified receipts before COMPLETED. Receipts retain the first
provider_message_id plus provider_message_ids and parts_delivered. Failures retain
acknowledged-count diagnostics; failed/unknown batches never automatically resume
or resend, even after partial delivery. No individual chunk-progress transaction
or exactly-once guarantee is introduced. Manual test input remains <=3500 chars;
runtime MessageInput permits <=60000. Tests and live calls were not run.

Telegram sendMessage supports bounded text messages; see [Telegram sendMessage](https://core.telegram.org/bots/api#sendmessage). Report splitting prevents the platform truncation previously seen as [Summary truncated]. It does not add PR diff/code access or change the factual scope of generated reviews.

## Running or changing code
Connector tools never clone. Steps that must run or edit code use sandboxed repository workspaces (draft PR only, Docker required, Direct API only). See [repo-workspaces.md](repo-workspaces.md).

## Final answer reliability
Connector completion now uses a strict internal finalization tool, optional single connector-free formatting pass and bounded redacted rejection diagnostics. Required current-policy/receipt checks remain unchanged. See [completion contract](connector-completion.md). No existing failed execution was retried or rewritten.

## AI-19 governed PR operations
Separate PR metadata/diff/check reads, explicit head-pinned comment/review writes and hardened server-only merge evidence/receipts are specified in [PR governance](github-pr-governance.md). Aggregate grants now require narrower read dependencies; no existing grants are migrated. Unknown provider rules, missing current-head review/required CI or strict protected-base enforcement block automatic merge. No live provider/agent verification was executed.
