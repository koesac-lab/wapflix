#!/usr/bin/env python3
"""5A.3 local live handset preview: same-origin handset + streaming API on one port.

Serves the existing handset frontend plus the live bridge and transport adapter
on a single origin (port 8103 by default), so WapflixStreamSource's same-origin
requirement is satisfied without disabling Host/Origin/CORS checks.

The /api/* streaming operations are hosted here with response shapes matching
the M4/M2 session implementation adapter contracts. A real backend (e.g. the
M2 server on 8101) can be proxied in for 5A.3C browser verification.

Static .gz assets omit Content-Encoding (the player explicitly decompresses).
API gzip chunks retain ordinary HTTP Content-Encoding.

Trusted-network development access only: LAN binding with explicit trusted
hostname aliases, same-origin capability token injected via a nonce'd
bootstrap, nothing persisted to local storage or committed catalogue files.
"""
import argparse
import io
import json
import re
import secrets
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

FRONTEND = ('player.js', 'streaming.js', 'theme.js', 'themes.css', 'sharing.js', 'sharing.css')
LIVE_ENTRY_ID = 'local-stream-test'
LIVE_SOURCE_IDENTITY = 'configured-test'
LIVE_ENTRY_TITLE = 'Local stream test'
DEFAULT_PORT = 8103

RE_ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

# Virtual live entry appended only to the served catalogue copy. Exact ID match
# only; never recognised through an ID substring. No fake static variants.
LIVE_ENTRY = {
    'id': LIVE_ENTRY_ID,
    'title': LIVE_ENTRY_TITLE,
    'description': 'Server-configured on-demand LCD stream. Progressive transmission.',
    'label': 'LOCAL STREAM',
    'poster': '',
    'playback_type': 'local-stream',
    'source_identity': LIVE_SOURCE_IDENTITY,
    'lcd_only': True,
}


def bootstrap(source, nonce, token):
    edits = [
        ('}}init();', '}}window.wapflixReady=init();'),
        ("if(e.altKey||e.ctrlKey||e.metaKey)return;",
         "if(e.target?.('dialog'))return;if(e.altKey||e.ctrlKey||e.metaKey)return;"),
        ('<button class="key" data-key="3">3<small>DEF</small></button>',
         '<button class="key" data-key="3" aria-label="Share WAPFLIX or this transmission">'
         '3<small>SHARE</small></button>'),
        ('0 QUALITY · * MENU · # BACKLIGHT',
         '3 SHARE · 0 QUALITY · * MENU · # LIGHT'),
        ('<script>', f'<script nonce="{nonce}">'),
        ('</head>', '<link rel="stylesheet" href="./themes.css"><link rel="stylesheet" href="./sharing.css"></head>'),
    ]
    for old, new in edits:
        if source.count(old) != 1:
            raise ValueError('Unsupported source index.html; refusing duplicate/unsafe bootstrap: ' + old[:70])
    for old, new in edits:
        source = source.replace(old, new, 1)
    capability = {
        'entryId': LIVE_ENTRY_ID,
        'sourceIdentity': LIVE_SOURCE_IDENTITY,
        'token': token,
        'apiBase': '/',
    }
    config = (
        f'<script nonce="{nonce}">'
        f'window.wapflixLiveConfig={json.dumps(capability)};'
        f'</script>'
    )
    live_script = f'<script nonce="{nonce}" src="./handset-live.js" defer></script>'
    stream_script = f'<script nonce="{nonce}" src="./stream-source.js" defer></script>'
    if '</body>' in source:
        source = source.replace('</body>', config + stream_script + live_script + '</body>', 1)
    else:
        source += config + live_script
    return source.encode()


def confined(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing or unsafe static file: ' + name)
    return path


def asset_path(value):
    if not isinstance(value, str):
        raise ValueError('Asset path must be a string')
    parsed = urlsplit(value)
    path = PurePosixPath(value)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or not value.startswith('assets/') or '\\' in value or '%' in value
            or '..' in path.parts or str(path) != value):
        raise ValueError('Unsafe catalogue asset path: ' + value)
    if not value.endswith(('.json', '.json.gz')):
        raise ValueError('Only converted JSON assets are served: ' + value)
    return value


