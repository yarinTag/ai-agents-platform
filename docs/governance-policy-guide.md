# P01 capability policy: configuration, recovery and rollout (AI-18)

Use this with the [policy algebra and role matrix](architecture/p01-policy-algebra.md),
[API/schema reference](architecture/p01-governance-api.md) and
[AI-17 UI contract](design/capability-policy-editor.md).
P01 is implemented in the review stack; this is not evidence of deployment or verified
provider/browser behavior. Examples describe authorized future operator actions; none
were performed while writing this guide.

## What an administrator is configuring

Choose a capability (an implemented action), an exact configured resource and an effect.
Keep these separate from base connector grants and human approval. A policy allow can
permit something **within** an existing ceiling; it cannot create a missing tool grant,
credential, adapter or provider permission. An explicit deny at any applicable current
or captured policy layer wins, including when an administrator initiates the run.

The same model applies to repositories and channels. Adding a channel to an organization
does not make all its members platform users, trigger principals or authorized approvers.
Send, listen/trigger and approve are distinct capabilities; the latter channel capabilities
remain unimplemented in this slice.

## Configure through the existing interface

1. Sign in with your personal current platform account. Use the header to choose one
   authorized department. All Departments does not permit a wildcard policy edit.
2. Open `/organization`. An administrator selects **Capabilities & resources**; other
   department members see the same panel in the scoped organization-access page.
3. In **Available access**, inspect exact resource IDs and separate Authoring/Execution
   decisions. Requires approval is conditional. A configured connection is not a live
   provider verification, and an absent row is not a complete reason for denial.
4. An effective department manager can select **Department policy** and **Edit policy**
   to append deny/require_approval restrictions. Saved rules/default cannot be changed
   or removed by that manager. Request an organization administrator for any expansion
   or removal of saved restrictions.
5. An organization administrator can select Department policy or **Organization policy**.
   Confirm the intended layer. An organization restriction affects applicable own-org
   departments; it is not a global/cross-tenant permission.
6. Select a trusted action/connector and exact repositories or channel IDs. Choose the
   effect, then **Apply rule to draft**. There is no free-form execution command, secret,
   wildcard resource or arbitrary tool registration field. Existing subject, workflow,
   branch and validity constraints are preserved/displayed when editing; the basic UI
   does not author new advanced selectors.
7. Choose **Review changes**. Read the complete Before/After document, default and exact
   rule resources. The drawer identifies organization/department target, scope ID and
   revision. A new/changed write/destructive allow rule shows a warning; that warning
   does not confer permission. Unapplied rule edits must be applied or cancelled first.
8. **Confirm and save** is the explicit mutation. It sends the full desired policy with
   expected_revision, and the server validates current personal authority again. A
   successful save refreshes effective access; it does not start or activate a workflow.

Rule/resource options include currently typed-policy-denied configured resources so an
administrator can repair policy. They do not certify credentials, provider status or a
legacy per-operation grant. Unsupported actions cannot be made runnable by policy.
If a previously configured resource disappears, retained rules may need administrator
repair before a full-document update can validate. Do not silently drop unrelated rules.

Managers and administrators can inspect **Department revision history** and expand
saved rule documents. It shows the newest100 department revisions, actual actor IDs
and timestamps. There is no organization-history screen/API or one-click restore action.

## Read-only journeys and identity changes

MEMBER and OPERATOR see effective access; neither edits policy. Members can author/save
new inactive workflows, but base membership does not allow execution or activation.
A global MANAGER whose selected department membership is MEMBER gets the member view.
An organization administrator can select own-org departments without joining each one.

The JWT is a signed session identity, not an authorization snapshot. A token claiming
admin cannot restore a demoted/disabled account. Current database status, organization,
role, membership and selected department are checked on protected requests. Displayed
controls are presentation only: editing a request or unhiding a button cannot grant access.
The `/auth/me` profile recovery path can refresh revoked/deleted header selections.

Switching organization/user/department/effective role clears old rows, errors, drawers
and drafts. Late requests are aborted/discarded. A draft is memory-only; a refresh,
scope change or explicit close can discard it. No policy data, credentials or execution
authority is stored in a URL or browser draft cache by this feature.

## Common failures and recovery

