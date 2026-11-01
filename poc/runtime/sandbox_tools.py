"""Direct-worker local tools executed inside a repository sandbox container.

Every file and shell operation goes through `docker exec`, so the host
filesystem is never read or written on the model's behalf. Grep uses POSIX
extended regular expressions (grep -E) rather than Python regex syntax.
"""
import asyncio
import fnmatch
import json
import re

CONTAINER_NAME = re.compile(r'repo_sbx_[0-9a-f]{24}')
WORKDIR = '/workspace/repo'
READ_LIMIT = 1_000_000


class SandboxTools:
    def __init__(self, container, env, redactions_path=None):
        if not CONTAINER_NAME.fullmatch(container or ''):
            raise ValueError('Invalid repository sandbox container.')
        self.container, self.env = container, env
        self.redactions = {}
        if redactions_path:
            with open(redactions_path) as handle:
                # Longest first so a value containing another value is fully masked.
                self.redactions = dict(sorted(json.load(handle).items(), key=lambda item: -len(item[1])))

    def redact(self, text):
        """Workflow secret values never reach the model, even when a command prints them."""
        for name, value in self.redactions.items():
            if len(value) >= 4:
                text = text.replace(value, f'[REDACTED:{name}]')
        return text

    async def _exec(self, argv, stdin=None, timeout=120):
        process = await asyncio.create_subprocess_exec(
            'docker', 'exec', *(['--interactive'] if stdin is not None else []), '--workdir', WORKDIR,
            self.container, *argv, env=self.env,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            output, _ = await asyncio.wait_for(process.communicate(stdin), timeout)
        except asyncio.TimeoutError:
            # Processes left inside the container end when the step's container is removed.
            process.kill()
            await process.wait()
            raise ValueError('Sandbox command exceeded the time limit.')
        return process.returncode, output

    async def _read(self, path):
        code, output = await self._exec(['head', '-c', str(READ_LIMIT + 1), '--', path])
        if code != 0:
            raise ValueError('File could not be read in the sandbox.')
        if len(output) > READ_LIMIT:
            raise ValueError('File exceeds the 1 MB read limit.')
        return output.decode(errors='replace')

    async def _write(self, path, content):
        code, _ = await self._exec(['/bin/sh', '-c', 'mkdir -p -- "$(dirname -- "$1")" && cat > "$1"', 'sh', path],
                                   stdin=content.encode())
        if code != 0:
            raise ValueError('File could not be written in the sandbox.')

    async def call(self, name, inputs):
        return self.redact(await self._call(name, inputs))

    async def _call(self, name, inputs):
        if name == 'Bash':
            timeout = min(max(inputs.get('timeout', 120000) / 1000, 1), 600)
            code, output = await self._exec(['/bin/sh', '-c', inputs['command']], timeout=timeout)
            return f'Exit code: {code}\n' + output.decode(errors='replace')[-30000:]
        if name == 'Read':
            return (await self._read(inputs['file_path']))[:30000]
        if name == 'Write':
            await self._write(inputs['file_path'], inputs['content'])
            return 'File written.'
        if name == 'Edit':
            text = await self._read(inputs['file_path'])
            if not inputs['old_string'] or text.count(inputs['old_string']) != 1:
                raise ValueError('old_string must match exactly once.')
            await self._write(inputs['file_path'], text.replace(inputs['old_string'], inputs['new_string'], 1))
            return 'File edited.'
        if name == 'Glob':
            code, output = await self._exec(['find', '.', '-type', 'f', '-not', '-path', './.git/*'])
            if code != 0:
                raise ValueError('Files could not be listed in the sandbox.')
            pattern = inputs['pattern']
            files = [line[2:] if line.startswith('./') else line
                     for line in output.decode(errors='replace').splitlines()]
            matches = [f for f in files if fnmatch.fnmatch(f, pattern)
                       or (pattern.startswith('**/') and fnmatch.fnmatch(f, pattern[3:]))]
            return '\n'.join(sorted(matches))[:30000]
        if name == 'Grep':
            code, output = await self._exec(['grep', '-rnIE', '-e', inputs['pattern'], '--', inputs.get('path', '.')])
            if code > 1:
                raise ValueError('Search failed in the sandbox; check the pattern and path.')
            return '\n'.join(line[:500] for line in output.decode(errors='replace').splitlines()[:100])
        raise ValueError('Unsupported sandbox tool.')
