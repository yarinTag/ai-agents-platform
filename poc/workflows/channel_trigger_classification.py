"""Run one metered, tool-free relevance request per eligible event/workflow."""
import time
from types import SimpleNamespace

from runtime.channel_relevance import MAX_OUTPUT_TOKENS, infer_relevance
from runtime.direct_pricing import pricing
from storage.hosted_budget import reserve, settle

from .channel_trigger_dispatch import plan_triggers
from .channel_trigger_rules import RelevanceDecision

MAX_CLASSIFIERS_PER_EVENT = 4
MAX_INPUT_TOKENS = 16384


def _lease(conn, claim):
    return conn.execute("""SELECT 1 FROM channel_ingress_outbox WHERE event_id=?
        AND lease_token=? AND status='PROCESSING' AND lease_until>?""",
        (claim['event']['id'], claim['lease_token'], int(time.time()))).fetchone()


def _claim_decision(db, claim, plan):
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not _lease(conn, claim) or plan not in plan_triggers(db, claim, connection=conn, include_unclassified=True):
            return False
        attempts = conn.execute("""SELECT count(*) FROM channel_trigger_classifications
            WHERE event_id=? AND reason<>'event_classifier_limit'""", (plan.event_id,)).fetchone()[0]
        allowed = attempts < MAX_CLASSIFIERS_PER_EVENT
        state, reason = ('STARTED', 'inference_pending') if allowed else ('ERROR', 'event_classifier_limit')
        inserted = conn.execute("""INSERT INTO channel_trigger_classifications
            (event_id,workflow_id,workflow_revision,binding_id,sender_user_id,principal_id,state,reason,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id,workflow_id) DO NOTHING""",
            (plan.event_id, plan.workflow_id, plan.revision, plan.binding_id,
             plan.sender_user_id, plan.principal_id, state, reason, int(time.time()))).rowcount
        return allowed and bool(inserted)


def _record(db, plan, state, reason, confidence=None, selected=None):
    selected = selected or {}
    with db._get_connection() as conn:
        conn.execute("""UPDATE channel_trigger_classifications SET state=?,reason=?,confidence=?,
            model=?,provider=?,updated_at=? WHERE event_id=? AND workflow_id=? AND state='STARTED'""",
            (state, reason, confidence, selected.get('model_id'), selected.get('provider_id'),
             int(time.time()), plan.event_id, plan.workflow_id))


def classify(db, runtime, claim):
    candidates = [plan for plan in plan_triggers(db, claim, include_unclassified=True) if plan.relevance]
    for plan in candidates:
        if not _claim_decision(db, claim, plan):
            continue
        if not runtime or not hasattr(runtime, 'workflow_chat_selection'):
            _record(db, plan, 'ERROR', 'model_unavailable')
            continue
        _evaluate(db, runtime, claim, plan)


def _evaluate(db, runtime, claim, plan):
    workflow = db.get_workflow(plan.workflow_id)
    selected = None
    hold = None

    def cancelled():
        with db._get_connection() as conn:
            return not _lease(conn, claim)

    try:
        if not workflow or workflow.revision != plan.revision or cancelled():
            _record(db, plan, 'ERROR', 'admission_changed')
            return
        selected = runtime.workflow_chat_selection(workflow.organization_id)
        from runtime.direct_config import DIRECT_PROVIDERS
        if selected['provider_id'] not in DIRECT_PROVIDERS or selected['cost_source'] != 'API_KEY':
            _record(db, plan, 'ERROR', 'model_unavailable')
            return
        price = pricing(selected['provider_id'], selected['model_id'])
        if price['rates'] is None:
            _record(db, plan, 'ERROR', 'pricing_unavailable', selected=selected)
            return
        input_rate, output_rate = price['rates']
        budget = (MAX_INPUT_TOKENS * input_rate + MAX_OUTPUT_TOKENS * output_rate) / 1_000_000
        key = f'channel_relevance:{plan.event_id}:{plan.workflow_id}'
        context = SimpleNamespace(organization_id=workflow.organization_id, department_id=workflow.department_id,
                                  execution_id=key, task_id=key, model=selected['model_id'])
        try:
            hold = reserve(db, context, budget, price)
        except ValueError:
            _record(db, plan, 'ERROR', 'budget_unavailable', selected=selected)
            return
        if cancelled() or plan not in plan_triggers(db, claim, include_unclassified=True):
            settle(db, hold, 0)
            _record(db, plan, 'ERROR', 'admission_changed', selected=selected)
            return
        result = infer_relevance(runtime, selected, plan.relevance, claim['trigger_text'], budget, cancelled)
        settle(db, hold, result.get('cost_usd'), {key: result.get(key) for key in ('input_tokens', 'output_tokens')})
        if result.get('error') or cancelled():
            _record(db, plan, 'ERROR', 'inference_unavailable', selected=selected)
            return
        output = result.get('output')
        decision = RelevanceDecision.model_validate_json(output) if isinstance(output, str) else RelevanceDecision.model_validate(output)
        state = 'MATCH' if decision.permits_run(plan.relevance) else (
            'NO_MATCH' if decision.decision == 'no_match' else 'UNCERTAIN')
        reason = 'below_confidence_threshold' if state == 'UNCERTAIN' and decision.decision == 'match' else decision.reason
        _record(db, plan, state, reason, decision.confidence, selected)
    except (TypeError, ValueError, KeyError, AttributeError):
        if hold:
            settle(db, hold)
        _record(db, plan, 'ERROR', 'invalid_model_or_result', selected=selected)
