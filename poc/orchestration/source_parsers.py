"""Source/document parsing independent of embeddings and vector storage."""
import ast
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_python_file(file_path: Path, rel_path: str, chunk_fallback=None) -> List[Dict[str, Any]]:
    """Parse Python source file using AST to extract functions, classes, and methods."""
    chunks = []
    try:
        code = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(code, filename=str(file_path))
        lines = code.splitlines()

        # 1. Module-level docstring
        mod_doc = ast.get_docstring(tree)
        if mod_doc:
            chunks.append({
                "symbol_name": Path(rel_path).stem,
                "symbol_type": "module",
                "start_line": 1,
                "end_line": min(len(lines), 30),
                "content": f"# Module: {rel_path}\n\"\"\"{mod_doc}\"\"\"",
                "docstring": mod_doc,
                "entity_type": "DOCS" if "doc" in rel_path.lower() else "CODE"
            })

        for node in tree.body:
            # Class definitions
            if isinstance(node, ast.ClassDef):
                class_doc = ast.get_docstring(node) or ""
                start = node.lineno
                end = getattr(node, "end_lineno", min(start + 50, len(lines)))
                class_snippet = "\n".join(lines[start - 1:min(end, start + 30)])

                chunks.append({
                    "symbol_name": node.name,
                    "symbol_type": "class",
                    "start_line": start,
                    "end_line": end,
                    "content": f"class {node.name}:\n" + class_snippet,
                    "docstring": class_doc,
                    "entity_type": "TEST" if "test" in rel_path.lower() else "CODE"
                })

                # Methods within the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_doc = ast.get_docstring(item) or ""
                        m_start = item.lineno
                        m_end = getattr(item, "end_lineno", min(m_start + 40, len(lines)))
                        method_snippet = "\n".join(lines[m_start - 1:m_end])
                        chunks.append({
                            "symbol_name": f"{node.name}.{item.name}",
                            "symbol_type": "method",
                            "start_line": m_start,
                            "end_line": m_end,
                            "content": f"# In class {node.name} ({rel_path})\n{method_snippet}",
                            "docstring": m_doc,
                            "entity_type": "TEST" if "test" in rel_path.lower() else "CODE"
                        })

            # Standalone functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_doc = ast.get_docstring(node) or ""
                start = node.lineno
                end = getattr(node, "end_lineno", min(start + 40, len(lines)))
                fn_snippet = "\n".join(lines[start - 1:end])
                chunks.append({
                    "symbol_name": node.name,
                    "symbol_type": "function",
                    "start_line": start,
                    "end_line": end,
                    "content": f"# Function in {rel_path}\n{fn_snippet}",
                    "docstring": f_doc,
                    "entity_type": "TEST" if "test" in rel_path.lower() else "CODE"
                })

    except Exception as e:
        logger.debug(f"AST parsing failed for {rel_path}: {e}")
        # Fallback to line-window chunking
        chunks.extend((chunk_fallback or _chunk_by_lines)(file_path, rel_path, "CODE"))

    return chunks


def parse_markdown_file(file_path: Path, rel_path: str) -> List[Dict[str, Any]]:
    """Parse markdown file into sections by headers."""
    chunks = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        current_header = Path(rel_path).name
        current_lines = []
        start_line = 1

        for idx, line in enumerate(lines, 1):
            if line.startswith("#"):
                if current_lines:
                    chunks.append({
                        "symbol_name": current_header,
                        "symbol_type": "markdown_section",
                        "start_line": start_line,
                        "end_line": idx - 1,
                        "content": f"# {rel_path} - {current_header}\n" + "\n".join(current_lines),
                        "docstring": current_lines[0] if current_lines else "",
                        "entity_type": "DOCS"
                    })
                    current_lines = []
                current_header = line.lstrip("#").strip()
                start_line = idx
            current_lines.append(line)

        if current_lines:
            chunks.append({
                "symbol_name": current_header,
                "symbol_type": "markdown_section",
                "start_line": start_line,
                "end_line": len(lines),
                "content": f"# {rel_path} - {current_header}\n" + "\n".join(current_lines),
                "docstring": current_lines[0] if current_lines else "",
                "entity_type": "DOCS"
            })
    except Exception as e:
        logger.debug(f"Markdown parsing failed for {rel_path}: {e}")
    return chunks


def _chunk_by_lines(file_path: Path, rel_path: str, entity_type: str, window_size: int = 40, overlap: int = 10) -> List[Dict[str, Any]]:
    """Generic line-based sliding window chunking."""
    chunks = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        if not lines:
            return []

        i = 0
        while i < len(lines):
            end = min(i + window_size, len(lines))
            chunk_lines = lines[i:end]
            chunks.append({
                "symbol_name": f"{Path(rel_path).name}:{i+1}-{end}",
                "symbol_type": "chunk",
                "start_line": i + 1,
                "end_line": end,
                "content": f"// File: {rel_path} (Lines {i+1}-{end})\n" + "\n".join(chunk_lines),
                "docstring": "",
                "entity_type": entity_type
            })
            if end == len(lines):
                break
            i += (window_size - overlap)
    except Exception:
        pass
    return chunks


