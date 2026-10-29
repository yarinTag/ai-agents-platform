# Platform modularity and refactoring roadmap

Date: 2026-10-29. Status: broad implementation and agent/parent source reviews in progress; see the implementation ledger.

Execution branch: `codex/platform-modular-refactor`, created directly from local `master` at the user's request. The inventory below was collected on `codex/workflow-playground-and-dashboard`, which contained three commits beyond master. Those commits were deliberately not merged or cherry-picked. File counts, line sizes, authoring/revision/playground details and dependency observations below are planning context from that branch and must be re-established on this base before their implementation slices. Local master was used without a remote fetch.

### Historical first slice record

Extracted the master version of `dashboard/src/services/api.ts` into one HTTP/interceptor owner and 18 domain endpoint clients. The public facade retains existing named/default exports, functions and type imports; model/filesystem interfaces moved to `src/types`. Endpoint bodies and request behavior were relocated without intentional changes. Existing callers remain on the facade; no compatibility removal is scheduled until their migration is explicitly scoped.

Updated the services guide, frontend architecture guide and frontend development rules. No backend/schema/UI behavior changes were introduced intentionally. No tests, builds, lint, type checking, startup or live inference were run. Compilation and runtime compatibility remain unverified. Rollback is limited to restoring api.ts and its docs and removing the newly introduced client/type files after preserving any subsequent edits.

That first slice left the ownership inventory open. Subsequent master-based extraction and parent/agent review now cover storage, backend routers, lifecycle, runtime, orchestration, workflows, plugin discovery and the frontend. See the implementation ledger and source inventory for current evidence; the historical first-slice record is not the current completion status.

## Scope and evidence

This plan follows source and documentation inspection only. No application startup, tests, build, lint, type checks, provider calls, or failure injection were performed. Current runtime behavior and fault isolation are not verified.

