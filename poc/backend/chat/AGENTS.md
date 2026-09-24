# AGENTS.md - Interactive Agent Mini-Chat Service

## 1. Service Identity & Mission
The **Interactive Agent Mini-Chat Service** (`poc/backend/chat/router.py`) provides real-time, bidirectional communication between the human operator and AI agents. It powers interactive conversation drawers, streams intermediate thoughts and tool executions, and automatically resolves blocked questions or approval requests directly from dialogue.

---

## 2. Core Capabilities & Specializations
* **Conversational Lifecycle & Thread Persistence**:
  * One persistent `agent_conversations` session per agent (optionally scoped to a `project_id`).
  * Full chronological transcript of messages with typed roles (`USER`, `AGENT`, `SYSTEM`, `TOOL`).
* **Interactive Blocking Interception**:
  * If an agent is blocked in `WAITING_INPUT` or `PENDING_APPROVAL`, a user chat response automatically resolves the pending interaction (`db.resolve_interaction`).
  * Seamlessly transitions the task back to `RUNNING` and emits `approval.granted` via the platform `EventBus`.
* **Autonomous Task Launch / Resumption**:
  * If no blocking interaction exists, the user message immediately launches a fresh task or resumes execution via `runtime_adapter.start_task`.
* **Real-Time Event Broadcasting**:
  * Broadcasts `chat.message` events immediately upon receipt to keep connected SSE dashboards in sync.

---

## 3. Interfaces & REST Endpoints

### API Endpoints
* `GET /api/v1/chat/{agent_id}/messages` - Retrieve full message history, agent thoughts, and tool execution logs.
* `POST /api/v1/chat/{agent_id}/messages` - Send an interactive prompt to the agent, resolving blockers or launching tasks.
* `POST /api/v1/chat/{agent_id}/clear` - Reset/clear dialogue history for the specified agent.

---

## 4. Invariant Rules & Guardrails
1. **Agent Existence**: Messages can only be directed to valid agents registered in SQLite (`agents` table).
2. **Atomic Resolution**: Resolving blocked interactions via chat must atomically transition the interaction status and the task status.
3. **Event Stream Synchronization**: Every user message and interaction resolution must publish an event through `EventBus` to guarantee UI coherence.
