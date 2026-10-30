"""Skills: git scanner ownership."""
from .packages import summarize_plugins

from typing import List, Optional, Dict, Any
import re
import json
import httpx
from .metadata import extract_skill_meta_from_text


_GIT_TREE_SCAN_CACHE: Dict[tuple, List[Dict[str, Any]]] = {}



def _parse_github_owner_repo(raw_url: str) -> Optional[tuple[str, str]]:
    clean = raw_url.strip().rstrip("/")
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", clean)
    if m:
        return m.group(1), m.group(2)
    m_short = re.match(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$", clean)
    if m_short:
        return m_short.group(1), m_short.group(2)
    return None



async def _scan_git_repo_via_api(repo_url: str, token: Optional[str], force_refresh: bool = False) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Scan a GitHub repository directly via REST API in-memory without cloning to disk."""
    import asyncio

    parsed = _parse_github_owner_repo(repo_url)
    if not parsed:
        return [], None
    owner, repo = parsed

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Agents-Platform"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        tree_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
            headers=headers
        )
        if tree_resp.status_code != 200:
            return [], f"github://{owner}/{repo}"

        tree_json = tree_resp.json()
        tree_sha = tree_json.get("sha") or "HEAD"
        cache_key = (owner.lower(), repo.lower(), tree_sha)
        if not force_refresh and cache_key in _GIT_TREE_SCAN_CACHE:
            return _GIT_TREE_SCAN_CACHE[cache_key], f"https://github.com/{owner}/{repo}"

        blobs = [
            item["path"]
            for item in tree_json.get("tree", [])
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
        ]
        blob_set = set(blobs)

        sem = asyncio.Semaphore(15)
        raw_headers = dict(headers)
        raw_headers["Accept"] = "application/vnd.github.raw+json"

        async def fetch_raw(blob_path: str) -> str:
            async with sem:
                try:
                    r = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/contents/{blob_path}",
                        headers=raw_headers
                    )
                    if r.status_code == 200:
                        return r.text
                except Exception:
                    pass
                return ""

        plugins_map: Dict[str, Dict[str, Any]] = {}

        mp_path = None
        mp_prefix = ""
        if "skills-marketplace/marketplace.json" in blob_set:
            mp_path = "skills-marketplace/marketplace.json"
            mp_prefix = "skills-marketplace/"
        elif "marketplace.json" in blob_set:
            mp_path = "marketplace.json"
            mp_prefix = ""

        if mp_path:
            mp_raw = await fetch_raw(mp_path)
            try:
                mp_data = json.loads(mp_raw)
            except Exception:
                mp_data = {}

            tasks_to_fetch = []
            for p_meta in mp_data.get("plugins", []):
                p_id = p_meta.get("id")
                if not p_id:
                    continue
                rel_p_dir = p_meta.get("path", f"plugins/{p_id}").strip("/")
                full_p_dir = f"{mp_prefix}{rel_p_dir}".strip("/")
                if p_id not in plugins_map:
                    plugins_map[p_id] = {
                        "name": p_id,
                        "display_name": p_id.replace("-", " ").replace("_", " ").title(),
                        "version": p_meta.get("version", "1.0.0"),
                        "description": p_meta.get("description", ""),
                        "domain": p_meta.get("domain", ""),
                        "path": f"github://{owner}/{repo}/{full_p_dir}",
                        "skills": []
                    }

                prefix_with_slash = f"{full_p_dir}/"
                for b_path in sorted(blobs):
                    if not b_path.startswith(prefix_with_slash) or not b_path.lower().endswith(".md"):
                        continue
                    parts = b_path.split("/")
                    parts_lower = [pt.lower() for pt in parts]
                    if any(ign in parts_lower for ign in ("references", "assets", "examples", "docs")):
                        continue
                    fname = parts[-1]
                    if fname.lower() in ("changelog.md", "versioning.md", "claude.md", "taxonomy.md", "readme.md", "agents.md"):
                        continue
                    parent_folder = parts[-2] if len(parts) >= 2 else p_id
                    if fname.lower() != "skill.md" and parent_folder not in ("skills", p_id):
                        continue
                    tasks_to_fetch.append((p_id, p_meta, b_path, fname, parent_folder))

            contents = await asyncio.gather(*(fetch_raw(t[2]) for t in tasks_to_fetch))
            for (p_id, p_meta, b_path, fname, parent_folder), text in zip(tasks_to_fetch, contents):
                if not text:
                    continue
                v_path = f"github://{owner}/{repo}/{b_path}"
                meta = extract_skill_meta_from_text(
                    content=text,
                    virtual_path=v_path,
                    filename=fname,
                    parent_name=parent_folder,
                    default_plugin=p_id,
                    default_domain=p_meta.get("domain", ""),
                    default_version=p_meta.get("version", "1.0.0")
                )
                if not any(s["id"] == meta["id"] for s in plugins_map[p_id]["skills"]):
                    plugins_map[p_id]["skills"].append(meta)
        else:
            # Non-manifest Git repository: scan .md skill files
            md_blobs = []
            for b_path in sorted(blobs):
                if not b_path.lower().endswith(".md"):
                    continue
                parts = b_path.split("/")
                parts_lower = [pt.lower() for pt in parts]
                if any(ign in parts_lower for ign in ("references", "assets", "examples", "docs")):
                    continue
                fname = parts[-1]
                if fname.lower() in ("readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md", "agents.md"):
                    continue
                p_name = parts[0] if len(parts) > 1 else repo
                parent_folder = parts[-2] if len(parts) >= 2 else repo
                md_blobs.append((p_name, b_path, fname, parent_folder))

            contents = await asyncio.gather(*(fetch_raw(t[1]) for t in md_blobs))
            for (p_name, b_path, fname, parent_folder), text in zip(md_blobs, contents):
                if not text:
                    continue
                if p_name not in plugins_map:
                    plugins_map[p_name] = {
                        "name": p_name,
                        "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                        "version": "1.0.0",
                        "description": f"Plugin package {p_name}",
                        "domain": "general",
                        "path": f"github://{owner}/{repo}/{p_name}",
                        "skills": []
                    }
                v_path = f"github://{owner}/{repo}/{b_path}"
                meta = extract_skill_meta_from_text(
                    content=text,
                    virtual_path=v_path,
                    filename=fname,
                    parent_name=parent_folder,
                    default_plugin=p_name
                )
                if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                    plugins_map[p_name]["skills"].append(meta)

        plugins_data = summarize_plugins(plugins_map)

        _GIT_TREE_SCAN_CACHE[cache_key] = plugins_data
        return plugins_data, f"https://github.com/{owner}/{repo}"

