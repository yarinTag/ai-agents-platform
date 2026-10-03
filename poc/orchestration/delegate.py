#!/usr/bin/env python3
"""
CLI tool for agents to delegate subtasks to subordinate agents in the platform hierarchy.
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


def wait_for_subtask_api(api_url: str, subtask_id: str, target_agent: str, timeout_sec: int, poll_interval: float = 3.0):
    start_time = time.time()
    last_status_print = 0.0
    task_endpoint = f"{api_url.rstrip('/')}/api/v1/tasks/{subtask_id}"

    print(f"\n[DELEGATE] Subtask {subtask_id} launched for @{target_agent}. Waiting for completion (timeout: {timeout_sec}s)...", flush=True)

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_sec:
            print(f"\n[DELEGATE] ⚠️ Subtask {subtask_id} timed out after {int(elapsed)}s. Still running asynchronously.", flush=True)
            sys.exit(0)

        try:
            req = urllib.request.Request(task_endpoint, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                status = (data.get("status") or "").lower()

                if status in ("completed", "failed", "cancelled", "waiting_input", "pending_approval"):
                    print(f"\n[DELEGATE] Subtask reached terminal status: '{status}' after {int(elapsed)}s.", flush=True)
                    if status == "completed":
                        result = data.get("result") or "(Task completed successfully. Check workspace files.)"
                        print(f"\n--- SUBTASK OUTPUT (@{target_agent}) ---\n{result}\n---------------------------------------\n", flush=True)
                        sys.exit(0)
                    elif status == "waiting_input":
                        result = data.get("result") or "(Subtask is waiting for your supervisor input)"
                        print(f"\n--- SUPERVISOR INPUT REQUIRED (@{target_agent}) ---\n{result}\n------------------------------------------------\n", flush=True)
                        sys.exit(0)
                    else:
                        error = data.get("error") or "Unknown error"
                        print(f"\n--- SUBTASK FAILED (@{target_agent}) ---\nStatus: {status}\nError: {error}\n-------------------------------------\n", flush=True)
                        sys.exit(1)

                if time.time() - last_status_print >= 10.0:
                    print(f"[DELEGATE] Still working... @{target_agent} ({subtask_id}) status: {status} ({int(elapsed)}s elapsed)", flush=True)
                    last_status_print = time.time()

        except Exception:
            pass

        time.sleep(poll_interval)


def wait_for_subtask_db(subtask_id: str, target_agent: str, timeout_sec: int, poll_interval: float = 3.0):
    start_time = time.time()
    last_status_print = 0.0

    print(f"\n[DELEGATE] Subtask {subtask_id} launched for @{target_agent}. Waiting for completion (timeout: {timeout_sec}s)...", flush=True)

    try:
        poc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if poc_dir not in sys.path:
            sys.path.insert(0, poc_dir)
        from backend.dependencies import get_db_manager
        db_manager = get_db_manager()
    except Exception as e:
        print(f"Could not load db_manager for polling: {e}")
        return

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_sec:
            print(f"\n[DELEGATE] ⚠️ Subtask {subtask_id} timed out after {int(elapsed)}s.", flush=True)
            sys.exit(0)

        task = db_manager.get_task_run(subtask_id)
        if task:
            status = getattr(task.status, "value", str(task.status)).lower()
            if status in ("completed", "failed", "cancelled", "waiting_input", "pending_approval"):
                print(f"\n[DELEGATE] Subtask reached terminal status: '{status}' after {int(elapsed)}s.", flush=True)
                if status == "completed":
                    result = task.result or "(Task completed successfully. Check workspace files.)"
                    print(f"\n--- SUBTASK OUTPUT (@{target_agent}) ---\n{result}\n---------------------------------------\n", flush=True)
                    sys.exit(0)
                elif status == "waiting_input":
                    result = task.result or "(Subtask is waiting for your supervisor input)"
                    print(f"\n--- SUPERVISOR INPUT REQUIRED (@{target_agent}) ---\n{result}\n------------------------------------------------\n", flush=True)
                    sys.exit(0)
                else:
                    error = task.error or "Unknown error"
                    print(f"\n--- SUBTASK FAILED (@{target_agent}) ---\nStatus: {status}\nError: {error}\n-------------------------------------\n", flush=True)
                    sys.exit(1)

        if time.time() - last_status_print >= 10.0:
            print(f"[DELEGATE] Still working... @{target_agent} ({subtask_id}) ({int(elapsed)}s elapsed)", flush=True)
            last_status_print = time.time()

        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Delegate a subtask to a subordinate agent.")
    parser.add_argument("--target-agent", "-a", required=True, help="ID of the target subordinate agent")
    parser.add_argument("--prompt", "-p", required=True, help="Detailed prompt/instructions for the subtask")
    parser.add_argument("--parent-task-id", "-t", default=os.getenv("PLATFORM_PARENT_TASK_ID"), help="ID of the parent task")
    parser.add_argument("--project-id", default=os.getenv("PLATFORM_PROJECT_ID"), help="Project ID context")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    parser.add_argument("--api-url", default=os.getenv("PLATFORM_API_URL", "http://localhost:8000"), help="Platform API base URL")
    parser.add_argument("--no-wait", action="store_true", default=False, help="Do not wait for subtask completion (fire-and-forget)")
    parser.add_argument("--description", "-d", default=None, help="Optional human-readable description")

    args, _unknown = parser.parse_known_args()

    parent_task_id = args.parent_task_id
    if not parent_task_id:
        # Fallback: look up active running task in DB
        try:
            import sqlite3
            db_path = os.path.join(os.path.dirname(__file__), "..", "data", "agents_platform.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT run_id FROM task_runs WHERE status IN ('running', 'queued') ORDER BY started_at DESC LIMIT 1")
                row = c.fetchone()
                if row:
                    parent_task_id = row[0]
        except Exception:
            pass

    if not parent_task_id:
        print("Error: No parent task ID specified and could not infer from environment or database.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "target_agent_id": args.target_agent,
        "subtask_prompt": args.prompt,
        "timeout_seconds": args.timeout,
        "project_id": args.project_id
    }

    api_endpoint = f"{args.api_url.rstrip('/')}/api/v1/tasks/{parent_task_id}/delegate"

    subtask_id = None
    used_api = False

    # Attempt via HTTP API first
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            subtask_id = resp_data.get("run_id") or resp_data.get("task_id")
            used_api = True
            print(f"Subtask delegated successfully: ID={subtask_id} -> Agent={args.target_agent}")
    except Exception as http_err:
        # Direct fallback via python engine if API is not responding
        try:
            poc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            if poc_dir not in sys.path:
                sys.path.insert(0, poc_dir)
            from backend.dependencies import get_orchestration_engine
            engine = get_orchestration_engine()
            subtask = engine.delegate_task(
                parent_task_id=parent_task_id,
                target_agent_id=args.target_agent,
                subtask_prompt=args.prompt,
                timeout_seconds=args.timeout,
                project_id=args.project_id
            )
            subtask_id = subtask.run_id
            print(f"Subtask delegated successfully via internal engine: ID={subtask_id} -> Agent={args.target_agent}")
        except Exception as engine_err:
            print(f"Failed to delegate task: HTTP error: {http_err}; Direct engine error: {engine_err}", file=sys.stderr)
            sys.exit(1)

    if not subtask_id:
        print("Error: Subtask ID could not be retrieved.", file=sys.stderr)
        sys.exit(1)

    if args.no_wait:
        print(f"[DELEGATE] Running asynchronously (--no-wait specified).")
        return

    # Synchronous wait loop
    if used_api:
        wait_for_subtask_api(args.api_url, subtask_id, args.target_agent, args.timeout)
    else:
        wait_for_subtask_db(subtask_id, args.target_agent, args.timeout)


if __name__ == "__main__":
    main()
