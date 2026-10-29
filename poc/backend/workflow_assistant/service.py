"""Authoritative authoring policy, independent of HTTP, MCP, and model providers."""

import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from croniter import croniter

from .yaml_contract import proposal_artifact
from .models import DraftCreate, DraftUpdate, WorkflowProposal


class AssistantError(ValueError):
    def __init__(self, code: str, message: str, status: int = 403, **details):
        super().__init__(message)
        self.status = status
        self.detail = {"code": code, "message": message, **details}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _approved_ids(value: Any, field: str) -> list[str]:
    """Only explicit list entries count, never defaults, discovery results, or wildcards."""
    if not isinstance(value, list):
        return []
    result = set()
    for item in value:
        if isinstance(item, dict):
            item = item.get(field) or item.get("id")
        if isinstance(item, (str, int)) and not isinstance(item, bool):
            text = str(item).strip()
            if not text or any(char in text for char in ("*", "?", "\n", "\r")):
                continue
            if field == "repository" and (not re.fullmatch(r"[^/:@\s?#]+(?:/[^/:@\s?#]+)+", text)
                    or any(part in (".", "..") for part in text.split("/"))):
                continue
            result.add(text)
    return sorted(result)


class WorkflowAssistantService:
    def __init__(self, db, claims: dict, *, source: str = "platform_api",
                 granted_scopes: Optional[set[str]] = None):
        self.db = db
        self.claims = dict(claims or {})
        self.source = source
        self.client_id = self.claims.get("azp") if isinstance(self.claims.get("azp"), str) else None
        self.granted_scopes = frozenset(granted_scopes) if granted_scopes is not None else None
        if source not in ("platform_api", "mcp"):
            raise ValueError("Unknown authoring client source")
        if source == "mcp" and self.granted_scopes is None:
            raise AssistantError("CLIENT_AUTHORIZATION_REQUIRED", "MCP clients require verified delegated scopes.", 401)

    def _require_scope(self, scope):
        if self.granted_scopes is not None and scope not in self.granted_scopes:
            raise AssistantError("CLIENT_SCOPE_DENIED", "This client connection was not granted the required authoring scope.")

    def _identity(self):
        self._require_scope("workflow-assistant:read")
        user_id, org_id = self.claims.get("sub"), self.claims.get("org_id")
        if not user_id or not org_id:
            raise AssistantError("USER_LOGIN_REQUIRED", "Sign in with your personal organization account.", 401)
        user = self.db.get_user(user_id)
        if not user or user.status != "ACTIVE" or user.organization_id != org_id:
            raise AssistantError("ACCOUNT_UNAVAILABLE", "The account is inactive or no longer belongs to this organization.")
        if not self.db.get_organization(org_id):
            raise AssistantError("ORGANIZATION_UNAVAILABLE", "Organization access is unavailable.")
        return user

    def _workspace(self, department_id: str, *, write: bool = False):
        user = self._identity()
        if not isinstance(department_id, str) or not department_id or len(department_id) > 200:
            raise AssistantError("INVALID_WORKSPACE", "Select a valid department identifier.", 422)
        department = self.db.get_department(department_id)
        if not department or department.organization_id != user.organization_id:
            raise AssistantError("WORKSPACE_NOT_FOUND", "Workspace not found.", 404)
        membership = next((item for item in self.db.get_user_departments(user.id)
                           if item["department_id"] == department_id
                           and item["organization_id"] == user.organization_id), None)
        if user.role != "ORG_ADMIN" and membership is None:
            raise AssistantError("DEPARTMENT_ACCESS_DENIED", "You are not a current member of this department.")
        department_role = membership["department_role"] if membership else None
        can_write = user.role not in ("AUDITOR", "VIEWER") and (
            user.role in ("ORG_ADMIN", "MANAGER", "OPERATOR")
            or department_role in ("MANAGER", "OPERATOR"))
        can_write = can_write and (self.granted_scopes is None or "workflow-assistant:write" in self.granted_scopes)
        can_review = user.role in ("ORG_ADMIN", "MANAGER") or department_role == "MANAGER"
        if write:
            self._require_scope("workflow-assistant:write")
        if write and not can_write:
            raise AssistantError("DRAFT_WRITE_DENIED", "Your current role does not allow authoring drafts.")
        return user, department, can_write, can_review

    def context(self) -> dict:
        user = self._identity()
        departments = self.db.list_departments(organization_id=user.organization_id)
        memberships = {item["department_id"] for item in self.db.get_user_departments(user.id)
                       if item["organization_id"] == user.organization_id}
        return {
            "user": {"id": user.id, "name": user.full_name, "role": user.role},
            "organization_id": user.organization_id,
            "departments": [{"id": item.id, "name": item.name,
                "can_write_drafts": self._workspace(item.id)[2]}
                for item in departments if user.role == "ORG_ADMIN" or item.id in memberships],
            "supports_activation": False,
            "proposal_schema_version": 1,
        }

    def catalog(self, department_id: str) -> dict:
        user, department, can_write, _ = self._workspace(department_id)
        connectors, tools_by_connector = [], {}
        for connector in self.db.list_mcp_connectors(organization_id=user.organization_id):
            grant = self.db.get_department_mcp_access(department.id, connector.id)
            if not grant or grant.organization_id != user.organization_id:
                continue
            tools = [tool for tool in self.db.list_mcp_tools(connector.id)
                     if self.db.check_department_mcp_permission(department.id, connector.id, tool.name)["allowed"]]
            tools_by_connector[connector.id] = tools
            config = connector.configuration if isinstance(connector.configuration, dict) else {}
            connectors.append({
                "id": connector.id, "name": connector.name, "provider": connector.provider,
                "available": connector.status == "CONNECTED",
                "tools": [{"id": tool.id, "name": tool.name} for tool in tools],
                "channels": _approved_ids(config.get("allowed_channels"), "channel_id")
                    if connector.provider in ("slack", "telegram") else [],
                "repositories": _approved_ids(config.get("allowed_repos"), "repository")
                    if connector.provider in ("github", "gitlab", "git") else [],
            })
        agents = []
        with self.db._get_connection() as conn:
            registered_skills = {row["id"] for row in conn.execute(
                "SELECT s.id FROM skills s JOIN projects p ON p.id = s.project_id WHERE p.organization_id = ?",
                (user.organization_id,)).fetchall()}
        for agent in self.db.list_agents(organization_id=user.organization_id, department_ids=[department.id]):
            if agent.is_workflow_agent:
                continue
            permissions = self.db.get_agent_mcp_permissions(agent.id)
            allowed_tools = []
            for connector_id, tools in tools_by_connector.items():
                for tool in tools:
                    allowed = self.db.check_agent_mcp_permission(agent.id, connector_id, tool.name)
                    # Stored grants may refer to the registered tool ID rather than its name.
                    allowed = allowed or any(
                        item["connector_id"] == connector_id and item.get("tool_id") in (None, tool.id, tool.name)
                        for item in permissions)
                    if allowed:
                        allowed_tools.append({"connector_id": connector_id, "tool_name": tool.name})
            agents.append({"id": agent.id, "name": agent.name, "model": agent.model,
                "skills": sorted({skill for skill in agent.skills if isinstance(skill, str) and skill in registered_skills}),
                "tools": allowed_tools})
        result = {
            "organization_id": user.organization_id, "department_id": department.id,
            "user_id": user.id, "can_write_drafts": can_write,
            "agents": agents, "connectors": connectors,
            "skills": [{"id": skill} for skill in sorted({skill for agent in agents for skill in agent["skills"]})],
            "supported_trigger_kinds": ["manual", "webhook", "cron", "channel", "repository"],
            "supports_approval_gates": False,
            "limitations": ["Skills must be registered under an organization-owned project and assigned to the selected agent. Unscoped legacy skills are excluded."],
        }
        if not connectors:
            result["limitations"].append(
                "No MCP connectors are approved for this department. This does not mean the organization has no installed connectors. "
                "An administrator must grant department connector/tool access and explicitly approve the required repositories/channels. "
                "Supplying a connector ID cannot grant access.")
        result["catalog_version"] = _hash({key: value for key, value in result.items()
                                          if key not in ("user_id", "can_write_drafts")})
        return result

    def validate(self, department_id: str, proposal: WorkflowProposal) -> dict:
        return self._validate_in_catalog(proposal, self.catalog(department_id))

    def _validate_in_catalog(self, proposal: WorkflowProposal, catalog: dict) -> dict:
        agents = {item["id"]: item for item in catalog["agents"]}
        connectors = {item["id"]: item for item in catalog["connectors"]}
        errors = []

        def issue(code, path, message):
            errors.append({"code": code, "path": path, "message": message})

        def connector_at(connector_id, path):
            connector = connectors.get(connector_id)
            if not connector:
                issue("CONNECTOR_NOT_ALLOWED", path, "Connector is not registered or permitted in this workspace.")
            elif not connector["available"]:
                issue("CONNECTOR_UNAVAILABLE", path, "The approved connector is not connected.")
            return connector

        def resource_at(connector_id, value, kind, path):
            connector = connector_at(connector_id, path + ".connector_id")
            if connector and value not in connector[kind]:
                field = "repository" if kind == "repositories" else "channel_id"
                issue("RESOURCE_NOT_APPROVED", path + "." + field,
                      "The requested destination is not in the administrator-approved list.")

        keys = [step.key for step in proposal.steps]
        if len(set(keys)) != len(keys):
            issue("DUPLICATE_STEP_KEY", "steps", "Step keys must be unique.")
        dependencies = {}
        for index, step in enumerate(proposal.steps):
            path = f"steps[{index}]"
            dependencies[step.key] = set(step.depends_on)
            for parent in step.depends_on:
                if parent not in keys:
                    issue("UNKNOWN_DEPENDENCY", path + ".depends_on", "Dependency does not identify a proposal step.")
            agent = agents.get(step.agent_id)
            if not agent:
                issue("AGENT_NOT_ALLOWED", path + ".agent_id", "Agent is not available in this workspace.")
            for skill in step.skills:
                if not agent or skill not in agent["skills"]:
                    issue("SKILL_NOT_ALLOWED", path + ".skills", "Skill is not assigned to the selected agent.")
            for tool_index, binding in enumerate(step.tools):
                tool_path = f"{path}.tools[{tool_index}]"
                connector = connector_at(binding.connector_id, tool_path + ".connector_id")
                if connector and not any(tool["name"] == binding.tool_name for tool in connector["tools"]):
                    issue("TOOL_NOT_ALLOWED", tool_path + ".tool_name", "Tool is not registered or allowed for this department.")
                if not agent or binding.model_dump() not in agent["tools"]:
                    issue("AGENT_TOOL_NOT_ALLOWED", tool_path + ".tool_name", "Tool is not permitted for the selected agent.")
                if connector and connector["provider"] in ("github", "gitlab", "git"):
                    if not any(ref.connector_id == binding.connector_id for ref in step.repositories):
                        issue("MISSING_INPUT", path + ".repositories", "Select an approved repository for this tool.")
                if connector and connector["provider"] in ("slack", "telegram"):
                    if not any(ref.connector_id == binding.connector_id for ref in step.channels):
                        issue("MISSING_INPUT", path + ".channels", "Select an approved channel for this tool.")
            for resource_index, ref in enumerate(step.repositories):
                resource_at(ref.connector_id, ref.repository, "repositories", f"{path}.repositories[{resource_index}]")
            for resource_index, ref in enumerate(step.channels):
                resource_at(ref.connector_id, ref.channel_id, "channels", f"{path}.channels[{resource_index}]")
            if step.requires_approval:
                issue("APPROVAL_GATE_NOT_SUPPORTED", path + ".requires_approval",
                      "An enforceable approval gate is not supported by this authoring contract yet.")
        pending = {key: parents & set(keys) for key, parents in dependencies.items()}
        while pending:
            ready = {key for key, parents in pending.items() if not parents}
            if not ready:
                issue("DEPENDENCY_CYCLE", "steps", "Step dependencies contain a cycle.")
                break
            pending = {key: parents - ready for key, parents in pending.items() if key not in ready}
        trigger = proposal.trigger
        if trigger.kind == "cron":
            if not trigger.cron_expression:
                issue("MISSING_INPUT", "trigger.cron_expression", "Provide a cron expression.")
            elif not croniter.is_valid(trigger.cron_expression):
                issue("INVALID_CRON", "trigger.cron_expression", "Provide a valid cron expression.")
        elif trigger.kind in ("channel", "repository"):
            kind = "channels" if trigger.kind == "channel" else "repositories"
            value = trigger.channel_id if trigger.kind == "channel" else trigger.repository
            if not trigger.connector_id or not value:
                issue("MISSING_INPUT", "trigger", "Select an approved trigger connector and destination.")
            else:
                resource_at(trigger.connector_id, value, kind, "trigger")
            supported_events = ("message",) if trigger.kind == "channel" else ("pull_request.opened", "pull_request.updated", "push")
            if not trigger.event:
                issue("MISSING_INPUT", "trigger.event", "Choose a trigger event.")
            elif trigger.event not in supported_events:
                issue("UNSUPPORTED_EVENT", "trigger.event", "Choose an event supported by this authoring contract.")
        # Fields belonging to another trigger kind must not be silently ignored.
        permitted = {"kind"}
        permitted |= {"cron_expression"} if trigger.kind == "cron" else set()
        permitted |= {"connector_id", "channel_id", "event"} if trigger.kind == "channel" else set()
        permitted |= {"connector_id", "repository", "event"} if trigger.kind == "repository" else set()
        for field, value in trigger.model_dump(exclude_none=True).items():
            if field not in permitted:
                issue("UNEXPECTED_TRIGGER_FIELD", f"trigger.{field}", "This field is not used by the selected trigger kind.")
        for index, _ in enumerate(proposal.unresolved_requirements):
            issue("UNRESOLVED_REQUIREMENT", f"unresolved_requirements[{index}]",
                  "Resolve this requirement before the proposal can be ready for review.")
        if not errors:
            artifact = proposal_artifact(proposal)
            if artifact["yaml_error"]:
                issue("WORKFLOW_SCHEMA_INVALID", "workflow", artifact["yaml_error"])
        status = "READY_FOR_REVIEW"
        if errors:
            status = "NEEDS_CLARIFICATION" if all(item["code"] in ("MISSING_INPUT", "UNRESOLVED_REQUIREMENT") for item in errors) else "BLOCKED"
        return {"valid": not errors, "status": status, "errors": errors, "warnings": [],
            "catalog_version": catalog["catalog_version"], "proposal_hash": _hash(proposal.model_dump()),
            "proposal_schema_version": 1}

    def _draft_row(self, conn, draft_id):
        user = self._identity()
        row = conn.execute("SELECT * FROM workflow_assistant_drafts WHERE id = ? AND organization_id = ?",
                           (draft_id, user.organization_id)).fetchone()
        if not row:
            raise AssistantError("DRAFT_NOT_FOUND", "Draft not found.", 404)
        user, _, _, reviewer = self._workspace(row["department_id"])
        if row["created_by"] != user.id and not reviewer:
            raise AssistantError("DRAFT_NOT_FOUND", "Draft not found.", 404)
        return dict(row)

    def _present(self, row, catalog=None) -> dict:
        proposal = WorkflowProposal.model_validate_json(row["proposal_json"])
        current = self._validate_in_catalog(proposal, catalog if catalog is not None else self.catalog(row["department_id"]))
        saved = json.loads(row["validation_json"])
        return {"id": row["id"], "organization_id": row["organization_id"],
            "department_id": row["department_id"], "created_by": row["created_by"],
            "intent_text": row["intent_text"], "proposal": proposal.model_dump(),
            "revision": row["revision"], "status": current["status"], "saved_status": row["status"],
            "validation": current, "saved_validation": saved,
            "catalog_changed": saved["catalog_version"] != current["catalog_version"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "executable": False, **proposal_artifact(proposal)}

    def get_draft(self, draft_id: str) -> dict:
        with self.db._get_connection() as conn:
            row = self._draft_row(conn, draft_id)
        return self._present(row)

    @staticmethod
    def _pagination(limit, offset=0, before_revision=None):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise AssistantError("INVALID_PAGINATION", "Use a limit of 1..100 and a non-negative offset.", 422)
        if before_revision is not None and (type(before_revision) is not int or before_revision < 1):
            raise AssistantError("INVALID_PAGINATION", "before_revision must be a positive integer.", 422)

    def list_drafts(self, department_id: str, limit=50, offset=0) -> list[dict]:
        self._pagination(limit, offset)
        user, _, _, reviewer = self._workspace(department_id)
        catalog = self.catalog(department_id)
        query = "SELECT * FROM workflow_assistant_drafts WHERE organization_id = ? AND department_id = ?"
        params = [user.organization_id, department_id]
        if not reviewer:
            query += " AND created_by = ?"
            params.append(user.id)
        with self.db._get_connection() as conn:
            rows = conn.execute(query + " ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                                (*params, limit, offset)).fetchall()
        return [self._present(dict(row), catalog) for row in rows]

    def _write_revision(self, conn, row, user, generation_id=None):
        snapshot = {"proposal": json.loads(row["proposal_json"]), "intent_text": row["intent_text"],
                    "status": row["status"], "validation": json.loads(row["validation_json"])}
        snapshot.update(proposal_artifact(WorkflowProposal.model_validate(snapshot["proposal"])))
        if generation_id:
            snapshot["generation_id"] = generation_id
        conn.execute("""INSERT INTO workflow_assistant_draft_revisions
            (draft_id, revision, snapshot_json, actor_id, actor_label, source, client_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["id"], row["revision"], _json(snapshot), user.id, user.full_name,
             self.source, self.client_id, row["updated_at"]))

    def _generation_link(self, conn, generation_id, user, department_id, draft_id=None, proposal=None):
        if generation_id is None:
            return None
        generation = conn.execute("""SELECT * FROM workflow_assistant_generations
            WHERE id=? AND organization_id=? AND department_id=? AND created_by=? AND status='COMPLETED'""",
            (generation_id, user.organization_id, department_id, user.id)).fetchone()
        if not generation:
            raise AssistantError("GENERATION_NOT_FOUND", "Completed generation not found.", 404)
        if proposal is not None and _hash(proposal) != _hash(json.loads(generation["result_json"] or "{}").get("proposal")):
            raise AssistantError("GENERATION_PROPOSAL_MISMATCH", "Save the proposal produced by this generation.", 409)
        if generation["saved_draft_id"]:
            return self._draft_row(conn, generation["saved_draft_id"])
        if draft_id:
            revision = conn.execute("SELECT revision FROM workflow_assistant_drafts WHERE id=?", (draft_id,)).fetchone()["revision"]
            conn.execute("UPDATE workflow_assistant_generations SET saved_draft_id=?, saved_draft_revision=? WHERE id=?", (draft_id, revision, generation_id))
        return None

    def create_draft(self, request: DraftCreate, idempotency_key: Optional[str] = None,
                     *, source_generation_id=None) -> dict:
        if idempotency_key is not None and (not isinstance(idempotency_key, str)
                or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key)):
            raise AssistantError("INVALID_IDEMPOTENCY_KEY", "Use a 1..128 character request identifier.", 422)
        with self.db._get_connection() as conn:
            # Lock policy writes as well as draft writes through validation and commit.
            conn.execute("BEGIN IMMEDIATE")
            user, _, _, _ = self._workspace(request.department_id, write=True)
            linked = self._generation_link(conn, source_generation_id, user, request.department_id, proposal=request.proposal.model_dump())
            if linked:
                conn.commit()
                return {**self._present(linked), "replayed": True}
            validation = self.validate(request.department_id, request.proposal)
            if not validation["valid"] and not request.save_blocked:
                raise AssistantError("PROPOSAL_INVALID", "Proposal has unresolved validation errors.", 422, validation=validation)
            request_hash = _hash(request.model_dump())
            if idempotency_key:
                existing = conn.execute("""SELECT * FROM workflow_assistant_drafts
                    WHERE organization_id = ? AND created_by = ? AND idempotency_key = ?""",
                    (user.organization_id, user.id, idempotency_key)).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise AssistantError("IDEMPOTENCY_CONFLICT", "Idempotency key was used for different input.", 409)
                    conn.commit()
                    return {**self._present(dict(existing)), "replayed": True}
            now = datetime.now().isoformat()
            row = {"id": "wfd_" + uuid.uuid4().hex[:16], "organization_id": user.organization_id,
                "department_id": request.department_id, "created_by": user.id, "intent_text": request.intent_text,
                "proposal_json": _json(request.proposal.model_dump()), "validation_json": _json(validation),
                "status": validation["status"], "revision": 1, "created_at": now, "updated_at": now,
                "idempotency_key": idempotency_key, "request_hash": request_hash}
            conn.execute("INSERT INTO workflow_assistant_drafts (" + ", ".join(row) + ") VALUES (" +
                         ", ".join("?" for _ in row) + ")", tuple(row.values()))
            self._write_revision(conn, row, user, source_generation_id)
            self._generation_link(conn, source_generation_id, user, request.department_id, row["id"])
            conn.commit()
        return {**self._present(row), "replayed": False}

    def update_draft(self, draft_id: str, request: DraftUpdate, *, source_generation_id=None) -> dict:
        with self.db._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._draft_row(conn, draft_id)
            user, _, _, reviewer = self._workspace(row["department_id"], write=True)
            if row["created_by"] != user.id and not reviewer:
                raise AssistantError("DRAFT_NOT_FOUND", "Draft not found.", 404)
            linked = self._generation_link(conn, source_generation_id, user, row["department_id"], proposal=request.proposal.model_dump())
            if linked:
                conn.commit()
                return self._present(linked)
            if row["revision"] != request.expected_revision:
                raise AssistantError("REVISION_CONFLICT", "Draft changed. Reload its latest revision before saving.", 409)
            validation = self.validate(row["department_id"], request.proposal)
            if not validation["valid"] and not request.save_blocked:
                raise AssistantError("PROPOSAL_INVALID", "Proposal has unresolved validation errors.", 422, validation=validation)
            values = {"proposal_json": _json(request.proposal.model_dump()),
                      "intent_text": row["intent_text"] if request.intent_text is None else request.intent_text,
                      "validation_json": _json(validation), "status": validation["status"]}
            if any(row[field] != value for field, value in values.items()):
                row.update(values, revision=row["revision"] + 1, updated_at=datetime.now().isoformat())
                conn.execute("""UPDATE workflow_assistant_drafts SET proposal_json = ?, intent_text = ?,
                    validation_json = ?, status = ?, revision = ?, updated_at = ? WHERE id = ?""",
                    (row["proposal_json"], row["intent_text"], row["validation_json"],
                     row["status"], row["revision"], row["updated_at"], draft_id))
                self._write_revision(conn, row, user, source_generation_id)
            self._generation_link(conn, source_generation_id, user, row["department_id"], row["id"])
            conn.commit()
        return self._present(row)

    def history(self, draft_id: str, limit=50, before_revision=None) -> list[dict]:
        self._pagination(limit, before_revision=before_revision)
        with self.db._get_connection() as conn:
            self._draft_row(conn, draft_id)
            query = "SELECT * FROM workflow_assistant_draft_revisions WHERE draft_id = ?"
            params = [draft_id]
            if before_revision is not None:
                query += " AND revision < ?"
                params.append(before_revision)
            rows = conn.execute(query + " ORDER BY revision DESC LIMIT ?", (*params, limit)).fetchall()
        return [{**{key: row[key] for key in ("draft_id", "revision", "actor_id", "actor_label", "source", "client_id", "created_at")},
                 "snapshot": json.loads(row["snapshot_json"])} for row in rows]
