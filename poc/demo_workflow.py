"""
Live Interactive Workflow Demonstration (Overcut-Inspired Engine)

Demonstrates:
1. Defining a multi-agent workflow in YAML.
2. Department budget check (HARD_STOP protection).
3. Sandbox isolation (ephemeral environment created & torn down).
4. Step-by-step DAG execution with dynamic variable passing between agents.
5. Token & Cost accumulation.
6. Webhook triggering format.
7. Human-in-the-loop review & lessons learned capture.
"""

import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

# Add 'poc' directory to sys.path so modules resolve cleanly
POC_ROOT = Path(__file__).resolve().parent
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))

from persistence import db_manager
from workflows.parser import WorkflowParser
from workflows.engine import WorkflowEngine
from workflows.sandbox import SandboxManager


def run_live_workflow_demo():
    print("=" * 70)
    print("🚀  AI AGENTS PLATFORM — OVERCUT WORKFLOW LIVE DEMO")
    print("=" * 70)

    # 1. Setup Department & Budget
    dept_id = "dept-platform-eng"
    dept = db_manager.get_department(dept_id)
    if not dept:
        dept = db_manager.create_department(
            id=dept_id,
            name="Platform Engineering",
            monthly_budget_usd=100.0,
            budget_action="HARD_STOP"
        )
        print(f"✅ Created Department: '{dept.name}' (Monthly Budget: ${dept.monthly_budget_usd})")
    else:
        print(f"ℹ️  Using Existing Department: '{dept.name}' (Monthly Budget: ${dept.monthly_budget_usd})")

    # 2. Define Workflow in YAML
    wf_yaml = """id: wf-pr-security-gate
name: Pull Request Security & Quality Gate
description: Autonomous multi-agent pipeline for auditing incoming pull requests
department_id: dept-platform-eng
steps:
  - key: triage
    name: PR Code & Test Triage
    agent_id: qa-test-engineer
    prompt_template: "Triage pull request #{{pr_number}}: '{{pr_title}}'. Assess code coverage and identify potential test regressions."

  - key: security_audit
    name: Security & Vulnerability Audit
    agent_id: release-security-reviewer
    depends_on:
      - triage
    prompt_template: "Perform static security audit based on QA triage results: {{triage.output}}. Verify no secret leakage and validate input sanitization."

  - key: executive_signoff
    name: Final Executive Sign-off
    agent_id: ceo-orchestrator
    depends_on:
      - security_audit
    prompt_template: "Review QA triage and Security audit findings: {{security_audit.output}}. Provide final deployment approval decision."
"""

    print("\n📄 Workflow Definition (YAML):")
    print("-" * 50)
    print(wf_yaml.strip())
    print("-" * 50)

    # 3. Parse and Save Workflow
    wf_def = WorkflowParser.from_yaml(wf_yaml)
    wf_json = wf_def.to_json()

    existing_wf = db_manager.get_workflow(wf_def.id)
    if existing_wf:
        workflow = existing_wf
    else:
        workflow = db_manager.create_workflow(
            id=wf_def.id,
            name=wf_def.name,
            description=wf_def.description,
            definition_json=wf_json,
            department_id=dept_id,
            webhook_enabled=True
        )
    webhook_token = workflow.webhook_token

    print(f"\n🔗 Workflow Registered in Database:")
    print(f"   • ID: {workflow.id}")
    print(f"   • Steps Count: {len(wf_def.steps)}")
    print(f"   • Dedicated Webhook Token: {webhook_token}")
    print(f"   • Webhook Trigger Endpoint: /api/v1/workflows/webhook/{webhook_token}")

    # 4. Execute Workflow
    print("\n⚙️  Executing Workflow Live...")
    engine = WorkflowEngine(db_manager=db_manager)

    trigger_payload = {
        "pr_number": "104",
        "pr_title": "Integrate Overcut Workflow Engine & Sandboxing"
    }

    execution = engine.execute_workflow(
        workflow_id=workflow.id,
        trigger_type="WEBHOOK",
        trigger_payload=trigger_payload
    )

    print(f"\n📊 Execution Completed: {execution.status}")
    print(f"   • Execution ID: {execution.id}")
    print(f"   • Started At:   {execution.started_at}")
    print(f"   • Completed At: {execution.completed_at}")
    print(f"   • Total Cost:   ${execution.total_cost_usd:.4f}")
    print(f"   • Total Tokens: In={execution.total_input_tokens}, Out={execution.total_output_tokens}")
    print(f"   • Sandbox Used: {execution.sandbox_path} (Auto-cleaned)")

    # 5. Fetch and Display Individual Step Outputs
    print("\n📋 Step-by-Step Execution Results:")
    with db_manager._get_connection() as conn:
        step_runs = conn.execute(
            "SELECT step_key, agent_id, status, output_data, cost_usd FROM workflow_step_runs WHERE execution_id = ? ORDER BY started_at ASC",
            (execution.id,)
        ).fetchall()

    for idx, s in enumerate(step_runs, start=1):
        print(f"\n  [Step {idx}] {s['step_key']} (Agent: {s['agent_id']}) — Status: {s['status']}")
        print(f"     Output: {s['output_data']}")

    # 6. Submit Human Review Evaluation (Learning Loop)
    print("\n🧠 Recording Human-in-the-Loop Review (Learning Loop):")
    eval_record = db_manager.save_run_evaluation(
        id=f"eval_{uuid.uuid4().hex[:8]}",
        execution_id=execution.id,
        workflow_id=workflow.id,
        rating=5,
        feedback_notes="All security checks completed properly before CEO signoff.",
        lessons_extracted="Always cascade QA coverage notes directly into security reviewer prompts."
    )
    print(f"   • Evaluation Saved ID: {eval_record.id}")
    print(f"   • Rating: {eval_record.rating}/5 ⭐")
    print(f"   • Lesson Extracted: '{eval_record.lessons_extracted}'")

    print("\n" + "=" * 70)
    print("✨ Live Demo Finished Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    run_live_workflow_demo()
