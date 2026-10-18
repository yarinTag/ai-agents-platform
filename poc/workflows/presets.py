"""
Workflow Template & Prompt-Based DAG Preset Generator.
Extracted from API layer to keep routers concise and domain-focused.
"""

from typing import List, Optional, Dict, Any, Tuple
import json
import uuid
from workflows.parser import WorkflowParser


def build_generated_workflow_definition(
    db: Any,
    prompt_raw: Optional[str] = None,
    template_type: Optional[str] = None,
    name: Optional[str] = None,
    channel_provider: Optional[str] = None,
    channel_id: Optional[str] = None,
    allowed_mcps: Optional[List[str]] = None,
    skills: Optional[List[Dict[str, Any]]] = None,
    target_repo: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an intelligent, production-ready workflow definition with steps,
    agent assignments, and dependencies, restricted strictly to configured MCPs.
    """
    tmpl = (template_type or "").lower()
    prompt = (prompt_raw or "").lower()
    wf_id = f"wf_{uuid.uuid4().hex[:10]}"

    installed_connectors = db.list_mcp_connectors()
    installed_mcp_ids = [c.id for c in installed_connectors]
    if not installed_mcp_ids:
        installed_mcp_ids = ["telegram", "github", "trello", "slack"]

    if allowed_mcps and len(allowed_mcps) > 0:
        effective_mcps = [
            m for m in allowed_mcps
            if m in installed_mcp_ids or m in ["telegram", "github", "trello", "slack"]
        ]
    else:
        effective_mcps = installed_mcp_ids

    workflow_skills = list(skills or [])
    attached_skill_ids = [s.get("id") for s in workflow_skills if isinstance(s, dict) and s.get("id")]

    is_telegram = (
        channel_provider == "telegram"
        or "telegram" in prompt
        or "טלגרם" in prompt
        or "ערוץ" in prompt
    )
    is_github_repo = (
        "github" in prompt
        or "גיטאהב" in prompt
        or "repo" in prompt
        or "ריפו" in prompt
        or "diff" in prompt
        or "שינויים" in prompt
        or tmpl == "telegram_github_daily_report"
    )
    is_daily_report = (
        "daily" in prompt
        or "דוח יומי" in prompt
        or "יומי" in prompt
        or "report" in prompt
        or "digest" in prompt
    )

    if (is_telegram and is_github_repo) or tmpl == "telegram_github_daily_report":
        repo = target_repo or "yarinTag/ai-agents-platform"
        wf_name = name or f"Telegram Trigger ➔ GitHub Daily Repo Changes ({repo})"
        desc = f"Triggered on Telegram channel message, inspects commits & diffs on repository '{repo}' via GitHub MCP, synthesizes daily changes digest, and publishes the report back to Telegram."
        default_channel = channel_id or ("Hermes_test" if "telegram" in effective_mcps else "general")
        provider = "telegram"

        if not workflow_skills:
            workflow_skills = [{
                "id": "daily-git-reporter",
                "name": "Daily Git Reporter",
                "source": "git",
                "location": f"https://github.com/{repo}.git",
                "description": "Extracts git commits & pull requests and drafts a structured daily digest"
            }]
            attached_skill_ids = ["daily-git-reporter"]

        steps = [
            {
                "key": "telegram_message_ingest",
                "name": "Telegram Channel Ingestion & Intent Parse",
                "agent_id": "software-architect",
                "prompt_template": f"Ingest message trigger from Telegram channel '{default_channel}'. Extract target repository parameter (default: '{repo}') and time range (last 24h).",
                "depends_on": [],
                "timeout_seconds": 180,
                "mcp_servers": ["telegram"] if "telegram" in effective_mcps else [],
                "skills": []
            },
            {
                "key": "github_fetch_diff",
                "name": "GitHub Repo Changes & Diff Extraction",
                "agent_id": "backend-developer",
                "prompt_template": f"Using GitHub MCP for repository '{repo}', fetch git diff, merged PRs, and commit logs since yesterday. Include modified file summaries.",
                "depends_on": ["telegram_message_ingest"],
                "timeout_seconds": 300,
                "mcp_servers": ["github"] if "github" in effective_mcps else [],
                "skills": attached_skill_ids[:1]
            },
            {
                "key": "synthesize_daily_digest",
                "name": "Synthesize Executive Daily Changes Digest",
                "agent_id": "qa-test-engineer",
                "prompt_template": "Analyze the git changes from {{github_fetch_diff.output}}. Generate a clean markdown daily digest grouped into: 🚀 Features, 🐛 Bug Fixes, 🔒 Security, and 📊 Summary.",
                "depends_on": ["github_fetch_diff"],
                "timeout_seconds": 240,
                "mcp_servers": [],
                "skills": attached_skill_ids
            },
            {
                "key": "telegram_dispatch_report",
                "name": "Dispatch Daily Report to Telegram Channel",
                "agent_id": "ceo-orchestrator",
                "prompt_template": f"Format and send the completed daily changes digest from {{{{synthesize_daily_digest.output}}}} to Telegram channel '{default_channel}' with completion status.",
                "depends_on": ["synthesize_daily_digest"],
                "timeout_seconds": 180,
                "mcp_servers": ["telegram"] if "telegram" in effective_mcps else [],
                "skills": []
            }
        ]

    elif ("branch" in prompt or "בראנץ" in prompt or ("שינויים" in prompt and ("פרויקט" in prompt or "פרוייקט" in prompt or "repo" in prompt)) or tmpl == "branch_diff_inspector"):
        repo_name = target_repo or "ai-agents-platform"
        wf_name = name or f"Git Branch & Code Changes Inspector ({repo_name})"
        desc = f"Inspects active git branch, checks staged/unstaged changes and recent commits on '{repo_name}', analyzes diffs, and synthesizes a structured changes report."
        default_channel = channel_id or ("Hermes_test" if channel_provider == "telegram" or "telegram" in effective_mcps else "general")
        provider = channel_provider or ("telegram" if "telegram" in effective_mcps else "slack")

        steps = [
            {
                "key": "branch_status_inspect",
                "name": "Git Branch & Working Tree Inspection",
                "agent_id": "software-architect",
                "prompt_template": f"In project repository '{repo_name}', inspect the active branch name, git status, and last 5 commits (`git branch --show-current`, `git status -s`, `git log -n 5 --oneline`). Output the branch name and raw changes.",
                "depends_on": [],
                "timeout_seconds": 240,
                "mcp_servers": ["github"] if "github" in effective_mcps else [],
                "skills": attached_skill_ids[:1]
            },
            {
                "key": "diff_impact_analysis",
                "name": "Diff & Impact Analysis",
                "agent_id": "backend-developer",
                "prompt_template": "Analyze the git changes and status from {{branch_status_inspect.output}}. Detail what code changes were introduced, modified files, potential risks, and architectural impact.",
                "depends_on": ["branch_status_inspect"],
                "timeout_seconds": 300,
                "mcp_servers": ["github"] if "github" in effective_mcps else [],
                "skills": attached_skill_ids
            },
            {
                "key": "synthesize_git_report",
                "name": "Synthesize & Dispatch Changes Report",
                "agent_id": "ceo-orchestrator",
                "prompt_template": f"Synthesize findings from {{{{diff_impact_analysis.output}}}} into a clean markdown executive report with: 🌿 Active Branch, 📝 Recent Commits, 🔍 Modified Files, and 🚀 Summary. Prepare report for channel '{default_channel}'.",
                "depends_on": ["diff_impact_analysis"],
                "timeout_seconds": 180,
                "mcp_servers": ["telegram"] if "telegram" in effective_mcps else [],
                "skills": []
            }
        ]

    elif tmpl == "github_pr_review" or ("pr" in prompt or "review" in prompt):
        wf_name = name or "GitHub PR Review & Autonomous Gate"
        desc = "Autonomous pipeline that inspects pull requests, validates architecture contracts, runs QA tests, and alerts the team."
        steps = [
            {
                "key": "pr_triage",
                "name": "PR Diff & Architecture Analysis",
                "agent_id": "software-architect",
                "prompt_template": "Inspect incoming PR {{pr_id}} on repository {{repo}}. Review architectural adherence, API contracts, and code diff.",
                "depends_on": [],
                "timeout_seconds": 300,
                "mcp_servers": ["github"] if "github" in effective_mcps else [],
                "skills": attached_skill_ids[:1]
            },
            {
                "key": "qa_validation",
                "name": "Automated Test Suite & Regression Check",
                "agent_id": "qa-test-engineer",
                "prompt_template": "Execute test suites and verify 100% pass rate for PR {{pr_id}} changes: {{pr_triage.output}}.",
                "depends_on": ["pr_triage"],
                "timeout_seconds": 300,
                "mcp_servers": [],
                "skills": attached_skill_ids
            },
            {
                "key": "security_audit",
                "name": "Secrets & Security Release Audit",
                "agent_id": "release-security-reviewer",
                "prompt_template": "Perform secrets scan, CVE check, and readiness gate audit for PR {{pr_id}}.",
                "depends_on": ["qa_validation"],
                "timeout_seconds": 240,
                "mcp_servers": [],
                "skills": []
            },
        ]
        default_channel = channel_id or ("Hermes_test" if channel_provider == "telegram" else "#pr-review")
        provider = channel_provider or ("telegram" if "telegram" in prompt else "slack")

    elif tmpl == "incident_triage" or ("incident" in prompt or "error" in prompt or "alert" in prompt or "bug" in prompt):
        wf_name = name or "Incident Triage & Rapid Hotfix"
        desc = "High-priority incident response pipeline analyzing stack traces, generating hotfix proposals, and alerting on-call."
        steps = [
            {
                "key": "error_analysis",
                "name": "Crash Dump & Error Log Triage",
                "agent_id": "software-architect",
                "prompt_template": "Analyze error report {{incident_id}}: {{error_log}}. Identify root cause in application services.",
                "depends_on": [],
                "timeout_seconds": 200,
                "mcp_servers": [],
                "skills": attached_skill_ids[:1]
            },
            {
                "key": "hotfix_draft",
                "name": "Implement Hotfix Patch",
                "agent_id": "backend-developer",
                "prompt_template": "Draft code patch to resolve root cause identified in {{error_analysis.output}}.",
                "depends_on": ["error_analysis"],
                "timeout_seconds": 360,
                "mcp_servers": ["github"] if "github" in effective_mcps else [],
                "skills": attached_skill_ids
            },
            {
                "key": "security_check",
                "name": "Verify Hotfix Security",
                "agent_id": "release-security-reviewer",
                "prompt_template": "Validate hotfix patch for security implications and confirm deployment readiness.",
                "depends_on": ["hotfix_draft"],
                "timeout_seconds": 180,
                "mcp_servers": [],
                "skills": []
            },
        ]
        default_channel = channel_id or ("Hermes_test" if channel_provider == "telegram" else "#alerts")
        provider = channel_provider or ("telegram" if "telegram" in prompt else "slack")

    elif tmpl == "daily_health_check" or (is_daily_report and ("health" in prompt or "metric" in prompt)):
        wf_name = name or "Daily System Health & Metrics Digest"
        desc = "Scheduled diagnostic routine checking system uptime, API response times, and agent task throughput."
        steps = [
            {
                "key": "run_diagnostics",
                "name": "System Health & Benchmark Probing",
                "agent_id": "qa-test-engineer",
                "prompt_template": "Run health ping checks across all MCP connectors and backend endpoints.",
                "depends_on": [],
                "timeout_seconds": 180,
                "mcp_servers": effective_mcps[:2],
                "skills": []
            },
            {
                "key": "compile_digest",
                "name": "Executive Status Digest",
                "agent_id": "ceo-orchestrator",
                "prompt_template": "Synthesize diagnostic findings from {{run_diagnostics.output}} into an executive status digest.",
                "depends_on": ["run_diagnostics"],
                "timeout_seconds": 240,
                "mcp_servers": ["telegram"] if "telegram" in effective_mcps else [],
                "skills": attached_skill_ids
            },
        ]
        default_channel = channel_id or ("Hermes_test" if channel_provider == "telegram" else "#workflows-feed")
        provider = channel_provider or ("telegram" if "telegram" in prompt else "slack")

    else:
        wf_name = name or ("Autonomous Pipeline: " + (prompt_raw[:30] + "..." if prompt_raw and len(prompt_raw) > 30 else "Custom Task"))
        desc = prompt_raw or "Custom multi-agent orchestration workflow"
        steps = [
            {
                "key": "step_plan",
                "name": "Planning & Strategy",
                "agent_id": "software-architect",
                "prompt_template": f"Plan execution for requirement: {prompt_raw or 'Define workflow deliverables'}.",
                "depends_on": [],
                "timeout_seconds": 300,
                "mcp_servers": effective_mcps[:1],
                "skills": attached_skill_ids[:1]
            },
            {
                "key": "step_execute",
                "name": "Core Implementation",
                "agent_id": "backend-developer",
                "prompt_template": "Implement solution based on plan: {{step_plan.output}}.",
                "depends_on": ["step_plan"],
                "timeout_seconds": 360,
                "mcp_servers": effective_mcps[:2],
                "skills": attached_skill_ids
            },
            {
                "key": "step_qa",
                "name": "Quality & Verification Gate",
                "agent_id": "qa-test-engineer",
                "prompt_template": "Verify output and compliance of implementation: {{step_execute.output}}.",
                "depends_on": ["step_execute"],
                "timeout_seconds": 240,
                "mcp_servers": [],
                "skills": []
            },
        ]
        default_channel = channel_id or ("Hermes_test" if channel_provider == "telegram" else "#general")
        provider = channel_provider or ("telegram" if "telegram" in prompt else "slack")

    for s in steps:
        s["mcp_servers"] = [m for m in s.get("mcp_servers", []) if m in effective_mcps]

    metadata = {}
    if default_channel and provider:
        metadata["channel_binding"] = {
            "provider": provider,
            "connector_id": provider,
            "channel_id": default_channel,
            "channel_name": default_channel,
            "trigger_enabled": True,
            "notify_mode": "ON_COMPLETE",
            "message_template": f"🚀 Workflow {wf_name} finished step execution with status: {{{{status}}}}",
        }

    raw_dict = {
        "id": wf_id,
        "name": wf_name,
        "description": desc,
        "department_id": None,
        "mcp_servers": effective_mcps,
        "skills": workflow_skills,
        "steps": steps,
        "cron_expression": "0 9 * * *" if (tmpl == "daily_health_check" or (is_daily_report and not is_telegram)) else None,
        "webhook_enabled": True,
        "metadata": metadata,
    }

    def_json = json.dumps(raw_dict, indent=2)
    def_yaml = WorkflowParser.json_to_yaml(def_json)

    return {
        "id": wf_id,
        "name": wf_name,
        "description": desc,
        "definition_json": def_json,
        "definition_yaml": def_yaml,
        "steps_count": len(steps),
    }
