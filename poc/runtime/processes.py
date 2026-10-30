"""Bounded subprocess termination used by execution and cancellation."""

import subprocess
import os
import signal


def terminate_process(process, timeout: float = 5):
    authoring_group = getattr(process, "_authoring_process_group", False)
    if authoring_group:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if authoring_group:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
            process.wait(timeout=timeout)
