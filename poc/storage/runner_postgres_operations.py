"""Durable provisioning intents only; no Kubernetes transport or success assertions."""
import json
import secrets

from governance.sandbox_manifests import build_sandbox_bundle
from runner.models import OwnedResource, RunnerPlan
from .runner_postgres import RunnerConflict


class PostgresRunnerOperations:
    """Separate operation receipts from renewable controller ownership tokens.

    Provision/Start intent claims require current ownership and exact revision.
    UNKNOWN is permanently fenced; late UID evidence cannot authorize execution.
    Cleanup claims and verified Ready/Running/Released transitions remain absent.
    """
    def __init__(self, journal):
        self.journal = journal

    @staticmethod
    def _matches(row, token, *, late=False):
        states = {'STARTED', 'UNKNOWN'} if late else {'STARTED'}
        if (not isinstance(token, str) or row['operation_state'] not in states
                or not secrets.compare_digest(row['operation_token'] or '', token)):
            raise RunnerConflict('No matching operation claim.')

    def begin(self, org, attempt, owner_token, owner_epoch, revision, operation):
        allowed = {'Provision': 'Requested', 'Start': 'Ready'}
        if operation not in allowed:
            raise RunnerConflict('Cleanup and verified transitions are not implemented.')
        j = self.journal
        with j.transaction(org) as cursor:
            row, installation = j.locked_attempt(cursor, org, attempt)
            j.check_owner(cursor, row, installation, owner_token, owner_epoch)
            if (type(revision) is not int or row['revision'] != revision
                    or row['operation_state'] != 'IDLE' or row['state'] != allowed[operation]):
                raise RunnerConflict('Stale revision, invalid state or outstanding operation.')
            token = secrets.token_hex(32)
            state = 'Preparing' if operation == 'Provision' else row['state']
            cursor.execute("UPDATE sandbox_runner_attempts SET operation=%s,operation_state='STARTED',"
                'operation_token=%s,state=%s,revision=revision+1,updated_at=%s '
                'WHERE organization_id=%s AND attempt_id=%s RETURNING *',
                (operation, token, state, j.now(cursor), org, attempt))
            updated = dict(cursor.fetchone())
            j.history(cursor, updated, 'OPERATION_STARTED')
            return updated

    def record_resource(self, org, attempt, operation_token, resource):
        """Retain exact acknowledged UIDs, even after expiry/revoke/recovery."""
        if not isinstance(resource, OwnedResource):
            raise RunnerConflict('A validated resource receipt is required.')
        resource = OwnedResource.model_validate(resource.model_dump())
        j = self.journal
        with j.transaction(org) as cursor:
            row, _ = j.locked_attempt(cursor, org, attempt)
            self._matches(row, operation_token, late=True)
            plan = RunnerPlan.model_validate_json(row['plan_json'])
            expected = {(item['kind'], item['metadata']['name']) for item in
                        build_sandbox_bundle(plan.profile, plan.attempt)}
            if ((resource.kind, resource.name) not in expected
                    or row['operation'] not in {'Provision', 'Start'}
                    or (resource.kind == 'Job') != (row['operation'] == 'Start')):
                raise RunnerConflict('Resource is outside the exact operation plan.')
            resources = json.loads(row['resources_json'])
            for previous in resources:
                if (previous['kind'], previous['name']) == (resource.kind, resource.name):
                    if previous['uid'] != resource.uid:
                        raise RunnerConflict('Resource name has another UID.')
                    return dict(row)
            if len(resources) >= 5:
                raise RunnerConflict('Unexpected runner resource count.')
            resources.append(resource.model_dump())
            cursor.execute('UPDATE sandbox_runner_attempts SET resources_json=%s,'
                'revision=revision+1,updated_at=%s WHERE organization_id=%s '
                'AND attempt_id=%s RETURNING *',
                (json.dumps(resources, sort_keys=True), j.now(cursor), org, attempt))
            updated = dict(cursor.fetchone())
            j.history(cursor, updated, 'RESOURCE_ACKNOWLEDGED')
            return updated

    def finish(self, org, attempt, operation_token, *, outcome):
        """No boolean can assert that a cluster is Ready, Running or Released."""
        if outcome not in {'NOT_DISPATCHED', 'UNKNOWN'}:
            raise RunnerConflict('Verified adapter completion is not implemented.')
        j = self.journal
        with j.transaction(org) as cursor:
            row, _ = j.locked_attempt(cursor, org, attempt)
            self._matches(row, operation_token)
            resources = json.loads(row['resources_json'])
            owned = [item for item in resources if (item['kind'] == 'Job') == (row['operation'] == 'Start')]
            if outcome == 'NOT_DISPATCHED' and owned:
                raise RunnerConflict('Acknowledged resources cannot be declared not dispatched.')
            unknown = outcome == 'UNKNOWN'
            state = 'CleanupFailed' if unknown else row['state']
            if not unknown and row['operation'] == 'Provision' and state == 'Preparing':
                state = 'Requested'
            cursor.execute('UPDATE sandbox_runner_attempts SET state=%s,operation_state=%s,'
                'operation=%s,operation_token=%s,revoked=(revoked OR %s),reason=%s,'
                'revision=revision+1,updated_at=%s WHERE organization_id=%s AND attempt_id=%s RETURNING *',
                (state, 'UNKNOWN' if unknown else 'IDLE', row['operation'] if unknown else None,
                 operation_token if unknown else None, unknown, outcome, j.now(cursor), org, attempt))
            updated = dict(cursor.fetchone())
            j.history(cursor, updated, 'OPERATION_' + outcome)
            return updated
