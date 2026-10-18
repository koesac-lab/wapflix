#!/usr/bin/env python3
"""Generate original demo assets, or convert your own video. Python standard library only."""
import argparse
import gzip
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

RAMP = ' .,:;irsXA253hMHGS#9B&@'
LEVELS = {'low': (48, 4), 'medium': (72, 6), 'high': (96, 8)}

def render(kind, t, cols, rows):
    lines = []
    for j in range(rows):
        y = (j + .5) / rows
        line = []
        for i in range(cols):
            x = (i + .5) / cols
            u, v = (x - .5) * 1.7778, y - .5
            light = .025
            if kind == 'drive':
                if y < .43:
                    if math.sin(i * 71 + j * 19) > .998: light = .65
                    if (x - .77)**2 + ((y - .19) * .5625)**2 < .025**2: light = .65
                else:
                    d = (y - .43) / .57
                    road = .035 + .38 * d
                    if abs(x - .5) < road:
                        light = .07
                        if abs(x - .5) < .008 + .007 * d and (1 / (d + .08) - t * 2) % 2 < .8: light = .9 * d
                        if abs(abs(x - .5) - road) < .008: light = .45
                    else:
                        light = .17 + .13 * math.sin(x * 80)
                        if (math.floor(x * 65) + math.floor((1 / (d + .08) - t) * 4)) % 11 == 0: light = .65 * d
                    for side in (-1, 1):
                        for k in range(5):
                            z = (k / 5 + t * .17) % 1
                            lx, ly = .5 + side * (.06 + .49 * z), .43 + .52 * z * z
                            light += .5 * math.exp(-((x - lx)**2 + (y - ly)**2) / (.00008 + .0002 * z))
            elif kind == 'orbit':
                radius = math.hypot(u, v)
                if radius < .285:
                    z = math.sqrt(.285**2 - radius**2)
                    shade = max(0, (u * .5 - v * .3 + z * .8) / .285)
                    clouds = math.sin(u * 32 + t * .7 + math.sin(v * 27)) + .5 * math.sin(u * 60 - v * 23 + t)
                    light = (.16 + .43 * (clouds > 0) + .18 * (clouds > .7)) * shade
                    light += .12 * math.exp(-((radius - .278) / .008)**2)
                elif math.sin(i * 127.1 + j * 311.7) > .993: light = .4 + .2 * math.sin(t + i)
                if abs(x - (.5 + .38 * math.cos(t * .37))) < .017 and abs(y - (.5 + .18 * math.sin(t * .37))) < .025: light = .95
            else:
                if .09 < x < .91 and .1 < y < .9:
                    light = .1 + .09 * math.sin(x * 28 + t * .25) * math.sin(y * 12)
                    if y > .53 + .13 * math.sin(math.floor(x * 20) * 7): light = .16 if (math.floor(x * 90) + math.floor(y * 48)) % 5 == 0 else .03
                    for k in range(15):
                        rx = (k * .137 + .1 * math.sin(k)) % 1
                        ry = (t * (.12 + (k % 4) * .03) + k * .239) % 1
                        if abs(x - rx) < .006 and abs(y - ry) < .04: light = .48 * (1 - abs(y - ry) / .04)
                    if abs(x - .5) < .012 or abs(y - .5) < .012: light = .015
                if abs(x - .08) < .012 or abs(x - .92) < .012 or abs(y - .09) < .015 or abs(y - .91) < .015: light = .4
            line.append(RAMP[max(0, min(len(RAMP) - 1, int(light * (len(RAMP) - 1))))])
        lines.append(''.join(line))
    return '\n'.join(lines)

def save(output, ident, title, description, variants, subtitles):
    paths = {}
    poster = ''
    for level, (cols, rows, fps, frames) in variants.items():
        if not frames: raise ValueError('No frames decoded; check start time and source duration')
        raw = json.dumps(dict(version=1, cols=cols, rows=rows, fps=fps, frames=frames, subtitles=subtitles), separators=(',', ':')).encode()
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        name = f'{ident}-{level}.json'
        (output / name).write_bytes(raw)
        (output / (name + '.gz')).write_bytes(packed)
        paths[level] = dict(path=f'assets/{name}.gz', fallback=f'assets/{name}', bytes=len(packed))
        if level == 'low': poster = frames[min(fps, len(frames) - 1)]
        print(f'{ident}/{level}: {len(packed)} bytes, {len(frames) / fps:.1f} seconds')
    catalogue = output / 'catalogue.json'
    entries = json.loads(catalogue.read_text()) if catalogue.exists() else []
    entries = [entry for entry in entries if entry['id'] != ident]
    entries.append(dict(id=ident, title=title, description=description, label='ORIGINAL / TRANSMISSION', poster=poster, variants=paths))
    catalogue.write_text(json.dumps(entries, indent=2))

