"""Opt-in PostgreSQL attempt ownership; no DatabaseManager or runtime wiring.

Connection factory must yield a new transactional psycopg2 connection, commit on
normal exit, rollback on error, and close it. It must use RealDictCursor, a trusted
DSN and a restricted application role. No SQL/connection fallback is performed.
"""
import secrets
from contextlib import contextmanager
from pathlib import Path

from runner.models import validate_plan


class RunnerConflict(ValueError):
    pass


def connection_factory(dsn):
    """Explicit opt-in DSN; no environment, SQLite or local credential fallback."""
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError('Explicit PostgreSQL DSN required.')

    @contextmanager
    def connect():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor,
                                      connect_timeout=5)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
    return connect


def initialize(connection):
    """Fresh-schema bootstrap only. Caller owns transaction and migration role."""
    with connection.cursor() as cursor:
        cursor.execute(Path(__file__).with_name('runner_postgres_schema.sql').read_text())


class PostgresRunnerJournal:
    def __init__(self, connect):
        self.connect = connect

    @contextmanager
    def transaction(self, org):
        if not isinstance(org, str) or not org or org != org.strip():
            raise RunnerConflict('Exact organization identity required.')
        with self.connect() as connection:
            if connection.autocommit:
                raise RunnerConflict('Journal requires a transactional connection.')
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_org_id', %s, true)", (org,))
                yield cursor

    @staticmethod
    def now(cursor):
        cursor.execute('SELECT floor(extract(epoch FROM clock_timestamp()))::bigint AS now')
        return cursor.fetchone()['now']

    @staticmethod
    def installation(cursor, org, installation, *, exclusive=False):
        lock = 'UPDATE' if exclusive else 'SHARE'
        cursor.execute('SELECT * FROM sandbox_runner_installations '
                       'WHERE organization_id=%s AND installation_id=%s FOR ' + lock,
                       (org, installation))
        row = cursor.fetchone()
        if row is None:
            raise RunnerConflict('Installation not found.')
        return row

    def locked_attempt(self, cursor, org, attempt):
        # Global lock order: installation -> attempt -> effect.
        cursor.execute('SELECT installation_id FROM sandbox_runner_attempts '
                       'WHERE organization_id=%s AND attempt_id=%s', (org, attempt))
        row = cursor.fetchone()
        if row is None:
            raise RunnerConflict('Attempt not found.')
        installation = self.installation(cursor, org, row['installation_id'])
        cursor.execute('SELECT * FROM sandbox_runner_attempts '
                       'WHERE organization_id=%s AND attempt_id=%s FOR UPDATE',
                       (org, attempt))
        return cursor.fetchone(), installation

    def history(self, cursor, row, event, effect_id=None):
        cursor.execute('INSERT INTO sandbox_runner_history '
                       '(organization_id,attempt_id,event,effect_id,owner_epoch,recorded_at) '
                       'VALUES (%s,%s,%s,%s,%s,%s)',
                       (row['organization_id'], row['attempt_id'], event,
                        effect_id, row['owner_epoch'], self.now(cursor)))

    def register_installation(self, org, installation):
        if not org or not installation:
            raise RunnerConflict('Exact installation and organization are required.')
        with self.transaction(org) as cursor:
            cursor.execute('INSERT INTO sandbox_runner_installations '
                           '(organization_id,installation_id) VALUES (%s,%s) '
                           'ON CONFLICT DO NOTHING', (org, installation))

    def get(self, org, attempt):
        """Internal record only; claim tokens must never reach HTTP/log projections."""
        with self.transaction(org) as cursor:
            row, _ = self.locked_attempt(cursor, org, attempt)
            return dict(row)

    def create(self, plan, installation_id, execution_id):
        plan = validate_plan(plan)
        if not execution_id:
            raise RunnerConflict('Execution identity is required.')
        org, attempt = plan.attempt.organization_id, plan.attempt.attempt_id
        with self.transaction(org) as cursor:
            installation = self.installation(cursor, org, installation_id)
            cursor.execute('INSERT INTO sandbox_runner_attempts '
                '(organization_id,attempt_id,installation_id,execution_id,recovery_epoch,'
                'plan_json,plan_sha256,deadline_at,updated_at) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (org, attempt, installation_id, execution_id, installation['recovery_epoch'],
                 plan.model_dump_json(), plan.fingerprint(), plan.deadline_at, self.now(cursor)))
            created = cursor.rowcount == 1
            row, _ = self.locked_attempt(cursor, org, attempt)
            if (row['plan_sha256'], row['installation_id'], row['execution_id']) != (
                    plan.fingerprint(), installation_id, execution_id):
                raise RunnerConflict('Attempt is bound to another immutable plan or scope.')
            if created:
                if not plan.requested_at <= self.now(cursor) < plan.deadline_at:
                    raise RunnerConflict('Attempt is outside its lifetime.')
                self.history(cursor, row, 'CREATED')
            return dict(row)

    def claim(self, org, attempt, revision, lease_seconds):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise RunnerConflict('Lease must be 1..300 seconds.')
        with self.transaction(org) as cursor:
            row, installation = self.locked_attempt(cursor, org, attempt)
            now = self.now(cursor)
            if (row['revision'] != revision or row['revoked'] or
                    row['recovery_epoch'] != installation['recovery_epoch'] or
                    row['deadline_at'] <= now or row['lease_until'] > now or
                    row['operation_state'] != 'IDLE' or
                    row['state'] in {'Stopping', 'Released', 'CleanupFailed'}):
                raise RunnerConflict('Attempt cannot be claimed.')
            cursor.execute('SELECT 1 FROM sandbox_runner_effects WHERE '
                           'organization_id=%s AND attempt_id=%s '
                           "AND state IN ('IN_FLIGHT','UNKNOWN') LIMIT 1", (org, attempt))
            if cursor.fetchone():
                raise RunnerConflict('Unresolved effect prohibits ownership takeover.')
            token = secrets.token_hex(32)
            cursor.execute('UPDATE sandbox_runner_attempts SET owner_epoch=owner_epoch+1,'
                'revision=revision+1,claim_token=%s,lease_until=%s,updated_at=%s '
                'WHERE organization_id=%s AND attempt_id=%s RETURNING *',
                (token, min(now + lease_seconds, row['deadline_at']), now, org, attempt))
            updated = cursor.fetchone()
            self.history(cursor, updated, 'CLAIMED')
            return dict(updated)

    def check_owner(self, cursor, row, installation, token, epoch):
        if (row['revoked'] or row['recovery_epoch'] != installation['recovery_epoch'] or
                row['owner_epoch'] != epoch or not secrets.compare_digest(
                    row['claim_token'] or '', token) or
                min(row['lease_until'], row['deadline_at']) <= self.now(cursor)):
            raise RunnerConflict('Expired, revoked or stale ownership.')

    def renew(self, org, attempt, token, epoch, lease_seconds):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise RunnerConflict('Lease must be 1..300 seconds.')
        with self.transaction(org) as cursor:
            row, installation = self.locked_attempt(cursor, org, attempt)
            self.check_owner(cursor, row, installation, token, epoch)
            now = self.now(cursor)
            cursor.execute('UPDATE sandbox_runner_attempts SET lease_until=%s,'
                'revision=revision+1,updated_at=%s WHERE organization_id=%s '
                'AND attempt_id=%s RETURNING *',
                (min(now + lease_seconds, row['deadline_at']), now, org, attempt))
            updated = dict(cursor.fetchone())
            self.history(cursor, updated, 'LEASE_RENEWED')
            return updated

    def revoke(self, org, attempt):
        with self.transaction(org) as cursor:
            row, _ = self.locked_attempt(cursor, org, attempt)
            if not row['revoked']:
                cursor.execute('UPDATE sandbox_runner_attempts SET revoked=TRUE,'
                    "state='Stopping',revision=revision+1,updated_at=%s "
                    'WHERE organization_id=%s AND attempt_id=%s',
                    (self.now(cursor), org, attempt))
                self.history(cursor, row, 'REVOKED')

    def rotate_recovery_epoch(self, org, installation_id):
        """Explicit post-restore invalidation, never automatic startup behavior."""
        with self.transaction(org) as cursor:
            self.installation(cursor, org, installation_id, exclusive=True)
            cursor.execute('UPDATE sandbox_runner_installations SET '
                'recovery_epoch=recovery_epoch+1 WHERE organization_id=%s '
                'AND installation_id=%s RETURNING recovery_epoch', (org, installation_id))
            epoch = cursor.fetchone()['recovery_epoch']
            cursor.execute('UPDATE sandbox_runner_attempts SET revoked=TRUE,'
                "state='Stopping',revision=revision+1,updated_at=%s "
                'WHERE organization_id=%s AND installation_id=%s RETURNING *',
                (self.now(cursor), org, installation_id))
            rows = cursor.fetchall()
            for row in rows:
                self.history(cursor, row, 'RECOVERY_REVOKED')
            return epoch
