#!/usr/bin/env python3
"""Export one small, watchable ASCII clip; does not touch the Pages site."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

RAMP = " .,:;irsXA253hMHGS#9B&@"
TABLE = bytes(ord(RAMP[value * (len(RAMP) - 1) // 255]) for value in range(256))
PLAYER_HTML = '<!doctype html>\n<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>WAPFLIX / first playback test</title>\n<style>\n*{box-sizing:border-box}body{margin:0;padding:24px;background:#171d22;color:#c8d2bd;font:15px system-ui;max-width:740px;margin:auto}h1{font-size:20px}canvas{display:block;width:100%;height:auto;background:#a6bd70;image-rendering:pixelated;border:10px solid #303d49;border-radius:8px}button,input{font:inherit}button{padding:12px 20px;margin:16px 12px 12px 0}input{width:100%}#status{min-height:2em}p{line-height:1.5;color:#b7c0b0}\n</style>\n<h1>WAPFLIX / first playback test</h1>\n<p>A preconverted local clip. Not progressive streaming. No audio or subtitles.</p>\n<canvas id="screen" width="240" height="136" aria-label="ASCII animation"></canvas>\n<button id="play" disabled>Play</button><button id="restart" disabled>Restart</button>\n<label for="seek">Position</label><input id="seek" type="range" min="0" max="1" step="0.01" value="0" disabled>\n<p id="status" role="status" aria-live="polite">Loading clip…</p>\n<script>\n\'use strict\';\nconst canvas=document.getElementById(\'screen\'),ctx=canvas.getContext(\'2d\');\nconst play=document.getElementById(\'play\'),restart=document.getElementById(\'restart\');\nconst seek=document.getElementById(\'seek\'),status=document.getElementById(\'status\');\nlet clip=null,time=0,playing=false,last=null,frame=-1;\nfunction draw(){\n  if(!clip)return;\n  const n=Math.min(clip.frames.length-1,Math.floor(time*clip.fps));\n  if(n!==frame){\n    frame=n;ctx.fillStyle=\'#a6bd70\';ctx.fillRect(0,0,canvas.width,canvas.height);\n    ctx.fillStyle=\'#25371e\';ctx.font=\'8px monospace\';ctx.textBaseline=\'top\';\n    clip.frames[n].split(\'\\n\').forEach((line,y)=>{\n      for(let x=0;x<line.length;x++)ctx.fillText(line[x],x*6,y*8,6);\n    });\n  }\n  seek.value=String(time);play.textContent=playing?\'Pause\':\'Play\';\n  status.textContent=`${time.toFixed(1)} / ${(clip.frames.length/clip.fps).toFixed(1)}s · ${clip.cols}×${clip.rows} · ${clip.fps} fps`;\n}\nplay.onclick=()=>{if(!clip)return;if(time>=clip.frames.length/clip.fps)time=0;playing=!playing;last=null;draw();};\nrestart.onclick=()=>{time=0;last=null;frame=-1;draw();};\nseek.oninput=()=>{time=Number(seek.value);last=null;draw();};\ndocument.addEventListener(\'visibilitychange\',()=>{if(document.hidden){playing=false;last=null;draw();}});\nfunction tick(now){\n  if(playing&&clip){\n    if(last!==null)time+=(now-last)/1000;\n    last=now;\n    if(time>=clip.frames.length/clip.fps){time=clip.frames.length/clip.fps;playing=false;last=null;}\n    draw();\n  }\n  requestAnimationFrame(tick);\n}\nrequestAnimationFrame(tick);\nfetch(\'./clip.json\').then(r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json();}).then(data=>{\n  if(!Number.isInteger(data.cols)||data.cols<2||data.cols>120||!Number.isInteger(data.rows)||data.rows<2||data.rows>160||!Number.isFinite(data.fps)||data.fps<1||data.fps>24||!Array.isArray(data.frames)||!data.frames.length||data.frames.length>2880||data.frames.some(f=>typeof f!==\'string\'||f.split(\'\\n\').length!==data.rows||f.split(\'\\n\').some(line=>line.length!==data.cols)))throw Error(\'Invalid clip\');\n  clip=data;canvas.width=clip.cols*6;canvas.height=clip.rows*8;\n  seek.max=String(clip.frames.length/clip.fps);play.disabled=false;restart.disabled=false;seek.disabled=false;draw();\n}).catch(error=>{status.textContent=\'Could not load clip: \'+error.message+\'. Serve this directory over HTTP; do not open index.html directly.\';});\n</script></html>\n'

def run(command, timeout):
    with tempfile.TemporaryFile() as errors:
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=errors, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"{command[0]} timed out") from error
        if result.returncode:
            errors.seek(0, 2)
            errors.seek(max(0, errors.tell()-4096))
            raise RuntimeError(errors.read().decode(errors='replace'))
        return result.stdout

def export(video, output, start=30, seconds=10):
    if not math.isfinite(start) or start<0 or not math.isfinite(seconds) or not 0<seconds<=30:
        raise ValueError("start must be finite and non-negative; seconds must be between 0 and 30")
    for tool in ('ffmpeg','ffprobe'):
        if not shutil.which(tool):
            raise ValueError(f"Missing {tool} on PATH")
    video=video.resolve()
    if not video.is_file():
        raise ValueError(f"Video not found: {video}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be a new or empty directory; nothing will be overwritten")
    probe=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
        'stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation','-of','json',str(video)],30))
    if not probe.get('streams'):
        raise ValueError('No video stream found')
    stream=probe['streams'][0]
    width,height=float(stream['width']),float(stream['height'])
    sar=stream.get('sample_aspect_ratio','1:1')
    if sar not in (None,'N/A','0:1'):
        a,b=map(int,sar.split(':'))
        if a>0 and b>0:width*=a/b
    rotation=float(stream.get('tags',{}).get('rotate',0))
    for side in stream.get('side_data_list',[]):rotation=float(side.get('rotation',rotation))
    if not math.isfinite(rotation) or abs(rotation/90-round(rotation/90))>.001:
        raise ValueError('Only right-angle rotation supported in this test')
    if round(rotation)%180:width,height=height,width
    cols,fps=40,6
    rows=max(2,round(cols*6*height/(8*width)))
    if rows>160:raise ValueError('Extreme aspect ratio not supported')
    before=time.perf_counter()
    raw=run(['ffmpeg','-nostdin','-v','error','-ss',str(start),'-i',str(video),'-t',str(seconds),
        '-map','0:v:0','-an','-sn','-dn','-vf',f'fps={fps},scale={cols}:{rows}:flags=area,setsar=1',
        '-frames:v',str(math.ceil(seconds*fps)),'-threads:v','1','-f','rawvideo','-pix_fmt','gray','pipe:1'],120)
    size=cols*rows
    if not raw or len(raw)%size:raise ValueError('No frames or incomplete frame; check source position')
    frames=[]
    for offset in range(0,len(raw),size):
        text=raw[offset:offset+size].translate(TABLE).decode('ascii')
        frames.append('\n'.join(text[n:n+cols] for n in range(0,size,cols)))
    clip={'version':1,'cols':cols,'rows':rows,'fps':fps,'frames':frames}
    output.mkdir(parents=True,exist_ok=True)
    with (output/'clip.json').open('x',encoding='utf-8') as handle:json.dump(clip,handle,separators=(',',':'))
    with (output/'index.html').open('x',encoding='utf-8') as handle:handle.write(PLAYER_HTML)
    print(json.dumps({'frames':len(frames),'duration':len(frames)/fps,'conversion_seconds':round(time.perf_counter()-before,3),'output':str(output.resolve())}))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,default=Path.home()/'.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--start',type=float,default=30)
    parser.add_argument('--seconds',type=float,default=10)
    args=parser.parse_args()
    export(args.video,args.output,args.start,args.seconds)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as error:
        print(f'Export failed: {error}',file=sys.stderr)
        raise SystemExit(2)
