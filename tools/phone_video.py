#!/usr/bin/env python3
"""Recompose demo scenes for the handset and install the clean playback renderer."""
import argparse
import gzip
import json
import math
import shutil
from pathlib import Path

COLS, ROWS = 40, 25
FPS = {'low': 4, 'medium': 6, 'high': 8}

def scene(theme, season, episode, t):
    grid = [[' '] * COLS for _ in range(ROWS)]
    phase, moment = min(2, int(t // 8)), t % 8
    def put(x, y, value):
        if 0 <= y < ROWS:
            for offset, char in enumerate(value):
                if 0 <= x+offset < COLS:
                    grid[y][x+offset] = char
    def line(x0, y0, x1, y1, char):
        count = max(abs(x1-x0), abs(y1-y0))
        for step in range(count+1):
            f = step / max(1, count)
            put(round(x0+(x1-x0)*f), round(y0+(y1-y0)*f), char)
    def box(x, y, width, height):
        put(x,y,'+'+'-'*(width-2)+'+')
        for row in range(y+1,y+height-1): put(x,row,'|'+' '*(width-2)+'|')
        put(x,y+height-1,'+'+'-'*(width-2)+'+')
    def sprite(x, y, ghost=False, scale=1):
        blink = int((t+episode*.3)*3) % 13 == 0
        mouth = 'o' if int(t*4+episode) % 3 == 0 else '-'
        eyes = '- -' if blink else 'o o'
        if ghost:
            art = [' .---. ', '/     '+chr(92), '| '+eyes+' |', '|  '+mouth+'  |', '|     |', '/ | | '+chr(92), '~ ~ ~ ~']
        else:
            art = [' .---. ', '/     '+chr(92), '| '+eyes+' |', '|  '+mouth+'  |', ' '+chr(92)+'___/ ', '   |   ', ' ./|'+chr(92)+'. ', '/  |  '+chr(92), '  / '+chr(92)+'  ', ' _| |_ ']
        for row, value in enumerate(art):
            for repeat in range(scale): put(x,y+row*scale+repeat,''.join(char*scale for char in value))
    for row in range(20,ROWS):
        for col in range((row+episode)%4,COLS,8): put(col,row,'.')
    if theme == 'pods':
        if phase == 0:
            box(1,1,18,20); box(21,1,18,20)
            for y in range(2,21): put(20,y,':')
            box(3,15,14,5); box(23,15,14,5)
            put(6,3,'[===]'); put(26,3,'[===]')
            sprite(6,6); sprite(26,6)
            put(19,9,'<3' if int(t*2)%3 == 0 else '  ')
        elif phase == 1:
            line(0,0,8,5,chr(92)); line(39,0,32,5,'/')
            box(3,4,34,19)
            sprite(13,2,scale=2)
            put(2,22,'_'*36)
        else:
            line(1,0,1,23,'|'); line(38,0,38,23,'|')
            for y in range(3,23,3): put(0,y,'=='); put(38,y,'==')
            line(10,1,29,1,'_'); line(9,2,9,19,'|'); line(30,2,30,19,'|')
            shift = min(3,int(moment/2))
            sprite(4+shift,6); sprite(29-shift,6)
            if moment > 3: put(18,6,'<3')
            line(0,20,39,20,'_')
    elif phase == 0:
        line(3,7,20,0,'/'); line(20,0,36,7,chr(92))
        box(5,7,30,17)
        for x in (8,15,23,30):
            box(x,9,4,4)
            put(x+1,10,'oo' if (int(t*2)+x+season)%5 else '  ')
        box(16,15,8,9); put(19,18,'|'); put(19,19,'|')
        sprite(26,14+int(math.sin(t*2)),True)
        line(0,24,39,24,'_')
    elif phase == 1:
        line(0,0,15,7,chr(92)); line(39,0,24,7,'/')
        line(0,24,15,18,'/'); line(39,24,24,18,chr(92))
        box(15,7,10,12)
        box(1,4,9,16); box(30,4,9,16)
        put(3,5,str(111+episode)); put(32,5,str(211+episode))
        put(7,12,'o'); put(31,12,'o')
        for y in (20,22,24): line(11-(y-20)*2,y,28+(y-20)*2,y,'_')
        sprite(17+int(math.sin(t*1.4)*3),10+int(math.sin(t*2)),True)
    else:
        box(1,2,7,15); put(3,4,'(o)'); put(4,7,'|'); put(3,9,'/|')
        box(29,3,9,10); sprite(30,5,True)
        put(12,3,'o o o o'); put(12,4,'| | | |')
        sprite(16,7,True)
        box(2,17,36,7); put(4,18,'='*32)
        for x in range(5,35,5): put(x,21,'|')
        put(31,16,'(o)' if int(t*3)%3 else ' o ')
    return '\n'.join(''.join(row) for row in grid)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('_site'))
    args = parser.parse_args()
    assets = args.output/'assets'
    path = assets/'catalogue.json'
    catalogue = json.loads(path.read_text())
    count = 0
    for item in catalogue:
        if not item.get('series') or not item.get('episode'):
            continue
        original = json.loads((assets/Path(item['variants']['low']['fallback']).name).read_text())
        theme = 'pods' if '-pods-' in item['id'] else 'hotel'
        for quality, fps in FPS.items():
            frames = [scene(theme,item['season'],item['episode'],n/fps) for n in range(24*fps)]
            data = dict(version=1,layout='phone-cells',cell_width=6,cell_height=8,cols=COLS,rows=ROWS,fps=fps,frames=frames,subtitles=original.get('subtitles',[]))
            raw = json.dumps(data,separators=(',',':')).encode()
            packed = gzip.compress(raw,compresslevel=9,mtime=0)
            variant = item['variants'][quality]
            name = f"{item['id']}-lcd2-{quality}.json"
            (assets/name).write_bytes(raw)
            (assets/(name+'.gz')).write_bytes(packed)
            variant.update(path='assets/'+name+'.gz',fallback='assets/'+name,bytes=len(packed))
            if quality == 'low': item['poster'] = frames[fps*2]
        item['playback_layout'] = 'phone-cells'
        count += 1
    path.write_text(json.dumps(catalogue,indent=2))
    root = Path(__file__).resolve().parents[1]
    shutil.copyfile(root/'player.js',args.output/'player.js')
    shutil.copyfile(root/'streaming.js',args.output/'streaming.js')
    shutil.copyfile(root/'themes.css',args.output/'themes.css')
    shutil.copyfile(root/'theme.js',args.output/'theme.js')
    index = args.output/'index.html'
    source = index.read_text()
    anchor = '<script src="./sharing.js" defer></script>'
    if source.count(anchor) != 1:
        raise ValueError('Expected the sharing build to run before phone_video.py')
    source = source.replace('</head>','<link rel="stylesheet" href="./themes.css"></head>',1)
    source = source.replace(anchor,'<script src="./player.js?v=lcd2" defer></script><script src="./streaming.js?v=nav3" defer></script><script src="./theme.js?v=1" defer></script>'+anchor,1)
    index.write_text(source)
    print(f'Recomposed {count} demo clips for a native 240x200 LCD scene area.')

if __name__ == '__main__':
    main()
