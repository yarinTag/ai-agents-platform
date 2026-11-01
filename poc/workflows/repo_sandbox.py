"""Docker containers for repository workspaces. There is intentionally no host fallback.

Only the cloned worktree is mounted; git metadata and credentials stay on the
host. Containers have no network, no capabilities, a read-only root filesystem,
a non-root user and CPU/memory/process limits.
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
CONTAINER_WORKDIR = '/workspace/repo'
CONTAINER_NAME = re.compile(r'repo_sbx_[0-9a-f]{24}')
_DIGEST = re.compile(r'[a-z0-9][a-z0-9._/:-]{0,255}@sha256:[0-9a-f]{64}')


def sandbox_image():
    image = os.environ.get(IMAGE_SETTING, '').strip()
    if not _DIGEST.fullmatch(image):
        raise ToolAccessError(f'Set {IMAGE_SETTING} to a digest-pinned image (name@sha256:...) '
                              'before running repository workspaces.')
    return image


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


def start_container(worktree: Path, image: str) -> str:
    name = 'repo_sbx_' + uuid.uuid4().hex[:24]
    command = ['docker', 'run', '--detach', '--rm', '--name', name,
               '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m',
               '--pids-limit', '256', '--memory', '2g', '--cpus', '2',
               '--user', _container_user(worktree), '--env', 'HOME=/tmp',
               '--mount', f'type=bind,source={worktree.resolve()},target={CONTAINER_WORKDIR}',
               '--workdir', CONTAINER_WORKDIR, '--entrypoint', 'sleep', image, '3600']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
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
        subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=60, check=False)
    except Exception as exc:
        logger.warning('Sandbox container %s cleanup failed: %s', name, type(exc).__name__)
