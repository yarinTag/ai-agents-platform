#!/usr/bin/env python
"""
CLI and internal tool for agents to delegate subtasks to subordinate agents in the platform hierarchy.
Usage:
    python -m orchestration.delegate --target-agent product-manager --prompt "Author PRD for LMS"
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Optional, List


def delegate(
    target_agent: str,
    prompt: str,
    parent_task_id: Optional[str] = None,
    project_id: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
    acceptance_criteria: Optional[str] = None,
    timeout: int = 300,
    api_url: str = "http://localhost:8000",
    wait: bool = False
) -> dict:
    """Programmatic helper to delegate a task via internal engine or API."""
    if not parent_task_id:
        parent_task_id = os.getenv("PLATFORM_PARENT_TASK_ID")

    if not project_id:
        project_id = os.getenv("PLATFORM_PROJECT_ID")

    # Prefer direct engine invocation if running inside Python environment
    try:
        poc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if poc_dir not in sys.path:
            sys.path.insert(0, poc_dir)
        from backend.dependencies import get_orchestration_engine, get_db_manager
        engine = get_orchestration_engine()
        db = get_db_manager()

        if not parent_task_id:
            # Fallback: look up active running task in DB
            runs = db.list_task_runs(limit=5)
            for r in runs:
                if r.status.value in ("running", "queued", "waiting_for_children"):
                    parent_task_id = r.run_id
                    break

        if not parent_task_id:
            raise ValueError("No parent task ID specified and could not infer from environment or database.")

        subtask = engine.delegate_task(
            parent_task_id=parent_task_id,
            target_agent_id=target_agent,
            subtask_prompt=prompt,
            timeout_seconds=timeout,
            project_id=project_id,
            dependencies=dependencies,
            acceptance_criteria=acceptance_criteria
        )

        if wait:
            # Wait for subtask completion
            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(0.5)
                curr = db.get_task_run(subtask.run_id)
                if curr and curr.status.value in ("completed", "failed", "cancelled"):
                    return curr.to_dict()

        return subtask.to_dict()
    except Exception as direct_err:
        pass

    # Fallback to HTTP API
    if not parent_task_id:
        raise ValueError("No parent task ID specified.")

    payload = {
        "target_agent_id": target_agent,
        "subtask_prompt": prompt,
        "timeout_seconds": timeout,
        "project_id": project_id,
        "dependencies": dependencies,
        "acceptance_criteria": acceptance_criteria
    }
    api_endpoint = f"{api_url.rstrip('/')}/api/v1/tasks/{parent_task_id}/delegate"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
        subtask_id = resp_data.get("run_id") or resp_data.get("id")

        if wait and subtask_id:
            status_endpoint = f"{api_url.rstrip('/')}/api/v1/tasks/{subtask_id}"
            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(0.5)
                with urllib.request.urlopen(status_endpoint, timeout=5) as s_resp:
                    s_data = json.loads(s_resp.read().decode("utf-8"))
                    if s_data.get("status") in ("completed", "failed", "cancelled"):
                        return s_data

        return resp_data


def main():
    parser = argparse.ArgumentParser(description="Delegate a subtask to a subordinate agent.")
    parser.add_argument("--target-agent", "-a", required=True, help="ID of the target subordinate agent")
    parser.add_argument("--prompt", "-p", required=True, help="Detailed prompt/instructions for the subtask")
    parser.add_argument("--parent-task-id", "-t", default=os.getenv("PLATFORM_PARENT_TASK_ID"), help="ID of the parent task")
    parser.add_argument("--project-id", default=os.getenv("PLATFORM_PROJECT_ID"), help="Project ID context")
    parser.add_argument("--dependencies", "-d", default=None, help="Comma-separated prerequisite task IDs")
    parser.add_argument("--acceptance-criteria", "-c", default=None, help="Acceptance criteria for task completion")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--api-url", default=os.getenv("PLATFORM_API_URL", "http://localhost:8000"), help="Platform API base URL")
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for subtask completion and return actual result")

    args = parser.parse_args()

    deps = [d.strip() for d in args.dependencies.split(",") if d.strip()] if args.dependencies else None

    try:
        result = delegate(
            target_agent=args.target_agent,
            prompt=args.prompt,
            parent_task_id=args.parent_task_id,
            project_id=args.project_id,
            dependencies=deps,
            acceptance_criteria=args.acceptance_criteria,
            timeout=args.timeout,
            api_url=args.api_url,
            wait=args.wait
        )
        subtask_id = result.get("run_id") or result.get("id")
        print(f"Subtask delegated successfully: ID={subtask_id} -> Agent={args.target_agent}")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Failed to delegate task: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
