"""
Workflow Definition Parser:
Loads, validates, and converts workflow definitions between YAML and JSON formats.
Follows declarative playbooks with step-by-step DAG dependencies.
"""

import json
import yaml
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowDefinition:
    """Full workflow definition containing metadata and ordered/DAG steps."""
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    steps: List[WorkflowStepDefinition] = field(default_factory=list)
    cron_expression: Optional[str] = None
    webhook_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "department_id": self.department_id,
            "steps": [s.to_dict() for s in self.steps],
            "cron_expression": self.cron_expression,
            "webhook_enabled": self.webhook_enabled,
            "metadata": self.metadata
        }

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
        """Parse raw dictionary into WorkflowDefinition."""
        steps_raw = data.get("steps", [])
        parsed_steps: List[WorkflowStepDefinition] = []

        for s in steps_raw:
            parsed_steps.append(
                WorkflowStepDefinition(
                    key=s.get("key", s.get("id", "")),
                    name=s.get("name", s.get("key", "")),
                    agent_id=s.get("agent_id", ""),
                    prompt_template=s.get("prompt_template", s.get("prompt", "")),
                    depends_on=s.get("depends_on", []),
                    condition=s.get("condition"),
                    timeout_seconds=int(s.get("timeout_seconds", 300)),
                    acceptance_criteria=s.get("acceptance_criteria"),
                    retry_count=int(s.get("retry_count", 0)),
                    estimated_cost_usd=float(s.get("estimated_cost_usd", 0.0))
                )
            )

        return WorkflowDefinition(
            id=data.get("id", ""),
            name=data.get("name", "Unnamed Workflow"),
            description=data.get("description"),
            department_id=data.get("department_id"),
            steps=parsed_steps,
            cron_expression=data.get("cron_expression"),
            webhook_enabled=bool(data.get("webhook_enabled", True)),
            metadata=data.get("metadata", {})
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
