#!/usr/bin/env python3
"""Caption-enabled wrapper around the already working progressive test."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs,urlsplit
try:
    import progressive_test as base
    from wapflix_captions import load_captions
except ModuleNotFoundError as error:
    raise SystemExit('Required local test files missing. Keep tools/progressive_test.py and tools/srt.py installed. '+str(error))

CAPTION_JS = r"""
// Uses the same lexical playback clock as the working progressive renderer.
let captionCues=[],captionsOn=true;
const captionText=document.getElementById('captionText'),captionButton=document.getElementById('captions');
function drawCaptions(){
 const active=session&&manifest&&captionsOn&&phase!=='Finished'&&!phase.startsWith('Error');
 const lines=active?captionCues.filter(c=>clock>=c.start&&clock<c.end).flatMap(c=>c.text.split('\n')):[];
 captionText.textContent=[...new Set(lines)].join('\n');
}
captionButton.onclick=()=>{captionsOn=!captionsOn;captionButton.textContent='Captions: '+(captionsOn?'on':'off');captionButton.setAttribute('aria-pressed',String(captionsOn));drawCaptions();};
const videoDraw=draw;
draw=function(){videoDraw();drawCaptions();};
const videoPhase=setPhase;
setPhase=function(value){videoPhase(value);if(value==='Stopped'||value==='Starting'||value==='Finished'||value.startsWith('Error'))captionText.textContent='';};
const videoApi=api;
api=async function(path,body,signal){
 const result=await videoApi(path,body,signal);
 if(path==='/api/start'){
  try{
   const captions=await videoApi('/api/captions?id='+encodeURIComponent(result.id),undefined,signal);
   captionCues=captions.cues;captionsOn=true;captionButton.disabled=!captionCues.length;
   captionButton.textContent='Captions: '+(captionCues.length?'on':'none in section');captionButton.setAttribute('aria-pressed','true');
   document.getElementById('captionInfo').textContent=`${captions.selected_cue_count} cues in this section; ${captions.parse_error_count} parser warnings. Captions follow playback, not wall time.`;
  }catch(error){try{await videoApi('/api/stop',{id:result.id});}catch{}throw error;}
 }
 return result;
};
"""

def caption_html(source):
    anchors=['<style>','<canvas id="screen"','</canvas>','</script>']
    for anchor in anchors:
        if source.count(anchor)!=1:raise ValueError('Progressive test HTML differs; refusing an unsafe injection: '+anchor)
    for identifier in ('function draw(){','function setPhase(','async function api(','let session='):
        if identifier not in source:raise ValueError('Unsupported progressive test revision: '+identifier)
    source=source.replace('No audio, subtitles or seeking.','No audio or seeking. Captions enabled.')
    source=source.replace('<style>','<style>#captionText{min-height:4em;padding:12px;background:#25371e;color:#d7e3c5;white-space:pre-line;text-align:center;line-height:1.45}#captionInfo{font-size:13px}',1)
    source=source.replace('<canvas id="screen"','<button id="captions" disabled aria-pressed="true">Captions: pending</button><canvas id="screen"',1)
    source=source.replace('</canvas>','</canvas><div id="captionText" aria-label="Captions" aria-live="off"></div><p id="captionInfo">Waiting for a session.</p>',1)
    return source.replace('</script>',CAPTION_JS+'\n</script>',1)

class CaptionApp(base.App):
    def __init__(self,video,subtitles,start=30,seconds=60,lease=10):
        self.caption_data=load_captions(subtitles,start,seconds)
        super().__init__(video,start,seconds,lease)


def make_handler(app):
    Parent=base.make_handler(app)
    html=caption_html(base.HTML)
    class Handler(Parent):
        def do_GET(self):
            parsed=urlsplit(self.path)
            if parsed.path=='/':return self.reply(200,html.replace('__TOKEN__',app.token).encode(),'text/html; charset=utf-8')
            if parsed.path=='/api/captions':
                if self.headers.get('X-Wapflix-Test')!=app.token:return self.reply(403,{'error':'Forbidden'})
                try:
                    app.get(parse_qs(parsed.query).get('id',[''])[0])
                    return self.reply(200,app.caption_data)
                except KeyError:return self.reply(404,{'error':'Session not found'})
            return super().do_GET()
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,default=Path.home()/'.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4')
    parser.add_argument('--subtitles',type=Path)
    parser.add_argument('--start',type=float,default=30);parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--bind',default='127.0.0.1');parser.add_argument('--port',type=int,default=8100)
    args=parser.parse_args()
    subtitles=args.subtitles or args.video.parent/'source.youtube.en.srt'
    if not subtitles.is_file():raise ValueError('SRT missing. Run python3 tools/fetch_test_subtitles.py first.')
    # Validate compatibility before starting any monitor or worker threads.
    caption_html(base.HTML)
    app=CaptionApp(args.video,subtitles,args.start,args.seconds);server=None
    try:
        server=base.TestServer((args.bind,args.port),make_handler(app))
        data=app.caption_data
        print(f'Caption test listening on {args.bind}:{args.port}',flush=True)
        print(f'{data["selected_cue_count"]} cues overlap this extract; {data["parse_error_count"]} parser warnings.',flush=True)
        print('Trusted LAN/Tailscale only. Ctrl-C stops the server. No audio.',flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:
        app.close()
        if server:server.server_close()

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print(f'Cannot start caption test: {error}',file=sys.stderr);raise SystemExit(2)
