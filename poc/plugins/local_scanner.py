"""Local manifest/directory discovery adapter with explicit empty-path behavior."""
from .packages import summarize_plugins
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from .metadata import extract_skill_meta

logger = logging.getLogger(__name__)


def scan_local_source(effective_source_mode, effective_git_repo, effective_local_path):
    potential_roots: List[Path] = []
    if effective_source_mode == "local" and effective_local_path:
        lp = Path(effective_local_path).expanduser().resolve()
        if lp.exists():
            if (lp / "skills-marketplace" / "marketplace.json").exists():
                potential_roots.append(lp / "skills-marketplace")
            else:
                potential_roots.append(lp)

    plugins_map: Dict[str, Dict[str, Any]] = {}
    primary_marketplace_root: Optional[str] = None

    # Iterate potential roots and discover plugins
    for p_root in potential_roots:
        if not p_root.exists():
            continue

        mp_file = p_root / "marketplace.json"
        if mp_file.exists():
            if not primary_marketplace_root:
                primary_marketplace_root = str(p_root)
            try:
                with open(mp_file, "r", encoding="utf-8") as f:
                    mp_data = json.load(f)
                for p_meta in mp_data.get("plugins", []):
                    p_id = p_meta.get("id")
                    if not p_id:
                        continue
                    p_dir = p_root / p_meta.get("path", f"plugins/{p_id}")
                    if not p_dir.exists():
                        continue

                    if p_id not in plugins_map:
                        plugins_map[p_id] = {
                            "name": p_id,
                            "display_name": p_id.replace("-", " ").replace("_", " ").title(),
                            "version": p_meta.get("version", "1.0.0"),
                            "description": p_meta.get("description", ""),
                            "domain": p_meta.get("domain", ""),
                            "path": str(p_dir),
                            "skills": []
                        }

                    # Scan for SKILL.md in this plugin
                    for f_path in sorted(p_dir.rglob("*.md")):
                        parts_lower = [part.lower() for part in f_path.parts]
                        if any(ignored in parts_lower for ignored in ["references", "assets", "examples", "docs"]):
                            continue
                        if f_path.name.lower() in ["changelog.md", "versioning.md", "claude.md", "taxonomy.md", "readme.md"]:
                            continue
                        if f_path.name.lower() != "skill.md" and f_path.parent.name not in ["skills", p_id]:
                            continue

                        meta = extract_skill_meta(
                            f_path,
                            default_plugin=p_id,
                            default_domain=p_meta.get("domain", ""),
                            default_version=p_meta.get("version", "1.0.0")
                        )
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_id]["skills"]):
                            plugins_map[p_id]["skills"].append(meta)
                continue
            except Exception as e:
                logger.warning("Could not parse marketplace manifest %s", mp_file)

        # Non-manifest directory:
        # Group each child folder containing .md files as its own plugin package,
        # and top-level .md files under p_root.name
        top_mds = [
            f for f in sorted(p_root.glob("*.md"))
            if f.is_file() and f.name.lower() not in ["readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md"]
        ]
        if top_mds:
            root_pkg = p_root.name
            if root_pkg not in plugins_map:
                plugins_map[root_pkg] = {
                    "name": root_pkg,
                    "display_name": root_pkg.replace("-", " ").replace("_", " ").title(),
                    "version": "1.0.0",
                    "description": f"Skills library from {root_pkg}",
                    "domain": "general",
                    "path": str(p_root),
                    "skills": []
                }
            for f in top_mds:
                meta = extract_skill_meta(f, default_plugin=root_pkg)
                if not any(s["id"] == meta["id"] for s in plugins_map[root_pkg]["skills"]):
                    plugins_map[root_pkg]["skills"].append(meta)

        for child in sorted(p_root.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "__")):
                continue

            if child.name.lower() == "plugins":
                for sub in sorted(child.iterdir()):
                    if not sub.is_dir() or sub.name.startswith((".", "__")):
                        continue
                    p_name = sub.name
                    if p_name not in plugins_map:
                        plugins_map[p_name] = {
                            "name": p_name,
                            "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                            "version": "1.0.0",
                            "description": f"Plugin package {p_name}",
                            "domain": "general",
                            "path": str(sub),
                            "skills": []
                        }
                    for f in sorted(sub.rglob("*.md")):
                        parts_lower = [part.lower() for part in f.parts]
                        if any(ignored in parts_lower for ignored in ["references", "assets", "examples", "docs"]):
                            continue
                        if f.name.lower() in ["readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md"]:
                            continue
                        meta = extract_skill_meta(f, default_plugin=p_name)
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                            plugins_map[p_name]["skills"].append(meta)
            else:
                child_mds = [
                    f for f in sorted(child.rglob("*.md"))
                    if f.is_file()
                    and f.name.lower() not in ["readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md"]
                    and not any(ignored in [part.lower() for part in f.parts] for ignored in ["references", "assets", "examples", "docs"])
                ]
                if child_mds:
                    p_name = child.name
                    if p_name not in plugins_map:
                        plugins_map[p_name] = {
                            "name": p_name,
                            "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                            "version": "1.0.0",
                            "description": f"Plugin package {p_name}",
                            "domain": "general",
                            "path": str(child),
                            "skills": []
                        }
                    for f in child_mds:
                        meta = extract_skill_meta(f, default_plugin=p_name)
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                            plugins_map[p_name]["skills"].append(meta)

    flow_documents = {}
    for root in potential_roots:
        for path in sorted(root.rglob("skill-dependency-dag.json")):
            resolved = path.resolve()
            if path.parent.name != "references" or not resolved.is_relative_to(root.resolve()):
                continue
            if not any(resolved.is_relative_to(Path(pkg["path"]).resolve()) for pkg in plugins_map.values()):
                continue
            try:
                if resolved.stat().st_size <= 1_000_000:
                    flow_documents[str(path)] = resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
    plugins_data = summarize_plugins(plugins_map, flow_documents)

    return {
        "status": "success",
        "source_mode": effective_source_mode,
        "git_repo": effective_git_repo,
        "local_path": effective_local_path,
        "marketplace_path": primary_marketplace_root or (str(potential_roots[0]) if potential_roots else None),
        "plugins": plugins_data,
        "total_skills": sum(p["skills_count"] for p in plugins_data)
    }

