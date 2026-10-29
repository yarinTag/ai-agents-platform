# AGENTS.md - Supervisor & Human-In-The-Loop Approval Service

## 1. Service Identity & Mission
The **Supervisor & Human-In-The-Loop Approval Service** (`poc/backend/approvals/router.py`) orchestrates permission gating, question resolution, and supervisor oversight across the agent network. It intercepts critical or ambiguous operations, escalates queries through the agent hierarchy tree or to human operators, and unblocks frozen agent execution upon resolution.

---

## 2. Core Capabilities & Specializations
* **Hierarchical Escalation Routing**:
  * Automatically resolves target approver based on the agent's manager (`parent_id`).
  * If no parent manager exists, escalates to `HUMAN_OPERATOR`.
* **State Machine Coordination**:
  * Suspends tasks into `WAITING_INPUT` (for questions/clarifications) or `PENDING_APPROVAL` (for dangerous commands or permissions).
  * Automatically transitions tasks back to `RUNNING` or `FAILED` upon decision.
* **Resumption Triggering (`resume_task`)**:
  * Integrates with `runtime_adapter.resume_task` to inject human/manager answers directly back into the waiting Claude agent run.
* **Notification Broadcasting**:
  * Publishes `approval.required`, `approval.granted`, and `approval.denied` events across the SSE EventBus.

---

## 3. Interfaces & REST Endpoints

### API Endpoints
* `GET /api/v1/approvals/pending` - List all pending approval requests and queries.
* `POST /api/v1/approvals/` - Create a new clarification or approval request.
* `POST /api/v1/approvals/respond` - Submit an approval, denial, or answer to unblock the agent.

---

## 4. Invariant Rules & Guardrails
1. **Target Approver Fallback**: Requests without an explicit `target_approver_id` must default to the agent's `parent_id`, and if None, to `HUMAN_OPERATOR`.
2. **Immutable Audit Log**: Every resolution records `resolved_by`, `resolution_response`, and `decision` in SQLite interactions table.
3. **Fail-Closed on Rejection**: Denied requests immediately mark the associated `task_run` as `FAILED` with an explicit reason.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any approval routing logic, escalation rule, interaction state model, or endpoint in `poc/backend/approvals/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.

## Runtime import boundary
Approval routes use canonical runtime.models.TaskStatus; importing the approval inbox no longer imports the concrete process implementation. Execution/resumption remains behind the runtime dependency. No endpoint/schema changes or runtime verification were introduced.

Creating a persisted approval/question no longer requires an unused live runtime dependency. Approve/resume operations still resolve the runtime explicitly.
