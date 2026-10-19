#!/usr/bin/env python3
"""Enable LAN/Tailscale IP access for the original M2 LCD test server."""
from pathlib import Path
import os
import sys

OLD_HOST="        def host_ok(self):\n            host=self.headers.get('Host','')\n            return host in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')"
NEW_HOST="        def host_ok(self):\n            # M2_LAN_V1: accept this connection's local IP, plus explicit aliases.\n            try:\n                parsed=urlsplit('http://'+self.headers.get('Host',''))\n                port=parsed.port if parsed.port is not None else 80\n                host=(parsed.hostname or '').lower().rstrip('.')\n            except ValueError:\n                return False\n            allowed={'127.0.0.1','localhost',self.connection.getsockname()[0].lower()}\n            allowed.update(getattr(app,'allowed_hosts',set()))\n            return (host in allowed and port==self.server.server_port\n                and parsed.username is None and parsed.password is None\n                and not parsed.path and not parsed.query and not parsed.fragment)"

EDITS=[
    (OLD_HOST,NEW_HOST),
    ("    p.add_argument('--video',type=Path,default=DEFAULT_VIDEO)",
     "    p.add_argument('--video',type=Path,default=DEFAULT_VIDEO)\n    p.add_argument('--bind',default='127.0.0.1',help='Use 0.0.0.0 for LAN/Tailscale IPv4 access')\n    p.add_argument('--allow-host',action='append',default=[],help='Optional trusted hostname alias, without port')"),
    ("args=p.parse_args();app=App(args.video,args.start,args.seconds,args.delay);server=None",
     "args=p.parse_args();app=App(args.video,args.start,args.seconds,args.delay);server=None\n    app.allowed_hosts={h.lower().rstrip('.') for h in args.allow_host}"),
    ("Server(('127.0.0.1',args.port),make_handler(app))","Server((args.bind,args.port),make_handler(app))"),
    ("print(f'LCD test viewer: http://127.0.0.1:{server.server_port}/',flush=True)",
     "print(f'LCD viewer listening on {args.bind}:{server.server_port}; open http://<mini-PC-IP>:{server.server_port}/ from LAN/Tailscale.',flush=True)"),
    ("Loopback only. No captions, seeking, Docker or handset integration. Ctrl-C stops the worker.",
     "Private development server: trusted LAN/Tailscale only. No public port forwarding. Ctrl-C stops the worker."),
    ("M2: loopback-only, single-viewer LCD streaming test.","M2: configurable-bind, single-viewer LCD streaming test.")
]

def transform(source):
    if '# M2_LAN_V1:' in source: return source
    for old,new in EDITS:
        if source.count(old)!=1: raise ValueError('M2 file differs from expected version; no files changed. Missing/nonunique anchor: '+old[:90])
    for old,new in EDITS: source=source.replace(old,new,1)
    compile(source,'lcd_stream_server.py','exec')
    return source

def main():
    root=Path(__file__).resolve().parents[1]
    target=root/'tools/lcd_stream_server.py'
    if not target.is_file(): raise ValueError('Install the milestone-2 archive first: tools/lcd_stream_server.py is missing')
    source=target.read_text();updated=transform(source)
    if source==updated:
        print('LAN support is already installed.');return
    backup=target.with_name(target.name+'.before-lan.bak')
    with backup.open('xb') as handle: handle.write(target.read_bytes())
    temporary=target.with_name(target.name+'.lan.tmp')
    temporary.write_text(updated);os.replace(temporary,target)
    print('LAN support installed; original server saved as '+backup.name)
    print('Run: python3 tools/lcd_stream_server.py --bind 0.0.0.0 --port 8101')

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,SyntaxError) as error:
        print('LAN patch failed: '+str(error),file=sys.stderr);raise SystemExit(2)