def read_frame(stream, size):
    result = bytearray()
    while len(result) < size:
        part = stream.read(size - len(result))
        if not part: break
        result.extend(part)
    return bytes(result)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', nargs='?', type=Path)
    p.add_argument('--output', type=Path, default=Path('assets'))
    p.add_argument('--id')
    p.add_argument('--title')
    p.add_argument('--description', default='A new transmission.')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--seconds', type=float, default=20)
    p.add_argument('--subtitles', type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.video is None:
        demos = [('drive', 'The last road', 'A journey with no destination.', 'There used to be more of the world.'), ('orbit', 'A small distance', 'One world. A few thousand characters.', 'From here, everything looks like punctuation.'), ('rain', 'Weather, waiting', 'Nothing happens. The connection holds.', 'The rain arrived before your message.')]
        for ident, title, description, subtitle in demos:
            variants = {level: (cols, round(cols * 9 / 32), fps, [render(ident, n / fps, cols, round(cols * 9 / 32)) for n in range(12 * fps)]) for level, (cols, fps) in LEVELS.items()}
            save(args.output, ident, title, description, variants, [dict(start=3, end=8, text=subtitle)])
        return
    if not args.id or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.id): p.error('--id must contain lowercase letters, digits and single hyphens')
    if not args.title: p.error('--title is required for video conversion')
    if not args.video.is_file(): p.error('Input video does not exist')
    if args.start < 0 or args.seconds <= 0: p.error('Invalid start or duration')
    if not all(shutil.which(x) for x in ('ffmpeg', 'ffprobe')): p.error('Install FFmpeg and ffprobe first')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation', '-of', 'json', str(args.video)]))
    if not probe.get('streams'): p.error('No video stream found')
    stream = probe['streams'][0]
    w, h = stream['width'], stream['height']
    sar = stream.get('sample_aspect_ratio', '1:1')
    if sar not in ('N/A', '0:1'):
        a, b = map(int, sar.split(':'))
        if a and b: w *= a / b
    rotation = stream.get('tags', {}).get('rotate', 0)
    for data in stream.get('side_data_list', []): rotation = data.get('rotation', rotation)
    if abs(round(float(rotation))) % 180 == 90: w, h = h, w
    subtitles = json.loads(args.subtitles.read_text()) if args.subtitles else []
    if not isinstance(subtitles, list) or any(not isinstance(s, dict) or not {'start', 'end', 'text'} <= s.keys() for s in subtitles): p.error('Subtitles must be a JSON array of {start,end,text}')
    table = [RAMP[n * (len(RAMP) - 1) // 255] for n in range(256)]
    variants = {}
    for level, (cols, fps) in LEVELS.items():
        rows = max(2, round(cols * h / w * .5))
        if rows > 250: p.error('Extreme aspect ratio; crop the source first')
        cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(args.start), '-i', str(args.video), '-t', str(args.seconds), '-map', '0:v:0', '-an', '-sn', '-vf', f'fps={fps},scale={cols}:{rows}:flags=area,setsar=1', '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
        frames = []
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            while True:
                raw = read_frame(proc.stdout, cols * rows)
                if not raw: break
                if len(raw) != cols * rows: raise ValueError('Incomplete FFmpeg frame')
                chars = ''.join(table[pixel] for pixel in raw)
                frames.append('\n'.join(chars[n:n+cols] for n in range(0, len(chars), cols)))
            if proc.wait(): raise RuntimeError('FFmpeg conversion failed')
        variants[level] = (cols, rows, fps, frames)
    save(args.output, args.id, args.title, args.description, variants, subtitles)

if __name__ == '__main__':
    main()
