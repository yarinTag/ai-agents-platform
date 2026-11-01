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
pyproject addopts loads `-p poc.tests.platform_test_env`, which setdefaults PLATFORM_DEV_MODE=1 because the app refuses to start without JWT_SECRET_KEY. It works with `python -m pytest` (cwd on sys.path), including --noconftest runs. Never commit a real JWT secret to tests.
