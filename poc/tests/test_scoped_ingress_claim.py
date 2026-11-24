"""Exact-event operational claims never advance or clean unrelated durable jobs."""
import time

from poc.tests.test_generic_governance_api import baseline
from poc.tests.test_channel_ingress_api import configure, telegram_message, telegram_headers
from storage import channel_ingress
from backend.channel_trigger_worker import consume_one
from workflows.engine import WorkflowEngine


def test_exact_claim_preserves_other_jobs_and_expired_inputs(baseline):
    db, client = baseline
    connector = configure(client, db, 'telegram')
    for index in (1, 2, 3):
        response = client.post('/api/v1/channel-ingress/' + connector,
            json=telegram_message(index, index), headers=telegram_headers())
        assert response.status_code == 202
    now = int(time.time())
    with db._get_connection() as conn:
        ids = [row[0] for row in conn.execute('SELECT id FROM channel_ingress_events ORDER BY message_id')]
        for identifier in ids:
            conn.execute('INSERT INTO channel_ingress_trigger_inputs VALUES (?,?,?)', (identifier, 'expired fixture', now - 1))
        conn.execute("UPDATE channel_ingress_outbox SET status='PROCESSING',attempts=?,lease_token='old',lease_until=? WHERE event_id=?",
                     (channel_ingress.MAX_ATTEMPTS, now - 1, ids[2]))
        before = [tuple(row) for row in conn.execute('SELECT * FROM channel_ingress_outbox WHERE event_id<>? ORDER BY event_id', (ids[1],))]
    claim = channel_ingress.claim(db, now, event_id=ids[1])
    assert claim['event']['id'] == ids[1] and claim['trigger_text'] is None
    with db._get_connection() as conn:
        assert [tuple(row) for row in conn.execute('SELECT * FROM channel_ingress_outbox WHERE event_id<>? ORDER BY event_id', (ids[1],))] == before
        assert {row[0] for row in conn.execute('SELECT event_id FROM channel_ingress_trigger_inputs')} == {ids[0], ids[2]}
    assert channel_ingress.claim(db, now, event_id='missing') is None
    assert channel_ingress.settle(db, ids[1], claim['lease_token'], success=True, now=now)
    assert channel_ingress.claim(db, now, event_id=ids[1]) is None
    # Default consumer behavior remains global, including exhausted-lease cleanup.
    assert channel_ingress.claim(db, now)['event']['id'] == ids[0]
    with db._get_connection() as conn:
        assert conn.execute('SELECT status FROM channel_ingress_outbox WHERE event_id=?', (ids[2],)).fetchone()[0] == 'FAILED'


def test_exact_worker_does_not_claim_other_pending_events(baseline):
    db, client = baseline
    connector = configure(client, db, 'telegram')
    for index in (10, 11):
        assert client.post('/api/v1/channel-ingress/' + connector,
            json=telegram_message(index, index), headers=telegram_headers()).status_code == 202
    with db._get_connection() as conn:
        target = conn.execute("SELECT id FROM channel_ingress_events WHERE message_id='11'").fetchone()[0]
        other = conn.execute("SELECT id FROM channel_ingress_events WHERE message_id='10'").fetchone()[0]
        before = tuple(conn.execute('SELECT * FROM channel_ingress_outbox WHERE event_id=?', (other,)).fetchone())
    assert consume_one(WorkflowEngine(db_manager=db), event_id=target)
    assert not consume_one(WorkflowEngine(db_manager=db), event_id=target)
    with db._get_connection() as conn:
        assert tuple(conn.execute('SELECT * FROM channel_ingress_outbox WHERE event_id=?', (other,)).fetchone()) == before
        assert conn.execute('SELECT status FROM channel_ingress_outbox WHERE event_id=?', (target,)).fetchone()[0] == 'COMPLETED'
