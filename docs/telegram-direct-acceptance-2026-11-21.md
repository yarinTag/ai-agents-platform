# Telegram direct acceptance — 2026-11-21

The user requested direct Telegram verification and deferred Slack because no
Slack installation is available. Slack is outside this acceptance pass, not passed.
This record supplements the Chrome/live-card record and does not establish full
AI-47 browser acceptance or AI-48 release sign-off.

## Source and isolation

Source: PR61 head `dab2859bc7168b9d67e9deb97f6897dc9ee55b73`, equivalent merged
master `7c6aeaf3c7088bc1e58ca700bb20d275f8e8511c`, plus the two test files in this PR.
Actual FastAPI routes, JWT/current-policy checks, SQLite repositories and workflow
engine are used. Databases are disposable under a private temporary directory.
No service mocks, response interception, application lifespan, external HTTP,
provider credentials or inference exist in these test fixtures. A Python audit
hook rejects network/DNS and child process attempts. --noconftest excludes the
legacy default-database reset fixture. The source clone has its own default data.
No production database rows, bindings, grants or workflow activation were changed.

## Executed results

- Existing Telegram/shared ingress, relevance and PR approval suites:
  **39 passed**, four Slack-specific cases deselected, six dependency warnings.
- New targeted Telegram suites: **26 passed**, six dependency warnings.
- Warnings are Starlette/httpx and Pydantic deprecations; no failing test.
- JUnit: private /private/tmp/ai49-direct-evidence-nov21/results.xml and
  targeted-results.xml. Temporary scripts/databases and credentials are not committed.

| Direct scenario | Result |
| --- | --- |
| Unlinked, initiator, member, foreign-organization or inactive approver | No vote, no callback decision receipt, no resume |
| Revoked membership/binding, wrong channel/message, changed workflow revision | No vote or continuation |
| Telegram Reject | Execution FAILED, terminal REJECTED card state, no continuation |
| Expiry and database reopen | TIMED_OUT, FAILED execution, no continuation |
| Two distinct concurrent callback IDs | One decision and callback receipt, one personal vote |
| Database reopen after approval | Durable approved gate found, one resume claim; next reopen cannot reclaim |
| Approver revoked after vote | Resume denied; failed closed without model or external action |
| Preview | Match explanation, zero execution records |
| Matching Telegram message | Actual consumer/engine reaches WAITING_APPROVAL; zero model tasks |
| Provider event retransmission and reopened consumer | One dispatch and one execution |
| Second matching event after hourly capacity | No second dispatch |
| Unrelated text, bot, unlinked sender | No execution |
| Inactive sender/principal/workflow or revoked trigger binding | No execution |
| Revision/principal/lease/text expiry after reservation | Admission denied before start |

The reopen cases prove durable SQLite recovery contracts, not a forced crash of a
live provider consumer. Provider event bodies in direct tests are signed fixtures;
these results are not described as live human Telegram traffic.

## Actual provider readiness and deployment limit

Read-only calls through the real fixed-host Telegram adapter: getMe,
getWebhookInfo, getChat and getChatMember for exact destination -1004464346735.
The bot is valid, is an administrator with can_post_messages=true, has no webhook
and reported zero pending updates. The configured transport is polling. No
getUpdates, send, edit, webhook replacement or credential change was made in this
readiness pass. The previously authorized card49/live independent vote remains
successful evidence in governed-workflow-chrome-acceptance-2026-11-21.md.

**The configured destination is a broadcast channel (`type=channel`), not a group.**
Telegram channel posts do not provide the personal verified sender required by
the current trigger contract. The adapter intentionally accepts personal MESSAGE
updates and rejects anonymous/forwarded/bot authority. Do not weaken identity checks
or enable blanket channel attribution to make a trigger test pass. A group with
the bot and an independently linked active platform operator is required for the
live matching/nonmatching trigger journey. Full group text visibility also needs
appropriate bot permissions/privacy setup. The bot currently reports
can_read_all_group_messages=false; a correctly addressed command or administrator
membership may supply the intended messages without blanket history access.

The live dashboard at localhost:5173 was unavailable during this pass. No production
application or global workers were started merely to overcome that observation.

## Remaining gates

- Telegram live group input: one matching and one unrelated message from a linked
  authorized person, actual polling/dispatch provenance, and no duplicate run.
- Optional live model relevance/uncertain outcomes remain unverified; direct tests
  prove validation/admission and budget handling, not model quality.
- AI-47 still needs remaining Chrome keyboard/locale/authoring/identity journeys;
  Firefox remains explicitly deferred by the user.
- Slack/Socket Mode live acceptance is deferred, with its own follow-up tracking.
- AI-48 sign-off remains dependent on the scoped acceptance gaps and review.

Keep tickets with these unmet criteria open. The 65 passing direct cases remove
specific evidence gaps; they do not certify an untested deployment path.
