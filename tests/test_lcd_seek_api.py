from concurrent.futures import ThreadPoolExecutor
import gzip
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from tools.lcd_stream_seek_api import SeekApp, StaleNavigation, make_handler, base

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
class SeekTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.video=Path(cls.temp.name)/'source.mkv'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=8','-t','16','-c:v','ffv1',str(cls.video)],check=True,capture_output=True)
        cls.video.with_suffix('.youtube.en.srt').write_text('1\n00:00:02,000 --> 00:00:04,000\nEarly\n\n2\n00:00:08,000 --> 00:00:10,000\nMiddle\n\n3\n00:00:12,000 --> 00:00:16,000\nTail\n')
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        self.app=SeekApp(self.video,start=2,seconds=12);self.sessions=[]
        original=self.app._replace
        def track(position):
            result=original(position);self.sessions.append(self.app.current);return result
        self.app._replace=track
    def tearDown(self):
        self.app.close()
        self.assertTrue(all(not s.thread.is_alive() for s in self.sessions))
        self.assertTrue(all(s.stream.process is None or s.stream.process.poll() is not None for s in self.sessions))
    def chunk(self,session):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            session.pulse(0,False)
            with session.lock: raw=session.chunks.get(0)
            if raw: return json.loads(gzip.decompress(raw))
            if session.snapshot()['state']=='error': self.fail(session.snapshot()['error'])
            time.sleep(.01)
        self.fail('No chunk produced')
    def test_forward_back_and_caption_window(self):
        initial=self.app.begin();nav=initial['navigation_id'];old=self.app.current
        self.chunk(old)
        ahead=self.app.seek(nav,1,8);self.assertEqual(ahead['source_start'],8)
        self.assertEqual(ahead['captions']['cues'][0]['text'],'Middle');self.assertEqual(ahead['captions']['cues'][-1]['end'],14)
        self.assertFalse(old.thread.is_alive());self.assertIsNotNone(old.stream.process.poll())
        self.assertEqual(self.chunk(self.app.current)['source_start'],8)
        back=self.app.seek(nav,2,3.3);self.assertEqual(back['source_start'],3.25)
        self.assertEqual(back['captions']['cues'][0],dict(start=3.25,end=4.0,text='Early'))
        self.assertEqual(self.chunk(self.app.current)['source_start'],3.25)
    def test_stale_and_out_of_order_revisions(self):
        nav=self.app.begin()['navigation_id'];current=self.app.seek(nav,2,8)['id']
        for revision in (1,2):
            with self.assertRaises(StaleNavigation): self.app.seek(nav,revision,4)
            self.assertEqual(self.app.current.id,current)
    def test_new_start_and_cancel_invalidate_old_navigation(self):
        first=self.app.begin()['navigation_id'];new=self.app.begin()['navigation_id']
        with self.assertRaises(StaleNavigation): self.app.seek(first,1,4)
        self.assertTrue(self.app.stop_navigation(first)['superseded']);self.assertFalse(self.app.current.stop_event.is_set())
        self.assertFalse(self.app.stop_navigation(new)['superseded'])
        with self.assertRaises(StaleNavigation): self.app.seek(new,99,8)
    def test_legacy_stop_prevents_resurrection(self):
        nav=self.app.begin()['navigation_id'];self.app.current.stop()
        with self.assertRaises(StaleNavigation): self.app.seek(nav,1,4)
    def test_validation_and_last_frame(self):
        nav=self.app.begin()['navigation_id']
        for revision,position in [(0,4),(True,4),(1.5,4),(1,float('nan')),(1,14),(1,1),(1,True)]:
            with self.assertRaises(ValueError): self.app.seek(nav,revision,position)
        result=self.app.seek(nav,1,13.875);self.assertEqual(result['seek_position'],13.875)
        self.assertEqual(len(self.chunk(self.app.current)['frames']),1)
    def test_concurrent_latest_revision_wins(self):
        nav=self.app.begin()['navigation_id'];barrier=threading.Barrier(2)
        def seek(revision,position):
            barrier.wait()
            try: return self.app.seek(nav,revision,position)
            except StaleNavigation: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(seek,1,4),pool.submit(seek,2,8)]
            [job.result(timeout=10) for job in jobs]
        self.assertEqual(self.app.revision,2);self.assertEqual(self.app.current.stream.start,8)
        self.assertLessEqual(sum(s.thread.is_alive() for s in self.sessions),1)
    def test_http_contract_security_and_smoke(self):
        server=base.Server(('127.0.0.1',0),make_handler(self.app))
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.02),daemon=True);thread.start()
        def request(path,body,token=True,extra=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Content-Type':'application/json'}
            if token: headers['X-Wapflix-Test']=self.app.token
            if extra: headers.update(extra)
            try:
                conn.request('POST',path,json.dumps(body),headers);r=conn.getresponse();raw=r.read();return r.status,json.loads(raw)
            finally: conn.close()
        try:
            self.assertEqual(request('/api/seek',{},token=False)[0],403)
            self.assertEqual(request('/api/seek',{},extra={'Origin':'https://evil.example'})[0],403)
            self.assertEqual(request('/api/seek',{},extra={'Host':'evil.example:'+str(server.server_port)})[0],403)
            status,data=request('/api/start',{});nav=data['navigation_id'];self.assertEqual(status,200)
            status,data=request('/api/seek',dict(navigation_id=nav,revision=2,position=8));self.assertEqual(status,200)
            self.assertEqual(request('/api/seek',dict(navigation_id=nav,revision=1,position=4))[0],409)
            self.assertEqual(request('/api/navigation/stop',dict(navigation_id=nav))[0],200)
            self.assertEqual(request('/api/seek',dict(navigation_id=nav,revision=3,position=4))[0],409)
            probe=subprocess.run([sys.executable,str(ROOT/'tools/lcd_seek_smoke.py'),'--url',f'http://127.0.0.1:{server.server_port}'],capture_output=True,text=True,timeout=20)
            self.assertEqual(probe.returncode,0,probe.stderr)
            final=json.loads(probe.stdout.splitlines()[-1]);self.assertEqual(final['event'],'m4a-complete')
            self.assertFalse(self.app.current.thread.is_alive())
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
