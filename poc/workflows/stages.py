"""Pure dependency-stage planning."""
from typing import List
from .parser import WorkflowStepDefinition

def group_steps_into_stages(steps: List[WorkflowStepDefinition]) -> List[List[WorkflowStepDefinition]]:
    """Group steps into DAG execution stages for parallel multi-agent execution."""
    if not steps:
        return []
    step_map = {s.key: s for s in steps}
    if len(step_map) != len(steps):
        raise ValueError("Workflow step keys must be unique")
    for step in steps:
        unknown = set(step.depends_on) - set(step_map)
        if unknown:
            raise ValueError(f"Workflow step '{step.key}' references unknown dependencies")
    completed_keys = set()
    stages: List[List[WorkflowStepDefinition]] = []
    remaining = list(steps)

    while remaining:
        ready = [
            s for s in remaining
            if all(dep in completed_keys for dep in s.depends_on)
        ]
        if not ready:
            raise ValueError("Workflow dependencies contain a cycle")
        stages.append(ready)
        for s in ready:
            completed_keys.add(s.key)
            remaining.remove(s)

    return stages

