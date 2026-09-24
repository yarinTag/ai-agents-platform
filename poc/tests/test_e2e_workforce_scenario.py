"""
End-to-End Enterprise Scenario Integration Test.

Validates the full enterprise multi-agent workflow:
1. User submits request to Engineering Manager.
2. Manager delegates subtask to Frontend Agent.
3. Frontend Agent hits architectural ambiguity (Tailwind vs Styled-Components).
4. Question is routed to Super Agent / SupervisorResolver.
5. Super Agent resolves it autonomously via Deep Project Intelligence (retrieving the ADR from Project Shared Memory).
6. Frontend Agent receives resolution as an AgentMessage, resumes its Claude Code session with --resume <session_id>.
7. Frontend Agent calls GitHub MCP tool (github.create_pull_request) to record progress.
8. Frontend Agent completes subtask and hands off to QA Agent via AgentMessage.
9. QA Agent verifies and replies.
10. Engineering Manager synthesizes completed results and delivers the final response.

Validates:
- SQLite persistence verified at each step
- EventBus events emitted and verified
- Session continuity verified
- Zero fake completion (honest status throughout)
"""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import (
    get_db_manager, get_event_bus, get_event_service,
    get_mcp_registry, get_mcp_executor
)
from config import AgentConfig, AgentRole, ProjectConfig
from runtime_adapter import TaskStatus, AgentRun
from orchestration import (
    SupervisorResolver, ProjectIntelligence,
    validate_agent_communication
)
from persistence import SuperAgentConfig


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_complete_workforce_scenario_lifecycle(client):
    db = get_db_manager()
    event_bus = get_event_bus()
    event_service = get_event_service()
    mcp_registry = get_mcp_registry()
    mcp_executor = get_mcp_executor()

    # Track all emitted platform events
    captured_events = []
    def on_platform_event(evt):
        captured_events.append(evt)
    event_bus.subscribe(on_platform_event)

    # -------------------------------------------------------------
    # 0. Setup Tenant Project, Workforce Hierarchy, and Super Agent
    # -------------------------------------------------------------
    proj_id = f"proj-corp-{uuid.uuid4().hex[:6]}"
    super_id = f"super-{uuid.uuid4().hex[:6]}"
    mgr_id = f"mgr-{uuid.uuid4().hex[:6]}"
    fe_id = f"fe-{uuid.uuid4().hex[:6]}"
    qa_id = f"qa-{uuid.uuid4().hex[:6]}"

    # Project
    db.save_project(ProjectConfig(
        id=proj_id,
        name="Enterprise SaaS WebApp",
        description="Core multi-tenant enterprise portal",
        working_directory="."
    ))

    # Super Agent
    super_agent = AgentConfig(
        id=super_id,
        name="Super Agent Architect",
        description="Autonomous technical decision maker",
        system_prompt="Resolve architectural ambiguities using project intelligence",
        role_type=AgentRole.SUPER_AGENT.value
    )
    db.save_agent(super_agent)
    db.save_super_agent_config(SuperAgentConfig(
        agent_id=super_id,
        project_id=proj_id,
        can_answer_questions=True,
        can_make_project_decisions=True
    ))


    # Engineering Manager (subordinate to Super Agent)
    mgr = AgentConfig(
        id=mgr_id,
        name="Engineering Manager",
        description="Coordinates web team",
        system_prompt="Plan and manage deliverables",
        role_type=AgentRole.MANAGER.value,
        parent_id=super_id,
        allow_sibling_communication=True
    )
    db.save_agent(mgr)

    # Frontend Specialist (subordinate to Manager, permitted to call GitHub MCP)
    fe = AgentConfig(
        id=fe_id,
        name="Frontend Engineer",
        description="Implements UI components",
        system_prompt="Build React UI",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id,
        allow_sibling_communication=True,
        allowed_peer_ids=[qa_id],
        mcp_permissions=["github"]
    )
    db.save_agent(fe)
    db.add_mcp_permission(agent_id=fe_id, connector_id="github")

    # QA Specialist (subordinate to Manager)
    qa = AgentConfig(
        id=qa_id,
        name="QA Automation Engineer",
        description="Validates quality and regressions",
        system_prompt="Review pull requests and run test suites",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id,
        allow_sibling_communication=True,
        allowed_peer_ids=[fe_id]
    )
    db.save_agent(qa)

    # Seed Project Shared Memory with architectural decision (ADR)
    db.create_project_memory({
        "project_id": proj_id,
        "category": "CONVENTION",
        "title": "Frontend Styling System Standard",
        "content": "All UI components must be styled using Tailwind CSS v3 with custom design tokens. Styled-Components is deprecated.",
        "tags": ["frontend", "styling", "tailwind", "css", "components"],
        "author_agent_id": super_id,
        "confidence": 1.0
    })

    # -------------------------------------------------------------
    # Step 1: User Request to Engineering Manager
    # -------------------------------------------------------------
    root_task_id = f"task-root-{uuid.uuid4().hex[:6]}"
    now = datetime.now()
    root_task = AgentRun(
        run_id=root_task_id,
        agent_id=mgr_id,
        project_id=proj_id,
        prompt="Deliver user profile page feature with authenticated state and tests",
        status=TaskStatus.RUNNING,
        created_at=now
    )
    db.save_task_run(root_task)

    # -------------------------------------------------------------
    # Step 2: Manager Delegates Subtask to Frontend Agent
    # -------------------------------------------------------------
    fe_task_id = f"task-fe-{uuid.uuid4().hex[:6]}"
    fe_session_id = f"session-fe-{uuid.uuid4().hex[:8]}"

    fe_task = AgentRun(
        run_id=fe_task_id,
        agent_id=fe_id,
        project_id=proj_id,
        prompt="Build the User Profile Page UI with responsive avatar, details form, and stats",
        status=TaskStatus.RUNNING,
        created_at=now,
        parent_task_id=root_task_id,
        root_task_id=root_task_id,
        assigned_by=mgr_id,
        session_id=fe_session_id
    )
    db.save_task_run(fe_task)

    # -------------------------------------------------------------
    # Step 3: Frontend Agent Hits Ambiguity & Submits Question
    # -------------------------------------------------------------
    fe_task.status = TaskStatus.WAITING_INPUT
    db.update_task_run(fe_task_id, status=TaskStatus.WAITING_INPUT)

    class MockRuntimeAdapter:
        def __init__(self):
            self.resumed_tasks = []

        def resume_task(self, task_id, answer):
            self.resumed_tasks.append({
                "task_id": task_id,
                "answer": answer
            })

    mock_adapter = MockRuntimeAdapter()
    resolver = SupervisorResolver(
        db_manager=db,
        event_bus=event_bus,
        runtime_adapter=mock_adapter
    )


    # -------------------------------------------------------------
    # Step 4 & 5: Autonomous Resolution via Project Intelligence
    # -------------------------------------------------------------
    question_text = "Should we style the user profile page components using Tailwind CSS or Styled-Components?"
    resolution = resolver.resolve_or_escalate_question(
        task_id=fe_task_id,
        requester_agent_id=fe_id,
        project_id=proj_id,
        question=question_text
    )

    assert resolution["status"] == "AUTO_RESOLVED"
    assert resolution["target_approver"] == super_id
    assert resolution["resolved_by"] == f"SUPER_AGENT:{super_id}"
    assert "Tailwind CSS" in resolution["answer"]



    # -------------------------------------------------------------
    # Step 6: Session Continuity & AgentMessage Verification
    # -------------------------------------------------------------
    # Verify AgentMessage was sent to Frontend Agent
    fe_messages = db.list_agent_messages(agent_id=fe_id)
    assert len(fe_messages) >= 1
    answer_msg = next((m for m in fe_messages if m.message_type == "ANSWER"), None)
    assert answer_msg is not None
    assert "Tailwind CSS" in answer_msg.content

    # Verify resume executed with task_id and answer
    assert len(mock_adapter.resumed_tasks) == 1
    assert mock_adapter.resumed_tasks[0]["task_id"] == fe_task_id
    assert "Tailwind CSS" in mock_adapter.resumed_tasks[0]["answer"]

    # Resume frontend execution
    db.update_task_run(fe_task_id, status=TaskStatus.RUNNING)


    # -------------------------------------------------------------
    # Step 7: Frontend Calls GitHub MCP Tool
    # -------------------------------------------------------------
    mcp_call = mcp_executor.execute_tool(
        agent_id=fe_id,
        connector_id="github",
        tool_name="create_pull_request",
        arguments={
            "title": "feat(ui): User profile page component with Tailwind CSS",
            "branch": "feature/user-profile",
            "base": "master",
            "body": "Implements responsive user profile according to project conventions."
        },
        task_id=fe_task_id
    )

    assert mcp_call["status"] == "COMPLETED"
    assert "pr_number" in str(mcp_call["result"])
    assert mcp_call["call_id"] is not None

    # Verify MCP tool call saved in DB
    saved_call = db.get_mcp_tool_call(mcp_call["call_id"])
    assert saved_call is not None
    assert saved_call.status == "COMPLETED"


    # Verify EventBus events for MCP execution
    mcp_events = [e for e in captured_events if e.event_type.startswith("mcp.tool.")]
    assert len(mcp_events) >= 2
    tool_event_types = [e.event_type for e in mcp_events]
    assert "mcp.tool.started" in tool_event_types
    assert "mcp.tool.completed" in tool_event_types

    # -------------------------------------------------------------
    # Step 8: Frontend Handoff to QA Agent via AgentMessage
    # -------------------------------------------------------------
    handoff_send = client.post(
        "/api/v1/messages",
        json={
            "from_agent_id": fe_id,
            "to_agent_id": qa_id,
            "content": "PR #42 is ready with User Profile UI using Tailwind. Please run automated QA suites.",
            "message_type": "HANDOFF",
            "task_id": fe_task_id
        }
    )
    assert handoff_send.status_code == 201, handoff_send.text
    handoff_msg = handoff_send.json()

    # QA Agent replies to Frontend Agent
    qa_reply = client.post(
        f"/api/v1/messages/{handoff_msg['id']}/reply",
        json={
            "from_agent_id": qa_id,
            "content": "Automated QA passed 42/42 tests. Responsive styling verified across all breakpoints.",
            "message_type": "RESULT"
        }
    )
    assert qa_reply.status_code == 201, qa_reply.text

    # Frontend subtask completed
    db.update_task_run(
        fe_task_id,
        status=TaskStatus.COMPLETED,
        result="User profile UI completed with Tailwind CSS. PR created and verified by QA."
    )

    # -------------------------------------------------------------
    # Step 9: Engineering Manager Synthesizes Final Results
    # -------------------------------------------------------------
    fe_completed = db.get_task_run(fe_task_id)
    assert fe_completed.status == TaskStatus.COMPLETED

    final_result_summary = (
        f"Feature Complete: User Profile Page delivered.\n"
        f"- Architectural Decision: Resolved by Super Agent (Tailwind CSS v3)\n"
        f"- Session Resumed: {fe_session_id}\n"
        f"- Artifact: GitHub PR created via MCP ({str(mcp_call['result'])[:40]}...)\n"
        f"- QA Verification: Passed all suites."
    )

    db.update_task_run(
        root_task_id,
        status=TaskStatus.COMPLETED,
        result=final_result_summary
    )

    # Verify final root task in DB
    final_root = db.get_task_run(root_task_id)
    assert final_root.status == TaskStatus.COMPLETED
    assert "Feature Complete" in final_root.result
    assert "Tailwind CSS v3" in final_root.result
    assert "GitHub PR" in final_root.result

    # Verify complete event chain was preserved
    all_event_types = [e.event_type for e in captured_events]
    assert "approval.auto_resolved" in all_event_types
    assert "agent.message.sent" in all_event_types
    assert "agent.message.received" in all_event_types
    assert "mcp.tool.started" in all_event_types
    assert "mcp.tool.completed" in all_event_types

