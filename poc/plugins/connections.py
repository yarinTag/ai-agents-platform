"""Evidence-backed skill relationships; mentions alone are never execution edges."""
import json
import re
from collections import defaultdict

_PREFIXES = ("product-", "meta-", "tech-", "business-", "shared-")
_ACTION = re.compile(
    r"\b(?:hand\s*off|handoff|route|delegate)\b.{0,220}?\b(?:to|through)\s*$"
    r"|\b(?:invoke|trigger|run|re-run|rerun)\s*$", re.I,
)
_NEGATIVE = re.compile(r"\b(?:not|never|cannot|can't|don't|mustn't|shouldn't|without|avoid|instead\s+of)\b", re.I)
_CONDITIONAL = re.compile(r"\b(?:if|when|once|unless|only|after|before|offer|optional|may|can)\b", re.I)
_ALTERNATIVE = re.compile(r"(?:not\s+to\s+(?:use|activate)|out\s+of\s+scope|do\s+not\s+use|non.goals|\bexamples?\b|\bsamples?\b|output\s+template)", re.I)


def _aliases(skills):
    candidates = defaultdict(set)
    for skill in skills:
        sid = skill["id"]
        candidates[sid.lower()].add(sid)
        short = sid.lower()
        for prefix in _PREFIXES:
            if short.startswith(prefix):
                short = short[len(prefix):]
                break
        if len(short) >= 5:
            candidates[short].add(sid)
    # An alias collision must not silently select the first discovered skill.
    return {alias: next(iter(ids)) for alias, ids in candidates.items() if len(ids) == 1}


def _body_lines(raw):
    """Exclude frontmatter and code examples from imperative handoff detection."""
    frontmatter = raw.startswith("---\n") or raw.startswith("---\r\n")
    fence = None
    section = ""
    headings = []
    for number, line in enumerate(raw.splitlines(), 1):
        if frontmatter:
            if number > 1 and line.strip() == "---":
                frontmatter = False
            continue
        marker = re.match(r"^\s*(```+|~~~+)", line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r"^\s*(#{1,6})\s+(.+)", line)
        if heading:
            level = len(heading[1])
            headings = [(depth, title) for depth, title in headings if depth < level]
            headings.append((level, heading[2]))
            section = " > ".join(title for _, title in headings)
            continue
        yield number, line, section


def _classify(line, start, end, section, pattern):
    # Markdown paths, script invocations and possessives are references to resources,
    # not a request to invoke the containing skill.
    if (start and line[start - 1] in "/-") or (end < len(line) and line[end] in "/-"):
        return "reference"
    if _ALTERNATIVE.search(section):
        return "reference"
    if re.search(r"\brouting\s+table\b", section, re.I) and line.lstrip().startswith("|"):
        return "conditional_handoff"
    prefix = re.sub(r"[`*_]", "", line[:start])
    # Do not carry an imperative verb across sentences or semicolon-separated clauses.
    clause = re.split(r"[.!?;]\s+", prefix)[-1]
    action = _ACTION.search(clause)
    # Preserve explicitly coordinated targets: "hand off to A for review and B".
    coordinated = pattern.sub("SKILL", clause)
    follows_action = re.search(
        r"\b(?:(?:invoke|trigger|run|re-run|rerun)\s+|(?:hand\s*off|handoff|route|delegate)\b.{0,220}?\b(?:to|through)\s+)"
        r"SKILL(?!/)[^.!?;]{0,180}?(?:\band|\bor|,)\s*$", coordinated, re.I,
    )
    if not (action or follows_action) or _NEGATIVE.search(clause):
        return "reference"
    return "conditional_handoff" if _CONDITIONAL.search(line + " " + section) else "handoff"


def enrich_skill_connections(plugins_map, flow_documents=None):
    skills = [skill for pkg in plugins_map.values() for skill in pkg.get("skills", []) if skill.get("id")]
    counts = defaultdict(int)
    for skill in skills:
        counts[skill["id"]] += 1
    known = {skill["id"] for skill in skills if counts[skill["id"]] == 1}
    aliases = _aliases([skill for skill in skills if skill["id"] in known])
    pattern = re.compile(r"(?<![a-z0-9_-])(" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r")(?![a-z0-9_-])", re.I) if aliases else None
    by_id = {skill["id"]: skill for skill in skills if skill["id"] in known}

    for skill in skills:
        raw = skill.pop("_raw_content", None)
        skill["skill_connections"] = []
        skill["connected_skills"] = []
        skill["connection_warnings"] = []
        if counts[skill["id"]] > 1:
            skill["connection_warnings"].append("Duplicate skill ID; relationships cannot be resolved uniquely.")
            continue
        if raw is None:
            skill["connection_warnings"].append("Full skill content unavailable; flow not inferred from preview.")
            continue
        if not pattern:
            continue
        seen = set()
        for number, line, section in _body_lines(raw):
            for match in pattern.finditer(line):
                target = aliases[match[1].lower()]
                if target == skill["id"]:
                    continue
                kind = _classify(line, match.start(), match.end(), section, pattern)
                key = (target, kind, number)
                if key in seen:
                    continue
                seen.add(key)
                skill["skill_connections"].append({
                    "source": skill["id"], "target": target, "kind": kind,
                    "evidence": {"path": skill.get("path", ""), "line": number,
                                 "text": line.strip(), "section": section,
                                 "revision": skill.get("source_revision")},
                })
                if target not in skill["connected_skills"]:
                    skill["connected_skills"].append(target)

    for path, raw in (flow_documents or {}).items():
        try:
            document = json.loads(raw)
            nodes = document["nodes"]
            if not isinstance(nodes, list):
                continue
            nodes_by_id = {node["id"]: node for node in nodes if isinstance(node, dict) and isinstance(node.get("id"), str)}
            if len(nodes_by_id) != len(nodes):
                continue
        except (ValueError, KeyError, TypeError):
            continue
        for node_id, node in nodes_by_id.items():
            source = node.get("skill")
            if not isinstance(source, str) or source not in by_id:
                continue
            next_nodes = node.get("nextNodes", [])
            if not isinstance(next_nodes, list):
                continue
            for target_id in next_nodes:
                next_node = nodes_by_id.get(target_id) if isinstance(target_id, str) else None
                target = next_node.get("skill") if next_node else None
                if not isinstance(target, str) or target not in known or source == target:
                    by_id[source]["connection_warnings"].append(f"Unresolved declared transition: {node_id} → {target_id}.")
                    continue
                by_id[source]["skill_connections"].append({
                    "source": source, "target": target, "kind": "declared_transition",
                    "conditional": bool(node.get("optional") or next_node.get("optional") or node.get("skipFlag") or next_node.get("skipFlag")),
                    "evidence": {"path": path, "node_id": node_id,
                                 "revision": by_id[source].get("source_revision"),
                                 "text": json.dumps({"from": node, "to": next_node}, ensure_ascii=False)},
                })
                if target not in by_id[source]["connected_skills"]:
                    by_id[source]["connected_skills"].append(target)
