"""Bounded subprocess termination used by execution and cancellation."""

import subprocess


def terminate_process(process, timeout: float = 5):
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout)
