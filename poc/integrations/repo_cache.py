"""Private Git object cache; each execution gets independent Git metadata and files.

The cache is never mounted into a sandbox. Every use resolves and fetches the
requested remote ref with current credentials; cached content is never an offline
authorization or freshness fallback. Copies contain no alternates or hard links.
"""
import fcntl
import hashlib
import json
import logging
import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from .tool_definitions import ToolAccessError

logger = logging.getLogger(__name__)
_HEX = re.compile(r'[0-9a-f]{64}')
_OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})')
_TTL = 7 * 24 * 60 * 60
_MAX_BYTES = 512 * 1024 * 1024
_MAX_ENTRIES = 8


def cache_identity(organization_id, connector_id, repository):
    if not organization_id or not connector_id:
        raise ToolAccessError('Repository caching requires an explicit tenant and connector.')
    tenant = hashlib.sha256(organization_id.encode()).hexdigest()
    key = hashlib.sha256(json.dumps([connector_id, repository.casefold()]).encode()).hexdigest()
    return tenant, key


def _positive_setting(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ToolAccessError(f'{name} must be a positive integer.') from exc
    if value <= 0:
        raise ToolAccessError(f'{name} must be a positive integer.')
    return value


def _private_directory(path):
    if path.is_symlink():
        raise ToolAccessError('Repository cache directory must not be a symbolic link.')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise ToolAccessError('Repository cache must be owned by the backend user.')
    path.chmod(0o700)


@contextmanager
def _lock(path, timeout=30):
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags, 0o600)
    acquired = False
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ToolAccessError('Repository cache is busy; no checkout was reused.')
                time.sleep(0.1)
        yield
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _size(path):
    total = 0
    for root, directories, files in os.walk(path, followlinks=False):
        if any((Path(root) / name).is_symlink() for name in directories + files):
            raise ToolAccessError('Symbolic links are forbidden in the repository object cache.')
        total += sum((Path(root) / name).stat().st_size for name in files)
    return total


def _remote_ref(run, env, url, requested):
    """Resolve only advertised branch/tag refs, never a stale local ref or arbitrary SHA."""
    if requested:
        output = run(['git', 'ls-remote', '--', url,
                      f'refs/heads/{requested}', f'refs/tags/{requested}'], env, timeout=30)
        refs = dict(line.split('\t')[::-1] for line in output.splitlines() if '\t' in line)
        for kind in ('heads', 'tags'):
            ref = f'refs/{kind}/{requested}'
            if _OID.fullmatch(refs.get(ref, '')):
                return ref, requested if kind == 'heads' else None
    else:
        output = run(['git', 'ls-remote', '--symref', '--', url, 'HEAD'], env, timeout=30)
        for line in output.splitlines():
            if line.startswith('ref: refs/heads/') and line.endswith('\tHEAD'):
                ref = line[5:].split('\t')[0]
                return ref, ref.removeprefix('refs/heads/')
    raise ToolAccessError('The requested remote branch/tag is unavailable; cached refs were not used.')


def _prune(tenant, locks, current, ttl, limit):
    """Lazy LRU/TTL retention; busy entries are never removed and lock files persist."""
    entries = sorted((path for path in tenant.iterdir() if _HEX.fullmatch(path.name)
                      and path.is_dir() and not path.is_symlink()), key=lambda path: path.stat().st_mtime,
                     reverse=True)
    for index, path in enumerate(entries):
        if path.name == current or (index < limit and time.time() - path.stat().st_mtime <= ttl):
            continue
        try:
            with _lock(locks / (path.name + '.lock'), timeout=0):
                # Another process may have refreshed it while we waited for its lock.
                if time.time() - path.stat().st_mtime > ttl or index >= limit:
                    shutil.rmtree(path)
        except (ToolAccessError, OSError):
            continue  # In-use entries can temporarily exceed the retention limit.


