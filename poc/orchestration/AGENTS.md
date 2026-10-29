# AGENTS.md - Orchestration & Hierarchy Service

## 1. Service Identity & Mission
The **Orchestration & Hierarchy Service** (`poc/orchestration/`) is the platform's organizational nervous system. It governs how autonomous agents relate to one another, delegate subtasks, enforce supervisor chains, coordinate multi-tenant scoping across organizations and departments, and enforce department-level MCP governance checks.

---

## 2. Core Capabilities & Specializations

* **Hierarchical Delegation Engine (`engine.py`)**:
  * Enables manager agents to break down high-level prompts into granular subtasks assigned to subordinate worker agents.
  * Manages recursive task trees (`parent_task_id`, `root_task_id`, `assigned_by`) and propagates outputs upward.
  * Preserves multi-tenant tenant boundaries by attaching `organization_id` to all delegated subtasks.
* **Concurrency Caps & Overload Protection**:
  * Enforces `max_concurrent_children` per manager to prevent worker runaway.
  * Rejects delegations exceeding capacity with HTTP 429 (`ConcurrencyLimitExceededError`).
* **Hierarchy Validation (`hierarchy_validator.py`)**:
  * Prevents cyclic supervisor relationships (e.g., A -> B -> A).
  * Enforces maximum hierarchy depth (default: 5 tiers) to prevent recursion exhaustion.
* **Multi-Tier Supervisor Resolver (`supervisor_resolver.py`)**:
  * **Tier 1 (Automated Memory Resolution)**: When a worker asks a question, automatically inspects `project_memories` for matching ADRs or conventions. If a confident match is found, auto-resolves and resumes the task without human intervention.
  * **Tier 2 (Manager Routing)**: If unresolvable from memory, routes the question to the worker's direct manager (`parent_id`).
  * **Tier 3 (Human Escalation)**: If no manager exists, escalates to `HUMAN_OPERATOR` via the approvals inbox and visual pixel office alerts.
* **Department MCP Governance Checks (`check_department_mcp_access`)**:
  * Pre-flight verification checking whether an agent's assigned department possesses permissions for requested MCP connectors and specific tools.
  * Prevents unauthorized tool execution across departmental boundaries.

---

## 3. Interfaces & Contracts

### Implementation ownership after modular extraction

`engine.py` retains the public `OrchestrationEngine` methods, hierarchy validation, retry/remediation, recovery and queries. `delegation.py` owns task creation/dispatch through a frozen `DelegationContext` containing only the task-store port, runtime, hierarchy validator callback and event callback. `completion.py:CompletionCoordinator` owns structured completion results, queued dependency release and recursive parent propagation. Runtime lookup is a callback so later runtime selection remains visible. `errors.py` is the single owner of DelegationError and ConcurrencyLimitExceededError, re-exported by engine imports.

`ports.py` defines TaskStore, SupervisorStore, HierarchyStore, IntelligenceStore, TeamStore and EventEmitter protocols. These contracts import provider-independent runtime models and do not import persistence or concrete runtime services. Hierarchy validation, project intelligence and team coordination use type-checking-only structural storage imports. Team coordination no longer imports the orchestration implementation merely for its unused collaborator annotation. No module imports the application dependency container.

Completion's atomic parent status update belongs to `TasksRepository.claim_waiting_parent`: only a `waiting_for_children` parent can be claimed as `running`, and a false return prevents duplicate propagation. The conditional predicate, commit/rollback boundary and return decision remain unchanged; completion no longer opens a SQL connection.

`supervisor_resolver.py` retains the public coordinator, resolve/escalate methods and compatibility helper methods. `decision_envelopes.py` owns DecisionQuestionEnvelope/DecisionAnswerEnvelope; they remain importable from supervisor_resolver. `supervisor_decision.py` owns background supervisor inference and worker continuation with explicit storage/event/runtime parameters. `memory_resolution.py` owns memory word/tag scoring. SupervisorResolver accepts an optional `project_intelligence` collaborator; the existing ProjectIntelligence implementation is imported/created only when one is not supplied.

