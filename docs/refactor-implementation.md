# Modular refactor implementation and review ledger

Branch: codex/platform-modular-refactor, created directly from master. The original source-only refactor was checkpointed in 71c1dcb before merging origin/master (523913e) at the user's explicit request. The merge incorporates the upstream workflow/queue/assistant additions. No deployment, application startup, tests, build, lint, type check or live inference was performed; commit hooks were disabled to honor that restriction.

## Ownership and review

| Work package | Implementation owner | Review |
|---|---|---|
| SQLite records/schema/connection and repositories | persistence agent | Parent reviewed composition, callbacks, SQL mapping and self-healing; requested canonical mappings and SQL ownership fixes |
| Five dashboard pages and API resource states | frontend_features agent | Parent reviewed Tasks extraction, MCP composition, resource contracts; component agent independently reviewed pages/services |
| Workflow/chat/office/war-room components and pixel renderer | frontend_components agent | Parent reviewed public component guards, hook models, scene state, drawing order; features agent independently reviewed component/shell boundaries |
| Runtime command/process/event collaborators | frontend_features agent | Parent reviewed ports, finalization, cancellation and question handling; fixed resumed-attempt cleanup races, stderr draining and lifecycle closure |
| Orchestration, supervisor/index parsing and test-source split | persistence agent | Parent reviewed delegation/completion ports, recovery, shared fixtures and policy distinctions |
| API modules, optional lifecycle, notifications, plugin domain and integration | Parent | Persistence agent independently reviewed API/lifecycle/workflows; findings led to explicit runtime-failure states and tenant-scoped execution/credential fixes |

All review was by reading source/diffs. Review evidence is not a compilation, execution, concurrency, provider-connectivity or resilience result. Later parent edits received parent source review; the final combined tree has not been executed.

## Requirements and source evidence

| Requirement | Current source evidence | Limit |
|---|---|---|
| At most 500 lines | Full source inventory including scripts, tests, Python/TS/JS/CSS/SQL/HTML/YAML/JSON; no owned code file above 500 after extraction | package-lock.json is generated dependency metadata and excluded; documentation is not code |
| One owner per business function | Canonical storage row mappers/JSON decoding, plugin summaries/metadata, channel delivery, provider selection, question/progress parsing, configured-resource projection and demo setup | Exact Python body comparison over substantial functions found only protocol stubs repeated; semantic similarity still requires human judgment |
| Reusable architecture | Storage callbacks/ports, runtime services, orchestration ports, workflow step/condition/stage collaborators, domain HTTP clients, feature hooks/panels, composed scene painters | Shared SQLite transactions remain; separate databases/processes are not introduced |
| Optional capability isolation | Lazy router registration, sanitized 503 fallback, independent optional startup/shutdown and process/subscriber cleanup | Required identity/configuration/storage/event primitives remain core; in-process crashes/memory exhaustion are not isolated |
| UI failure containment | Lazy route boundaries, scoped resource errors/retry, capability reporting, dismissible runtime setup | No rendered/browser verification was performed |
| No tests/build | Commands used source reads, edits, branch management and source inventories only | No claim of passing tests or preserved runtime behavior |
| Documentation synchronized | Updated root/backend/runtime/orchestration/workflow/frontend module guides; registered storage/plugins/integrations/tests | Guides describe intentional correctness changes separately from mechanical extraction |

## Dependency ownership

Configuration, identity/authentication, storage access, stable runtime models and core event primitives are required infrastructure. Backend dependencies/runtime_wiring/router_registry are composition adapters. Domain engines receive ports/callbacks; they do not initialize unrelated services. Runtime legacy_services and orchestration/delegate are explicit compatibility/CLI integration adapters, not reusable domain rules.

Storage repositories receive connection factories; cross-repository callbacks are selected in storage/composition. Existing cross-table cleanup, invitation and budget transactions remain intentionally coordinated. Workflow step SQL, parent-resumption claims and interaction retargeting belong to storage. Record serialization has one shared Record implementation; User keeps its specialized password-hash-excluding projection.

Optional router names are defined in backend/router_registry. Runtime, orchestration, intelligence, scheduler-worker, team-coordinator and notifications are service names. Scheduler/teams routers are separate from their execution workers so unavailable execution need not hide stored administration. PLATFORM_DISABLED_CAPABILITIES is startup configuration, not a hot-uninstall API. Core organizations cannot be disabled.

## Intentional corrections identified by review

