# Governed workflow browser verification (AI-47)

Use an isolated checkout and a disposable organization/database, or the approved
Access Lab environment. Obtain role credentials from its private credential
file. Use only the approved test connector, channel, and repository for any
provider action. Record provider-less journeys separately from connected tests.
Never attach tokens, chat contents, credentials, or raw ingress payloads.

## Role and department journeys

| Account | Browser actions | Expected result |
| --- | --- | --- |
| Organization administrator | Open Organization, inspect department capabilities, then open MCP Hub and Workflows. Switch Engineering to Finance. | Department lists, grants, connector references, execution history and approvals reflect the selection. A bookmarked run from another organization is inaccessible. |
| Department manager | Open a pending gate and review its evidence. Inspect channel trigger setup and preview a matching and nonmatching sample. | In-scope current roles can act. The preview shows the matched parameters or no match and creates no execution. A stale gate shows a conflict and preserves the next gate. |
| Department operator | Open Workflows, inspect catalog and logs, then try the manager actions. | In-scope operation is visible. Editing trigger policies and managing workflow decisions require the applicable authority. |
| Department member | Open Create with AI and confirm an eligible proposal. Try a blocked tool/resource combination and a direct manager deep link. | Eligible workflows are saved inactive. Unavailable resources have setup guidance. Approval mutation and activation are unavailable to this role. |
| Unassigned and inactive accounts | Attempt to open a bookmarked workflow and an approvals link. Repeat with a session issued before revocation. | No scoped data or action is exposed. The UI handles the server response without an uncaught error. |

## Channel and approval journeys

1. In Create with AI, review a plan with parallel predecessors, an approval node
   and a downstream action. Check that the preview shows every dependency and
   points to the specific unavailable resource when one is rejected.
2. Revoke an exact test grant after generating the proposal, then click Create.
   Verify that the updated validation appears in the preview, the proposal is
   no longer ready, and no workflow is created.
3. In identity linking, issue a test challenge and follow the provider's
   confirmation path. Verify the browser status and that only the intended
   organization and account expose the link.
4. In Workflows → Approvals, open Pending and History. Open the same execution
   through Workflow Logs → Run approvals and check that the list is scoped.
   For a multi-PR test execution, verify that the next pending round appears
   after the first decision and that the prior row retains its original PR and
   receipt. A repeated decision against the prior ID must leave the next
   approval pending.
5. With a live approved test destination, verify that the Telegram card
   acknowledges the decision and removes action buttons while processing. A
   subsequent card identifies only the next PR. Record Slack journeys only for
   functionality supported and configured in the test environment.

## Browser, locale and evidence

Repeat the core journeys in Chromium and Firefox at desktop and narrow widths
(for example 1440×900 and 390×844). Repeat preview, approval, and department
switching in English and Hebrew. Check RTL layout, keyboard focus/activation,
readable wrapped resource IDs, and that PR links and SHAs stay LTR. Record
the commit, browser, viewport, locale, role, department, expected and observed
result, and console exceptions. A browser pass requires actual observations;
API and unit checks provide separate evidence.

Status: partial Chrome role/access/approval journeys were executed on 2026-11-21;
see [observations and remaining coverage](governed-workflow-chrome-acceptance-2026-11-21.md).
Firefox was explicitly deferred by the user. This does not close the full AI-47
matrix, remaining localization/keyboard coverage or provider-trigger journeys.
