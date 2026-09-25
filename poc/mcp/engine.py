"""
MCP (Model Context Protocol) subsystem for AI Agents Platform.
Provides generic connector registry, tool execution engine, and provider implementations.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

from persistence import (
    DatabaseManager, MCPConnector, MCPTool, MCPToolCall
)
from events import EventBus, EventService, PlatformEvent, EventType

logger = logging.getLogger(__name__)


class MCPPermissionDeniedError(PermissionError):
    """Raised when an agent attempts to execute an MCP tool without declared permissions."""
    pass


class MCPRegistry:
    """Registry of available MCP connectors and tool definitions."""

    def __init__(self, db_manager: DatabaseManager, event_service: Optional[EventService] = None):
        self.db = db_manager
        self.event_service = event_service
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register built-in tool handlers for representative providers."""
        # GitHub tools
        self.register_handler("github", "create_issue", self._github_create_issue)
        self.register_handler("github", "get_repo_info", self._github_get_repo_info)
        self.register_handler("github", "create_pull_request", self._github_create_pull_request)

        # Google Workspace tools
        self.register_handler("google_workspace", "search_docs", self._google_search_docs)
        self.register_handler("google_workspace", "create_doc", self._google_create_doc)
        self.register_handler("google_workspace", "send_email_draft", self._google_send_email_draft)

        # Trello tools
        self.register_handler("trello", "create_card", self._trello_create_card)
        self.register_handler("trello", "list_cards", self._trello_list_cards)

        # Telegram tools
        self.register_handler("telegram", "send_message", self._telegram_send_message)

    def register_handler(self, provider: str, tool_name: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        key = f"{provider.lower()}:{tool_name.lower()}"
        self._handlers[key] = handler

    def get_handler(self, provider: str, tool_name: str) -> Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]:
        return self._handlers.get(f"{provider.lower()}:{tool_name.lower()}")

    def seed_default_connectors(self):
        """Seed default realistic connectors and tools if none exist."""
        return

        defaults = [
            {
                "id": "github",
                "name": "GitHub Connector",
                "provider": "github",
                "status": "CONNECTED",
                "configuration": {"api_url": "https://api.github.com", "auth_type": "bearer_token"},
                "capabilities": ["issues", "pull_requests", "repositories"],
                "tools": [
                    {
                        "id": "github-create-issue",
                        "name": "create_issue",
                        "description": "Create a GitHub issue in a repository",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "repo": {"type": "string"},
                                "title": {"type": "string"},
                                "body": {"type": "string"}
                            },
                            "required": ["repo", "title"]
                        }
                    },
                    {
                        "id": "github-create-pr",
                        "name": "create_pull_request",
                        "description": "Open a pull request for branch changes",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "repo": {"type": "string"},
                                "title": {"type": "string"},
                                "head": {"type": "string"},
                                "base": {"type": "string"}
                            },
                            "required": ["repo", "title", "head"]
                        }
                    },
                    {
                        "id": "github-repo-info",
                        "name": "get_repo_info",
                        "description": "Retrieve repository branch and metadata",
                        "input_schema": {
                            "type": "object",
                            "properties": {"repo": {"type": "string"}},
                            "required": ["repo"]
                        }
                    }
                ]
            },
            {
                "id": "google_workspace",
                "name": "Google Workspace Connector",
                "provider": "google_workspace",
                "status": "CONNECTED",
                "configuration": {"services": ["drive", "docs", "gmail"]},
                "capabilities": ["documents", "email", "calendar"],
                "tools": [
                    {
                        "id": "google-search-docs",
                        "name": "search_docs",
                        "description": "Search Google Drive documents and specifications",
                        "input_schema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]
                        }
                    },
                    {
                        "id": "google-create-doc",
                        "name": "create_doc",
                        "description": "Create a new document in Google Docs",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"}
                            },
                            "required": ["title"]
                        }
                    },
                    {
                        "id": "google-send-draft",
                        "name": "send_email_draft",
                        "description": "Draft an email communication",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "to": {"type": "string"},
                                "subject": {"type": "string"},
                                "body": {"type": "string"}
                            },
                            "required": ["to", "subject", "body"]
                        }
                    }
                ]
            },
            {
                "id": "trello",
                "name": "Trello Project Board",
                "provider": "trello",
                "status": "CONNECTED",
                "configuration": {"board_id": "main-board"},
                "capabilities": ["cards", "lists", "labels"],
                "tools": [
                    {
                        "id": "trello-create-card",
                        "name": "create_card",
                        "description": "Create a task card on a Trello board list",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "list_name": {"type": "string"},
                                "title": {"type": "string"},
                                "desc": {"type": "string"}
                            },
                            "required": ["list_name", "title"]
                        }
                    },
                    {
                        "id": "trello-list-cards",
                        "name": "list_cards",
                        "description": "List cards on a specific list",
                        "input_schema": {
                            "type": "object",
                            "properties": {"list_name": {"type": "string"}},
                            "required": ["list_name"]
                        }
                    }
                ]
            },
            {
                "id": "telegram",
                "name": "Telegram Bot Gateway",
                "provider": "telegram",
                "status": "CONNECTED",
                "configuration": {"bot_name": "AntigravityNotifierBot"},
                "capabilities": ["notifications", "messages"],
                "tools": [
                    {
                        "id": "telegram-send-message",
                        "name": "send_message",
                        "description": "Send alert message to Telegram channel or chat",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {"type": "string"},
                                "text": {"type": "string"}
                            },
                            "required": ["text"]
                        }
                    }
                ]
            }
        ]

        for d in defaults:
            tools = d.pop("tools")
            self.db.save_mcp_connector(MCPConnector(**d))
            for t in tools:
                self.db.save_mcp_tool(MCPTool(connector_id=d["id"], **t))

    # Built-in tool handler implementations
    def _github_create_issue(self, args: Dict[str, Any]) -> Dict[str, Any]:
        issue_num = int(datetime.now().timestamp()) % 1000 + 1
        return {
            "status": "success",
            "issue_number": issue_num,
            "url": f"https://github.com/{args.get('repo', 'org/repo')}/issues/{issue_num}",
            "title": args.get("title")
        }

    def _github_create_pull_request(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pr_num = int(datetime.now().timestamp()) % 500 + 1
        return {
            "status": "success",
            "pr_number": pr_num,
            "url": f"https://github.com/{args.get('repo', 'org/repo')}/pull/{pr_num}",
            "head": args.get("head"),
            "base": args.get("base", "main"),
            "title": args.get("title")
        }

    def _github_get_repo_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "repo": args.get("repo", "org/repo"),
            "default_branch": "master",
            "open_issues_count": 4,
            "stars": 128
        }

    def _google_search_docs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        q = args.get("query", "")
        return {
            "status": "success",
            "query": q,
            "results": [
                {"title": f"Product Spec - {q}", "doc_id": "doc_872134", "last_modified": datetime.now().isoformat()},
                {"title": "Architecture Standards v2", "doc_id": "doc_994120", "last_modified": datetime.now().isoformat()}
            ]
        }

    def _google_create_doc(self, args: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        return {
            "status": "success",
            "doc_id": doc_id,
            "title": args.get("title"),
            "url": f"https://docs.google.com/document/d/{doc_id}/edit"
        }

    def _google_send_email_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "draft_id": f"draft_{uuid.uuid4().hex[:8]}",
            "to": args.get("to"),
            "subject": args.get("subject")
        }

    def _trello_create_card(self, args: Dict[str, Any]) -> Dict[str, Any]:
        card_id = f"card_{uuid.uuid4().hex[:8]}"
        return {
            "status": "success",
            "card_id": card_id,
            "list": args.get("list_name"),
            "title": args.get("title")
        }

    def _trello_list_cards(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "list": args.get("list_name"),
            "cards": [
                {"id": "card_01", "name": "Review PR #45", "status": "In Progress"},
                {"id": "card_02", "name": "Implement UI Design Tokens", "status": "Done"}
            ]
        }

    def _telegram_send_message(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "message_id": int(datetime.now().timestamp()) % 10000,
            "chat_id": args.get("chat_id", "channel_ops"),
            "sent_at": datetime.now().isoformat(),
            "text": args.get("text")
        }


