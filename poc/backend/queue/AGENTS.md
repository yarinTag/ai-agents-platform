# AGENTS.md - Queue & Distributed Message Broker Service

## 1. Service Identity & Mission
The **Queue & Distributed Message Broker Service** (`poc/backend/queue/`) provides the high-throughput, fault-tolerant backbone for task dispatching and workflow execution across the AI Agents Platform. It decouples the FastAPI control plane from asynchronous worker runners using RabbitMQ (AMQP 0-9-1) with durable priority queues, dead-letter exchanges (DLX), multi-tenant department routing, and priority-based scheduling.

---

## 2. Core Capabilities & Architecture

* **Dual AMQP Connection Manager (`broker.py`)**:
  * Establishes resilient async connections via `aio-pika.connect_robust` to `RABBITMQ_URL`.
  * RabbitMQ failure raises QueueUnavailableError; only explicit PLATFORM_QUEUE_MODE=memory selects process-local, non-durable asyncio.PriorityQueue transport.
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
2. **Explicit Transport**: RabbitMQ outages mark only queue unavailable; memory transport must be explicitly selected and is reported DEGRADED.
3. **Tenant Context Headers**: Every published message must include `organization_id` and `department_id` in AMQP headers.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule
Whenever any queue name, exchange configuration, retry logic, or worker contract in `poc/backend/queue/` is modified, this document must be updated in the same commit.

## Modular dispatch integration
backend/queue_lifecycle independently owns broker and worker startup/shutdown. Standalone run_worker uses that same composition, including persistence and injected workflow guards; absent workflow handler never creates a bypass engine. dispatch.TaskPayloadExecutor preserves task_id, ACKs runtime acceptance and leaves terminal task outcome to runtime. No missing runtime or dispatch-only path fabricates COMPLETED. Workflow execution runs through asyncio.to_thread; paused/failed engine outcomes are acknowledged and never automatically replayed as transport failures. Precheck exceptions settle known executions FAILED. Rabbit retries republish confirmed bytes with incremented retry_count before ACK; up to three retries follow the initial attempt. Memory payloads use deep copies and sequence numbers for priority ties. Accepted side effects are not exactly-once; no transactional outbox is claimed.

Incoming tests have not been run. All merge review was source-only.

## Queue monitoring availability (2026-10-30)
The router descriptor is queue-api; queue remains the independent transport capability. GET /status and GET /dlq stay authenticated and readable when broker initialization fails, exposing connected=false rather than returning a transport-availability503. POST /retry/{message_id} and /publish-test explicitly require queue dispatch availability. Disabling queue-api removes the API independently of transport/worker use. No broker was started and no tests/build were run for this correction.
