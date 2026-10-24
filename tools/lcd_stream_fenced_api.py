"""R2B.4 opt-in fenced M4 HTTP server. No adapter/handset changes.

Run as python3 -m tools.lcd_stream_fenced_api --enable-fenced --video ...
Legacy lcd_stream_seek_viewer and control-only entry points remain separate.
"""
import argparse
import json
import math
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
from . import lcd_stream_server as base
from .lcd_m4_factory import FixedSource, M4Factory, M4Candidate
from .start_coordinator import StartCoordinator, CoordinatorError
from .start_fence import StartFence, FenceError, AdmissionFailed, MAX_REVISION

PROTOCOL = 'start-fence-v1'

class NavigationFence(StartFence):
    """Narrow core extension for atomic replacement within the SAME owner.

    Core-private access is confined here. Never hold this lock for probe/reap.
    The callback has the same short/nonblocking contract as core admit().
    """
    def update_owner(self, ticket, owner_id, action):
        with self._lock:
            record = self._check(ticket)
            if self._active != (ticket, owner_id):
                raise FenceError('owner_not_active')
            if record.outcome != 'admitted':
                raise AdmissionFailed(owner_id)
            try:
                action(owner_id)
            except BaseException as error:
                record.outcome = 'failed'
                raise AdmissionFailed(owner_id) from error

class NavigationCandidate(M4Candidate):
    def __init__(self, session, spec, track, ticket, *, range_start=None,
                 range_end=None, navigation_id=None, revision=0):
        super().__init__(session, spec, track, ticket)
        self.range_start = spec.start if range_start is None else range_start
        self.range_end = spec.start + session.stream.seconds if range_end is None else range_end
        if navigation_id is not None:
            self.navigation_id = navigation_id
        self.seek_revision = revision
        self.requested_revision = revision

    def snapshot(self):
        result = super().snapshot()
        result.update(range_start=self.range_start, range_end=self.range_end,
                      revision=self.seek_revision)
        return result

class NavigationFactory(M4Factory):
    def prepare(self, spec, ticket):
        candidate = super().prepare(spec, ticket)
        return NavigationCandidate(candidate.session, candidate.spec,
                                   candidate._track, candidate._ticket)

