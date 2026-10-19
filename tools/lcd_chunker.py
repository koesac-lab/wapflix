#!/usr/bin/env python3
"""Milestone 1: progressively produce LCD chunks. No HTTP server or player changes."""
import argparse
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

DEFAULT_VIDEO=Path.home()/'.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4'

def read_frame(source,size):
    raw=bytearray()
    while len(raw)<size:
        part=source.read(size-len(raw))
        if not part: break
        raw.extend(part)
    if raw and len(raw)!=size: raise ValueError('Incomplete monochrome frame')
    return bytes(raw)

def inspect_video(video):
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','format=duration:stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation',
        '-of','json',str(video)],timeout=30))
    if not data.get('streams'): raise ValueError('No video stream')
    s=data['streams'][0];w,h=float(s['width']),float(s['height'])
    sar=s.get('sample_aspect_ratio','1:1')
    if sar not in (None,'N/A','0:1'):
        a,b=map(int,sar.split(':'))
        if a>0 and b>0: w*=a/b
    rotation=s.get('tags',{}).get('rotate',0)
    for side in s.get('side_data_list',[]): rotation=side.get('rotation',rotation)
    rotation=float(rotation)
    if not math.isfinite(rotation) or abs(rotation/90-round(rotation/90))>.001:
        raise ValueError('Only right-angle rotation is supported')
    if round(rotation)%180: w,h=h,w
    duration=float(data['format']['duration'])
    if not all(math.isfinite(v) and v>0 for v in (w,h,duration)): raise ValueError('Invalid source geometry or duration')
    ratio=h/w
    cols=max(8,int(min(240,200/ratio))//8*8); rows=max(2,round(cols*ratio))
    if rows>200: raise ValueError('Extreme aspect ratio; crop the source')
    return cols,rows,duration

class LCDStream:
    def __init__(self,video,start=30,seconds=60):
        if not math.isfinite(start) or start<0 or not math.isfinite(seconds) or not 0<seconds<=120:
            raise ValueError('Use start >= 0 and 0 < seconds <= 120 for this milestone')
        self.video=Path(video).expanduser().resolve()
        if not self.video.is_file(): raise ValueError('Source video is missing')
        if not all(shutil.which(t) for t in ('ffmpeg','ffprobe')): raise ValueError('Install FFmpeg and ffprobe')
        self.cols,self.rows,duration=inspect_video(self.video)
        if start>=duration: raise ValueError('Start is after the video ends')
        self.start=start;self.seconds=min(seconds,duration-start)
        self.fps=8;self.chunk_frames=16;self.process=None;self.errors=None
        self.started=None;self.first_chunk_seconds=None;self.frames=0;self.used=False;self.closed=False
    def __enter__(self):
        if self.process is not None or self.closed: raise RuntimeError('Create a new stream for each conversion')
        self.started=time.perf_counter();self.errors=tempfile.TemporaryFile()
        graph=(f'setpts=PTS-STARTPTS,trim=duration={self.seconds},format=gray,'
            f'eq=contrast=1.08:gamma=1:brightness=0,negate,fps={self.fps},'
            f'scale={self.cols}:{self.rows}:flags=area:sws_dither=bayer,setsar=1,format=monob')
        command=['ffmpeg','-nostdin','-v','error','-ss',str(self.start),'-i',str(self.video),
            '-map','0:v:0','-an','-sn','-dn','-vf',graph,'-c:v','rawvideo','-threads:v','1',
            '-pix_fmt','monob','-f','rawvideo','pipe:1']
        try: self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=self.errors)
        except BaseException: self.close();raise
        return self
    def __exit__(self,*args): self.close()
    def close(self):
        if self.closed: return
        self.closed=True
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=2)
                except subprocess.TimeoutExpired: self.process.kill();self.process.wait(timeout=2)
            if self.process.stdout: self.process.stdout.close()
        if self.errors: self.errors.close()
    def __iter__(self):
        if self.process is None or self.closed or self.used: raise RuntimeError('Use one iterator inside with LCDStream(...)')
        self.used=True
        index=0;eof=False
        try:
            while not eof:
                frames=[]
                for _ in range(self.chunk_frames):
                    raw=read_frame(self.process.stdout,self.cols*self.rows//8)
                    if not raw: eof=True;break
                    frames.append(raw.hex())
                if not frames: break
                start_frame=self.frames;self.frames+=len(frames)
                if self.first_chunk_seconds is None: self.first_chunk_seconds=time.perf_counter()-self.started
                yield dict(version=1,layout='lcd-1bit',encoding='hex-msb',index=index,
                    cols=self.cols,rows=self.rows,fps=self.fps,start_frame=start_frame,
                    source_start=self.start,frames=frames)
                index+=1
            code=self.process.wait(timeout=10)
            if code or not self.frames:
                self.errors.seek(0,2);self.errors.seek(max(0,self.errors.tell()-4096))
                detail=self.errors.read().decode(errors='replace')
                raise RuntimeError('FFmpeg failed or produced no frames. '+detail)
        finally: self.close()

def atomic_write(path,raw):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes(raw);os.replace(temporary,path)

def export(video,output,start=30,seconds=60):
    stream=LCDStream(video,start,seconds)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    manifest=dict(version=1,state='converting',layout='lcd-1bit',encoding='hex-msb',
        cols=stream.cols,rows=stream.rows,fps=stream.fps,source_start=stream.start,
        requested_seconds=stream.seconds,chunk_frames=stream.chunk_frames,
        generated_frames=0,first_chunk_seconds=None,first_chunk_worker_running=None,chunks=[])
    def save(): atomic_write(output/'manifest.json',json.dumps(manifest,indent=2).encode())
    save()
    try:
        with stream:
            for chunk in stream:
                name=f"chunk-{chunk['index']:06}.json"
                raw=json.dumps(chunk,separators=(',',':')).encode()
                packed=gzip.compress(raw,compresslevel=6,mtime=0)
                atomic_write(output/name,raw);atomic_write(output/(name+'.gz'),packed)
                if not manifest['chunks']:
                    manifest['first_chunk_worker_running']=stream.process.poll() is None
                manifest['chunks'].append(dict(index=chunk['index'],path=name+'.gz',fallback=name,
                    start_frame=chunk['start_frame'],frames=len(chunk['frames']),bytes=len(packed)))
                manifest.update(generated_frames=stream.frames,first_chunk_seconds=stream.first_chunk_seconds)
                save()
                print(json.dumps(dict(event='chunk',index=chunk['index'],frames=len(chunk['frames']),
                    buffered_source_seconds=stream.frames/stream.fps,bytes=len(packed))),flush=True)
        manifest['state']='complete'
    except BaseException as error:
        manifest['state']='cancelled' if isinstance(error,KeyboardInterrupt) else 'error'
        manifest['error']=str(error) or type(error).__name__
        raise
    finally:
        stream.close()
        if stream.started is not None: manifest['conversion_seconds']=time.perf_counter()-stream.started
        save()
    print(json.dumps(dict(event='complete',frames=stream.frames,chunks=len(manifest['chunks']),
        first_chunk_worker_running=manifest['first_chunk_worker_running'],
        first_chunk_seconds=stream.first_chunk_seconds,conversion_seconds=manifest['conversion_seconds'],
        output=str(output.resolve()))),flush=True)
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,default=DEFAULT_VIDEO)
    p.add_argument('--output',type=Path,required=True,help='New directory; existing directories are never overwritten')
    p.add_argument('--start',type=float,default=30)
    p.add_argument('--seconds',type=float,default=60)
    args=p.parse_args();export(args.video,args.output,args.start,args.seconds)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: raise SystemExit(130)
    except (OSError,ValueError,KeyError,IndexError,RuntimeError,subprocess.SubprocessError) as error:
        print(f'Chunk conversion failed: {error}',file=sys.stderr);raise SystemExit(2)
