#!/usr/bin/env python3
"""M4A: restart-seek API only. M3 viewer remains unchanged; seek UI follows later."""
import argparse
import json
import math
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
try:
    from . import lcd_stream_captions as captions
except ImportError:
    try: import lcd_stream_captions as captions
    except ImportError as error: raise SystemExit('Install working M1-M3 files first.') from error
base=captions.base

class StaleNavigation(ValueError): pass

class SeekApp(captions.CaptionApp):
    def __init__(self,video,start=30,seconds=60,delay=0,lease=15,subtitles=None,no_srt=False):
        source=base.LCDStream(video,start,seconds)
        self.range_start=source.start;self.range_end=source.start+source.seconds
        self.navigation_id=None;self.revision=0
        super().__init__(video,start,seconds,delay,lease,subtitles,no_srt)
    def _replace(self,position):
        if self.current: self.current.stop()
        self.start=position;self.seconds=self.range_end-position
        self.current=base.Session(self)
        result=self.current.snapshot()
        result.update(captions=self.caption_data(self.current),navigation_id=self.navigation_id,
            revision=self.revision,range_start=self.range_start,range_end=self.range_end,
            seek_position=self.current.stream.start,seek_mode='restart')
        self.current.thread.start()
        return result
    def begin(self):
        with self.lock:
            self.navigation_id=secrets.token_hex(16);self.revision=0
            return self._replace(self.range_start)
    def seek(self,navigation_id,revision,position):
        if type(revision) is not int or not 1<=revision<=2**53-1: raise ValueError('revision must be a positive safe integer')
        if type(position) not in (int,float) or not math.isfinite(position): raise ValueError('position must be finite source seconds')
        with self.lock:
            if not self.navigation_id or navigation_id!=self.navigation_id: raise StaleNavigation('Navigation replaced or stopped')
            if self.current is None or self.current.stop_event.is_set(): raise StaleNavigation('Playback stopped or expired')
            if revision<=self.revision: raise StaleNavigation('Stale seek revision')
            if not self.range_start<=position<self.range_end: raise ValueError('position is outside the configured extract')
            # Frame boundaries are relative to the original configured extract.
            position=self.range_start+math.floor((position-self.range_start)*8)/8
            self.revision=revision
            return self._replace(position)
    def stop_navigation(self,navigation_id):
        if not isinstance(navigation_id,str) or not navigation_id: raise ValueError('navigation_id is required')
        with self.lock:
            if navigation_id!=self.navigation_id: return dict(stopped=True,superseded=True)
            self.navigation_id=None
            if self.current: self.current.stop()
            return dict(stopped=True,superseded=False)

def make_handler(app):
    Parent=base.make_handler(app)
    class Handler(Parent):
        def do_POST(self):
            path=urlsplit(self.path).path
            if path not in ('/api/seek','/api/navigation/stop'): return super().do_POST()
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
                if path=='/api/seek':
                    result=app.seek(body.get('navigation_id'),body.get('revision'),body.get('position'))
                else: result=app.stop_navigation(body.get('navigation_id'))
                return self.reply(200,result)
            except StaleNavigation as error: return self.reply(409,{'error':str(error)})
            except (ValueError,TypeError) as error: return self.reply(400,{'error':str(error)})
            except TimeoutError: return self.reply(408,{'error':'Request timeout'})
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                print(error,file=sys.stderr);return self.reply(503,{'error':'Restart-seek failed; check server terminal.'})
    return Handler

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,default=base.DEFAULT_VIDEO)
    p.add_argument('--start',type=float,default=30);p.add_argument('--seconds',type=float,default=60)
    p.add_argument('--bind',default='0.0.0.0');p.add_argument('--port',type=int,default=8101)
    p.add_argument('--allow-host',action='append',default=[]);p.add_argument('--delay',type=float,default=0)
    group=p.add_mutually_exclusive_group();group.add_argument('--srt','--subtitles',dest='subtitles',type=Path);group.add_argument('--no-srt',action='store_true')
    args=p.parse_args()
    if args.bind not in ('127.0.0.1','localhost') and 'M2_LAN_V1' not in Path(base.__file__).read_text(): p.error('Apply the M2 LAN update first')
    app=SeekApp(args.video,args.start,args.seconds,args.delay,subtitles=args.subtitles,no_srt=args.no_srt)
    app.allowed_hosts={h.lower().rstrip('.') for h in args.allow_host};server=None
    try:
        server=base.Server((args.bind,args.port),make_handler(app))
        print(f'M4A API listening on {args.bind}:{server.server_port}. Seek UI is NOT included yet.',flush=True)
        print('Close the browser viewer before running tools/lcd_seek_smoke.py against this server.',flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally:
        app.close()
        if server: server.server_close()

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,KeyError,IndexError,subprocess.SubprocessError) as error:
        print(f'Cannot start M4A API: {error}',file=sys.stderr);raise SystemExit(2)
