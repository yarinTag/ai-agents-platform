"""HTTP admission policy for every registered domain, before endpoint side effects."""
import json
from fastapi import HTTPException, Request, Depends
from ..dependencies import get_db_manager
from .identity import load_actor
from .resource_access import Resources
from .route_permissions import required_level

PUBLIC = {"/api/v1/auth/login", "/api/v1/auth/org-register", "/api/v1/invitations/accept", "/api/v1/auth/status"}
DISABLED = {"queue"}  # Host-global operations have no safe tenant partition.
ADMIN_DOMAINS = {"runtimes", "audit", "fs"}
REFERENCES = {
    "agent_id": "agent", "agentId": "agent", "agent": "agent", "runner_agent_id": "agent", "reviewerAgentId": "agent", "from_agent_id": "agent", "to_agent_id": "agent", "target_agent_id": "agent",
    "requester_agent_id": "agent", "moderator_agent_id": "agent", "manager_agent_id": "agent",
    "project_id": "project", "task_id": "task", "parent_task_id": "task", "parent_run_id": "task", "root_task_id": "task", "run_id": "task",
    "workflow_id": "workflow", "execution_id": "execution", "connector_id": "connector",
    "department_id": "department", "dept_id": "department", "interaction_id": "interaction",
    "parent_message_id": "message", "memory_id": None,
}
LIST_REFERENCES = {"member_agent_ids": "agent", "participant_agent_ids": "agent", "allowed_child_ids": "agent", "allowed_peer_ids": "agent", "task_ids": "task", "mcp_servers": "connector", "mcpServers": "connector"}



