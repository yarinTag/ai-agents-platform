#!/usr/bin/env python3
"""
Standalone Distributed Queue Worker Entrypoint.

Starts an autonomous worker daemon that pulls tasks and workflow steps
directly from RabbitMQ queues with manual ACKs and Docker sandbox capabilities.
"""

import asyncio
import os
import sys
import logging

# Ensure project root and poc directory are on path
current_dir = os.path.dirname(os.path.abspath(__file__))
poc_dir = os.path.dirname(os.path.dirname(current_dir))
project_root = os.path.dirname(poc_dir)
if poc_dir not in sys.path:
    sys.path.insert(0, poc_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Worker) %(message)s"
)
logger = logging.getLogger("worker_entrypoint")

from backend.queue import get_queue_worker
from backend.queue_lifecycle import start_queue, stop_queue
from backend.dependencies import shutdown_services


async def run_worker():
    """Use the same injected runtime/workflow composition as the API worker."""
    worker = get_queue_worker()
    worker.worker_id = os.environ.get("HOSTNAME", f"worker_{os.getpid()}")
    worker.max_concurrency = int(os.environ.get("WORKER_CONCURRENCY", "10"))
    try:
        await start_queue()
        if not worker.is_running:
            raise RuntimeError("Queue worker could not start")
        while worker.is_running:
            await asyncio.sleep(1)
    finally:
        await stop_queue()
        await shutdown_services()


if __name__ == "__main__":
    asyncio.run(run_worker())
