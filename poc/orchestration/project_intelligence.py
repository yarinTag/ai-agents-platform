"""
Deep Project Intelligence Service.
Assembles targeted context from project repositories, documentation, architecture,
conventions, ADRs, active/recent tasks, and skills to provide deterministic answers
for Super Agents and subordinate workers.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from persistence import DatabaseManager
try:
    from .code_indexer import CodeIndexer, code_indexer as default_code_indexer
except ImportError:
    try:
        from orchestration.code_indexer import CodeIndexer, code_indexer as default_code_indexer
    except ImportError:
        default_code_indexer = None

logger = logging.getLogger(__name__)


class ProjectIntelligence:
    """
    Project intelligence aggregator that retrieves and synthesizes deterministic
    context from repository docs, shared memories, conventions, and run histories.
    Combines Qdrant hybrid vector search with SQLite organizational memories.
    """

    def __init__(self, db_manager: DatabaseManager, code_indexer: Optional[Any] = None):
        self.db = db_manager
        self.code_indexer = code_indexer or default_code_indexer

    def retrieve_context(
        self,
        project_id: str,
        query: str,
        max_items: int = 5
    ) -> Dict[str, Any]:
        """
        Targeted retrieval across:
        1. Project shared memory (ADRs, conventions, architecture, lessons)
        2. Workspace documentation & guide files (README, CLAUDE.md, etc.)
        3. Project skills and allowed tools
        4. Recent completed task outputs in this project
        """
        STOP_WORDS = {
            "the", "and", "for", "that", "this", "with", "from", "should", "could",
            "would", "which", "what", "where", "when", "used", "using", "have", "been",
            "here", "there", "about", "into", "over", "after", "these", "those", "does", "will"
        }
        clean_q = re.sub(r'[^a-zA-Z0-9_\u0590-\u05fe\s]', ' ', query.lower())
        q_tokens = set(w for w in clean_q.split() if len(w) >= 4 and w not in STOP_WORDS)

        context_items: List[Dict[str, Any]] = []

        def _words_match(w1: str, w2: str) -> bool:
            if w1 == w2 or w1 in w2 or w2 in w1:
                return True
            if len(w1) >= 5 and len(w2) >= 5 and w1[:5] == w2[:5]:
                return True
            return False

        # 1. Search Project Shared Memories
        try:
            memories = self.db.list_project_memories(project_id=project_id)
            for mem in memories:
                score = 0
                title_lower = mem['title'].lower()
                content_lower = mem['content'].lower()
                tags = [t.lower() for t in mem.get('tags', [])]

                for tok in q_tokens:
                    matched_in_title = any(_words_match(tok, w) for w in title_lower.split())
                    matched_in_tags = any(_words_match(tok, t) for t in tags)
                    matched_in_content = tok in content_lower

                    if matched_in_title:
                        score += 4
                    if matched_in_tags:
                        score += 3
                    if matched_in_content and not matched_in_title:
                        score += 1

                if score >= 3:
                    context_items.append({
                        "type": "MEMORY",
                        "category": mem.get("category", "INSIGHT"),
                        "title": mem["title"],
                        "content": mem["content"],
                        "score": score,
                        "source": f"memory:{mem['id']}"
                    })
        except Exception as e:
            logger.warning(f"Error querying project memories for intelligence: {e}")

        # 2. Search Code & Documentation via Qdrant Hybrid Search (Dense + BM25 Sparse)
        qdrant_found = False
        if self.code_indexer and hasattr(self.code_indexer, "is_available") and self.code_indexer.is_available():
            try:
                q_items = self.code_indexer.search_code(project_id, query, limit=max_items)
                if q_items:
                    qdrant_found = True
                    for it in q_items:
                        context_items.append({
                            "type": it.get("entity_type", "CODE"),
                            "category": it.get("symbol_type", "CODE"),
                            "title": f"{it['file_path']} - {it['symbol_name']}",
                            "content": it["content"],
                            "score": it["score"],
                            "source": f"{it['file_path']}#L{it['start_line']}-L{it['end_line']}",
                            "file_path": it.get("file_path"),
                            "symbol_name": it.get("symbol_name"),
                            "start_line": it.get("start_line"),
                            "end_line": it.get("end_line")
                        })
            except Exception as e:
                logger.warning(f"Error querying Qdrant for code intelligence: {e}")

        # 3. Fallback: Search Project Workspace Files & Docs if Qdrant didn't match
        if not qdrant_found:
            try:
                proj = self.db.get_project(project_id)
                if proj and proj.working_directory and proj.working_directory not in (".", "", "./"):
                    wdir = Path(proj.working_directory)
                    if wdir.exists():
                        doc_candidates = ["CLAUDE.md", "README.md", "ARCHITECTURE.md", "GEMINI.md", "docs"]
                        for cand in doc_candidates:
                            cand_path = wdir / cand
                            if cand_path.is_file():
                                self._scan_file_for_context(cand_path, q_tokens, context_items)
                            elif cand_path.is_dir():
                                for sub_f in list(cand_path.glob("*.md"))[:5]:
                                    self._scan_file_for_context(sub_f, q_tokens, context_items)
            except Exception as e:
                logger.warning(f"Error scanning workspace docs for intelligence: {e}")

        # 4. Search Recent Tasks / Previous Agent Results
        try:
            recent_tasks = self.db.list_task_runs(project_id=project_id, limit=10)
            for t in recent_tasks:
                if t.result and t.status.value in ("completed", "waiting_input"):
                    score = 0
                    p_lower = t.prompt.lower()
                    r_lower = str(t.result).lower()
                    for tok in q_tokens:
                        if tok in p_lower:
                            score += 2
                        if tok in r_lower:
                            score += 1
                    if score >= 4:
                        context_items.append({
                            "type": "RECENT_RUN",
                            "category": "TASK_CONTEXT",
                            "title": f"Task {t.run_id}: {t.prompt[:60]}",
                            "content": str(t.result)[:400],
                            "score": score,
                            "source": f"task:{t.run_id}"
                        })
        except Exception as e:
            logger.warning(f"Error searching recent tasks: {e}")

        # Sort by relevance score
        context_items.sort(key=lambda x: x["score"], reverse=True)
        top_items = context_items[:max_items]

        return {
            "project_id": project_id,
            "query": query,
            "tokens": list(q_tokens),
            "total_matches": len(context_items),
            "items": top_items
        }

    def _scan_file_for_context(self, path: Path, q_tokens: set, context_items: List[Dict[str, Any]]):
        """Scan a markdown or text documentation file for relevant sections."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            sections = re.split(r'\n(?=#{1,3}\s)', content)
            for sec in sections:
                sec_lower = sec.lower()
                matches = sum(1 for tok in q_tokens if tok in sec_lower)
                if matches >= 2:
                    lines = sec.strip().splitlines()
                    title = lines[0] if lines else path.name
                    body = "\n".join(lines[1:15]) if len(lines) > 1 else lines[0]
                    context_items.append({
                        "type": "DOCS",
                        "category": "ARCHITECTURE",
                        "title": f"{path.name} - {title[:50]}",
                        "content": body[:500],
                        "score": matches * 2,
                        "source": str(path.name)
                    })
        except Exception:
            pass

    def synthesize_answer(
        self,
        project_id: str,
        question: str,
        requester_agent_id: str,
        context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesize a confident answer if targeted knowledge exists.
        Returns dictionary with answer, confidence, source, and approval flags.
        """
        retrieved = self.retrieve_context(project_id, question, max_items=3)
        items = retrieved["items"]
        if not items:
            return None

        best = items[0]
        # Require a threshold score of >= 4 for confident auto-resolution
        if best["score"] < 4:
            return None

        # Check for destructive/sensitive keywords requiring human intervention
        sensitive_markers = [
            "drop table", "delete from", "truncate", "rm -rf", "drop database",
            "production deploy", "push --force", "payment", "credit card", "stripe key",
            "transfer funds", "secret key", "wipe data"
        ]
        q_lower = question.lower()
        requires_human = any(marker in q_lower for marker in sensitive_markers)

        prefix = "Project Standard" if best.get("type") == "MEMORY" else "Project Implementation"
        answer_text = (
            f"{prefix} [{best['category']}: {best['title']}]:\n"
            f"{best['content'].strip()}"
        )

        return {
            "answer": answer_text,
            "confidence": min(1.0, 0.5 + (best["score"] * 0.1)),
            "source": best["source"],
            "category": best["category"],
            "requires_human_approval": requires_human,
            "supporting_items": [it["title"] for it in items]
        }
