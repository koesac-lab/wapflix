"""Static handset + real fenced API on one trusted-network origin.

5A.3B adds --enable-live for browser acceptance; static-only remains the default.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from . import handset_static_preview as static
from . import lcd_stream_fenced_api as fenced
from .lcd_m4_factory import FixedSource


def publish_live(preview, token):
    """Mutate only the served routes; never the catalogue/assets on disk."""
    raw, kind = preview.routes['/assets/catalogue.json']
    entries = json.loads(raw)
    if any(e.get('id') == 'local-stream-test' for e in entries):
        raise ValueError('Live entry ID collides with static catalogue')
    entries.append({'id': 'local-stream-test', 'title': 'Local stream test',
                    'description': 'One server-configured LCD stream. Select stops; Back returns.',
                    'playback_type': 'local-stream', 'source_identity': 'configured-test'})
    html, html_kind = preview.routes['/']
    if html.count(b'</body>') != 1:
        raise ValueError('Unsupported handset bootstrap')
    config = json.dumps({'token': token, 'apiBase': '/'}, separators=(',', ':'))
    config = config.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    scripts = (f'<script nonce="{preview.nonce}">window.wapflixLiveConfig={config};</script>'
               '<script src="./stream-source.js" defer></script>'
               '<script src="./handset-live.js" defer></script>')
    preview.routes['/'] = (html.replace(b'</body>', scripts.encode() + b'</body>'), html_kind)
    preview.routes['/assets/catalogue.json'] = (json.dumps(entries).encode(), kind)


class HandsetHost:
    def __init__(self, root, spec, *, allowed_hosts=(), subtitles=None,
                 no_srt=False, monitor=True, enable_live=False):
        self.preview = static.Preview(root, allowed_hosts)
        for name in ('stream-source.js', 'handset-live.js'):
            self.preview.routes['/' + name] = (
                static.confined(self.preview.root, name), 'text/javascript; charset=utf-8')
        self.live_enabled = enable_live
        # Validate bootstrap/catalogue before starting the API monitor.
        if enable_live:
            probe = type('Probe', (), {'routes': dict(self.preview.routes), 'nonce': self.preview.nonce})()
            publish_live(probe, 'validation-only')
        self.api = fenced.FencedApp(spec, subtitles=subtitles, no_srt=no_srt,
            allowed_hosts=self.preview.allowed_hosts, monitor=monitor)
        if enable_live:
            try:
                publish_live(self.preview, self.api.token)
            except Exception:
                self.api.close()
                raise

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
            return Static.dispatch(self)

        def do_HEAD(self):
            if urlsplit(self.path).path.startswith('/api/'):
                origin = self.headers.get('Origin')
                if (not self.host_ok() or
                    (origin is not None and origin != 'http://' + self.headers.get('Host', '')) or
                    not self.authorized(self.headers.get('X-Wapflix-Test'))):
                    self.send_response(403)
                else:
                    self.send_response(405)
                    self.send_header('Allow', 'GET, POST')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            return Static.dispatch(self, head=True)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-fenced', action='store_true')
    parser.add_argument('--enable-live', action='store_true', help='Enable repaired bridge and virtual live entry for browser acceptance')
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
        allowed_hosts=args.allow_host, subtitles=args.subtitles, no_srt=args.no_srt,
        enable_live=args.enable_live)
    server = None
    try:
        server = fenced.base.Server((args.bind, args.port), make_handler(host))
        print(f'Handset + real fenced API: http://<LAN-or-Tailscale-IP>:{server.server_port}/', flush=True)
        print('Live entry enabled for browser acceptance.' if args.enable_live else
              'Static only. Add --enable-live for the repaired bridge.', flush=True)
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
