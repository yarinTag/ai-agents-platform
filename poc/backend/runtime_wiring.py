"""Composition adapters between runtime ports and platform services."""

from dataclasses import replace
from datetime import datetime

from .capabilities import capabilities


def configure_runtime(adapter, database, configuration, event_service, event_bus, intelligence_provider=None, skill_provider=None):
    """Bind this application's instances, avoiding runtime global lookups."""
    from events import PlatformEvent

    def capture_session(run, session_id):
        with database._get_connection() as conn:
            conn.execute("""
                UPDATE agent_conversations
                SET claude_session_id = ?, runtime_session_id = ?, updated_at = ?
                WHERE agent_id = ? AND (task_id = ? OR status = 'ACTIVE')
            """, (session_id, session_id, datetime.now().isoformat(), run.agent_id, run.run_id))

    def publish_chat(run, message):
        event_bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            event_type="chat.message", agent_id=run.agent_id, task_id=run.run_id,
            payload={
                "id": message["id"], "sender_type": "ASSISTANT",
                "content": message["content"], "task_id": run.run_id,
                "metadata": message.get("metadata"),
                "created_at": datetime.now().isoformat(),
            }, source="runtime",
        ))

    def supervisor(**kwargs):
        try:
            capabilities.require("orchestration")
            from orchestration.supervisor_resolver import SupervisorResolver
        except Exception:
            interaction = database.create_interaction({
                "task_id": kwargs["task_id"], "requester_agent_id": kwargs["requester_agent_id"],
                "target_approver_id": "HUMAN_OPERATOR", "title": "Agent needs clarification",
                "content": kwargs["question"], "context_data": {"context": kwargs.get("context")},
            })
            event_service.emit(event_type="approval.required", payload=interaction,
                               agent_id=kwargs["requester_agent_id"], task_id=kwargs["task_id"],
                               project_id=kwargs.get("project_id"), source="runtime")
            return {"status": "PENDING_INPUT", "target_approver": "HUMAN_OPERATOR"}
        intelligence = None
        if intelligence_provider:
            try:
                intelligence = intelligence_provider()
            except Exception:
                pass
        resolver = SupervisorResolver(database, event_bus=event_bus, runtime_adapter=adapter,
                                      project_intelligence=intelligence, load_default_intelligence=False)
        return resolver.resolve_or_escalate_question(**kwargs)

    adapter.configure_services(replace(
        adapter.services,
        database=lambda: database, configuration=lambda: configuration,
        emit=event_service.emit, publish_chat=publish_chat,
        capture_session=capture_session, supervisor=supervisor, complete=None,
        skills_prompt=skill_provider or adapter.services.skills_prompt,
    ))
