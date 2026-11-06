"""Fail-closed I/O policy for explicitly authorized, in-process API-only audits.

This does not fake provider/runtime responses. Any attempted external network access
or child process fails the test. Load with -p before collecting audit test modules.
"""
import os
import sys

os.environ['PLATFORM_DISABLED_CAPABILITIES'] = 'runtime,scheduler-worker,intelligence,notifications'
os.environ['ALLOW_UNAUTHENTICATED_DEV'] = 'false'
os.environ['PLATFORM_API_AUDIT_GUARD'] = '1'


def _deny_external_io(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
        raise RuntimeError('API-only audit forbids provider/network calls and child processes.')


sys.addaudithook(_deny_external_io)
