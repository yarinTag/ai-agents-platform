# AGENTS.md - Events & Real-Time Streaming Bus Service

## 1. Service Identity & Mission
The **Events & Real-Time Streaming Bus Service** (`poc/events.py` & `poc/backend/api/events.py`) provides the reactive backbone of the platform. It captures lifecycle events from agents, tasks, schedules, approvals, and chats, broadcasting them instantaneously to connected UI dashboards and external listeners.

---

## 2. Core Capabilities & Specializations
* **High-Throughput In-Memory Pub/Sub (`EventBus`)**:
  * Decouples event producers from consumers with low-latency dispatch.
  * Supports topic/event_type filtering and project-specific subscription scopes.
* **FIFO Queue Drop Protection**:
  * In-memory subscriber queues implement bounded capacity.
  * When a consumer is slow, the oldest event is gracefully dropped to prevent memory leaks while preserving real-time freshness.
* **Persistent Event Store (`EventService`)**:
  * Persists every `PlatformEvent` in SQLite with monotonically increasing `sequence_number`.
  * Allows clients reconnecting to replay missed events using `Last-Event-ID` header.
* **Server-Sent Events Stream (`/api/v1/events/stream`)**:
  * Standard HTTP SSE stream consumed by the dashboard's `useOfficeEvents` hook.
  * Keeps the pixel office, desk statuses, and task counters in lockstep with the backend.

---

## 3. Interfaces & Contracts

### Publishing Events
```python
from events import EventBus, PlatformEvent, EventType

event_bus = get_event_bus()
event_bus.publish(PlatformEvent(
    event_id=f"evt_{datetime.now().timestamp()}",
    event_type=EventType.TASK_STARTED.value,
    agent_id="backend-dev",
    task_id="task-123",
    project_id="core-app",
    payload={"prompt": "Build API", "status": "running"},
    source="runtime_adapter"
))
```

### SSE Stream Endpoint
* `GET /api/v1/events/stream` - Persistent SSE stream with 15s keepalive ping and historical replay.

---

## 4. Invariant Rules & Guardrails
1. **Strict Monotonic Sequencing**: Every persisted event must have a strictly increasing `sequence_number` to guarantee total ordering.
2. **Non-Blocking Publishers**: Publishing an event must NEVER block or fail an agent's core execution loop.
3. **Structured Payload Integrity**: Every event must include a valid timestamp, event_id, event_type, and source identifier.
