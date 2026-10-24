"""5A.3A recovery: real HTTP routing, static gzip/CSP and real fenced media."""
import gzip
import http.client
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from tools import handset_fenced_preview as hosting
from tools.handset_static_preview import FRONTEND

SOURCE = """<!doctype html><html><head><style></style></head><body><button class="key" data-key="3">3<small>DEF</small></button><p>0 QUALITY · * MENU · # BACKLIGHT</p><script>document.addEventListener('keydown',e=>{if(e.altKey||e.ctrlKey||e.metaKey)return;});async function init(){try{}catch(e){}}init();</script></body></html>"""

def fixture(root):
    (root/'assets').mkdir()
    (root/'index.html').write_text(SOURCE)
    for name in (*FRONTEND, 'stream-source.js', 'handset-live.js'):
        (root/name).write_text('// fixture ' + name + '\n')
    raw = json.dumps({'version':1,'cols':8,'rows':2,'fps':8,'layout':'lcd-1bit',
        'encoding':'hex-msb','frames':['a55a'],'subtitles':[]}).encode()
    (root/'assets/sample.json').write_bytes(raw)
    (root/'assets/sample.json.gz').write_bytes(gzip.compress(raw, mtime=0))
    variants = {q:{'path':'assets/sample.json.gz','fallback':'assets/sample.json'}
                for q in ('low','medium','high')}
    (root/'assets/catalogue.json').write_text(json.dumps([
        {'id':'test-video','title':'Test','variants':variants,'lcd_variants':variants,'lcd_only':True}]))
    return raw

