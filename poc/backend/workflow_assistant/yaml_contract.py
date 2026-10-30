"""Lossless semantic bridge between governed resource plans and runtime-native YAML."""
import yaml
from workflows.authoring_schema import SCHEMA_VERSION, WorkflowDocument
from workflows.parser import WorkflowParser, validate_workflow_definition
from .models import WorkflowProposal


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError('YAML mapping keys must be unique strings.')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_workflow_yaml(content: str) -> WorkflowDocument:
    if not isinstance(content, str) or len(content.encode('utf-8')) > 200000:
        raise ValueError('Workflow YAML exceeds the 200 KB limit.')
    try:
        for token in yaml.scan(content):
            if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)):
                raise ValueError('YAML aliases and anchors are not supported.')
        data = yaml.load(content, Loader=UniqueKeyLoader)
        document = WorkflowDocument.model_validate(data)
        document_to_proposal(document)
        return document
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError('Invalid workflow YAML.') from exc


def document_to_proposal(document: WorkflowDocument) -> WorkflowProposal:
    data = document.model_dump(by_alias=True)
    validate_workflow_definition(data)
    parsed = WorkflowParser.from_dict(data)
    trigger = document.triggers[0]
    kind = ('channel' if trigger.event == 'channel_message' else
            'repository' if trigger.event in ('pull_request.opened', 'pull_request.updated', 'push') else trigger.event)
    if document.webhook_enabled != (kind == 'webhook'):
        raise ValueError('webhook_enabled must match the webhook trigger.')
    native_trigger = {'kind': kind}
    if kind == 'cron':
        native_trigger['cron_expression'] = document.cron_expression
    elif document.cron_expression is not None:
        raise ValueError('cron_expression is only supported with a cron trigger.')
    for key in ('connector_id', 'repository', 'channel_id'):
        value = getattr(trigger, key)
        if value is not None:
            native_trigger[key] = value
    if kind in ('channel', 'repository'):
        native_trigger['event'] = 'message' if kind == 'channel' else trigger.event
    steps = []
    for original, step in zip(document.steps, parsed.steps):
        bindings = original.params.model_dump()
        referenced = {r.connector_id for r in original.params.tools}
        referenced |= {r.connector_id for r in original.params.repositories}
        referenced |= {r.connector_id for r in original.params.channels}
        if len(original.mcp_servers) != len(set(original.mcp_servers)) or set(original.mcp_servers) != referenced:
            raise ValueError('Step mcp_servers must exactly match its explicit resource bindings.')
        steps.append({'key': step.key, 'name': step.name, 'agent_id': step.agent_id,
            'prompt_template': step.prompt_template, 'depends_on': step.depends_on,
            'timeout_seconds': step.timeout_seconds, 'skills': step.skills, **bindings})
    return WorkflowProposal.model_validate({'name': document.name, 'description': document.description,
        'trigger': native_trigger, 'steps': steps,
        'unresolved_requirements': document.metadata.unresolved_requirements})


def proposal_document(proposal: WorkflowProposal) -> WorkflowDocument:
    trigger = proposal.trigger
    event = 'channel_message' if trigger.kind == 'channel' else trigger.event if trigger.kind == 'repository' else trigger.kind
    # Incomplete proposals can be retained as blocked drafts. Preserve missing inputs,
    # but do not produce an apparently valid native document for them.
    if not event:
        raise ValueError('A repository trigger event is required for YAML export.')
    steps = []
    for step in proposal.steps:
        bindings = {key: getattr(step, key) for key in ('tools', 'repositories', 'channels', 'requires_approval')}
        referenced = sorted({ref.connector_id for ref in [*step.tools, *step.repositories, *step.channels]})
        steps.append({'key': step.key, 'name': step.name, 'agent_id': step.agent_id,
            'prompt_template': step.prompt_template, 'depends_on': step.depends_on,
            'timeout_seconds': step.timeout_seconds, 'skills': step.skills,
            'mcp_servers': referenced, 'params': bindings})
    return WorkflowDocument.model_validate({'name': proposal.name, 'description': proposal.description,
        'triggers': [{'event': event, **trigger.model_dump(include={'connector_id','repository','channel_id'}, exclude_none=True)}],
        'cron_expression': trigger.cron_expression, 'webhook_enabled': trigger.kind == 'webhook',
        'steps': steps, 'metadata': {'unresolved_requirements': proposal.unresolved_requirements}})


def proposal_artifact(proposal: WorkflowProposal) -> dict:
    try:
        document = proposal_document(proposal)
        # Guard against divergent semantics/ignored fields before emitting YAML.
        if document_to_proposal(document) != proposal:
            raise ValueError('Proposal cannot be exported without changing its semantics.')
        data = document.model_dump(by_alias=True, exclude_none=True)
        content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        if len(content.encode('utf-8')) > 200000:
            raise ValueError('Workflow YAML exceeds the 200 KB limit.')
        return {'workflow_schema_version': SCHEMA_VERSION, 'definition_json': data,
            'definition_yaml': content, 'yaml_error': None}
    except ValueError as exc:
        return {'workflow_schema_version': SCHEMA_VERSION, 'definition_json': None,
            'definition_yaml': None, 'yaml_error': str(exc)}


def workflow_schema() -> dict:
    schema = WorkflowDocument.model_json_schema(by_alias=True)
    return {'workflow_schema_version': SCHEMA_VERSION, 'schema': schema,
        'yaml_schema': yaml.safe_dump(schema, sort_keys=False, allow_unicode=True)}
