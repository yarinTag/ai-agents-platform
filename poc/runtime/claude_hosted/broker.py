"""Host-only, run-bound Anthropic gateway. No agent-controlled URL or real key.

The gateway listens on a private Unix socket mounted into a network-only relay,
not a TCP port on the application host. Responses are bounded and accounted for
before forwarding; tool activity remains incremental, model deltas are buffered.
"""
import hmac
import json
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit

import httpx
from runtime.direct_pricing import pricing, totals
from storage.hosted_budget import reserve, settle

MAX_BODY = 2_000_000
MAX_RESPONSE = 16_000_000
UPSTREAM = 'https://api.anthropic.com/v1/messages'


def validate_request(body, context):
    if not isinstance(body, dict) or body.get('model') != context.model:
        raise ValueError('Hosted requests must use the selected model.')
    if not isinstance(body.get('messages'), list) or not body['messages']:
        raise ValueError('Hosted messages are required.')
    if len(json.dumps(body).encode()) > 80_000:
        raise ValueError('Hosted text context exceeds the conservative standard-context limit.')
    maximum = body.get('max_tokens')
    if type(maximum) is not int or not 1 <= maximum <= context.max_tokens:
        raise ValueError('Hosted output-token limit exceeded.')
    forbidden = {'container', 'mcp_servers', 'service_tier', 'speed'}
    if forbidden & set(body):
        raise ValueError('Hosted server tools and elevated service tiers are disabled.')
    for tool in body.get('tools', []):
        if not isinstance(tool, dict) or tool.get('name') not in context.tools or tool.get('type', 'custom') != 'custom':
            raise ValueError('Hosted request contains an unapproved tool.')
    def walk(value):
        if isinstance(value, dict):
            if value.get('type') in ('image', 'document', 'base64', 'url', 'redacted_thinking', 'web_search_20250305', 'web_fetch_20250910'):
                raise ValueError('Hosted requests support text-only repository analysis.')
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(body)
    return body


def response_usage(data, streaming):
    """Missing terminal usage is an ambiguous charge, never zero."""
    if not streaming:
        obj = json.loads(data)
        usage = obj.get('usage')
    else:
        usage, done = {}, False
        for line in data.decode('utf-8').splitlines():
            if not line.startswith('data: '):
                continue
            event = json.loads(line[6:])
            if event.get('type') == 'message_start':
                usage.update((event.get('message') or {}).get('usage') or {})
            elif event.get('type') == 'message_delta':
                usage.update(event.get('usage') or {})
            elif event.get('type') == 'message_stop':
                done = True
            elif event.get('type') == 'error':
                return None
        if not done:
            return None
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                        for k in ('input_tokens', 'output_tokens')):
        return None
    for key in ('cache_read_input_tokens', 'cache_creation_input_tokens'):
        if type(usage.get(key, 0)) is not int or usage.get(key, 0) < 0:
            return None
    return {k: usage.get(k, 0) for k in ('input_tokens', 'output_tokens',
            'cache_read_input_tokens', 'cache_creation_input_tokens')}


class UnixServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    block_on_close = False
    address_family = socket.AF_UNIX
    def server_bind(self):
        socket.socket.bind(self.socket, self.server_address)
        self.server_name, self.server_port = 'hosted-broker', 0