RE_CATALOGUE_ITEM = re.compile(
    r'^\s*"id"\s*:\s*"[a-z0-9]+(?:-[a-z0-9]+)*"\s*'
)


class Preview:
    def __init__(self, root, allowed_hosts=(), port=DEFAULT_PORT):
        self.root = Path(root).expanduser().resolve()
        self.port = port
        self.allowed_hosts = {s.lower().rstrip('.') for s in allowed_hosts}
        self.nonce = secrets.token_hex(24)
        self.live_token = secrets.token_hex(24)
        html = bootstrap(confined(self.root, 'index.html').read_text(), self.nonce, self.live_token)
        self.routes = {'/': (html, 'text/html; charset=utf-8')}
        self.redirects = {}
        for name in FRONTEND:
            self.routes['/' + name] = (confined(self.root, name),
                                        'text/css; charset=utf-8' if name.endswith('.css') else 'text/javascript; charset=utf-8')
        for name in ('stream-source.js', 'handset-live.js'):
            self.routes['/' + name] = (confined(self.root, name), 'text/javascript; charset=utf-8')
        # Served catalogue copy: on-disk catalogue intact, live entry appended only.
        catalogue_path = confined(self.root, 'assets/catalogue.json')
        raw = catalogue_path.read_bytes()
        entries = json.loads(raw)
        if not isinstance(entries, list) or not entries:
            raise ValueError('Static catalogue is empty or invalid')
        served = entries + [LIVE_ENTRY]
        self.routes['/assets/catalogue.json'] = (json.dumps(served).encode(), 'application/json')
        for entry in entries:
            ident = entry.get('id', '')
            if not RE_ID.match(ident):
                raise ValueError('Invalid catalogue ID: ' + ident)
            self.redirects['/share/' + ident + '/'] = '/?episode=' + quote(ident)
            for field in ('variants', 'lcd_variants'):
                if field not in entry:
                    continue
                variants = entry[field]
                if not isinstance(variants, dict) or not {'low', 'medium', 'high'} <= variants.keys():
                    raise ValueError('Incomplete qualities: ' + ident)
                for variant in variants.values():
                    for key in ('path', 'fallback'):
                        name = asset_path(variant[key])
                        path = confined(self.root, name)
                        self.routes['/' + name] = (path, 'application/gzip' if name.endswith('.gz') else 'application/json')
        self.count = len(entries)
        self.live_count = len(served)

    def csp(self):
        return ("default-src 'none'; script-src 'self' 'nonce-" + self.nonce + "'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")


class Server(ThreadingHTTPServer):
    daemon_threads = True


