#!/usr/bin/env python3
"""R2B.1 isolated control-only HTTP server. No admission or media preparation."""
import argparse
import json
import re
import secrets
from urllib.parse import urlsplit
try:
    from . import lcd_stream_server as base
    from .start_fence import StartFence, FenceError, MAX_REVISION
except ImportError:
    import lcd_stream_server as base
    from start_fence import StartFence, FenceError, MAX_REVISION

PROTOCOL = 'start-fence-v1'

class ControlOnlyApp:
    mode = 'control-only'

    def __init__(self, *, fence=None, allowed_hosts=()):
        self.fence = fence if fence is not None else StartFence()
        self.allowed_hosts = {h.lower().rstrip('.') for h in allowed_hosts}
        self.token = secrets.token_hex(24)
        self.html = '<!doctype html><title>WAPFLIX control-only</title><p>Control-only: playback unavailable.</p>'

    def close(self):
        # This mode cannot own workers. Never silently release unexpected ownership.
        owner = self.fence.close()
        if owner is not None:
            raise RuntimeError('Unexpected owner requires cleanup; ownership retained')


def make_handler(app):
    if not isinstance(app, ControlOnlyApp) or app.mode != 'control-only':
        raise ValueError('R2B.1 requires an isolated ControlOnlyApp')
    Parent = base.make_handler(app)

    class Handler(Parent):
        def do_GET(self):
            if not self.host_ok():
                return self.reply(403, {'error': 'Invalid Host'})
            if urlsplit(self.path).path == '/':
                return self.reply(200, app.html.encode(), 'text/html; charset=utf-8')
            if not self.authorized(self.headers.get('X-Wapflix-Test')):
                return self.reply(403, {'error': 'Forbidden'})
            return self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.host_ok():
                return self.reply(403, {'error': 'Invalid Host'})
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + self.headers['Host']:
                return self.reply(403, {'error': 'Invalid Origin'})
            try:
                if self.headers.get('Transfer-Encoding') is not None:
                    raise ValueError('Transfer-Encoding is unsupported')
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                    raise ValueError('Invalid request size')
                size = int(lengths[0])
                if not 0 < size <= 4096:
                    raise ValueError('Invalid request size')
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('Incomplete request body')
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError('Expected an object')
                if not self.authorized(self.headers.get('X-Wapflix-Test') or body.get('token')):
                    return self.reply(403, {'error': 'Forbidden'})
                path = urlsplit(self.path).path
                if path == '/api/start':
                    return self.reply(409, {'error': 'Start admission unavailable in control-only mode',
                                            'code': 'fenced_admission_unavailable'})
                if path == '/api/control/open':
                    if set(body) - {'token'}:
                        raise ValueError('Unexpected control-open fields')
                    client = app.fence.open_client()
                    return self.reply(200, {'control_protocol': PROTOCOL,
                                           'control_client_id': client,
                                           'control_lease_seconds': 60})
                if path == '/api/control/cancel':
                    if set(body) - {'token', 'control_client_id', 'cancel_through'}:
                        raise ValueError('Unexpected cancellation fields')
                    client = body.get('control_client_id')
                    revision = body.get('cancel_through')
                    if not isinstance(client, str) or re.fullmatch(r'[0-9a-f]{48}', client) is None:
                        raise ValueError('Invalid control_client_id')
                    if type(revision) is not int or not 0 <= revision <= MAX_REVISION:
                        raise ValueError('Invalid cancel_through')
                    owner = app.fence.cancel(client, revision)
                    if owner is not None:
                        # No cleanup factory exists in this pass: retain ownership.
                        return self.reply(503, {'error': 'Owner cleanup unavailable',
                            'code': 'cleanup_unconfirmed', 'fence_recorded': True,
                            'cleanup': 'unconfirmed'})
                    return self.reply(200, {'fence_recorded': True, 'cleanup': 'not_required'})
                return self.reply(404, {'error': 'Not found'})
            except FenceError as error:
                code = error.code
                if code in ('unknown_client', 'client_expired'):
                    return self.reply(404, {'error': 'Control client gone', 'code': 'control_client_gone'})
                status = 429 if code == 'client_capacity' else 409
                return self.reply(status, {'error': str(error), 'code': code})
            except (ValueError, TypeError, UnicodeError):
                return self.reply(400, {'error': 'Invalid control request', 'code': 'invalid_request'})
            except TimeoutError:
                return self.reply(408, {'error': 'Request timeout'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8102)
    parser.add_argument('--allow-host', action='append', default=[])
    args = parser.parse_args()
    app = ControlOnlyApp(allowed_hosts=args.allow_host)
    server = base.Server((args.bind, args.port), make_handler(app))
    try:
        print(f'Control-only HTTP on {args.bind}:{server.server_port}; no Start admission.', flush=True)
        print(f'X-Wapflix-Test capability: {app.token}', flush=True)
        print('Trusted LAN/Tailscale only; do not expose publicly.', flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()

if __name__ == '__main__':
    main()
