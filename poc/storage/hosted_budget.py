"""Durable, conservative per-request reservations for hosted model requests.

Reservations never auto-expire: a crash after dispatch has an unknown paid outcome.
Usage is integer micro-USD, with pricing provenance kept per call.
"""
import json
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_CEILING


def micros(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError('Hosted pricing must be finite and non-negative.')
    return int((number * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS hosted_model_requests (
        id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, department_id TEXT NOT NULL,
        execution_id TEXT NOT NULL, task_id TEXT NOT NULL, model TEXT NOT NULL,
        reserved_micros INTEGER NOT NULL CHECK(reserved_micros>=0),
        charged_micros INTEGER, state TEXT NOT NULL CHECK(state IN ('RESERVED','SETTLED','UNKNOWN')),
        pricing_json TEXT NOT NULL, usage_json TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
        FOREIGN KEY(department_id) REFERENCES departments(id) ON DELETE CASCADE)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_hosted_budget ON hosted_model_requests(department_id,created_at)')


def outstanding(conn, department_id, month):
    """Settled ledger cost not already included in workflow aggregate costs."""
    rows = conn.execute("""SELECT r.execution_id,
        SUM(COALESCE(r.charged_micros,0)) AS ledger,
        COALESCE(e.total_cost_usd,0) AS booked, e.created_at AS execution_created
        FROM hosted_model_requests r LEFT JOIN workflow_executions e ON e.id=r.execution_id
        WHERE r.department_id=? AND r.created_at LIKE ? GROUP BY r.execution_id""",
        (department_id, month)).fetchall()
    return sum(max(0, int(row['ledger']) - (micros(row['booked'])
        if str(row['execution_created'] or '').startswith(month[:-1]) else 0)) for row in rows)


def reserved_total(conn, department_id, month):
    row = conn.execute("""SELECT COALESCE(SUM(reserved_micros),0) AS total
        FROM hosted_model_requests WHERE department_id=? AND created_at LIKE ?
        AND state IN ('RESERVED','UNKNOWN')""", (department_id, month)).fetchone()
    return int(row['total'])


def reserve(db, context, amount_usd, pricing):
    amount = micros(amount_usd)
    now = datetime.now().isoformat()
    identity = 'hosted_call_' + uuid.uuid4().hex
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        department = conn.execute('SELECT organization_id,monthly_budget_usd FROM departments WHERE id=?',
                                  (context.department_id,)).fetchone()
        if not department or department['organization_id'] != context.organization_id:
            raise ValueError('Hosted department budget context is invalid.')
        booked = micros(db.get_department_monthly_spend(context.department_id))
        held = reserved_total(conn, context.department_id, now[:7] + '%')
        if booked + held + amount >= micros(department['monthly_budget_usd']):
            raise ValueError('Department budget cannot reserve another hosted model request.')
        conn.execute('''INSERT INTO hosted_model_requests
            (id,organization_id,department_id,execution_id,task_id,model,reserved_micros,state,pricing_json,created_at)
            VALUES(?,?,?,?,?,?,?,'RESERVED',?,?)''', (identity, context.organization_id, context.department_id,
            context.execution_id, context.task_id, context.model, amount, json.dumps(pricing), now))
    return identity


def settle(db, identity, actual_usd=None, usage=None):
    """Unknown outcomes retain their entire reservation; settlement is repeat-safe."""
    charge = micros(actual_usd) if actual_usd is not None else None
    with db._get_connection() as conn:
        conn.execute('''UPDATE hosted_model_requests SET state=?,charged_micros=?,usage_json=?
            WHERE id=? AND state='RESERVED' ''', ('UNKNOWN' if charge is None else 'SETTLED', charge,
            json.dumps(usage) if usage is not None else None, identity))


def task_usage(db, task_id):
    with db._get_connection() as conn:
        rows = conn.execute('SELECT charged_micros,reserved_micros,usage_json,state FROM hosted_model_requests '
                            'WHERE task_id=?', (task_id,)).fetchall()
    usages = [json.loads(row['usage_json']) for row in rows if row['usage_json']]
    return {'input_tokens': sum(u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0)
            + u.get('cache_creation_input_tokens', 0) for u in usages),
        'output_tokens': sum(u.get('output_tokens', 0) for u in usages),
        'cost_usd': sum(row['charged_micros'] or 0 for row in rows) / 1_000_000,
        'reserved_usd': sum(row['reserved_micros'] for row in rows if row['charged_micros'] is None) / 1_000_000,
        'uncertain': any(row['state'] != 'SETTLED' for row in rows), 'calls': len(rows)}


def execution_settled(db, execution_id):
    """This execution's already-accounted hosted usage in the current budget period."""
    with db._get_connection() as conn:
        row = conn.execute("""SELECT COALESCE(SUM(charged_micros),0) AS total FROM hosted_model_requests
            WHERE execution_id=? AND state='SETTLED' AND created_at LIKE ?""",
            (execution_id, datetime.now().strftime('%Y-%m') + '%')).fetchone()
    return int(row['total']) / 1_000_000
