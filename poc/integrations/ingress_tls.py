"""Point-in-time TLS certificate probe for a server-configured public endpoint."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from ipaddress import ip_address
import socket
import ssl
from threading import BoundedSemaphore
import time
from urllib.parse import urlsplit

_lookups = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingress-dns")
_slots = BoundedSemaphore(2)


def _global(address):
    if "%" in address:
        return False
    parsed = ip_address(address)
    mapped = getattr(parsed, "ipv4_mapped", None)
    if mapped is not None:
        parsed = mapped
    return parsed.is_global and not parsed.is_multicast and not parsed.is_reserved


def check_tls(configured_url: str) -> tuple[str, bool]:
    """Return the certificate result and whether a network lookup was attempted."""
    if not _slots.acquire(blocking=False):
        return "UNVERIFIED", False
    release = True
    try:
        endpoint = urlsplit(configured_url)
        deadline = time.monotonic() + 4
        hostname, port = endpoint.hostname, endpoint.port or 443
        try:
            future = _lookups.submit(socket.getaddrinfo, hostname, port, 0, socket.SOCK_STREAM)
        except RuntimeError:
            return "UNVERIFIED", False
        try:
            addresses = future.result(timeout=2)
        except TimeoutError:
            release = False
            future.add_done_callback(lambda _: _slots.release())
            return "UNVERIFIED", True
        if not addresses or any(not _global(address[-1][0]) for address in addresses):
            return "UNVERIFIED", True
        context = ssl.create_default_context()
        for family, kind, protocol, _, address in addresses[:4]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                with socket.socket(family, kind, protocol) as connection:
                    connection.settimeout(remaining)
                    connection.connect(address)
                    connection.settimeout(max(0.01, deadline - time.monotonic()))
                    with context.wrap_socket(connection, server_hostname=hostname):
                        return "VALID", True
            except ssl.SSLCertVerificationError:
                return "INVALID", True
            except OSError:
                continue
    except (OSError, ValueError):
        pass
    finally:
        if release:
            _slots.release()
    return "UNVERIFIED", True
