"""Opt-in consumer for verified channel ingress."""
import asyncio
import logging
import os
import time

from storage import channel_ingress
from workflows.channel_trigger_dispatch import reserve_dispatches
from .dependencies import get_workflow_engine

logger = logging.getLogger(__name__)


def consume_one(engine):
    db = engine.db
    claim = channel_ingress.claim(db)
    if claim is None:
        return False
    event_id = claim["event"]["id"]
    lease = claim["lease_token"]
    try:
        executions = reserve_dispatches(db, claim)
    except Exception:
        logger.error("Channel trigger reservation failed event_id=%s", event_id)
        channel_ingress.settle(db, event_id, lease, success=False, retryable=True)
        return True
    failed = False
    for execution_id in executions:
        with db._get_connection() as conn:
            owned = conn.execute("""SELECT 1 FROM channel_ingress_outbox
                WHERE event_id=? AND status='PROCESSING' AND lease_token=? AND lease_until>?""",
                (event_id, lease, int(time.time()))).fetchone()
        if not owned:
            return True
        execution = db.get_workflow_execution(execution_id)
        if execution is None or execution.status != "QUEUED":
            continue
        try:
            engine.execute_workflow(execution.workflow_id, trigger_type="CHANNEL", execution_id=execution_id,
                                    channel_lease=lease)
        except Exception:
            failed = True
            with db._get_connection() as conn:
                conn.execute("""UPDATE workflow_executions
                    SET status='FAILED', completed_at=CURRENT_TIMESTAMP,
                        error_message='Channel execution admission or startup failed.'
                    WHERE id=? AND status='QUEUED' AND EXISTS (
                        SELECT 1 FROM channel_ingress_outbox WHERE event_id=?
                        AND status='PROCESSING' AND lease_token=? AND lease_until>?
                    )""", (execution_id, event_id, lease, int(time.time())))
            logger.warning("Channel execution rejected or failed execution_id=%s", execution_id)
    channel_ingress.settle(db, event_id, lease, success=not failed)
    return True


async def run(stop):
    if os.getenv("PLATFORM_CHANNEL_TRIGGER_WORKER") != "1":
        return
    while not stop.is_set():
        try:
            if await asyncio.to_thread(lambda: consume_one(get_workflow_engine())):
                continue
        except Exception:
            logger.error("Channel trigger consumer temporarily unavailable")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except TimeoutError:
            continue
