#!/usr/bin/env python3
"""
Test launching Claude Code with Free Claude Code environment variables.
"""

import subprocess
import os
import json
import time

def test_claude_launch():
    """Test launching Claude Code with FCC environment."""

    # Environment variables for Free Claude Code proxy
    env = os.environ.copy()
    env.update({
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082",
        "ANTHROPIC_AUTH_TOKEN": "freecc",  # default from FCC settings
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
    prompt = "Say 'Hello, World!' and nothing else."

    print("Launching Claude Code with Free Claude Code environment...")
    print(f"Proxy URL: {env['ANTHROPIC_BASE_URL']}")
    print(f"Auth token: {env['ANTHROPIC_AUTH_TOKEN']}")

    try:
        # Launch Claude Code process
        process = subprocess.Popen(
            [
                "claude",  # This should be in PATH from earlier check
                "--model", "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
                "-p", prompt,
                "--output-format", "stream-json",
                "--dangerously-skip-permissions",  # FCC uses this
                "--verbose"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=os.getcwd(),  # Current working directory
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        print(f"Process launched with PID: {process.pid}")

        # Read and display output in real-time
        print("\n--- Claude Code Output ---")
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())

                # Try to parse as JSON
                try:
                    event = json.loads(output.strip())
                    print(f"  Parsed event: {event.get('type', 'unknown')}")
                except json.JSONDecodeError:
                    pass  # Not JSON, could be raw output

        # Get return code
        return_code = process.wait()
        print(f"\nProcess exited with code: {return_code}")

        # Check stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"STDERR: {stderr_output}")

    except FileNotFoundError:
        print("ERROR: 'claude' command not found in PATH")
        print("Make sure Claude Code CLI is installed and accessible")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_claude_launch()