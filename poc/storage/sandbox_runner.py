"""Opt-in durable runner journal. Not wired into DatabaseManager or startup.

Uses an injected transactional connection factory; no global DB or cluster client.
Claims are never automatically replayed after ambiguous effects or lease expiry.
"""
import json
import secrets
import time

from runner.models import OwnedResource, RunnerPlan, validate_plan
from governance.sandbox_manifests import build_sandbox_bundle


class RunnerConflict(ValueError):
    pass


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS sandbox_runner_attempts (
        organization_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
        plan_json TEXT NOT NULL, plan_sha256 TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN
          ('Requested','Preparing','Ready','Running','Stopping','Released','CleanupFailed')),
        revision INTEGER NOT NULL, revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),
        operation TEXT CHECK(operation IN ('Provision','Start','Stop','Delete')),
        operation_state TEXT NOT NULL CHECK(operation_state IN ('IDLE','STARTED','UNKNOWN')),
        claim_token TEXT, resources_json TEXT NOT NULL,
        reason TEXT NOT NULL, updated_at INTEGER NOT NULL,
        PRIMARY KEY(organization_id, attempt_id)
    )""")


class RunnerJournal:
    def __init__(self, connect):
        self.connect = connect

    def create(self, plan: RunnerPlan):
        plan = validate_plan(plan)
        scope = (plan.attempt.organization_id, plan.attempt.attempt_id)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, scope, required=False)
            if row:
                if row['plan_sha256'] != plan.fingerprint():
                    raise RunnerConflict('Attempt ID is already bound to a different plan.')
                return dict(row)
            now = int(time.time())
            if not plan.requested_at <= now < plan.deadline_at:
                raise RunnerConflict('Attempt plan is outside its lifetime.')
            conn.execute("""INSERT INTO sandbox_runner_attempts VALUES
                (?,?,?,?,'Requested',1,0,NULL,'IDLE',NULL,'[]','CREATED',?)""",
                (*scope, plan.model_dump_json(), plan.fingerprint(), now))
            return dict(self._row(conn, scope))

    @staticmethod
    def _row(conn, scope, required=True):
        row = conn.execute('SELECT * FROM sandbox_runner_attempts '
                           'WHERE organization_id=? AND attempt_id=?', scope).fetchone()
        if required and row is None:
            raise RunnerConflict('Attempt not found in organization.')
        return row

    def get(self, organization_id, attempt_id):
        with self.connect() as conn:
            return dict(self._row(conn, (organization_id, attempt_id)))

    def claim(self, organization_id, attempt_id, revision, operation):
        allowed = {'Provision': {'Requested'}, 'Start': {'Ready'},
                   'Stop': {'Stopping'}, 'Delete': {'Stopping', 'CleanupFailed'}}
        if operation not in allowed:
            raise RunnerConflict('Unsupported runner operation.')
        scope = (organization_id, attempt_id)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, scope)
            plan = RunnerPlan.model_validate_json(row['plan_json'])
            if row['revision'] != revision or row['operation_state'] != 'IDLE':
                raise RunnerConflict('Stale revision or outstanding operation.')
            if row['state'] not in allowed[operation]:
                raise RunnerConflict('Operation is invalid in the current state.')
            if operation in {'Provision', 'Start'} and (
                    row['revoked'] or int(time.time()) >= plan.deadline_at):
                raise RunnerConflict('Attempt is revoked or expired.')
            token = secrets.token_hex(32)
            state = 'Preparing' if operation == 'Provision' else row['state']
            conn.execute("""UPDATE sandbox_runner_attempts SET state=?,operation=?,
                operation_state='STARTED',claim_token=?,revision=revision+1,updated_at=?
                WHERE organization_id=? AND attempt_id=?""",
                (state, operation, token, int(time.time()), *scope))
            return token

    def record_resource(self, organization_id, attempt_id, token, resource: OwnedResource):
        """Persist each acknowledged UID immediately, including a late response after stop."""
        resource = OwnedResource.model_validate(resource.model_dump())
        scope = (organization_id, attempt_id)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, scope)
            self._claim_matches(row, token, allow_unknown=True)
            if row['operation'] not in {'Provision', 'Start'}:
                raise RunnerConflict('This claim cannot create resources.')
            plan = RunnerPlan.model_validate_json(row['plan_json'])
            expected = {(item['kind'], item['metadata']['name']) for item in
                        build_sandbox_bundle(plan.profile, plan.attempt)}
            if (resource.kind, resource.name) not in expected or (
                    (resource.kind == 'Job') != (row['operation'] == 'Start')):
                raise RunnerConflict('Resource does not belong to this operation plan.')
            resources = json.loads(row['resources_json'])
            for old in resources:
                if old['kind'] == resource.kind and old['name'] == resource.name:
                    if old['uid'] != resource.uid:
                        raise RunnerConflict('Resource name was replaced with another UID.')
                    return
            resources.append(resource.model_dump())
            if len(resources) > 5:
                raise RunnerConflict('Unexpected runner resource count.')
            conn.execute("""UPDATE sandbox_runner_attempts SET resources_json=?,
                revision=revision+1,updated_at=? WHERE organization_id=? AND attempt_id=?""",
                (json.dumps(resources), int(time.time()), *scope))

    @staticmethod
    def _claim_matches(row, token, *, allow_unknown=False):
        states = {'STARTED', 'UNKNOWN'} if allow_unknown else {'STARTED'}
        if row['operation_state'] not in states or not secrets.compare_digest(
                row['claim_token'] or '', token):
            raise RunnerConflict('No matching active operation claim.')

    def finish(self, organization_id, attempt_id, token, *, outcome):
        """Close a definitely completed or definitely unsent operation.

        This source slice deliberately cannot assert Ready/Running/Released from
        a caller boolean. Successful mutation receipts need the future adapter.
        """
        if outcome not in {'NOT_DISPATCHED', 'UNKNOWN'}:
            raise RunnerConflict('Verified adapter completion is not implemented.')
        scope = (organization_id, attempt_id)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, scope)
            self._claim_matches(row, token)
            resources = json.loads(row['resources_json'])
            if outcome == 'NOT_DISPATCHED' and resources:
                raise RunnerConflict('Recorded effects cannot be declared not dispatched.')
            unknown = outcome == 'UNKNOWN'
            state = 'CleanupFailed' if unknown else row['state']
            if not unknown and row['operation'] == 'Provision' and state == 'Preparing':
                state = 'Requested'
            conn.execute("""UPDATE sandbox_runner_attempts SET state=?,
                operation_state=?,claim_token=?,operation=?,reason=?,
                revoked=CASE WHEN ? THEN 1 ELSE revoked END,
                revision=revision+1,updated_at=? WHERE organization_id=? AND attempt_id=?""",
                (state, 'UNKNOWN' if unknown else 'IDLE', token if unknown else None,
                 row['operation'] if unknown else None, outcome, unknown,
                 int(time.time()), *scope))

    def request_stop(self, organization_id, attempt_id):
        """Revoke before cleanup; retain in-flight/unknown claims and recorded UIDs."""
        scope = (organization_id, attempt_id)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, scope)
            if row['state'] in {'Released', 'Stopping'}:
                return dict(row)
            conn.execute("""UPDATE sandbox_runner_attempts SET state='Stopping',revoked=1,
                reason='STOP_REQUESTED',revision=revision+1,updated_at=?
                WHERE organization_id=? AND attempt_id=?""", (int(time.time()), *scope))
            return dict(self._row(conn, scope))
