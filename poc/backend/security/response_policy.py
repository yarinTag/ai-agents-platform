"""Serialization boundary for tenant-safe collections and legacy aggregate endpoints."""
import json
from collections import Counter
from fastapi import HTTPException
from starlette.responses import JSONResponse

COLLECTIONS = {"agents": "agent", "projects": "project", "tasks": "task", "workflows": "workflow",
               "departments": "department", "organizations": "organization", "skills": "skill",
               "templates": "template", "schedules": "schedule", "teams": "team", "war-room": "war_room",
               "messages": "message", "approvals": "interaction", "mcp": "connector"}
SECRET_WORDS = ("password", "secret", "token", "api_key", "apikey", "authorization", "private_key", "credential")


def redact_configuration(value):
    if isinstance(value, dict):
        return {key: ("••••••" if any(word in key.lower() for word in SECRET_WORDS) else redact_configuration(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_configuration(item) for item in value]
    if isinstance(value, str) and "://" in value:
        from urllib.parse import urlsplit, parse_qsl
        parsed = urlsplit(value)
        if parsed.username or parsed.password or any(any(word in key.lower() for word in SECRET_WORDS) for key, _ in parse_qsl(parsed.query)):
            return "••••••"
    return value


def safe_details(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return "Unstructured details are unavailable in the safe response."
    return redact_configuration(value)


def sanitize(value):
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: (safe_details(item) if key == "details" else redact_configuration(item) if key in ("configuration", "configuration_masked") else sanitize(item))
                for key, item in value.items() if key not in ("password_hash", "settings_json", "ciphertext", "nonce")}
    return value


def scoped_stats(actor, resources):
    agents = [item for item in actor.db.list_agents(organization_id=actor.organization_id) if resources.allows("agent", item.id)]
    projects = [item for item in actor.db.list_projects(organization_id=actor.organization_id) if resources.allows("project", item.id)]
    tasks = [item for item in actor.db.list_task_runs(organization_id=actor.organization_id, limit=100) if resources.allows("task", item.run_id)]
    counts = Counter(str(getattr(task.status, "value", task.status)) for task in tasks)
    active = [task for task in tasks if str(getattr(task.status, "value", task.status)).upper() in ("QUEUED", "RUNNING")]
    active_runs = [{"run_id": task.run_id, "agent_id": task.agent_id, "project_id": task.project_id,
                    "status": str(getattr(task.status, "value", task.status)),
                    "started_at": task.started_at.isoformat() if task.started_at else None} for task in active]
    skills = [item for item in actor.db.list_skills() if resources.allows("skill", item.id)]
    return {"agents": {"total": len(agents)}, "projects": {"total": len(projects)},
            "skills": {"total": len(skills), "global": sum(not s.project_id for s in skills), "project_specific": sum(bool(s.project_id) for s in skills)},
            "tasks": {"total_recent": len(tasks), "by_status": dict(counts),
                      "active": len(active), "active_runs": active_runs}}


def filter_payload(request, payload):
    actor = getattr(request.state, "access_actor", None)
    resources = getattr(request.state, "access_resources", None)
    path = request.url.path.rstrip("/")
    if not actor or not resources:
        if path == "/api/v1/auth/status":
            payload["active_key_prefix"] = None
        return sanitize(payload)
    domain = path.split("/")[3]
    if path == "/api/v1/events/system/health":
        payload["checks"] = [{"component": row.get("component"), "status": row.get("status"),
                              "message": "Component available" if row.get("status") == "healthy" else "Component unavailable"}
                             for row in payload.get("checks", [])]
        return payload
    if path == "/api/v1/events/system/stats":
        return {**scoped_stats(actor, resources), "timestamp": payload.get("timestamp"), "runtime_available": payload.get("runtime_available", False)}
    if domain == "audit" or path == "/api/v1/auth/logs":
        def visible_log(row):
            details = row.get("details") or {}
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except ValueError:
                    return False
            kind = {"task_run": "task", "department": "department", "organization": "organization", "agent": "agent", "workflow": "workflow", "project": "project", "user": "user", "mcp_connector": "connector"}.get(row.get("entity_type"))
            return resources.allows(kind, row.get("entity_id")) if kind else details.get("organization_id") == actor.organization_id
        return sanitize([row for row in payload if visible_log(row)])
    if domain == "events" and path.endswith("/recent-activity"):
        payload["activity"] = [row for row in payload.get("activity", []) if resources.allows("task", row.get("entity_id"))]
    # Plugin definitions and auth profiles are already projected by their tenant source;
    # the profile must list every accessible dept, independently of the selected dept.
    if domain == "auth" or (domain == "skills" and "/plugins/" in path):
        return sanitize(payload)
    kind = COLLECTIONS.get(domain)
    if domain == "workflows" and "/executions" in path:
        kind = "execution"
        if isinstance(payload, dict):
            for step in payload.get("step_runs") or []:
                agent_id, task_id = step.get("agent_id"), step.get("task_run_id")
                if (agent_id and not resources.allows("agent", agent_id)) or (task_id and not resources.allows("task", task_id)):
                    raise HTTPException(404, "Execution details are outside the authorized department scope.")
    if domain == "mcp" and path.endswith("/permissions"):
        payload["permissions"] = [row for row in payload.get("permissions", []) if resources.allows("agent", row.get("agent_id")) and resources.allows("connector", row.get("connector_id"))]
        return sanitize(payload)
    if domain == "mcp" and "/connectors" not in path:
        return sanitize(payload)
    if domain in ("agents", "tasks") and (path.endswith(("/tree", "/hierarchy", "/children")) or "/hierarchy/tree" in path):
        def prune_tree(node):
            if not isinstance(node, dict):
                return None
            identifier = node.get("run_id") or node.get("id") or node.get("agent_id")
            if not resources.allows(kind, identifier):
                return None
            result = dict(node)
            if isinstance(result.get("children"), list):
                result["children"] = [child for item in result["children"] if (child := prune_tree(item)) is not None]
            return result
        if isinstance(payload, list):
            return sanitize([node for item in payload if (node := prune_tree(item)) is not None])
        return sanitize(prune_tree(payload) or {})
    if domain == "tasks" and path.endswith("/subtasks") and isinstance(payload, list):
        return sanitize([row for row in payload if resources.allows("task", row.get("run_id") or row.get("id"))])
    def allowed(row):
        if not isinstance(row, dict):
            return False
        identifier = (row.get("run_id") or row.get("id")) if kind == "task" else (row.get("id") or row.get("agent_id"))
        return resources.allows(kind, identifier)
    if kind and isinstance(payload, list) and not request.path_params:
        payload = [row for row in payload if allowed(row)]
    elif isinstance(payload, dict):
        for key in ("workflows", "executions", "connectors", "tasks", "agents", "departments", "projects", "schedules", "teams", "sessions"):
            if isinstance(payload.get(key), list) and kind:
                payload[key] = [row for row in payload[key] if allowed(row)]
        if domain == "agents":
            def prune(node):
                if not isinstance(node, dict) or not resources.allows("agent", node.get("id") or node.get("agent_id")):
                    return None
                node = dict(node)
                if isinstance(node.get("children"), list):
                    node["children"] = [child for entry in node["children"] if (child := prune(entry))]
                return node
            if isinstance(payload.get("children"), list):
                payload["children"] = [child for entry in payload["children"] if (child := prune(entry))]
        if domain == "messages" and isinstance(payload.get("replies"), list):
            payload["replies"] = [row for row in payload["replies"] if resources.allows("message", row.get("id"))]
    if domain == "workflows" and not actor.admin:
        def hide_webhooks(item):
            if isinstance(item, list): return [hide_webhooks(row) for row in item]
            if isinstance(item, dict): return {key: hide_webhooks(value) for key, value in item.items() if key != "webhook_token"}
            return item
        payload = hide_webhooks(payload)
    return sanitize(payload)


def protect_response(request, response):
    if response.status_code >= 400 or response.status_code == 204:
        return response
    if "application/json" not in response.headers.get("content-type", ""):
        return response  # Streams authorize their subject before opening, events also filter each event.
    try:
        original = json.loads(response.body)
        content = filter_payload(request, original)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(500, "The response could not be safely scoped.")
    headers = {key: value for key, value in response.headers.items() if key.lower() not in ("content-length", "content-type")}
    return JSONResponse(content=content, status_code=response.status_code, headers=headers, background=response.background)
