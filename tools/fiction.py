#!/usr/bin/env python3
"""Build invented ASCII episode samples; no real footage, dialogue or episode metadata."""
import argparse
import gzip
import json
import math
from pathlib import Path

LEVELS = {'low': (48, 4), 'medium': (72, 6), 'high': (96, 8)}
SERIES = [
    ('pods', 'Love Is Blind', 11, 'Boston', [
        ('A Connection Without Bars', ['I came here for a connection.', 'Emotional or dial-up?', 'Ideally one that does not drop.', 'We have already buffered so much together.']),
        ('The Longest Pause', ['You went quiet for six seconds.', 'That was network latency, not doubt.', 'Then why did your heart time out?', 'I was negotiating a better connection.']),
        ('Commitment Pending', ['Will you share your bandwidth with me?', 'Even when the signal gets weak?', 'Especially then.', 'COMMITMENT REQUEST: ACCEPTED.'])]),
    ('hotel', 'The Haunted Hotel', 1, '', [
        ('Do Not Disturb the Dead', ['Welcome. Your room has a view.', 'Of what?', 'The previous occupants.', 'They never really checked out.']),
        ('Room Service from Beyond', ['Someone ordered room service.', 'Nobody is staying on this floor.', 'Then who asked for extra sheets?', 'Probably the gentleman made of one.']),
        ('Late Checkout', ['Checkout was at eleven.', 'I have been here since 1911.', 'Then we need to discuss the minibar.', 'Some debts follow you forever.'])]),
    ('hotel', 'The Haunted Hotel', 2, '', [
        ('Under New Possession', ['Management has changed.', 'New owners?', 'New entities.', 'The loyalty scheme is now eternal.']),
        ('The Lift to Nowhere', ['Which floor?', 'The one that was not here yesterday.', 'Stairs might be safer.', 'The stairs have also resigned.']),
        ('Five Stars, No Survivors', ['The guest left a review.', 'What did it say?', 'Lovely atmosphere. Difficult to leave.', 'Five stars. One unresolved haunting.'])])]