class CredentialBroker:
    def __init__(self, db, context, directory):
        self.db, self.context = db, context
        self.token = secrets.token_urlsafe(48)
        self.path = str(directory / 'broker.sock')
        self.server = None
        self.thread = None
        self.failed = False
        self.active = True
        self.lock = threading.Lock()
        self.calls = []
        self.on_usage = None

    def dispatch(self, path, token, data):
        if not self.active or not hmac.compare_digest(token or '', self.token):
            raise ValueError('Hosted authorization denied.')
        with self.lock:
            if self.failed or not self.active:
                raise ValueError('Hosted session is closed after a failed request.')
            _, credentials = self.context.authorize(self.db)
            route = urlsplit(path)
            if route.scheme or route.netloc or route.fragment:
                raise ValueError('Only relative broker routes are permitted.')
            if route.path == '/authorize' and not route.query:
                if not isinstance(data, dict) or data.get('tool') not in self.context.tools:
                    raise ValueError('Hosted tool access denied.')
                return b'{"allowed":true}', 'application/json'
            if route.path != '/v1/messages' or route.query not in ('', 'beta=true'):
                raise ValueError('Unsupported hosted API route.')
            if len(self.calls) >= 40:
                raise ValueError('Hosted model-call limit exceeded.')
            body = validate_request(data, self.context)
            policy = pricing('direct_anthropic', self.context.model)
            if policy['rates'] is None:
                raise ValueError('Configure explicit Anthropic token prices before hosted execution.')
            rate_in, rate_out = policy['rates']
            encoded = json.dumps(body).encode()
            # UTF-8 bytes plus framing, doubled input price bounds 1h cache writes.
            estimate = ((len(encoded) * 2 + 8192) * rate_in * 2 + body['max_tokens'] * rate_out) / 1_000_000
            identity = reserve(self.db, self.context, estimate, policy)
            dispatched = False
            try:
                self.context.authorize(self.db)  # Recheck revocation after reserving.
                key = credentials.resolve_credential('direct_anthropic')
                if not key or credentials.credential_version('direct_anthropic') != self.context.credential_version:
                    raise ValueError('Organization credential unavailable or changed.')
                with httpx.Client(timeout=httpx.Timeout(120, connect=15), follow_redirects=False,
                                  trust_env=False) as client:
                    dispatched = True
                    with client.stream('POST', UPSTREAM, json=body, headers={
                        'x-api-key': key, 'anthropic-version': '2023-06-01'}) as response:
                        if response.status_code != 200:
                            raise ValueError('Anthropic request failed; no automatic retries are permitted.')
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            if not self.active:
                                raise ValueError('Hosted session closed.')
                            self.context.authorize(self.db)
                            size += len(chunk)
                            if size > MAX_RESPONSE:
                                raise ValueError('Hosted response exceeded its size limit.')
                            chunks.append(chunk)
                        result = b''.join(chunks)
                usage = response_usage(result, bool(body.get('stream')))
                actual = None
                if usage:
                    actual = ((usage['input_tokens'] + usage['cache_read_input_tokens']
                        + usage['cache_creation_input_tokens'] * 2) * rate_in
                        + usage['output_tokens'] * rate_out) / 1_000_000
                settle(self.db, identity, actual, usage)
                if usage is None or actual > estimate:
                    raise ValueError('Hosted usage could not be safely reconciled.')
                call = {'input_tokens': usage['input_tokens'] + usage['cache_read_input_tokens'] + usage['cache_creation_input_tokens'],
                        'output_tokens': usage['output_tokens'], 'cost_usd': actual,
                        'source': 'CONFIGURED_ESTIMATE', 'reference_cost_usd': None}
                self.calls.append(call)
                if self.on_usage:
                    self.on_usage({'type': 'usage', 'provider': 'direct_anthropic', 'model': self.context.model,
                        'turn': len(self.calls), **call, 'cost_summary': totals(self.calls),
                        'session_cost_summary': totals(self.calls)})
                return result, 'text/event-stream' if body.get('stream') else 'application/json'
            except Exception:
                settle(self.db, identity, None if dispatched else 0)  # Keep uncertain dispatched charges reserved.
                self.failed = True
                raise ValueError('Hosted model request failed or was revoked. Check policy and provider configuration.') from None

    def __enter__(self):
        broker = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                        raise ValueError('Invalid request size.')
                    token = self.headers.get('x-api-key') or self.headers.get('Authorization', '').removeprefix('Bearer ')
                    result, mime = broker.dispatch(self.path, token, json.loads(self.rfile.read(size)))
                    code = 200
                except Exception:
                    broker.failed = True
                    result, mime, code = b'{"type":"error","error":{"type":"permission_error","message":"Hosted request denied."}}', 'application/json', 403
                self.send_response(code)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(result)))
                self.end_headers()
                self.wfile.write(result)
        self.server = UnixServer(self.path, Handler)
        os.chmod(self.path, 0o600)
        if os.getuid() == 0:
            os.chown(self.path, 1000, 1000)
        self.server.timeout = 1
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.active = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=5)
