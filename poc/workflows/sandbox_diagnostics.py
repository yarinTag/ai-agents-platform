"""Safe Docker startup diagnostics: static classifications, never raw stderr.

Docker errors can echo private mount paths, repository names or environment
values. Only fixed messages, numeric exit status and a correlation hash leave
the startup boundary.
"""
import hashlib

_RULES = (
    ('DISK_FULL', ('no space left on device', 'disk quota exceeded'),
     'Docker storage is full. Free space in Docker storage and on the host.'),
    ('MOUNT_DENIED', ('mounts denied', 'is not shared from the host', 'file sharing',
                      'permission denied while mounting'),
     'Docker cannot mount the workspace. Check Docker Desktop file sharing and host permissions.'),
    ('MOUNT_MISSING', ('bind source path does not exist', 'invalid mount config',
                       'invalid volume specification'),
     'Docker cannot access the workspace bind mount. The daemon must see the same workspace path as the backend.'),
    ('ARCHITECTURE', ('no matching manifest for', 'exec format error', 'does not match the detected host platform'),
     'The sandbox image does not match the Docker host architecture. Configure a compatible digest-pinned image.'),
    ('IMAGE_ACCESS', ('pull access denied', 'requested access to the resource is denied',
                      'unauthorized: authentication required', 'manifest unknown', 'manifest not found',
                      'repository does not exist', 'no such image', 'not found: manifest'),
     'Docker cannot fetch the configured image digest. Check the image reference, availability and registry authentication.'),
    ('DAEMON_UNAVAILABLE', ('cannot connect to the docker daemon', 'is the docker daemon running',
                            'error during connect', 'permission denied while trying to connect'),
     'The backend cannot reach Docker. Check the daemon, Docker context and socket permissions.'),
    ('REGISTRY_NETWORK', ('tls handshake timeout', 'i/o timeout', 'network is unreachable',
                          'no such host', 'certificate signed by unknown authority',
                          'failed to resolve reference', 'toomanyrequests'),
     'Docker could not reach or trust the image registry. Check registry connectivity, DNS, certificates and rate limits.'),
    ('RESOURCE_LIMIT', ('insufficient memory', 'cannot allocate memory', 'requested cpus',
                        'range of cpus', 'minimum memory', 'memory limit'),
     'Docker rejected the resource limits. Check available Docker resources and the workflow machine size.'),
    ('ENTRYPOINT', ('executable file not found',
                   'unable to find user', 'no matching entries in passwd file'),
     'The image cannot run the sandbox entrypoint or user. The Direct API sandbox image must provide sleep and the required toolchain.'),
)


def docker_failure(stderr, exit_code=None):
    """Return a credential-free code/message/reference, not a copy of the error."""
    raw = stderr.decode(errors='replace') if isinstance(stderr, bytes) else str(stderr or '')
    lowered = raw.lower()
    code, message = 'START_REJECTED', (
        'Docker rejected sandbox startup. The Docker error did not match a known safe diagnostic; inspect it on the server.')
    for identifier, patterns, hint in _RULES:
        if any(pattern in lowered for pattern in patterns):
            code, message = identifier, hint
            break
    status = f', Docker exit {exit_code}' if type(exit_code) is int else ''
    reference = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f'{message} [{code}{status}; reference {reference}]'
