"""HTTPS CONNECT egress proxy for repository sandboxes (stdlib only; runs in its own container).

Usage: python3 egress_proxy.py host1.example.com,host2.example.com
Only CONNECT to an exact allowlisted hostname on port 443 is accepted, and only to a
globally routable address (no private, loopback, link-local or metadata IPs). The
resolved address is dialed directly, so DNS cannot rebind between check and connect.
Plain HTTP is refused, so sandboxed code cannot send secrets in cleartext.
"""
import ipaddress
import select
import socket
import sys
import threading

PORT = 3128
MAX_CONNECTIONS = 64
IDLE_SECONDS = 300
_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)


def _reply(client, status):
    try:
        client.sendall(f'HTTP/1.1 {status}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'.encode())
    except OSError:
        pass


def _public_address(host):
    for family, kind, proto, _, address in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        if ipaddress.ip_address(address[0]).is_global:
            return family, kind, proto, address
    return None


def _pipe(client, upstream):
    sockets = [client, upstream]
    while True:
        readable, _, failed = select.select(sockets, [], sockets, IDLE_SECONDS)
        if failed or not readable:
            return
        for source in readable:
            data = source.recv(65536)
            if not data:
                return
            (upstream if source is client else client).sendall(data)


def _handle(client, allowed):
    upstream = None
    try:
        client.settimeout(30)
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = client.recv(4096)
            if not chunk or len(head) > 8192:
                return
            head += chunk
        request, _, rest = head.partition(b'\r\n\r\n')
        parts = request.split(b'\r\n', 1)[0].decode('latin-1').split()
        if len(parts) != 3 or parts[0] != 'CONNECT':
            return _reply(client, '405 Only HTTPS CONNECT is allowed')
        host, _, port = parts[1].rpartition(':')
        host = host.strip('[]').lower().rstrip('.')
        if port != '443' or host not in allowed:
            print(f'denied {parts[1]}', flush=True)
            return _reply(client, '403 Host not allowlisted')
        target = _public_address(host)
        if target is None:
            print(f'denied non-public {host}', flush=True)
            return _reply(client, '403 Host resolves to a non-public address')
        family, kind, proto, address = target
        upstream = socket.socket(family, kind, proto)
        upstream.settimeout(15)
        upstream.connect(address)
        upstream.settimeout(None)
        client.settimeout(None)
        client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        if rest:
            upstream.sendall(rest)
        print(f'allowed {host}', flush=True)
        _pipe(client, upstream)
    except OSError:
        _reply(client, '502 Upstream connection failed')
    finally:
        for sock in (client, upstream):
            if sock is not None:
                sock.close()
        _slots.release()


def main():
    allowed = {h.strip().lower() for h in (sys.argv[1] if len(sys.argv) > 1 else '').split(',') if h.strip()}
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', PORT))
    server.listen(128)
    while True:
        client, _ = server.accept()
        if not _slots.acquire(blocking=False):
            _reply(client, '503 Too many connections')
            client.close()
            continue
        threading.Thread(target=_handle, args=(client, allowed), daemon=True).start()


if __name__ == '__main__':
    main()
