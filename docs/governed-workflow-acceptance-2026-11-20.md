# AI-41 / AI-46 / AI-51 acceptance record

Date: 2026-11-20, Asia/Jerusalem. Baseline source:
`435533849732b0ad637ca48b24c853bd431f4442`, plus the localized validation
disclosure and documentation changes in the accompanying commit.

The user explicitly authorized isolated browser and SQLite/FastAPI checks only.
No model inference, messages, workflow activation, provider writes or deployment
were performed for this acceptance. The active application's database and grants
were not changed. An isolated fixture created one inactive workflow and zero
execution records. Existing unrelated local Dependabot-policy changes were excluded.

## AI-41: proposal preview and current-policy rejection

Used the actual `WorkflowChatModal`, `useWorkflowChat`, translations and HTTP client
from the application, served by Vite on loopback port 5189. The real Workflow Chat
FastAPI router on loopback port 8189 used a disposable SQLite database and actual
JWT authentication. No application lifespan, scheduler or runtime adapter ran.
No service mocks, intercepted responses or model generation were used. A READY
proposal was seeded as test input using the existing SQLite contract, rather than
asking a model to generate it. The fixture had no real credentials or provider URLs.

| Requirement | Observed evidence |
| --- | --- |
| Dependencies and approval | Four steps: two independent repository inspections, a dashboard checkpoint depending on both, and a final step depending on the checkpoint. Both dependency labels and the approval badge appeared. The preview uses a dependency-labelled step list, not a claim that parallel steps execute serially. |
| Capabilities | Exact repository/tool pairs appeared with Authorized in this preview badges. After explicit department revocation, the real create endpoint returned validation rejection and the three relevant resource badges changed to Setup required. |
| Guidance | Localized explanation and links to `/organization` and `/mcp` appeared after rejection. Both links open separately with `noopener noreferrer`, preserving the current draft. |
| Preservation | The same proposal, four steps and dependency labels survived reload through the private workflowChat ID and remained visible after rejected creation. The create control became disabled. |
| Successful creation | The positive fixture created exactly one inactive workflow; SQLite confirmed one inactive workflow and zero executions. The real success message appeared. |
| English/Hebrew/RTL | Both locales displayed translated preview, dependency, checkpoint, capability, setup and rejection labels. Hebrew reversed direction; repository/tool identifiers stayed LTR. Both layouts were inspected at normal desktop width and 390×844, with wrapping and vertical scrolling. |
| Raw diagnostics | Found raw English server errors in the primary Hebrew warning. They now appear only in a collapsed, localized Technical validation details disclosure with wrapped LTR content. Open/close and preservation were observed after the change. |

One fixture correction matters: deleting a GitHub department override restores
inheritance, so it is not revocation. The first attempt correctly created an
inactive workflow under inherited permissions. The negative test then used the
actual `revoke_department_mcp_access` repository operation to persist a denial;
subsequent create attempts in both locales were rejected with no additional workflow.

Private screenshots are under
`/private/tmp/ai-platform-acceptance-evidence/browser/`:
`ai41-en-ready.png`, `ai41-en-created.png`, `ai41-en-blocked.png`,
`ai41-he-fixed.png`, `ai41-he-mobile.png`, `ai41-he-mobile-setup.png`,
`ai41-en-mobile.png`. The pre-fix Hebrew screenshot is retained as a finding,
not final acceptance evidence. The temporary viewport override was reset.

Production build and `npx --no-install tsc --noEmit` passed after the UI change.
The build retains the existing large-chunk warning. This is component/real-API
browser acceptance for AI-41, not the full role, browser-engine, live channel or
application-navigation matrix required by AI-47. No model-quality claim is made.

## AI-46: isolation, races and populated migration rehearsal

The API-only audit runner uses a disposable tracked-source copy, real FastAPI
and SQLite, and a fail-closed Python audit hook forbidding external network/DNS
and child processes inside pytest. Runtime capabilities are disabled. The earlier
baseline run passed 110 tests in 76.16 seconds. Coverage includes two organizations,
three departments, all four roles, mixed memberships, unassigned/disabled users,
cross-tenant reads/mutations, catalog narrowing, grant revocation and verified ingress.

A focused final run passed nine cases in 5.97 seconds:

- `test_approval_department_and_role_matrix`: six organization/department cases;
  foreign admins, wrong departments, MEMBER/OPERATOR decision denial, stale tokens
  after account deactivation and actual manager attribution.
- `test_concurrent_dashboard_decisions_claim_the_gate_once`: exactly one claim.
- `test_simultaneous_verified_telegram_receipts_stage_one_event`: one durable
  receipt/outbox pair for concurrent copies.
- `test_legacy_approval_migration_preserves_card_and_merge_receipt`: data,
  idempotency, FK cascade and one-live-round constraint.

These counts overlap the earlier audit; they are not 119 distinct tests. The
six warnings in the final run are dependency deprecations. Reports:
`/private/tmp/ai-platform-acceptance-evidence/ai46-final/api-audit.{xml,log}`.
Merged baseline CI: https://github.com/yarinTag/ai-agents-platform/actions/runs/44787572811.

