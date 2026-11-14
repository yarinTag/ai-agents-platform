# Test source organization

The user currently prohibits running tests, builds, lint, type checking or application startup. The source refactor described here was not executed and collection/runtime compatibility remains unverified.

## Hierarchical orchestration cases

The former oversized `test_hierarchical_orchestration.py` is grouped by responsibility while retaining test function names/bodies and default function fixture scopes:

- `test_hierarchical_orchestration.py`: delegation/propagation (A), completion guard (C), failure/retry (D), dependencies/concurrency (E), restart recovery (F).
- `test_hierarchy_clarification.py`: supervisor resolution (B).
- `test_hierarchy_governance.py`: reviewer hierarchy/permissions (G), arbitrary department hierarchy and platform-path portability (I).
- `test_hierarchy_completion.py`: root completion (H) and requested complete hierarchy chain (J).
- `hierarchy_test_support.py`: single owners of existing db, mock_runtime and engine fixtures, imported explicitly by each case module. Support filenames do not match `test_*.py` collection patterns.

The mock_runtime fixture predates this refactor and was moved without alteration to preserve existing fixture semantics; its presence is not a claim that it satisfies the platform's zero-mocks invariant. No new mock/fake runtime behavior was introduced.

## Workflow cases

- `test_workflows.py`: YAML/JSON parsing, transitions/triggers and condition matching.
- `test_workflow_execution.py`: execution metrics, step resources/reuse and parallel stages.
- `test_workflow_governance.py`: sandbox lifecycle and budget hard stop.
- `test_workflow_api.py`: webhook trigger and evaluation capture.
- `workflow_test_support.py`: single owner of the existing function-scoped client fixture, preserving TestClient lifespan context behavior.

Each test function appears in exactly one case module; test functions are not re-exported into compatibility modules. New node IDs use the new module paths; selecting the old file alone no longer selects moved cases. Existing `conftest.py`, pytest collection patterns, pythonpath and autouse fixture behavior were not changed. Test files remain in the same directory so relative `__file__` root calculations remain valid. When behavior/schema/API code changes later, update the appropriate source cases and this guide without silently reintroducing duplicated fixtures.
# Runtime-unavailable workflow expectations

The three execution cases in test_workflow_execution.py now exercise explicit missing-runtime failure with the real SQLite-backed engine. They assert a FAILED execution/step, rendered input and agent preservation, zero fabricated usage, and no dependent-stage launch. The original fixture had no runtime but expected invented COMPLETED results; those assertions contradicted the corrected execution contract. DAG fan-out/fan-in planning assertions remain. No test was run, no inference adapter was added, and these cases do not establish successful live execution or metrics accumulation.

The runtime-unavailable execution cases now use a fresh tmp_path SQLite database and an explicit test-local agent capacity, so they do not depend on the application database contents or global capacity occupancy. This source change was not executed.

## Direct API runtime source cases
`test_direct_runtime.py` adds real-file private transcript persistence/fork/provider-model-tenant isolation, SQLite-backed Python-worker command routing/model selection, cross-method resume rejection, and local-tool inventory/workspace/symlink boundaries. `test_workflow_assistant*.py` have been removed alongside Workflow Assistant (2026-10-31). Use --noconftest when execution is authorized. These cases were not executed and do not establish live vendor HTTP, MCP tool inference, rendered setup behavior or budget/cancellation integration.

## New workflow chat source cases
test_workflow_chat.py uses real SQLite and FastAPI with signed JWTs, without calling a model. It covers credential-free allowed repo/channel/tool catalog projection, forbidden resources and cycles, inactive/idempotent creation plus dedicated runner/initial revision, revoked connector rejection, private draft isolation and department API-cost accounting. Persisted candidate fixtures test API/policy behavior, not model quality or live inference. These tests were added but not executed; use --noconftest only after execution is authorized.

Workflow chat source cases also cover rejection of draft-only disclaimers in execution prompts and creation denial without a workflow write. Not executed.

