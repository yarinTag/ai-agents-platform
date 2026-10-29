"""Compatibility facade and composition root for SQLite persistence.

Repositories own SQL; this module retains the historical DatabaseManager API.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Iterator, Tuple
import sqlite3
from config import AgentConfig, ProjectConfig, Skill, AgentTemplate, SuperAgentConfig, AgentRole
from runtime.models import AgentRun, TaskStatus
from events.models import PlatformEvent
from storage.records import (
    AgentMessage, MCPConnector, MCPTool, MCPToolCall, AgentTeam, Organization,
    User, DepartmentMember, OrgInvitation, Department, DepartmentMCPAccess,
    Workflow, WorkflowExecution, WorkflowStepRun, RunEvaluation,
)
from storage.paths import POC_ROOT, DEFAULT_DB_PATH
from storage.connection import ConnectionStore
from storage.legacy_api import METHOD_OWNERS
from storage.composition import configure_repositories
from storage.seeds import _seed_default_templates, _seed_default_agents
from storage.execution_schema import initialize as initialize_execution_schema
from storage.event_schema import initialize as initialize_event_schema
from storage.collaboration_schema import initialize as initialize_collaboration_schema
from storage.integration_schema import initialize as initialize_integration_schema
from storage.organization_schema import initialize as initialize_organization_schema
from storage.workflow_schema import initialize as initialize_workflow_schema

class DatabaseManager:
    """Compose repositories and retain the legacy instance API through delegation."""

    def __getattr__(self, name):
        """Resolve legacy methods to their single repository implementation."""
        owner = METHOD_OWNERS.get(name)
        if owner is None:
            raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")
        return getattr(object.__getattribute__(self, owner), name)

    def __dir__(self):
        return sorted(set(super().__dir__()) | METHOD_OWNERS.keys())

    def __init__(self, db_path: Optional[str] = None):
        self.max_agents = int(os.getenv("PLATFORM_MAX_AGENTS", "18"))
        self._connection = ConnectionStore(DEFAULT_DB_PATH if db_path is None else db_path, self._init_database_tables)
        configure_repositories(self)
        self._init_database()

    @property
    def db_path(self):
        return self._connection.db_path

    @db_path.setter
    def db_path(self, value):
        self._connection.db_path = Path(value)

    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        return self._connection.connect()

    def _init_database(self):
        self._connection.initialize()

    def _init_database_tables(self):
        with self._get_connection() as conn:
            initialize_execution_schema(conn)
            initialize_event_schema(conn)
            initialize_collaboration_schema(conn)
            initialize_integration_schema(conn)
            initialize_organization_schema(conn)
            initialize_workflow_schema(conn)
            self._seed_default_templates(conn)
            self._seed_default_agents(conn)
            conn.commit()

    def _seed_default_templates(self, conn):
        return _seed_default_templates(conn)

    def _seed_default_agents(self, conn):
        return _seed_default_agents(conn)

db_manager = DatabaseManager()