| Observation | Meaning and safe next action |
| --- | --- |
| No department selected | Choose an authorized department in the header; do not fabricate membership |
| Existing department selected, request fails | Refresh current context/profile; do not replace a load error with incorrect join-department advice |
| No available capabilities | Check base grants, exact configured resources, current role and policy separately; empty catalog alone does not diagnose the cause |
| No editor resource options | Check implemented adapters, configured resources and department connector grants; do not install arbitrary code through metadata |
| Action is Not implemented | Keep it unavailable; policy/approval cannot supply the missing adapter |
| Authoring allowed, Execution denied | Authoring a plan is separate from run permission/budget; check current actor and execution admission |
| Requires approval | Use a supported authenticated server gate if one exists; generic conditional sends/reads remain blocked pending P07 |
| HTTP409 while saving | Unsaved draft remains visible; saving is disabled. Close the editor, refresh, fetch the new revision and explicitly review/reapply intended changes |
| HTTP403/404 or role loss | Clear obsolete authority/data and refresh profile/scope. Do not retry as another tenant, agent or connector |
| HTTP422 | Recheck exact resources, retained rules, implemented capability and constraints; preserve unrelated rules and review again |
| Read/connectivity failure | Editing unavailable data is blocked; use refresh. Never infer successful provider verification from a successful catalog request |
| Policy relaxed, old run still blocked | Captured policy still caps that run. Do not rewrite its context/history or automatically retry it |
| External action result unknown | Inspect existing audit/receipts through an authorized path before deciding recovery; no generic automatic retry guarantee |

409 is not an invitation to increment expected_revision until a write succeeds. Read the
new document, account for other actors' changes and create a deliberately reviewed update.
If access changes during an external call, the next guard blocks further work; the platform
cannot recall a request already in flight or claim an external write was rolled back.

## Human approval today

The existing terminal PR workflow approval slice reuses scoped personal manager/admin
decisions, persisted approval state, exact reviewed subjects and fresh head/base-SHA and
readiness checks. Merge requires its explicit legacy grant and current/captured policy;
the model never receives merge authority. See [existing PR approval guide](workflow-pr-approvals.md).

Sending an approval link does not identify the recipient as an authorized approver.
PLATFORM_PUBLIC_URL enables reachable HTTPS dashboard links in that existing path; it
does not install a generic webhook or verified channel callback. Legacy Telegram/Slack
shared-secret callbacks remain disabled. Generic mid-DAG continuation, channel identity
linking, event ingress/listeners and channel-native approval belong to later phases.

## Rollout and rollback constraints

This is a review/deployment checklist for an authorized operator, not an instruction
to execute a migration, change grants or deploy as part of this documentation task.

1. Review the full stack in dependency order. AI-16 and AI-17 draft PRs are not master
   or production just because CI passed. Review roles, existing grants and intended policy
   before authorizing a deployment or any live provider/user acceptance test.
2. Use normal database backup/change controls. The new SQLite initializer adds current
   policy/history tables; existing unset policies resolve to revision0 inherit. No legacy
   grant, credential or saved-workflow backfill is included, and no PostgreSQL/RLS migration
   is claimed. The working application DB was not migrated by these implementation tasks.
3. Deploy compatible API and UI together. The UI requires protected policy resource_options
   from AI-17; an older API can still supply reads but has no complete editor choices.
   Do not substitute secret-bearing connector configuration as an editor fallback.
4. Initially inspect only authorized configuration/catalog data. Provider authentication,
   real actions, browser/keyboard/RTL checks and external messages require their own
   authorized validation. Configuration-only readiness is not a release health check.
5. Introduce restrictive policy deliberately per department. Test MEMBER/OPERATOR read
   journeys, effective-manager append-only behavior, administrator edits, revocation and
   conflict recovery against the actual deployed version before broad rollout.
6. To undo a policy change, an authorized administrator can review an earlier department
   document and submit a new complete CAS update against the current revision. Current
   configured resources/subjects are validated again. Preserve current/history rows;
   do not update SQL history or frozen contexts to simulate an earlier version.
7. Reverting binaries to a pre-policy version may **ignore typed restrictions**. Do not
   treat that as a safe policy rollback. A separately reviewed operational plan must
   control execution/ingress and preserve an equivalent enforced ceiling before any
   downgrade. Retain the additive tables/history; dropping them is not a rollback tool.

