#!/usr/bin/env python3
"""M2: configurable-bind, single-viewer LCD streaming test. No handset/Pages changes."""
import argparse
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
try:
    from .lcd_chunker import LCDStream, DEFAULT_VIDEO, resolve_ascii_dimensions
    from .chunk_cache import PersistentChunkCache
except ImportError:
    try:
        from lcd_chunker import LCDStream, DEFAULT_VIDEO, resolve_ascii_dimensions
        from chunk_cache import PersistentChunkCache
    except ImportError as error:
        raise SystemExit('Install milestone 1 (tools/lcd_chunker.py) first.') from error

class Session:
    def __init__(self, app):
        self.app=app;self.id=secrets.token_hex(16)
        self.stream=LCDStream(app.video,app.start,app.seconds,
            ascii_width=app.ascii_width,ascii_height=app.ascii_height)
        self.lock=threading.RLock();self.lifecycle=threading.Lock();self.stop_event=threading.Event()
        self.chunks={};self.generated=0;self.ready_frames=0;self.total_frames=None
        self.frame=0;self.paused=False;self.state='running';self.error=None
        self.heartbeat=time.monotonic();self.first=None
        self.thread=threading.Thread(target=self.work,daemon=True)
    def snapshot(self):
        with self.lock:
            return dict(id=self.id,state=self.state,error=self.error,cols=self.stream.cols,rows=self.stream.rows,
                fps=self.stream.fps,chunk_frames=self.stream.chunk_frames,source_start=self.stream.start,
                generated_chunks=self.generated,ready_frames=self.ready_frames,total_frames=self.total_frames,
                retained_chunks=len(self.chunks),first_chunk_seconds=self.first,
                worker_running=self.stream.process is not None and self.stream.process.poll() is None)
    def _protected_indices(self):
        with self.lock:
            floor=max(0,self.frame//self.stream.chunk_frames-1)
            return set(range(floor,self.generated+1))
    def pulse(self, frame, paused):
        if type(frame) is not int or frame<0 or type(paused) is not bool: raise ValueError('Invalid playback position')
        with self.lock:
            self.heartbeat=time.monotonic();self.frame=min(frame,self.ready_frames);self.paused=paused
            floor=self.frame//self.stream.chunk_frames-1
            for n in list(self.chunks):
                if n<floor: del self.chunks[n]
        return self.snapshot()
    def stop(self):
        self.stop_event.set()
        with self.lifecycle: self.stream.close()
        if self.thread.is_alive() and threading.current_thread()!=self.thread: self.thread.join(timeout=4)
        if self.thread.is_alive(): raise RuntimeError('Conversion worker did not stop')
        with self.lock: self.state='stopped';self.chunks.clear()
    def work(self):
        try:
            with self.lifecycle:
                if self.stop_event.is_set(): return
                self.stream.__enter__()
            for chunk in self.stream:
                while not self.stop_event.is_set():
                    with self.lock:
                        wait=self.paused or self.generated>=self.frame//self.stream.chunk_frames+8
                    if not wait: break
                    self.stop_event.wait(.03)
                if self.stop_event.wait(self.app.delay): return
                packed=gzip.compress(json.dumps(chunk,separators=(',',':')).encode(),compresslevel=6,mtime=0)
                with self.lock:
                    if self.stop_event.is_set(): return
                    self.chunks[chunk['index']]=packed
                    self.generated+=1;self.ready_frames+=len(chunk['frames'])
                    if self.first is None: self.first=self.stream.first_chunk_seconds
                if self.app.cache is not None:
                    self.app.cache.put(self.app.cache_identity,chunk['index'],packed,
                        protected_indices=self._protected_indices())
            with self.lock:
                if not self.stop_event.is_set(): self.total_frames=self.ready_frames;self.state='complete'
        except Exception as error:
            if not self.stop_event.is_set():
                print(f'LCD worker failed: {error}',file=sys.stderr,flush=True)
                with self.lock: self.state='error';self.error='Conversion failed; check the server terminal.'
        finally:
            with self.lifecycle: self.stream.close()

class App:
    def __init__(self,video,start=30,seconds=60,delay=0,lease=15,ascii_width=None,ascii_height=None,
            cache_dir=None,state_dir=None,cache_max_bytes=32*1024*1024):
        if not math.isfinite(delay) or not 0<=delay<=5: raise ValueError('Delay must be 0..5 seconds')
        if not math.isfinite(lease) or lease<=0: raise ValueError('Invalid session lease')
        self.ascii_width,self.ascii_height=resolve_ascii_dimensions(ascii_width,ascii_height)
        self.video=Path(video);self.start=start;self.seconds=seconds;self.delay=delay;self.lease=lease
        probe=LCDStream(self.video,start,seconds,ascii_width=self.ascii_width,ascii_height=self.ascii_height)
        self.cache_identity=PersistentChunkCache.identity(self.video,start,self.seconds,
            probe.cols,probe.rows,probe.fps)
        self.cache=None
        if cache_dir is not None and state_dir is not None and cache_max_bytes>0:
            try:
                self.cache=PersistentChunkCache(cache_dir,state_dir,cache_max_bytes)
            except OSError as error:
                print(f'Persistent cache disabled: {error}',file=sys.stderr,flush=True)
        self.html=Path(__file__).with_name('lcd_stream_viewer.html').read_text()
        self.token=secrets.token_hex(24);self.lock=threading.Lock();self.current=None
        self.closing=threading.Event();self.monitor=threading.Thread(target=self.reap,daemon=True);self.monitor.start()
    def begin(self):
        with self.lock:
            if self.current: self.current.stop()
            self.current=Session(self);self.current.thread.start()
            return self.current.snapshot()
    def get(self,ident):
        with self.lock: session=self.current
        if not session or session.id!=ident: raise KeyError('Session not found')
        return session
    def reap(self):
        while not self.closing.wait(.1):
            with self.lock: session=self.current
            if session:
                with session.lock: expired=time.monotonic()-session.heartbeat>self.lease
                if expired and not session.stop_event.is_set():
                    try: session.stop()
                    except RuntimeError as error: print(error,file=sys.stderr)
    def close(self):
        self.closing.set();self.monitor.join(timeout=1)
        with self.lock:
            if self.current: self.current.stop()

def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def setup(self): super().setup();self.connection.settimeout(5)
        def log_message(self,*args): pass
        def host_ok(self):
            try:
                parsed=urlsplit('http://'+self.headers.get('Host',''))
                port=parsed.port if parsed.port is not None else 80
                host=(parsed.hostname or '').lower().rstrip('.')
            except ValueError:
                return False
            allowed={'127.0.0.1','localhost',self.connection.getsockname()[0].lower()}
            allowed.update(getattr(app,'allowed_hosts',set()))
            return (host in allowed and port==self.server.server_port
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment)
        def reply(self,status,data,content_type='application/json',packed=False):
            if not isinstance(data,bytes): data=json.dumps(data).encode()
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',f"default-src 'none'; script-src 'nonce-{app.token}'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            if packed: self.send_header('Content-Encoding','gzip')
            self.end_headers()
            try: self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError): pass
        def authorized(self,token): return isinstance(token,str) and secrets.compare_digest(token,app.token)
        def do_GET(self):
            if not self.host_ok(): return self.reply(403,{'error':'Invalid Host'})
            parsed=urlsplit(self.path)
            if parsed.path=='/': return self.reply(200,app.html.replace('__TOKEN__',app.token).encode(),'text/html; charset=utf-8')
            if not self.authorized(self.headers.get('X-Wapflix-Test')): return self.reply(403,{'error':'Forbidden'})
            try:
                query=parse_qs(parsed.query);session=app.get(query.get('id',[''])[0])
                if parsed.path!='/api/chunk': return self.reply(404,{'error':'Not found'})
                n=int(query.get('n',['-1'])[0])
                if not 0<=n<60: raise ValueError('Invalid chunk index')
                with session.lock:
                    data=session.chunks.get(n)
                    old=n<session.generated and data is None
                    if data is None and not old and app.cache is not None:
                        data=app.cache.get(app.cache_identity,n)
                        if data is not None: session.chunks[n]=data
                if old: return self.reply(410,{'error':'Chunk evicted or session stopped'})
                if data is None: return self.reply(204,b'')
                return self.reply(200,data,packed=True)
            except KeyError: return self.reply(404,{'error':'Session not found'})
            except ValueError as error: return self.reply(400,{'error':str(error)})
        def do_POST(self):
            if not self.host_ok(): return self.reply(403,{'error':'Invalid Host'})
            origin=self.headers.get('Origin')
            if origin is not None and origin!='http://'+self.headers['Host']: return self.reply(403,{'error':'Invalid Origin'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096: raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict): raise ValueError('Expected an object')
                if not self.authorized(self.headers.get('X-Wapflix-Test') or body.get('token')):
                    return self.reply(403,{'error':'Forbidden'})
                path=urlsplit(self.path).path
                if path=='/api/start': return self.reply(200,app.begin())
                session=app.get(body.get('id',''))
                if path=='/api/pulse': return self.reply(200,session.pulse(body.get('frame',0),body.get('paused',False)))
                if path=='/api/stop': session.stop();return self.reply(200,{'stopped':True})
                return self.reply(404,{'error':'Not found'})
            except KeyError: return self.reply(404,{'error':'Session not found'})
            except (ValueError,TypeError) as error:
                return self.reply(400,{'error':str(error)})
            except TimeoutError: return self.reply(408,{'error':'Request timeout'})
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                print(error,file=sys.stderr);return self.reply(503,{'error':'Unable to start or stop conversion; check server terminal.'})
    return Handler

class Server(ThreadingHTTPServer): daemon_threads=True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,default=DEFAULT_VIDEO)
    p.add_argument('--bind',default='127.0.0.1',help='Use 0.0.0.0 for LAN/Tailscale IPv4 access')
    p.add_argument('--allow-host',action='append',default=[],help='Optional trusted hostname alias, without port')
    p.add_argument('--start',type=float,default=30);p.add_argument('--seconds',type=float,default=60)
    p.add_argument('--port',type=int,default=8101);p.add_argument('--delay',type=float,default=0,help='Artificial delay per chunk, 0..5 seconds')
    p.add_argument('--ascii-width',type=int,default=None,help='Optional ASCII canvas width; requires --ascii-height')
    p.add_argument('--ascii-height',type=int,default=None,help='Optional ASCII canvas height; requires --ascii-width')
    p.add_argument('--cache-dir',type=Path,default=Path('/cache'),help='Persistent chunk-cache directory')
    p.add_argument('--state-dir',type=Path,default=Path('/state'),help='Persistent cache-state directory')
    p.add_argument('--cache-max-bytes',type=int,default=32*1024*1024,help='Persistent cache ceiling in bytes')
    args=p.parse_args();app=App(args.video,args.start,args.seconds,args.delay,
        ascii_width=args.ascii_width,ascii_height=args.ascii_height,
        cache_dir=args.cache_dir,state_dir=args.state_dir,cache_max_bytes=args.cache_max_bytes);server=None
    app.allowed_hosts={h.lower().rstrip('.') for h in args.allow_host}
    try:
        server=Server((args.bind,args.port),make_handler(app))
        print(f'LCD viewer listening on {args.bind}:{server.server_port}; open http://<mini-PC-IP>:{server.server_port}/ from LAN/Tailscale.',flush=True)
        print('Private development server: trusted LAN/Tailscale only. No public port forwarding. Ctrl-C stops the worker.',flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally:
        app.close()
        if server: server.server_close()

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,KeyError,IndexError,subprocess.SubprocessError) as error:
        print(f'Cannot start LCD server: {error}',file=sys.stderr);raise SystemExit(2)
