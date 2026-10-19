#!/usr/bin/env python3
"""Build one-bit LCD variants alongside existing ASCII assets. Standard library + FFmpeg."""
import argparse
import gzip
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
LEVELS = {'low': (60, 4), 'medium': (80, 6), 'high': (120, 8)}

def dither(raw, width, height):
    """Hex, row-major, MSB first; 1 = dark ink. Final byte padding is zero."""
    if width < 1 or height < 1 or len(raw) != width * height:
        raise ValueError('Invalid greyscale frame geometry')
    packed = bytearray((width * height + 7) // 8)
    for y in range(height):
        thresholds = BAYER[y & 3]
        for x in range(width):
            n = y * width + x
            if raw[n] < (thresholds[x & 3] + .5) * 16:
                packed[n >> 3] |= 128 >> (n & 7)
    return packed.hex()

class Raster:
    def __init__(self, width, height, background=235):
        self.width, self.height = width, height
        self.data = bytearray([background]) * (width * height)
    def rect(self, x, y, width, height, shade):
        if width <= 0 or height <= 0: return
        x, y = round(x), round(y)
        width, height = max(1, round(width)), max(1, round(height))
        left, right = max(0, x), min(self.width, x + width)
        for row in range(max(0, y), min(self.height, y + height)):
            if right > left:
                start = row * self.width + left
                self.data[start:start + right-left] = bytes([shade]) * (right-left)
    def ellipse(self, x, y, rx, ry, shade):
        for row in range(max(0, math.ceil(y-ry)), min(self.height, math.floor(y+ry)+1)):
            extent = rx * math.sqrt(max(0, 1 - ((row-y)/ry)**2))
            self.rect(math.ceil(x-extent), row, math.floor(x+extent)-math.ceil(x-extent)+1, 1, shade)

def scene(kind, t, width, height, episode=1):
    """Original greyscale illustrations, never rasterised ASCII or real episode footage."""
    r = Raster(width, height)
    sx, sy = width / 120, height / 100
    def box(x, y, w, h, shade): r.rect(x*sx, y*sy, w*sx, h*sy, shade)
    def oval(x, y, rx, ry, shade): r.ellipse(x*sx, y*sy, rx*sx, ry*sy, shade)
    def person(x, y, ghost=False):
        oval(x, y+12, 9, 11, 65 if ghost else 110)
        box(x-8, y+23, 16, 25, 85 if ghost else 145)
        box(x-5, y+9, 2, 2, 0); box(x+3, y+9, 2, 2, 0)
        box(x-3, y+16, 6, 1+(int(t*4+episode)%2), 15)
        if not ghost:
            box(x-7, y+48, 5, 15, 40); box(x+2, y+48, 5, 15, 40)
    if kind == 'orbit':
        r = Raster(width, height, 10)
        oval(60, 50, 32, 38, 95)
        oval(66, 46, 25, 32, 180)
        for n in range(6):
            oval(57+13*math.sin(n*2+t*.3), 28+n*8, 8, 3, 115)
        oval(60+48*math.cos(t*.4), 50+43*math.sin(t*.4), 3, 3, 255)
    elif kind == 'drive':
        r = Raster(width, height, 25)
        oval(92, 17, 5, 6, 245)
        for y in range(height//2, height):
            depth = (y-height/2)/(height/2)
            half = int(width*(.03+.43*depth))
            r.rect(width//2-half, y, half*2, 1, 80)
            if (1/(depth+.08)-t*2)%2 < 1:
                r.rect(width//2-max(1,int(depth*2)), y, max(1,int(depth*4)), 1, 230)
    elif kind == 'rain':
        box(9, 8, 102, 84, 70); box(13, 12, 94, 76, 165)
        for n in range(24):
            x = 16+(n*29)%88; y = 12+(n*17+t*(16+n%4*3))%70
            box(x, y, 1, 7, 230)
        box(58, 12, 4, 76, 25); box(13, 48, 94, 4, 25)
    else:
        phase = int(t//8)%3
        box(0, 76, 120, 24, 180)
        if phase == 0:
            box(5, 5, 110, 70, 90); box(9, 9, 102, 62, 210)
            for x in (15, 85):
                box(x, 15, 20, 20, 20); box(x+2, 17, 16, 16, 150)
            if kind == 'pods':
                box(58, 9, 3, 65, 30)
                person(32, 25); person(88, 25)
            else:
                box(50, 25, 20, 50, 60)
                person(80+4*math.sin(t*2), 28, True)
        elif phase == 1:
            box(0, 0, 120, 100, 185)
            oval(60, 37, 29, 33, 115)
            box(25, 68, 70, 32, 70)
            for x in (49, 71):
                box(x-4, 31, 8, 3 if int(t*3)%13 == 0 else 6, 15)
            box(51, 53, 18, 2+int(t*4)%3, 30)
        else:
            box(4, 3, 112, 70, 205)
            for x in (10, 95): box(x, 12, 15, 46, 80)
            person(38+4*math.sin(t), 18, kind != 'pods')
            person(82-4*math.sin(t), 18, kind != 'pods')
    return r.data

def write_variant(assets, ident, level, width, height, fps, frames, subtitles):
    if not frames: raise ValueError('No decoded frames')
    data = dict(version=1, layout='lcd-1bit', encoding='hex-msb', cols=width,
                rows=height, fps=fps, frames=frames, subtitles=subtitles)
    raw = json.dumps(data, separators=(',', ':')).encode()
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    name = f'{ident}-lcd1-{level}.json'
    (assets/name).write_bytes(raw); (assets/(name+'.gz')).write_bytes(packed)
    return dict(path='assets/'+name+'.gz', fallback='assets/'+name, bytes=len(packed))

def geometry(video):
    result = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation',
        '-of', 'json', str(video)], timeout=30)
    streams = json.loads(result).get('streams', [])
    if not streams: raise ValueError('No video stream')
    s = streams[0]; width, height = float(s['width']), float(s['height'])
    sar = s.get('sample_aspect_ratio', '1:1')
    if sar not in (None, 'N/A', '0:1'):
        a, b = map(int, sar.split(':'))
        if a > 0 and b > 0: width *= a/b
    rotation = s.get('tags', {}).get('rotate', 0)
    for side in s.get('side_data_list', []): rotation = side.get('rotation', rotation)
    rotation = float(rotation)
    if not math.isfinite(rotation) or abs(rotation/90-round(rotation/90)) > .001:
        raise ValueError('Only right-angle video rotation is supported')
    if round(rotation)%180: width, height = height, width
    return height/width

def read_frame(stream, size):
    result = bytearray()
    while len(result) < size:
        part = stream.read(size-len(result))
        if not part: break
        result.extend(part)
    if result and len(result) != size: raise ValueError('Incomplete decoded frame')
    return result

def video_frames(video, start, seconds, width, height, fps):
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(start), '-i', str(video),
        '-t', str(seconds), '-map', '0:v:0', '-an', '-sn', '-dn', '-vf',
        f'fps={fps},scale={width}:{height}:flags=area,setsar=1',
        '-threads:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
    frames = []
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        try:
            while True:
                raw = read_frame(proc.stdout, width*height)
                if not raw: break
                frames.append(dither(raw, width, height))
            if proc.wait(): raise RuntimeError('FFmpeg conversion failed')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=2)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    return frames

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('_site'), help='Site root containing assets/')
    p.add_argument('--video', type=Path)
    p.add_argument('--id', help='Existing catalogue ID; create ASCII version with build.py first')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--seconds', type=float, default=20)
    args = p.parse_args()
    if not math.isfinite(args.start) or args.start < 0 or not math.isfinite(args.seconds) or args.seconds <= 0:
        p.error('Invalid start or duration')
    if args.video and (not args.video.is_file() or not args.id): p.error('--video requires a file and --id')
    if args.video and not all(shutil.which(t) for t in ('ffmpeg', 'ffprobe')): p.error('Install FFmpeg and ffprobe')
    assets = args.output/'assets'; path = assets/'catalogue.json'
    catalogue = json.loads(path.read_text())
    if args.video and not any(e['id'] == args.id for e in catalogue): p.error('--id is not in this catalogue')
    ratio = geometry(args.video) if args.video else None
    for item in catalogue:
        ident = item['id']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', ident): raise ValueError('Unsafe catalogue ID')
        if args.video:
            if ident != args.id: continue
        elif ident not in ('drive', 'orbit', 'rain') and not item.get('fictional'):
            continue
        variants = {}
        for level, (width, fps) in LEVELS.items():
            original = json.loads((assets/Path(item['variants'][level]['fallback']).name).read_text())
            height = max(2, round(width*ratio) if args.video else (round(width*9/16) if ident in ('drive','orbit','rain') else width*5//6))
            if height > 250: raise ValueError('Extreme aspect ratio; crop the source')
            if args.video:
                frames = video_frames(args.video, args.start, args.seconds, width, height, fps)
            else:
                duration = len(original['frames'])/original['fps']
                kind = ident if ident in ('drive','orbit','rain') else ('pods' if '-pods-' in ident else 'hotel')
                frames = [dither(scene(kind, n/fps, width, height, item.get('episode', 1)), width, height)
                          for n in range(round(duration*fps))]
            variants[level] = write_variant(assets, ident, level, width, height, fps, frames, original.get('subtitles', []))
        item['lcd_variants'] = variants
    path.write_text(json.dumps(catalogue, indent=2))
    print('LCD variants written; original ASCII variants retained.')

if __name__ == '__main__':
    main()
