"""Schedule execution dispatch contract shared by worker and manual triggers."""

import inspect


async def dispatch_scheduled_job(runtime, job):
    result = runtime.start_task(
        prompt=job["prompt"], agent_id=job["agent_id"], project_id=job.get("project_id"),
    )
    if inspect.isawaitable(result):
        result = await result
    run_id = getattr(result, "run_id", result)
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("Execution dispatcher did not return a run ID")
    return run_id
