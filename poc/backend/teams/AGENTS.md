# AGENTS.md - Multi-Agent Teams Service

## 1. Service Identity & Mission
The **Multi-Agent Teams Service** (`poc/backend/teams/` & `poc/orchestration/team_coordinator.py`) manages dynamic, cross-functional agent squads grouped together to achieve complex, shared organizational goals under designated leadership.

---

## 2. Core Capabilities & Specializations
* **Team Lifecycle & Membership (`router.py`)**:
  * Create, query, update, and disband agent teams (`AgentTeam`).
  * Enforces role assignment: designated `manager_agent_id` with specialized member agents.
* **Collective Mission Dispatch (`TeamCoordinator`)**:
  * Decomposes high-level objectives (`shared_goal`) into coordinated subtasks across team members.
  * Links member task runs to a common parent task or executive goal.
* **Executive Synthesis**:
  * Aggregates completed artifacts and deliverables from multiple team members into a unified completion report.
  * Preserves full multi-agent audit trail and event propagation.

---

## 3. Interfaces & Contracts

### Key Endpoints
* `POST /api/v1/teams` - Create a team with manager and members (`201 Created`).
* `GET /api/v1/teams` - List all teams (optionally filtered by `project_id`).
* `GET /api/v1/teams/{team_id}` - Retrieve team details and active member roles.
* `POST /api/v1/teams/{team_id}/dispatch` - Dispatch collaborative task runs to team members.
* `POST /api/v1/teams/{team_id}/synthesize` - Synthesize member task outputs into an executive summary.
* `PATCH /api/v1/teams/{team_id}` - Update team status (`ACTIVE`, `COMPLETED`, `DISBANDED`).

### Usage Example
```python
# Create and dispatch a team
team_payload = {
    "name": "Feature Ship Squad",
    "manager_agent_id": "delivery-lead",
    "member_agent_ids": ["lead-engineer", "security"],
    "project_id": "core-platform"
}
# Dispatch shared mission
dispatch_payload = {
    "shared_goal": "Implement and audit the file explorer component",
    "member_prompts": {
        "lead-engineer": "Build the frontend folder tree",
        "security": "Review path traversal protections"
    }
}
```

---

## 4. Invariant Rules & Guardrails
1. **Manager Membership**: The manager agent must exist in the database and be registered as the team coordinator.
2. **Member Verification**: All `member_agent_ids` must correspond to active agents in `DatabaseManager`.
3. **No Phantom Tasks**: All member subtasks dispatched through a team must record `assigned_by=manager_agent_id`.
4. **Lifecycle Progression**: Teams begin in `ACTIVE` state and transition explicitly to `COMPLETED` or `DISBANDED`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any multi-agent team coordination logic, membership model, dispatch flow, or endpoint in `poc/backend/teams/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.
