"""
Workflows and Webhooks API router.
Supports:
- CRUD for workflows (JSON / YAML formats)
- Workflow execution (manual trigger)
- Incoming Webhooks with webhook token lookup
- Execution inspection with full token usage and cost accounting
- Human evaluations and lessons learned
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Header, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

import json
import logging

from ..dependencies import get_db_manager, get_workflow_engine, DatabaseManager, AgentConfig, AgentRole
from workflows.parser import WorkflowParser, WorkflowDefinition
from workflows.engine import WorkflowEngine, BudgetExceededError, MCPGovernanceViolationError

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: bool = True


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class ChannelBindingDto(BaseModel):
    provider: str = Field(..., description="slack or telegram")
    connector_id: Optional[str] = "slack"
    channel_id: str = Field(..., min_length=1, description="e.g. #pr-review or @channel_bot")
    channel_name: Optional[str] = None
    trigger_enabled: bool = True
    notify_mode: str = Field("ON_COMPLETE", description="ON_COMPLETE, ON_FAILURE, ALWAYS, NONE")
    message_template: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_json: str
    definition_yaml: Optional[str] = None
    webhook_enabled: bool
    webhook_token: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: bool
    channel_binding: Optional[Dict[str, Any]] = None
    runner_agent_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    trigger_type: str
    trigger_payload: Optional[str] = None
    status: str
    department_id: Optional[str] = None
    sandbox_path: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class EvaluationRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_notes: Optional[str] = None
    lessons_extracted: Optional[str] = None


class WorkflowGenerateRequest(BaseModel):
    prompt: Optional[str] = None
    template_type: Optional[str] = None
    name: Optional[str] = None
    channel_provider: Optional[str] = None
    channel_id: Optional[str] = None
    allowed_mcps: Optional[List[str]] = None
    skills: Optional[List[Dict[str, Any]]] = None
    target_repo: Optional[str] = None


class WorkflowGenerateResponse(BaseModel):
    id: str
    name: str
    description: str
    definition_json: str
    definition_yaml: str
    steps_count: int


class WorkflowFormatConvertRequest(BaseModel):
    yaml_content: Optional[str] = None
    json_content: Optional[str] = None


class WorkflowFormatConvertResponse(BaseModel):
    yaml_content: str
    json_content: str


@router.post("/generate", response_model=WorkflowGenerateResponse)
def generate_workflow_definition(
    req: WorkflowGenerateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Generate an intelligent, production-ready workflow definition with steps,
    agent assignments, and dependencies, restricted strictly to configured MCPs,
    incorporating attached skills and auto-generating the complete YAML file.
    """
    import json
    tmpl = (req.template_type or "").lower()
    prompt = (req.prompt or "").lower()
    wf_id = f"wf_{uuid.uuid4().hex[:10]}"

    # 1. Discover installed MCP connectors and enforce configured MCP scope
    installed_connectors = db.list_mcp_connectors()
    installed_mcp_ids = [c.id for c in installed_connectors]
    if not installed_mcp_ids:
        # Default active servers if none persisted yet in DB
        installed_mcp_ids = ["telegram", "github", "trello", "slack"]

    if req.allowed_mcps and len(req.allowed_mcps) > 0:
        effective_mcps = [m for m in req.allowed_mcps if m in installed_mcp_ids or m in ["telegram", "github", "trello", "slack"]]
    else:
        effective_mcps = installed_mcp_ids

    # 2. Extract attached skills
    workflow_skills = req.skills or []
    attached_skill_ids = [s.get("id") for s in workflow_skills if isinstance(s, dict) and s.get("id")]

    # Detect Telegram Trigger + GitHub Daily Report requirement
    is_telegram = (
        req.channel_provider == "telegram"
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
        target_repo = req.target_repo or "yarinTag/ai-agents-platform"
        wf_name = req.name or f"Telegram Trigger ➔ GitHub Daily Repo Changes ({target_repo})"
        desc = f"Triggered on Telegram channel message, inspects commits & diffs on repository '{target_repo}' via GitHub MCP, synthesizes daily changes digest, and publishes the report back to Telegram."
        default_channel = req.channel_id or ("Hermes_test" if "telegram" in effective_mcps else "general")
        channel_provider = "telegram"

        # Provide a default git-diff-reporter skill if none attached
        if not workflow_skills:
            workflow_skills = [{
                "id": "daily-git-reporter",
                "name": "Daily Git Reporter",
                "source": "git",
                "location": f"https://github.com/{target_repo}.git",
                "description": "Extracts git commits & pull requests and drafts a structured daily digest"
            }]
            attached_skill_ids = ["daily-git-reporter"]

        steps = [
            {
                "key": "telegram_message_ingest",
                "name": "Telegram Channel Ingestion & Intent Parse",
                "agent_id": "software-architect",
                "prompt_template": f"Ingest message trigger from Telegram channel '{default_channel}'. Extract target repository parameter (default: '{target_repo}') and time range (last 24h).",
                "depends_on": [],
                "timeout_seconds": 180,
                "mcp_servers": ["telegram"] if "telegram" in effective_mcps else [],
                "skills": []
            },
            {
                "key": "github_fetch_diff",
                "name": "GitHub Repo Changes & Diff Extraction",
                "agent_id": "backend-developer",
                "prompt_template": f"Using GitHub MCP for repository '{target_repo}', fetch git diff, merged PRs, and commit logs since yesterday. Include modified file summaries.",
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
        repo_name = req.target_repo or "ai-agents-platform"
        wf_name = req.name or f"Git Branch & Code Changes Inspector ({repo_name})"
        desc = f"Inspects active git branch, checks staged/unstaged changes and recent commits on '{repo_name}', analyzes diffs, and synthesizes a structured changes report."
        default_channel = req.channel_id or ("Hermes_test" if req.channel_provider == "telegram" or "telegram" in effective_mcps else "general")
        channel_provider = req.channel_provider or ("telegram" if "telegram" in effective_mcps else "slack")

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
        wf_name = req.name or "GitHub PR Review & Autonomous Gate"
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
        default_channel = req.channel_id or ("Hermes_test" if req.channel_provider == "telegram" else "#pr-review")
        channel_provider = req.channel_provider or ("telegram" if "telegram" in prompt else "slack")

    elif tmpl == "incident_triage" or ("incident" in prompt or "error" in prompt or "alert" in prompt or "bug" in prompt):
        wf_name = req.name or "Incident Triage & Rapid Hotfix"
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
        default_channel = req.channel_id or ("Hermes_test" if req.channel_provider == "telegram" else "#alerts")
        channel_provider = req.channel_provider or ("telegram" if "telegram" in prompt else "slack")

    elif tmpl == "daily_health_check" or (is_daily_report and ("health" in prompt or "metric" in prompt)):
        wf_name = req.name or "Daily System Health & Metrics Digest"
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
        default_channel = req.channel_id or ("Hermes_test" if req.channel_provider == "telegram" else "#workflows-feed")
        channel_provider = req.channel_provider or ("telegram" if "telegram" in prompt else "slack")

    else:
        wf_name = req.name or ("Autonomous Pipeline: " + (req.prompt[:30] + "..." if req.prompt and len(req.prompt) > 30 else "Custom Task"))
        desc = req.prompt or "Custom multi-agent orchestration workflow"
        steps = [
            {
                "key": "step_plan",
                "name": "Planning & Strategy",
                "agent_id": "software-architect",
                "prompt_template": f"Plan execution for requirement: {req.prompt or 'Define workflow deliverables'}.",
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
        default_channel = req.channel_id or ("Hermes_test" if req.channel_provider == "telegram" else "#general")
        channel_provider = req.channel_provider or ("telegram" if "telegram" in prompt else "slack")

    # Strictly filter all step mcp_servers to only effective_mcps
    for s in steps:
        s["mcp_servers"] = [m for m in s.get("mcp_servers", []) if m in effective_mcps]

    metadata = {}
    if default_channel and channel_provider:
        metadata["channel_binding"] = {
            "provider": channel_provider,
            "connector_id": channel_provider,
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

    return WorkflowGenerateResponse(
        id=wf_id,
        name=wf_name,
        description=desc,
        definition_json=def_json,
        definition_yaml=def_yaml,
        steps_count=len(steps),
    )


@router.post("/convert-format", response_model=WorkflowFormatConvertResponse)
def convert_format(req: WorkflowFormatConvertRequest):
    """Convert bidirectionally between YAML and JSON workflow definitions."""
    if req.yaml_content:
        try:
            json_str = WorkflowParser.yaml_to_json(req.yaml_content)
            return WorkflowFormatConvertResponse(yaml_content=req.yaml_content, json_content=json_str)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    elif req.json_content:
        try:
            yaml_str = WorkflowParser.json_to_yaml(req.json_content)
            return WorkflowFormatConvertResponse(yaml_content=yaml_str, json_content=req.json_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    raise HTTPException(status_code=400, detail="Either yaml_content or json_content is required")


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    req: WorkflowCreateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new workflow from YAML or JSON definition."""
    def_json = req.definition_json
    if not def_json and req.definition_yaml:
        try:
            def_json = WorkflowParser.yaml_to_json(req.definition_yaml)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML definition: {e}")
    elif not def_json:
        raise HTTPException(status_code=400, detail="Either definition_yaml or definition_json is required")

    wf_id = f"wf_{uuid.uuid4().hex[:10]}"
    runner_agent_id = f"wf-agent-{wf_id}"

    # Extract metadata, MCPs, skills, steps, and channel info for the dedicated runner agent
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
    cron = req.cron_expression or def_dict.get("trigger", {}).get("cron_expression") or def_dict.get("trigger", {}).get("cron") or "None"

    # Build prompt for background automation agent
    step_desc = "\n".join(f"- Step {i+1} [{s.get('id', 'step')}]: {s.get('name', 'Action')} ({s.get('type', 'AGENT')})" for i, s in enumerate(steps)) or "- Multi-step automated DAG pipeline"
    system_prompt = (
        f"You are the autonomous workflow execution agent for '{req.name}' (Workflow ID: {wf_id}).\n"
        f"Trigger schedule: Cron [{cron}], Channel trigger [{channel_info}].\n"
        f"Assigned MCP scope: {', '.join(mcps) if mcps else 'All platform MCPs'}.\n"
        f"Connected skills: {', '.join(skill_names) if skill_names else 'Standard'}.\n"
        f"Pipeline stages:\n{step_desc}\n\n"
        f"Execution rules:\n"
        f"1. You run automatically in background cloud workers on schedule or when triggered via the channel.\n"
        f"2. You are completely detached from the 2D pixel office simulation canvas and do not occupy an office desk.\n"
        f"3. Strictly enforce the assigned MCP scope and skills during DAG execution."
    )

    # Save dedicated workflow automation agent
    try:
        runner_agent = AgentConfig(
            id=runner_agent_id,
            name=f"{req.name} Runner",
            description=f"Autonomous workflow agent for '{req.name}'. Runs periodically or via channel '{channel_info}'. Detached from office floor.",
            system_prompt=system_prompt,
            skills=skill_names,
            department="Workflow Automations",
            role_type="WORKFLOW_AUTOMATION",
            is_workflow_agent=True,
            workflow_id=wf_id,
            mcp_permissions=mcps,
            allowed_tools=["*"],
            avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={wf_id}",
            temperature=0.3
        )
        db.save_agent(runner_agent)
    except Exception as e:
        logger.warning(f"Could not auto-create runner agent: {e}")

    # Inject runner agent ID and status into definition
    def_dict["runner_agent_id"] = runner_agent_id
    def_dict["is_workflow_agent"] = True
    def_json = json.dumps(def_dict, indent=2)

    wf = db.create_workflow(
        id=wf_id,
        name=req.name,
        definition_json=def_json,
        department_id=req.department_id,
        description=req.description,
        cron_expression=req.cron_expression,
        webhook_enabled=req.webhook_enabled
    )

    yaml_repr = None
    try:
        yaml_repr = WorkflowParser.json_to_yaml(wf.definition_json)
    except Exception:
        pass

    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        department_id=wf.department_id,
        definition_json=wf.definition_json,
        definition_yaml=yaml_repr,
        webhook_enabled=wf.webhook_enabled,
        webhook_token=wf.webhook_token,
        cron_expression=wf.cron_expression,
        is_active=wf.is_active,
        runner_agent_id=runner_agent_id,
        created_at=wf.created_at,
        updated_at=wf.updated_at
    )


def _workflow_to_response(wf) -> WorkflowResponse:
    y_repr = None
    try:
        y_repr = WorkflowParser.json_to_yaml(wf.definition_json)
    except Exception:
        pass

    channel_binding = None
    runner_agent_id = None
    try:
        import json
        dj = json.loads(wf.definition_json)
        channel_binding = dj.get("metadata", {}).get("channel_binding")
        runner_agent_id = dj.get("runner_agent_id") or f"wf-agent-{wf.id}"
    except Exception:
        runner_agent_id = f"wf-agent-{wf.id}"

    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        department_id=wf.department_id,
        definition_json=wf.definition_json,
        definition_yaml=y_repr,
        webhook_enabled=wf.webhook_enabled,
        webhook_token=wf.webhook_token,
        cron_expression=wf.cron_expression,
        is_active=wf.is_active,
        channel_binding=channel_binding,
        runner_agent_id=runner_agent_id,
        created_at=wf.created_at,
        updated_at=wf.updated_at
    )


@router.get("", response_model=List[WorkflowResponse])
@router.get("/", response_model=List[WorkflowResponse])
def list_workflows(
    department_id: Optional[str] = None,
    active_only: bool = False,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List workflows."""
    workflows = db.list_workflows(department_id=department_id, active_only=active_only)
    return [_workflow_to_response(wf) for wf in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get workflow by ID."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_to_response(wf)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    req: WorkflowUpdateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update workflow settings or definition."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    def_json = req.definition_json
    if not def_json and req.definition_yaml:
        try:
            def_json = WorkflowParser.yaml_to_json(req.definition_yaml)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML definition: {e}")

    updated = db.update_workflow(
        id=workflow_id,
        name=req.name,
        description=req.description,
        department_id=req.department_id,
        definition_json=def_json,
        cron_expression=req.cron_expression,
        webhook_enabled=req.webhook_enabled,
        is_active=req.is_active
    )
    return _workflow_to_response(updated)


@router.post("/{workflow_id}/channel-binding", response_model=WorkflowResponse)
def bind_workflow_channel(
    workflow_id: str,
    req: ChannelBindingDto,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Bind a communication channel (Slack / Telegram) to a workflow.
    Configures incoming trigger permissions and outgoing execution reports.
    """
    import json
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        def_dict = json.loads(wf.definition_json or "{}")
    except Exception:
        def_dict = {"id": wf.id, "name": wf.name, "steps": []}

    metadata = def_dict.get("metadata") or {}
    metadata["channel_binding"] = req.model_dump()
    def_dict["metadata"] = metadata

    new_def_json = json.dumps(def_dict, indent=2)
    updated = db.update_workflow(id=workflow_id, definition_json=new_def_json)
    return _workflow_to_response(updated)


@router.delete("/{workflow_id}/channel-binding", response_model=WorkflowResponse)
def unbind_workflow_channel(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Remove communication channel binding from a workflow."""
    import json
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        def_dict = json.loads(wf.definition_json or "{}")
    except Exception:
        def_dict = {}

    if "metadata" in def_dict and "channel_binding" in def_dict["metadata"]:
        del def_dict["metadata"]["channel_binding"]

    new_def_json = json.dumps(def_dict, indent=2)
    updated = db.update_workflow(id=workflow_id, definition_json=new_def_json)
    return _workflow_to_response(updated)


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Delete a workflow."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Clean up associated runner agent
    try:
        db.delete_agent(f"wf-agent-{workflow_id}")
    except Exception:
        pass
    try:
        with db._get_connection() as conn:
            conn.execute("DELETE FROM agents WHERE workflow_id = ? OR id = ?", (workflow_id, f"wf-agent-{workflow_id}"))
            conn.commit()
    except Exception:
        pass

    db.delete_workflow(workflow_id)
    return {"status": "success", "message": f"Workflow {workflow_id} deleted"}


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(
    workflow_id: str,
    payload: Optional[Dict[str, Any]] = None,
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """Manually trigger a workflow execution."""
    try:
        execution = engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_type="MANUAL",
            trigger_payload=payload
        )
        return WorkflowExecutionResponse(
            id=execution.id,
            workflow_id=execution.workflow_id,
            trigger_type=execution.trigger_type,
            trigger_payload=execution.trigger_payload,
            status=execution.status,
            department_id=execution.department_id,
            sandbox_path=execution.sandbox_path,
            total_input_tokens=execution.total_input_tokens,
            total_output_tokens=execution.total_output_tokens,
            total_cost_usd=execution.total_cost_usd,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            error_message=execution.error_message,
            created_at=execution.created_at
        )
    except MCPGovernanceViolationError as mcp_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MCP Governance Violation: {str(mcp_err)}"
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Budget limit reached for department '{be.department_id}': {str(be)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/{webhook_token}", response_model=WorkflowExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook(
    webhook_token: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """
    Incoming webhook endpoint for a specific workflow.
    Validates token, extracts JSON body payload, and launches workflow execution.
    """
    wf = db.get_workflow_by_webhook_token(webhook_token)
    if not wf:
        raise HTTPException(status_code=404, detail="Invalid or inactive webhook token")

    body_data = {}
    try:
        body_data = await request.json()
    except Exception:
        pass

    try:
        execution = engine.execute_workflow(
            workflow_id=wf.id,
            trigger_type="WEBHOOK",
            trigger_payload=body_data
        )
        return WorkflowExecutionResponse(
            id=execution.id,
            workflow_id=execution.workflow_id,
            trigger_type=execution.trigger_type,
            trigger_payload=execution.trigger_payload,
            status=execution.status,
            department_id=execution.department_id,
            sandbox_path=execution.sandbox_path,
            total_input_tokens=execution.total_input_tokens,
            total_output_tokens=execution.total_output_tokens,
            total_cost_usd=execution.total_cost_usd,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            error_message=execution.error_message,
            created_at=execution.created_at
        )
    except MCPGovernanceViolationError as mcp_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MCP Governance Violation: {str(mcp_err)}"
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Department budget exceeded: {str(be)}"
        )


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution_status(
    execution_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get full status and token/cost metrics of a workflow execution."""
    exec_record = db.get_workflow_execution(execution_id)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")

    return WorkflowExecutionResponse(
        id=exec_record.id,
        workflow_id=exec_record.workflow_id,
        trigger_type=exec_record.trigger_type,
        trigger_payload=exec_record.trigger_payload,
        status=exec_record.status,
        department_id=exec_record.department_id,
        sandbox_path=exec_record.sandbox_path,
        total_input_tokens=exec_record.total_input_tokens,
        total_output_tokens=exec_record.total_output_tokens,
        total_cost_usd=exec_record.total_cost_usd,
        started_at=exec_record.started_at,
        completed_at=exec_record.completed_at,
        error_message=exec_record.error_message,
        created_at=exec_record.created_at
    )


@router.post("/executions/{execution_id}/evaluate", status_code=status.HTTP_201_CREATED)
def evaluate_execution(
    execution_id: str,
    req: EvaluationRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Submit human review, rating, and lessons learned for self-improvement."""
    exec_record = db.get_workflow_execution(execution_id)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")

    eval_id = f"eval_{uuid.uuid4().hex[:10]}"
    db.save_run_evaluation(
        id=eval_id,
        execution_id=execution_id,
        workflow_id=exec_record.workflow_id,
        rating=req.rating,
        feedback_notes=req.feedback_notes,
        lessons_extracted=req.lessons_extracted
    )
    return {"status": "SUCCESS", "evaluation_id": eval_id}
