"""Shared legacy fixtures; function scopes and implementations are unchanged."""
import os
import sys
import uuid
import json
import pytest
from datetime import datetime
from pathlib import Path
from backend.dependencies import get_db_manager, get_event_service, get_orchestration_engine
from config import AgentConfig, AgentRole, ProjectConfig
from runtime_adapter import TaskStatus, AgentRun, ClaudeCodeRuntimeAdapter
from orchestration.engine import OrchestrationEngine, DelegationError, ConcurrencyLimitExceededError
from orchestration.supervisor_resolver import SupervisorResolver
from events import EventType, PlatformEvent, EventBus


@pytest.fixture
def db():
    manager = get_db_manager()
    return manager


@pytest.fixture
def mock_runtime():
    """Mock runtime adapter to record launches without invoking external claude processes."""
    class MockAdapter:
        def __init__(self):
            self.started_tasks = []
            self.resumed_tasks = []
            self.on_task_completed = None

        def start_task(self, task_id=None, agent_id=None, project_id=None, prompt=None, **kwargs):
            tid = task_id or f"run_{uuid.uuid4().hex[:6]}"
            self.started_tasks.append((tid, agent_id or task_id, prompt))
            return tid

        def resume_task(self, task_id, answer):
            self.resumed_tasks.append((task_id, answer))
            return f"resume_{task_id}"

    return MockAdapter()


@pytest.fixture
def engine(db, mock_runtime):
    ev_svc = get_event_service()
    eng = OrchestrationEngine(db_manager=db, runtime_adapter=mock_runtime, event_service=ev_svc)
    mock_runtime.on_task_completed = eng.handle_task_completion
    return eng

