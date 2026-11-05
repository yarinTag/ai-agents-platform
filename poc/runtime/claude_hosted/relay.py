"""Container-only HTTP -> private Unix-socket relay, with no external networking."""
import http.client
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 2_000_000


class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(150)
        self.sock.connect('/broker/broker.sock')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        connection = None
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                raise ValueError('Invalid request.')
            connection = UnixConnection('broker', timeout=150)
            connection.request('POST', self.path, self.rfile.read(size), headers={
                'Content-Type': 'application/json', 'x-api-key': self.headers.get('x-api-key', ''),
                'Authorization': self.headers.get('Authorization', '')})
            response = connection.getresponse()
            data = response.read(16_000_001)
            if len(data) > 16_000_000:
                raise ValueError('Response too large.')
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(502, 'Hosted broker unavailable')
        finally:
            if connection:
                connection.close()


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