def materialize_checkout(bare, worktree, gitdir, commit, branch, *, run, env):
    """Copy objects, not cache config/refs, into a wholly independent checkout."""
    run(['git', 'init', '--template=', f'--separate-git-dir={gitdir}', str(worktree)], env)
    if (bare / 'objects/info/alternates').exists():
        raise ToolAccessError('Repository cache must not depend on external object stores.')
    size = _size(bare)
    shutil.copytree(bare / 'objects', gitdir / 'objects', dirs_exist_ok=True)
    if (bare / 'shallow').exists():
        shutil.copyfile(bare / 'shallow', gitdir / 'shallow')
    base = ['git', f'--git-dir={gitdir}', f'--work-tree={worktree}']
    if branch:
        run([*base, 'symbolic-ref', 'HEAD', f'refs/heads/{branch}'], env)
        run([*base, 'reset', '--hard', commit], env)
    else:
        run([*base, 'checkout', '--detach', '--force', commit, '--'], env)
    (worktree / '.git').unlink(missing_ok=True)
    return size


def checkout_repository(cache_root, organization_id, connector_id, repository, ref,
                        worktree, gitdir, *, run, git_env, token, authorize):
    """Refresh a scoped bare object cache, then materialize a private shallow checkout."""
    ttl = _positive_setting('PLATFORM_REPO_CACHE_TTL_SECONDS', _TTL)
    limit = _positive_setting('PLATFORM_REPO_CACHE_MAX_ENTRIES', _MAX_ENTRIES)
    max_bytes = _positive_setting('PLATFORM_REPO_CACHE_MAX_ENTRY_BYTES', _MAX_BYTES)
    tenant_key, key = cache_identity(organization_id, connector_id, repository)
    root = Path(cache_root).expanduser().absolute()
    tenant = root / tenant_key
    locks = tenant / 'locks'
    for path in (root, tenant, locks):
        _private_directory(path)
    entry = tenant / key
    bare = entry / 'objects.git'
    url = f'https://github.com/{repository}.git'
    # The object cache has no remote configuration or persisted authentication.
    network_env = git_env(worktree, token)
    network_env['GIT_DIR'] = str(bare)  # ls-remote must not discover the backend checkout's Git config.
    local_env = git_env(worktree)
    hit = False
    with _lock(locks / (key + '.lock')):
        authorize()
        if entry.exists() and (entry.is_symlink() or not entry.is_dir()):
            raise ToolAccessError('Invalid repository cache entry.')
        if entry.exists() and time.time() - entry.stat().st_mtime > ttl:
            shutil.rmtree(entry)
        if bare.is_symlink():
            raise ToolAccessError('Repository cache must not contain symbolic links.')
        hit = (bare / 'HEAD').is_file()
        if not hit:
            if entry.exists():
                shutil.rmtree(entry)
            _private_directory(entry)
            run(['git', 'init', '--bare', '--template=', str(bare)], local_env)
        try:
            _size(bare)  # Reject tampered cache paths before Git writes into them.
            remote_ref, branch = _remote_ref(run, network_env, url, ref)
            run(['git', 'check-ref-format', remote_ref], local_env)
            authorize()
            run(['git', f'--git-dir={bare}', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'fetch.fsckObjects=true',
                 'fetch', '--force', '--no-tags', '--no-recurse-submodules', '--depth=1',
                 '--', url, f'+{remote_ref}:refs/cache/tip'], network_env)
            commit = run(['git', f'--git-dir={bare}', 'rev-parse', 'refs/cache/tip^{commit}'], local_env).strip()
            if not _OID.fullmatch(commit):
                raise ToolAccessError('The repository cache returned an invalid commit.')
            authorize()
            # A normal copy prevents cache eviction, concurrent runs, commits or gc
            # from changing another execution's objects. Never copy config/remotes.
            size = materialize_checkout(bare, worktree, gitdir, commit, branch, run=run, env=local_env)
            authorize()
            os.utime(entry, None)
            if size > max_bytes:
                shutil.rmtree(entry)  # The independent checkout remains usable.
        except Exception:
            # Failed refreshes cannot leave a stale entry for a later offline reuse.
            shutil.rmtree(entry, ignore_errors=True)
            raise
    try:
        _prune(tenant, locks, key, ttl, limit)
    except OSError:
        logger.warning('Repository cache retention cleanup was deferred.')
    return {'hit': hit, 'refreshed': True, 'retained': size <= max_bytes,
            'commit': commit, 'base_branch': branch}