def render(theme, season, episode, title, t, cols, rows):
    grid = [[' '] * cols for _ in range(rows)]
    def text(x, y, value):
        if 0 <= y < rows:
            for i, char in enumerate(value):
                if 0 <= x + i < cols: grid[y][x+i] = char
    def center(y, value): text(max(0, (cols-len(value))//2), y, value[:cols])
    def box(x, y, w, h):
        text(x, y, '+' + '-' * (w-2) + '+')
        for yy in range(y+1, y+h-1): text(x, yy, '|' + ' ' * (w-2) + '|')
        text(x, y+h-1, '+' + '-' * (w-2) + '+')
    def person(x, y, ghost=False):
        text(x-1, y, '.-. ' if ghost else ' O ')
        text(x-1, y+1, 'o o' if ghost else '/|\\')
        text(x-1, y+2, '~~~' if ghost else '/ \\')
    center(0, 'FICTIONAL SAMPLE / NOT ACTUAL FOOTAGE')
    center(1, f'S{season:02} E{episode:02} / {title.upper()}')
    phase = min(2, int(t//8))
    if theme == 'pods':
        if phase == 0:
            w = cols//2-4
            box(2, 3, w, rows-5); box(cols//2+2, 3, w, rows-5)
            center(3, ' BOSTON / THE PODS ')
            for y in range(5, rows-3): text(cols//2, y, ':')
            person(cols//4, rows-7); person(cols*3//4, rows-7)
            text(4, rows-4, '[___]'); text(cols-10, rows-4, '[___]')
            center(rows//2, '<3' if int(t*2)%2 else ' . ')
        elif phase == 1:
            center(4, 'PRIVATE CONFESSIONAL')
            person(cols//2, rows//2-1)
            center(rows-4, '[ CAMERA 01 / FEELINGS UNCOMPRESSED ]')
            text(3, 6, 'REC *' if int(t*2)%2 else 'REC  ')
        else:
            center(4, 'THE REVEAL')
            person(cols//2-7+min(3,int((t-16)/2)), rows//2-1)
            person(cols//2+7-min(3,int((t-16)/2)), rows//2-1)
            center(rows-4, '<3  CONNECTION ESTABLISHED  <3')
    else:
        if phase == 0:
            center(3, ' THE HAUNTED HOTEL ')
            box(cols//5, 4, cols*3//5, rows-7)
            for x in range(cols//5+3, cols*4//5-3, 7):
                text(x, 6, '[:]' if (int(t)+x+season)%4 else '[ ]')
            center(rows-5, '[ CHECK IN / NEVER OUT ]')
            person(cols-7, rows-7, True)
        elif phase == 1:
            center(3, 'CORRIDOR / FLOOR ' + ('13' if season == 1 else '??'))
            for k in range(3):
                box(2+k*(cols//3), 5, max(8,cols//3-4), rows-8)
                text(4+k*(cols//3), 5, f' {113+k+episode} ')
            person(cols//2+int(math.sin(t*2)*3), rows-7, True)
            if int(t*3)%3 == 0: center(rows-3, '... SOMETHING MOVED ...')
        else:
            center(3, 'RECEPTION / NIGHT SHIFT')
            person(cols//2, rows//2-1, True)
            center(rows-5, '_' * (cols-12))
            center(rows-4, '|  VACANCY: BOTH KINDS OF SPIRIT  |')
            center(rows-3, 'DING' if int(t*2)%2 else '    ')
    center(rows-1, 'WAPFLIX / INVENTED 24-SECOND ART CLIP')
    return '\n'.join(''.join(line) for line in grid)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('assets'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output/'catalogue.json'
    catalogue = json.loads(path.read_text()) if path.exists() else []
    entries = []
    for theme, series, season, location, episodes in SERIES:
        for episode, (title, dialogue) in enumerate(episodes, 1):
            ident = f'fiction-{theme}-s{season:02}e{episode:02}'
            subtitles = [dict(start=1+i*6, end=min(24,6+i*6), text=line) for i,line in enumerate(dialogue)]
            variants = {}
            poster = ''
            for level, (cols, fps) in LEVELS.items():
                rows = round(cols*9/32)
                frames = [render(theme, season, episode, title, n/fps, cols, rows) for n in range(24*fps)]
                data = dict(version=1, cols=cols, rows=rows, fps=fps, frames=frames, subtitles=subtitles)
                raw = json.dumps(data, separators=(',',':')).encode()
                packed = gzip.compress(raw, compresslevel=9, mtime=0)
                name = f'{ident}-{level}.json'
                (args.output/name).write_bytes(raw)
                (args.output/(name+'.gz')).write_bytes(packed)
                variants[level] = dict(path=f'assets/{name}.gz', fallback=f'assets/{name}', bytes=len(packed))
                if level == 'low': poster = frames[fps*2]
            search = 'Love%20Is%20Blind' if theme == 'pods' else 'The%20Haunted%20Hotel'
            entries.append(dict(id=ident, title=f'{series} / S{season:02}E{episode:02}: {title}', label=f'FICTIONAL SAMPLE / S{season:02}E{episode:02}', description=f'Invented 24-second ASCII scene. {location+": " if location else ""}{dialogue[0]} Not an actual episode.', poster=poster, variants=variants, fictional=True, series=series, season=season, episode=episode, duration=24, overseerr=f'https://overseerr.alexkoester.com/search?query={search}'))
    ids = {entry['id'] for entry in entries}
    catalogue = entries + [entry for entry in catalogue if entry['id'] not in ids]
    path.write_text(json.dumps(catalogue, indent=2))
    print(f'Generated {len(entries)} fictional samples across {len(SERIES)} season collections.')

if __name__ == '__main__':
    main()
