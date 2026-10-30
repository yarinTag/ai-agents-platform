"""Tool-free playground run dispatch; no ordinary runtime task IDs allowed."""
import threading


def start_playground_task(adapter, agent_id: str, task_id: str, prompt: str, workspace: str) -> str:
    """Run fresh inference without tools, external escalation, or completion callbacks."""
    if adapter._shutting_down:
        raise RuntimeError("Runtime is shutting down")
    if not task_id.startswith("pg_task_"):
        raise ValueError("Playground tasks require a pg_task_ ID")
    db_manager = adapter.services.database()
    agent = db_manager.get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent not found: {agent_id}")
    active = sum(1 for process in adapter._processes.values() if process.poll() is None)
    if active >= adapter.max_concurrent_runs:
        raise RuntimeError("Platform concurrency limit reached")
    run = db_manager.get_task_run(task_id)
    if not run:
        raise ValueError("Playground task record not found")
    adapter._runs[task_id] = run
    thread = threading.Thread(
        target=adapter._execute_task,
        args=(task_id, agent, None, prompt, None, False),
        kwargs={"playground_workspace": workspace}, daemon=True
    )
    adapter._execution_threads[thread] = task_id
    thread.start()
    return task_id

