"""Safe startup diagnosis contracts. No Docker or subprocess execution."""
import pytest
from workflows.sandbox_diagnostics import docker_failure


@pytest.mark.parametrize(('message', 'code'), [
    ('mounts denied: private workspace is not shared from the host', 'MOUNT_DENIED'),
    ('invalid mount config for type bind: bind source path does not exist', 'MOUNT_MISSING'),
    ('no matching manifest for linux/arm64/v8', 'ARCHITECTURE'),
    ('pull access denied: repository does not exist', 'IMAGE_ACCESS'),
    ('Cannot connect to the Docker daemon', 'DAEMON_UNAVAILABLE'),
    ('failed to resolve reference: network is unreachable', 'REGISTRY_NETWORK'),
    ('requested CPUs exceed the available limit', 'RESOURCE_LIMIT'),
    ('executable file not found in PATH', 'ENTRYPOINT'),
    ('no space left on device', 'DISK_FULL'),
])
def test_safe_known_error_categories(message, code):
    result = docker_failure(message, 125)
    assert code in result and 'Docker exit 125' in result


def test_raw_secrets_paths_and_malicious_exit_strings_never_leave_boundary():
    raw = 'unknown private error: token=super-secret /private/customer/repo'
    result = docker_failure(raw, 'super-secret')
    assert 'START_REJECTED' in result
    assert 'super-secret' not in result and '/private/customer/repo' not in result
    assert 'Docker exit' not in result
    assert result == docker_failure(raw.encode(), 'super-secret')


def test_disk_failure_takes_precedence_over_pull_noise():
    result = docker_failure('Unable to find image locally; pull access denied: no space left on device', 125)
    assert 'DISK_FULL' in result
