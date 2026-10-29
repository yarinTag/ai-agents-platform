"""
Code & Document Indexer using Tree-sitter/AST parsing, FastEmbed, and Qdrant.
Provides incremental code indexing, dense+sparse vector representations,
and hybrid search with Reciprocal Rank Fusion (RRF).
"""

import os
import ast
import json
import uuid
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from fastembed import TextEmbedding, SparseTextEmbedding
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

from . import source_parsers

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "project_intelligence"
DEFAULT_DENSE_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"

_SHARED_DENSE_MODEL: Optional[Any] = None
_SHARED_SPARSE_MODEL: Optional[Any] = None


def get_shared_dense_model():
    global _SHARED_DENSE_MODEL
    if _SHARED_DENSE_MODEL is None and QDRANT_AVAILABLE:
        _SHARED_DENSE_MODEL = TextEmbedding(model_name=DEFAULT_DENSE_MODEL)
    return _SHARED_DENSE_MODEL


def get_shared_sparse_model():
    global _SHARED_SPARSE_MODEL
    if _SHARED_SPARSE_MODEL is None and QDRANT_AVAILABLE:
        _SHARED_SPARSE_MODEL = SparseTextEmbedding(model_name=DEFAULT_SPARSE_MODEL)
    return _SHARED_SPARSE_MODEL


