# AI-47 Chrome acceptance and AI-49 Telegram gate evidence

Date: 2026-11-21, Asia/Jerusalem. Baseline: PR60 / master `f7dd468`;
the accompanying change adds localized eligibility and authentication guidance.
This is a partial release acceptance record, not completion of AI-47 or AI-49.

## Authorization and environments

The user authorized isolated browser/SQLite/FastAPI checks. Firefox was unavailable;
the user explicitly selected Chrome-only work for now. Firefox acceptance remains
open rather than changing the original cross-browser requirement.

The Chrome lab runs the actual App, AuthProvider, routes, JWT authentication,
request/response policy, repositories and UI on loopback 5197/8197, using a fresh
SQLite database and the existing explicit Access Lab registration: two organizations,
six departments, 26 accounts, inactive workflows and offline connector fixtures.
No production database, provider key or channel is copied into that lab. The
application lifespan and background workers are off; outbound I/O and child
processes are rejected. API responses are not mocked or intercepted.

Only the temporary bootstrap changes HTTP/SSE base URLs, selects a test locale and
displays an uncaught-error/rejection event counter. The SPA fallback uses that same
bootstrap. No testing bootstrap, password file or database is part of the product.

The live Telegram check had separate explicit user authorization after automatic
approval review initially rejected access to the active installation as beyond the
isolated-only permission. The user then explicitly authorized the one-gate live
check, including persisted workflow/execution/approval data and one Telegram card.
No browser rejection was bypassed. The live sequence is described separately below.

## Observed Chrome role journeys

| Account/context | Observed result |
| --- | --- |
| ORG_ADMIN / Atlas | Signed in through the actual login form. Three own departments were available. Engineering showed only its workflow; switching to Finance showed the Finance workflow and Finance approval. |
| Initiating administrator | Pending approval evidence could be read; no Approve/Reject controls were available to the initiator. |
| MANAGER / Atlas Engineering | Own workflow and approval appeared. A separate eligible manager approved the fixture; the pending row disappeared, Decision recorded appeared and History showed Approved, Dashboard and 1/1. SQLite recorded one vote. No continuation worker or model ran in the lab. |
| Foreign organization deep link | An Atlas manager opened the actual Boreal workflow/execution URL. The page showed Resource not found in the authorized scope, with no foreign history/output. |
| OPERATOR | Own workflows were readable; in-scope operation controls appeared. The organization deep link showed department access instead of organization administration, with an explicit read-only explanation. An approval requiring MANAGER/ORG_ADMIN showed evidence but no decision controls. |
| MEMBER | Own workflows/logs and pending approval evidence were readable. Run was disabled. Organization administration was replaced by read-only department access. The pending-approval explanation was localized in Hebrew; no vote controls appeared. |
| Run-specific approvals | Opening Run approvals from the authorized execution log showed that execution's pending request, not the other execution's approved round. |
| Stale signed-in MEMBER | Deactivated the temporary account while its session existed, then reloaded the bookmarked run. The application returned to Sign In without exposing the run. |
| Unassigned MEMBER | Logged in successfully but no department selector or scoped workflow/approval content appeared. The guard displayed administrator-assignment guidance. Its previously English-only text is now localized. |
| DISABLED MEMBER | Actual login failed and remained at Sign In. Exact DISABLED/INACTIVE failures now have localized account-unavailable guidance. |
| Mixed MANAGER | Engineering and Finance were the only selectable departments. The account is MANAGER in Engineering and MEMBER in Finance. After switching to Finance, only its workflow appeared and Run, Playground, Edit and Delete were disabled despite the global MANAGER label. |
| Partial quorum / repeated vote | An independent manager voted once on a 2-person fixture. It remained Pending at 1/2; reopening evidence showed the personal Approved vote, no decision controls and the Hebrew already-recorded explanation. |