async def authorize_request(request: Request, db=Depends(get_db_manager)):
    path = request.url.path.rstrip("/")
    if path in PUBLIC:
        return
    # Global callback secrets do not identify a tenant user or department approver.
    if path.endswith(("/telegram-callback", "/slack-callback", "/dispatch-channel")):
        raise HTTPException(403, "Legacy channel approvals require tenant-bound identity and are disabled.")
    actor = load_actor(request, db)
    resources = Resources(actor)
    request.state.access_actor, request.state.access_resources = actor, resources
    domain = path.split("/")[3] if len(path.split("/")) > 3 else ""
    if domain in DISABLED:
        raise HTTPException(403, "This host-global operation is unavailable to tenant accounts.")
    if domain not in {"agents", "projects", "skills", "tasks", "events", "templates", "models", "runtimes",
                      "audit", "auth", "schedules", "approvals", "chat", "war-room", "messages", "teams",
                      "workflows", "mcp", "organizations", "departments"}:
        raise HTTPException(403, "No tenant policy is registered for this operation.")
    level = required_level(request, domain)
    if level == 1 and domain != "auth":
        actor.require(level=1)
    if domain in ADMIN_DOMAINS or path in ("/api/v1/auth/logs", "/api/v1/skills/plugins/git-repos") or path.endswith("/users"):
        if not actor.admin:
            raise HTTPException(403, "Organization administrator access is required.")
    if domain == "organizations" and request.method == "POST":
        raise HTTPException(403, "Tenant creation uses the explicit registration flow.")
    if domain == "templates" and path.endswith("/instantiate"):
        level = 3
    if level == 4 and not actor.admin:
        raise HTTPException(403, "Organization administrator access is required.")
    body = {}
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        try:
            raw = await request.body()
            body = json.loads(raw) if raw else {}
        except (ValueError, UnicodeError):
            raise HTTPException(422, "A JSON request body is required.")
        if not isinstance(body, dict):
            raise HTTPException(422, "A JSON object is required.")
    execution_input = domain == "workflows" and (path.endswith(("/execute", "/playground")) or "/webhook/" in path)
    if execution_input:
        body = {}  # This endpoint body is model input, not an authoring authority document.
    query = dict(request.query_params)
    if domain == "skills" and path.endswith("/plugins/scan") and any(k in query for k in ("source_mode", "git_repo", "local_path")):
        if not actor.admin:
            raise HTTPException(403, "Only administrators may change plugin sources.")
    if request.method in ("PUT", "PATCH") and "organization_id" in body and body["organization_id"] != actor.organization_id:
        raise HTTPException(403, "Organization ownership cannot be reassigned.")
    if parameters_token := request.path_params.get("webhook_token"):
        workflow = actor.db.get_workflow_by_webhook_token(parameters_token)
        resources.require("workflow", workflow.id if workflow else None, 2)
    for values in (request.path_params, query, body):
        for key in ("organization_id", "org_id"):
            if values.get(key) and values[key] != actor.organization_id:
                raise HTTPException(404, "Organization not found in the authorized scope.")
    parameters = {**query, **request.path_params}
    extra = {"user_id": "user", "team_id": "team", "skill_id": "skill", "template_id": "template"}
    if domain == "schedules":
        extra["job_id"] = "schedule"
    if domain == "war-room":
        extra["session_id"] = "war_room"
    if domain == "messages":
        extra["message_id"] = "message"
    for key, kind in {**REFERENCES, **extra}.items():
        if kind and parameters.get(key):
            resources.require(kind, parameters[key], 1 if level == 4 or kind == "template" else level)
    # Membership/invitation removal is always admin-only, including foreign IDs.
    if domain in ("organizations", "departments") and request.method not in ("GET", "HEAD"):
        actor.require(level=4)
    if level in (2, 3) and not any(rank >= level for rank in actor.departments.values()):
        raise HTTPException(403, "This operation requires an authorized department role.")
    if domain in ("agents", "workflows") and request.method == "POST" and not request.path_params and path in ("/api/v1/agents", "/api/v1/workflows"):
        actor.require(body.get("department_id") or actor.default_department(), level)
    inspected = 0
    def validate(values, depth=0):
        nonlocal inspected
        inspected += 1
        if depth > 20 or inspected > 5000:
            raise HTTPException(422, "Resource references exceed the supported nesting limit.")
        for key, value in values.items():
            kind = REFERENCES.get(key)
            if kind and value:
                if value == "__workflow_runner__" and key == "agent_id" and domain == "workflows":
                    continue
                resources.require(kind, value, 1 if level == 4 or kind in ("project", "connector") else level)
            if key in LIST_REFERENCES and isinstance(value, list):
                for identifier in value:
                    resources.require(LIST_REFERENCES[key], identifier, 1 if level == 4 or LIST_REFERENCES[key] == "connector" else level)
            if key in ("steps", "resources", "authorized_resources") and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        validate(item, depth + 1)
            if key in ("workspace", "params", "settings", "channel_binding") and isinstance(value, dict):
                validate(value, depth + 1)
        if domain in ("agents", "templates") and values.get("parent_id"):
            resources.require("agent", values["parent_id"], 1 if level == 4 else level)
    validate(body)
    if body.get("definition_yaml"):
        import yaml
        try:
            definition = yaml.safe_load(body["definition_yaml"])
            if isinstance(definition, dict):
                validate(definition)
        except yaml.YAMLError:
            raise HTTPException(422, "Invalid workflow YAML.")
    if body.get("definition_json"):
        try:
            definition = json.loads(body["definition_json"])
            if isinstance(definition, dict):
                validate(definition)
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid workflow JSON.")
    # Explicit null must not move a department-owned record into org-wide scope.
    if not actor.admin and "department_id" in body and not body["department_id"]:
        raise HTTPException(403, "An authorized department is required.")
    if domain in ("agents", "projects", "workflows", "mcp") and request.method == "POST" and body.get("id"):
        kind = {"agents": "agent", "projects": "project", "workflows": "workflow", "mcp": "connector"}[domain]
        if resources.get(kind, body["id"]):
            resources.require(kind, body["id"], 1 if level == 4 else level)
    # Local files are explicit tenant storage, never host directories or another dept.
    from runtime.tenant_workspace import tenant_workspace
    target_department = body.get("department_id") or actor.default_department(3)
    if domain == "agents" and parameters.get("agent_id"):
        target_department = body.get("department_id") or getattr(resources.get("agent", parameters["agent_id"]), "department_id", None)
    for values in (body, query):
        for key in ("repo_path", "working_directory", "local_path", "plugins_local_path"):
            if values.get(key):
                try:
                    tenant_workspace(actor.organization_id, target_department, values[key], shared=key != "repo_path")
                except ValueError:
                    raise HTTPException(403, "File access is limited to authorized tenant storage.")
    if domain == "fs" and path.endswith("/pick-folder"):
        raise HTTPException(403, "Host-native folder selection is not a tenant-scoped operation.")
    if domain == "workflows" and path.endswith("/generate"):
        actor.require(actor.default_department(3), 3)
    if domain == "skills" and "/plugins/" in path:
        org = actor.db.get_organization(actor.organization_id)
        if org.plugins_source_mode == "local" and org.plugins_local_path:
            try:
                tenant_workspace(actor.organization_id, candidate=org.plugins_local_path, shared=True)
            except ValueError:
                raise HTTPException(403, "The local plugin source is outside tenant storage.")

    memory_id = request.path_params.get("memory_id")
    if memory_id:
        memory = actor.db.get_project_memory(memory_id)
        if not memory or memory.get("project_id") != request.path_params.get("project_id"):
            raise HTTPException(404, "Memory not found in the authorized project.")
    conversation_id = body.get("conversation_id") or parameters.get("conversation_id")
    if domain == "chat" and conversation_id:
        conversation = actor.db.get_conversation(conversation_id)
        if not conversation or conversation.get("agent_id") != parameters.get("agent_id"):
            raise HTTPException(404, "Conversation not found for this agent.")
        if conversation.get("project_id"):
            resources.require("project", conversation["project_id"])
        if conversation.get("task_id"):
            resources.require("task", conversation["task_id"])
    if domain == "chat" and request.method == "POST":
        agent_id = parameters.get("agent_id")
        pending = actor.db.list_interactions(agent_id=agent_id, status="PENDING")
        for interaction in pending:
            resources.require("interaction", interaction["id"], 2 if interaction.get("interaction_type") == "QUESTION" else 3)
    if body.get("target_approver_id") and body["target_approver_id"] != "HUMAN_OPERATOR":
        resources.require("agent", body["target_approver_id"])
    if body.get("tool_id"):
        tool = actor.db.get_mcp_tool(body["tool_id"])
        connector = body.get("connector_id") or parameters.get("connector_id")
        if not tool or (connector and getattr(tool, "connector_id", None) != connector):
            raise HTTPException(404, "Tool not found for this connector.")
    if domain == "skills" and path.endswith("/plugins/content"):
        content_path = query.get("path", "")
        org = actor.db.get_organization(actor.organization_id)
        if content_path.startswith("github://"):
            from plugins.git_scanner import _parse_github_owner_repo
            parsed = _parse_github_owner_repo(org.plugins_git_repo or "")
            if org.plugins_source_mode != "git" or not parsed or not content_path.startswith(f"github://{parsed[0]}/{parsed[1]}/") or ".." in content_path.split("/"):
                raise HTTPException(404, "Skill is outside the configured organization source.")
        else:
            try:
                tenant_workspace(actor.organization_id, candidate=content_path, shared=True)
            except ValueError:
                raise HTTPException(404, "Skill is outside tenant storage.")

    if request.method == "DELETE" and domain == "agents" and parameters.get("agent_id"):
        for child in actor.db.get_child_agents(parameters["agent_id"]):
            resources.require("agent", child.id, 3)
    if body.get("dangerously_skip_permissions"):
        raise HTTPException(403, "Tenant accounts cannot enable host permission bypass.")

    if request.method in ("PUT", "PATCH") and domain in ("agents", "workflows") and "department_id" in body:
        kind = "agent" if domain == "agents" else "workflow"
        identifier = parameters.get("agent_id" if kind == "agent" else "workflow_id")
        existing = resources.get(kind, identifier)
        if existing and getattr(existing, "department_id", None) != body["department_id"]:
            raise HTTPException(409, "Department transfers require an explicit ownership/history migration; create a resource in the destination department instead.")

    if execution_input and request.path_params.get("workflow_id"):
        workflow = resources.require("workflow", request.path_params["workflow_id"], 2)
        from workflows.parser import WorkflowParser
        try:
            definition = WorkflowParser.from_json(workflow.definition_json)
        except Exception:
            definition = WorkflowParser.from_yaml(workflow.definition_json)
        for step in definition.steps:
            agent = resources.require("agent", step.agent_id, 2)
            if getattr(agent, "department_id", None) not in (None, workflow.department_id):
                raise HTTPException(403, "Step agents must belong to the workflow department.")
            reviewer = (getattr(step, "params", None) or {}).get("reviewerAgentId")
            if reviewer:
                reviewer_agent = resources.require("agent", reviewer, 2)
                if getattr(reviewer_agent, "department_id", None) not in (None, workflow.department_id):
                    raise HTTPException(403, "Reviewer must belong to the workflow department.")
