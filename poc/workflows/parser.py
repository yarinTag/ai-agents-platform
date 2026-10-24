"""
Workflow Definition Parser:
Loads, validates, and converts workflow definitions between YAML and JSON formats.
Supports declarative playbooks with DAG dependencies, explicit flow transitions,
triggers with conditional matching, and step-level skills.
"""

import json
import re
import yaml
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union


def _slugify(text: str) -> str:
    """Convert text to a clean slug identifier."""
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return s.strip('-')


@dataclass
class WorkflowStepDefinition:
    """Definition of an individual step in a workflow."""
    key: str
    name: str
    agent_id: str
    prompt_template: str
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    timeout_seconds: int = 300
    acceptance_criteria: Optional[str] = None
    retry_count: int = 0
    estimated_cost_usd: float = 0.0
    mcp_servers: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not self.mcp_servers:
            d.pop("mcp_servers", None)
        if not self.skills:
            d.pop("skills", None)
        if not self.condition:
            d.pop("condition", None)
        if not self.acceptance_criteria:
            d.pop("acceptance_criteria", None)
        if not self.params:
            d.pop("params", None)
        return d


@dataclass
class WorkflowDefinition:
    """Full workflow definition containing metadata, triggers, steps, and flow."""
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    priority: int = 0
    timeout_ms: int = 0
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[WorkflowStepDefinition] = field(default_factory=list)
    flow: List[Dict[str, str]] = field(default_factory=list)
    cron_expression: Optional[str] = None
    webhook_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    mcp_servers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "department_id": self.department_id,
        }
        if self.priority:
            res["priority"] = self.priority
        if self.timeout_ms:
            res["timeoutMs"] = self.timeout_ms
        if self.triggers:
            res["triggers"] = self.triggers
        if self.mcp_servers:
            res["mcp_servers"] = self.mcp_servers
        if self.skills:
            res["skills"] = self.skills
        res["steps"] = [s.to_dict() for s in self.steps]
        if self.flow:
            res["flow"] = self.flow
        res["cron_expression"] = self.cron_expression
        res["webhook_enabled"] = self.webhook_enabled
        res["metadata"] = self.metadata
        return res

    def to_json(self, indent: int = 2) -> str:
        """Convert workflow definition to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_yaml(self) -> str:
        """Convert workflow definition to YAML string."""
        return yaml.dump(self.to_dict(), sort_keys=False)


class WorkflowParser:
    """Parses, validates, and serializes workflow YAML/JSON."""

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> WorkflowDefinition:
        """Parse raw dictionary into WorkflowDefinition with flow resolution."""
        steps_raw = data.get("steps", [])
        parsed_steps: List[WorkflowStepDefinition] = []

        flow_raw = data.get("flow", [])
        flow_deps: Dict[str, List[str]] = {}

        # Parse flow transitions (from -> to)
        for transition in flow_raw:
            if isinstance(transition, dict):
                src = transition.get("from", "").strip()
                dst = transition.get("to", "").strip()
                if dst:
                    if dst not in flow_deps:
                        flow_deps[dst] = []
                    if src and src not in flow_deps[dst]:
                        flow_deps[dst].append(src)

        for s in steps_raw:
            name = s.get("name", "")
            raw_key = s.get("key") or s.get("id") or _slugify(name) or f"step_{len(parsed_steps)+1}"
            # Explicit keys are stable identifiers used by dependencies and prompt references.
            step_key = str(raw_key)

            # Determine agent_id from step or params
            params = s.get("params", {})
            agent_id = s.get("agent_id") or params.get("agentId") or s.get("agent") or "default-agent"

            # Determine prompt from instructions, prompt_template, prompt, or action
            prompt = s.get("prompt_template") or s.get("instructions") or s.get("prompt") or s.get("action") or ""

            # Determine timeout (seconds)
            timeout_sec = int(s.get("timeout_seconds") or 0)
            if not timeout_sec:
                if "stepMaxDurationMinutes" in s:
                    timeout_sec = int(s["stepMaxDurationMinutes"]) * 60
                elif "timeoutMs" in s:
                    timeout_sec = int(s["timeoutMs"]) // 1000
                else:
                    timeout_sec = 300

            # Dependencies: combine explicit depends_on with flow transitions
            deps = list(s.get("depends_on", []))
            if step_key in flow_deps:
                for src_dep in flow_deps[step_key]:
                    if src_dep not in deps:
                        deps.append(src_dep)
            # Also check if raw_key in flow_deps
            if raw_key in flow_deps and raw_key != step_key:
                for src_dep in flow_deps[raw_key]:
                    if src_dep not in deps:
                        deps.append(src_dep)

            parsed_steps.append(
                WorkflowStepDefinition(
                    key=step_key,
                    name=name or step_key,
                    agent_id=agent_id,
                    prompt_template=prompt,
                    depends_on=deps,
                    condition=s.get("condition"),
                    timeout_seconds=timeout_sec,
                    acceptance_criteria=s.get("acceptance_criteria"),
                    retry_count=int(s.get("retry_count", 0)),
                    estimated_cost_usd=float(s.get("estimated_cost_usd", 0.0)),
                    mcp_servers=s.get("mcp_servers", []),
                    skills=s.get("skills", []),
                    params=params
                )
            )

        name = data.get("name", "Unnamed Workflow")
        wf_id = data.get("id") or _slugify(name) or "unnamed-workflow"

        timeout_ms = int(data.get("timeoutMs") or data.get("timeout_ms") or 0)
        priority = int(data.get("priority", 0))
        triggers = data.get("triggers", [])

        return WorkflowDefinition(
            id=wf_id,
            name=name,
            description=data.get("description"),
            department_id=data.get("department_id"),
            priority=priority,
            timeout_ms=timeout_ms,
            triggers=triggers,
            steps=parsed_steps,
            flow=flow_raw,
            cron_expression=data.get("cron_expression"),
            webhook_enabled=bool(data.get("webhook_enabled", True)),
            metadata=data.get("metadata", {}),
            skills=data.get("skills", []),
            mcp_servers=data.get("mcp_servers", [])
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> WorkflowDefinition:
        """Parse a YAML string into a WorkflowDefinition."""
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            raise ValueError("YAML content must be a mapping/dictionary")
        return cls.from_dict(parsed)

    @classmethod
    def from_json(cls, json_content: str) -> WorkflowDefinition:
        """Parse a JSON string into a WorkflowDefinition."""
        parsed = json.loads(json_content)
        if not isinstance(parsed, dict):
            raise ValueError("JSON content must be a mapping/dictionary")
        return cls.from_dict(parsed)

    @classmethod
    def yaml_to_json(cls, yaml_content: str, indent: int = 2) -> str:
        """Convert a YAML workflow definition directly to JSON string."""
        wf = cls.from_yaml(yaml_content)
        return wf.to_json(indent=indent)

    @classmethod
    def json_to_yaml(cls, json_content: str) -> str:
        """Convert a JSON workflow definition directly to YAML string."""
        wf = cls.from_json(json_content)
        return wf.to_yaml()
