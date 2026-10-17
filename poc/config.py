"""
Configuration management for the AI Agents Platform PoC.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path


from enum import Enum


class AgentRole(str, Enum):
    """Canonical roles for platform agents."""
    ROOT_ORCHESTRATOR = "ROOT_ORCHESTRATOR"
    SUPER_AGENT = "SUPER_AGENT"
    MANAGER = "MANAGER"
    WORKER = "WORKER"
    SPECIALIST = "SPECIALIST"
    WORKFLOW_AUTOMATION = "WORKFLOW_AUTOMATION"


@dataclass
class AgentConfig:
    """Configuration for an AI agent with organizational hierarchy support."""
    id: str
    name: str
    description: str
    system_prompt: str
    skills: List[str] = None
    model: str = "default"
    effort: str = "medium"
    max_tokens: int = 8000
    temperature: float = 0.7
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    department: str = "Engineering"
    avatar: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Hierarchy and delegation fields
    parent_id: Optional[str] = None
    role_type: str = "WORKER"
    max_concurrent_children: int = 3
    delegation_strategy: str = "hierarchical"
    allowed_child_ids: List[str] = None
    allowed_tools: List[str] = None
    template_id: Optional[str] = None
    dangerously_skip_permissions: bool = False
    # Overrides the platform default runtime provider for this agent. None = inherit default.
    runtime_provider: Optional[str] = None

    # Communication & MCP permissions
    allow_sibling_communication: bool = True
    allowed_peer_ids: List[str] = None
    mcp_permissions: List[str] = None

    # Workflow automation fields (detached from physical office floor)
    is_workflow_agent: bool = False
    workflow_id: Optional[str] = None

    # Logical model capability tier (e.g. "tier:architect", "tier:worker", "tier:executive")
    model_tier: Optional[str] = None

    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.allowed_child_ids is None:
            self.allowed_child_ids = []
        if self.allowed_tools is None:
            self.allowed_tools = []
        if self.allowed_peer_ids is None:
            self.allowed_peer_ids = []
        if self.mcp_permissions is None:
            self.mcp_permissions = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        import inspect
        valid_fields = set(inspect.signature(cls).parameters.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class SuperAgentConfig:
    """Explicit decision authority configuration for a Super Agent."""
    agent_id: str
    project_id: str
    can_answer_questions: bool = True
    can_delegate: bool = True
    can_create_subtasks: bool = True
    can_use_mcp: bool = True
    can_make_project_decisions: bool = True
    can_modify_files: bool = True
    can_execute_commands: bool = True
    require_human_approval_for: List[str] = None

    def __post_init__(self):
        if self.require_human_approval_for is None:
            self.require_human_approval_for = [
                "external_messages",
                "destructive_actions",
                "production_changes",
                "financial_actions"
            ]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SuperAgentConfig':
        import inspect
        valid_fields = set(inspect.signature(cls).parameters.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)



@dataclass
class AgentTemplate:
    """Reusable template definition for creating agents."""
    id: str
    name: str
    description: str
    role: str
    system_prompt: str
    model: str = "default"
    skills: List[str] = None
    tools: List[str] = None
    suggested_children: List[str] = None
    category: str = "Engineering"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.tools is None:
            self.tools = []
        if self.suggested_children is None:
            self.suggested_children = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentTemplate':
        return cls(**data)


@dataclass
class ProjectConfig:
    """Configuration for a project."""
    id: str
    name: str
    description: str
    working_directory: str
    instructions: Optional[str] = None
    skills: List[str] = None
    allowed_tools: List[str] = None

    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.allowed_tools is None:
            # Default to safe, read-only tools
            self.allowed_tools = ["read", "grep", "glob"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectConfig':
        return cls(**data)


@dataclass
class Skill:
    """Represents a reusable skill."""
    id: str
    name: str
    description: str
    content: str  # Markdown content
    project_id: Optional[str] = None  # None for global skills
    source: Optional[str] = "custom"  # "builtin", "local", "git", "custom"
    location: Optional[str] = None    # Repository URL or filesystem path

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Skill':
        return cls(**data)


class ConfigManager:
    """Manages configuration for agents, projects, and skills."""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            self.config_dir = Path(__file__).resolve().parent / "config"
        else:
            self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        self.agents_file = self.config_dir / "agents.json"
        self.projects_file = self.config_dir / "projects.json"
        self.skills_dir = self.config_dir / "skills"
        self.skills_dir.mkdir(exist_ok=True)

        # Load existing configurations
        self.agents: Dict[str, AgentConfig] = self._load_agents()
        self.projects: Dict[str, ProjectConfig] = self._load_projects()

    def _load_agents(self) -> Dict[str, AgentConfig]:
        """Load agents from JSON file."""
        if self.agents_file.exists():
            try:
                with open(self.agents_file, 'r') as f:
                    data = json.load(f)
                    return {
                        agent_id: AgentConfig.from_dict(agent_data)
                        for agent_id, agent_data in data.items()
                    }
            except Exception as e:
                print(f"Warning: Could not load agents: {e}")
                return {}
        return {}

    def _load_projects(self) -> Dict[str, ProjectConfig]:
        """Load projects from JSON file."""
        if self.projects_file.exists():
            try:
                with open(self.projects_file, 'r') as f:
                    data = json.load(f)
                    return {
                        project_id: ProjectConfig.from_dict(project_data)
                        for project_id, project_data in data.items()
                    }
            except Exception as e:
                print(f"Warning: Could not load projects: {e}")
                return {}
        return {}

    def save_agents(self):
        """Save agents to JSON file."""
        try:
            with open(self.agents_file, 'w') as f:
                json.dump(
                    {agent_id: agent.to_dict() for agent_id, agent in self.agents.items()},
                    f,
                    indent=2
                )
        except Exception as e:
            print(f"Error saving agents: {e}")

    def save_projects(self):
        """Save projects to JSON file."""
        try:
            with open(self.projects_file, 'w') as f:
                json.dump(
                    {project_id: project.to_dict() for project_id, project in self.projects.items()},
                    f,
                    indent=2
                )
        except Exception as e:
            print(f"Error saving projects: {e}")

    def register_agent(self, agent: AgentConfig):
        """Register a new agent."""
        self.agents[agent.id] = agent
        self.save_agents()

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent by ID."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.save_agents()
            return True
        return False

    def list_agents(self) -> List[AgentConfig]:
        """List all registered agents."""
        return list(self.agents.values())

    def register_project(self, project: ProjectConfig):
        """Register a new project."""
        self.projects[project.id] = project
        self.save_projects()

    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        """Get a project by ID."""
        return self.projects.get(project_id)

    def list_projects(self) -> List[ProjectConfig]:
        """List all registered projects."""
        return list(self.projects.values())

    def load_skill(self, skill_id: str) -> Optional[Skill]:
        """Load a skill from markdown file."""
        skill_file = self.skills_dir / f"{skill_id}.md"
        if skill_file.exists():
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Try to parse frontmatter for metadata
                name = skill_id.replace('-', ' ').title()
                description = f"Skill loaded from {skill_id}"

                # Check for YAML frontmatter
                if content.startswith('---'):
                    try:
                        _, frontmatter, rest = content.split('---', 2)
                        import yaml
                        metadata = yaml.safe_load(frontmatter)
                        name = metadata.get('name', name)
                        description = metadata.get('description', description)
                        content = rest.strip()
                    except Exception:
                        pass  # If frontmatter parsing fails, use whole content

                return Skill(
                    id=skill_id,
                    name=name,
                    description=description,
                    content=content
                )
            except Exception as e:
                print(f"Error loading skill {skill_id}: {e}")
                return None
        return None

    def save_skill(self, skill: Skill):
        """Save a skill to markdown file."""
        try:
            skill_file = self.skills_dir / f"{skill.id}.md"
            # Simple markdown format with optional frontmatter
            frontmatter = f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n"
            with open(skill_file, 'w', encoding='utf-8') as f:
                f.write(frontmatter + skill.content)
        except Exception as e:
            print(f"Error saving skill {skill.id}: {e}")


# Global config manager instance
config_manager = ConfigManager()