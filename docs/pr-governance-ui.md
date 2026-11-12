# AI-20: PR scopes and evidence UI

The workflow step editor shows required declared operations and exact repository/connector references. Workspace write means clone_repository + open_pull_request and publishes a draft. PR read, comment, review and human-approved server merge are separate. Requirements are descriptive, not an effective grant or provider-connectivity test. Legacy implicit scopes do not acquire new PR writes. No workflows, grants or credentials are modified by this feature.

Execution logs and inspection render persisted PR audit evidence independently of model output. The existing detail API adds step_runs[].pr_evidence, capped at 32 per task, with exact task/agent/current connector organization matching. The projection supports GitHub read, draft creation and comment/review records; it omits arbitrary arguments, bodies, patches, URLs and configuration. Removed audit dependencies may leave historical evidence unavailable. Existing scoped approval GET provides merge receipts. No new mutation endpoint or schema migration.

PR links use validated owner/name and positive integer PR identity on fixed github.com. Pinned comparison links require both complete SHA identities; unavailable base evidence instead offers an explicitly labeled Current PR diff, without fabricating a pinned comparison. Displayed review/CI/base readiness is historical and does not authorize execution. Legacy proof, incomplete results and blocked evidence are explicit. Raw runtime events remain available through the existing JSON toggle.

Approval views show reviewed HEAD/base, personal-approval semantics, expiration, read-only role explanation, receipt audit ID, platform approver, merge SHA and timestamps when recorded. Platform approver identity is distinct from the GitHub credential actor. COMPLETED requires a recorded acknowledgment; approval alone is not a merge receipt. STARTED/UNKNOWN instruct administrator reconciliation with no automatic resend; NOT_DISPATCHED calls for blocker resolution and a fresh authorized review. Current server role/policy, exact revisions and fresh evidence remain authoritative.

Recovery copy covers reviews, base drift, required CI, unknown/unsupported protection, draft/closed/conflicting PRs and incomplete evidence. Strict classic branch protection with administrator enforcement remains the supported automatic-merge slice; UI does not relax it. English/Hebrew copy and logical layout/identifier isolation support RTL.

Source owners: components/workflows/PrPermissionSummary.tsx, PrEvidence.tsx, WorkflowApprovalPanel.tsx, StepEventTimeline.tsx; pages/WorkflowLogs.tsx and WorkflowExecutionDrawer.tsx; backend/api/workflow_pr_evidence.py. Backend action contract: [AI-19](github-pr-governance.md).

Verification: 81 isolated real API/SQLite contracts passed (including eight new AI-20 cases); API contracts cover scoped audit projection and existing governance/approval contracts. Frontend lint/types/tests/build run through GitHub CI only. No local UI/browser/startup, agent/model/provider calls, live messages, PR writes or merges are used for verification. UI rendering and live provider outcomes are not established by API tests.

Checks-only diagnostics preserve files_included=false and explicitly remain incomplete approval proof even when their CI facts pass; the UI never displays a full-review readiness badge for that result. API contracts assert this field survives the safe projection.

For operational decisions based on these views, use the [AI-21 recovery runbook](pr-governance-runbook.md#recover-a-blocked-or-interrupted-run).
