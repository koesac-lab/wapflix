#!/usr/bin/env python3
"""M4B: additive browser controls on the M4A restart-seek API."""
import argparse
from pathlib import Path
import subprocess
import sys

def seek_html(source):
    for anchor in ('<style>','<canvas id="screen"','</script>'):
        if source.count(anchor)!=1: raise ValueError('Unsupported caption viewer anchor: '+anchor)
    for anchor in ('id="captions"','function renderCaptions(){','captionSession','function bufferedEnd(){','painted=-1'):
        if anchor not in source: raise ValueError('Expected the M3 caption viewer: '+anchor)
    if 'id="seekControls"' in source: raise ValueError('Seek controls already installed')
    overlay=Path(__file__).with_name('lcd_seek_controls.js').read_text()
    source=source.replace('<style>','<style>#seekControls{padding:8px 0}#seekControls input{width:120px;font:inherit;padding:10px}#seekNotice{font-size:13px;min-height:1.5em}',1)
    controls='<div id="seekControls"><button id="seekBack" disabled>-10 sec</button><button id="seekForward" disabled>+10 sec</button><label>Source seconds <input id="seekPosition" type="number" step="0.125" disabled></label><button id="seekGo" disabled>Go</button><p id="seekNotice" role="status">Start playback to enable seeking.</p></div>'
    source=source.replace('<canvas id="screen"',controls+'<canvas id="screen"',1)
    source=source.replace('Milestone 3.','Milestone 4B.').replace('Captions enabled; no seeking.','Captions and restart-seeking enabled.')
    return source.replace('</script>',overlay+'\n</script>',1)

def make_app_class(backend):
    class SeekViewerApp(backend.SeekApp):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            try: self.html=seek_html(self.html)
            except BaseException: self.close();raise
    return SeekViewerApp

def main():
    try:
        from . import lcd_stream_seek_api as backend
    except ImportError:
        try: import lcd_stream_seek_api as backend
        except ImportError as error: raise SystemExit('Install the working M4A API first.') from error
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,default=backend.base.DEFAULT_VIDEO)
    p.add_argument('--start',type=float,default=30);p.add_argument('--seconds',type=float,default=60)
    p.add_argument('--bind',default='0.0.0.0');p.add_argument('--port',type=int,default=8101)
    p.add_argument('--allow-host',action='append',default=[]);p.add_argument('--delay',type=float,default=0)
    group=p.add_mutually_exclusive_group();group.add_argument('--srt','--subtitles',dest='subtitles',type=Path);group.add_argument('--no-srt',action='store_true')
    args=p.parse_args()
    if args.bind not in ('127.0.0.1','localhost') and 'M2_LAN_V1' not in Path(backend.base.__file__).read_text(): p.error('Apply the M2 LAN update first')
    app=make_app_class(backend)(args.video,args.start,args.seconds,args.delay,subtitles=args.subtitles,no_srt=args.no_srt)
    app.allowed_hosts={h.lower().rstrip('.') for h in args.allow_host};server=None
    try:
        server=backend.base.Server((args.bind,args.port),backend.make_handler(app))
        print(f'M4B seek viewer listening on {args.bind}:{server.server_port}. Open http://<mini-PC-IP>:{server.server_port}/',flush=True)
        print('Trusted LAN/Tailscale development only. Every seek restarts conversion. Ctrl-C stops the worker.',flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally:
        app.close()
        if server: server.server_close()

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,KeyError,IndexError,subprocess.SubprocessError) as error:
        print(f'Cannot start seek viewer: {error}',file=sys.stderr);raise SystemExit(2)
