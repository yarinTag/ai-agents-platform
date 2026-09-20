#!/usr/bin/env python3
import subprocess
import os
import sys
import time

# Environment variables for Free Claude Code proxy
env = os.environ.copy()
env.update({
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082",
    "ANTHROPIC_AUTH_TOKEN": "freecc",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "190000",
    "DISABLE_AUTOUPDATER": "1",
    "DISABLE_FEEDBACK_COMMAND": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_TELEMETRY": "1",
    "TERM": "dumb",
    "PYTHONIOENCODING": "utf-8"
})

# Simple test prompt
prompt = "Say 'test' and nothing else."

print("Launching Claude Code to check stderr...")
start = time.time()

try:
    # Launch Claude Code process
    process = subprocess.Popen(
        [
            "claude",
            "--model", "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
            "-p", prompt,
            "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            "--verbose"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=os.getcwd(),
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    print(f"Process launched with PID: {process.pid}")

    # Read output for 5 seconds or until done
    output_lines = []
    stderr_lines = []

    # Use threading to read both streams
    import queue
    stdout_queue = queue.Queue()
    stderr_queue = queue.Queue()

    def enqueue_output(out, queue):
        for line in iter(out.readline, ''):
            queue.put(line)
        out.close()

    from threading import Thread
    stdout_thread = Thread(target=enqueue_output, args=(process.stdout, stdout_queue))
    stderr_thread = Thread(target=enqueue_output, args=(process.stderr, stderr_queue))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    # Read outputs for 5 seconds
    end_time = time.time() + 5
    while time.time() < end_time:
        # Try to get stdout lines
        try:
            while True:
                line = stdout_queue.get_nowait()
                if line:
                    output_lines.append(line)
                    print(f"STDOUT: {line.strip()}")
        except queue.Empty:
            pass

        # Try to get stderr lines
        try:
            while True:
                line = stderr_queue.get_nowait()
                if line:
                    stderr_lines.append(line)
                    print(f"STDERR: {line.strip()}")
        except queue.Empty:
            pass

        time.sleep(0.1)

        # Check if process has ended
        if process.poll() is not None:
            break

    # Wait for threads to finish
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)

    # Get return code
    return_code = process.wait()
    print(f"\nProcess exited with code: {return_code}")

    # Show any remaining stderr
    try:
        remaining_stderr = process.stderr.read()
        if remaining_stderr:
            print(f"Remaining STDERR: {remaining_stderr}")
    except:
        pass

    print(f"\nTotal STDOUT lines: {len(output_lines)}")
    print(f"Total STDERR lines: {len(stderr_lines)}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()