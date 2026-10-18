#!/usr/bin/env python3
"""Single-viewer progressive ASCII experiment. Standard library + FFmpeg only."""
import argparse
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

HTML = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>WAPFLIX / progressive test</title>\n<style>*{box-sizing:border-box}body{max-width:740px;margin:auto;padding:24px;background:#171d22;color:#c8d2bd;font:15px system-ui}h1{font-size:20px}canvas{display:block;width:100%;height:auto;background:#a6bd70;border:10px solid #303d49;image-rendering:pixelated;border-radius:8px}button,input{font:inherit}button{padding:11px 18px;margin:12px 8px 12px 0}input{width:65px;padding:7px}p{line-height:1.5}pre{white-space:pre-wrap}#state{min-height:1.5em}</style>\n<h1>WAPFLIX / progressive test</h1><p>Two-second chunks, four-second startup buffer. No audio, subtitles or seeking. Start replaces the current test session.</p>\n<label>Artificial delay per chunk (seconds): <input id="delay" type="number" min="0" max="5" step="0.5" value="0"></label><br>\n<button id="start">Start</button><button id="pause" disabled>Pause</button><button id="stop" disabled>Stop</button>\n<canvas id="screen" width="240" height="136" aria-label="ASCII animation"></canvas>\n<p id="state" role="status" aria-live="polite">Ready</p><pre id="stats"></pre>\n<script>\n\'use strict\';\nconst token=\'__TOKEN__\', $=id=>document.getElementById(id), canvas=$(\'screen\'),ctx=canvas.getContext(\'2d\');\nlet session=null,controller=null,generation=0,frames=new Map(),clock=0,last=null,warmed=false,intent=false,manifest=null,painted=-1,phase=\'Ready\',nextPulse=0;\nconst sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));\nfunction setPhase(value){phase=value;$(\'state\').textContent=value;}\nasync function api(path,body,signal){\n const options={headers:{\'X-Wapflix-Test\':token},signal};\n if(body!==undefined){options.method=\'POST\';options.headers[\'Content-Type\']=\'application/json\';options.body=JSON.stringify(body);}\n const r=await fetch(path,options);if(!r.ok){let e=await r.text();try{e=JSON.parse(e).error;}catch{}throw Error(e||`HTTP ${r.status}`);}return r.status===204?null:await r.json();\n}\nfunction endBeacon(){if(session)navigator.sendBeacon(\'/api/stop\',JSON.stringify({id:session,token}));}\nwindow.addEventListener(\'pagehide\',endBeacon);\ndocument.addEventListener(\'visibilitychange\',()=>{if(document.hidden&&session){intent=false;last=null;$(\'pause\').textContent=\'Resume\';setPhase(\'Paused\');nextPulse=0;}});\nasync function stop(){\n const old=session;session=null;generation++;if(controller)controller.abort();intent=false;last=null;frames.clear();\n $(\'pause\').disabled=true;$(\'stop\').disabled=true;\n if(old){try{await api(\'/api/stop\',{id:old});}catch{}}\n setPhase(\'Stopped\');\n}\n$(\'stop\').onclick=stop;\n$(\'pause\').onclick=()=>{if(!session)return;intent=!intent;last=null;nextPulse=0;$(\'pause\').textContent=intent?\'Pause\':\'Resume\';setPhase(intent?\'Buffering\':\'Paused\');};\n$(\'start\').onclick=async()=>{\n $(\'start\').disabled=true;\n try{\n  await stop();const g=generation;controller=new AbortController();setPhase(\'Starting\');\n  const m=await api(\'/api/start\',{delay:Number($(\'delay\').value)},controller.signal);\n  if(g!==generation)return;\n  session=m.id;manifest=m;frames.clear();clock=0;last=null;warmed=false;intent=true;painted=-1;nextPulse=0;\n  canvas.width=m.cols*6;canvas.height=m.rows*8;$(\'pause\').disabled=false;$(\'stop\').disabled=false;$(\'pause\').textContent=\'Pause\';\n  setPhase(\'Buffering\');pump(g,controller.signal);\n }catch(e){if(e.name!==\'AbortError\')setPhase(\'Error: \'+e.message);}finally{$(\'start\').disabled=false;}\n};\nasync function pump(g,signal){\n try{\n  while(session&&g===generation){\n   if(performance.now()>=nextPulse){manifest=await api(\'/api/pulse\',{id:session,frame:Math.floor(clock*6),paused:!intent},signal);nextPulse=performance.now()+700;}\n   if(g!==generation)return;\n   if(manifest.state===\'error\'||manifest.state===\'cancelled\')throw Error(manifest.error||\'Session cancelled or expired\');\n   const base=Math.floor(clock/2);\n   for(const n of [...frames.keys()])if(n<base-1)frames.delete(n);\n   for(let n=base;n<base+4;n++){\n    if(g!==generation)return;\n    if(frames.has(n)||n>=manifest.generated_chunks)continue;\n    const data=await api(`/api/chunk?id=${encodeURIComponent(session)}&n=${n}`,undefined,signal);\n    if(g!==generation)return;if(data)frames.set(n,data);\n   }\n   if(!warmed&&(frames.has(0)&&frames.has(1)||(manifest.state===\'complete\'&&frames.has(0))))warmed=true;\n   await sleep(100);\n  }\n }catch(e){if(e.name!==\'AbortError\'&&g===generation){intent=false;setPhase(\'Error: \'+e.message);endBeacon();}}\n}\nfunction draw(){\n if(!manifest)return;\n const number=Math.floor(clock*6),n=Math.floor(number/12),chunk=frames.get(n);\n if(chunk&&number!==painted){\n  const frame=chunk.frames[number-chunk.start_frame];\n  if(frame!==undefined){painted=number;ctx.fillStyle=\'#a6bd70\';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle=\'#25371e\';ctx.font=\'8px monospace\';ctx.textBaseline=\'top\';frame.split(\'\\n\').forEach((line,y)=>{for(let x=0;x<line.length;x++)ctx.fillText(line[x],x*6,y*8,6);});}\n }\n let end=clock;\n for(let i=Math.floor(clock/2);frames.has(i);i++){const c=frames.get(i);end=(c.start_frame+c.frames.length)/6;}\n $(\'stats\').textContent=`Position: ${clock.toFixed(1)}s\\nBuffered ahead: ${Math.max(0,end-clock).toFixed(1)}s\\nGenerated chunks: ${manifest.generated_chunks}\\nDecoded chunks in browser: ${frames.size}\\nWorker: ${manifest.state}\\nFirst chunk: ${manifest.first_chunk_seconds===null?\'pending\':manifest.first_chunk_seconds.toFixed(2)+\'s\'}`;\n}\nfunction tick(now){\n if(session&&manifest){\n  const dt=last===null?0:Math.min(.25,(now-last)/1000);last=now;\n  if(intent&&warmed){\n   let end=clock;\n   for(let i=Math.floor(clock/2);frames.has(i);i++){const c=frames.get(i);end=(c.start_frame+c.frames.length)/6;}\n   clock=Math.min(clock+dt,end);\n   if(manifest.state===\'complete\'&&manifest.total_frames!==null&&clock>=manifest.total_frames/6){intent=false;$(\'pause\').disabled=true;setPhase(\'Finished\');nextPulse=0;}\n   else setPhase(clock>=end?\'Buffering\':\'Playing\');\n  }\n  draw();\n }\n requestAnimationFrame(tick);\n}\nrequestAnimationFrame(tick);\n</script></html>'
RAMP = ' .,:;irsXA253hMHGS#9B&@'
TABLE = bytes(ord(RAMP[n*(len(RAMP)-1)//255]) for n in range(256))
FPS, COLS, CHUNK_FRAMES = 6, 40, 12

def geometry(video):
    result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
      'stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation','-of','json',str(video)],
      capture_output=True,timeout=30)
    if result.returncode:raise ValueError('ffprobe failed; check source and FFmpeg installation')
    streams=json.loads(result.stdout).get('streams',[])
    if not streams:raise ValueError('No video stream found')
    s=streams[0];w,h=float(s['width']),float(s['height']);sar=s.get('sample_aspect_ratio','1:1')
    if sar not in (None,'N/A','0:1'):
        a,b=map(int,sar.split(':'))
        if a>0 and b>0:w*=a/b
    rotation=float(s.get('tags',{}).get('rotate',0))
    for side in s.get('side_data_list',[]):rotation=float(side.get('rotation',rotation))
    if not math.isfinite(rotation) or abs(rotation/90-round(rotation/90))>.001:raise ValueError('Only right-angle rotation supported')
    if round(rotation)%180:w,h=h,w
    rows=max(2,round(COLS*6*h/(8*w)))
    if rows>160:raise ValueError('Extreme aspect ratio unsupported')
    return rows

class Session:
    def __init__(self,app,delay):
        self.app=app;self.id=secrets.token_hex(16);self.delay=delay
        self.lock=threading.RLock();self.event=threading.Event();self.process=None
        self.chunks={};self.generated=0;self.ready_frames=0;self.total_frames=None
        self.state='running';self.error=None;self.frame=0;self.paused=False
        self.started=time.monotonic();self.heartbeat=self.started;self.first=None
        self.thread=threading.Thread(target=self.work,daemon=True)
    def snapshot(self):
        with self.lock:
            return {'id':self.id,'cols':COLS,'rows':self.app.rows,'fps':FPS,'chunk_seconds':2,
                    'generated_chunks':self.generated,'ready_frames':self.ready_frames,'total_frames':self.total_frames,
                    'state':self.state,'error':self.error,'first_chunk_seconds':self.first}
    def pulse(self,frame,paused):
        if type(frame) is not int or frame<0 or type(paused) is not bool:raise ValueError('Invalid playback position')
        with self.lock:
            self.heartbeat=time.monotonic();self.frame=min(frame,self.ready_frames);self.paused=paused
            floor=self.frame//CHUNK_FRAMES-1
            for n in list(self.chunks):
                if n<floor:del self.chunks[n]
        return self.snapshot()
    def stop(self):
        self.event.set()
        with self.lock:
            if self.state not in ('complete','error'):self.state='cancelled'
            proc=self.process
        if proc and proc.poll() is None:
            try:proc.terminate()
            except ProcessLookupError:pass
            try:proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=2)
        if self.thread.is_alive() and threading.current_thread()!=self.thread:self.thread.join(timeout=3)
        with self.lock:self.chunks.clear()
    def work(self):
        count=math.ceil(self.app.seconds*FPS);size=COLS*self.app.rows
        command=['ffmpeg','-nostdin','-v','error','-ss',str(self.app.start),'-i',str(self.app.video),
            '-t',str(self.app.seconds),'-map','0:v:0','-an','-sn','-dn','-vf',
            f'fps={FPS},scale={COLS}:{self.app.rows}:flags=area,setsar=1','-frames:v',str(count),
            '-threads:v','1','-f','rawvideo','-pix_fmt','gray','pipe:1']
        proc=None
        try:
            with tempfile.TemporaryFile() as errors:
                proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors)
                with self.lock:self.process=proc
                eof=False
                while not self.event.is_set() and not eof:
                    with self.lock:wait=self.paused or self.generated>=self.frame//CHUNK_FRAMES+15
                    if wait:
                        self.event.wait(.05);continue
                    frames=[]
                    for _ in range(CHUNK_FRAMES):
                        raw=bytearray()
                        while len(raw)<size and not self.event.is_set():
                            part=proc.stdout.read(size-len(raw))
                            if not part:break
                            raw.extend(part)
                        if self.event.is_set():break
                        if not raw:eof=True;break
                        if len(raw)!=size:raise ValueError('Incomplete FFmpeg frame')
                        text=bytes(raw).translate(TABLE).decode('ascii')
                        frames.append('\n'.join(text[n:n+COLS] for n in range(0,size,COLS)))
                    if self.event.is_set():break
                    if frames:
                        if self.event.wait(self.delay):break
                        with self.lock:
                            index=self.generated
                            chunk={'version':1,'start_frame':index*CHUNK_FRAMES,'fps':FPS,'cols':COLS,
                                   'rows':self.app.rows,'frames':frames}
                            self.chunks[index]=gzip.compress(json.dumps(chunk,separators=(',',':')).encode(),compresslevel=6,mtime=0)
                            self.generated+=1;self.ready_frames+=len(frames)
                            if self.first is None:self.first=time.monotonic()-self.started
                if self.event.is_set():return
                code=proc.wait(timeout=10)
                if code or not self.ready_frames:
                    errors.seek(0,2);errors.seek(max(0,errors.tell()-4096))
                    print('Conversion failed:',errors.read().decode(errors='replace'),file=sys.stderr)
                    raise ValueError('Decoder failed or source position is past the end')
                with self.lock:self.total_frames=self.ready_frames;self.state='complete'
        except Exception as error:
            if not self.event.is_set():
                print(f'Worker error: {error}',file=sys.stderr)
                with self.lock:self.state='error';self.error='Conversion failed; see the server terminal.'
        finally:
            if proc:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                if proc.stdout:proc.stdout.close()

