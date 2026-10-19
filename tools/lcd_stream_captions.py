#!/usr/bin/env python3
"""M3: source-time SRT captions on the working LAN LCD viewer. Additive wrapper."""
import argparse
from pathlib import Path
import subprocess
import sys
try:
    from . import lcd_stream_server as base
    from . import srt
except ImportError:
    try:
        import lcd_stream_server as base
        import srt
    except ImportError as error:
        raise SystemExit('Install M1, M2 and the repository tools/srt.py first.') from error

def find_subtitles(video,explicit=None,disabled=False):
    if disabled: return None
    if explicit is not None: return Path(explicit).expanduser()
    video=Path(video).expanduser()
    return next((p for p in (video.with_suffix('.youtube.en.srt'),video.with_suffix('.en.srt'),video.with_suffix('.srt')) if p.is_file()),None)

def caption_html(source):
    for anchor in ('<style>','<canvas id="screen"','</canvas>','</script>'):
        if source.count(anchor)!=1: raise ValueError('Unsupported M2 viewer; refusing injection at '+anchor)
    for anchor in ('function draw(){','function phase(','async function api(','let session=','painted=-1'):
        if anchor not in source: raise ValueError('Unsupported M2 viewer: '+anchor)
    if 'id="captions"' in source: raise ValueError('Viewer already contains a caption layer')
    overlay=Path(__file__).with_name('lcd_caption_overlay.js').read_text()
    source=source.replace('<style>','<style>#captionText{min-height:4em;padding:12px;background:#25371e;color:#d7e3c5;white-space:pre-line;text-align:center;line-height:1.4;overflow-wrap:anywhere}#captionInfo{font-size:13px}',1)
    source=source.replace('<canvas id="screen"','<button id="captions" disabled aria-pressed="false">Captions: pending</button><canvas id="screen"',1)
    source=source.replace('</canvas>','</canvas><div id="captionText" aria-label="Captions" aria-live="off"></div><p id="captionInfo">Waiting for a session.</p>',1)
    source=source.replace('Milestone 2.','Milestone 3.').replace('Silent. No captions or seeking.','Silent. Captions enabled; no seeking.')
    return source.replace('</script>',overlay+'\n</script>',1)

class CaptionApp(base.App):
    def __init__(self,video,start=30,seconds=60,delay=0,lease=15,subtitles=None,no_srt=False):
        html=caption_html(Path(base.__file__).with_name('lcd_stream_viewer.html').read_text())
        self.subtitle_path=find_subtitles(video,subtitles,no_srt)
        self.parsed=srt.parse_srt(self.subtitle_path) if self.subtitle_path is not None else None
        super().__init__(video,start,seconds,delay,lease)
        self.html=html
    def caption_data(self,session):
        start=session.stream.start;end=start+session.stream.seconds
        cues=[] if self.parsed is None else [dict(start=max(start,c.start),end=min(end,c.end),text=c.text)
            for c in self.parsed.cues if c.end>start and c.start<end]
        return dict(timebase='source',cues=cues,selected_cue_count=len(cues),
            parse_error_count=len(self.parsed.errors) if self.parsed is not None else 0,
            track_found=self.parsed is not None)
    def begin(self):
        with self.lock:
            if self.current: self.current.stop()
            self.current=base.Session(self)
            result=self.current.snapshot()
            result['captions']=self.caption_data(self.current)
            self.current.thread.start()
            return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,default=base.DEFAULT_VIDEO)
    p.add_argument('--start',type=float,default=30);p.add_argument('--seconds',type=float,default=60)
    p.add_argument('--port',type=int,default=8101);p.add_argument('--bind',default='0.0.0.0')
    p.add_argument('--allow-host',action='append',default=[])
    p.add_argument('--delay',type=float,default=0)
    group=p.add_mutually_exclusive_group()
    group.add_argument('--srt','--subtitles',dest='subtitles',type=Path)
    group.add_argument('--no-srt',action='store_true')
    args=p.parse_args()
    if args.bind not in ('127.0.0.1','localhost') and 'M2_LAN_V1' not in Path(base.__file__).read_text():
        p.error('Apply the working M2 LAN update before using a LAN bind address')
    app=CaptionApp(args.video,args.start,args.seconds,args.delay,subtitles=args.subtitles,no_srt=args.no_srt)
    app.allowed_hosts={h.lower().rstrip('.') for h in args.allow_host}
    server=None
    try:
        server=base.Server((args.bind,args.port),base.make_handler(app))
        print(f'Captioned LCD viewer listening on {args.bind}:{server.server_port}. Open http://<mini-PC-IP>:{server.server_port}/',flush=True)
        print('SRT loaded.' if app.parsed is not None else 'No SRT found; video remains usable without captions.',flush=True)
        if app.parsed and app.parsed.errors: print(f'SRT warnings: {len(app.parsed.errors)} malformed cues skipped.',flush=True)
        print('Trusted LAN/Tailscale development use only. Ctrl-C stops server and worker.',flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally:
        app.close()
        if server: server.server_close()

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,KeyError,IndexError,subprocess.SubprocessError) as error:
        print(f'Cannot start captioned LCD server: {error}',file=sys.stderr);raise SystemExit(2)
