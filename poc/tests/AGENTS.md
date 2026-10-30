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
