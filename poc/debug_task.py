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
    """Debug task execution with detailed logging."""
    print("=== Debugging Task Execution ===")

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

    # Monitor the queues directly for debugging
    if run_id in runtime_adapter._event_queues:
        event_queue = runtime_adapter._event_queues[run_id]
        print(f"Event queue size: {event_queue.qsize()}")
    else:
        print("✗ No event queue found for run_id")

    # Wait for completion with polling and queue checking
    max_wait = 15  # seconds
    waited = 0
    events_seen = 0

    while waited < max_wait:
        run_status = runtime_adapter.get_run_status(run_id)
        if run_id in runtime_adapter._event_queues:
            queue_size = runtime_adapter._event_queues[run_id].qsize()
        else:
            queue_size = 0

        print(f"[{waited:.1f}s] Status: {run_status.status.value if run_status else 'None'}, Queue: {queue_size}")

        # Drain any events in the queue without blocking
        if run_id in runtime_adapter._event_queues:
            try:
                while True:
                    event = runtime_adapter._event_queues[run_id].get_nowait()
                    events_seen += 1
                    print(f"  Event {events_seen}: {event.get('type', 'unknown')}")
                    if event.get('type') in ['result', 'error']:
                        print(f"    Details: {event}")
            except:
                pass  # Queue empty

        if run_status and run_status.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            break

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
    print(f"Total events seen during monitoring: {events_seen}")
    print(f"Total events in run: {len(run.events)}")

    if run.status == TaskStatus.COMPLETED:
        print(f"✓ SUCCESS: Task completed successfully")
        if run.result:
            print(f"\nResult:\n{run.result}")
    else:
        print(f"✗ FAILED: Task failed")
        if run.error:
            print(f"Error: {run.error}")
        # Show stderr if available
        if run_id in runtime_adapter._processes:
            process = runtime_adapter._processes[run_id]
            if process.poll() is not None:
                try:
                    stderr_output = process.stderr.read()
                    if stderr_output:
                        print(f"Process STDERR: {stderr_output}")
                except:
                    pass

    # Show some events
    print(f"\n=== Events in run ({len(run.events)} total) ===")
    for i, event in enumerate(run.events[:10]):  # Show first 10 events
        event_type = event.get('type', 'unknown')
        timestamp = event.get('_timestamp', 0)
        print(f"  {i+1}. [{timestamp:.3f}] {event_type}")
        if event_type == 'assistant' and 'message' in event:
            msg = event['message']
            if isinstance(msg, dict):
                if 'content' in msg:
                    content = msg['content']
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                if item.get('type') == 'text':
                                    text = item.get('text', '')
                                    if text.strip():
                                        print(f"      Text: {text[:100]}...")
                                elif item.get('type') == 'thinking':
                                    thinking = item.get('thinking', '')
                                    if thinking.strip():
                                        print(f"      Thinking: {thinking[:100]}...")
                elif msg.get('type') == 'text':
                    text = msg.get('text', '')
                    if text.strip():
                        print(f"      Text: {text[:100]}...")

    if len(run.events) > 10:
        print(f"      ... and {len(run.events) - 10} more events")

    return run

if __name__ == "__main__":
    debug_task_execution()
    print("\nDebug test completed!")