New test_workflow_local_dispatch.py uses real FastAPI/SQLite and a temporary sandbox to cover explicit broker-free local acceptance, reuse of the execution ID, and truthful FAILED state for missing inference. It makes no model calls or mock broker and was not executed under the current restriction.

## Governed connector source cases
test_connector_execution_security.py uses real SQLite, real FastAPI/JWT discovery authorization, actual runtime services and tool inventories, with no model/provider traffic. It covers credential-free narrowed schemas; forged repo/URL/token/identity/oversized arguments; denied-call audits; missing receipt completion; live department/tool/user/tenant/cancellation/expiry revocation; permission growth not widening scopes; agent skip flags not bypassing restrictions; atomic ambiguous channel-send suppression; hashed message audits; no local escape tools; task-bound transcript attachment; Playground exclusion; exact notification targets; and stale-admin/foreign-connector discovery denial. No mocked successful HTTP transport is introduced; actual vendor calls/receipts remain unverified. Updated workflow chat fixtures use implemented canonical tool names and real-format channel IDs. Tests were added/edited but not executed under the current restriction.

Connector security source cases additionally cover invalid optional notification not blocking a GitHub-only explicit resource scope even when legacy mcp_servers contains Telegram; completion still requires a real receipt. No execution verification was run.

Connector security source cases also cover manual channel-test rejection of aliases, foreign connectors and stale administrator claims without outbound I/O. These cases were not executed.

Connector security source includes explicit channel-action destination substitution denial with real SQLite and no outbound call, dependency enforcement, missing output and single-message bounds. Added cases remain unexecuted under repository instructions.

Workflow chat source cases cover real local plugin files + SQLite: skills catalog, proposal validation/native persistence, full scoped instruction resolution, unique relative reference compatibility and revocation after source clearing. Cases were not executed.

Workflow chat source cases now verify workflow-level skill persistence, legacy step promotion, deduplication and mixed attached-object/string inheritance. Cases remain unexecuted.

Workflow chat source cases cover real SQLite/FastAPI creation with no office agents, planned option tool grants, actual runner provisioning/tenant/department binding, inactive workflow persistence without sentinel IDs, invented-ID rejection and revocation before confirmation. Tests remain unexecuted.

Manual workflow creation has a real FastAPI/SQLite source case asserting planned-runner ID replacement and actual department-bound runner creation; not executed.

Connector source tests cover exact long-report preservation, Hebrew/emoji UTF-16 chunk bounds, numbering, whitespace reconstruction and explicit >60000-character rejection. No tests executed.

## Test security environment
pyproject addopts loads `-p poc.tests.platform_test_env`, which setdefaults PLATFORM_DEV_MODE=1 because the app refuses to start without JWT_SECRET_KEY. It works with `python -m pytest` (cwd on sys.path), including --noconftest runs. Never commit a real JWT secret to tests. It also setdefaults PLATFORM_WORKSPACE_ROOTS to the system temp directory so pytest tmp_path project folders pass the runtime workspace allow-list.

## Reasoning log source contracts (2026-11-01)
test_direct_reasoning.py adds pure transformation cases without mocked transports or model calls: visible summary/answer separation, opaque continuation excluded from logs but preserved for resume, phase preservation, legacy and Responses tool history conversion, incomplete responses, missing summaries, compatible detail filtering/deduplication and model-specific thinking budgets. Cases not executed.


test_direct_pricing.py adds unexecuted source cases for missing versus explicit free rates, fixed NVIDIA free-endpoint provenance, exact-model rate separation, reference versus provider charge (including zero), incomplete totals/known spend, invalid rates, real-file session resume/fork/legacy history and legacy workflow zero-cost display. No mocked transports or inference calls; tests remain unrun.


test_workflow_pr_authoring.py adds unexecuted real-SQLite catalog/grant tests (read-only/wildcard PR denial, explicit grant native conversion and revocation) plus pure workspace-required-PR validation and structured blocked/malformed final-outcome cases. It imports only the existing setup fixture. No provider/Docker/model calls or test execution.