New connector-backed runs capture typed-policy documents and workflow revision; historical
runs without those fields keep their older declared scopes plus current policy checks.
No automatic history reconstruction or replay is provided. A policy rollback/expiry does
not release restrictions captured by an existing run. Never create a replacement run just
to evade a deny; a new execution still requires current authorized intent and admission.

## Verification ledger and limits

| Evidence | What it establishes | Limits |
| --- | --- | --- |
| AI-16 final API audit:63 real FastAPI/SQLite cases | Core policy/roles/CAS/frozen and current checks, catalog and exact destination regressions | No model/workflow/provider execution |
| AI-17 API audit:65 cases, including secret-free editor options | Same boundary plus denied-resource choices and org/dept option scoping | No UI interaction or provider calls |
| [AI-17 CI on4aa4728](https://github.com/yarinTag/ai-agents-platform/actions/runs/42288511153) | API/core/security/runtime groups, Dashboard lint/type/logic/build, three image builds and CI required passed | Not a deployment, browser test or live action |
| AI-18 source/document review | Algebra, API field/route inventory, role matrix and guide match the reviewed implementation | Documentation adds no new executable enforcement |

The [isolated audit runner](../poc/tests/run_api_audit.py) copies tracked source to a
disposable directory, uses real FastAPI/SQLite without app lifespan, strips credentials
and disables runtime capabilities. Its [interpreter guard](../poc/tests/api_audit_guard.py)
rejects network/DNS and child processes inside pytest; it supplies no provider/service
doubles. Persisted agent/execution rows used as policy subjects do not imply actual runs.
The outer runner launches the isolated pytest subprocess; the guard applies within it.

Source contracts: [policy API tests](../poc/tests/test_capability_policy_api.py),
[generic HTTP baseline](../poc/tests/test_generic_governance_api.py),
[current access policy tests](../poc/tests/test_access_policy.py) and
[approval contracts](../poc/tests/test_workflow_pr_approvals.py).
No new tests are needed solely to mirror documentation; CI continues to verify the
unchanged implementation. New code/behavior changes require appropriate API regression
coverage. No local app startup, browser, model, Docker, live workflow connector/provider
call, message, workflow execution, credential/grant change, production migration or
deployment was performed for AI-18. GitHub PR/CI and Trello administration are separate
review/project-management operations, not live platform workflow validation.

## מדריך קצר בעברית

1. היכנסו עם חשבון אישי ובחרו מחלקה מורשית בכותרת.
2. פתחו `/organization` ואז **יכולות ומשאבים**. בדקו בנפרד את **יצירה** ו־**הרצה**.
3. מנהל מחלקה יכול לבחור **מדיניות המחלקה** ולהוסיף הגבלות בלבד. הרחבת גישה או
   הסרת הגבלה שמורה דורשות מנהל ארגון. מנהל ארגון יכול לערוך גם **מדיניות הארגון**.
4. בחרו פעולה, חיבור ומשאבים מדויקים, ואז **החלת הכלל בטיוטה**. הרשאה במדיניות
   אינה יוצרת הרשאת חיבור חסרה; אישור אנושי אינו עוקף חסימה.
5. לחצו **סקירת שינויים**, בדקו את היעד והמצב לפני/אחרי, ואז **אישור ושמירה**.
   השמירה אינה מפעילה תהליך עבודה או שולחת הודעה.
6. בשגיאת409 הטיוטה לא נשמרה. סגרו את העורך, רעננו את הגרסה הנוכחית ובדקו מחדש
   את השינוי. אין לדרוס שינוי של משתמש אחר באמצעות ניחוש מספר הגרסה.
7. מעבר למחלקה/חשבון אחר מנקה טיוטות. טוקן ישן אינו משמר תפקיד שכבר נשלל;
   ההרשאות הנוכחיות נבדקות בשרת. חברות בקבוצת Telegram אינה מעניקה הרשאת טריגר או אישור.

בדיקות ה־API אינן הוכחה להפעלה מול ספק אמיתי. בדיקות דפדפן, נגישות, RTL ופעולות
חיצוניות חיות עדיין דורשות אימות מורשה נפרד לפני הצגת המערכת כמאומתת בסביבת ייצור.
