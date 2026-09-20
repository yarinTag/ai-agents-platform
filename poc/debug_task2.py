#!/usr/bin/env python3
import sys
import os
import time
import threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config_manager
from persistence import db_manager
from runtime_adapter import runtime_adapter, TaskStatus

def debug_task_execution():
    """Debug task execution with longer timeout."""
    print("=== Debugging Task Execution (Longer Timeout) ===")

    # Define a simple task
    task_prompt = "Say 'Hello, Debug!' and nothing else."
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

    # Monitor execution with event subscription - show ALL events
    def event_handler(event):
        event_type = event.get('type', 'unknown')
        timestamp = event.get('_timestamp', 0)
        rel_time = timestamp - start_time if timestamp else 0

        # Show all events for debugging
        if event_type == 'system':
            subtype = event.get('subtype', '')
            if subtype == 'thinking_tokens':
                estimated = event.get('estimated_tokens', 0)
                delta = event.get('estimated_tokens_delta', 0)
                print(f"[{rel_time:.1f}s] THINKING: {estimated} tokens (+{delta})")
            elif subtype == 'init':
                print(f"[{rel_time:.1f}s] INIT: session_id={event.get('session_id', 'unknown')}")
            else:
                print(f"[{rel_time:.1f}s] SYSTEM: {subtype}")
        elif event_type == 'assistant':
            message = event.get('message', {})
            if isinstance(message, dict):
                content = message.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get('type') == 'thinking':
                                thinking = item.get('thinking', '')
                                if thinking.strip():
                                    print(f"[{rel_time:.1f}s] ASSISTANT THINKING: {thinking[:100]}...")
                            elif item.get('type') == 'text':
                                text = item.get('text', '')
                                if text.strip():
                                    print(f"[{rel_time:.1f}s] ASSISTANT TEXT: {text}")
                            elif item.get('type') == 'signature':
                                sig = item.get('signature', '')
                                if sig:
                                    print(f"[{rel_time:.1f}s] ASSISTANT SIGNATURE: {sig}")
                elif isinstance(message, dict) and message.get('type') == 'text':
                    text = message.get('text', '')
                    if text.strip():
                        print(f"[{rel_time:.1f}s] ASSISTANT TEXT: {text}")
        elif event_type == 'result':
            result = event.get('result', '')
            print(f"[{rel_time:.1f}s] RESULT: {result}")
        elif event_type == 'error':
            error = event.get('error', {})
            print(f"[{rel_time:.1f}s] ERROR: {error.get('message', 'Unknown error')}")
        else:
            print(f"[{rel_time:.1f}s] {event_type.upper()}: {str(event)[:100]}...")

    # Subscribe to events
    unsubscribe = runtime_adapter.subscribe_to_events(run_id, event_handler)

    # Wait for completion with longer timeout
    max_wait = 30  # seconds
    waited = 0
    while waited < max_wait:
        run_status = runtime_adapter.get_run_status(run_id)
        if run_status and run_status.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            break
        time.sleep(0.5)
        waited += 0.5
        if int(waited) % 5 == 0 and waited > 0:  # Every 5 seconds
            print(f"[{waited:.1f}s] Still waiting... (status: {run_status.status.value if run_status else 'unknown'})")

    print()  # New line

    # Clean up subscription
    unsubscribe()

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

    # Show some statistics
    print(f"\n=== Execution Statistics ===")
    print(f"Total events captured: {len(run.events)}")
    event_types = {}
    for event in run.events:
        event_type = event.get('type', 'unknown')
        if event_type == 'system':
            subtype = event.get('subtype', 'unknown')
            key = f"system.{subtype}"
        else:
            key = event_type
        event_types[key] = event_types.get(key, 0) + 1

    for event_type, count in sorted(event_types.items()):
        print(f"  {event_type}: {count}")

    return run

if __name__ == "__main__":
    debug_task_execution()
    print("\nDebug test completed!")