The initial inventory covers `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, and `.css` under `poc`, excluding dependency/build/cache directories. It contains 222 files, of which 29 exceed 500 physical lines. This is a baseline for the inspected tree, not a complete repository-wide compliance claim. Before implementation, inventory other owned source extensions and scripts outside `poc` through file reads. Do not execute verification tools without a subsequent user instruction changing the current restriction.

The historical `docs/audit/phase0-plan.md` describes earlier work and must not be treated as the current state or as authorization to run its verification commands.

## Working rules

- Maximum 500 physical lines per owned source file, including comments and blank lines; aim for 250–350. Existing oversized files form a migration backlog, not a permanent exception.
- Include test source and operational scripts. Exclude vendored dependencies and generated outputs explicitly; keep generated sources reproducible and their inputs owned.
- Split by responsibility, not line ranges. No numbered parts, compressed formatting, or inheritance solely to bypass the limit.
- Keep names, types, errors, and state transitions explicit. Extract business decisions from HTTP and presentation code.
- One owner per business rule. Similar syntax alone does not establish a duplicate business responsibility.
- Preserve public routes, payloads, tenant boundaries, session resumption, budgets, and revision semantics during structural extraction.
- Update relevant AGENTS.md and CLAUDE.md alongside implementation. Register any new module guide in the root index.
- No tests, build, lint, type checks, startup, or live inference in the currently authorized work. Record changes as reviewed by reading only; never label them behaviorally verified.

## Architecture decisions

Start with a modular monolith. Separate processes are a later, explicit deployment step where resource/crash isolation is required. In-process interfaces alone cannot isolate a process crash, deadlock, or memory exhaustion.

Candidate ownership boundaries: identity/governance; agent/task management; execution orchestration; runtime; workflows; workflow authoring; MCP; plugins; scheduling; approvals; collaboration; notifications. Refine boundaries after tracing consumers and transactions, rather than creating every layer in every small module.

Each substantial domain may contain domain rules, application use cases, ports, infrastructure adapters, and HTTP adapters. A composition root owns concrete implementation selection and lifecycle. Business modules receive narrow ports rather than importing concrete implementations or the global dependency container. Cross-domain coordination belongs in explicit use cases and versioned contracts; the composition root contains no business decisions.

Shared code is limited to stable primitives and contracts with named ownership. Do not create a universal shared service, giant contracts file, or unrestricted utils package. Event handlers and clients must not write another domain's tables directly. Existing cross-domain transactions require an explicit migration decision before moving ownership.

Keep SQLite and existing schemas initially. Repository extraction is not authorization to migrate to PostgreSQL, introduce network services, or redesign data consistency.

## Dependency seams observed

| Current seam | Evidence | Intended change |
|---|---|---|
| Global startup coupling | `backend/dependencies.py:init_services` starts cron, connects broker, starts worker, and rethrows initialization failures | Separate required core startup from optional capability lifecycles; clean up partially started resources |
| Eager router loading | `backend/main.py` imports and registers domain routers directly | Register optional capabilities through descriptors without importing disabled implementations |
| Global concrete runtime wiring | dependencies imports the concrete runtime and assigns `on_task_completed` | Inject runtime ports; explicit event/callback registration with lifecycle ownership |
| Persistence/runtime coupling | `persistence.py` imports AgentRun and TaskStatus from runtime_adapter | Use canonical lightweight models already under runtime where appropriate; inspect cycles and compatibility imports first |
| Workflow/orchestration coupling | get_workflow_engine injects the full orchestration engine | Inventory actual calls and replace with narrow execution/governance ports |
| API container as import hub | API workflows imports both dependencies and domain types from dependencies | Separate type imports from dependency providers; retain framework-specific wiring at the edge |
| Scheduler/execution coupling | scheduler engine calls RuntimeAdapter directly | Depend on an execution dispatch contract; define unavailable-runtime behavior |
| Permission fallback | orchestration check_department_mcp_access allows when DB permission method is missing | Track separately as a behavior/security change; decide explicit deny/unavailable semantics rather than silently altering it during extraction |
| Deployment coupling | enterprise compose makes API depend on healthy broker and PostgreSQL | Reconcile actual supported persistence/deployment modes before changing readiness or dependencies |

## Capability availability contract — proposed, not current API

Use separate capability states: DISABLED, STARTING, READY, DEGRADED, UNAVAILABLE, STOPPING. Availability is distinct from task/workflow business state. Define transition ownership and retry policy before implementation.

The process liveness endpoint reports that the API process is alive. Required-core readiness reports whether essential dependencies work. A capability report exposes availability and sanitized reasons without disclosing credentials. Route/schema details will be specified in the implementing slice, preserving existing health consumers through compatibility handling.

| Missing capability | Expected platform behavior | Affected operation |
|---|---|---|
| Scheduler | Administration and manual execution remain available | No automatic schedule dispatch; explicit status and recovery policy |
| Notifications | Execution state remains authoritative | Failed delivery is recorded separately; bounded retries must avoid duplicate sends |
| Runtime | Authorized reads and configuration remain available | New inference/resume fails explicitly or enters a defined durable queue; never pretend success |
| Broker/worker | Supported control-plane reads remain available | Queue-backed dispatch unavailable; no silent inline fallback |
| Workflow engine | Other domains remain available | Workflow execution unavailable; configuration reads may remain available |
| MCP connector | Other connectors and unrelated tasks remain available | Only dependent tool actions fail explicitly |
| Optional UI feature | Navigation and unrelated routes remain usable | Scoped unavailable state and retry action |
| Identity/policy/budget dependency | Unrelated safe operations may remain available | Sensitive actions fail closed |
| Core database | Avoid claiming functional readiness | DB-backed functionality is unavailable; process liveness alone is insufficient |

Disabling a capability is not deleting its data. Physical package removal is a separate acceptance target requiring import isolation. Domain deletion, external deployment, and destructive schema changes are outside this refactor plan.

## Oversized file migration map

Paths are relative to `poc/`. Targets below are responsibility names, not approved new exports. All extracted files must remain under 500 lines; split repositories further by cohesive operations where needed.

| Source | Lines | Extraction responsibilities | Slice |
|---|---:|---|---|
| persistence.py | 5130 | connection/transactions; versioned schema initialization; seeds; domain records; repositories per domain | 3 |
| runtime_adapter.py | 1551 | command/environment construction; process lifecycle; output parsing; checkpoints/events; authoring inference; task resume/cancel; compatibility facade | 5 |
| backend/api/workflows.py | 1330 | DTOs; generation/conversion; CRUD/revisions; execution queries; production/playground/webhook dispatch; channel bindings | 6 |
| backend/api/skills.py | 1010 | skill CRUD; metadata parsing; local scanner; remote tree/blob scanner; credentials lookup port; plugin settings/content/cache | 4 |
| backend/api/mcp.py | 888 | catalog; connector CRUD; permission use cases; provider discovery adapters; channel delivery | 6 |
| backend/api/organizations.py | 836 | organization settings; departments/budgets; membership/invitations; governance routes | 6 |
| backend/api/tasks.py | 712 | task CRUD/query; dispatch/cancel/delegation; logs/stream transport | 6 |
| backend/api/agents.py | 524 | DTOs; agent CRUD; hierarchy queries/validation; configuration mapping | 6 |
| workflows/engine.py | 785 | conditions; execution planning; step runner; budget/governance gates; result persistence; lifecycle coordinator | 7 |
| orchestration/engine.py | 676 | delegation policy; dispatch; completion/parent propagation; retry/remediation; recovery; query facade | 7 |
| orchestration/supervisor_resolver.py | 733 | question/answer contracts; memory resolution; manager decision inference; escalation; task continuation coordinator | 7 |
| orchestration/code_indexer.py | 566 | source parsers; chunking; file hash cache; embedding/vector adapters; indexing/search coordinator | 7 |
| dashboard/src/services/api.ts | 515 | one HTTP/interceptor owner; clients by domain; temporary compatibility exports | 2 |
| dashboard/src/pages/McpHub.tsx | 2690 | catalog; connectors; discovery; permissions; channels; workflow integration; scoped loading hooks | 8 |
| dashboard/src/engine/PixelRenderer.ts | 2234 | palette/geometry; scene layers; furniture drawing groups; agent/connection rendering; render coordinator | 10 |
| dashboard/src/components/workflows/CreateWorkflowModal.tsx | 1607 | draft state; YAML/visual conversion; resource selection; step editor; save/revision coordination; tab presentation | 9 |
| dashboard/src/components/chat/AgentMiniChatDrawer.tsx | 1031 | sessions; conversation loading; streaming subscriptions; composer; transcript; blocker actions | 9 |
| dashboard/src/pages/Workflows.tsx | 1013 | table/actions; executions; launch; inspector; edit/history integration; polling hooks | 9 |
| dashboard/src/components/office/AgentsOfficeV3Canvas.tsx | 945 | canvas lifecycle; input/camera; scene state; overlay UI; rendering integration | 10 |
| dashboard/src/pages/Skills.tsx | 943 | source configuration; plugin browsing; scan/cache state; skill detail/actions | 8 |
| dashboard/src/pages/Tasks.tsx | 865 | task table; queue/DLQ panels; creation/delegation; tree/log dialogs | 8 |
| dashboard/src/pages/Agents.tsx | 780 | roster; agent editor; hierarchy; resources/model selection | 8 |
| dashboard/src/pages/CalendarView.tsx | 645 | calendar projection; schedule table/actions; editor integration; approvals panel | 8 |
| dashboard/src/components/workflows/WorkflowCanvasGraph.tsx | 615 | graph mapping/layout; nodes/edges; selection; mutation callbacks | 9 |
| dashboard/src/components/office/AgentDeskDrawer.tsx | 611 | agent summary; task activity; actions; tab data loading | 10 |
| dashboard/src/components/office/OfficeRightSidebar.tsx | 603 | summary sections; activity feed; selection/actions | 10 |
| dashboard/src/components/warroom/WarRoomModal.tsx | 579 | session state; rounds/messages; synthesis actions; presentation | 9 |
| tests/test_hierarchical_orchestration.py | 774 | existing cases grouped by delegation, completion, recovery, governance; preserve collection/fixtures | 11 |
| tests/test_workflows.py | 521 | existing parser/engine/API cases grouped by responsibility; preserve collection/fixtures | 11 |

## Duplication inventory protocol

No complete duplicate-function audit has been performed. For each candidate record source locations, inputs/outputs, side effects, authorization, callers, proposed owner, and migration impact. Read both implementations and callers before merging.

Prioritize tenant/department authorization, MCP governance, workflow serialization/conversion, runtime event mapping, plugin metadata parsing, channel selection, and repeated frontend loading/error/polling logic. These are candidate areas, not confirmed duplicates.

Known deliberate forwarding: orchestration get_subtasks/get_task_tree call persistence queries; backend/cron_engine.py re-exports scheduler implementation. Preserve public compatibility until callers migrate; do not count forwarding as duplicate business logic. Repeated trivial dataclass to_dict methods are lower priority than policy duplication; do not add a framework solely to remove them.

## Ordered implementation slices

1. Expand the read-only inventory to all owned source files. Record domain import edges, cycles, module-level side effects, callers of legacy exports, cross-domain SQL and transactions. Deliver an ownership/dependency ledger and duplicate candidate ledger.
2. Extract a small frontend HTTP-client slice first: central HTTP instance/interceptors, domain clients, compatibility exports. Preserve auth behavior, request cache invalidation, routes and payloads. This establishes the file-size and documentation pattern without touching startup or database transactions.
3. Extract persistence incrementally: canonical records/import seams, connection and transaction primitives, schema initialization, then repositories one domain at a time. Keep DatabaseManager as a temporary delegating facade. Do not use mixins to redistribute a monolith without ownership. Preserve self-healing, WAL/foreign keys/busy timeout, revision transaction boundaries and legacy baseline behavior.
4. Extract plugin discovery as the first complete backend domain: pure metadata parsing, source-specific adapters, settings/cache/application service, thin HTTP routes. Preserve empty-path semantics, tenant-scoped credentials, in-memory remote scans, cache invalidation and zero cloning. This domain is a smaller pilot than workflow execution.
5. Introduce explicit service descriptors and composition/lifecycle ownership. Isolate optional imports and startup/shutdown failures, then refactor runtime internals behind existing RuntimeAdapter contracts. Bound process/concurrency resources and maintain session_id/checkpoints. Split this slice into independent changes rather than one combined runtime/startup rewrite.
6. Extract remaining HTTP use cases and domain repositories/ports. Inventory each route contract before moving it. Preserve security checks at the application boundary for HTTP and internal callers alike.
7. Refactor workflow/orchestration coordination against narrow ports, including policy, completion, recovery and escalation. Separate structural moves from any approved correction of permissive fallback behavior. Preserve PLAYGROUND isolation, execution hash/revision semantics and WAITING_INPUT/PENDING_APPROVAL states.
8. Refactor MCP, Skills, Tasks, Agents and Calendar frontend features. One owner for each data lifecycle; scoped error states must prevent an optional capability failure from blocking unrelated content. Preserve EN/HE and RTL behavior.
9. Refactor workflow builder/list/graph, chat and war room. Preserve extensions in YAML, optimistic concurrency, draft-versus-executable boundaries, cancellation and subscription cleanup.
10. Refactor office/rendering by scene responsibility; preserve coordinates, draw ordering, hit testing, animation timing and Office/workflow activity separation.
11. Split existing oversized test source without running it; remove temporary facades only after a complete caller inventory. Reconcile documentation, source-size backlog, dependency ledger and unresolved behavior risks.

Slices 2 and 4 are deliberate pilots. A pattern should be refined from actual extraction before applying it across every domain. No fixed delivery estimate is claimed before slice 1 establishes the full scope.

## Required transaction and compatibility decisions

- Workflow update + expected_revision check + revision snapshot remain one BEGIN IMMEDIATE transaction. Deduplication continues to include saved revision.
- Workflow assistant draft/generation persistence remains separate from executable workflows and ordinary tasks. Current-policy revalidation is preserved.
- Tenant scoping belongs to explicit request/use-case context; asynchronous work must capture validated scope rather than read mutable global request state.
- Event contracts specify producer, consumer, payload version, durable versus ephemeral delivery, ordering requirements, correlation and tenant identifiers. Do not assume the current in-memory bus provides cross-process delivery.
- Queue dispatch needs an explicit decision on publish failure and DB commit ordering before changing implementation. A durable outbox, if selected, is a separately documented schema/behavior change.
- Never add automatic retries to non-idempotent operations or re-dispatch accepted jobs merely because a capability restarts.
- Compatibility facades have a caller list and removal slice. Do not duplicate implementations behind old and new imports.

## Per-slice completion record

Record responsibilities moved, public contract preservation, caller migration, file sizes, dependency changes, duplicate decisions, documentation updates, unresolved risks and rollback path. Use small reversible changes; avoid schema changes in mechanical extraction slices. Do not overwrite unrelated working-tree changes or create commits unless requested.

Distinguish three outcomes: extracted by source review; behavior verified; failure isolation verified. Under the current restriction only the first can be claimed. Future execution-based validation requires changed user instructions and is not an automatic next step in this plan.

## Immediate next work

The broad source implementation is recorded in [the implementation/review ledger](refactor-implementation.md). Final combined-tree source review and documentation reconciliation are ongoing. Compilation, runtime compatibility and live failure isolation remain unverified under the no-execution instruction. Do not mark the full goal achieved merely from file-size evidence.