class FencedApp(StartCoordinator):
    mode = 'fenced'

    def __init__(self, spec, *, subtitles=None, no_srt=False, allowed_hosts=(),
                 lease=15, monitor=True, fence=None):
        if type(lease) not in (int, float) or not math.isfinite(lease) or lease <= 0:
            raise ValueError('Invalid playback lease')
        super().__init__(NavigationFactory(spec, subtitles=subtitles, no_srt=no_srt),
                         fence=fence if fence is not None else NavigationFence())
        if not isinstance(self.fence, NavigationFence):
            raise ValueError('NavigationFence is required')
        self.token = secrets.token_hex(24)
        self.allowed_hosts = {h.lower().rstrip('.') for h in allowed_hosts}
        self.html = b'<!doctype html><title>WAPFLIX fenced API</title><p>Experimental fenced API. Browser adapter not connected.</p>'
        self.lease = lease
        self._seek_slots = threading.BoundedSemaphore(4)
        self._closing = threading.Event()
        self._monitor = None
        if monitor:
            self._monitor = threading.Thread(target=self._reap, daemon=True)
            self._monitor.start()

    def begin(self, client, revision):
        return self.start(client, revision, self.factory.spec)

    def _active(self, *, navigation=None, session_id=None):
        owner = self._owner
        if owner is None or not owner.admitted:
            raise CoordinatorError('navigation_ended')
        candidate = owner.candidate
        if navigation is not None and candidate.navigation_id != navigation:
            raise CoordinatorError('navigation_superseded')
        if session_id is not None and candidate.session.id != session_id:
            raise KeyError('Session not found')
        if candidate.session.stop_event.is_set():
            raise CoordinatorError('navigation_ended')
        return owner

    def pulse(self, session_id, frame, paused):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError('id is required')
        with self._lifecycle():
            owner = self._active(session_id=session_id)
            result = owner.candidate.session.pulse(frame, paused)
            # Only validated traffic for the matching current session renews control.
            self.fence.touch(owner.ticket.client)
            return result

    def chunk(self, session_id, index):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError('id is required')
        with self._lifecycle():
            session = self._active(session_id=session_id).candidate.session
            with session.lock:
                data = session.chunks.get(index)
                old = index < session.generated and data is None
            return data, old

    def stop_navigation(self, navigation):
        if not isinstance(navigation, str) or not navigation:
            raise ValueError('navigation_id is required')
        with self._lifecycle():
            if self._owner is None or self._owner.candidate.navigation_id != navigation:
                return {'stopped': True, 'superseded': True}
            ticket = self._owner.ticket
        # Scoped tombstone, including any pending seek, before waiting for cleanup.
        self.cancel(ticket.client, ticket.revision)
        return {'stopped': True, 'superseded': False}

    def stop_session(self, session_id):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError('id is required')
        with self._lifecycle():
            if self._owner is None or self._owner.candidate.session.id != session_id:
                raise KeyError('Session not found')
            navigation = self._owner.candidate.navigation_id
        return self.stop_navigation(navigation)

    def seek(self, navigation, revision, position):
        if not isinstance(navigation, str) or not navigation:
            raise ValueError('navigation_id is required')
        if type(revision) is not int or not 1 <= revision <= MAX_REVISION:
            raise ValueError('Invalid seek revision')
        if type(position) not in (int, float) or not math.isfinite(position):
            raise ValueError('Invalid seek position')
        if not self._seek_slots.acquire(blocking=False):
            raise CoordinatorError('preparation_capacity')
        try:
            with self._lifecycle():
                owner = self._active(navigation=navigation)
                self.fence.check(owner.ticket)
                current = owner.candidate
                if revision <= current.requested_revision:
                    raise CoordinatorError('stale_seek')
                if not current.range_start <= position < current.range_end:
                    raise ValueError('Seek outside configured extract')
                position = current.range_start + math.floor((position-current.range_start)*8)/8
                current.requested_revision = revision
                spec = FixedSource(current.spec.video, position,
                                   current.range_end-position, current.spec.delay)
                self.fence.touch(owner.ticket.client)
            # The one real probe runs outside BOTH lifecycle and core locks.
            session = base.Session(spec)
            replacement = NavigationCandidate(session, spec, current._track, owner.ticket,
                range_start=current.range_start, range_end=current.range_end,
                navigation_id=current.navigation_id, revision=revision)
            with self._lifecycle():
                if self._owner is not owner or owner.candidate is not current or current.requested_revision != revision:
                    raise CoordinatorError('stale_seek')
                self.fence.check(owner.ticket)
                if not current.stop():
                    raise CoordinatorError('cleanup_unconfirmed')
                # Retain the navigation owner; do NOT call fence.finish for seek.
                def publish(owner_id):
                    owner.candidate = replacement
                    owner.admitted = False
                    replacement.publish(owner_id)
                    owner.admitted = True
                self.fence.update_owner(owner.ticket, owner.owner_id, publish)
                return replacement.snapshot()
        finally:
            self._seek_slots.release()

    def reap_once(self):
        with self._lifecycle():
            owner = self._owner
            if owner is None:
                return False
            session = owner.candidate.session
            with session.lock:
                expired = time.monotonic() - session.heartbeat > self.lease
            control_expired = self.fence.expired_owner() == owner.owner_id
            if expired or control_expired:
                return self._stop_locked(owner.owner_id)
            return False

    def _reap(self):
        while not self._closing.wait(.1):
            try:
                self.reap_once()
            except (CoordinatorError, RuntimeError, OSError, subprocess.SubprocessError):
                print('Fenced expiry cleanup unconfirmed; owner retained.', file=sys.stderr)

    def close(self):
        self._closing.set()
        try:
            super().close()
        finally:
            if self._monitor is not None:
                self._monitor.join(timeout=1)