### Existing-data migration procedure and result

1. Open the existing local database with SQLite `mode=ro` and use the backup API
   to make a consistent private snapshot. Private directory permissions 0700;
   database files 0600. No row contents, callback tokens or credentials are published.
2. Apply the current approval initializer twice to the full current-schema copy:
   all eight approvals and eight delivery records remain byte-for-byte equal at
   row level; integrity and foreign-key checks pass.
3. No original populated pre-sequence approval backup was available. Reconstruct the predecessor
   approval tables verbatim from committed source `504a622`, retaining all other
   database tables. Populate legacy columns from the actual snapshot rows without
   editing their values. The old schema allows one row per execution; partition
   into eight private trials so every original approval and its delivery is tested,
   including rows that cannot coexist under that historical uniqueness constraint.
4. For each trial, run the real current `workflow_approvals_schema.initialize`
   twice. Compare every legacy approval field and complete delivery row, then hash
   all 64 other tables before/after. Require default sequence fields, repeatability,
   `foreign_key_check=[]` and `integrity_check=ok`.

Result: eight/eight trials PASS, all eight approvals and eight deliveries covered,
all 64 unrelated tables unchanged in every trial, including authorization records.
Private reproducible script, predecessor source, reports and databases:
`/private/tmp/ai-platform-acceptance-evidence/populated-legacy/`.

This is explicitly a populated, derived legacy-schema rehearsal using real existing
data, not a newly discovered historical customer backup. The independent Advisor
review identified that split trials alone do not test one complete representative
legacy dataset. The subsequent combined snapshot check below closes that gap;
it does not pretend to be an original historical customer backup.
It does not certify unknown customer
installations, PostgreSQL cutover, provider delivery or all future schema migrations.
Each customer upgrade still requires its own isolated backup/restore rehearsal.

### Authentic older baseline snapshots

A subsequent Git-history search found two authentic SQLite snapshots in initial
commit `3394c7f` (2026-09-20): `poc/data/agents_platform.db` (one agent and one
project) and `poc/backend/data/agents_platform.db` (seven agents). They predate
organization, channel and approval tables entirely. Extracted the original Git
blobs into private files and initialized disposable copies with the current real
DatabaseManager three times. Every original row/column value was preserved; all
tables were unchanged on repeated initialization; integrity and FK checks passed.
No organization, user, department MCP grant or channel binding was created.

Report: `/private/tmp/ai-platform-acceptance-evidence/historical/report.json`.
These are actual full older database migrations, distinct from the derived
approval-schema trials. They still contain no previous-version approval records
and do not alone substitute for the specific populated pre-sequence approval
snapshot required by the release checklist.

### Combined representative previous-approval snapshot

Following independent review, built one full representative database with the
verbatim predecessor approval schema and six distinct existing executions, their
six approval rows and six matching delivery records together. Selected the earliest
round of each execution to respect the predecessor's single-approval uniqueness;
all selected legacy values were copied unchanged. This includes APPROVED, FAILED
and REJECTED decisions. The eight earlier trials separately cover every original
row, including later rounds that cannot coexist in that old schema. All 64 other
existing tables, including authorization and workflow context, remain intact.

The input database passed FK validation before migration. The real current
initializer ran twice: all six approval rows' legacy fields, all six delivery rows
and the hashes of all 64 other tables remained unchanged; repeat initialization,
integrity and foreign-key checks passed. A rolled-back savepoint then verified:
an ordered second round is accepted, two simultaneously live rounds for one
execution are rejected, and deleting the parent execution cascades to approvals
and deliveries. After rollback the verified complete dataset was unchanged.

Result: PASS. Private script and result:
`populated-legacy/verify_combined.py` and `populated-legacy/combined-report.json`
under the evidence directory. This is a documented reconstructed representative
previous-schema snapshot, not an authentic historical backup. It supplies the
full-dataset migration evidence missing from the split trials, without changing
the acceptance criteria. Customer-specific upgrade rehearsals remain required.

Final independent Advisor source review verified the combined script, report and
old/current initializers and found the representative-snapshot gap closed. This
explicitly supersedes the earlier pending assessment based only on split trials.
The reviewed current backend is the baseline SHA at the top of this record;
the predecessor is `504a622`. The reviewer did not rerun tests or certify a rollout.
No PostgreSQL cutover, live provider operation or future migration is accepted here.

## AI-51: accepted product decision

[Pilot decision](architecture/ai-51-pilot-decision.md) contains the selected profile,
data routes including failure/update paths, hostile-code boundary, tenant/domain
and continuity policy, service ownership, key custody, bounded upgrade rollback,
numeric targets and named accountable roles for remaining installation gates.

Yarin explicitly approved the concrete pilot baseline and targets in this chat.
Independent architecture Advisor reviewed the packet and deployment/sandbox models.
Its three clarifications were incorporated, along with unreachable-node and frozen
benchmark rules. The approval record is in the packet. Closing this decision ticket
does not close AI-52/53/54/55/56 or establish deployment, HA, model or Air-Gap support.