class CodeIndexer:
    """
    Incremental Code & Documentation Indexer.
    Extracts semantic and structural code units via AST, generates dense and
    sparse vectors, and stores them in Qdrant with rich payload metadata.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME
    ):
        self.collection_name = collection_name
        self.storage_path = storage_path or os.getenv("QDRANT_STORAGE_PATH", "poc/data/qdrant_storage")
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", None)

        self._client: Optional[Any] = None
        self._dense_model: Optional[Any] = None
        self._sparse_model: Optional[Any] = None
        self._initialized = False

        # Ignore patterns
        self.ignore_dirs: Set[str] = {
            ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
            "build", ".idea", ".vscode", ".pytest_cache", "site-packages",
            "egg-info", "data", "qdrant_storage", "qdrant_db"
        }
        self.ignore_extensions: Set[str] = {
            ".pyc", ".pyo", ".pyd", ".db", ".sqlite", ".sqlite3", ".log",
            ".bin", ".exe", ".dll", ".so", ".dylib", ".png", ".jpg", ".jpeg",
            ".gif", ".ico", ".svg", ".zip", ".tar", ".gz", ".lock"
        }

    def close(self):
        """Close Qdrant client connection and release file locks."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._initialized = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def _get_cache_path(self, project_id: str) -> Path:
        p = Path(self.storage_path)
        p.mkdir(parents=True, exist_ok=True)
        return p / f"index_cache_{project_id}.json"

    def _load_cache(self, project_id: str) -> Dict[str, str]:
        cpath = self._get_cache_path(project_id)
        if cpath.exists():
            try:
                return json.loads(cpath.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_cache(self, project_id: str, cache: Dict[str, str]):
        cpath = self._get_cache_path(project_id)
        try:
            cpath.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save index cache for {project_id}: {e}")

    def _init_qdrant(self):
        """Lazy-initialize Qdrant client and FastEmbed models."""
        if self._initialized or not QDRANT_AVAILABLE:
            return

        try:
            if self.qdrant_url:
                self._client = QdrantClient(url=self.qdrant_url)
            else:
                Path(self.storage_path).mkdir(parents=True, exist_ok=True)
                self._client = QdrantClient(path=self.storage_path)

            self._dense_model = get_shared_dense_model()
            self._sparse_model = get_shared_sparse_model()

            # Ensure collection exists with dense + sparse vector configuration
            existing_colls = [c.name for c in self._client.get_collections().collections]
            if self.collection_name not in existing_colls:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
                    },
                    sparse_vectors_config={
                        "sparse": models.SparseVectorParams()
                    }
                )
                # Create payload indices for fast filtering (server Qdrant only)
                if self.qdrant_url:
                    for field_name in ["project_id", "entity_type", "file_path", "symbol_name"]:
                        try:
                            self._client.create_payload_index(
                                collection_name=self.collection_name,
                                field_name=field_name,
                                field_schema=models.PayloadSchemaType.KEYWORD
                            )
                        except Exception:
                            pass

            self._initialized = True
            logger.info(f"CodeIndexer initialized successfully with Qdrant collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to initialize CodeIndexer / Qdrant: {e}")
            self._initialized = False

    def is_available(self) -> bool:
        if not QDRANT_AVAILABLE:
            return False
        if not self._initialized:
            self._init_qdrant()
        return bool(self._initialized and self._client)

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 content hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def parse_python_file(self, file_path: Path, rel_path: str) -> List[Dict[str, Any]]:
        return source_parsers.parse_python_file(file_path, rel_path, self._chunk_by_lines)

    def parse_markdown_file(self, file_path: Path, rel_path: str) -> List[Dict[str, Any]]:
        return source_parsers.parse_markdown_file(file_path, rel_path)

    def _chunk_by_lines(self, file_path: Path, rel_path: str, entity_type: str, window_size: int = 40, overlap: int = 10) -> List[Dict[str, Any]]:
        return source_parsers._chunk_by_lines(file_path, rel_path, entity_type, window_size, overlap)

    def index_project(self, project_id: str, root_dir: str, force: bool = False) -> Dict[str, Any]:
        """
        Incrementally index an entire project directory.
        Only parses and embeds files that have been created or modified since last index.
        Purges points for files that have been deleted.
        """
        if not self.is_available():
            return {"status": "unavailable", "error": "Qdrant or FastEmbed not initialized"}

        root_path = Path(root_dir).resolve()
        if not root_path.exists():
            return {"status": "error", "error": f"Root directory {root_dir} does not exist"}

        cache = {} if force else self._load_cache(project_id)
        current_files: Dict[str, Path] = {}

        # Discover files
        storage_resolved = Path(self.storage_path).resolve()
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [
                d for d in dirs
                if d not in self.ignore_dirs
                and not d.startswith(".")
                and (Path(root) / d).resolve() != storage_resolved
            ]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.ignore_extensions or f.startswith(".") or f.startswith("index_cache_"):
                    continue
                file_full = Path(root) / f
                if file_full.resolve().is_relative_to(storage_resolved):
                    continue
                rel_path = str(file_full.relative_to(root_path))
                current_files[rel_path] = file_full

        # Detect changes
        files_to_index: List[str] = []
        files_deleted: List[str] = [p for p in cache.keys() if p not in current_files]

        for rel_path, fpath in current_files.items():
            try:
                curr_hash = self._compute_hash(fpath)
                if rel_path not in cache or cache[rel_path] != curr_hash:
                    files_to_index.append(rel_path)
            except Exception:
                pass

        # Handle deleted files: remove points from Qdrant
        if files_deleted:
            for d_path in files_deleted:
                try:
                    self._client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.FilterSelector(
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id)),
                                    models.FieldCondition(key="file_path", match=models.MatchValue(value=d_path))
                                ]
                            )
                        )
                    )
                    del cache[d_path]
                except Exception as e:
                    logger.warning(f"Error purging deleted file {d_path} from Qdrant: {e}")

        # Process new and modified files
        new_chunks = []
        for rel_path in files_to_index:
            fpath = current_files[rel_path]
            # Purge existing points for this modified file first
            if rel_path in cache:
                try:
                    self._client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.FilterSelector(
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id)),
                                    models.FieldCondition(key="file_path", match=models.MatchValue(value=rel_path))
                                ]
                            )
                        )
                    )
                except Exception:
                    pass

            ext = fpath.suffix.lower()
            if ext == ".py":
                parsed = self.parse_python_file(fpath, rel_path)
            elif ext in (".md", ".txt", ".rst"):
                parsed = self.parse_markdown_file(fpath, rel_path)
            elif ext in (".ts", ".js", ".json", ".sql", ".sh"):
                parsed = self._chunk_by_lines(fpath, rel_path, "CODE")
            else:
                parsed = []

            for chk in parsed:
                chk["project_id"] = project_id
                chk["file_path"] = rel_path
                new_chunks.append(chk)

        # Batch embed and upsert
        upserted_count = 0
        if new_chunks:
            batch_size = 64
            for i in range(0, len(new_chunks), batch_size):
                batch = new_chunks[i:i + batch_size]
                texts = [c["content"] for c in batch]

                dense_vectors = list(self._dense_model.embed(texts))
                sparse_vectors = list(self._sparse_model.embed(texts))

                points = []
                for idx, item in enumerate(batch):
                    point_id = str(uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"{project_id}:{item['file_path']}:{item['start_line']}:{item['symbol_name']}"
                    ))
                    sp_vec = sparse_vectors[idx]
                    points.append(models.PointStruct(
                        id=point_id,
                        vector={
                            "dense": dense_vectors[idx].tolist(),
                            "sparse": models.SparseVector(
                                indices=sp_vec.indices.tolist(),
                                values=sp_vec.values.tolist()
                            )
                        },
                        payload={
                            "project_id": project_id,
                            "file_path": item["file_path"],
                            "symbol_name": item["symbol_name"],
                            "symbol_type": item["symbol_type"],
                            "start_line": item["start_line"],
                            "end_line": item["end_line"],
                            "content": item["content"],
                            "docstring": item["docstring"],
                            "entity_type": item["entity_type"]
                        }
                    ))

                self._client.upsert(collection_name=self.collection_name, points=points)
                upserted_count += len(points)

            # Update cache with new hashes
            for rel_path in files_to_index:
                try:
                    cache[rel_path] = self._compute_hash(current_files[rel_path])
                except Exception:
                    pass

        self._save_cache(project_id, cache)

        return {
            "status": "success",
            "project_id": project_id,
            "files_scanned": len(current_files),
            "files_indexed": len(files_to_index),
            "files_deleted": len(files_deleted),
            "chunks_upserted": upserted_count,
            "total_cached_files": len(cache)
        }

    def search_code(
        self,
        project_id: str,
        query: str,
        limit: int = 5,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining dense semantic search + sparse BM25 with Reciprocal Rank Fusion.
        """
        if not self.is_available():
            return []

        try:
            # Embed query
            dense_vec = list(self._dense_model.embed([query]))[0].tolist()
            sparse_vec = list(self._sparse_model.embed([query]))[0]

            must_filters = [
                models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id))
            ]
            if entity_type:
                must_filters.append(
                    models.FieldCondition(key="entity_type", match=models.MatchValue(value=entity_type))
                )

            res = self._client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    models.Prefetch(
                        query=dense_vec,
                        using="dense",
                        filter=models.Filter(must=must_filters),
                        limit=limit * 2
                    ),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist()
                        ),
                        using="sparse",
                        filter=models.Filter(must=must_filters),
                        limit=limit * 2
                    )
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit
            )

            results = []
            for p in res.points:
                payload = p.payload or {}
                results.append({
                    "score": round(float(p.score or 0.0) * 10, 2),
                    "file_path": payload.get("file_path", ""),
                    "symbol_name": payload.get("symbol_name", ""),
                    "symbol_type": payload.get("symbol_type", "chunk"),
                    "start_line": payload.get("start_line", 1),
                    "end_line": payload.get("end_line", 1),
                    "content": payload.get("content", ""),
                    "docstring": payload.get("docstring", ""),
                    "entity_type": payload.get("entity_type", "CODE")
                })
            return results

        except Exception as e:
            logger.warning(f"Qdrant hybrid search failed: {e}")
            return []


# Global singleton instance
code_indexer = CodeIndexer()
