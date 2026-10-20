import gzip
import hashlib
import http.client
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from tools.handset_static_preview import Preview, Server, FRONTEND, asset_path, bootstrap, make_handler

SOURCE='<!doctype html><html><head><style></style></head><body><button class="key" data-key="3">3<small>DEF</small></button><p>0 QUALITY · * MENU · # BACKLIGHT</p><script>document.addEventListener(\'keydown\',e=>{if(e.altKey||e.ctrlKey||e.metaKey)return;});async function init(){try{}catch(e){}}init();</script></body></html>'

def fixture(root):
    (root/'assets').mkdir()
    (root/'index.html').write_text(SOURCE)
    for name in FRONTEND: (root/name).write_text('// existing '+name+'\n')
    raw=json.dumps(dict(version=1,cols=8,rows=2,fps=8,layout='lcd-1bit',encoding='hex-msb',frames=['a55a'],subtitles=[])).encode()
    (root/'assets/sample.json').write_bytes(raw);(root/'assets/sample.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    variants={level:dict(path='assets/sample.json.gz',fallback='assets/sample.json') for level in ('low','medium','high')}
    entries=[dict(id='test-video',title='Test',variants=variants,lcd_variants=variants,lcd_only=True)]
    (root/'assets/catalogue.json').write_text(json.dumps(entries))
    return raw

class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.raw=fixture(self.root)
    def tearDown(self): self.temp.cleanup()
    def test_bootstrap_order_ready_and_source_unchanged(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        app=Preview(self.root);html=app.routes['/'][0].decode()
        self.assertIn('window.wapflixReady=init();',html)
        self.assertIn('nonce="'+app.nonce+'"',html)
        self.assertIn("e.target.closest?.('dialog')",html)
        offsets=[html.index('src="./'+name+'"') for name in ('player.js','streaming.js','theme.js','sharing.js')]
        self.assertEqual(offsets,sorted(offsets));self.assertEqual(app.count,1)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        if shutil.which('node'):
            inline=re.search(r'<script nonce="[^"]+">([\s\S]*?)</script>',html).group(1)
            result=subprocess.run(['node','--check'],input=inline,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_unknown_bootstrap_refused(self):
        with self.assertRaises(ValueError): bootstrap(SOURCE.replace('}}init();','changed();'),'nonce')
        with self.assertRaises(ValueError): bootstrap(SOURCE+SOURCE,'nonce')
    def test_bad_paths_refused(self):
        for name in ('../secret.json','assets/../secret.json','/assets/a.json','https://example.com/a.json',
                     'assets/a.json?x=1','assets/a%2ejson','assets/a\\b.json','assets/source.mp4'):
            with self.subTest(name=name),self.assertRaises(ValueError): asset_path(name)
    def test_missing_asset_fails_without_building(self):
        (self.root/'assets/sample.json.gz').unlink()
        with self.assertRaises(ValueError): Preview(self.root)
        self.assertFalse((self.root/'_site').exists())
    def test_symlink_escape_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            target=Path(outside)/'outside.json';target.write_text('secret')
            (self.root/'assets/sample.json').unlink();(self.root/'assets/sample.json').symlink_to(target)
            with self.assertRaises(ValueError): Preview(self.root)
    def test_http_routes_and_explicit_gzip(self):
        app=Preview(self.root,['mini.local']);server=Server(('127.0.0.1',0),make_handler(app))
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.02),daemon=True);thread.start()
        def request(path,method='GET',host=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            try:
                connection.request(method,path,headers={'Host':host} if host else {})
                response=connection.getresponse();raw=response.read();return response.status,dict(response.getheaders()),raw
            finally: connection.close()
        try:
            status,headers,raw=request('/');self.assertEqual(status,200);self.assertIn(b'window.wapflixReady',raw)
            for name in FRONTEND: self.assertEqual(request('/'+name)[0],200)
            self.assertEqual(request('/assets/catalogue.json')[0],200)
            status,headers,raw=request('/assets/sample.json.gz')
            self.assertEqual(status,200);self.assertNotIn('Content-Encoding',headers);self.assertEqual(gzip.decompress(raw),self.raw)
            self.assertEqual(request('/assets/sample.json')[2],self.raw)
            self.assertEqual(request('/assets/sample.json','HEAD')[2],b'')
            for path in ('/.git/config','/tools/handset_static_preview.py','/source.mp4','/%2e%2e/secret','/api/start'):
                self.assertEqual(request(path)[0],404)
            status,headers,_=request('/share/test-video/');self.assertEqual(status,302);self.assertEqual(headers['Location'],'/?episode=test-video')
            self.assertEqual(request('/',host='evil.example:'+str(server.server_port))[0],403)
            self.assertEqual(request('/',host='mini.local:'+str(server.server_port))[0],200)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
