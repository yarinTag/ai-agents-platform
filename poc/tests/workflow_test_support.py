"""Shared legacy fixtures; function scopes and implementations are unchanged."""
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from persistence import db_manager, Department, Workflow
from backend.main import app
from workflows.parser import WorkflowParser, WorkflowDefinition
from workflows.sandbox import SandboxManager
from workflows.engine import WorkflowEngine, BudgetExceededError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

