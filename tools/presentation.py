#!/usr/bin/env python3
"""Build static social previews, pixel icons and sharing hooks. Standard library only."""
import argparse
import html
import json
import re
import shutil
import struct
import textwrap
import zlib
from pathlib import Path
from urllib.parse import urlparse

GREEN = '#a6bd70'
INK = '#25371e'
DESCRIPTION = 'A green-backlit pocket cinema. Tiny ASCII transmissions, large feelings. An interactive art experiment.'

def rgb(value):
    return bytes.fromhex(value.lstrip('#'))

class Raster:
    def __init__(self, width, height, colour=GREEN):
        self.width, self.height = width, height
        self.data = bytearray(rgb(colour) * (width * height))
    def rect(self, x, y, width, height, colour=INK):
        x, y, width, height = map(int, (x, y, width, height))
        left, right = max(0, x), min(self.width, x + width)
        top, bottom = max(0, y), min(self.height, y + height)
        if right <= left or bottom <= top:
            return
        line = rgb(colour) * (right-left)
        for row in range(top, bottom):
            offset = (row*self.width+left)*3
            self.data[offset:offset+len(line)] = line
    def text(self, value, x, y, scale, glyphs):
        for char in value.upper():
            bits = glyphs.get(char)
            if bits:
                for row in range(7):
                    mask = int(bits[row*2:row*2+2], 16)
                    for col in range(5):
                        if mask & (16 >> col):
                            self.rect(x+col*scale, y+row*scale, scale, scale)
            x += 6*scale
    def png(self):
        def chunk(kind, payload):
            return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind+payload) & 0xffffffff)
        stride = self.width*3
        scanlines = b''.join(b'\x00'+self.data[y*stride:(y+1)*stride] for y in range(self.height))
        return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', self.width, self.height, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(scanlines, 9))+chunk(b'IEND', b'')

