"""Provider selection, environment preparation and CLI command construction."""

import logging
import os
import sys
from typing import Dict, List, Optional
from config import AgentConfig, ProjectConfig
import runtime_providers as providers
from .services import RuntimeServices

logger = logging.getLogger(__name__)
RUNTIME_PROVIDER_SETTING_KEY = providers.SETTING_PROVIDER
RUNTIME_GATEWAY_URL_SETTING_KEY = providers.SETTING_GATEWAY_URL
# Workspace file tools without shell access; the default for workflow runners.
SAFE_WORKSPACE_TOOLS = ("AskUserQuestion", "Edit", "Glob", "Grep", "Read", "Write")


class RuntimeCommandBuilder:
    def __init__(self, services: RuntimeServices):
        self.services = services

    def organization_settings(self, agent_config):
        from storage.runtime_settings import OrganizationRuntimeSettings
        return OrganizationRuntimeSettings(self.services.database(), getattr(agent_config, 'organization_id', None))

    def resolve_runtime_provider(self, agent_config: Optional[AgentConfig] = None) -> str:
        """Resolve agent override/model owner, then the organization's default.

        Host provider defaults, global keys and legacy CLI auth never select an
        organization's execution credential.
        """
        from .direct_config import DIRECT_PROVIDERS, provider_for_model
        settings = self.organization_settings(agent_config)
        selected = getattr(agent_config, 'runtime_provider', None)
        if not selected and agent_config:
            selected = provider_for_model(getattr(agent_config, 'model', None))
        selected = selected or settings.get_setting(RUNTIME_PROVIDER_SETTING_KEY)
        if selected not in DIRECT_PROVIDERS:
            raise ValueError('Configure a Direct API provider for this organization.')
        if not settings.has_credential(selected):
            raise ValueError('This organization has no API key for the selected provider.')
        return selected

    def _build_claude_env(
        self,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> Dict[str, str]:
        """Build environment variables for Claude Code subprocess."""
        provider_id = self.resolve_runtime_provider(agent_config)

        from .env_hygiene import strip_secrets
        # Only this organization's selected key reaches the HTTP worker.
        # Tool environments remove it and the broker context.
        env = strip_secrets(os.environ.copy())
        for name in tuple(env):
            if name.startswith(('ANTHROPIC_', 'PLATFORM_PROVIDER_', 'PLATFORM_CONNECTOR_')) or name in {
                'PLATFORM_SECRETS_KEY', 'NVIDIA_API_KEY', 'NVIDIA_NIM_API_KEY', 'OPENAI_API_KEY',
                'OPENROUTER_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN'}:
                env.pop(name, None)
        env['PLATFORM_RUNTIME_PROVIDER'] = provider_id
        from pathlib import Path
        db = self.services.database()
        organization_id = getattr(agent_config, 'organization_id', None)
        env['PLATFORM_PROVIDER_DB'] = str(Path(db.db_path).resolve())
        env['PLATFORM_PROVIDER_ORGANIZATION'] = organization_id
        env['PLATFORM_PROVIDER_DEPARTMENT'] = getattr(agent_config, 'department_id', None) or ''
        from .direct_config import DIRECT_PROVIDERS
        settings = self.organization_settings(agent_config)
        version = settings.credential_version(provider_id)
        key = settings.resolve_credential(provider_id)
        if version is None or not key or settings.credential_version(provider_id) != version:
            raise ValueError('The organization credential changed. Start the run again.')
        env[DIRECT_PROVIDERS[provider_id][1]] = key
        env['PLATFORM_PROVIDER_VERSION'] = str(version)
        env['PLATFORM_API_SESSION_DIR'] = str(Path(db.db_path).resolve().parent / 'runtime_sessions')
        env['PLATFORM_API_SESSION_SCOPE'] = organization_id + ':' + str(agent_config.id)
        env.update({
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": os.getenv("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "40000"),
            "DISABLE_AUTOUPDATER": "1",
            "DISABLE_FEEDBACK_COMMAND": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "DISABLE_TELEMETRY": "1",
            "TERM": "dumb",
            "PYTHONIOENCODING": "utf-8"
        })
        poc_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{poc_dir}:{existing_pythonpath}" if existing_pythonpath else poc_dir
        if run_id:
            env["PLATFORM_PARENT_TASK_ID"] = run_id
        if project_id:
            env["PLATFORM_PROJECT_ID"] = project_id
        return env

    def _resolve_working_directory(
        self,
        project_config: Optional[ProjectConfig],
        agent_config: Optional[AgentConfig]
    ) -> str:
        """Resolve the run's working directory inside an approved workspace root.

        Paths outside PLATFORM_WORKSPACE_ROOTS fail the run (WorkspacePolicyError)
        instead of silently falling back; runs without a path use the platform's
        default workspace, never the server's own working directory.
        """
        from .workspace_policy import resolve_workspace
        candidate = None
        if project_config and getattr(project_config, "working_directory", None) and project_config.working_directory.strip():
            candidate = project_config.working_directory.strip()
        elif agent_config and getattr(agent_config, "repo_path", None) and agent_config.repo_path.strip():
            candidate = agent_config.repo_path.strip()
        organization_id = getattr(agent_config, "organization_id", None)
        if organization_id:
            from .tenant_workspace import tenant_workspace
            return str(tenant_workspace(organization_id, getattr(agent_config, "department_id", None), candidate,
                                        shared=bool(project_config), create=True))
        raise ValueError("An organization-scoped workspace is required.")

    def _agent_skills_prompt(self, agent_config, project_config):
        from plugins.workflow_skills import agent_skill_context

        try:
            context = agent_skill_context(
                self.services.database(), agent_config.organization_id, agent_config.skills,
                getattr(project_config, "id", None), department_id=agent_config.department_id,
                parent_agent_id=agent_config.parent_id,
            )
            if not context:
                raise ValueError("Configured skill context could not be resolved")
            return context
        except Exception as error:
            raise RuntimeError("Required agent skill context is unavailable") from error

    def _build_claude_command(
        self,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str] = None,
        fork_session: bool = False,
        dangerously_skip_permissions: bool = False,
        playground: bool = False
    ) -> List[str]:
        """
        Build Claude Code command with appropriate arguments.

        Args:
            agent_config: Agent configuration
            project_config: Project configuration (optional)
            prompt: The prompt to execute
            session_id: Optional session ID to resume
            fork_session: Whether to fork a new session
            dangerously_skip_permissions: Whether to skip permission prompts

        Returns:
            List of command arguments
        """
        from .direct_config import DIRECT_PROVIDERS, resolve_model_for_provider
        provider_id = self.resolve_runtime_provider(agent_config)
        direct = provider_id in DIRECT_PROVIDERS
        if session_id and not session_id.startswith(('pending_', 'sess_')):
            if session_id.startswith('api_') != direct:
                raise ValueError('This session belongs to a different execution method. Start a new session.')
        cmd = [sys.executable, '-m', 'runtime.direct_worker'] if direct else ["claude"]
        # Resolve logical model tier (e.g. tier:architect, tier:worker) to runtime model
        resolved_model = agent_config.model
        try:
            resolved_model = self.services.resolve_model(agent_config.model)
        except Exception:
            pass

        if direct:
            resolved_model = resolve_model_for_provider(
                provider_id, agent_config.model, db=self.organization_settings(agent_config)
            )
            cmd.extend(['--max-tokens', str(agent_config.max_tokens)])

        if resolved_model and resolved_model.lower() != "default":
            cmd.extend(["--model", resolved_model if direct else resolved_model.lower()])

        if playground:
            system_prompt = agent_config.system_prompt or ""
            if agent_config.skills:
                skill_context = self._agent_skills_prompt(agent_config, project_config)
                system_prompt += "\n" + skill_context
            # Explicit tool inventory and MCP configuration; no inherited customization.
            cmd.extend([
                "-p", prompt, "--output-format", "stream-json", "--verbose",
                "--safe-mode", "--tools", "", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}',
                "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
                "--permission-mode", "dontAsk", "--no-session-persistence",
                "--disable-slash-commands", "--no-chrome",
                "--system-prompt", system_prompt +
                "\nThis is an internal, tool-free workflow exercise. Use only supplied "
                "data. Report missing information explicitly; do not claim external actions occurred."
            ])
            return cmd

        if session_id and not session_id.startswith("pending_") and not session_id.startswith("sess_"):
            cmd.extend(["--resume", session_id])
            if fork_session:
                cmd.append("--fork-session")

        cmd.extend([
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose"
        ])

        # Permission bypass is opt-in: per-agent flag or an explicit environment
        # setting. By default only tools in allowed_tools are auto-approved.
        skip_permissions = (
            dangerously_skip_permissions or
            getattr(agent_config, "dangerously_skip_permissions", False) or
            os.getenv("PLATFORM_DANGEROUSLY_SKIP_PERMISSIONS", "false").lower() in ("true", "1")
        )
        if skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Add working directory restriction if specified
        target_dir = self._resolve_working_directory(project_config, agent_config)
        cmd.extend(["--add-dir", target_dir])

        # Pass agent system prompt with supervisor context, workspace, and equipped skills
        prompt_parts: List[str] = []
        if getattr(agent_config, "system_prompt", None) and agent_config.system_prompt.strip():
            prompt_parts.append(agent_config.system_prompt.strip())

        prompt_parts.append(
            f"[PROJECT WORKSPACE]\n"
            f"Your assigned project workspace directory is: {target_dir}\n"
            f"All files created, edited, read, or verified MUST reside inside this directory: {target_dir}"
        )

        if getattr(agent_config, "parent_id", None):
            parent_name = agent_config.parent_id
            try:
                db_manager = self.services.database()
                parent = db_manager.get_agent(agent_config.parent_id)
                if parent and parent.name:
                    parent_name = parent.name
            except Exception:
                pass
            prompt_parts.append(
                f"[ORGANIZATION HIERARCHY & SUPERVISOR INSTRUCTIONS]\n"
                f"Your supervisor is {parent_name} (ID: {agent_config.parent_id}).\n"
                f"If you lack required information, parameters, or permissions, ask your supervisor directly by stating your question clearly or using AskUserQuestion.\n"
                f"State the question clearly so your supervisor can provide the answer or permission."
            )

        # Inject delegation mandate for managers and orchestrators
        allowed_children = getattr(agent_config, "allowed_child_ids", []) or []
        role_type = (getattr(agent_config, "role_type", "") or "").upper()
        if allowed_children or role_type in ("ROOT_ORCHESTRATOR", "MANAGER"):
            subordinates_info = []
            try:
                db_manager = self.services.database()
                for cid in allowed_children:
                    child_agent = db_manager.get_agent(cid)
                    if child_agent:
                        subordinates_info.append(f"- `{cid}` ({child_agent.name}): {child_agent.description or child_agent.department}")
                    else:
                        subordinates_info.append(f"- `{cid}`")
            except Exception:
                subordinates_info = [f"- `{cid}`" for cid in allowed_children]

            subordinates_text = "\n".join(subordinates_info) if subordinates_info else "(subordinates defined in organization hierarchy)"

            prompt_parts.append(
                f"[ORGANIZATION HIERARCHY & TASK DELEGATION MANDATE]\n"
                f"You are an Orchestrator/Manager agent ({agent_config.name}, Role: {role_type}).\n"
                f"CRITICAL INVARIANT: You DO NOT execute lower-tier worker tasks yourself (do not write frontend/backend code, test suites, or subordinate specs directly).\n"
                f"You MUST delegate work packages down the organizational hierarchy to your authorized subordinates:\n"
                f"{subordinates_text}\n\n"
                f"HOW TO DELEGATE IN THIS PLATFORM:\n"
                f"To dispatch a task to a subordinate agent, run this command using the Bash tool:\n"
                f"python -m orchestration.delegate --target-agent <agent_id> --prompt \"<detailed requirements, deliverables, and acceptance criteria>\"\n\n"
                f"CRITICAL TIMEOUT REQUIREMENT:\n"
                f"Always pass `timeout: 600000` (10 minutes) in your Bash tool call when running delegate commands so the system does not prematurely background your task while waiting for subordinates!\n"
                f"NOTE: The delegate command automatically WAITS for the subordinate agent to finish and outputs their completed deliverables to your terminal, allowing you to seamlessly verify their work and proceed to the next milestone in your turn!\n\n"
                f"CRITICAL EXECUTION MANDATE:\n"
                f"- You interact with this platform EXCLUSIVELY via standard tool calls (Write, Read, Edit, Bash, Grep, Glob).\n"
                f"- NEVER output XML pseudo-tags such as `<assistant to=...>` or simulated responses in markdown.\n"
                f"- When initiating a new project charter, first write PROJECT_PLAN.md using the Write tool.\n"
                f"- Then immediately dispatch your subordinate manager (e.g. `product-manager`) using the Bash tool with `python -m orchestration.delegate`.\n"
                f"- Inspect the output returned by the delegate command and proceed to coordinate subsequent steps."
            )

        if agent_config.skills:
            prompt_parts.append(self._agent_skills_prompt(agent_config, project_config))

        if prompt_parts:
            cmd.extend(["--system-prompt", "\n\n".join(prompt_parts)])

        # Enforce agent tool restrictions. Managers/orchestrators always get Bash
        # (delegation runs `python -m orchestration.delegate`) on top of the
        # workspace file tools, even when no explicit list is configured.
        configured_tools = list(getattr(agent_config, "allowed_tools", None) or [])
        is_manager = bool(allowed_children) or role_type in ("ROOT_ORCHESTRATOR", "MANAGER")
        if not configured_tools and is_manager:
            configured_tools = list(SAFE_WORKSPACE_TOOLS)
        if configured_tools:
            tool_mapping = {
                # Legacy workflow runners stored ["*"]; it never means "every tool".
                "*": list(SAFE_WORKSPACE_TOOLS),
                "read": ["Read", "View"], "view": ["Read", "View"],
                "write": ["Write", "Edit", "FileEdit"], "edit": ["Edit", "Write", "FileEdit"],
                "grep": ["Grep"], "glob": ["Glob"],
                "bash": ["Bash"], "Bash": ["Bash"],
                "delegate_task": ["Bash"],
                "ask_supervisor": ["AskUserQuestion"], "ask_manager": ["AskUserQuestion"],
                "ask_human": ["AskUserQuestion"], "AskUserQuestion": ["AskUserQuestion"]
            }
            mapped_tools = set()
            for t in configured_tools:
                if t in tool_mapping:
                    mapped = tool_mapping[t]
                    if isinstance(mapped, list):
                        mapped_tools.update(mapped)
                    else:
                        mapped_tools.add(mapped)
                else:
                    mapped_tools.add(t)
            if is_manager:
                mapped_tools.add("Bash")
            cmd.extend(["--allowedTools", ",".join(sorted(mapped_tools))])

        return cmd
