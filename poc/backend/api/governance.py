"""Versioned capability policy APIs. Decisions are explanatory, never execution tokens."""
from fastapi import APIRouter, Depends, HTTPException, Request
from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources
from governance.models import DecisionRequest, PolicyDocument, PolicyUpdate
from governance.policy import decide
from governance.registry import capability, configured_resources, descriptors
from governance import store
from governance.validation import validate_document

router = APIRouter()


def _editor_record(db, actor, scope_type, scope_id):
    record = store.load(db, actor.organization_id, scope_type, scope_id)
    options = []
    for connector in db.list_mcp_connectors(organization_id=actor.organization_id):
        if connector.organization_id != actor.organization_id:
            continue
        if scope_type == 'department':
            grant = db.get_department_mcp_access(scope_id, connector.id)
            if not grant or not grant.is_active or grant.organization_id not in (None, actor.organization_id):
                continue
        for cap in descriptors().values():
            resources = configured_resources(connector, cap) if cap.implemented else []
            if resources:
                options.append({'capability_id': cap.id, 'connector_id': connector.id,
                                'connector_name': connector.name, 'resource_type': cap.resource_type,
                                'resource_ids': resources})
    # Configuration/credentials never cross this projection. Options are not grants.
    return {**record, 'resource_options': options}


def _actor(request, db, department_id=None, level=1):
    actor = load_actor(request, db)
    if department_id:
        Resources(actor).require('department', department_id, level)
    else:
        actor.require(level=level)
    return actor


def _save(request, db, payload, scope_type, scope_id):
    actor = _actor(request, db, scope_id if scope_type == 'department' else None, 3 if scope_type == 'department' else 4)
    document = PolicyDocument.model_validate(payload.model_dump(exclude={'expected_revision'}))
    try:
        store.save(db, actor.organization_id, scope_type, scope_id, document, payload.expected_revision, actor.user_id,
                   validator=lambda previous: validate_document(db, actor, document, scope_type, scope_id, previous))
    except store.RevisionConflict as error:
        raise HTTPException(409, str(error)) from None
    except PermissionError as error:
        raise HTTPException(403, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return store.load(db, actor.organization_id, scope_type, scope_id)


@router.get('/capabilities')
def list_capability_descriptors(request: Request, db=Depends(get_db_manager)):
    _actor(request, db)
    return {'schema_version': 1, 'capabilities': [cap.public() for cap in descriptors().values()]}


@router.get('/organization/policy')
def get_organization_capability_policy(request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, level=4)
    return _editor_record(db, actor, 'organization', actor.organization_id)


@router.put('/organization/policy')
def put_organization_capability_policy(payload: PolicyUpdate, request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, level=4)
    return _save(request, db, payload, 'organization', actor.organization_id)


@router.get('/departments/{department_id}/policy')
def get_department_capability_policy(department_id: str, request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id, 3)
    return _editor_record(db, actor, 'department', department_id)


@router.put('/departments/{department_id}/policy')
def put_department_capability_policy(department_id: str, payload: PolicyUpdate, request: Request, db=Depends(get_db_manager)):
    return _save(request, db, payload, 'department', department_id)


@router.get('/departments/{department_id}/policy/history')
def list_department_capability_revisions(department_id: str, request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id, 3)
    return {'revisions': store.history(db, actor.organization_id, 'department', department_id)}


def _decision(db, actor, department_id, payload):
    resources = Resources(actor)
    resources.require('connector', payload.connector_id)
    for kind, identifier in (('agent', payload.agent_id), ('workflow', payload.workflow_id), ('execution', payload.execution_id)):
        if identifier:
            record = resources.require(kind, identifier)
            if getattr(record, 'department_id', None) not in (None, department_id):
                raise HTTPException(404, 'Decision subject is outside the selected department.')
    frozen = None
    if payload.execution_id:
        execution = db.get_workflow_execution(payload.execution_id)
        if execution.department_id != department_id or payload.workflow_id != execution.workflow_id:
            raise HTTPException(422, 'Execution decisions require their exact stored workflow and department.')
        from integrations.tool_scopes import execution_context
        frozen = (execution_context(db, execution.id) or {}).get('governance')
    return decide(db, actor.organization_id, department_id, payload.connector_id, payload.capability_id,
                  payload.resource_id, user_id=actor.user_id, service=bool(actor.service),
                  agent_id=payload.agent_id, workflow_id=payload.workflow_id, purpose=payload.purpose,
                  branch=payload.branch, frozen=frozen)


@router.post('/departments/{department_id}/decisions')
def explain_capability_decision(department_id: str, payload: DecisionRequest, request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id)
    return _decision(db, actor, department_id, payload)


@router.get('/departments/{department_id}/catalog')
def get_effective_capability_catalog(department_id: str, request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id)
    entries = []
    for connector in db.list_mcp_connectors(organization_id=actor.organization_id):
        grant = db.get_department_mcp_access(department_id, connector.id)
        if not grant or not grant.is_active or connector.status != 'CONNECTED':
            continue
        for cap in descriptors().values():
            if not cap.implemented or cap.provider != connector.provider.lower():
                continue
            choices = []
            for resource in configured_resources(connector, cap):
                payload = DecisionRequest(capability_id=cap.id, connector_id=connector.id, resource_id=resource, purpose='authoring')
                authoring = _decision(db, actor, department_id, payload)
                if authoring['decision'] == 'denied':
                    continue
                payload.purpose = 'execution'
                choices.append({'resource_id': resource, 'authoring': authoring,
                                'execution': _decision(db, actor, department_id, payload)})
            if choices:
                entries.append({'connector_id': connector.id, 'capability': cap.public(), 'resources': choices,
                                'provider_verified': False, 'readiness': 'configuration_and_policy_only'})
    return {'schema_version': 1, 'department_id': department_id, 'entries': entries, 'non_executable': True}