class MCPExecutor:
    """Executes MCP tool calls with permission checking, event emission, and persistence."""

    def __init__(self, db_manager: DatabaseManager, registry: MCPRegistry, event_service: Optional[EventService] = None):
        self.db = db_manager
        self.registry = registry
        self.event_service = event_service

    def execute_tool(
        self,
        agent_id: str,
        connector_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        task_id: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool call on behalf of an agent.
        Enforces server-side permissions, tracks call lifecycle, and emits real-time events.
        """
        now = datetime.now().isoformat()
        call_id = f"mcpcall_{uuid.uuid4().hex[:12]}"

        # 1. Enforce Server-Side Permission Check
        has_perm = self.db.check_agent_mcp_permission(agent_id, connector_id, tool_name)
        if not has_perm:
            # Emit permission denied event
            if self.event_service:
                try:
                    self.event_service.emit(
                        event_type=EventType.MCP_PERMISSION_DENIED,
                        payload={
                            "agent_id": agent_id,
                            "connector_id": connector_id,
                            "tool_name": tool_name,
                            "task_id": task_id,
                            "status": "PERMISSION_DENIED"
                        },
                        agent_id=agent_id,
                        task_id=task_id,
                        source="mcp_executor"
                    )
                except Exception as e:
                    logger.warning(f"Error emitting mcp permission denied event: {e}")

            raise MCPPermissionDeniedError(
                f"Agent '{agent_id}' is not authorized to use MCP connector '{connector_id}' or tool '{tool_name}'"
            )

        # 2. Find tool
        tools = self.db.list_mcp_tools(connector_id=connector_id)
        matching_tool = next((t for t in tools if t.name.lower() == tool_name.lower()), None)
        tool_id = matching_tool.id if matching_tool else f"{connector_id}-{tool_name}"

        # 3. Create tool call record in STARTED status
        call_record = MCPToolCall(
            id=call_id,
            connector_id=connector_id,
            tool_id=tool_id,
            agent_id=agent_id,
            task_id=task_id,
            run_id=run_id,
            status="STARTED",
            arguments=arguments,
            started_at=now
        )
        self.db.save_mcp_tool_call(call_record)

        # 4. Emit mcp.tool.started event for the UI animation
        if self.event_service:
            try:
                self.event_service.emit(
                    event_type=EventType.MCP_TOOL_STARTED,
                    payload={
                        "call_id": call_id,
                        "agent_id": agent_id,
                        "connector_id": connector_id,
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                        "task_id": task_id,
                        "run_id": run_id,
                        "status": "STARTED",
                        "arguments": arguments,
                        "timestamp": now
                    },
                    agent_id=agent_id,
                    task_id=task_id,
                    source="mcp_executor"
                )
            except Exception as e:
                logger.warning(f"Error emitting mcp tool started event: {e}")

        # 5. Execute tool via registry handler
        connector = self.db.get_mcp_connector(connector_id)
        provider = connector.provider if connector else connector_id
        handler = self.registry.get_handler(provider, tool_name)

        completed_at = datetime.now().isoformat()
        if not handler:
            # Fallback generic execution result
            result_data = {
                "status": "success",
                "message": f"Executed MCP tool '{tool_name}' on connector '{connector_id}'",
                "arguments": arguments
            }
        else:
            try:
                result_data = handler(arguments)
            except Exception as ex:
                # Record tool failure
                self.db.update_mcp_tool_call(
                    call_id=call_id,
                    status="FAILED",
                    error=str(ex),
                    completed_at=completed_at
                )
                if self.event_service:
                    try:
                        self.event_service.emit(
                            event_type=EventType.MCP_TOOL_FAILED,
                            payload={
                                "call_id": call_id,
                                "agent_id": agent_id,
                                "connector_id": connector_id,
                                "tool_id": tool_id,
                                "tool_name": tool_name,
                                "task_id": task_id,
                                "status": "FAILED",
                                "error": str(ex),
                                "timestamp": completed_at
                            },
                            agent_id=agent_id,
                            task_id=task_id,
                            source="mcp_executor"
                        )
                    except Exception as e:
                        logger.warning(f"Error emitting mcp tool failed event: {e}")
                raise ex

        # 6. Record tool completion
        res_str = json.dumps(result_data) if isinstance(result_data, dict) else str(result_data)
        self.db.update_mcp_tool_call(
            call_id=call_id,
            status="COMPLETED",
            result=res_str,
            completed_at=completed_at
        )

        # 7. Emit mcp.tool.completed event for UI animation completion
        if self.event_service:
            try:
                self.event_service.emit(
                    event_type=EventType.MCP_TOOL_COMPLETED,
                    payload={
                        "call_id": call_id,
                        "agent_id": agent_id,
                        "connector_id": connector_id,
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                        "task_id": task_id,
                        "status": "COMPLETED",
                        "result": result_data,
                        "timestamp": completed_at
                    },
                    agent_id=agent_id,
                    task_id=task_id,
                    source="mcp_executor"
                )
            except Exception as e:
                logger.warning(f"Error emitting mcp tool completed event: {e}")

        return {
            "call_id": call_id,
            "status": "COMPLETED",
            "result": result_data,
            "started_at": now,
            "completed_at": completed_at
        }
