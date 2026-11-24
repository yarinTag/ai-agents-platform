# AI-47 additional Chrome acceptance — 2026-11-23

Baseline: master `27c21a005186b24432f2d5323988ce3b87c62c28` (PR65).
This record supplements the [earlier role matrix](governed-workflow-chrome-acceptance-2026-11-21.md).
It does not close AI-47, AI-49 or release sign-off.

## Isolated environment and limits

Actual React App, routes, authentication and FastAPI/SQLite on loopback 5199/8199,
using a new Access Lab with two organizations, six departments and 26 accounts.
Application lifespan/workers are off; an audit guard denies outbound network and
child processes. No production configuration or credentials were copied. HTTP
responses were not intercepted. Private fixtures, credentials and screenshots
remain under `/private/tmp/ai47-final-evidence-nov23`, outside source control.

Authoring uses explicitly stored model-result fixtures, not model inference. The
first fixture omitted model defaults and caused a caught render exception when
reading `depends_on.length`. Canonicalizing all three fixtures through the real
`ChatWorkflow` model fixed the invalid setup. This is recorded as a fixture error;
it is not evidence that generation or arbitrary legacy result handling passed.
Subsequent observations use the canonical generated-result shape.

## Observed journeys

| Journey | Actual observation |
| --- | --- |
| Manager trigger preview, EN | Keyword `review` matched mixed-case input; unrelated input did not match. Keyboard activation worked. Saving fixed the manager principal, revision 2, with relevance disabled. Preview created no execution; workflow stayed inactive. |
| Sequential checkpoints, HE | Actual engine suspended before first gate. Independent manager approved through the inbox using Return. A direct isolated engine continuation claimed it and created the second gate in the same run. History retained first vote; replay to the first ID returned 409 and second remained pending. |
| Run-scoped approvals, HE / 390×844 | Logs and Run approvals showed the selected execution and second gate. Prior output wrapped readably. Rejecting the second gate via keyboard recorded REJECTED and the run failed without inference. |
| Member proposal, HE | Four steps displayed parallel predecessors, named dependencies, continuation policy and authorized exact repository/tool. Create saved one inactive workflow. Run remained disabled for Member; no generation or workflow execution occurred. |
| Member blocked proposal, HE | Forbidden repository remained visible, creation disabled, localized correction summary and expandable original diagnostic. |
| Revocation after preview, EN | Revoked the exact disposable GitHub grant after preview. Create-time validation replaced Authorized with Setup required, retained proposal/dependencies, displayed access/MCP links and disabled creation. No corresponding workflow was created. |
| Identity enrollment, EN | Member issued an actual challenge in Linked accounts. A fixture-secret-authenticated request passed the real provider proof receiver, with fixture sender777001. Browser polling showed the subject; Return on Confirm account created a Verified link. This is offline proof-path evidence, not an actual Telegram delivery. |
| Identity personal/management scope, EN | A different manager had no personal link; Department linked accounts showed the Member link. No other account inherited the personal identity. |
| Multi-PR successor/history, EN | Real persistence `finish` boundary consumed a recorded fixture receipt for PR20 and queued PR23. Actual inbox showed PR2 of2 with its pinned head/base and cumulative PR20 receipt. History retained PR1 of2 with its original PR20 SHAs and disabled decisions. No GitHub reads or merges occurred. |
| Old PR decision | Real authenticated HTTP request against the first ID returned409; successor ID and PENDING state remained unchanged. Rejecting PR23 through the actual HE confirmation preserved PR20's recorded fixture receipt. |
| PR evidence, HE / 390×844 | RTL text, LTR PR links and wrapped SHAs were readable; scrolling reached both decision buttons. Keyboard opened review and rejection. |

The PR receipts above are **fixture data**, never proof of a provider merge.
The direct engine continuation is not evidence of automatic worker recovery.
Existing independent live provider evidence remains in the Telegram records.

## Finding corrected in this change

Terminal approval expiry used the browser's default locale, and Popconfirm showed
English OK/Cancel under Hebrew. WorkflowApprovalPanel now uses the selected locale
for expiry and explicit EN/HE confirm/cancel labels. Approval IDs, submission locks,
permission checks and decision behavior are unchanged.

## Remaining acceptance

Core hub/navigation/log labels still contain English in the Hebrew interface, so
full Hebrew coverage cannot yet be asserted. Remaining matrix observations and
the combined live Telegram trigger/decision/continuation still need completion.
Firefox and unavailable Slack remain explicitly deferred by the user; that is
not a cross-browser or Slack pass. Live model classification was requested but
awaits an explicit total cost ceiling before any paid request.

The active application is reachable but signed out. Saved credentials belonged
to the earlier temporary initiator, now INACTIVE after cleanup; actual sign-in
correctly rejected it. No account was reactivated and no credential was reset.

Validation: production build and `tsc --noEmit` passed for the two-file locale
change. Existing Vite chunk-size warning remains. No live provider call, model
request, production grant or workflow change was made by this acceptance pass.

Post-fix Chrome verification: the Hebrew dialog displayed ביטול / אישור ההחלטה, and expiry displayed 24.11.2026, 21:12:15 under the selected Hebrew locale. The confirmation was cancelled without changing that new fixture gate.


## Further acceptance — 2026-11-23
Workflow hub/list/run controls, shell navigation/logout/department labels and logs now use EN/HE dictionaries; Ant Design receives the selected locale/direction, including pagination. Narrow headers wrap, tables scroll, log titles wrap and run filters stack below sm. Collapsed navigation retains localized accessible names. Browser observed readable HE hub/logs at390x844 and no page-width overflow. SQLite UTC step timestamps now agree with audit/run timestamps; second gate ended21:02:56 throughout. Raw enum values and provider/fixture content remain unchanged. Production build/typecheck and167 existing frontend tests passed before the final narrow-layout correction; final checks are recorded in the publication PR.


Post-change verification: 167 existing frontend tests, final production build/typecheck and lint passed (existing lint/deprecation and bundle warnings remain). 28 ingress/trigger tests passed, including two new exact-event isolation contracts. Fresh-tab ORG_ADMIN signed in through the HE form, dismissed optional setup and switched Engineering→Finance by keyboard; only Finance workflow appeared, history count0. A stale browser handle stopped responding to clicks; a new tab on the same browser restored normal interaction, so unchanged trees from that handle were not counted as product failures or passes. Full-application legacy runtime/provider descriptions are outside these governed-flow observations.
