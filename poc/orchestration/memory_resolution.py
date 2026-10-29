"""Project memory scoring for supervisor clarification."""
import logging
import re
from typing import Optional

from .ports import SupervisorStore

logger = logging.getLogger(__name__)


def resolve_from_memory(db: SupervisorStore, project_id: Optional[str], question: str) -> Optional[str]:
    """
    Inspect project memories to check if an active ADR, convention, or insight answers the question.
    Returns the resolution response text if a confident match is found, else None.
    """
    if not project_id:
        return None

    try:
        memories = db.list_project_memories(project_id=project_id)
    except Exception as e:
        logger.warning(f"Failed to fetch project memories: {e}")
        return None

    if not memories:
        return None

    clean_q = re.sub(r'[^a-zA-Z0-9_\u0590-\u05fe\s]', ' ', question.lower())
    q_words = set(w for w in clean_q.split() if len(w) >= 4)

    if not q_words:
        return None

    best_memory = None
    highest_score = 0

    for mem in memories:
        score = 0
        mem_title_words = set(re.sub(r'[^a-zA-Z0-9_\u0590-\u05fe\s]', ' ', mem['title'].lower()).split())
        mem_content_lower = mem['content'].lower()
        tags = [t.lower() for t in mem.get('tags', [])]

        for word in q_words:
            if word in mem_title_words:
                score += 3
            if word in tags:
                score += 2
            if word in mem_content_lower:
                score += 1

        if score > highest_score:
            highest_score = score
            best_memory = mem

    if highest_score >= 3 and best_memory:
        return (
            f"Auto-resolved from Project Standard [{best_memory['category']}: {best_memory['title']}]:\n"
            f"{best_memory['content']}"
        )

    return None