test_repo_cache.py adds unexecuted source contracts for tenant/connector/repository cache identity, real local Git checkout materialization, edit/object independence and cache eviction survival, exact commit/detached checkout behavior, alternates/symlink rejection and lazy TTL/LRU cleanup. No mocked HTTP/Git transport or model inference. No tests were run, per explicit user instruction.


test_workflow_notification_modes.py adds unexecuted pure contracts for terminal/start/step selection, disabled and legacy compatibility, and deterministic per-execution/per-event delivery claim IDs. No provider, model, Docker or mocked transport calls; no tests were run.

## Organization provider credentials
test_organization_provider_credentials.py adds unexecuted real SQLite/FastAPI contracts: encrypted organization separation and model defaults, global/environment fallback denial, stale admin/inactive users, secret-safe 422, invalid-batch/missing-encryption-key atomic failure, worker rotation/revocation, AES-GCM organization AAD and command/tool environment hygiene. No mocks or provider requests. Existing global-runtime fixtures need migration to organization-scoped setup. No tests/collection/build/import/runtime verification was performed.

test_direct_runtime.py command-routing fixture now creates an organization and encrypted scoped provider configuration instead of global settings. Not executed.

## Execution backend foundation contracts
test_execution_backends.py adds unexecuted pure-policy and real-SQLite cases for legacy Direct API default, immutable/source-only capability inventory, strict IDs, pending-backend authoring versus execution refusal, YAML/JSON preservation, step override/null inheritance, later-step whole-DAG blocking, deterministic delivery exemption and persisted task lineage/missing-step denial. No fake runtime, Docker or model transport. No tests or collection run.

## Hosted Claude read-only source tests
test_claude_hosted.py adds real SQLite/Unix HTTP source cases for capability/routes, current user/tool/key/cancellation checks, text/model/tool request limits, concurrent department reservations, conservative unknown holds versus actual spend, aggregate deduplication and terminal SSE usage. Existing backend tests accept fail-closed Claude shape/configuration errors now that source integration exists. No SDK/Docker/vendor mocks or calls; tests were not run.

test_sandbox_diagnostics.py adds unexecuted pure startup-error category, secret/path exclusion, exit-code type and classification-priority contracts. No Docker, application or test execution.

test_completion_validation.py adds unexecuted pure contracts for strict final schema/types/required fields, whole-fence compatibility, prose/duplicate-key rejection, blockers, single repair with connector-free inventory, rejection of mixed/external recovery calls, and bounded credential-redacted diagnostics. No mocked transport, provider calls or test execution.

## Initial GitHub CI fixture repair
The origin SSE replay test now assigns the shared agent to a real organization and supplies organization-admin request claims so replay passes current tenant filtering. Live MCP grant tests now create a real organization, department, scoped agent and registered CONNECTED GitHub connector without a grant; they assert the appropriate workflow/step missing-grant denial. No model or connector HTTP call is performed. These repair stale fixtures without relaxing production security. Verification is through GitHub CI only.

Missing-grant cases also assert the persisted error at the actual rejection layer: workflow governance prefix for root MCP declarations, explicit no-active-grant reason for step preflight. Both require FAILED execution and a raised governance exception.

The playground command-inventory case uses a temporary SQLite organization, test-only encrypted provider credential and injected RuntimeServices. It checks command flags only; it performs no model call or subprocess launch. This aligns the fixture with organization-only credential resolution.

The playground command fixture supplies an api_-prefixed prior session, matching its Direct API provider, and still requires no --resume in the resulting tool-free command. Cross-method session rejection remains a separate runtime contract.

## Expanded GitHub CI contracts
CI selects 16 reviewed test files across core, security and runtime groups, covering organization credentials, current connector policy, workflow authoring, execution backend admission, hosted broker/budget limits, completion formatting, diagnostics and local session/tool handling alongside the original six. Real SQLite/FastAPI/local filesystem and Unix HTTP contracts are retained. No production keys, model calls or notifications are supplied. Shared conftest is disabled. Each suite uploads its own JUnit report, and any failure blocks CI required. Unreviewed legacy suites remain excluded pending isolation review. Verification runs on GitHub, not the local application environment.

