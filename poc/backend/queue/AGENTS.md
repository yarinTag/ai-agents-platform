# AGENTS.md - Queue & Distributed Message Broker Service

## 1. Service Identity & Mission
The **Queue & Distributed Message Broker Service** (`poc/backend/queue/`) provides the high-throughput, fault-tolerant backbone for task dispatching and workflow execution across the AI Agents Platform. It decouples the FastAPI control plane from asynchronous worker runners using RabbitMQ (AMQP 0-9-1) with quorum queues, dead-letter exchanges (DLX), multi-tenant department routing, and priority-based scheduling.

---

## 2. Core Capabilities & Architecture

* **Dual AMQP Connection Manager (`broker.py`)**:
  * Establishes resilient async connections via `aio-pika.connect_robust` to `RABBITMQ_URL`.
  * Automatic graceful fallback to in-memory `asyncio.PriorityQueue` if RabbitMQ is offline or during testing, guaranteeing zero broken environments.
  * Declares topic exchanges (`platform.tasks.exchange`) and direct dead-letter exchanges (`platform.tasks.dlx`).
* **Topic Routing & Priority Bands (`publisher.py`)**:
  * Priority 8–10 ➔ `platform.tasks.high_priority` (`task.urgent.#`, `task.security.#`).
  * Priority 4–7 ➔ `platform.tasks.standard` (`task.standard.#`, `task.dept.*`).
  * Priority 1–3 ➔ `platform.tasks.background` (`task.background.#`, `task.cron.#`).
  * Workflow DAG steps ➔ `platform.workflows.step` (`workflow.step.#`).
  * Workflow Macro Executions ➔ `platform.workflows.execution` (`workflow.execution.#`).
* **Distributed Worker Consumer (`worker.py`)**:
  * `QueueWorkerDaemon` processes messages with bounded concurrency (`max_concurrency`).
  * Handles both atomic agent tasks (`agent_task`) and workflow macro executions (`workflow_execution`) via `WorkflowEngine`.
  * Enforces manual acknowledgments (`basic_ack`).
  * Recoverable failures re-queue with exponential backoff up to 3 attempts.
  * Fatal or exhausted failures route to `platform.tasks.dlq` for human investigation.
* **Management & DLQ REST API (`router.py`)**:
  * `GET /api/v1/queue/status` - Live health, queue depths, active workers.
  * `GET /api/v1/queue/dlq` - Inspect dead-lettered messages.
  * `POST /api/v1/queue/retry/{message_id}` - Re-enqueue dead letters.
  * `POST /api/v1/queue/publish-test` - Test queue dispatch.

---

## 3. Invariant Rules & Guardrails
1. **Zero Message Loss**: Messages must never be dropped silently; any message failing 3 attempts must be captured in the DLQ store.
2. **Transparent Fallback**: When RabbitMQ is unreachable, fallback queues must emulate priority ordering without crashing the server.
3. **Tenant Context Headers**: Every published message must include `organization_id` and `department_id` in AMQP headers.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule
Whenever any queue name, exchange configuration, retry logic, or worker contract in `poc/backend/queue/` is modified, this document must be updated in the same commit.
