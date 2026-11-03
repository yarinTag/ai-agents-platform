"""Read-only SDK container plus relay on a private internal Docker network."""
import os
import subprocess
import uuid
from pathlib import Path

from workflows.repo_sandbox import _docker, require_docker
from workflows.settings import MACHINE_SIZES
from .policy import configured_image

SOURCES = Path(__file__).resolve().parent


class HostedContainers:
    def __init__(self, workspace, socket_directory, token, machine_size):
        suffix = uuid.uuid4().hex[:24]
        self.network = 'sdknet_' + suffix
        self.relay = 'sdkrelay_' + suffix
        self.worker = 'sdkworker_' + suffix
        self.workspace, self.directory, self.token = workspace, socket_directory, token
        self.size = MACHINE_SIZES[machine_size]
        self.image = configured_image()
        self.process = None

    def _run(self, args):
        result = _docker(args, timeout=60)
        if result.returncode:
            raise ValueError('Hosted container setup failed. Check Docker and the pinned SDK image.')

    def __enter__(self):
        require_docker()
        try:
            self._run(['network', 'create', '--internal', self.network])
            uid = f'{os.getuid()}:{os.getgid()}' if os.getuid() else '1000:1000'
            base = ['--rm', '--network', self.network, '--dns', '127.0.0.1', '--cap-drop', 'ALL',
                    '--security-opt', 'no-new-privileges', '--read-only', '--user', uid,
                    '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m', '--env', 'HOME=/tmp',
                    '--env', 'PYTHONUNBUFFERED=1', '--env', 'PYTHONDONTWRITEBYTECODE=1']
            self._run(['run', '--detach', '--name', self.relay, *base,
                '--pids-limit', '64', '--memory', '128m', '--cpus', '0.25',
                '--mount', f'type=bind,source={self.directory},target=/broker,readonly',
                '--mount', f'type=bind,source={SOURCES / "relay.py"},target=/app/relay.py,readonly',
                '--entrypoint', 'python3', self.image, '/app/relay.py'])
            self._run(['exec', self.relay, 'python3', '-c',
                'import socket,time; deadline=time.monotonic()+10\n'
                'while True:\n'
                ' try:\n  s=socket.create_connection(("127.0.0.1",8080),timeout=1); s.close(); break\n'
                ' except OSError:\n  if time.monotonic()>deadline: raise\n  time.sleep(0.1)'])
            # Only a scoped broker capability, never an Anthropic key, crosses into the worker.
            command = ['docker', 'run', '--interactive', '--name', self.worker, *base,
                '--pids-limit', self.size['pids'], '--memory', self.size['memory'], '--cpus', self.size['cpus'],
                '--env', 'ANTHROPIC_AUTH_TOKEN=', '--env', 'CLAUDE_CODE_OAUTH_TOKEN=',
                '--env', 'ANTHROPIC_API_KEY', '--env', f'ANTHROPIC_BASE_URL=http://{self.relay}:8080',
                '--env', 'CLAUDE_CONFIG_DIR=/tmp/claude',
                '--env', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1',
                '--mount', f'type=bind,source={Path(self.workspace["worktree"]).resolve()},target=/workspace/repo,readonly',
                '--mount', f'type=bind,source={SOURCES / "worker.py"},target=/app/worker.py,readonly',
                '--workdir', '/workspace/repo', '--entrypoint', 'python3', self.image, '/app/worker.py']
            env = {key: os.environ[key] for key in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT',
                'DOCKER_CONFIG', 'DOCKER_CERT_PATH', 'DOCKER_TLS_VERIFY') if key in os.environ}
            env['ANTHROPIC_API_KEY'] = self.token
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env, text=True, bufsize=1, start_new_session=True)
            self.process._process_group = True
            return self.process
        except BaseException:
            self.close()
            raise

    def close(self):
        # Killing docker's client is insufficient: kill the container/process tree.
        for name in (self.worker, self.relay):
            try:
                _docker(['rm', '--force', name], timeout=10)
            except Exception:
                pass
        if self.process:
            from runtime.processes import terminate_process
            terminate_process(self.process, timeout=2)
        try:
            _docker(['network', 'rm', self.network], timeout=10)
        except Exception:
            pass

    def __exit__(self, *args):
        self.close()
