# Governed workflow release checklist

Use this checklist for the AI-12 epic. For each release candidate, record the
commit, environment and evidence link next to each check. The checklist remains
open until the listed evidence is available.

| Ticket | Required evidence | Current status |
| --- | --- | --- |
| AI-40 | Confirm the model sees only the scoped capability catalog. Verify exact tool/resource selection, checkpoint compilation, and current-policy confirmation after grant revocation. | Merged source and contract evidence; master CI 44787572811 success. Done. |
| AI-41 | Inspect a proposal with dependencies, an approval node, and a blocked resource. Verify setup links, preservation of the draft, correct state after rejected creation, and both locales. | Actual component + real API/SQLite browser checks passed in EN/HE, desktop/narrow; diagnostic presentation corrected. See acceptance record below. |
| AI-42 | Inspect planner and worker instructions against the capability catalog, trust boundaries and diff evidence contract. | Independent Advisor source review passed; synchronized guides and master CI. Done; no claim of model comprehension. |
| AI-46 | Verify the two-organization role matrix, decision and ingress races, and migration from the previous approval schema using a representative database snapshot. | Guarded API audit and nine focused cases passed; current snapshot preservation plus eight populated derived-legacy trials passed. Authentic pre-migration snapshot acceptance remains pending; derived trials do not close that gate. |
| AI-47 | Complete the [browser role and channel matrix](governed-workflow-browser-verification.md). | Journeys defined. Browser results pending. |
| AI-49 | Verify exact identity and callback binding, durable trigger deduplication and expiry, and transport diagnostics. Verify authorized Telegram and Slack test journeys, including Slack Socket Mode, and test relevance classification and dry-run behavior. | Deterministic trigger and chat approval source present. Classifier and end-to-end evidence pending. |
| AI-48 | Review module instructions, release notes and operational guides against the final implementation. Add CI, browser, provider and independent review evidence. | Checklist and guide index assembled. Sign-off pending. |

## Administrator and operator guides

[2026-11-20 acceptance record](governed-workflow-acceptance-2026-11-20.md) records
AI-41/46 verification and AI-51 product approval, including the difference between
derived legacy migration inputs and an original historical customer backup. The
broader AI-47 browser matrix, AI-49 live providers and AI-48 sign-off remain open.

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
