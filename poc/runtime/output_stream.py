"""Subprocess stream parsing and event queue delivery."""

import json
import queue
import subprocess
import threading
import time
from typing import Any, Dict, Optional

def parse_output_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single line of Claude Code stream-json output.

    Args:
        line: Raw output line from Claude Code

    Returns:
        Parsed event dictionary or None if not valid JSON
    """
    line = line.strip()
    if not line:
        return None

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        # Return as raw output event
        return {
            "type": "raw",
            "content": line
        }

def read_output(
    parser,
    run_id: str,
    process: subprocess.Popen,
    event_queue: queue.Queue,
    stop_event: threading.Event
):
    """
    Read output from Claude Code subprocess and put events in queue.

    Args:
        run_id: ID of the run
        process: Claude Code subprocess
        event_queue: Queue to put parsed events
        stop_event: Event to signal when to stop reading
    """
    try:
        while not stop_event.is_set() and process.poll() is None:
            line = process.stdout.readline()
            if line:
                event = parser(line)
                if event:
                    # Add metadata
                    event['_timestamp'] = time.time()
                    event['_run_id'] = run_id
                    event_queue.put(event)
            else:
                time.sleep(0.01)  # Short sleep to prevent busy waiting

        # Read any remaining output after process ends
        remaining_output = process.stdout.read()
        if remaining_output:
            for line in remaining_output.splitlines():
                if line.strip():
                    event = parser(line.decode('utf-8', errors='replace') if isinstance(line, bytes) else line)
                    if event:
                        event['_timestamp'] = time.time()
                        event['_run_id'] = run_id
                        event_queue.put(event)

    except Exception as e:
        # Put error event in queue
        error_event = {
            "type": "error",
            "error": {"message": f"Output reader error: {str(e)}"},
            "_timestamp": time.time(),
            "_run_id": run_id
        }
        event_queue.put(error_event)
    finally:
        # Signal end of output
        end_event = {
            "type": "end_of_output",
            "_timestamp": time.time(),
            "_run_id": run_id
        }
        event_queue.put(end_event)


def drain_stderr(process):
    """Drain the optional diagnostics pipe without retaining unbounded/secret text."""
    if process.stderr is None:
        return
    try:
        while process.stderr.read(4096):
            pass
    except (OSError, ValueError):
        pass


def read_stderr_tail(process, tail):
    """Drain stderr independently so a full pipe cannot block runtime exit."""
    if process.stderr is None:
        return
    for line in process.stderr:
        text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
        if text.strip():
            tail.append(text.strip()[-2000:])

