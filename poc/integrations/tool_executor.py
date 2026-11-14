"""Governed execution/audit for a fixed workflow task. No arbitrary connector RPC."""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from pydantic import ValidationError
from .github_activity import fetch_activity
from .scoped_channels import send_message
from .tool_definitions import MessageInput, RepositoryInput, ToolAccessError, public_tool, require_credentials, resource_values, input_model, WRITE_OPERATIONS
from .tool_scopes import agent_tool_allowed, connector_authorized, live_scope, load_scope


class WorkflowToolExecutor:
    def __init__(self, db, task_id):
        self.db, self.task_id = db, task_id
        self.scope = load_scope(db, task_id)
        if not self.scope:
            raise ToolAccessError('No server-authorized connector scope exists for this task.')
        self.entries = {entry['name']: entry for entry in self.scope['entries']}

    def authorize(self, entry, inputs=None):
        agent = live_scope(self.db, self.task_id, self.scope)
        connector = connector_authorized(self.db, entry['connector_id'], self.scope['organization_id'],
            self.scope['department_id'], agent)
        if connector.provider.lower() != entry['provider']:
            raise ToolAccessError('Connector provider changed since this run was authorized.')
        require_credentials(connector)
        tool = self.db.get_mcp_tool(entry['tool_id'])
        if not tool or tool.connector_id != connector.id or tool.name != entry['operation']:
            raise ToolAccessError('The connector tool definition was removed or changed.')
        if not agent_tool_allowed(self.db, agent, connector, tool):
            raise ToolAccessError('The execution agent is not allowed to invoke this connector tool.')
        if not self.db.check_department_mcp_permission(self.scope['department_id'], connector.id, entry['operation'])['allowed']:
            raise ToolAccessError('The requested tool was revoked from this department.')
        group = 'repositories' if entry['provider'] == 'github' else 'channels'
        current = set(resource_values(connector.configuration or {}, group))
        # Scope never expands when connector settings or grants grow during a run.
        allowed = current.intersection(entry[group])
        if not allowed:
            raise ToolAccessError('The step’s configured resources are no longer permitted.')
        if inputs is not None:
            value = inputs.repository if group == 'repositories' else inputs.channel_id
            if value not in allowed:
                raise ToolAccessError('Requested repository or channel is outside the authorized step scope.')
            if 'pull_numbers' in self.scope and getattr(inputs, 'pull_number', None) not in self.scope['pull_numbers']:
                raise ToolAccessError('Requested pull request is outside the discovered review batch.')
        from governance.enforcement import require_capability
        targets = [inputs.repository if group == 'repositories' else inputs.channel_id] if inputs is not None else entry[group]
        for target in targets:
            require_capability(self.db, self.scope['execution_id'], agent, connector, entry['operation'], target)
        return connector

    def inventory(self):
        tools = []
        for entry in self.entries.values():
            self.authorize(entry)
            tools.append(public_tool(entry))
        return tools

    def _claim(self, entry, arguments):
        identity = {key: value for key, value in arguments.items() if key not in ('text', 'body')}
        canonical = json.dumps(identity, sort_keys=True, ensure_ascii=False)
        identifier = 'call_exec_' + hashlib.sha256(f'{self.task_id}:{entry["name"]}:{canonical}'.encode()).hexdigest()
        previous = self.db.get_mcp_tool_call(identifier)
        if previous:
            return identifier, previous
        # Never persist message bodies or provider credentials in the call arguments.
        safe = {key: value for key, value in arguments.items() if key not in ('text', 'body')}
        if 'text' in arguments:
            safe['message_sha256'] = hashlib.sha256(arguments['text'].encode()).hexdigest()
        if 'body' in arguments:
            safe['body_sha256'] = hashlib.sha256(arguments['body'].encode()).hexdigest()
        with self.db._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            count = conn.execute('SELECT COUNT(*) FROM mcp_tool_calls WHERE task_id=? AND id LIKE ?',
                (self.task_id, 'call_exec_%')).fetchone()[0]
            if count >= 32:
                raise ToolAccessError('The workflow step reached its 32 audited connector-call limit.')
            try:
                conn.execute('''INSERT INTO mcp_tool_calls
                    (id,connector_id,tool_id,agent_id,task_id,run_id,status,arguments,started_at)
                    VALUES (?,?,?,?,?,?,'STARTED',?,?)''',
                    (identifier, entry['connector_id'], entry['tool_id'], self.scope['agent_id'], self.task_id,
                     self.task_id, json.dumps(safe), datetime.now().isoformat()))
            except sqlite3.IntegrityError:
                previous = self.db.get_mcp_tool_call(identifier)
                if not previous:
                    raise ToolAccessError('Unable to reserve an audited connector call.')
                return identifier, previous
        return identifier, None

    def call(self, name, arguments):
        if name not in self.entries:
            raise ToolAccessError('Tool is not authorized for this workflow step.')
        entry = self.entries[name]
        try:
            try:
                inputs = input_model(entry).model_validate(arguments)
            except ValidationError as exc:
                raise ToolAccessError('Invalid tool arguments; only the declared repository/channel and bounded options are accepted.') from exc
            connector = self.authorize(entry, inputs)
        except ToolAccessError:
            # Denied attempts are auditable without retaining hostile/secret-bearing arguments.
            try:
                self.db.save_mcp_tool_call({'id': 'call_denied_' + uuid.uuid4().hex,
                    'connector_id': entry['connector_id'], 'tool_id': entry['tool_id'],
                    'agent_id': self.scope['agent_id'], 'task_id': self.task_id, 'run_id': self.task_id,
                    'status': 'FAILED', 'arguments': {'denied': True}, 'error': 'Tool argument or current policy check denied invocation.',
                    'completed_at': datetime.now().isoformat()})
            except Exception:
                pass  # The denied operation remains blocked even if its actor was deleted.
            raise
        normalized = inputs.model_dump()
        identifier, previous = self._claim(entry, normalized)
        if previous:
            if 'body' in normalized and (previous.arguments or {}).get('body_sha256') != hashlib.sha256(normalized['body'].encode()).hexdigest():
                raise ToolAccessError('This PR write was already attempted for the pinned head. Changed content is not automatically sent.')
            if 'text' in normalized and (previous.arguments or {}).get('message_sha256') != hashlib.sha256(normalized['text'].encode()).hexdigest():
                raise ToolAccessError('Delivery to this channel was already attempted for this step; another message will not be sent.')
            if previous.status == 'COMPLETED' and previous.result:
                self.authorize(entry, inputs)
                return json.loads(previous.result)
            raise ToolAccessError('This action already started or failed. Delivery may be unknown; it will not be repeated automatically.')
        try:
            authorize = lambda: self.authorize(entry, inputs)
            if entry['provider'] == 'github':
                if entry['operation'] in WRITE_OPERATIONS:
                    from .github_pr_writes import execute_write
                    output = execute_write(connector.configuration or {}, entry['operation'], inputs, authorize)
                elif entry['operation'] in ('list_open_pull_requests', 'get_pull_request_review', 'get_pull_request', 'get_pull_request_diff', 'get_pull_request_checks'):
                    from .github_prs import execute_read
                    output = execute_read(connector.configuration or {}, entry['operation'], inputs, authorize)
                    if 'pull_numbers' in self.scope:
                        pull = output.get('pull_request', {})
                        if pull.get('state') != 'open' or pull.get('author') != self.scope.get('pull_author'):
                            raise ToolAccessError('A discovered pull request no longer matches the open state and author filter.')
                else:
                    output = fetch_activity(connector.configuration or {}, entry['operation'], inputs.repository, inputs.days, authorize)
                if entry['operation'] not in WRITE_OPERATIONS:
                    self.authorize(entry, inputs)
            else:
                output = send_message(connector, inputs.channel_id, inputs.text, authorize)
            self.db.update_mcp_tool_call(identifier, status='COMPLETED', result=json.dumps(output, ensure_ascii=False),
                completed_at=datetime.now().isoformat())
            return output
        except ToolAccessError as exc:
            self.db.update_mcp_tool_call(identifier, status='FAILED', error=str(exc), completed_at=datetime.now().isoformat())
            raise
        except Exception as exc:
            self.db.update_mcp_tool_call(identifier, status='FAILED', error='Integration execution failed.',
                completed_at=datetime.now().isoformat())
            raise ToolAccessError('Integration execution failed. No success or retry is assumed.') from exc

    def verify_completion(self):
        """Model prose alone cannot satisfy a task requiring real integration access."""
        live_scope(self.db, self.task_id, self.scope)
        fulfilled = set()
        operations = set()
        reviewed = set()
        with self.db._get_connection() as conn:
            calls = conn.execute('SELECT connector_id,tool_id,status,arguments FROM mcp_tool_calls WHERE task_id=? AND id LIKE ?',
                (self.task_id, 'call_exec_%')).fetchall()
        for call in calls:
            if call['status'] == 'COMPLETED':
                args = json.loads(call['arguments'] or '{}')
                fulfilled.add((call['connector_id'], args.get('repository') or args.get('channel_id')))
                operations.add((call['tool_id'], args.get('repository') or args.get('channel_id')))
                if 'pull_number' in args:
                    reviewed.add(args['pull_number'])
        if set(self.scope.get('pull_numbers', [])) - reviewed:
            raise ToolAccessError('The PR review did not return successful receipts for the entire batch.')
        for entry in self.entries.values():
            self.authorize(entry)
            required = entry['repositories'] if entry['provider'] == 'github' else entry['channels']
            if any((entry['connector_id'], value) not in fulfilled for value in required):
                raise ToolAccessError('Required connector work has no successful tool receipt. The model response cannot be marked completed.')
            if entry.get('required_operation'):
                missing = [value for value in required if (entry['tool_id'], value) not in operations]
                if missing:
                    raise ToolAccessError(f"Required tool {entry['operation']} has no successful receipt for {', '.join(missing)}.")