Expanded-CI fixture corrections: hosted task records explicitly provide project_id=None. Channel-action cases now declare the required connector/resource envelope before testing frozen-destination substitution and delivery text; the missing-envelope denial is asserted separately. Production checks remain unchanged.

## Master CI groups
Master runs 11 reviewed files across core (six), security (connector_execution_security, workflow_chat, workflow_pr_authoring) and runtime (direct_runtime, workflow_notification_modes). Temporary SQLite/local contracts run with --noconftest on disposable runners, without provider keys or live sends. Connector channel tests now declare valid connector/resource envelopes before testing frozen destination and report rules; missing envelopes remain explicitly rejected. Feature-specific organization/hosted tests are introduced only with PR #18.

test_anthropic_threads.py adds unexecuted pure wire/state contracts and real private-filesystem session lease cases: suffix continuation, interrupted cursor invalidation, resume/fork, changed tools/reasoning wire isolation, credential rotation/expiry, refusal/truncation/pause clearing, concurrent lease rejection and legacy records. No provider mocks or live calls; no tests executed. Provider HTTP recovery and end-to-end runtime remain unverified.


## Skill relationship evidence
`test_skill_connections.py` adds unexecuted pure source-parser contracts for engineering
review handoffs versus documentation, negation/frontmatter/code/script/non-goal exclusion,
conditions before a sentence boundary, coordinated targets, routing tables, alias collisions,
duplicate IDs, preview-only incompleteness, DAG direction/optional flags/unresolved group
warnings and malformed documents. Fixtures are plain Markdown/JSON data, not mocked API,
database or runtime services. No tests/scanners/application scripts were executed.


The existing real SQLite/FastAPI organization auth case now asserts that an admin's old
token can refresh /auth/me and see a newly created department without membership; foreign
organization departments remain excluded, login agrees, JWT claims remain membership-only,
and invited operators still see only their assigned department. Added assertions were not
executed under the local runtime restriction.


## Current identity/role isolation contracts (2026-11-05)
test_access_policy.py creates real SQLite organizations, departments, users, agents and workflows,
registers the real guarded FastAPI routers and signs real JWTs. It covers read/detail selection,
stale admin claims, disabled users, capped mixed memberships, revocation, nested foreign references,
manager updates versus operator/member denial, own-organization boundaries, unsafe host/queue
operations, unattributed activity, unknown endpoint fail-closed behavior and path/symlink containment.
test_access_lab_setup.py checks additive2-org fixture registration,26 accounts, exact canonical
password verification,0600 output and disabled/inactive resources. These are not provider/runtime
mocks. Existing revision/origin/playground fixtures now create real user identities for the current
DB-based scope contract. New cases are selected in CI but were not executed locally.

Access-policy cases additionally cover engine admission with fresh DB roles, admin rejection of
cross-department step assignments and409 on implicit department/history transfer. These cases
are prepared but not run. Runtime tests/commands remain unexecuted under the project restriction.

Playground diagnostic fixtures now persist agent/task organization and department identity, preserving the intended missing-application-agent failure rather than failing tenant admission earlier. No fixture was executed.

CI repair: provider credential fixtures override the current database authentication dependency; disabled identities expect401. Local plugin fixtures live inside the temporary tenant shared root. Workflow exception compatibility and organization-list isolation remain enforced by existing contracts. No local runtime verification performed.

test_direct_runtime.py covers organization-scoped authoring from an ephemeral non-tenant directory with empty tools or restricted mode: no file/shell inventory or calls, no MCP escape, and local-tool re-enablement still rejects the outside path. No local test execution; GitHub CI verifies the contracts.

Access-policy contracts cover MEMBER/OPERATOR/MANAGER workflow authoring through real registered routes, AI context, forced inactive lower-role workflows, retained execution/activation restrictions, foreign/unassigned departments and immediate membership revocation. No local runtime verification performed.

