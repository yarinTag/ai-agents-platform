"""Explicit tool inventory for the direct worker. No inherited CLI integrations."""
import asyncio
import json
import os
import re
from contextlib import AsyncExitStack
from pathlib import Path


class DirectTools:
    def __init__(self, args):
        self.args = args
        self.stack = AsyncExitStack()
        self.sessions = {}
        self.inventory = []
        self.connector = None
        self.root = Path(args.add_dir or os.getcwd()).resolve()
        self.sandbox = None

    async def __aenter__(self):
        try:
            if getattr(self.args, 'connector_only', False):
                from persistence import DatabaseManager
                from integrations.tool_executor import WorkflowToolExecutor
                database = os.environ.get('PLATFORM_CONNECTOR_DB')
                task = os.environ.get('PLATFORM_CONNECTOR_TASK')
                if not database or not task:
                    raise ValueError('Trusted workflow connector context is missing.')
                self.connector = WorkflowToolExecutor(DatabaseManager(database), task)
                self.inventory = self.connector.inventory()
                return self
            if getattr(self.args, 'sandbox_container', None):
                from .sandbox_tools import SandboxTools
                self.sandbox = SandboxTools(self.args.sandbox_container, self._shell_env())
            config = json.loads(self.args.mcp_config or '{"mcpServers":{}}')
            if config.get('mcpServers'):
                raise ValueError('Unsupported MCP server in direct API runtime.')
            if not self.args.restricted and self.args.tools != '':
                self._add_local_tools()
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *exc):
        await self.stack.__aexit__(*exc)

    @staticmethod
    def _shell_env():
        return {k: v for k, v in os.environ.items() if not any(x in k for x in ('API_KEY', 'AUTH_TOKEN', 'OAUTH_TOKEN'))}

    def allowed(self):
        return set((self.args.allowedTools or '').split(','))

    def _add_local_tools(self):
        definitions = {
            'Read': ('Read a UTF-8 file inside the workspace.', {'file_path': {'type': 'string'}}, ['file_path']),
            'Write': ('Write a UTF-8 file inside the workspace.', {'file_path': {'type': 'string'}, 'content': {'type': 'string'}}, ['file_path', 'content']),
            'Edit': ('Replace an exact unique string inside a workspace file.', {k: {'type': 'string'} for k in ('file_path', 'old_string', 'new_string')}, ['file_path', 'old_string', 'new_string']),
            'Glob': ('List workspace files matching a glob.', {'pattern': {'type': 'string'}}, ['pattern']),
            'Grep': ('Search text in workspace files using a regular expression.', {'pattern': {'type': 'string'}, 'path': {'type': 'string'}}, ['pattern']),
            'Bash': ('Run a shell command in the assigned workspace.', {'command': {'type': 'string'}, 'timeout': {'type': 'integer'}}, ['command']),
            'AskUserQuestion': ('Ask the supervisor for missing information or permission.', {'question': {'type': 'string'}}, ['question']),
        }
        allowed = self.allowed()
        for name, (description, properties, required) in definitions.items():
            if self.args.allowedTools is not None and name not in allowed:
                continue
            self.inventory.append({'name': name, 'description': description,
                'input_schema': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}})

    def path(self, value):
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('File access is limited to the assigned workspace.')
        return path

    async def call(self, name, inputs):
        if name not in {t['name'] for t in self.inventory}:
            raise ValueError('Tool is not in this run’s authorized inventory.')
        if self.connector is not None:
            return json.dumps(await asyncio.to_thread(self.connector.call, name, inputs), ensure_ascii=False)
        if name in self.sessions:
            session, tool = self.sessions[name]
            response = await session.call_tool(tool, inputs)
            return json.dumps(response.model_dump(mode='json'), ensure_ascii=False)
        if name == 'Bash' and not self.args.dangerously_skip_permissions:
            raise PermissionError('Shell execution requires operator permission.')
        if self.sandbox is not None:
            return await self.sandbox.call(name, inputs)  # Never touch the host filesystem.
        if name == 'Bash':
            env = self._shell_env()
            process = await asyncio.create_subprocess_exec('/bin/sh', '-c', inputs['command'], cwd=self.root,
                env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            try:
                output, _ = await asyncio.wait_for(process.communicate(), min(max(inputs.get('timeout', 120000) / 1000, 1), 600))
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ValueError('Shell command exceeded the time limit.')
            return f'Exit code: {process.returncode}\n' + output.decode(errors='replace')[-30000:]
        if name == 'Grep':
            root = self.path(inputs.get('path', '.'))
            pattern = re.compile(inputs['pattern'])
            matches = []
            for file in ([root] if root.is_file() else root.rglob('*')):
                if not file.is_file() or not file.resolve().is_relative_to(self.root) or file.stat().st_size > 1_000_000:
                    continue
                for number, line in enumerate(file.read_text(errors='replace').splitlines(), 1):
                    if pattern.search(line):
                        matches.append(f'{file.relative_to(self.root)}:{number}:{line[:500]}')
                    if len(matches) >= 100:
                        return '\n'.join(matches)
            return '\n'.join(matches)
        if name == 'Glob':
            return '\n'.join(str(p.relative_to(self.root)) for p in self.root.glob(inputs['pattern'])
                if p.is_file() and p.resolve().is_relative_to(self.root))[:30000]
        path = self.path(inputs['file_path'])
        if name == 'Read':
            if path.stat().st_size > 1_000_000:
                raise ValueError('File exceeds the 1 MB read limit.')
            return path.read_text()[:30000]
        if name == 'Write':
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(inputs['content'])
            return 'File written.'
        if name == 'Edit':
            text = path.read_text()
            if not inputs['old_string'] or text.count(inputs['old_string']) != 1:
                raise ValueError('old_string must match exactly once.')
            path.write_text(text.replace(inputs['old_string'], inputs['new_string'], 1))
            return 'File edited.'
        raise ValueError('Unsupported local tool.')