- Persisted task list/detail reads can operate without runtime; execution still returns explicit unavailable errors.
- Workflow execution no longer requires an unused full orchestration instance; manual scope lookup uses engine.db.
- Workflow steps persist observed success/failure/cancellation/pause. Missing runtime, dispatch errors and timeout do not become COMPLETED. Paused executions omit completed_at and stop dependent stages.
- Workflow DAG planning is separated from execution; existing task/session resumption remains distinct from automatically resuming an entire paused workflow.
- Notifications are separate from authoritative execution results. Telegram/Slack acknowledgement is required for delivery success; failures are recorded independently without fake successful sends.
- Runtime subscriptions use subscriber-owned bounded queues, not competing consumers of the executor input. Unsubscribe works. stderr is drained; termination waits are bounded. Same-run attempts serialize so prior cleanup cannot terminate a resumed subprocess. Shutdown cancels known runs and closes subscriptions.
- Runtime supervisor outages retain WAITING_INPUT and route to human clarification. Manager inference failure no longer chooses the worker's first suggested option. Missing MCP permission implementation denies instead of allowing.
- Team synthesis no longer treats waiting_input or missing tasks as completed. Team dispatch uses an injected runtime-dispatch provider and does not claim a running task without dispatch.
- Tenant-scoped Git credentials do not fall back to other organizations/host auth. Workflow execution reads/evaluations check current workflow tenant and current/historical department membership. Remote plugin content is not served from an unscoped private-content cache.
- Interaction escalation updates only existing target_approver_id; the former updated_at write referenced a nonexistent column.
- Optional view failures remain contained to their route/section. Runtime setup can be deferred; configured connector/channel discovery does not invent fallback resources after failed reads.

## Compatibility and exclusions

API facades and existing component/renderer entry points remain because inspected consumers still use them. They re-export or delegate to one implementation; they are not duplicate business implementations. DatabaseManager delegates legacy instance methods via an explicit ownership registry. Class-level introspection/patching differs and is documented; inspected source found no such callers. Restoring the original class-level API is an explicit future compatibility decision if external consumers require it.

The subsequent user-authorized master merge incorporates enterprise queue/deployment files, workflow revision schema, model-only workflow authoring, internal MCP and playground. Incoming changes were moved into the extracted repositories, runtime collaborators, workflow modules and frontend hooks rather than restoring oversized source files. New backend router descriptors isolate queue and workflow-assistant availability.

Upstream deployment templates are retained; no deployment was performed and no outbox/exactly-once delivery guarantee is added. Queue dispatch acknowledgement is separate from runtime task completion. No mock adapter was introduced; existing fixtures were relocated without execution. Three runtime-free workflow cases were subsequently corrected to assert explicit unavailability, preserved rendered inputs and dependency-stop behavior instead of fabricated success. They do not establish successful inference/metrics accumulation. A complete pre-existing security-policy audit is not claimed.

## Completion evidence still missing

The implementation and source review cover structural changes and the fault-handling branches described above. Compilation, live route registration, real SQLite migration/concurrency behavior, UI rendering and actual failure-isolation scenarios remain unverified under the user's no-execution restriction. These must not be represented as passed. The goal must not be marked complete merely because source files are smaller.

Final source-review follow-up: capability guards also reject a recorded DISABLED state; required skill context is injected at composition boundaries and missing/unresolved context fails dependent execution explicitly. Monitoring, persisted task logs and chat history use optional runtime reads. Scheduler dispatch now shares one synchronous/awaitable return-normalization helper. Existing runtime-free workflow tests were corrected to truthful failure/dependency-stop expectations on a temporary SQLite database; none were executed.

## Latest combined-source review

Reviewed the dispatch return normalization through both worker/manual scheduler call paths and corrected its event task ID to the normalized run_id. Reviewed required skill-provider injection through runtime and workflow composition; unresolved required context now fails dependent work explicitly. Reviewed the runtime-free workflow case source against the actual failed-step persistence/stop contract and made its database isolation explicit. No project code or test was executed.

Source implementation/review is substantially complete; the remaining evidence gap is the combined application's compilation and behavior, including actual service-failure isolation. The user's no-tests/build/startup restriction remains in force, so this record does not mark those outcomes verified or the full goal achieved.

## Master merge integration (2026-10-29)

Merged master revision 523913e into the refactor branch. Revision/history transactions, optimistic concurrency, workflow task origin, generation/tool-audit schema, generation spend, authoring inference, tool-free playground and plugin refresh/cache contracts remain implemented in focused modules. Workflow step rows are saved RUNNING before dispatch and upserted with the same ID at completion; production and playground preserve actual runtime outcomes. Playground suppresses notification/reviewer/escalation callbacks. Workflow prompt/output policy and optional ChatOps are injected by backend/workflow_wiring rather than imported by the domain runner. Human approval wait is bounded to 30 minutes.

Workflow execution list/detail/evaluation share exact organization and current/historical department scope. Publication failures settle precreated queue records as FAILED and return 503; they cannot leave undelivered QUEUED rows that deduplication treats as accepted. Queue broker and worker lifecycle are separate optional capabilities. Broker absence cannot block required-core readiness. Process-local memory transport is explicitly non-durable and reported DEGRADED.

All merge review remains source-only; Python source parsing and line/conflict-marker inventories do not execute project imports or application behavior. No incoming or existing tests were run.
