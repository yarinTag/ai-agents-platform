"""Logical effect journal sharing the Runner's PostgreSQL transaction authority."""
import json
import re
import secrets

from .runner_postgres import RunnerConflict


class PostgresRunnerEffects:
    def __init__(self, journal):
        self.journal = journal

    @staticmethod
    def effect(cursor, org, execution, effect_id):
        cursor.execute('SELECT * FROM sandbox_runner_effects WHERE organization_id=%s '
            'AND execution_id=%s AND effect_id=%s FOR UPDATE', (org, execution, effect_id))
        row = cursor.fetchone()
        if row is None:
            raise RunnerConflict('Effect not found.')
        return row

    def reserve(self, org, attempt, token, epoch, effect_id, request_sha256):
        if (not isinstance(effect_id, str) or not re.fullmatch(
                r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}', effect_id) or
                not isinstance(request_sha256, str) or not re.fullmatch(
                    r'[0-9a-f]{64}', request_sha256)):
            raise RunnerConflict('Exact logical effect ID and request digest required.')
        j = self.journal
        with j.transaction(org) as cursor:
            row, installation = j.locked_attempt(cursor, org, attempt)
            j.check_owner(cursor, row, installation, token, epoch)
            cursor.execute('INSERT INTO sandbox_runner_effects '
                '(organization_id,execution_id,effect_id,attempt_id,request_sha256,'
                'owner_epoch,recovery_epoch,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) '
                'ON CONFLICT DO NOTHING',
                (org, row['execution_id'], effect_id, attempt, request_sha256,
                 epoch, row['recovery_epoch'], j.now(cursor)))
            created = cursor.rowcount == 1
            effect = self.effect(cursor, org, row['execution_id'], effect_id)
            if effect['request_sha256'] != request_sha256:
                raise RunnerConflict('Logical effect ID is bound to another request.')
            if created:
                j.history(cursor, row, 'EFFECT_RESERVED', effect_id)
            # Returning an existing record never authorizes another dispatch.
            return dict(effect)

    def begin(self, org, attempt, token, epoch, effect_id):
        """Persist uncertainty BEFORE the broker sends; only INTENT can begin."""
        j = self.journal
        with j.transaction(org) as cursor:
            row, installation = j.locked_attempt(cursor, org, attempt)
            j.check_owner(cursor, row, installation, token, epoch)
            effect = self.effect(cursor, org, row['execution_id'], effect_id)
            if (effect['state'] != 'INTENT' or effect['attempt_id'] != attempt or
                    effect['owner_epoch'] != epoch or
                    effect['recovery_epoch'] != installation['recovery_epoch']):
                raise RunnerConflict('Effect cannot be dispatched again.')
            cursor.execute("UPDATE sandbox_runner_effects SET state='IN_FLIGHT',"
                'revision=revision+1,updated_at=%s WHERE organization_id=%s '
                'AND execution_id=%s AND effect_id=%s RETURNING *',
                (j.now(cursor), org, row['execution_id'], effect_id))
            updated = dict(cursor.fetchone())
            j.history(cursor, row, 'EFFECT_DISPATCH_STARTED', effect_id)
            return updated

    def settle(self, org, attempt, token, epoch, effect_id, outcome, receipt=None):
        """Trusted broker receipts only; late evidence never grants new authority.

        FAILED requires definitive rejection, not an exception or timeout.
        UNKNOWN -> terminal accepts a late authenticated result. No reset to INTENT.
        """
        if outcome not in {'SUCCEEDED', 'FAILED', 'UNKNOWN'}:
            raise RunnerConflict('Unsupported effect outcome.')
        if outcome == 'UNKNOWN':
            if receipt is not None:
                raise RunnerConflict('Unknown outcome has no terminal receipt.')
            encoded = None
        else:
            if not isinstance(receipt, dict) or not receipt:
                raise RunnerConflict('Terminal outcome requires a broker receipt.')
            encoded = json.dumps(receipt, sort_keys=True, separators=(',', ':'),
                                 allow_nan=False)
            if len(encoded.encode()) > 16384:
                raise RunnerConflict('Receipt exceeds storage limit.')
        j = self.journal
        with j.transaction(org) as cursor:
            row, _ = j.locked_attempt(cursor, org, attempt)
            effect = self.effect(cursor, org, row['execution_id'], effect_id)
            if (effect['attempt_id'] != attempt or effect['owner_epoch'] != epoch or
                    not secrets.compare_digest(row['claim_token'] or '', token)):
                raise RunnerConflict('Receipt does not match the original claim.')
            if effect['state'] in {'SUCCEEDED', 'FAILED'}:
                if (effect['state'], effect['receipt_json']) != (outcome, encoded):
                    raise RunnerConflict('Terminal receipt is immutable.')
                return dict(effect)
            if effect['state'] not in {'IN_FLIGHT', 'UNKNOWN'}:
                raise RunnerConflict('Undispatched intent has no provider outcome.')
            cursor.execute('UPDATE sandbox_runner_effects SET state=%s,receipt_json=%s,'
                'revision=revision+1,updated_at=%s WHERE organization_id=%s '
                'AND execution_id=%s AND effect_id=%s RETURNING *',
                (outcome, encoded, j.now(cursor), org, row['execution_id'], effect_id))
            updated = dict(cursor.fetchone())
            if outcome == 'UNKNOWN':
                cursor.execute('UPDATE sandbox_runner_attempts SET revoked=TRUE,'
                    "state='Stopping',reason='EFFECT_UNKNOWN',revision=revision+1,updated_at=%s "
                    'WHERE organization_id=%s AND attempt_id=%s',
                    (j.now(cursor), org, attempt))
            j.history(cursor, row, 'EFFECT_' + outcome, effect_id)
            return updated