class App:
    def __init__(self,video,start=30,seconds=60,lease=10):
        if not math.isfinite(start) or start<0 or not math.isfinite(seconds) or not 0<seconds<=120:raise ValueError('Invalid start/duration (maximum 120 seconds)')
        self.video=Path(video).resolve()
        if not self.video.is_file():raise ValueError('Source video is missing')
        for tool in ('ffmpeg','ffprobe'):
            if not shutil.which(tool):raise ValueError(f'{tool} missing on PATH')
        self.start=start;self.seconds=seconds;self.rows=geometry(self.video);self.lease=lease
        self.token=secrets.token_hex(24);self.current=None;self.lock=threading.Lock();self.closing=threading.Event()
        self.monitor=threading.Thread(target=self.reap,daemon=True);self.monitor.start()
    def begin(self,delay):
        if type(delay) not in (float,int) or not math.isfinite(delay) or not 0<=delay<=5:raise ValueError('Delay must be 0-5 seconds')
        with self.lock:
            if self.current:self.current.stop()
            self.current=Session(self,delay);self.current.thread.start()
            return self.current.snapshot()
    def get(self,ident):
        with self.lock:s=self.current
        if not s or s.id!=ident:raise KeyError('Session not found')
        return s
    def reap(self):
        while not self.closing.wait(.25):
            with self.lock:s=self.current
            if s:
                with s.lock:expired=time.monotonic()-s.heartbeat>self.lease;overdue=time.monotonic()-s.started>300 and s.state=='running'
                if (expired and not s.event.is_set()) or overdue:s.stop()
    def close(self):
        self.closing.set()
        with self.lock:
            if self.current:self.current.stop()
        self.monitor.join(timeout=1)

