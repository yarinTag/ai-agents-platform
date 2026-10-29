"""Provider selection, environment preparation and CLI command construction."""

import logging
import os
from typing import Dict, List, Optional
from config import AgentConfig, ProjectConfig
import runtime_providers as providers
from .services import RuntimeServices

logger = logging.getLogger(__name__)
RUNTIME_PROVIDER_SETTING_KEY = providers.SETTING_PROVIDER
RUNTIME_GATEWAY_URL_SETTING_KEY = providers.SETTING_GATEWAY_URL


class RuntimeCommandBuilder:
    def __init__(self, services: RuntimeServices):
        self.services = services

    def resolve_runtime_provider(self, agent_config: Optional[AgentConfig] = None) -> str:
        """
        Resolve which runtime provider a run should use.

        Precedence, most specific first:
          1. The agent's own `runtime_provider` override
          2. PLATFORM_RUNTIME_PROVIDER in the environment
          3. The default saved by the first-run setup prompt
          4. Native Claude Code CLI auth

        Detection is intentionally *not* part of this chain: a saved default must
        not flip because a proxy happened to be asleep. Detection only feeds the
        setup prompt's suggestion.
        """
        saved_choice = None
        try:
            saved_choice = self.services.database().get_setting(RUNTIME_PROVIDER_SETTING_KEY)
        except Exception:
            logging.getLogger(__name__).debug("Saved runtime provider unavailable")
        return providers.resolve_provider_selection(
            getattr(agent_config, "runtime_provider", None), saved_choice,
        )

    def _build_claude_env(
        self,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> Dict[str, str]:
        """Build environment variables for Claude Code subprocess."""
        provider_id = self.resolve_runtime_provider(agent_config)

        gateway_url = None
        try:
            db_manager = self.services.database()
            gateway_url = db_manager.get_setting(RUNTIME_GATEWAY_URL_SETTING_KEY)
        except Exception:
            pass

        # build_provider_env strips inherited backend-steering vars before
        # applying the selected provider, so a stale ANTHROPIC_BASE_URL in the
        # platform's own shell cannot hijack a native-auth run.
        env = providers.build_provider_env(
            provider_id, os.environ.copy(), gateway_base_url=gateway_url
        )
        env["PLATFORM_RUNTIME_PROVIDER"] = provider_id
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
        """Resolve a robust, cross-platform working directory, avoiding invalid macOS paths."""
        candidate = None
        if project_config and getattr(project_config, "working_directory", None) and project_config.working_directory.strip():
            candidate = project_config.working_directory.strip()
        elif agent_config and getattr(agent_config, "repo_path", None) and agent_config.repo_path.strip():
            candidate = agent_config.repo_path.strip()

        if candidate:
            # Detect invalid macOS/Unix paths on Windows
            if os.name == "nt" and (candidate.startswith("/Users/") or candidate.startswith("/home/")):
                local_poc_lms = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "lms"))
                if os.path.exists(local_poc_lms):
                    return local_poc_lms
                return os.getcwd()
            try:
                abs_path = os.path.abspath(candidate)
                os.makedirs(abs_path, exist_ok=True)
                return abs_path
            except Exception:
                pass
        return os.getcwd()

    def _build_claude_command(
        self,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str] = None,
        fork_session: bool = False,
        dangerously_skip_permissions: bool = False
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
        cmd = ["claude"]
        # Resolve logical model tier (e.g. tier:architect, tier:worker) to runtime model
        resolved_model = agent_config.model
        try:
            resolved_model = self.services.resolve_model(agent_config.model)
        except Exception:
            pass

        if resolved_model and resolved_model.lower() != "default":
            cmd.extend(["--model", resolved_model.lower()])

        if session_id and not session_id.startswith("pending_") and not session_id.startswith("sess_"):
            cmd.extend(["--resume", session_id])
            if fork_session:
                cmd.append("--fork-session")

        cmd.extend([
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose"
        ])

        # Make --dangerously-skip-permissions configurable per-agent, per-run, or per-environment
        skip_permissions = (
            dangerously_skip_permissions or
            getattr(agent_config, "dangerously_skip_permissions", False) or
            os.getenv("PLATFORM_DANGEROUSLY_SKIP_PERMISSIONS", "true").lower() in ("true", "1")
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

        # Inject equipped skills if configured
        agent_skills = getattr(agent_config, "skills", None)
        if agent_skills and len(agent_skills) > 0:
            try:
                skills_prompt = self.services.skills_prompt(agent_skills)
                if not skills_prompt:
                    raise RuntimeError("Configured skill context could not be resolved")
                prompt_parts.append(skills_prompt)
            except Exception as error:
                raise RuntimeError("Required agent skill context is unavailable") from error

        if prompt_parts:
            cmd.extend(["--system-prompt", "\n\n".join(prompt_parts)])

        # Enforce agent tool restrictions if configured
        if getattr(agent_config, "allowed_tools", None) and len(agent_config.allowed_tools) > 0:
            tool_mapping = {
                "read": ["Read", "View"], "view": ["Read", "View"],
                "write": ["Write", "Edit", "FileEdit"], "edit": ["Edit", "Write", "FileEdit"],
                "grep": ["Grep"], "glob": ["Glob"],
                "bash": ["Bash"], "Bash": ["Bash"],
                "delegate_task": ["Bash"],
                "ask_supervisor": ["AskUserQuestion"], "ask_manager": ["AskUserQuestion"],
                "ask_human": ["AskUserQuestion"], "AskUserQuestion": ["AskUserQuestion"]
            }
            mapped_tools = set()
            for t in agent_config.allowed_tools:
                if t in tool_mapping:
                    mapped = tool_mapping[t]
                    if isinstance(mapped, list):
                        mapped_tools.update(mapped)
                    else:
                        mapped_tools.add(mapped)
                else:
                    mapped_tools.add(t)
            if allowed_children or role_type in ("ROOT_ORCHESTRATOR", "MANAGER"):
                mapped_tools.add("Bash")
            cmd.extend(["--allowedTools", ",".join(sorted(mapped_tools))])

        return cmd
