"""Real local Git/filesystem cache contracts. Not executed under current restrictions."""
import os
import shutil
import subprocess
import time

import pytest
from integrations.repo_cache import cache_identity, materialize_checkout, _private_directory, _prune
from integrations.repo_workspace import _git_env, _run
from integrations.tool_definitions import ToolAccessError


def git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                          capture_output=True, text=True, env=_git_env(root)).stdout.strip()


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    git(root, 'init', '--template=')
    git(root, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    (root / 'version.txt').write_text('original\n')
    git(root, 'add', '--', 'version.txt')
    git(root, '-c', 'user.name=Local contract', '-c', 'user.email=local@example.test',
        'commit', '--no-gpg-sign', '-m', 'Initial content')
    return root, git(root, 'rev-parse', 'HEAD')


def test_identity_separates_tenants_connectors_and_repositories():
    base = cache_identity('org-a', 'github-a', 'Team/Repo')
    assert base == cache_identity('org-a', 'github-a', 'team/repo')
    assert base != cache_identity('org-b', 'github-a', 'Team/Repo')
    assert base != cache_identity('org-a', 'github-b', 'Team/Repo')
    assert base != cache_identity('org-a', 'github-a', 'Team/Other')


def test_private_checkout_survives_cache_eviction_and_isolates_edits(source, tmp_path):
    root, commit = source
    checkout, metadata = tmp_path / 'run' / 'repo', tmp_path / 'run' / 'git'
    checkout.parent.mkdir()
    materialize_checkout(root / '.git', checkout, metadata, commit, 'main',
                         run=_run, env=_git_env(checkout))
    assert not (checkout / '.git').exists()
    assert not (metadata / 'objects/info/alternates').exists()
    (checkout / 'version.txt').write_text('run-only change\n')
    assert (root / 'version.txt').read_text() == 'original\n'
    objects = [path for path in (metadata / 'objects').rglob('*') if path.is_file()]
    assert objects and all(path.stat().st_nlink == 1 for path in objects)
    shutil.rmtree(root)
    assert _run(['git', f'--git-dir={metadata}', 'cat-file', '-e', commit], _git_env(checkout)) == ''


def test_checkouts_use_requested_commit_and_detached_tags(source, tmp_path):
    root, initial = source
    (root / 'version.txt').write_text('updated\n')
    git(root, 'add', '--', 'version.txt')
    git(root, '-c', 'user.name=Local contract', '-c', 'user.email=local@example.test',
        'commit', '--no-gpg-sign', '-m', 'New content')
    current = git(root, 'rev-parse', 'HEAD')
    for label, commit, branch, expected in [('old-tag', initial, None, 'original\n'),
                                            ('new-branch', current, 'main', 'updated\n')]:
        parent = tmp_path / label
        parent.mkdir()
        materialize_checkout(root / '.git', parent / 'repo', parent / 'git', commit, branch,
                             run=_run, env=_git_env(parent / 'repo'))
        assert (parent / 'repo/version.txt').read_text() == expected
        assert (parent / 'git/HEAD').read_text().strip() == ('ref: refs/heads/main' if branch else commit)


def test_external_object_alternates_and_symlink_cache_are_rejected(source, tmp_path):
    root, commit = source
    (root / '.git/objects/info/alternates').write_text('/another/object/store\n')
    with pytest.raises(ToolAccessError, match='external object stores'):
        materialize_checkout(root / '.git', tmp_path / 'run', tmp_path / 'git', commit, 'main',
                             run=_run, env=_git_env(tmp_path / 'run'))
    link = tmp_path / 'cache-link'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ToolAccessError, match='symbolic link'):
        _private_directory(link)


def test_idle_ttl_and_lru_pruning_preserve_current_entry(tmp_path):
    tenant, locks = tmp_path / 'tenant', tmp_path / 'tenant/locks'
    locks.mkdir(parents=True)
    names = ['a' * 64, 'b' * 64, 'c' * 64]
    for index, name in enumerate(names):
        path = tenant / name
        path.mkdir()
        (path / 'marker').write_text('cached')
        timestamp = time.time() - index * 100
        os.utime(path, (timestamp, timestamp))
    _prune(tenant, locks, names[0], ttl=150, limit=1)
    assert (tenant / names[0]).exists()
    assert not (tenant / names[1]).exists()
    assert not (tenant / names[2]).exists()