def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,data,content_type='application/json',packed=False):
            if not isinstance(data,bytes):data=json.dumps(data).encode()
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            if packed:self.send_header('Content-Encoding','gzip')
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            parsed=urlsplit(self.path)
            if parsed.path=='/':return self.reply(200,HTML.replace('__TOKEN__',app.token).encode(),'text/html; charset=utf-8')
            if self.headers.get('X-Wapflix-Test')!=app.token:return self.reply(403,{'error':'Forbidden'})
            try:
                query=parse_qs(parsed.query);s=app.get(query.get('id',[''])[0])
                if parsed.path!='/api/chunk':return self.reply(404,{'error':'Not found'})
                n=int(query.get('n',['-1'])[0])
                if n<0 or n>60:raise ValueError('Invalid chunk index')
                with s.lock:data=s.chunks.get(n);old=n<s.generated and data is None
                if old:return self.reply(410,{'error':'Chunk evicted or session stopped'})
                if data is None:return self.reply(204,b'')
                return self.reply(200,data,packed=True)
            except KeyError:return self.reply(404,{'error':'Session not found'})
            except ValueError as e:return self.reply(400,{'error':str(e)})
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('Expected an object')
                token=self.headers.get('X-Wapflix-Test') or body.get('token')
                if token!=app.token:return self.reply(403,{'error':'Forbidden'})
                path=urlsplit(self.path).path
                if path=='/api/start':return self.reply(200,app.begin(body.get('delay',0)))
                s=app.get(body.get('id',''))
                if path=='/api/pulse':return self.reply(200,s.pulse(body.get('frame',0),body.get('paused',False)))
                if path=='/api/stop':s.stop();return self.reply(200,{'stopped':True})
                return self.reply(404,{'error':'Not found'})
            except KeyError:return self.reply(404,{'error':'Session not found'})
            except (ValueError,TypeError) as e:return self.reply(400,{'error':str(e)})
    return Handler

class TestServer(ThreadingHTTPServer):
    daemon_threads=True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,default=Path.home()/'.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4')
    parser.add_argument('--start',type=float,default=30);parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--bind',default='127.0.0.1');parser.add_argument('--port',type=int,default=8100)
    args=parser.parse_args();app=App(args.video,args.start,args.seconds)
    server=None
    try:
        server=TestServer((args.bind,args.port),make_handler(app))
        print(f'Progressive test listening on {args.bind}:{args.port}',flush=True)
        print('Trusted LAN/Tailscale only. Ctrl-C stops the worker and server.',flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:
        app.close()
        if server:server.server_close()

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.TimeoutExpired) as e:
        print(f'Cannot start progressive test: {e}',file=sys.stderr);raise SystemExit(2)