class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = fixture(self.root)
        self.host = hosting.HandsetHost(self.root, hosting.FixedSource(self.root/'unused.mp4'),
                                        no_srt=True, monitor=False)
        self.server = hosting.fenced.base.Server(('127.0.0.1',0), hosting.make_handler(self.host))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval':.01})
        self.thread.start()
        self.addCleanup(self.finish)

    def finish(self):
        self.server.shutdown()
        self.thread.join(2)
        self.host.close()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, method, path, body=None, *, auth=False, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=40)
        supplied = {'X-Wapflix-Test':self.host.token} if auth else {}
        supplied.update(headers or {})
        try:
            connection.request(method,path,body=None if body is None else json.dumps(body),headers=supplied)
            response = connection.getresponse()
            return response.status, response.getheaders(), response.read()
        finally:
            connection.close()

    def test_root_preserves_static_bootstrap_without_premature_live_entry(self):
        before = {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        status, headers, raw = self.request('GET','/')
        self.assertEqual(status,200)
        html = raw.decode()
        self.assertIn('window.wapflixReady=init();',html)
        self.assertIn("e.target.closest?.('dialog')",html)
        self.assertNotIn("e.target?.('dialog')",html)
        for name in ('player.js','streaming.js','theme.js','sharing.js'):
            self.assertIn('src="./'+name+'"',html)
        self.assertNotIn('src="./handset-live.js"',html)
        self.assertNotIn('wapflixLiveConfig',html)
        self.assertNotIn(self.host.token,html)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_one_nonce_on_static_api_and_errors(self):
        nonce = self.host.preview.nonce
        for method,path,body,auth in (
            ('GET','/',None,False),('GET','/stream-source.js',None,False),
            ('GET','/missing',None,False),('POST','/api/control/open',{},True),
            ('POST','/api/start',{},True)):
            status, headers, raw = self.request(method,path,body,auth=auth)
            csp = [v for k,v in headers if k.lower()=='content-security-policy']
            self.assertEqual(csp,[self.host.csp()])
            self.assertIn("'nonce-"+nonce+"'",csp[0])
            self.assertNotIn("'nonce-"+self.host.token+"'",csp[0])

    def test_static_gzip_is_explicit_not_http_encoded(self):
        status,headers,raw = self.request('GET','/assets/sample.json.gz')
        self.assertEqual(status,200)
        self.assertNotIn('Content-Encoding',dict(headers))
        self.assertEqual(gzip.decompress(raw),self.raw)
        self.assertEqual(self.request('GET','/assets/sample.json')[2],self.raw)
        self.assertEqual(self.request('HEAD','/assets/sample.json.gz')[2],b'')

    def test_catalogue_is_unchanged_and_only_allowlisted_files_are_served(self):
        status,headers,raw = self.request('GET','/assets/catalogue.json')
        self.assertEqual(raw,(self.root/'assets/catalogue.json').read_bytes())
        self.assertNotIn(b'local-stream-test',raw)
        for path in ('/.git/config','/tools/start_fence.py','/source.mp4','/assets/source.mp4',
                     '/%2e%2e/secret','/handset-live.js.bak'):
            self.assertEqual(self.request('GET',path)[0],404)
        for name in (*FRONTEND,'stream-source.js','handset-live.js'):
            self.assertEqual(self.request('GET','/'+name)[0],200)

    def test_host_origin_capability_and_fenced_identity(self):
        self.assertEqual(self.request('GET','/',headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('POST','/api/control/open',{})[0],403)
        self.assertEqual(self.request('POST','/api/control/open',{},auth=True,
            headers={'Origin':'http://evil.example'})[0],403)
        status,_,raw = self.request('POST','/api/start',{},auth=True)
        self.assertEqual(status,409)
        self.assertEqual(json.loads(raw)['code'],'fencing_required')
        self.assertIsNone(self.host.api.fence.snapshot()['active_owner'])

    def test_head_api_does_not_invoke_operations(self):
        before = self.host.api.fence.snapshot()
        self.assertEqual(self.request('HEAD','/api/control/open')[0],403)
        status,headers,raw = self.request('HEAD','/api/control/open',auth=True)
        self.assertEqual(status,405)
        self.assertEqual(raw,b'')
        self.assertEqual(dict(headers)['Content-Length'],'0')
        self.assertEqual(self.host.api.fence.snapshot(),before)
        for headers in ({'Host':'evil.example'},{'Origin':'http://evil.example'}):
            status,_,raw = self.request('HEAD','/api/control/open',auth=True,headers=headers)
            self.assertEqual((status,raw),(403,b''))

    def test_root_does_not_probe_or_start_conversion(self):
        with patch.object(hosting.fenced.base,'LCDStream',side_effect=AssertionError('probe')):
            self.assertEqual(self.request('GET','/')[0],200)
            self.assertEqual(self.request('GET','/assets/catalogue.json')[0],200)
        self.assertIsNone(self.host.api.fence.snapshot()['active_owner'])

    def test_missing_required_script_fails_before_backend_creation(self):
        (self.root/'stream-source.js').unlink()
        with patch.object(hosting.fenced,'FencedApp') as factory:
            with self.assertRaises(ValueError):
                hosting.HandsetHost(self.root,hosting.FixedSource(self.root/'unused.mp4'),no_srt=True)
            factory.assert_not_called()

    def test_trusted_hostname_alias(self):
        self.host.api.allowed_hosts.add('mini.local')
        self.host.preview.allowed_hosts.add('mini.local')
        host = {'Host':'mini.local:'+str(self.server.server_port)}
        self.assertEqual(self.request('GET','/',headers=host)[0],200)
        self.assertEqual(self.request('POST','/api/control/open',{},auth=True,headers=host)[0],200)

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg and ffprobe required')
class RealMediaHostTests(unittest.TestCase):
    setUp = HostTests.setUp
    finish = HostTests.finish
    request = HostTests.request
    def test_real_chunks_and_static_assets_share_origin_and_csp(self):
        video = self.root/'generated.mkv'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
            'testsrc2=size=64x48:rate=8','-t','6','-an','-c:v','ffv1','-threads','1',str(video)],
            check=True,timeout=30)
        self.host.api.factory = hosting.fenced.NavigationFactory(
            hosting.FixedSource(video,.5,3),no_srt=True)
        status,headers,raw = self.request('POST','/api/control/open',{},auth=True)
        client = json.loads(raw)['control_client_id']
        status,headers,raw = self.request('POST','/api/start',
            {'control_client_id':client,'start_revision':1},auth=True)
        self.assertEqual(status,200,raw)
        metadata = json.loads(raw)
        deadline = time.monotonic()+8
        result = None
        while time.monotonic()<deadline:
            result = self.request('GET','/api/chunk?id='+metadata['id']+'&n=0',auth=True)
            if result[0]==200: break
            time.sleep(.02)
        self.assertEqual(result[0],200)
        self.assertEqual(dict(result[1])['Content-Encoding'],'gzip')
        self.assertEqual(dict(result[1])['Content-Security-Policy'],self.host.csp())
        chunk = json.loads(gzip.decompress(result[2]))
        self.assertEqual(chunk['source_start'],.5)
        self.assertGreater(len(chunk['frames']),0)
        self.assertEqual(self.request('GET','/assets/sample.json.gz')[2],
                         (self.root/'assets/sample.json.gz').read_bytes())
        self.assertEqual(self.request('GET','/generated.mkv')[0],404)
        status,_,raw = self.request('POST','/api/control/cancel',
            {'control_client_id':client,'cancel_through':1},auth=True)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['cleanup'],'confirmed')
        self.assertIsNone(self.host.api.fence.snapshot()['active_owner'])

if __name__=='__main__':
    unittest.main()