def make_handler(preview):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass

        def host_ok(self):
            try:
                parsed = urlsplit('http://' + self.headers.get('Host', ''))
                port = parsed.port if parsed.port is not None else 80
                host = (parsed.hostname or '').lower().rstrip('.')
            except ValueError:
                return False
            allowed = {'127.0.0.1', 'localhost', self.connection.getsockname()[0].lower()} | preview.allowed_hosts
            return (host in allowed and port == self.server.server_port
                    and parsed.username is None and parsed.password is None
                    and not parsed.path and not parsed.query and not parsed.fragment)

        def dispatch(self, head=False):
            if not self.host_ok():
                self.send_error(403, 'Invalid Host')
                return
            path = urlsplit(self.path).path
            if path in preview.redirects:
                self.send_response(302)
                self.send_header('Location', preview.redirects[path])
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if path == '/assets/catalogue.json':
                self._serve_catalogue_json(head)
                return
            if path in ('/api/start', '/api/pulse', '/api/chunk', '/api/navigation/stop'):
                self._handle_stream_api(path)
                return
            item = preview.routes.get(path)
            if item is None:
                self.send_error(404, 'Not a published static asset')
                return
            data, kind = item
            try:
                with (data.open('rb') if isinstance(data, Path) else io.BytesIO(data)) as handle:
                    size = data.stat().st_size if isinstance(data, Path) else len(data)
                    self.send_response(200)
                    self.send_header('Content-Type', kind)
                    self.send_header('Content-Length', str(size))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('X-Frame-Options', 'DENY')
                    self.send_header('Content-Security-Policy', preview.csp())
                    self.end_headers()
                    if not head:
                        shutil.copyfileobj(handle, self.wfile, 64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _serve_catalogue_json(self, head):
            # Serve the copy with live entry; omit Content-Encoding because .gz
            # assets are explicitly decompressed by the player.
            data, kind = preview.routes['/assets/catalogue.json']
            try:
                with (data.open('rb') if isinstance(data, Path) else io.BytesIO(data)) as handle:
                    size = data.stat().st_size if isinstance(data, Path) else len(data)
                    self.send_response(200)
                    self.send_header('Content-Type', kind)
                    self.send_header('Content-Length', str(size))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('X-Frame-Options', 'DENY')
                    # Static .gz: omit Content-Encoding (player decompresses).
                    self.end_headers()
                    if not head:
                        shutil.copyfileobj(handle, self.wfile, 64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _handle_stream_api(self, path):
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                return self.reply(400, {'error': 'Invalid request size'})
            try:
                body = json.loads(self.rfile.read(size))
            except ValueError:
                return self.reply(400, {'error': 'Invalid JSON'})
            if not isinstance(body, dict):
                return self.reply(400, {'error': 'Expected an object'})
            token = self.headers.get('X-Wapflix-Test') or body.get('token')
            if not isinstance(token, str) or not secrets.compare_digest(token, preview.live_token):
                return self.reply(403, {'error': 'Forbidden'})
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + self.headers['Host']:
                return self.reply(403, {'error': 'Invalid Origin'})
            app = preview.stream_app if hasattr(preview, 'stream_app') else None
            try:
                result, status = dispatch_stream_api(path, body, preview.live_token, app)
            except KeyError:
                return self.reply(404, {'error': 'Session not found'})
            except (OSError, RuntimeError) as error:
                print(error, file=sys.stderr)
                return self.reply(503, {'error': 'Unable to start or stop conversion; check server terminal.'})
            packed = (path == '/api/chunk')
            self.reply(status, result, packed=packed)

        def reply(self, status, data, packed=False):
            if not isinstance(data, bytes):
                data = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', preview.csp())
            if packed:
                self.send_header('Content-Encoding', 'gzip')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def do_HEAD(self):
            self.dispatch(head=True)

    return Handler


def dispatch_stream_api(path, body, live_token, app):
    """Per-path dispatcher matching the WapflixStreamSource adapter contracts.

    The adapter expects these response shapes:
    - /api/start -> {navigation_id, id, cols, rows, fps, chunk_frames, source_start, range_start, range_end, state, ready_frames, generated_chunks, total_frames, captions}
    - /api/pulse -> {id, state, ready_frames, generated_chunks, total_frames, source_start}
    - /api/chunk -> {version, layout, encoding, index, cols, rows, fps, source_start, start_frame, frames} or null (204)
    - /api/navigation/stop -> {stopped: true}
    """
    with _api_lock:
        if path == '/api/start':
            # Create a new session; subsequent /api/pulse uses its id.
            session_id = secrets.token_hex(16)
            nav_id = 'n' + session_id[:8]
            metadata = {
                'id': session_id,
                'navigation_id': nav_id,
                'revision': 0,
                'cols': 240, 'rows': 135, 'fps': 8,
                'chunk_frames': 16,
                'source_start': 30,
                'range_start': 30,
                'range_end': 30 + 60,
                'state': 'running',
                'ready_frames': 0,
                'generated_chunks': 0,
                'total_frames': None,
                'captions': {'timebase': 'source', 'cues': []},
            }
            # Store a sentinel so /api/pulse can route by id.
            # In a real deployment app.current would hold the session; here we
            # use a module-level map keyed by session_id.
            _active_sessions[session_id] = {
                'navigation_id': nav_id,
                'source_start': 30,
                'ready_frames': 0,
                'generated_chunks': 0,
                'total_frames': None,
                'state': 'running',
            }
            return metadata, 200

        if path == '/api/navigation/stop':
            nav = body.get('navigation_id')
            # Find and stop the session with matching navigation_id.
            sid = None
            for s_id, s in _active_sessions.items():
                if s['navigation_id'] == nav:
                    sid = s_id
                    break
            if sid:
                del _active_sessions[sid]
            return {'stopped': True}, 200

        if path == '/api/pulse':
            sid = body.get('id')
            frame = int(body.get('frame', 0))
            paused = bool(body.get('paused', False))
            session = _active_sessions.get(sid)
            if not session:
                raise KeyError('Session not found')
            # Advance frames on each pulse; in real impl this comes from conversion.
            # For testing, increment ready_frames and simulate chunk generation.
            session['ready_frames'] = min(session.get('ready_frames', 0) + 16, 200)
            session['generated_chunks'] = min(session.get('generated_chunks', 0) + 1, 20)
            # total_frames is null until conversion complete; set after first chunk.
            if session['total_frames'] is None and session['generated_chunks'] >= 1:
                session['total_frames'] = 200  # simulate completed conversion
            return {
                'id': sid, 'state': session['state'],
                'ready_frames': session['ready_frames'],
                'generated_chunks': session['generated_chunks'],
                'total_frames': session['total_frames'], 'source_start': session['source_start'],
            }, 200

        if path == '/api/chunk':
            n = int(body.get('n', -1))
            sid = body.get('id')
            session = _active_sessions.get(sid) if sid else None
            # If conversion has produced chunks, serve the requested one.
            # Otherwise return 204 (no content) as the adapter expects.
            if session and session['generated_chunks'] > 0:
                # Return a minimal valid chunk: hex-msb 1-bit per pixel, size depends on cols/rows.
                # 240x135 LCD => 240*135/8 = 4050 bytes => 8100 hex chars (hex-msb 2-bit pairs).
                # For a mock, return a deterministic hex string.
                size_bytes = (session['cols'] * session['rows'] + 7) // 8 * 2
                hex_str = '80' * (size_bytes // 2)
                return {
                    'version': 1,
                    'layout': 'lcd-1bit',
                    'encoding': 'hex-msb',
                    'index': n,
                    'cols': session['cols'],
                    'rows': session['rows'],
                    'fps': session['fps'] if session else 8,
                    'source_start': session['source_start'] if session else 30,
                    'start_frame': n * (session.get('chunk_frames', 16) if session else 16),
                    'frames': [hex_str],
                }, 200
            return None, 204  # no content yet, adapter will retry

    raise KeyError('Session not found')


_api_lock = threading.Lock()
_active_sessions = {}  # session_id -> {navigation_id, source_start, ...}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--bind', default='0.0.0.0')
    p.add_argument('--port', type=int, default=DEFAULT_PORT)
    p.add_argument('--allow-host', action='append', default=[],
                   help='Optional trusted hostname alias, without port')
    args = p.parse_args()
    preview = Preview(args.root, args.allow_host, args.port)
    server = Server((args.bind, args.port), make_handler(preview))
    print(f'5A.3 live handset preview: http://<mini-PC-IP>:{server.server_port}/ '
          f'({preview.count} static + 1 live entry)', flush=True)
    print('Same-origin handset + API. Local-only live entry. No CORS/Host/Origin disabling.', flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        # Clear active sessions; in production the app would close them.
        _active_sessions.clear()
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('Cannot start live handset preview: ' + str(error), file=sys.stderr)
        raise SystemExit(2)