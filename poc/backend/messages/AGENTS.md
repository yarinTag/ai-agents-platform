# AGENTS.md - Agent-to-Agent Messaging Service

## 1. Service Identity & Mission
The **Agent-to-Agent Messaging Service** (`poc/backend/messages/`) enables first-class, structured asynchronous and synchronous communication between agents. It facilitates peer questions, handoffs, supervisor inquiries, and status updates with strict hierarchy authorization.

---

## 2. Core Capabilities & Specializations
* **Structured Message Types (`router.py`)**:
  * `QUESTION`: Asking peer/manager for technical clarification or missing context.
  * `ANSWER`: Providing requested resolution to unblock a waiting session.
  * `REQUEST`: Soliciting action, assistance, or review.
  * `DELEGATION`: Delegating work or subtask responsibility.
  * `STATUS`: Progress reporting or heartbeat updates.
  * `RESULT`: Returning finished work outputs.
  * `HANDOFF`: Passing workflow ownership to downstream specialist (e.g. Developer -> QA).
* **Communication Authorization & Guardrails**:
  * Enforces `validate_agent_communication` before delivering messages.
  * Checks `allow_sibling_communication` and `allowed_peer_ids` to maintain organizational hierarchy.
* **Threaded Conversation Tracking**:
  * Chains replies via `parent_message_id` for transparent auditing and contextual replay.
  * Automatically transitions replied questions from `SENT`/`DELIVERED` to `RESPONDED`.
* **Real-Time Event Propagation**:
  * Emits `agent.message.sent` and `agent.message.received` through `EventService` and the live SSE stream.

---

## 3. Interfaces & Contracts

### Key Endpoints
* `POST /api/v1/messages` - Send a message from one agent to another (`201 Created`).
* `GET /api/v1/messages` - List messages (filtered by `agent_id`, `task_id`, or `run_id`).
* `GET /api/v1/messages/{message_id}` - Retrieve a message and its complete reply thread.
* `POST /api/v1/messages/{message_id}/reply` - Send a threaded reply to a message.
* `GET /api/v1/messages/threads/{message_id}` - Retrieve full conversation tree.

### Usage Example
```python
# Send a question from Developer to Manager
message_payload = {
    "from_agent_id": "lead-engineer",
    "to_agent_id": "chief-orchestrator",
    "content": "Should we use PostgreSQL or SQLite for local caching?",
    "message_type": "QUESTION",
    "task_id": "task-402"
}

# Reply to unblock
reply_payload = {
    "from_agent_id": "chief-orchestrator",
    "content": "Use SQLite with WAL mode as defined in the architectural guidelines.",
    "message_type": "ANSWER"
}
```

---

## 4. Invariant Rules & Guardrails
1. **Agent Existence**: Both `from_agent_id` and `to_agent_id` must exist in `DatabaseManager`.
2. **Authorization Enforcement**: Unauthorized peer messages are rejected with HTTP 403 (`CommunicationAuthorizationError`).
3. **Session Linkage**: When answering an unresolved task question, the message MUST include the associated `task_id` so the runtime can resume the suspended session.
4. **Immutability of Audit Log**: Message content cannot be deleted or overwritten once delivered.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any messaging logic, route, communication authorization rule, or schema in `poc/backend/messages/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.