Member authoring denial contracts accept403/404 (resource concealment) and assert activation remains false; neither denial response authorizes execution.


test_workflow_pr_approvals.py covers rich PR projection, conservative readiness, strict read tool schema/no model merge tool, terminal graph/channel validation, real SQLite/FastAPI personal actor/tenant/role decision and expiry contracts, duplicate claims and explicit merge grants versus wildcard/revocation. No mocks or provider/model calls; local execution not performed.

PR gate fixtures additionally prove failed/missing/partial read receipts cannot pin candidates; only completed full provider-fact records in the source task qualify. No network or model simulation is used.

The explicit-merge rejection fixture uses the canonical stored wildcard string (*), preserving the production distinction from an explicit JSON tool-name list.


## API-only governance audit
By explicit user authorization, local API tests are now allowed without agent/model/provider execution. run_api_audit.py executes an explicit HTTP-node inventory under real FastAPI/SQLite in a disposable tracked-source snapshot, excluding working data/workspaces/env/credentials. api_audit_guard.py disables actual runtime capability and rejects network/DNS/child-process attempts instead of faking responses. test_generic_governance_api.py covers GitHub/Telegram/Slack and descriptive-only Postgres metadata with 2 orgs/3 departments, four roles/mixed/unassigned/disabled users, redaction, grant/revocation/catalog/write boundaries and disabled callbacks. Static agent definitions are authorization records only, never launched. Selected existing HTTP access and report-approval contracts run too; no application lifespan. See docs/architecture/ai-13-api-audit.md for results and limits.


AI-14/AI-15 add UX/ADR artifacts, not executable UI or API behavior. Reuse the 39-case isolated API-only runner as regression evidence; static wireframe/document inspection is not browser/E2E/provider verification. Later tickets must add API tests for actual new routes/state transitions before release.

## AI-16 API-only contracts
run_api_audit.API_CONTRACTS includes test_capability_policy_api.py plus the AI-13 baseline. Real guarded FastAPI routes/SQLite exercise registry honesty, role/tenant/resource isolation, restrictive managers, CAS/history, current/frozen policy, selectors/time windows, channel policy and AI catalog narrowing. Server-seeded execution rows are policy subjects only; no workflow/agent/model dispatch or live provider request occurs. The disposable source snapshot and interpreter guard forbid network/subprocess; service doubles are not used. See docs/architecture/capability-policy-v1.md.

AI-16 destination regression: workflow chat validates channel-only Destination objects without repository/tool fields, then checks exact channel delivery policy and notification-agent permissions. API-only saved-preview tests cover allowed and denied channels on the same connector, with zero executions or sends.

AI-17 adds real HTTP editor-option contracts to test_capability_policy_api.py: secret-free exact projections include currently typed-policy-denied resources, exclude unsupported/foreign resources, honor department grants and deny organization policy reads to managers. The isolated API runner now covers 65 cases with no agent/model/provider execution.

## AI-18 evidence scope
The P01 documentation maps behavior to existing test_capability_policy_api.py/test_generic_governance_api.py and selected access/approval API contracts; AI-17 had 65 passing real HTTP/SQLite cases. The isolated runner/guard boundary, prior CI head and unverified provider/browser/runtime scope are recorded in ../../docs/governance-policy-guide.md. AI-18 changes documentation only and adds no tests that merely mirror prose; new behavior changes still require appropriate real API regression coverage. No new local runtime verification was performed for AI-18.

## AI-19 API-only coverage
run_api_audit includes test_github_pr_governance_api.py: actual guarded FastAPI/SQLite checks PR read/write descriptor schemas, required read dependencies, write wildcard denial, exact resource/current role, no grant backfill, inactive write-plan creation and authenticated merge resolution blocked before I/O when merge is ungranted. Baseline GitHub fixture now explicitly grants narrower read dependencies; existing receipt fixtures carry version2 proof as persisted subjects. No provider responses are mocked, agents dispatched or live PR actions run. Live evidence parsing/write success paths remain unverified. See ../../docs/github-pr-governance.md.

