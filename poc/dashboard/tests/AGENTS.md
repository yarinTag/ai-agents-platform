# Dashboard logic tests

## Runner and boundaries
Run with Node22 and locked npm dependencies: npm test from poc/dashboard.
The script uses Node's built-in test runner and native TypeScript stripping; tests import
real .ts modules directly. No new test framework, browser shim, HTTP server, API credentials,
model inference or external API calls are required. AxiosError values are real error objects
used to check presentation logic; they are not network transports. Fixtures are plain inputs,
not replacement database/API implementations. Runtime verification remains GitHub-only.

## Coverage map
- workflowDefinitions: root/middle/last deletion, fan-in/fan-out dependency reconnection,
  deduplication, legacy step IDs, no self-dependencies, flow-edge cleanup, unknown-field
  preservation, missing IDs and invalid JSON/steps.
- workflowSettingsRules: secret name length/format/reserved environment names, UTF-8 byte
  boundaries, Secrets Manager ARN validation, host allowlist normalization/exact validation,
  model-default roundtrips, memory/time presentation and secret-safe API error projection.
- workflowCosts: unavailable/partial/free/no-usage/reported/estimated prices, explicit zero,
  sub-micro-dollar display, reference estimates and unknown-event parsing.
- mcpResources: exact provider/ID selection, array/legacy channel IDs, malformed values,
  stable deduplication and no fabricated destinations or input mutation.
- workflowSkills: shared/legacy skill promotion, stable ordering, first-selection metadata
  precedence and immutable-input handling.
- requestCache: pending request sharing, retry, force refresh, invalidation, bounded eviction,
  organization-key separation, late success/rejection races and synchronous loader errors.
- resourceLoading: success-empty versus failure, no state overwrite on failure, containment of
  application errors and independent partial resource loading.
- modelPresentation: context-window boundaries, tier/case fallback and unique grouped catalog.
- pixelCoordinates: scaled grid projection with zoom and positive/negative pan.
- pixelAgentActivity: active/inactive statuses, agent fallback, completion transitions,
  missing prerequisites, idempotent delivery and walk/wait/return animation lifecycle.

Each *.test.mjs is auto-discovered by both npm test and master CI's frontend test glob.
Tests are split by responsibility and kept under 500 lines. They assert user-facing
contracts and edge cases; passing does not establish DOM behavior, hook lifecycle, browser
rendering, live integration connectivity or complete application coverage.

## Determinism
Use explicit expected outputs, frozen/serialized inputs to check non-mutation, deferred
Promises for races and direct scene ticks for animation. No arbitrary sleeps or wall-clock
TTL assumptions. Cache tests clear shared state after every case. No production state is read.


pluginsFlowModel.test.mjs covers cross-plugin incoming references, cycles, deduplication,
self/unknown target exclusion, empty packages, immutable inputs, and the absence of fabricated
Core lifecycle/preview edges. Added for CI; not executed locally. This does not verify graph
layout, panning, zoom, selection or browser accessibility.


The audited pluginsFlowModel cases now use typed evidence-backed connections and reject
legacy/reference-only edges. pluginGraphModel.test.mjs adds strict package/search filters,
cross-package direction, conditional flags, opt-in references, evidence aggregation and
self/unknown/wrong-owner exclusion. These pure contracts do not replace DOM event/scroll
verification. Added but not run under the local runtime restriction.


accessPermissions.test.mjs covers admin membership independence, account/membership rank caps,
operator-versus-manager flags, read-only members and fail-closed unassigned/unknown roles. It is
included by the existing *.test.mjs CI glob; not executed locally. No DOM/session/stream correctness
claim is inferred from the pure helper cases.
