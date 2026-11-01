"""Private, provider/agent/tenant-bound conversation transcripts for API resumption."""
import hashlib
import json
import os
import re
import uuid
from pathlib import Path


class DirectSession:
    def __init__(self, provider, model, resume=None, fork=False, ephemeral=False):
        self.ephemeral = ephemeral
        self.provider, self.model = provider, model
        self.scope = os.environ.get('PLATFORM_API_SESSION_SCOPE', '')
        self.id = 'api_' + uuid.uuid4().hex
        self.messages = []
        self.usage_calls = []
        self.prior_usage_unknown = False
        self.directory = Path(os.environ.get('PLATFORM_API_SESSION_DIR', '.runtime_sessions'))
        if resume:
            if not re.fullmatch(r'api_[0-9a-f]{32}', resume):
                raise ValueError('The session is not a direct API session. Start a new session.')
            record = json.loads(self.path(resume).read_text())
            if (record['provider'], record['model'], record['scope']) != (provider, model, self.scope):
                raise ValueError('Session provider, model or agent changed. Start a new session.')
            self.messages = record['messages']
            if not fork:
                self.id = resume
                self.usage_calls = record.get('usage_calls', [])
                self.prior_usage_unknown = bool(record.get('prior_usage_unknown') or 'usage_calls' not in record)

    def path(self, session_id):
        scope = hashlib.sha256(self.scope.encode()).hexdigest()
        return self.directory / scope / (session_id + '.json')

    def save(self):
        if self.ephemeral:
            return
        path = self.path(self.id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            with open(temporary, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
                json.dump({'provider': self.provider, 'model': self.model, 'scope': self.scope,
                    'messages': self.messages, 'usage_calls': self.usage_calls,
                    'prior_usage_unknown': self.prior_usage_unknown}, stream, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