def icon(size):
    image = Raster(64, 64)
    image.rect(14, 16, 36, 32)
    for x in (16, 46):
        for y in (20, 28, 36):
            image.rect(x, y, 2, 4, GREEN)
    for x, y, w, h in ((26,22,4,20),(30,26,4,12),(34,30,4,4)):
        image.rect(x, y, w, h, GREEN)
    result = Raster(size, size)
    for y in range(size):
        for x in range(size):
            src = ((y*64//size)*64+x*64//size)*3
            dst = (y*size+x)*3
            result.data[dst:dst+3] = image.data[src:src+3]
    return result.png()

def poster(path, glyphs, title=None):
    image = Raster(1200, 630, '#171d22')
    image.rect(52, 44, 1096, 542, '#303d49')
    image.rect(72, 64, 1056, 502)
    image.rect(84, 76, 1032, 478, GREEN)
    image.text('WAP / TEXT CONNECTION', 116, 100, 3, glyphs)
    image.text('WAPFLIX', 116, 157, 13, glyphs)
    for i in range(4):
        image.rect(976+i*16, 117-i*10, 11, 10+i*10)
    lines = textwrap.wrap(title, 36)[:3] if title else ['POCKET CINEMA.', 'SMALL PICTURES. LARGE FEELINGS.']
    for n, line in enumerate(lines):
        image.text(line, 116, 302+n*48, 4, glyphs)
    image.text('ASCII DEMO / NOT ACTUAL EPISODE FOOTAGE' if title else 'CINEMA FOR THE END OF THE BANDWIDTH.', 116, 500, 3, glyphs)
    path.write_bytes(image.png())

def tags(base, title, description, url=None, image=None):
    e = html.escape
    url, image = url or base, image or base+'social/cover.png'
    return f"""
<meta name="description" content="{e(description, quote=True)}">
<link rel="canonical" href="{e(url, quote=True)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="WAPFLIX">
<meta property="og:locale" content="en_GB">
<meta property="og:title" content="{e(title, quote=True)}">
<meta property="og:description" content="{e(description, quote=True)}">
<meta property="og:url" content="{e(url, quote=True)}">
<meta property="og:image" content="{e(image, quote=True)}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title+' on a green-backlit pixel screen', quote=True)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title, quote=True)}">
<meta name="twitter:description" content="{e(description, quote=True)}">
<meta name="twitter:image" content="{e(image, quote=True)}">
<meta name="twitter:image:alt" content="{e(title+' on a green-backlit pixel screen', quote=True)}">
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('_site'))
    parser.add_argument('--base-url', default='https://koesac-lab.github.io/wapflix/')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')+'/'
    parsed = urlparse(base)
    if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.query or parsed.fragment:
        parser.error('--base-url must be an absolute HTTP(S) directory URL without query or fragment')
    root = Path(__file__).resolve().parents[1]
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    source = (root/'index.html').read_text()
    glyphs = dict(re.findall(r"([A-Z]):'([0-9A-F]{14})'", source))
    glyphs.update(re.findall(r"'([^']+)':'([0-9A-F]{14})'", source))
    if len(glyphs) < 30:
        raise ValueError('Expected the handset bitmap font in index.html')
    def replace(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Handset integration anchor changed: '+old)
        source = source.replace(old, new, 1)
    replace('}}init();', '}}window.wapflixReady=init();')
    replace("if(e.altKey||e.ctrlKey||e.metaKey)return;", "if(e.target.closest?.('dialog'))return;if(e.altKey||e.ctrlKey||e.metaKey)return;")
    replace('<button class="key" data-key="3">3<small>DEF</small></button>', '<button class="key" data-key="3" aria-label="Share WAPFLIX or this transmission">3<small>SHARE</small></button>')
    replace('0 QUALITY · * MENU · # BACKLIGHT', '3 SHARE · 0 QUALITY · * MENU · # LIGHT')
    head = tags(base, 'WAPFLIX / pocket cinema', DESCRIPTION)
    head += """<link rel="icon" href="./favicon.ico" sizes="16x16 32x32">
<link rel="icon" href="./favicon.svg" type="image/svg+xml" sizes="any">
<link rel="apple-touch-icon" href="./icons/apple-touch-icon.png" sizes="180x180">
<link rel="manifest" href="./manifest.webmanifest">
<meta name="application-name" content="WAPFLIX">
<meta name="apple-mobile-web-app-title" content="WAPFLIX">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="stylesheet" href="./sharing.css">
"""
    replace('</head>', head+'</head>')
    replace('</body>', '<script src="./sharing.js" defer></script></body>')
    (output/'index.html').write_text(source)
    for name in ('sharing.js', 'sharing.css'):
        shutil.copyfile(root/name, output/name)
    icons, social = output/'icons', output/'social'
    icons.mkdir(exist_ok=True)
    social.mkdir(exist_ok=True)
    for size, name in ((16,'favicon-16.png'),(32,'favicon-32.png'),(180,'apple-touch-icon.png'),(192,'icon-192.png'),(512,'icon-512.png'),(512,'maskable-512.png')):
        (icons/name).write_bytes(icon(size))
    images = [(size, icon(size)) for size in (16,32)]
    offset = 6+16*len(images)
    entries, payloads = [], []
    for size, payload in images:
        entries.append(struct.pack('<BBBBHHII',size,size,0,0,1,24,len(payload),offset))
        payloads.append(payload)
        offset += len(payload)
    (output/'favicon.ico').write_bytes(struct.pack('<HHH',0,1,len(images))+b''.join(entries)+b''.join(payloads))
    holes = ''.join(f'<rect x="{x}" y="{y}" width="2" height="4" fill="{GREEN}"/>' for x in (16,46) for y in (20,28,36))
    (output/'favicon.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" shape-rendering="crispEdges"><rect width="64" height="64" fill="{GREEN}"/><rect x="14" y="16" width="36" height="32" fill="{INK}"/>{holes}<path d="M26 22h4v4h4v4h4v4h-4v4h-4v4h-4z" fill="{GREEN}"/></svg>')
    manifest = dict(id='./',name='WAPFLIX / pocket cinema',short_name='WAPFLIX',description=DESCRIPTION,start_url='./?source=homescreen',scope='./',display='standalone',background_color=GREEN,theme_color=GREEN,lang='en-GB',icons=[dict(src=f'icons/icon-{size}.png',sizes=f'{size}x{size}',type='image/png',purpose='any') for size in (192,512)]+[dict(src='icons/maskable-512.png',sizes='512x512',type='image/png',purpose='maskable')])
    (output/'manifest.webmanifest').write_text(json.dumps(manifest,indent=2))
    poster(social/'cover.png', glyphs)
    catalogue = json.loads((output/'assets/catalogue.json').read_text())
    for item in catalogue:
        ident = item['id']
        if not re.fullmatch('[a-z0-9-]+', ident):
            raise ValueError('Unsafe catalogue identifier')
        title = 'WAPFLIX / '+item['title']
        description = item['description']
        if 'demo' not in description.lower():
            description += ' An original ASCII art transmission.'
        url = base+'share/'+ident+'/'
        poster(social/(ident+'.png'), glyphs, item['title'])
        head = tags(base,title,description,url,base+'social/'+ident+'.png')
        destination = base+'?episode='+ident
        redirect = 'const u=new URL('+json.dumps(destination)+');const t=new URLSearchParams(location.search).get("t");if(t!==null&&Number.isFinite(Number(t))&&Number(t)>=0)u.searchParams.set("t",String(Math.floor(Number(t))));location.replace(u.href);'
        page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title>'+head+'</head><body style="background:#a6bd70;color:#25371e;font-family:monospace"><h1>'+html.escape(item['title'])+'</h1><p>'+html.escape(description)+'</p><p><a href="'+html.escape(destination,quote=True)+'">Open transmission in WAPFLIX</a></p><script>'+redirect+'</script></body></html>'
        directory = output/'share'/ident
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'index.html').write_text(page)
    print(f'Built app icons, root preview and {len(catalogue)} static transmission share pages.')

if __name__ == '__main__':
    main()
