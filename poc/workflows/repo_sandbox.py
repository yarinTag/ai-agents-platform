"""Docker containers for repository workspaces. There is intentionally no host fallback.

Only the cloned worktree is mounted; git metadata and credentials stay on the
host. Containers have no capabilities, a read-only root filesystem, a non-root
user and the workflow's machine-size limits. Without an allowlist they have no
network. With one, they sit on an internal Docker network whose only exit is an
egress proxy (egress_proxy.py) that permits HTTPS to the listed hosts.
Workflow secrets reach the container through the docker CLI's process environment
(`--env NAME`), never through command-line arguments or files.
"""
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from integrations.tool_definitions import ToolAccessError

logger = logging.getLogger(__name__)

IMAGE_SETTING = 'PLATFORM_SANDBOX_IMAGE'
PROXY_IMAGE_SETTING = 'PLATFORM_SANDBOX_PROXY_IMAGE'
CONTAINER_WORKDIR = '/workspace/repo'
CONTAINER_NAME = re.compile(r'repo_sbx_[0-9a-f]{24}')
PROXY_NAME = re.compile(r'sbxproxy_[0-9a-f]{24}')
NETWORK_NAME = re.compile(r'sbxnet_[0-9a-f]{24}')
PROXY_PORT = 3128
_DIGEST = re.compile(r'[a-z0-9][a-z0-9._/:-]{0,255}@sha256:[0-9a-f]{64}')
_PROXY_SCRIPT = Path(__file__).resolve().with_name('egress_proxy.py')
# The docker CLI itself needs these; secret names can never shadow them (see workflow_secrets).
_DOCKER_ENV = ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG', 'DOCKER_CERT_PATH', 'DOCKER_TLS_VERIFY')


def _pinned(setting, purpose):
    image = os.environ.get(setting, '').strip()
    if not _DIGEST.fullmatch(image):
        raise ToolAccessError(f'Set {setting} to a digest-pinned image (name@sha256:...) before {purpose}.')
    return image


def sandbox_image():
    return _pinned(IMAGE_SETTING, 'running repository workspaces')


def proxy_image():
    """Any digest-pinned image with python3 (for example a pinned python:3.x-slim)."""
    return _pinned(PROXY_IMAGE_SETTING, 'allowing sandbox network access')


def configuration_status():
    """Static authoring diagnostics only; never starts Docker or contacts its daemon."""
    errors = []
    if os.name != 'posix' or shutil.which('docker') is None:
        errors.append('Install Docker on a POSIX host for isolated repository execution.')
    try:
        sandbox_image()
    except ToolAccessError as exc:
        errors.append(str(exc))
    return {'configured': not errors, 'errors': errors, 'verification': 'configuration_only'}


def _docker(args, timeout=60, env=None):
    base = {key: os.environ[key] for key in _DOCKER_ENV if key in os.environ}
    return subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout, check=False,
                          env={**base, **(env or {})})


def require_docker():
    if os.name != 'posix' or shutil.which('docker') is None:
        raise ToolAccessError('Repository workspaces require Docker on a POSIX host; no unsandboxed fallback exists.')
    try:
        probe = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                               capture_output=True, timeout=10, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolAccessError('Docker did not respond; repository workspaces cannot run.') from exc
    if probe.returncode != 0:
        raise ToolAccessError('The Docker daemon is unavailable; repository workspaces cannot run.')


def _container_user(worktree: Path):
    uid, gid = os.getuid(), os.getgid()
    if uid != 0:
        return f'{uid}:{gid}'
    # Never run sandboxed code as root; hand the worktree to an unprivileged id.
    for path in [worktree, *worktree.rglob('*')]:
        os.lchown(path, 1000, 1000)
    return '1000:1000'


def start_egress(hosts, image: str) -> dict:
    """Internal network plus a proxy container that is the network's only route out."""
    suffix = uuid.uuid4().hex[:24]
    egress = {'network': f'sbxnet_{suffix}', 'proxy': f'sbxproxy_{suffix}', 'hosts': list(hosts)}
    try:
        steps = [
            ['network', 'create', '--internal', egress['network']],
            ['run', '--detach', '--rm', '--name', egress['proxy'], '--network', egress['network'],
             '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--read-only',
             '--pids-limit', '128', '--memory', '256m', '--cpus', '0.5', '--user', '65534:65534',
             '--mount', f'type=bind,source={_PROXY_SCRIPT},target=/proxy/egress_proxy.py,readonly',
             '--entrypoint', 'python3', image, '/proxy/egress_proxy.py', ','.join(hosts)],
            ['network', 'connect', 'bridge', egress['proxy']],
        ]
        for args in steps:
            result = _docker(args, timeout=180)
            if result.returncode != 0:
                logger.warning('Sandbox egress setup failed: %s', result.stderr[-500:])
                raise ToolAccessError('The sandbox egress proxy could not start. Check the proxy image and Docker.')
    except subprocess.TimeoutExpired as exc:
        remove_egress(egress)
        raise ToolAccessError('The sandbox egress proxy did not start in time.') from exc
    except ToolAccessError:
        remove_egress(egress)
        raise
    return egress


def remove_egress(egress):
    if not egress:
        return
    for args, name, pattern in ((['rm', '--force'], egress.get('proxy'), PROXY_NAME),
                                (['network', 'rm'], egress.get('network'), NETWORK_NAME)):
        if pattern.fullmatch(name or ''):
            try:
                _docker([*args, name])
            except Exception as exc:
                logger.warning('Sandbox egress cleanup of %s failed: %s', name, type(exc).__name__)


def start_container(worktree: Path, image: str, size: dict, secrets=None, egress=None) -> str:
    name = 'repo_sbx_' + uuid.uuid4().hex[:24]
    network = ['--network', egress['network']] if egress else ['--network', 'none']
    proxy = []
    if egress:
        url = f'http://{egress["proxy"]}:{PROXY_PORT}'
        for key in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy'):
            proxy += ['--env', f'{key}={url}']
    secret_flags = [flag for key in sorted(secrets or {}) for flag in ('--env', key)]  # Values via env only.
    command = ['run', '--detach', '--rm', '--name', name, *network,
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m',
               '--pids-limit', size['pids'], '--memory', size['memory'], '--cpus', size['cpus'],
               '--user', _container_user(worktree), '--env', 'HOME=/tmp', *proxy, *secret_flags,
               '--mount', f'type=bind,source={worktree.resolve()},target={CONTAINER_WORKDIR}',
               '--workdir', CONTAINER_WORKDIR, '--entrypoint', 'sleep', image, '3600']
    try:
        result = _docker(command, timeout=180, env=secrets)
    except subprocess.TimeoutExpired as exc:
        remove_container(name)
        raise ToolAccessError('The sandbox container did not start in time.') from exc
    if result.returncode != 0:
        logger.warning('Sandbox container start failed: %s', result.stderr[-500:])
        remove_container(name)
        raise ToolAccessError('The sandbox container could not start. Check the sandbox image and Docker.')
    return name


def remove_container(name: str):
    if not CONTAINER_NAME.fullmatch(name or ''):
        return
    try:
        _docker(['rm', '--force', name])
    except Exception as exc:
        logger.warning('Sandbox container %s cleanup failed: %s', name, type(exc).__name__)
