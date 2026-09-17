"""Signed GitHub push receiver; standard library only, no deployment privileges."""
import hashlib
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def validate(body, signature, event, secret, repository):
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not re.fullmatch(r'sha256=[0-9a-f]{64}', signature) or not hmac.compare_digest(expected, signature):
        return 403, 'Invalid signature', None
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError()
        repo = data.get('repository') or {}
        if not isinstance(repo, dict) or repo.get('full_name') != repository:
            return 403, 'Wrong repository', None
    except (ValueError, TypeError):
        return 400, 'Invalid payload', None
    if event == 'ping':
        return 200, 'pong', None
    if event != 'push' or data.get('ref') != 'refs/heads/main' or data.get('deleted'):
        return 200, 'Ignored event', None
    sha = data.get('after', '')
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha) or sha == '0' * 40:
        return 400, 'Invalid commit', None
    return 202, 'Queued', sha


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def do_POST(self):
        if self.path != '/hooks/github':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if not 0 < length <= 25 * 1024 * 1024:
            self.send_error(413)
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.send_error(400)
            return
        status, message, sha = validate(body, self.headers.get('X-Hub-Signature-256', ''),
                                        self.headers.get('X-GitHub-Event', ''),
                                        os.environ['WEBHOOK_SECRET'], os.environ['WEBHOOK_REPOSITORY'])
        if sha:
            delivery = self.headers.get('X-GitHub-Delivery', '')
            if not re.fullmatch(r'[0-9a-fA-F-]{36}', delivery):
                self.send_error(400)
                return
            spool = Path(os.environ['WEBHOOK_SPOOL'])
            seen = spool / 'seen' / delivery
            if seen.exists():
                status, message = 200, 'Already accepted'
            else:
                # Atomic replacement coalesces bursts; worker always fetches current main.
                temp = spool / ('pending.' + delivery)
                with temp.open('w') as output:
                    json.dump({'delivery': delivery, 'sha': sha}, output)
                    output.flush()
                    os.fsync(output.fileno())
                temp.replace(spool / 'pending.json')
                seen.touch()
        output = json.dumps({'message': message}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(output)))
        self.end_headers()
        self.wfile.write(output)


if __name__ == '__main__':
    HTTPServer((os.environ.get('WEBHOOK_BIND', '172.17.0.1'), 9000), Handler).serve_forever()
