"""Workflow-wide instruction inheritance with legacy per-step compatibility."""

def workflow_skill_ids(definition):
    values = list(definition.get('skills') or [])
    for step in definition.get('steps') or []:
        values.extend(step.get('skills') or [])
    identifiers = []
    for value in values:
        identifier = value.get('id') or value.get('location') if isinstance(value, dict) else value
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError('Workflow skills require a nonempty skill ID.')
        if identifier not in identifiers:
            identifiers.append(identifier)
    return identifiers
