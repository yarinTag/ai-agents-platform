# Governed workflow release checklist

Use this checklist for the AI-12 epic. For each release candidate, record the
commit, environment and evidence link next to each check. The checklist remains
open until the listed evidence is available.

| Ticket | Required evidence | Current status |
| --- | --- | --- |
| AI-40 | Confirm the model sees only the scoped capability catalog. Verify exact tool/resource selection, checkpoint compilation, and current-policy confirmation after grant revocation. | Merged source and contract evidence; master CI 44787572811 success. Done. |
| AI-41 | Inspect a proposal with dependencies, an approval node, and a blocked resource. Verify setup links, preservation of the draft, correct state after rejected creation, and both locales. | Actual component + real API/SQLite browser checks passed in EN/HE, desktop/narrow; diagnostic presentation corrected. See acceptance record below. |
| AI-42 | Inspect planner and worker instructions against the capability catalog, trust boundaries and diff evidence contract. | Independent Advisor source review passed; synchronized guides and master CI. Done; no claim of model comprehension. |
| AI-46 | Verify the two-organization role matrix, decision and ingress races, and migration from the previous approval schema using a representative database snapshot. | Guarded API audit and nine focused cases passed; two authentic older baseline upgrades, current preservation, eight per-row trials and one complete reconstructed previous-schema snapshot passed. Six approvals/deliveries and all 64 other tables preserved; constraints verified. See provenance/limits below. |
| AI-47 | Complete the [browser role and channel matrix](governed-workflow-browser-verification.md). | Partial Chrome role, department, denial, pending/history and Hebrew mobile evidence recorded 2026-11-21; three guidance defects fixed. Firefox explicitly deferred; remaining full-matrix/localization/keyboard coverage is open. |
| AI-49 | Verify exact identity and callback binding, durable trigger deduplication and expiry, and transport diagnostics. Verify authorized Telegram and Slack test journeys, including Slack Socket Mode, and test relevance classification and dry-run behavior. | Real Telegram gate passed: one linked independent approver, one callback/vote, one completed continuation, edited message49, zero inference. Slack/Socket Mode, trigger, negative/restart and model relevance acceptance remain open. |
| AI-48 | Review module instructions, release notes and operational guides against the final implementation. Add CI, browser, provider and independent review evidence. | Checklist and guide index assembled. Sign-off pending. |

## Administrator and operator guides

[2026-11-20 acceptance record](governed-workflow-acceptance-2026-11-20.md) records
AI-41/46 verification and AI-51 product approval, including the difference between
reconstructed representative migration inputs and original historical backups. The
broader AI-47 browser matrix, AI-49 live providers and AI-48 sign-off remain open.

[2026-11-21 Chrome and Telegram observations](governed-workflow-chrome-acceptance-2026-11-21.md)
record partial role-matrix results, fixes, the separate live authorization boundary,
the real provider receipt and outstanding acceptance work. These partial results
do not mark AI-47/49 or release sign-off complete.

- [Capability policy](governance-policy-guide.md) and [binding permissions](channel-bindings.md)
  describe setup and exact department grants. Configure Send, Listen and Approve
  individually.
- [Ingress setup](webhook-ingress.md) covers Telegram webhook/polling, Slack
  webhook and Socket Mode. Use a dedicated test installation and test channels
  for acceptance. Check provider scopes and membership separately.
- [Identity enrollment and recovery](identity-proof-runbook.md) and
  [interactive approvals](interactive-channel-approvals.md) cover verified user
  decisions, expiry and dashboard fallback.
- [Workflow authoring](workflow-chat.md), [channel triggers](channel-trigger-policy.md)
  and [DAG approvals](dag-approvals.md) describe the user-facing execution contract.
- [PR governance](github-pr-governance.md), [operations](operations-runbook.md)
  and [credential and state recovery](disaster-recovery.md) cover approvals,
  merge receipts and incident response.

## Release and rollback

Capture and verify an offline database backup before applying the approval
migration. It preserves existing decisions and delivery receipts and replaces
the single-approval constraint with an ordered sequence plus a unique active
approval. An older server expects one row per execution. Coordinate startup
during rollout. Before restoring a backup, reconcile every post-backup provider
decision, merge receipt and dispatch; restore does not undo a provider action.
Use the incident runbook for unknown writes or interrupted resolutions.

Require CI results for the final PR heads, observed browser results and a
record of any authorized provider checks. Record independent review findings,
their resolution and the base/head of each stacked PR. A green automated
suite alone does not establish that a provider installation is configured or
that the approved production channel can deliver.

## Telegram-only direct acceptance — 2026-11-21

The user deferred unavailable Slack. [65 direct passing cases](telegram-direct-acceptance-2026-11-21.md)
cover callback denials/races/recovery and deterministic ingress-to-engine dispatch.
The existing provider destination is a broadcast channel: approval cards work,
but a personal-sender live trigger requires a Telegram test group. Live relevance
and remaining Chrome journeys are still open; AI-47/49/48 are not closed by these
direct tests. No production grants or bindings were changed.

## Real Telegram group input — 2026-11-21

[Live-group input evidence](telegram-live-group-acceptance-2026-11-21.md) now proves
actual provider matching/nonmatching messages, verified sender provenance and
hourly capacity through the real engine on disposable backend state: three events,
one completed execution/vote, no inference. This supersedes the earlier lack of a
usable group. The earlier card49 proves Telegram approval on the active installation;
the new run's independent decision used the lab dashboard API. Active deployment
trigger configuration/worker acceptance and optional live model relevance remain
unverified; remaining AI-47 journeys and AI-48 sign-off stay open.

## Active Telegram admission and rollback

The later explicitly authorized test reached WAITING_APPROVAL in the active DB
with one real group command, one execution, denied self-approval403 and no inference.
The dashboard was unavailable; the gate expired during an interruption. Test-only
cleanup verified inactive principal/workflow, disabled exact binding and exact
connector restoration. See the later section of the live-group evidence record.
Independent decision/continuation was not completed for this run; no ticket is
closed on the strength of an expired test.
