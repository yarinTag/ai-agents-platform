"""Read-only cost projections after execution authorization; no historical repricing."""
import json
from runtime.direct_pricing import totals


def task_cost(events, cost, inputs, outputs):
    calls = [event for event in events if event.get('type') == 'usage' and isinstance(event.get('cost_summary'), dict)]
    if calls:
        return totals(calls)
    # Legacy zero records cannot establish free pricing; preserve uncertainty.
    return {'cost_usd': cost if cost > 0 or not (inputs or outputs) else None,
            'known_cost_usd': cost, 'status': 'estimated' if cost > 0 else
                'unavailable' if inputs or outputs else 'no_usage',
            'complete': cost > 0 or not (inputs or outputs), 'calls': 0,
            'input_tokens': inputs, 'output_tokens': outputs, 'reference_cost_usd': None}


def execution_costs(db, execution_id):
    with db._get_connection() as connection:
        rows = connection.execute('''SELECT s.id, t.events, t.cost_usd, t.input_tokens, t.output_tokens
            FROM workflow_step_runs s LEFT JOIN task_runs t ON t.run_id=s.task_run_id
            WHERE s.execution_id=?''', (execution_id,)).fetchall()
    summaries = {}
    for row in rows:
        events = json.loads(row['events'] or '[]')
        summary = task_cost(events, row['cost_usd'] or 0, row['input_tokens'] or 0, row['output_tokens'] or 0)
        session = next((event.get('session_cost_summary') for event in reversed(events)
                        if isinstance(event.get('session_cost_summary'), dict)), None)
        summaries[row['id']] = {'cost_summary': summary, 'session_cost_summary': session}
    values = [value['cost_summary'] for value in summaries.values()]
    complete = all(value['complete'] for value in values)
    known = sum(value['known_cost_usd'] for value in values)
    active = [value for value in values if value['status'] != 'no_usage']
    reference = [value['reference_cost_usd'] for value in active]
    return {'cost_usd': known if complete else None, 'known_cost_usd': known,
            'status': 'unavailable' if not complete else 'no_usage' if not active else
                'free' if known == 0 else 'estimated' if any(value['status'] == 'estimated' for value in active) else 'reported',
            'complete': complete,
            'reference_cost_usd': sum(reference) if reference and all(v is not None for v in reference) else None}, summaries
