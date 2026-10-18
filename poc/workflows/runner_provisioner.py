"""
Workflow Runner Agent Provisioner.
Handles automatic creation and cleanup of dedicated background automation agents
for workflows.
"""

from typing import Tuple, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)


def provision_workflow_runner_agent(
    db: Any,
    agent_config_cls: Any,
    wf_id: str,
    workflow_name: str,
    def_json: str,
    cron_expression: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Create and persist a dedicated background automation runner agent for a workflow,
    and return (runner_agent_id, enriched_definition_json).
    """
    runner_agent_id = f"wf-agent-{wf_id}"

    try:
        def_dict = json.loads(def_json) if isinstance(def_json, str) else dict(def_json)
    except Exception:
        def_dict = {}

    mcps = def_dict.get("mcp_servers") or []
    skills_raw = def_dict.get("skills") or []
    skill_names = [s.get("name", s.get("id", str(s))) if isinstance(s, dict) else str(s) for s in skills_raw]
    steps = def_dict.get("steps") or []
    cb = def_dict.get("metadata", {}).get("channel_binding") or {}
    channel_info = f"{cb.get('provider')}:{cb.get('channel_id')}" if cb.get("channel_id") else "API/Webhook/Manual"
    cron = cron_expression or def_dict.get("trigger", {}).get("cron_expression") or def_dict.get("trigger", {}).get("cron") or "None"

    step_desc = "\n".join(
        f"- Step {i+1} [{s.get('id', 'step')}]: {s.get('name', 'Action')} ({s.get('type', 'AGENT')})"
        for i, s in enumerate(steps)
    ) or "- Multi-step automated DAG pipeline"

    system_prompt = (
        f"You are the autonomous workflow execution agent for '{workflow_name}' (Workflow ID: {wf_id}).\n"
        f"Trigger schedule: Cron [{cron}], Channel trigger [{channel_info}].\n"
        f"Assigned MCP scope: {', '.join(mcps) if mcps else 'All platform MCPs'}.\n"
        f"Connected skills: {', '.join(skill_names) if skill_names else 'Standard'}.\n"
        f"Pipeline stages:\n{step_desc}\n\n"
        f"Execution rules:\n"
        f"1. You run automatically in background cloud workers on schedule or when triggered via the channel.\n"
        f"2. You are completely detached from the 2D pixel office simulation canvas and do not occupy an office desk.\n"
        f"3. Strictly enforce the assigned MCP scope and skills during DAG execution."
    )

    try:
        runner_agent = agent_config_cls(
            id=runner_agent_id,
            name=f"{workflow_name} Runner",
            description=f"Autonomous workflow agent for '{workflow_name}'. Runs periodically or via channel '{channel_info}'. Detached from office floor.",
            system_prompt=system_prompt,
            skills=skill_names,
            department="Workflow Automations",
            role_type="WORKFLOW_AUTOMATION",
            is_workflow_agent=True,
            workflow_id=wf_id,
            mcp_permissions=mcps,
            allowed_tools=["*"],
            avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={wf_id}",
            temperature=0.3,
        )
        db.save_agent(runner_agent)
    except Exception as e:
        logger.warning(f"Could not auto-create runner agent: {e}")

    def_dict["runner_agent_id"] = runner_agent_id
    def_dict["is_workflow_agent"] = True
    enriched_json = json.dumps(def_dict, indent=2)
    return runner_agent_id, enriched_json


def cleanup_workflow_runner_agent(db: Any, workflow_id: str) -> None:
    """Remove the dedicated background runner agent associated with a deleted workflow."""
    runner_id = f"wf-agent-{workflow_id}"
    try:
        db.delete_agent(runner_id)
    except Exception:
        pass
    try:
        with db._get_connection() as conn:
            conn.execute("DELETE FROM agents WHERE workflow_id = ? OR id = ?", (workflow_id, runner_id))
            conn.commit()
    except Exception:
        pass
