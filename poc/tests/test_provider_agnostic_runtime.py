"""
Tests for Provider-Agnostic Runtime Architecture, Model Policy & Capability Abstraction.

Verifies:
1. ModelPolicyResolver resolves logical tiers (tier:architect, tier:worker) to runtime-specific models.
2. ModelPolicyResolver supports multi-runtime model resolution (e.g., claude_code vs openai).
3. RuntimeRegistry allows registering, retrieving, and switching runtime adapters.
4. OrchestrationEngine operates with any RuntimeAdapter protocol implementation without modifications.
5. ClaudeCodeRuntimeAdapter dynamically resolves model tiers in command generation.
6. Persistence layer supports provider-agnostic runtime_session_id.
7. /api/v1/models/tiers exposes decoupled intelligence tiers.
"""

import pytest
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List

from config import AgentConfig, AgentRole
from runtime.protocol import RuntimeAdapter, RuntimeCapabilities
from runtime.models import TaskStatus, AgentRun
from runtime.model_policy import model_policy_resolver, ModelTier, ModelCapability
from runtime.registry import RuntimeRegistry, RuntimeNotFoundError
from persistence import db_manager


class MockCustomRuntimeAdapter:
    """Mock alternative runtime implementing RuntimeAdapter protocol to verify zero orchestration lock-in."""

    def __init__(self):
        self.started_tasks = []
        self.runs = {}

    def start_task(
        self,
        agent_id: str,
        project_id: Optional[str] = None,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        fork_session: bool = False,
        task_id: Optional[str] = None,
    ) -> str:
        run_id = task_id or f"mock_run_{len(self.started_tasks) + 1}"
        self.started_tasks.append((agent_id, prompt))
        run = AgentRun(
            run_id=run_id,
            agent_id=agent_id,
            project_id=project_id,
            prompt=prompt or "",
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            result="Executed by MockCustomRuntimeAdapter"
        )
        self.runs[run_id] = run
        return run_id

    def get_run_status(self, run_id: str) -> Optional[AgentRun]:
        return self.runs.get(run_id)

    def cancel_run(self, run_id: str) -> bool:
        if run_id in self.runs:
            self.runs[run_id].status = TaskStatus.CANCELLED
            return True
        return False

    def resume_task(self, run_id: str, answer: str) -> str:
        if run_id in self.runs:
            self.runs[run_id].status = TaskStatus.RUNNING
            self.runs[run_id].result = f"Resumed with: {answer}"
        return run_id

    def list_runs(self) -> List[AgentRun]:
        return list(self.runs.values())

    def start_execution(
        self,
        agent_config: AgentConfig,
        project_config: Optional[Any],
        prompt: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        return self.start_task(agent_config.id, None, prompt, session_id, task_id=task_id)

    def get_execution_status(self, execution_id: str) -> Optional[AgentRun]:
        return self.get_run_status(execution_id)

    def cancel_execution(self, execution_id: str) -> bool:
        return self.cancel_run(execution_id)

    def subscribe_to_events(
        self,
        execution_id: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> Callable[[], None]:
        return lambda: None

    def get_capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supports_streaming=True,
            supports_tool_use=True,
            supports_session_resume=True,
            supports_cancellation=True,
            supports_concurrent=True,
            max_concurrent=10,
            supported_models=["mock-model-v1"]
        )


def test_model_policy_resolves_tiers_for_claude_code():
    """Verify ModelPolicyResolver maps logical tiers to Claude models."""
    res_exec = model_policy_resolver.resolve("tier:executive", runtime_type="claude_code")
    assert res_exec.is_tier_mapped is True
    assert res_exec.tier == ModelTier.EXECUTIVE
    assert "claude-3-7-sonnet" in res_exec.resolved_model

    res_worker = model_policy_resolver.resolve("tier:worker", runtime_type="claude_code")
    assert res_worker.is_tier_mapped is True
    assert res_worker.tier == ModelTier.WORKER
    assert "claude-3-5-haiku" in res_worker.resolved_model

    res_dev = model_policy_resolver.resolve("developer", runtime_type="claude_code")
    assert res_dev.is_tier_mapped is True
    assert res_dev.tier == ModelTier.DEVELOPER
    assert "claude-3-5-sonnet" in res_dev.resolved_model


def test_model_policy_resolves_tiers_for_alternative_runtimes():
    """Verify ModelPolicyResolver supports future alternative runtimes (OpenAI, NVIDIA)."""
    res_openai_arch = model_policy_resolver.resolve("tier:architect", runtime_type="openai")
    assert res_openai_arch.is_tier_mapped is True
    assert res_openai_arch.resolved_model == "gpt-4o"

    res_nim_worker = model_policy_resolver.resolve("tier:worker", runtime_type="nvidia_nim")
    assert res_nim_worker.is_tier_mapped is True
    assert "llama-3.3-70b" in res_nim_worker.resolved_model


def test_model_policy_direct_model_pass_through():
    """Verify non-tier proprietary model names are passed through for backward compatibility."""
    res_direct = model_policy_resolver.resolve("claude-3-opus-20240229", runtime_type="claude_code")
    assert res_direct.is_tier_mapped is False
    assert res_direct.tier is None
    assert res_direct.resolved_model == "claude-3-opus-20240229"

    res_default = model_policy_resolver.resolve("default", runtime_type="claude_code")
    assert res_default.resolved_model == "default"


def test_model_policy_list_tiers():
    """Verify listing logical tiers exposes capabilities without proprietary lock-in."""
    tiers = model_policy_resolver.list_tiers()
    tier_ids = {t["id"] for t in tiers}
    assert "tier:executive" in tier_ids
    assert "tier:architect" in tier_ids
    assert "tier:developer" in tier_ids
    assert "tier:worker" in tier_ids
    assert "tier:fast" in tier_ids
    for t in tiers:
        assert "min_context_window" in t
        assert "requires_tools" in t


def test_runtime_registry_lifecycle():
    """Verify registering, retrieving, and switching runtime implementations."""
    registry = RuntimeRegistry()
    mock_adapter = MockCustomRuntimeAdapter()

    assert isinstance(mock_adapter, RuntimeAdapter)

    registry.register("mock_runtime", mock_adapter, set_default=True)
    assert registry.has("mock_runtime") is True
    assert registry.get_default_name() == "mock_runtime"

    retrieved = registry.get()
    assert retrieved is mock_adapter

    retrieved_by_name = registry.get("mock_runtime")
    assert retrieved_by_name is mock_adapter

    caps = registry.list_runtimes()
    assert "mock_runtime" in caps
    assert caps["mock_runtime"].supported_models == ["mock-model-v1"]

    with pytest.raises(RuntimeNotFoundError):
        registry.get("non_existent_runtime")


def test_claude_code_command_builder_resolves_tier():
    """Verify ClaudeCodeRuntimeAdapter resolves model tiers into CLI command flags."""
    from runtime_adapter import runtime_adapter

    agent_with_tier = AgentConfig(
        id="test-tier-agent",
        name="Tier Test Agent",
        description="Testing model tier",
        system_prompt="You are a tier test agent",
        model="tier:worker"
    )

    cmd = runtime_adapter._build_claude_command(
        agent_config=agent_with_tier,
        project_config=None,
        prompt="Do work"
    )

    # Should have resolved tier:worker to claude-3-5-haiku-20241022
    assert "--model" in cmd
    idx = cmd.index("--model")
    assert "claude-3-5-haiku" in cmd[idx + 1]


def test_orchestration_engine_with_alternative_runtime():
    """
    CRITICAL ARCHITECTURAL VERIFICATION:
    Proves that OrchestrationEngine works with an alternative RuntimeAdapter
    without modifying OrchestrationEngine, task lifecycle, hierarchy, or A2A code.
    """
    from orchestration.engine import OrchestrationEngine

    mock_runtime = MockCustomRuntimeAdapter()
    engine = OrchestrationEngine(
        db_manager=db_manager,
        runtime_adapter=mock_runtime,
        event_service=None
    )

    # Create root agent and subordinate in DB for hierarchy validation
    manager_agent = AgentConfig(
        id="test-orch-mgr",
        name="Orch Manager",
        description="Manager",
        system_prompt="Manage",
        role_type="MANAGER",
        allowed_child_ids=["test-orch-wkr"]
    )
    worker_agent = AgentConfig(
        id="test-orch-wkr",
        name="Orch Worker",
        description="Worker",
        system_prompt="Work",
        parent_id="test-orch-mgr",
        role_type="WORKER"
    )
    db_manager.save_agent(manager_agent)
    db_manager.save_agent(worker_agent)

    try:
        # Create a parent run
        parent_run = AgentRun(
            run_id="test_parent_run_1",
            agent_id="test-orch-mgr",
            project_id=None,
            prompt="Root goal",
            status=TaskStatus.RUNNING,
            created_at=datetime.now()
        )
        db_manager.save_task_run(parent_run)

        # Delegate task using OrchestrationEngine
        child_run = engine.delegate_task(
            parent_task_id=parent_run.run_id,
            target_agent_id="test-orch-wkr",
            subtask_prompt="Implement feature",
            acceptance_criteria="Pass unit tests"
        )

        assert child_run.parent_task_id == parent_run.run_id
        assert child_run.agent_id == "test-orch-wkr"
        assert child_run.status == TaskStatus.RUNNING

        # Manager status must transition to WAITING_FOR_CHILDREN
        updated_parent = db_manager.get_task_run(parent_run.run_id)
        assert updated_parent.status == TaskStatus.WAITING_FOR_CHILDREN

        # Complete child task through engine
        completed_child = engine.complete_task(
            task_id=child_run.run_id,
            result="Implementation done",
            structured_result={"summary": "Done", "deliverables": ["code.py"]}
        )
        assert completed_child.status == TaskStatus.COMPLETED

        # Parent should atomically resume and complete
        final_parent = db_manager.get_task_run(parent_run.run_id)
        assert final_parent.status == TaskStatus.COMPLETED

    finally:
        db_manager.delete_agent("test-orch-mgr")
        db_manager.delete_agent("test-orch-wkr")


def test_persistence_supports_runtime_session_id():
    """Verify persistence layer stores and returns runtime_session_id alongside claude_session_id."""
    from config import AgentConfig
    agent_id = "test-session-agent"
    agent = db_manager.get_agent(agent_id)
    if not agent:
        agent = AgentConfig(
            id=agent_id,
            name="Session Test Agent",
            description="Agent for session tests",
            system_prompt="You are a test agent."
        )
        db_manager.save_agent(agent)

    try:
        sess = db_manager.create_agent_session(
            agent_id=agent_id,
            title="Session Provider Agnostic",
            close_existing=False
        )
        assert "runtime_session_id" in sess
        assert "claude_session_id" in sess
        assert sess["runtime_session_id"] == sess["claude_session_id"]

        # Verify list sessions returns runtime_session_id
        sessions = db_manager.list_agent_sessions(agent_id)
        found = next((s for s in sessions if s["id"] == sess["id"]), None)
        assert found is not None
        assert "runtime_session_id" in found
    finally:
        db_manager.delete_agent(agent_id)


@pytest.mark.asyncio
async def test_api_models_tiers_endpoint():
    """Verify /api/v1/models/tiers endpoint returns decoupled intelligence tiers."""
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/models/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5
        tier_names = [t["tier"] for t in data]
        assert "executive" in tier_names
        assert "architect" in tier_names
        assert "worker" in tier_names
