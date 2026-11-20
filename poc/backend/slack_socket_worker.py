"""Authenticated, outbound Slack Socket Mode for explicitly configured installations."""
import asyncio
import fcntl
import hashlib
import json
import logging
import re
import time
from urllib.parse import urlsplit

from integrations.identity_proofs import InvalidProof
from integrations.provider_http import request_json
from storage.external_identities import connector_settings

from .api.channel_ingress import MAX_BODY, receive_slack_socket
from .dependencies import get_db_manager

logger = logging.getLogger(__name__)
_APP_TOKEN = re.compile(r'xapp-[A-Za-z0-9-]{12,512}')
_ENVELOPE_ID = re.compile(r'[A-Za-z0-9_-]{1,128}')


def configured_app_token(config):
    token = config.get('socket_app_token')
    return token if isinstance(token, str) and _APP_TOKEN.fullmatch(token) else None


def _configurations(db):
    candidates = {}
    with db._get_connection() as conn:
        rows = conn.execute("""SELECT id,configuration FROM mcp_connectors WHERE lower(provider)='slack'
            AND status='CONNECTED' AND CASE WHEN json_valid(configuration)
            THEN json_extract(configuration,'$.ingress_mode')='socket' ELSE 0 END""")
        for row in rows:
            token = configured_app_token(json.loads(row['configuration']))
            if not token:
                continue
            try:
                _, _, (_, team, app), version = connector_settings(conn, row['id'])
            except InvalidProof:
                continue
            candidates[row['id']] = (team, app, version, token)
    # Multiple eligible local connectors for one installation are ambiguous.
    installations = [(team, app) for team, app, _, _ in candidates.values()]
    return {identifier: (version, token) for identifier, (team, app, version, token) in candidates.items()
            if installations.count((team, app)) == 1}


def _url(app_token):
    result = request_json('slack.com', '/api/apps.connections.open',
                          {'Authorization': f'Bearer {app_token}'}, payload={})
    if not isinstance(result, dict) or result.get('ok') is not True or not isinstance(result.get('url'), str):
        raise InvalidProof('SOCKET_UNAVAILABLE')
    url = result['url']
    parsed = urlsplit(url)
    if (parsed.scheme != 'wss' or not re.fullmatch(r'wss(?:-[a-z0-9-]+)?\.slack\.com', parsed.hostname or '')
            or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment
            or not parsed.path.startswith('/') or any(ord(char) < 33 or ord(char) > 126 for char in url) or '\\' in url):
        raise InvalidProof('SOCKET_URL_REJECTED')
    return url


async def _connection(db, connector_id, version, app_token):
    from websockets.asyncio.client import connect

    class NoRedirectConnection(connect):
        def process_redirect(self, exc):
            return exc

    digest = hashlib.sha256(app_token.encode()).hexdigest()
    url = await asyncio.to_thread(_url, app_token)
    async with NoRedirectConnection(url, proxy=None, compression=None, max_size=MAX_BODY, max_queue=8,
                                    open_timeout=10, close_timeout=2) as socket:
        await asyncio.to_thread(db.set_setting, f'slack_socket_health:{connector_id}', 'CONNECTED')
        async for message in socket:
            envelope = json.loads(message)
            kind = envelope.get('type')
            if kind == 'disconnect':
                return
            identifier = envelope.get('envelope_id')
            if not isinstance(identifier, str) or not _ENVELOPE_ID.fullmatch(identifier):
                continue
            try:
                await asyncio.to_thread(receive_slack_socket, db, connector_id, version,
                                        digest, kind, envelope.get('payload'))
            except InvalidProof as exc:
                if str(exc) not in {'INVALID_EVENT', 'INVALID_PROOF', 'INVALID_APPROVAL_CALLBACK'}:
                    raise
            await socket.send(json.dumps({'envelope_id': identifier}))
            await asyncio.to_thread(db.set_setting, f'slack_socket_last_ack:{connector_id}', str(int(time.time())))


async def _reconnect(db, connector_id, version, token):
    delay = 2
    try:
        while True:
            started = time.monotonic()
            try:
                await _connection(db, connector_id, version, token)
            except Exception as exc:
                logger.warning('Slack Socket Mode disconnected connector=%s error=%s', connector_id, type(exc).__name__)
            await asyncio.to_thread(db.set_setting, f'slack_socket_health:{connector_id}', 'RECONNECTING')
            delay = 2 if time.monotonic() - started > 30 else min(delay * 2, 60)
            await asyncio.sleep(delay)
    finally:
        await asyncio.to_thread(db.set_setting, f'slack_socket_health:{connector_id}', 'DISCONNECTED')


async def run(stop):
    workers = {}
    lock = None
    try:
        db = get_db_manager()
        while not stop.is_set():
            try:
                configured = await asyncio.to_thread(_configurations, db)
                if configured and lock is None:
                    candidate = open(str(db.db_path.resolve()) + '.slack-socket.lock', 'a')
                    try:
                        fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError:
                        candidate.close()
                    else:
                        lock = candidate
                if lock is not None:
                    outdated = [key for key, (settings, task) in workers.items()
                                if configured.get(key) != settings or task.done()]
                    for key in outdated:
                        _, task = workers.pop(key)
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                    for key, settings in configured.items():
                        if key not in workers:
                            workers[key] = (settings, asyncio.create_task(_reconnect(db, key, *settings)))
            except Exception as exc:
                logger.warning('Slack Socket Mode configuration unavailable error=%s', type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except TimeoutError:
                continue
    finally:
        tasks = [task for _, task in workers.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if lock:
            lock.close()
