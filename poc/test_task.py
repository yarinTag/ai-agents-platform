#!/usr/bin/env python3
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config_manager
from persistence import db_manager
from runtime_adapter import runtime_adapter, TaskStatus

def test_task_execution():
    """Test task execution."""
    print("=== Testing Task Execution ===")

    # Define a simple task
    task_prompt = "Say 'Hello, Test!' and nothing else."
    print(f"Task: {task_prompt}")

    # Start the task
    print("\nStarting task execution...")
    start_time = time.time()

    run_id = runtime_adapter.start_task(
        agent_id="general-task-agent",
        project_id="demo-project",
        prompt=task_prompt
    )

    print(f"✓ Task started with Run ID: {run_id}")

    # Wait for completion with polling (simple version)
    max_wait = 10  # seconds
    waited = 0
    while waited < max_wait:
        run_status = runtime_adapter.get_run_status(run_id)
        if run_status:
            print(f"[{waited:.1f}s] Status: {run_status.status.value}")
            if run_status.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                break
        else:
            print(f"[{waited:.1f}s] Run status not found yet")
        time.sleep(0.5)
        waited += 0.5

    print()  # New line

    # Get final status
    run = runtime_adapter.get_run_status(run_id)
    if not run:
        print("✗ ERROR: Could not retrieve run status")
        return None

    execution_time = time.time() - start_time
    print(f"\n=== Task Completed ===")
    print(f"Status: {run.status.value}")
    print(f"Execution time: {execution_time:.2f} seconds")

    if run.status == TaskStatus.COMPLETED:
        print(f"✓ SUCCESS: Task completed successfully")
        if run.result:
            print(f"\nResult:\n{run.result}")
    else:
        print(f"✗ FAILED: Task failed")
        if run.error:
            print(f"Error: {run.error}")

    # Show some events
    print(f"\n=== Events ({len(run.events)} total) ===")
    for i, event in enumerate(run.events[:5]):  # Show first 5 events
        event_type = event.get('type', 'unknown')
        print(f"  {i+1}. {event_type}")
        if event_type == 'assistant' and 'message' in event:
            msg = event['message']
            if isinstance(msg, dict) and 'content' in msg:
                content = msg['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            if text.strip():
                                print(f"      Text: {text[:50]}...")
                elif isinstance(msg, dict) and msg.get('type') == 'text':
                    text = msg.get('text', '')
                    if text.strip():
                        print(f"      Text: {text[:50]}...")

    if len(run.events) > 5:
        print(f"      ... and {len(run.events) - 5} more events")

    return run

if __name__ == "__main__":
    test_task_execution()
    print("\nTest completed!")