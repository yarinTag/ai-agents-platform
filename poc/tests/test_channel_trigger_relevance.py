"""Real admission and persistence contracts for channel relevance decisions."""
import json

from poc.tests.test_channel_ingress_api import BASE, configure, telegram_headers, telegram_message
from poc.tests.test_generic_governance_api import auth, baseline
from storage import channel_ingress
from workflows.channel_trigger_classification import _claim_decision, _record
from workflows.channel_trigger_dispatch import plan_triggers, reserve_dispatches
from workflows.channel_trigger_rules import RelevanceDecision


def test_relevance_gates_dispatch_and_fences_repeat_classification(baseline):
    db, client = baseline
    connector = configure(client, db, 'telegram')
    response = client.post('/api/v1/governance/channel-bindings', headers=auth(), json={
        'department_id': 'atlas_engineering', 'connector_id': connector, 'provider': 'telegram',
        'channel_id': '12345', 'uses': {'trigger_workflows': True},
    })
    assert response.status_code == 201, response.text
    rule = {'binding_id': response.json()['id'], 'enabled': True, 'matcher': 'keyword',
            'pattern': 'review', 'sender_ids': ['12345'], 'max_runs_per_hour': 1,
            'relevance': {'instructions': 'Only dependency reviews.', 'minimum_confidence': 0.8}}
    metadata = {'channel_trigger': rule, 'channel_trigger_principal': 'atlas_MANAGER'}
    db.create_workflow(id='relevance', name='Relevance', department_id='atlas_engineering',
                       organization_id='atlas', definition_json=json.dumps({'metadata': metadata}))
    with db._get_connection() as conn:
        conn.execute("""INSERT INTO external_identity_links
            (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
            VALUES ('relevance-link','atlas',?,'atlas_OPERATOR','telegram','123456','12345',unixepoch())""",
            (connector,))

    def receive(update_id):
        response = client.post(f'{BASE}/{connector}', headers=telegram_headers(),
                               json=telegram_message(update_id=update_id, message_id=update_id, text='Review dependencies'))
        assert response.status_code == 202, response.text
        return channel_ingress.claim(db)

    first = receive(10)
    assert reserve_dispatches(db, first) == []
    plan, = plan_triggers(db, first, include_unclassified=True)
    assert _claim_decision(db, first, plan)
    assert not _claim_decision(db, first, plan)
    weak = RelevanceDecision(decision='match', reason='relevant', confidence=0.7)
    assert not weak.permits_run(plan.relevance)
    _record(db, plan, 'UNCERTAIN', 'below_confidence_threshold', weak.confidence)
    assert reserve_dispatches(db, first) == []
    assert channel_ingress.settle(db, plan.event_id, first['lease_token'], success=True)

    second = receive(11)
    plan, = plan_triggers(db, second, include_unclassified=True)
    assert _claim_decision(db, second, plan)
    strong = RelevanceDecision(decision='match', reason='relevant', confidence=0.95)
    assert strong.permits_run(plan.relevance)
    _record(db, plan, 'MATCH', strong.reason, strong.confidence)
    execution_id, = reserve_dispatches(db, second)
    assert reserve_dispatches(db, second) == [execution_id]
    assert channel_ingress.settle(db, plan.event_id, second['lease_token'], success=True)

    third = receive(12)
    assert plan_triggers(db, third, include_unclassified=True) == []
    assert reserve_dispatches(db, third) == []
    preview = client.post('/api/v1/workflows/relevance/channel-trigger/preview', headers=auth(), json={
        'rule': rule, 'event': {'event_type': 'MESSAGE', 'channel_id': '12345', 'message_id': 'sample',
                                'sender_id': '12345', 'text': 'Review dependencies'},
    })
    assert preview.json() == {'matched': True, 'parameters': {}, 'requires_classification': True}
    assert len(db.list_workflow_executions('relevance')) == 1


def test_relevance_accepts_reasoning_prefix_and_fenced_json():
    from runtime.direct_outcomes import unwrap_model_json
    from workflows.channel_trigger_rules import RelevanceRule

    output = '<think>Private reasoning</think>\n```json\n{"decision":"match","confidence":0.9,"reason":"relevant"}\n```'
    decision = RelevanceDecision.model_validate_json(unwrap_model_json(output))
    assert decision.permits_run(RelevanceRule(instructions='Dependency reviews only.'))


def test_busy_tool_free_runtime_returns_zero_cost_before_model_setup():
    from types import SimpleNamespace
    from runtime.workflow_chat import infer_tool_free

    # Capacity zero is sufficient to exercise the admission decision.
    # No command builder, credentials, subprocess or provider is available.
    capacity = SimpleNamespace(_shutting_down=False, _processes={}, max_concurrent_runs=0)
    outcome = infer_tool_free(capacity, {}, '', {}, 1, lambda: False, system='')
    assert outcome['cost_usd'] == 0.0
    assert 'busy' in outcome['error']


def test_zero_cost_pre_dispatch_outcome_releases_budget(baseline):
    from types import SimpleNamespace
    from storage.hosted_budget import reserve, settle

    db, _ = baseline
    context = SimpleNamespace(organization_id='atlas', department_id='atlas_engineering',
                              execution_id='classifier-budget', task_id='classifier-budget', model='configured')
    hold = reserve(db, context, 0.1, {'source': 'CONFIGURED_ESTIMATE'})
    settle(db, hold, 0.0, {'input_tokens': 0, 'output_tokens': 0})
    with db._get_connection() as conn:
        row = conn.execute('SELECT state,charged_micros FROM hosted_model_requests WHERE id=?', (hold,)).fetchone()
        assert tuple(row) == ('SETTLED', 0)
