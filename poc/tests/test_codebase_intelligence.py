"""
Integration tests for Codebase Intelligence, AST Parsing, and Qdrant Hybrid Retrieval.
Validates:
- AST parsing of Python classes, methods, and functions.
- Incremental indexing and change detection.
- Dense + Sparse hybrid retrieval via Qdrant with Reciprocal Rank Fusion (RRF).
- ProjectIntelligence unified retrieval blending SQLite memories with Qdrant code chunks.
"""

import pytest
import uuid
import tempfile
from pathlib import Path

from persistence import DatabaseManager
from config import ProjectConfig
from orchestration.code_indexer import CodeIndexer
from orchestration.project_intelligence import ProjectIntelligence


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory with Python and Markdown files."""
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir)

    # Create auth service code file
    auth_code = '''"""Authentication and security module."""

class AuthManager:
    """Manages user authentication and token issuance."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def verify_jwt_token(self, token: str) -> bool:
        """Verify the signature and claims of a Bearer JWT token."""
        return len(token) > 20 and token.startswith("eyJ")

def generate_session_cookie(user_id: str) -> str:
    """Generate secure HTTP-only session cookie for the user."""
    return f"sess_{user_id}_secure"
'''
    (tmp_path / "auth_service.py").write_text(auth_code, encoding="utf-8")

    # Create supervisor module code file
    sup_code = '''"""Supervisor coordination module."""

class SupervisorCoordinator:
    """Coordinates supervisor decisions and unblocks worker agents."""

    def resolve_subordinate_question(self, question: str) -> str:
        """Resolve worker question using deep project intelligence or supervisor escalation."""
        return f"Resolution for: {question}"

    def resume_subordinate_task(self, task_id: str, answer: str) -> bool:
        """Resume execution of a paused worker task with the supervisor answer."""
        return True
'''
    (tmp_path / "supervisor_coordinator.py").write_text(sup_code, encoding="utf-8")

    # Create architecture markdown doc
    doc_content = '''# Security Architecture

## Authentication Protocol
All internal services require Bearer JWT tokens with RS256 signing algorithm.

## Token Expiration
Access tokens expire after 15 minutes, refresh tokens after 7 days.
'''
    (tmp_path / "ARCHITECTURE.md").write_text(doc_content, encoding="utf-8")

    yield tmp_path

    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


def test_code_indexer_ast_parsing_and_indexing(temp_workspace):
    """Test that CodeIndexer parses Python AST and indexes symbols into Qdrant."""
    storage_dir = temp_workspace / "qdrant_db"
    indexer = CodeIndexer(storage_path=str(storage_dir))
    try:
        assert indexer.is_available() is True

        proj_id = f"proj-test-{uuid.uuid4().hex[:6]}"
        res = indexer.index_project(proj_id, str(temp_workspace))

        assert res["status"] == "success"
        assert res["files_scanned"] == 3
        assert res["files_indexed"] == 3
        assert res["chunks_upserted"] > 5
    finally:
        indexer.close()


def test_incremental_indexing_skips_unchanged_files(temp_workspace):
    """Test that unchanged files are skipped on subsequent indexing runs."""
    storage_dir = temp_workspace / "qdrant_db"
    indexer = CodeIndexer(storage_path=str(storage_dir))
    try:
        proj_id = f"proj-incr-{uuid.uuid4().hex[:6]}"
        # First run: indexes all files
        res1 = indexer.index_project(proj_id, str(temp_workspace))
        assert res1["files_indexed"] == 3

        # Second run without changes: indexes 0 files
        res2 = indexer.index_project(proj_id, str(temp_workspace))
        assert res2["files_indexed"] == 0
        assert res2["chunks_upserted"] == 0

        # Modify one file: only that file should be re-indexed
        (temp_workspace / "auth_service.py").write_text(
            (temp_workspace / "auth_service.py").read_text() + "\n\ndef new_helper(): pass\n",
            encoding="utf-8"
        )
        res3 = indexer.index_project(proj_id, str(temp_workspace))
        assert res3["files_indexed"] == 1
    finally:
        indexer.close()


def test_qdrant_hybrid_search(temp_workspace):
    """Test hybrid search with semantic queries and exact symbol matching."""
    storage_dir = temp_workspace / "qdrant_db"
    indexer = CodeIndexer(storage_path=str(storage_dir))
    try:
        proj_id = f"proj-search-{uuid.uuid4().hex[:6]}"
        indexer.index_project(proj_id, str(temp_workspace))

        # Semantic query
        sem_results = indexer.search_code(proj_id, "How does the system verify Bearer tokens and signatures?")
        assert len(sem_results) > 0
        top_sem = sem_results[0]
        assert "auth_service.py" in top_sem["file_path"] or "ARCHITECTURE.md" in top_sem["file_path"]

        # Exact symbol query
        sym_results = indexer.search_code(proj_id, "SupervisorCoordinator")
        assert len(sym_results) > 0
        symbols_found = [r["symbol_name"] for r in sym_results]
        assert any("SupervisorCoordinator" in s for s in symbols_found)
    finally:
        indexer.close()


def test_project_intelligence_blending(temp_workspace):
    """Test that ProjectIntelligence blends SQLite memories with Qdrant code chunks."""
    db_file = temp_workspace / "test.db"
    db = DatabaseManager(str(db_file))
    storage_dir = temp_workspace / "qdrant_db"
    indexer = CodeIndexer(storage_path=str(storage_dir))
    try:
        proj_id = f"proj-blend-{uuid.uuid4().hex[:6]}"
        db.save_project(ProjectConfig(
            id=proj_id,
            name="Blended Project",
            description="Testing code + memory retrieval",
            working_directory=str(temp_workspace)
        ))

        # Add an ADR memory in SQLite
        db.create_project_memory({
            "project_id": proj_id,
            "category": "ADR",
            "title": "Token Encryption Algorithm",
            "content": "All tokens must use RS256 asymmetric encryption with rotating key pairs.",
            "tags": ["token", "encryption", "rs256", "auth"]
        })

        # Index workspace into Qdrant
        indexer.index_project(proj_id, str(temp_workspace))

        # Initialize ProjectIntelligence with indexer
        intel = ProjectIntelligence(db, code_indexer=indexer)

        # Query for token verification
        ctx = intel.retrieve_context(proj_id, "How are JWT bearer tokens verified and encrypted?", max_items=8)
        assert ctx["total_matches"] >= 2

        types_found = {it["type"] for it in ctx["items"]}
        # Expect both MEMORY (from SQLite) and CODE/DOCS (from Qdrant)
        assert "MEMORY" in types_found
        assert any(t in ("CODE", "DOCS") for t in types_found)

        # Test auto-resolution synthesis from code or memory
        synth = intel.synthesize_answer(proj_id, "How are tokens encrypted in this project?", "worker-1")
        assert synth is not None
        assert synth["confidence"] > 0.6
        assert "RS256" in synth["answer"] or "JWT" in synth["answer"]
    finally:
        indexer.close()