The tested pending-approval text explains current authority and separation of duties,
without inferring a new permission from the account role. A recorded personal vote
has a distinct explanation. The server still owns can_decide, current role/link
checks, quorum and duplicate-vote fencing; this change adds no API permission.

English and Hebrew approval/access/login states were inspected. Hebrew approval
details were also observed at 390×844, with wrapped evidence and readable controls.
The temporary viewport override was reset. The visible error counter remained zero
on the observed instrumented page loads; this is not a claim about every route or
all console warnings. Dependency deprecation warnings are separate from uncaught
application exceptions.

Private screenshots and lab metadata:
`/private/tmp/ai47-evidence-nov21/`. Credentials are outside the repository in a
0600 file under the 0700 evidence directory. Screenshots include admin Finance,
manager approved History, foreign denial, operator read-only, Hebrew member/mobile,
unassigned/inactive account and mixed-department authority cases.

## Findings and remaining AI-47 acceptance

Fixed: missing read-only approval explanation, English-only unassigned-account
guard, English-only authentication progress and exact inactive/disabled failure.
All changes retain server authority. Build/typecheck are recorded with the PR.

Still open: Firefox (explicitly deferred), complete keyboard/locale/responsive
coverage across the full journey matrix, multi-round PR approval/stale selection
journeys, and provider identity/trigger paths outside the one Telegram gate below.
Some existing hub/navigation/log labels remain English in the Hebrew UI; the
observations above do not establish full-application Hebrew acceptance. AI-47 must
remain In Progress until those original criteria have appropriate evidence.

## AI-49: real Telegram approval and one continuation

Created one explicitly authorized test initiator with OPERATOR role in the exact
existing test department, no administrator role and no new MCP grants. Its generated
password is private and never included in the report. The existing linked ORG_ADMIN
remained the independent human approver.

Used the real application routes through FastAPI TestClient with normal password
login/JWT and production authorization. No lifespan was started. During admission,
a Python audit guard rejected all subprocess/network attempts, making inference
or direct external effects impossible in that process. Created one inactive,
webhook-disabled, unscheduled workflow containing only a DAG approval checkpoint.
The real execution API suspended it at WAITING_APPROVAL. The private test script's
post-admission assertion initially used the wrong task column; it was corrected
to task_run_id and the existing execution was inspected, not recreated.

The existing Telegram consumer held its lock. The custom send driver exited before
claiming or sending anything; no second poller was launched and no webhook was
changed. The installation's existing governed worker delivered the queued card to
platform_summary_test, exact channel `-1004464346735`, message **49**. The user
clicked Approve on that real provider card. No synthetic callback or chat-text
assertion was used as approval authority.

| Persisted evidence | Observed result |
| --- | --- |
| Workflow | `wf_f008f21864`, revision 1, inactive, webhook disabled |
| Execution | `wf_exec_1d8ab21642b0`, COMPLETED |
| Approval | `dga_64bd01091f43469fb799fdd65e920a68`, CLAIMED (approved checkpoint consumed) |
| Decision | Exactly one callback receipt and one vote; actor matches the linked Telegram user and differs from initiator |
| Original message | DELIVERED, message49, rendered APPROVED after acknowledged edit; terminal rendering removes action controls |
| Inference/effects | Zero model task references, zero input/output tokens, cost 0; no GitHub operation or merge |
| Dashboard | Actual live execution logs show Completed, Telegram decision source, actor/principal separation and card receipt49 |

Private receipt and screenshot: `/private/tmp/ai49-live-approval-test/result.json`
and `completed-logs.png`. No raw callback body, action token, bot credential or
encrypted key is published. The temporary initiator was set INACTIVE after the
completed test and audited; the inactive workflow and decision history are retained.

This passes the configured Telegram approval-only happy path. It does not establish
live wrong-actor/replay/restart handling, Telegram trigger admission, Slack/Socket
Mode or model relevance quality. Those remain AI-49 acceptance work. There is no
new Send/Listen/Approve grant or permission to activate unrelated workflows.