`source_parsers.py` owns Python AST, Markdown section and sliding-window chunk extraction independently of Qdrant/FastEmbed. CodeIndexer delegates its original parser methods and keeps client lifecycle, file cache, indexing and search. The Python parser receives the instance's chunk fallback callback, preserving override behavior. Optional vector-library availability semantics and embedding/storage configuration are unchanged.

Preserved transitions include delegation to QUEUED/RUNNING, parent WAITING_FOR_CHILDREN, compare-and-set parent resumption, child failure propagation, retry and restart recovery, clarification WAITING_INPUT and existing fast/slow resolution paths. Existing optional-runtime handling, permission-check fallback behavior and manager suggested-option fallback are intentionally unchanged; changing those decisions requires a separately documented behavior change. These source moves do not establish process isolation or runtime resilience.

All implementation files in this extraction are below 500 physical lines. No tests, imports, build, lint or live execution were run. Source review does not establish behavior or concurrent recovery correctness.

### Key Classes & Methods
```python
# Concurrency, Delegation & MCP Checks
engine = OrchestrationEngine(db_manager, runtime_adapter, event_service)

# 1. Delegate subtask within tenant boundary
run_id = await engine.delegate_task(
    manager_agent_id="eng-lead",
    worker_agent_id="backend-dev",
    prompt="Refactor database schema",
    parent_task_id="task-100",
    project_id="core-app"
)

# 2. Check department MCP access
mcp_check = engine.check_department_mcp_access(
    department_id="dept_engineering",
    connector_id="github",
    tool_name="git_commit"
)
# Returns: {"allowed": bool, "reason": str}

# 3. Multi-Tier Question Resolution
resolver = SupervisorResolver(db_manager, event_bus, runtime_adapter)
resolution = resolver.resolve_or_escalate_question(
    task_id="task-101",
    requester_agent_id="backend-dev",
    question="What is the JWT expiration duration?",
    project_id="core-app"
)
# Returns: {"status": "AUTO_RESOLVED" | "PENDING_INPUT", "target_approver": ...}
```

---

## 4. Invariant Rules & Guardrails
1. **Never Delegate to Self**: A manager agent cannot delegate tasks to itself.
2. **Never Delegate to Superior**: A worker cannot delegate tasks up the hierarchy chain.
3. **No Cross-Tenant Leaks**: Delegated tasks inherit the parent task's `organization_id` strictly.
4. **No Phantom Tasks**: Every delegated subtask must have a verified parent in the database before execution commences.
5. **Zero Silent Hangs**: If a worker asks a question, it must either be auto-resolved within 100ms or explicitly transitioned to `WAITING_INPUT`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any orchestration logic, delegation rule, hierarchy validation, supervisor resolution, or MCP governance check in `poc/orchestration/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.

## Final parent review corrections
TasksRepository.claim_waiting_parent owns the atomic parent-resumption claim; SupervisorStore.retarget_interaction owns approver changes. The former updated_at escalation write referenced a nonexistent column and is removed without schema migration. Missing MCP permission implementation now returns allowed=false. Optional intelligence failures leave remaining clarification tiers usable. Supervisor inference timeout/failure never selects the first suggested option as an answer; pending interactions retarget HUMAN_OPERATOR.

TeamCoordinator accepts a lazy dispatch_provider instead of requiring a concrete orchestration engine for team administration. Dispatch persists QUEUED runs, invokes the dispatcher, and records FAILED when dispatch fails; no fabricated RUNNING state is emitted without dispatch. Team synthesis requires nonempty requested IDs and completed results; missing/paused tasks yield IN_PROGRESS and a team.progress event, not team.completed. Stable string statuses/schema remain unchanged apart from these truthful decisions.

Parent completion treats every nonterminal child (including pending approval) as still waiting and treats cancelled children as failure. Project status verification does not infer that external QA/security checks ran merely from task status; non-completed records block GO.
