#!/usr/bin/env python3
"""5A.1 only: serve the existing handset and committed static assets on the LAN."""
import argparse
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import sys
from urllib.parse import urlsplit, quote

FRONTEND=('player.js','streaming.js','theme.js','themes.css','sharing.js','sharing.css')

def bootstrap(source,nonce):
    edits=[
        ('}}init();','}}window.wapflixReady=init();'),
        ("if(e.altKey||e.ctrlKey||e.metaKey)return;","if(e.target.closest?.('dialog'))return;if(e.altKey||e.ctrlKey||e.metaKey)return;"),
        ('<button class="key" data-key="3">3<small>DEF</small></button>','<button class="key" data-key="3" aria-label="Share WAPFLIX or this transmission">3<small>SHARE</small></button>'),
        ('0 QUALITY · * MENU · # BACKLIGHT','3 SHARE · 0 QUALITY · * MENU · # LIGHT'),
        ('<script>',f'<script nonce="{nonce}">'),
        ('</head>','<link rel="stylesheet" href="./themes.css"><link rel="stylesheet" href="./sharing.css"></head>'),
        ('</body>','<script src="./player.js" defer></script><script src="./streaming.js" defer></script><script src="./theme.js" defer></script><script src="./sharing.js" defer></script></body>')]
    for old,new in edits:
        if source.count(old)!=1: raise ValueError('Unsupported source index.html; refusing duplicate/unsafe bootstrap: '+old[:70])
    for old,new in edits: source=source.replace(old,new,1)
    return source.encode()

def confined(root,name):
    path=(root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise ValueError('Missing or unsafe static file: '+name)
    return path

def asset_path(value):
    if not isinstance(value,str): raise ValueError('Asset path must be a string')
    parsed=urlsplit(value);path=PurePosixPath(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not value.startswith('assets/') or '\\' in value or '%' in value or '..' in path.parts or str(path)!=value:
        raise ValueError('Unsafe catalogue asset path: '+value)
    if not value.endswith(('.json','.json.gz')): raise ValueError('Only converted JSON assets are served: '+value)
    return value

class Preview:
    def __init__(self,root,allowed_hosts=()):
        self.root=Path(root).expanduser().resolve();self.allowed_hosts={s.lower().rstrip('.') for s in allowed_hosts}
        self.nonce=secrets.token_hex(24)
        html=bootstrap(confined(self.root,'index.html').read_text(),self.nonce)
        self.routes={'/':(html,'text/html; charset=utf-8')};self.redirects={}
        for name in FRONTEND:
            self.routes['/'+name]=(confined(self.root,name),'text/css; charset=utf-8' if name.endswith('.css') else 'text/javascript; charset=utf-8')
        catalogue_path=confined(self.root,'assets/catalogue.json');raw=catalogue_path.read_bytes();entries=json.loads(raw)
        if not isinstance(entries,list) or not entries: raise ValueError('Static catalogue is empty or invalid; no video generation is performed')
        self.routes['/assets/catalogue.json']=(raw,'application/json')
        for entry in entries:
            ident=entry.get('id','')
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',ident): raise ValueError('Invalid catalogue ID')
            self.redirects['/share/'+ident+'/']='/?episode='+quote(ident)
            for field in ('variants','lcd_variants'):
                if field=='variants' and field not in entry: raise ValueError('Missing static variants: '+ident)
                if field not in entry: continue
                variants=entry[field]
                if not isinstance(variants,dict) or not {'low','medium','high'}<=variants.keys(): raise ValueError('Incomplete qualities: '+ident)
                for variant in variants.values():
                    for key in ('path','fallback'):
                        name=asset_path(variant[key]);path=confined(self.root,name)
                        self.routes['/'+name]=(path,'application/gzip' if name.endswith('.gz') else 'application/json')
        self.count=len(entries)

def make_handler(preview):
    class Handler(BaseHTTPRequestHandler):
        def setup(self): super().setup();self.connection.settimeout(5)
        def log_message(self,*args): pass
        def host_ok(self):
            try:
                parsed=urlsplit('http://'+self.headers.get('Host',''))
                port=parsed.port if parsed.port is not None else 80;host=(parsed.hostname or '').lower().rstrip('.')
            except ValueError: return False
            allowed={'127.0.0.1','localhost',self.connection.getsockname()[0].lower()}|preview.allowed_hosts
            return host in allowed and port==self.server.server_port and parsed.username is None and parsed.password is None and not parsed.path and not parsed.query and not parsed.fragment
        def dispatch(self,head=False):
            if not self.host_ok(): self.send_error(403,'Invalid Host');return
            path=urlsplit(self.path).path
            if path in preview.redirects:
                self.send_response(302);self.send_header('Location',preview.redirects[path]);self.send_header('Content-Length','0');self.end_headers();return
            item=preview.routes.get(path)
            if item is None: self.send_error(404,'Not a published static asset');return
            data,kind=item
            try:
                with (data.open('rb') if isinstance(data,Path) else io.BytesIO(data)) as handle:
                    size=data.stat().st_size if isinstance(data,Path) else len(data)
                    self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(size))
                    self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
                    self.send_header('Content-Security-Policy',f"default-src 'none'; script-src 'self' 'nonce-{preview.nonce}'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
                    # Static player explicitly decompresses .gz assets. Never add Content-Encoding.
                    self.end_headers()
                    if not head: shutil.copyfileobj(handle,self.wfile,64*1024)
            except (BrokenPipeError,ConnectionResetError): pass
        def do_GET(self): self.dispatch()
        def do_HEAD(self): self.dispatch(True)
    return Handler

class Server(ThreadingHTTPServer): daemon_threads=True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--bind',default='0.0.0.0');p.add_argument('--port',type=int,default=8102)
    p.add_argument('--allow-host',action='append',default=[])
    args=p.parse_args();preview=Preview(args.root,args.allow_host)
    server=Server((args.bind,args.port),make_handler(preview))
    print(f'5A.1 static handset: http://<mini-PC-IP>:{server.server_port}/ ({preview.count} existing titles)',flush=True)
    print('Static playback ONLY. No FFmpeg, API connection, source conversion, build or repository writes. Ctrl-C stops this preview.',flush=True)
    try: server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('Cannot start static handset preview: '+str(error),file=sys.stderr);raise SystemExit(2)
