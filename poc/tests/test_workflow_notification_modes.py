"""Pure lifecycle selection/idempotency contracts; no delivery or runtime calls."""
from workflows.notification_modes import should_notify
from integrations.notification_guard import notification_call_id


def test_completion_only_covers_all_terminal_states_without_progress():
    for status in ('COMPLETED', 'FAILED', 'CANCELLED'):
        assert should_notify('COMPLETION_ONLY', 'complete', status)
    assert not should_notify('COMPLETION_ONLY', 'start', 'RUNNING')
    assert not should_notify('COMPLETION_ONLY', 'step:work', 'COMPLETED')
    assert not should_notify('COMPLETION_ONLY', 'complete', 'WAITING_INPUT')


def test_start_complete_and_each_step_have_distinct_scope():
    assert should_notify('START_AND_COMPLETE', 'start', 'RUNNING')
    assert should_notify('START_AND_COMPLETE', 'complete', 'FAILED')
    assert not should_notify('START_AND_COMPLETE', 'step:work', 'COMPLETED')
    assert should_notify('EACH_STEP', 'start', 'RUNNING')
    assert should_notify('EACH_STEP', 'step:work', 'COMPLETED')
    assert should_notify('EACH_STEP', 'step:work', 'FAILED')
    assert should_notify('EACH_STEP', 'complete', 'FAILED')
    for event in ('start', 'step:work', 'complete'):
        assert not should_notify('NONE', event, 'COMPLETED')


def test_legacy_completion_modes_remain_compatible():
    assert should_notify('ON_COMPLETE', 'complete', 'COMPLETED')
    assert not should_notify('ON_COMPLETE', 'complete', 'FAILED')
    assert should_notify('ON_FAILURE', 'complete', 'FAILED')
    assert not should_notify('ON_FAILURE', 'complete', 'COMPLETED')
    assert should_notify('ALWAYS', 'complete', 'WAITING_INPUT')
    assert not should_notify('ALWAYS', 'step:work', 'COMPLETED')


def test_notification_claims_are_unique_per_run_and_event():
    assert notification_call_id('run-a') == 'call_notify_run-a'
    assert notification_call_id('run-a', 'step:one') == notification_call_id('run-a', 'step:one')
    claims = {notification_call_id('run-a', event) for event in ('start', 'step:one', 'step:two', 'complete')}
    assert len(claims) == 4
    assert notification_call_id('run-a', 'step:one') != notification_call_id('run-b', 'step:one')
