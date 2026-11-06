# AGENTS.md - Events & Real-Time Streaming Bus Service

## 1. Service Identity & Mission
The **Events & Real-Time Streaming Bus Service** (`poc/events.py` & `poc/backend/events/router.py`) provides the reactive backbone of the platform. It captures lifecycle events from agents, tasks, schedules, approvals, and chats, broadcasting them instantaneously to connected UI dashboards and external listeners.

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
* `GET /api/v1/events/system/stats` - Platform health and task execution metrics.

---

## 4. Invariant Rules & Guardrails
1. **Strict Monotonic Sequencing**: Every persisted event must have a strictly increasing `sequence_number` to guarantee total ordering.
2. **Non-Blocking Publishers**: Publishing an event must NEVER block or fail an agent's core execution loop.
3. **Structured Payload Integrity**: Every event must include a valid timestamp, event_id, event_type, and source identifier.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any event type, pub/sub queue logic, SSE streaming protocol, or event persistence schema in `poc/backend/events/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.
# Optional runtime monitoring

System statistics and health use an optional runtime dependency. When inference is unavailable they still return stored information; stats includes runtime_available=false and recorded recent active tasks, while health reports the unavailable runtime component. Monitoring uses the RuntimeAdapter.list_runs contract rather than the private _runs dictionary. This is separate from /health liveness and /health/ready required-core database readiness. No monitoring endpoint was executed during this refactor.

## Execution origin in event feeds
EventService.emit enriches task event payloads with workflow_execution_id/workflow_id resolved from persisted step and ancestor records. SSE serialization also enriches historical or direct EventBus publications lacking that context, so filtering does not depend on a producer. Existing event names and global stream subscription remain unchanged. `GET /api/v1/events/system/recent-activity` accepts execution_scope=all|office|workflow (422 for invalid values), filters before LIMIT and scopes task queries to the authenticated organization. Office/Live Flow clients request office; other clients default to all.

## Tenant-scoped streaming
GET /api/v1/events/stream builds events/scope.EventScope from get_authorized_scope. Each replayed and live event resolves its owner with storage get_event_owner(task_id, agent_id, project_id), checking the task first (org plus its agent's department), then the agent, then the project, cached per connection. It streams only owner.organization_id == caller org, and for non-admins only when the department is null or among their departments. Unattributable events are dropped. Lookups run via asyncio.to_thread in the consumer, never in the publisher's filter. /system/stats requires an org and filters agents, projects, task runs and active runs by organization; skills are global or belong to the org's projects. /system/health messages carry no cross-tenant counts.


## Current stream and department boundaries (2026-11-05)
EventScope now rechecks active user, organization, current memberships and current event subject
ownership per event; the stale owner cache no longer authorizes a moved subject. Scope includes
selected_department_id and JWT expires_at; unauthorized/expired/revoked events are dropped.
A department query is accepted only for authenticated SSE and validated against current grants.
Response policy scopes recent activity and statistics. Legacy /ws/system closes1008 until a
separate tenant-authenticated websocket protocol exists; SSE remains supported. No streams,
model calls, tests or application startup were executed locally.


AI-15 plans per-connector verified ingress, normalized bounded events, durable dedup/outbox and authorized trigger principals. No such listener is implemented/enabled by this ADR; saved trigger_enabled is not delivery evidence. Provider authenticity must precede privileged event interpretation; policy independently authorizes the normalized sender and action.
