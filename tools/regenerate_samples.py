#!/usr/bin/env python3
"""Regenerate fine LCD samples: snippet, full, both, or procedural demos. No auto-push."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

VERSION = 2
DEFAULT_VIDEO = Path.home()/'.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4'

def probe(video):
    data = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','format=duration:stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation',
        '-of','json',str(video)], timeout=30))
    s = data['streams'][0]
    w, h = float(s['width']), float(s['height'])
    sar = s.get('sample_aspect_ratio','1:1')
    if sar not in (None,'N/A','0:1'):
        a,b = map(int,sar.split(':'))
        if a > 0 and b > 0: w *= a/b
    rotation = s.get('tags',{}).get('rotate',0)
    for side in s.get('side_data_list',[]): rotation = side.get('rotation',rotation)
    rotation = float(rotation)
    if not math.isfinite(rotation) or abs(rotation/90-round(rotation/90)) > .001:
        raise ValueError('Only right-angle rotation is supported')
    if round(rotation)%180: w,h = h,w
    duration = float(data['format']['duration'])
    if not math.isfinite(duration) or duration <= 0: raise ValueError('Invalid source duration')
    return h/w, duration

def profiles(width, ratio):
    result = {}
    for level, limit, fps in [('low',width//2,6),('medium',width,8),('high',width,12)]:
        cols = max(8, int(min(limit,200/ratio))//8*8)
        rows = max(2, round(cols*ratio))
        if rows > 200: raise ValueError('Source is too tall; crop it first')
        result[level] = (cols,rows,fps)
    return result

def pack_variant(raw_path, destination, cols, rows, fps, subtitles):
    size = cols*rows//8
    if cols%8 or raw_path.stat().st_size == 0 or raw_path.stat().st_size%size:
        raise ValueError('Incomplete monochrome FFmpeg output')
    count = raw_path.stat().st_size//size
    header = dict(version=1,layout='lcd-1bit',encoding='hex-msb',cols=cols,rows=rows,fps=fps,subtitles=subtitles)
    with raw_path.open('rb') as source, destination.open('wb') as plain, \
         (destination.parent/(destination.name+'.gz')).open('wb') as compressed, \
         gzip.GzipFile(filename='',fileobj=compressed,mode='wb',compresslevel=6,mtime=0) as packed:
        def write(data): plain.write(data); packed.write(data)
        write(json.dumps(header,separators=(',',':')).encode()[:-1]+b',"frames":[')
        for n in range(count):
            if n: write(b',')
            write(b'"'+source.read(size).hex().encode()+b'"')
        write(b']}')
    return count

def decode(video, start, seconds, settings, scratch, contrast, gamma, brightness):
    graph = f'[0:v:0]setpts=PTS-STARTPTS,trim=duration={seconds},format=gray,eq=contrast={contrast}:gamma={gamma}:brightness={brightness},negate,split=3[a][b][c];'
    filters=[]
    for label,(level,(cols,rows,fps)) in zip(('a','b','c'),settings.items()):
        filters.append(f'[{label}]fps={fps},scale={cols}:{rows}:flags=area:sws_dither=bayer,setsar=1,format=monob[{level}]')
    command=['ffmpeg','-nostdin','-v','error','-ss',str(start),'-i',str(video),
             '-filter_complex_threads','1','-filter_complex',graph+';'.join(filters)]
    for level in settings:
        command += ['-map',f'[{level}]','-an','-sn','-dn','-c:v','rawvideo','-threads:v','1',
                    '-pix_fmt','monob','-f','rawvideo',str(scratch/(level+'.raw'))]
    subprocess.run(command,check=True)

def signature(path):
    stat = path.stat()
    return [str(path.resolve()),stat.st_size,stat.st_mtime_ns]

def captions(video, explicit, disabled, start, seconds):
    if disabled: return [], None
    path = Path(explicit).expanduser() if explicit else next((p for p in (
        video.with_suffix('.youtube.en.srt'),video.with_suffix('.en.srt'),video.with_suffix('.srt')) if p.is_file()),None)
    if path is None:
        print('No adjacent SRT found; generating without captions.',flush=True)
        return [], None
    try:
        from . import srt
    except ImportError:
        import srt
    parsed = srt.parse_srt(path)
    if parsed.errors: raise ValueError('Fix malformed SRT cues before publishing: '+'; '.join(parsed.errors[:3]))
    selected = srt.cues_for_window(parsed,start,start+seconds)
    return [dict(start=c.start,end=c.end,text=c.text) for c in selected], signature(path)

def publish(assets, item):
    path=assets/'catalogue.json'
    entries=json.loads(path.read_text()) if path.exists() else []
    entries=[e for e in entries if e['id']!=item['id']]+[item]
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(entries,indent=2)+'\n')
    os.replace(temporary,path)

def cached(assets, ident, key):
    path=assets/'catalogue.json'
    for item in json.loads(path.read_text()) if path.exists() else []:
        if item['id']!=ident or item.get('sample_generation',{}).get('key')!=key: continue
        variants=[*item.get('variants',{}).values(),*item.get('lcd_variants',{}).values()]
        if variants and all((assets/Path(v[f]).name).is_file() for v in variants for f in ('path','fallback')):
            return True
    return False

def generate(args, mode, ratio, duration):
    video=args.video.expanduser().resolve()
    start=args.start if mode=='snippet' else 0
    if start>=duration: raise ValueError('Snippet starts after the source ends')
    seconds=min(args.seconds,duration-start) if mode=='snippet' else duration
    ident=args.id if mode=='snippet' else args.id+'-full'
    subtitles,srt_signature=captions(video,args.srt,args.no_srt,start,seconds)
    settings=profiles(args.width,ratio)
    recipe=dict(version=VERSION,mode=mode,start=start,seconds=seconds,profiles=settings,
        contrast=args.contrast,gamma=args.gamma,brightness=args.brightness,ascii=args.ascii,title=args.title)
    key=hashlib.sha256(json.dumps([recipe,signature(video),srt_signature],sort_keys=True).encode()).hexdigest()[:16]
    assets=args.output/'assets'; assets.mkdir(parents=True,exist_ok=True)
    if not args.force and cached(assets,ident,key):
        print(f'{ident}: unchanged; cached assets retained. Use --force to rebuild.',flush=True)
        return
    before=time.perf_counter()
    print(f'{ident}: converting {seconds:.2f}s from {start:.2f}s, three LCD qualities / one decode.',flush=True)
    with tempfile.TemporaryDirectory(prefix='.lcd-',dir=assets) as temporary:
        scratch=Path(temporary)
        decode(video,start,seconds,settings,scratch,args.contrast,args.gamma,args.brightness)
        variants={}
        for level,(cols,rows,fps) in settings.items():
            name=f'{ident}-{key}-lcd-{level}.json'
            count=pack_variant(scratch/(level+'.raw'),scratch/name,cols,rows,fps,subtitles)
            variants[level]=dict(path='assets/'+name+'.gz',fallback='assets/'+name,bytes=(scratch/(name+'.gz')).stat().st_size)
            print(f'  {level}: {cols}x{rows}, {fps} fps, {count} frames, {variants[level]["bytes"]/1024:.1f} KiB',flush=True)
        title=args.title+(' / full' if mode=='full' else ' / preview')
        item=dict(id=ident,title=title,description='Silent one-bit LCD video conversion.',
            label='LCD / TRANSMISSION',poster='',variants=variants,lcd_variants=variants,lcd_only=True,
            sample_generation=dict(key=key,recipe=recipe))
        if args.ascii:
            subtitle_file=scratch/'subtitles.json'; subtitle_file.write_text(json.dumps(subtitles))
            ascii_dir=scratch/'ascii'; ascii_dir.mkdir()
            subprocess.run([sys.executable,str(Path(__file__).with_name('build.py')),str(video),
                '--output',str(ascii_dir),'--id',ident,'--title',title,'--start',str(start),'--seconds',str(seconds),
                '--subtitles',str(subtitle_file)],check=True)
            original=json.loads((ascii_dir/'catalogue.json').read_text())[0]
            for level,v in original['variants'].items():
                name=f'{ident}-{key}-ascii-{level}.json'
                for field,suffix in [('fallback',''),('path','.gz')]:
                    shutil.move(ascii_dir/Path(v[field]).name,scratch/(name+suffix))
                    v[field]='assets/'+name+suffix
            item.update(variants=original['variants'],poster=original['poster'],lcd_only=False)
        for path in scratch.glob('*.json*'):
            if path.name!='subtitles.json': os.replace(path,assets/path.name)
        publish(assets,item)
    elapsed=time.perf_counter()-before
    print(f'{ident}: done in {elapsed:.2f}s ({seconds/elapsed:.1f}x source duration).',flush=True)

def demos(output, width):
    try:
        from . import lcd_video as lcd
    except ImportError:
        import lcd_video as lcd
    assets=output/'assets'; path=assets/'catalogue.json'
    entries=json.loads(path.read_text())
    for item in entries:
        ident=item['id']
        if ident not in ('drive','orbit','rain') and not item.get('fictional'): continue
        kind=ident if ident in ('drive','orbit','rain') else ('pods' if '-pods-' in ident else 'hotel')
        item['lcd_variants']={}
        for level,(cols,rows,fps) in profiles(width,9/16 if kind in ('drive','orbit','rain') else 5/6).items():
            original=json.loads((assets/Path(item['variants'][level]['fallback']).name).read_text())
            count=round(len(original['frames'])/original['fps']*fps)
            frames=[lcd.dither(lcd.scene(kind,n/fps,cols,rows,item.get('episode',1)),cols,rows) for n in range(count)]
            item['lcd_variants'][level]=lcd.write_variant(assets,ident,level,cols,rows,fps,frames,original.get('subtitles',[]))
    path.write_text(json.dumps(entries,indent=2)+'\n')
    print('Fine LCD procedural demos regenerated; custom footage retained.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['snippet','full','both','demos'])
    p.add_argument('--video',type=Path,default=DEFAULT_VIDEO)
    p.add_argument('--output',type=Path,default=Path('.'),help='Site root; writes assets/')
    p.add_argument('--id',default='test-video')
    p.add_argument('--title',default='Video test')
    p.add_argument('--start',type=float,default=30)
    p.add_argument('--seconds',type=float,default=15)
    p.add_argument('--width',type=int,default=240)
    p.add_argument('--contrast',type=float,default=1.08)
    p.add_argument('--gamma',type=float,default=1)
    p.add_argument('--brightness',type=float,default=0)
    group=p.add_mutually_exclusive_group(); group.add_argument('--srt'); group.add_argument('--no-srt',action='store_true')
    p.add_argument('--ascii',action='store_true',help='Also generate legacy ASCII renditions; slower, three extra decodes')
    p.add_argument('--force',action='store_true')
    args=p.parse_args()
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',args.id) or args.id in ('drive','orbit','rain'):
        p.error('Use a safe non-demo ID, such as test-video')
    if args.width<96 or args.width>240 or args.width%16: p.error('--width must be 96..240 and divisible by 16')
    for value,lo,hi in [(args.start,0,float('inf')),(args.seconds,.001,float('inf')),
                        (args.contrast,.1,3),(args.gamma,.1,3),(args.brightness,-1,1)]:
        if not math.isfinite(value) or not lo<=value<=hi: p.error('Invalid time or tone setting')
    if args.mode=='demos': demos(args.output,args.width); return
    if not args.video.expanduser().is_file(): p.error('Source video is missing; no download is performed')
    if not all(shutil.which(t) for t in ('ffmpeg','ffprobe')): p.error('Install FFmpeg and ffprobe')
    ratio,duration=probe(args.video.expanduser())
    for mode in (['snippet','full'] if args.mode=='both' else [args.mode]): generate(args,mode,ratio,duration)

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as error:
        print(f'Generation failed: {error}',file=sys.stderr); raise SystemExit(2)
