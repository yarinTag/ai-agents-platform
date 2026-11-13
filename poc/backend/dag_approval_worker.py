"""Resume approved checkpoints from durable storage."""
import asyncio
import logging

from storage import dag_approvals
from .dependencies import get_db_manager, get_workflow_engine

logger = logging.getLogger(__name__)


def consume_one(db):
    dag_approvals.expire(db)
    item = dag_approvals.next_approved(db)
    if item is None:
        return
    engine = get_workflow_engine()
    try:
        engine.execute_workflow(item["workflow_id"], dag_approval_id=item["id"])
    except Exception:
        dag_approvals.fail_resume(db, item["id"])
        logger.warning("DAG continuation failed approval_id=%s", item["id"])


async def run(stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(lambda: consume_one(get_db_manager()))
        except Exception:
            logger.warning("DAG approval worker unavailable")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except TimeoutError:
            continue
