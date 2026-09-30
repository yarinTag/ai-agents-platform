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
import urllib.request
import urllib.error

def main():
    parser = argparse.ArgumentParser(description="Delegate a subtask to a subordinate agent.")
    parser.add_argument("--target-agent", "-a", required=True, help="ID of the target subordinate agent")
    parser.add_argument("--prompt", "-p", required=True, help="Detailed prompt/instructions for the subtask")
    parser.add_argument("--parent-task-id", "-t", default=os.getenv("PLATFORM_PARENT_TASK_ID"), help="ID of the parent task")
    parser.add_argument("--project-id", default=os.getenv("PLATFORM_PROJECT_ID"), help="Project ID context")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--api-url", default=os.getenv("PLATFORM_API_URL", "http://localhost:8000"), help="Platform API base URL")

    args = parser.parse_args()

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
            print(f"Subtask delegated successfully: ID={subtask_id} -> Agent={args.target_agent}")
            print(json.dumps(resp_data, indent=2))
            return
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
            print(f"Subtask delegated successfully via internal engine: ID={subtask.run_id} -> Agent={args.target_agent}")
            return
        except Exception as engine_err:
            print(f"Failed to delegate task: HTTP error: {http_err}; Direct engine error: {engine_err}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
