"""Implementation-owned descriptors. Connector metadata cannot register capabilities."""
from dataclasses import dataclass, asdict
from integrations.tool_definitions import OPERATIONS, input_model, resource_values, valid_channel, valid_repository, operation_effect, operation_requirements


@dataclass(frozen=True)
class Capability:
    id: str
    provider: str
    operation: str
    effect: str
    resource_type: str
    description: str
    version: int = 1
    server_only: bool = False
    approval_required: bool = False
    implemented: bool = True

    def public(self):
        value = asdict(self)
        value['input_schema'] = (input_model({'provider': self.provider, 'operation': self.operation}).model_json_schema()
                                 if not self.server_only and self.implemented else None)
        value['verification'] = 'implementation_metadata_only'
        value['requires_capabilities'] = [self.provider + '.' + operation for operation in operation_requirements(self.provider, self.operation)]
        return value


def descriptors():
    result = {}
    for provider, operations in OPERATIONS.items():
        for operation, description in operations.items():
            cap = Capability(f'{provider}.{operation}', provider, operation,
                operation_effect(provider, operation), 'repository' if provider == 'github' else 'channel', description)
            result[cap.id] = cap
    for operation, description, effect, approval in (
        ('clone_repository', 'Read an approved repository in a governed workspace.', 'read', False),
        ('open_pull_request', 'Publish an approved write workspace as a draft PR.', 'write', False),
        ('merge_pull_request', 'Server-only reviewed-SHA merge after authenticated human approval.', 'destructive', True)):
        cap = Capability(f'github.{operation}', 'github', operation, effect, 'repository', description,
                         server_only=True, approval_required=approval)
        result[cap.id] = cap
    # Known roadmap names are honest about not having an implementation.
    for provider, operation, resource in (
        ('github', 'edit_pull_request', 'repository'), ('github', 'rerun_checks', 'repository'),
        ('telegram', 'listen_channel', 'channel'), ('telegram', 'approve_action', 'channel'),
        ('slack', 'listen_channel', 'channel'), ('slack', 'approve_action', 'channel')):
        cap = Capability(f'{provider}.{operation}', provider, operation, 'write', resource,
                         'Not implemented; cannot be granted or executed.', server_only=True, implemented=False)
        result[cap.id] = cap
    return result


def capability(identifier):
    return descriptors().get(identifier)


def configured_resources(connector, cap):
    if connector.provider.lower() != cap.provider:
        return []
    group = 'repositories' if cap.resource_type == 'repository' else 'channels'
    values = resource_values(connector.configuration or {}, group)
    return [value for value in values if (valid_repository(value) if cap.resource_type == 'repository'
                                        else valid_channel(cap.provider, value))]