## AI-20 PR scopes and evidence
AI-20 extends test_github_pr_governance_api.py with real FastAPI/SQLite historical audit projection checks across all four roles: exact draft receipt identity, allowlisted output, foreign-connector omission and tenant/selected-department denials. Fixtures are persisted diagnostic records, not provider-response mocks; no agent/model/provider/worker is executed. The existing isolated API audit runner includes this file.

AI-20 also checks nested evidence/reviewer field allowlists and approval GET preservation of STARTED/UNKNOWN/NOT_DISPATCHED/COMPLETED receipts independently of a FAILED batch, with no connector calls.

Checks-only diagnostics preserve files_included=false and explicitly remain incomplete approval proof even when their CI facts pass; the UI never displays a full-review readiness badge for that result. API contracts assert this field survives the safe projection.

## AI-22 channel registry contracts

`test_generic_governance_api.py` exercises real FastAPI routes and temporary SQLite for Telegram/Slack registration, role and tenant isolation, validation, revision conflicts, pagination, independent flags and allowlisted audit details. The existing API CI selection includes these cases.

AI-23 updates the channel registry contract test to require department member read access while preserving administrator-only mutations and cross-department denial.

Channel registry API contracts cover configured-ID enforcement and the credential-free provider catalog for admins and members.

The channel catalog contract checks display labels are limited to configured channel IDs and omitted for member reads.

The channel catalog contract also checks that members can read the name of their exact registered channel.

The isolated API audit exercises AI-25 using signed request fixtures, real FastAPI and temporary SQLite. It covers both providers, unsigned proof rejection, user confirmation and isolation, replay, rotation, unlink and safe audit metadata.

AI-26 real API contracts cover active connector catalog projection and department management, including foreign tenant/department denial, live role downgrade, shared link restrictions and revocation audit.

test_channel_ingress_api.py covers verified Telegram and Slack staging, replay, org/admin scoping, rate limiting, secret-free diagnostics, Telegram identity proof routing and outbox leases using real FastAPI and temporary SQLite.

The channel ingress API contracts also exercise AI-31 revisioned rules, side-effect-free preview, exact replay prevention, revoked sender admission and lease fencing.

The isolated channel ingress API module also checks the real deterministic DAG engine across two approval barriers, including quorum, duplicate decisions, preserved step history and rejection.

AI-31 verifies signed Slack command projection and deduplication through the real ingress API.

The isolated ingress contract includes an authenticated Telegram callback case for exact message matching, duplicate delivery, atomic voting and terminal edit selection.

Terminal Telegram approval contracts verify exact provider message binding, durable callback deduplication and refusal to merge after the original identity link is replaced.

The terminal Telegram contract also checks that the real workflow catalog and native compiler preserve pinned PR merge intent with an exact interactive binding and no dashboard URL.
test_workflow_pr_approvals covers same-tenant GitHub defaults, department overrides, revocation and restoring inheritance with isolated SQLite.
The PR approval contract tests verify that an empty receipt-scoped review completes its terminal gate without an approval record or a notification tool scope.
The PR approval contracts exercise discovery receipt handoff against real SQLite, including empty results, duplicate numbers and rejected closed or wrong-author entries.
The generic governance API tests cover same-tenant GitHub inheritance in the authoring catalog, disabling connector defaults, and denied out-of-scope department selection.
PR approval report regression coverage verifies literal multiline findings and strict integer eligibility.
PR approval tests cover typed connector completion, refusal to select out-of-batch PRs, and report serialization with multiline findings and quotes.
The terminal Telegram approval contract checks that the claimed delivery includes the workflow step key needed to render the card.
The terminal Telegram approval contract also exercises the internal polling ingress path against the persisted connector and verified callback.
The terminal polling callback regression covers channel-attributed messages without a bot from field.
Capability editor tests verify inherited GitHub resources and per-department revocation. Missing-grant execution tests explicitly disable GitHub inheritance to exercise admission with no effective grants.
