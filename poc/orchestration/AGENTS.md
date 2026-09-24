# AGENTS.md - Orchestration & Hierarchy Service

## 1. Service Identity & Mission
The **Orchestration & Hierarchy Service** (`poc/orchestration/`) is the platform's organizational nervous system. It governs how autonomous agents relate to one another, delegate subtasks, enforce supervisor chains, and coordinate resolution when a worker encounters missing parameters.

---

## 2. Core Capabilities & Specializations
* **Hierarchical Delegation Engine (`engine.py`)**:
  * Allows a manager agent to break down high-level prompts into granular subtasks assigned to subordinate worker agents.
  * Constructs and manages recursive task trees (`parent_task_id`, `root_task_id`, `assigned_by`).
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

---

## 3. Interfaces & Contracts

### Key Classes & Methods
```python
# Concurrency & Delegation
engine = OrchestrationEngine(db_manager, runtime_adapter, event_service)
run_id = await engine.delegate_task(
    manager_agent_id="eng-lead",
    worker_agent_id="backend-dev",
    prompt="Refactor database schema",
    parent_task_id="task-100",
    project_id="core-app"
)

# Multi-Tier Question Resolution
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
3. **No Phantom Tasks**: Every delegated subtask must have a verified parent in the database before execution commences.
4. **Zero Silent Hangs**: If a worker asks a question, it must either be auto-resolved within 100ms or explicitly transitioned to `WAITING_INPUT`.