def _handle(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{48}', value) is None:
        raise ValueError('Invalid control_client_id')
    return value


def make_handler(app):
    if not isinstance(app, FencedApp):
        raise ValueError('FencedApp required; legacy bypass forbidden')
    Parent = base.make_handler(app)

    class Handler(Parent):
        def boundary(self):
            if not self.host_ok():
                self.reply(403, {'error': 'Invalid Host'})
                return False
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + self.headers['Host']:
                self.reply(403, {'error': 'Invalid Origin'})
                return False
            return True

        def failure(self, error, *, cancel=False):
            if isinstance(error, FenceError):
                code = error.code
                if code in ('unknown_client', 'client_expired'):
                    return self.reply(404, {'error': 'Control client gone', 'code': 'control_client_gone'})
                status = 429 if code == 'client_capacity' else 400 if code == 'invalid_revision' else 409
            elif isinstance(error, CoordinatorError):
                code = error.code
                status = 429 if code == 'preparation_capacity' else 503 if code in (
                    'cleanup_unconfirmed', 'lifecycle_busy', 'ownership_mismatch',
                    'admission_failed_cleanup_required') else 409
                if cancel:
                    return self.reply(503, {'error': 'Owner cleanup unconfirmed',
                        'code': 'cleanup_unconfirmed', 'fence_recorded': True, 'cleanup': 'unconfirmed'})
            elif isinstance(error, AdmissionFailed):
                code, status = 'admission_failed_cleanup_required', 503
            elif isinstance(error, KeyError):
                code, status = 'session_not_found', 404
            elif isinstance(error, TimeoutError):
                code, status = 'request_timeout', 408
            elif isinstance(error, (ValueError, TypeError, UnicodeError)):
                code, status = 'invalid_request', 400
            else:
                code, status = 'media_operation_failed', 503
            # Never return probe stderr, filesystem paths or capability tokens.
            return self.reply(status, {'error': code.replace('_', ' '), 'code': code})

        def do_GET(self):
            if not self.boundary():
                return
            parsed = urlsplit(self.path)
            if parsed.path == '/':
                return self.reply(200, app.html, 'text/html; charset=utf-8')
            if not self.authorized(self.headers.get('X-Wapflix-Test')):
                return self.reply(403, {'error': 'Forbidden'})
            if parsed.path != '/api/chunk':
                return self.reply(404, {'error': 'Not found'})
            try:
                query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=4)
                if set(query) != {'id', 'n'} or any(len(v) != 1 for v in query.values()):
                    raise ValueError('Invalid chunk query')
                index = int(query['n'][0])
                if not 0 <= index < 60:
                    raise ValueError('Invalid chunk index')
                data, old = app.chunk(query['id'][0], index)
                if old:
                    return self.reply(410, {'error': 'Chunk evicted or session stopped'})
                if data is None:
                    return self.reply(204, b'')
                return self.reply(200, data, packed=True)
            except (FenceError, CoordinatorError, KeyError, ValueError, TypeError, OSError) as error:
                return self.failure(error)

        def do_POST(self):
            if not self.boundary():
                return
            path = urlsplit(self.path).path
            try:
                lengths = self.headers.get_all('Content-Length', [])
                if self.headers.get('Transfer-Encoding') is not None or len(lengths) != 1:
                    raise ValueError('Invalid request framing')
                if not lengths[0].isascii() or not lengths[0].isdigit():
                    raise ValueError('Invalid request size')
                size = int(lengths[0])
                if not 0 < size <= 4096:
                    raise ValueError('Invalid request size')
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('Incomplete request')
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError('Expected an object')
                if not self.authorized(self.headers.get('X-Wapflix-Test') or body.get('token')):
                    return self.reply(403, {'error': 'Forbidden'})
                fields = {
                    '/api/control/open': set(),
                    '/api/control/cancel': {'control_client_id', 'cancel_through'},
                    '/api/start': {'control_client_id', 'start_revision'},
                    '/api/pulse': {'id', 'frame', 'paused'},
                    '/api/stop': {'id'},
                    '/api/navigation/stop': {'navigation_id'},
                    '/api/seek': {'navigation_id', 'revision', 'position'},
                }
                if path not in fields:
                    return self.reply(404, {'error': 'Not found'})
                if set(body) - (fields[path] | {'token'}):
                    raise ValueError('Unexpected fields')
                if path == '/api/control/open':
                    result = {'control_protocol': PROTOCOL,
                        'control_client_id': app.fence.open_client(), 'control_lease_seconds': 60}
                elif path == '/api/control/cancel':
                    client = _handle(body.get('control_client_id'))
                    revision = body.get('cancel_through')
                    if type(revision) is not int or not 0 <= revision <= MAX_REVISION:
                        raise ValueError('Invalid cancel_through')
                    # Only CoordinatorError after cancel() means fence was recorded.
                    try:
                        result = app.cancel(client, revision)
                    except CoordinatorError as error:
                        return self.failure(error, cancel=True)
                elif path == '/api/start':
                    if 'control_client_id' not in body or 'start_revision' not in body:
                        return self.reply(409, {'error': 'Fencing identity required', 'code': 'fencing_required'})
                    client = _handle(body['control_client_id'])
                    result = app.begin(client, body['start_revision'])
                elif path == '/api/pulse':
                    result = app.pulse(body.get('id'), body.get('frame', 0), body.get('paused', False))
                elif path == '/api/stop':
                    result = app.stop_session(body.get('id'))
                elif path == '/api/navigation/stop':
                    result = app.stop_navigation(body.get('navigation_id'))
                else:
                    result = app.seek(body.get('navigation_id'), body.get('revision'), body.get('position'))
                return self.reply(200, result)
            except (FenceError, CoordinatorError, AdmissionFailed, KeyError, ValueError,
                    TypeError, UnicodeError, TimeoutError, OSError, RuntimeError, subprocess.SubprocessError) as error:
                return self.failure(error)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-fenced', action='store_true', help='Explicit experimental opt-in')
    parser.add_argument('--video', type=Path, default=base.DEFAULT_VIDEO)
    parser.add_argument('--start', type=float, default=30)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--delay', type=float, default=0)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8103)
    parser.add_argument('--allow-host', action='append', default=[])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--srt', '--subtitles', dest='subtitles', type=Path)
    group.add_argument('--no-srt', action='store_true')
    args = parser.parse_args()
    if not args.enable_fenced:
        parser.error('R2B.4 is opt-in: pass --enable-fenced after running the test gate')
    app = FencedApp(FixedSource(args.video, args.start, args.seconds, args.delay),
        subtitles=args.subtitles, no_srt=args.no_srt, allowed_hosts=args.allow_host)
    server = None
    try:
        server = base.Server((args.bind, args.port), make_handler(app))
        print(f'Experimental fenced M4 API on {args.bind}:{server.server_port}', flush=True)
        print(f'X-Wapflix-Test capability: {app.token}', flush=True)
        print('Trusted LAN/Tailscale only. No connected browser/handset adapter yet.', flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        if server is not None:
            server.server_close()

if __name__ == '__main__':
    main()
