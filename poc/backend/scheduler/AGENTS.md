# AGENTS.md - Scheduler & Cron Engine Service

## 1. Service Identity & Mission
The **Scheduler & Cron Engine Service** (`poc/backend/scheduler/engine.py` & `poc/backend/scheduler/router.py`) provides headless, autonomous time-based task triggering. It enables agents to run routine maintenance, audits, security sweeps, and data syncing according to standard 5-part Cron expressions.

---

## 2. Core Capabilities & Specializations
* **Headless Background Polling Loop**:
  * An asynchronous lifespan background worker (`asyncio.sleep` polling) checking `cron_jobs` table for due tasks (`next_run_at <= CURRENT_TIMESTAMP`).
* **Cron Expression Forecasting (`croniter`)**:
  * Accurate calculation of future run timestamps.
  * Validation endpoint (`POST /api/v1/schedules/validate`) returning 5 upcoming execution times.
* **Concurrency Overlap Policies**:
  * `SKIP` (Default): If an agent is already actively executing a task, skips this tick to prevent overload.
  * `ALLOW`: Dispatches concurrent task runs.
  * `COALESCE`: Combines missed executions into a single catch-up run.
* **Autonomous Task Dispatching**:
  * Upon trigger, automatically spawns an `AgentRun` through `runtime_adapter.start_task` and logs execution history in `last_run_id` and `last_status`.

---

## 3. Interfaces & REST Endpoints

### API Endpoints
* `GET /api/v1/schedules/` - List all scheduled jobs (filterable by `agent_id`, `project_id`, `enabled`).
* `POST /api/v1/schedules/` - Create a new cron job.
* `POST /api/v1/schedules/{id}/trigger` - Run scheduled job immediately on demand.
* `POST /api/v1/schedules/{id}/toggle` - Pause or enable schedule without deleting it.
* `POST /api/v1/schedules/validate` - Test cron expression syntax and view upcoming schedule.
* `DELETE /api/v1/schedules/{id}` - Remove scheduled job.

---

## 4. Invariant Rules & Guardrails
1. **Clock Drift Protection**: `next_run_at` must always be calculated from the current execution reference point, preventing backward time loops.
2. **Graceful Shutdown**: On FastAPI shutdown, `_cron_engine.stop()` must cancel the polling task and allow in-flight dispatches to complete gracefully.
3. **Database Consistency**: Every triggered job must atomically update `last_run_at`, `last_run_id`, and `next_run_at` in a single transaction.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any scheduler logic, polling frequency, cron calculation, or scheduling endpoint in `poc/backend/scheduler/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.

## Optional worker boundary
expressions.py owns calculate_next_run/get_upcoming_runs/validate_cron_expression without importing the worker. The package lazily exports CronSchedulerEngine, and router annotations use RuntimeAdapter/canonical models rather than the concrete subprocess adapter. scheduler-worker readiness is separate from scheduler router availability; runtime outage stops worker startup while stored schedule APIs remain usable. Only explicit dispatch requires live runtime. No tests/startup were run.

Worker/manual dispatch share dispatch_scheduled_job. It accepts synchronous or awaitable RuntimeAdapter returns and requires a nonempty run ID before recording dispatch. Worker busy detection uses list_runs; no unavailable get_active_runs concrete method is assumed.
Final source review also aligned TASK_CREATED.task_id with the normalized dispatch run_id; it no longer references the removed task_run local after dispatch extraction. No scheduler or test was executed.
