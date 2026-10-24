"""5A.3A recovery: static handset + real fenced API on ONE origin.

No virtual live entry or bridge execution yet. Never imports the simulated
handset_live_preview dispatcher. Run from repo root with python3 -m tools.handset_fenced_preview.
"""
import argparse
from pathlib import Path
import sys
from urllib.parse import urlsplit
from . import handset_static_preview as static
from . import lcd_stream_fenced_api as fenced
from .lcd_m4_factory import FixedSource

class HandsetHost:
    def __init__(self, root, spec, *, allowed_hosts=(), subtitles=None,
                 no_srt=False, monitor=True):
        # Validate every published asset before starting the backend monitor.
        self.preview = static.Preview(root, allowed_hosts)
        for name in ('stream-source.js', 'handset-live.js'):
            self.preview.routes['/' + name] = (
                static.confined(self.preview.root, name), 'text/javascript; charset=utf-8')
        self.api = fenced.FencedApp(spec, subtitles=subtitles, no_srt=no_srt,
            allowed_hosts=self.preview.allowed_hosts, monitor=monitor)
        # No live entry, injected capability or bridge script tag in this pass.
        # Existing static bootstrap keeps its numeric invalidation token intact.

    @property
    def token(self):
        return self.api.token

    def csp(self):
        return ("default-src 'none'; script-src 'self' 'nonce-" + self.preview.nonce + "'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")

    def close(self):
        self.api.close()


def make_handler(host):
    if not isinstance(host, HandsetHost):
        raise ValueError('HandsetHost required')
    API = fenced.make_handler(host.api)
    Static = static.make_handler(host.preview)

    class Handler(API):
        # Both existing components emit CSP. Normalize to the one static
        # bootstrap nonce, including API errors/redirects, with one header only.
        def send_response(self, code, message=None):
            self._host_csp_sent = False
            return super().send_response(code, message)

        def send_header(self, keyword, value):
            if keyword.lower() == 'content-security-policy':
                value = host.csp()
                self._host_csp_sent = True
            return super().send_header(keyword, value)

        def end_headers(self):
            if not getattr(self, '_host_csp_sent', False):
                self.send_header('Content-Security-Policy', host.csp())
            return super().end_headers()

        def do_GET(self):
            if urlsplit(self.path).path.startswith('/api/'):
                return super().do_GET()
            # Only the established static allowlist; no directory serving.
            return Static.dispatch(self)

        def do_HEAD(self):
            if urlsplit(self.path).path.startswith('/api/'):
                origin = self.headers.get('Origin')
                if (not self.host_ok() or
                    (origin is not None and origin != 'http://' + self.headers.get('Host', '')) or
                    not self.authorized(self.headers.get('X-Wapflix-Test'))):
                    # HEAD failures have no body and never invoke API operations.
                    self.send_response(403)
                else:
                    self.send_response(405)
                    self.send_header('Allow', 'GET, POST')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            return Static.dispatch(self, head=True)

        # POST is inherited unchanged from the tested fenced API, including
        # Host/Origin, capability, body bounds, identity and cleanup truthfulness.
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-fenced', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--video', type=Path, default=fenced.base.DEFAULT_VIDEO)
    parser.add_argument('--start', type=float, default=30)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--delay', type=float, default=0)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8104)
    parser.add_argument('--allow-host', action='append', default=[])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--srt', '--subtitles', dest='subtitles', type=Path)
    group.add_argument('--no-srt', action='store_true')
    args = parser.parse_args()
    if not args.enable_fenced:
        parser.error('Pass --enable-fenced after the R2B/R2C gates pass')
    host = HandsetHost(args.root, FixedSource(args.video, args.start, args.seconds, args.delay),
        allowed_hosts=args.allow_host, subtitles=args.subtitles, no_srt=args.no_srt)
    server = None
    try:
        server = fenced.base.Server((args.bind, args.port), make_handler(host))
        print(f'5A.3A handset + real fenced API: http://<LAN-or-Tailscale-IP>:{server.server_port}/', flush=True)
        print('Live catalogue entry disabled pending bridge recovery. Static playback remains available.', flush=True)
        print(f'X-Wapflix-Test capability: {host.token}', flush=True)
        print('Trusted LAN/Tailscale only; no public forwarding or HTTPS proxy support.', flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            host.close()
        finally:
            if server is not None:
                server.server_close()

if __name__ == '__main__':
    main()
