"""Lazy compatibility wiring for callers outside the backend composition root.

Only this adapter imports concrete platform services on demand. Backend startup
can replace these defaults using ClaudeCodeRuntimeAdapter.configure_services.
"""

from datetime import datetime
from .services import RuntimeServices


def get_database():
    from persistence import db_manager
    return db_manager


def get_configuration():
    from config import config_manager
    return config_manager


def resolve_model(model):
    from .model_policy import model_policy_resolver
    return model_policy_resolver.resolve(model, runtime_type="claude_code").resolved_model


def skills_prompt(skills):
    from skills_service import build_skills_system_prompt
    return build_skills_system_prompt(skills)


def capture_session(run, session_id):
    with get_database()._get_connection() as conn:
        conn.execute("""
            UPDATE agent_conversations
            SET claude_session_id = ?, runtime_session_id = ?, updated_at = ?
            WHERE agent_id = ? AND (task_id = ? OR status = 'ACTIVE')
        """, (session_id, session_id, datetime.now().isoformat(), run.agent_id, run.run_id))
        conn.commit()


def emit(**kwargs):
    import backend.dependencies as dependencies
    service = getattr(dependencies, "_event_service", None)
    if service:
        service.emit(**kwargs)


def publish_chat(run, message):
    from events import PlatformEvent
    import backend.dependencies as dependencies
    bus = getattr(dependencies, "_event_bus", None)
    if bus:
        bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            event_type="chat.message",
            agent_id=run.agent_id,
            task_id=run.run_id,
            payload={
                "id": message["id"],
                "sender_type": "ASSISTANT",
                "content": message["content"],
                "task_id": run.run_id,
                "metadata": message.get("metadata"),
                "created_at": datetime.now().isoformat(),
            },
            source="runtime",
        ))


def complete(run):
    import backend.dependencies as dependencies
    engine = dependencies.get_orchestration_engine()
    if engine:
        engine.handle_task_completion(run)


def create_legacy_services(adapter):
    def supervisor(**kwargs):
        from orchestration.supervisor_resolver import SupervisorResolver
        resolver = SupervisorResolver(get_database(), runtime_adapter=adapter)
        return resolver.resolve_or_escalate_question(**kwargs)

    return RuntimeServices(
        database=get_database,
        configuration=get_configuration,
        resolve_model=resolve_model,
        skills_prompt=skills_prompt,
        capture_session=capture_session,
        emit=emit,
        publish_chat=publish_chat,
        supervisor=supervisor,
        complete=complete,
    )
