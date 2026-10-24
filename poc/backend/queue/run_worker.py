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

from backend.queue import get_message_broker, get_queue_worker
from backend.dependencies import get_runtime_adapter, get_event_bus


async def run_worker():
    logger.info("Starting Enterprise Autonomous Agent Worker Node...")
    concurrency = int(os.environ.get("WORKER_CONCURRENCY", "10"))
    worker_id = os.environ.get("HOSTNAME", f"worker_{os.getpid()}")

    broker = get_message_broker()
    connected = await broker.connect()
    if not connected:
        logger.error("Failed to connect to RabbitMQ broker.")
        return

    worker = get_queue_worker()
    worker.worker_id = worker_id
    worker.max_concurrency = concurrency
    worker.runtime_adapter = get_runtime_adapter()
    worker.event_bus = get_event_bus()

    await worker.start()
    logger.info(f"Worker Node [{worker_id}] is listening on RabbitMQ topic queues. Ready for tasks!")

    # Keep worker running indefinitely
    try:
        while True:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Worker shutting down gracefully...")
        await worker.stop()
        await broker.disconnect()


if __name__ == "__main__":
    asyncio.run(run_worker())
