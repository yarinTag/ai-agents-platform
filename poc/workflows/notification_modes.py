"""Lifecycle notification modes; legacy completion-only bindings remain readable."""
MODES = {'NONE', 'COMPLETION_ONLY', 'START_AND_COMPLETE', 'EACH_STEP',
         'ON_COMPLETE', 'ON_FAILURE', 'ALWAYS'}
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED'}


def should_notify(mode, event, status):
    if event == 'start':
        return mode in ('START_AND_COMPLETE', 'EACH_STEP')
    if event.startswith('step:'):
        return mode == 'EACH_STEP'
    if event != 'complete':
        return False
    if mode in ('COMPLETION_ONLY', 'START_AND_COMPLETE', 'EACH_STEP'):
        return status in TERMINAL
    return (mode == 'ALWAYS' or mode == 'ON_COMPLETE' and status == 'COMPLETED'
            or mode == 'ON_FAILURE' and status == 'FAILED')
