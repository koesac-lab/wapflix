import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from progressive_test import App, TestServer, make_handler

def wait_for(predicate,timeout=4):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        value=predicate()
        if value:return value
        time.sleep(.02)
    raise AssertionError('Timed out waiting for test condition')

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class ProgressiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.video=Path(cls.temp.name)/'fixture.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=12:duration=42',
            '-c:v','mpeg4','-threads','1',str(cls.video)],check=True,capture_output=True,timeout=20)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):self.apps=[]
    def app(self,seconds=6,lease=20):
        app=App(self.video,0,seconds,lease);self.apps.append(app);return app
    def tearDown(self):
        for app in self.apps:app.close()
    def test_first_chunk_before_completion(self):
        app=self.app();ident=app.begin(.2)['id'];s=app.get(ident)
        wait_for(lambda:s.snapshot()['generated_chunks']>=1)
        self.assertEqual(s.snapshot()['state'],'running')
        self.assertLess(s.snapshot()['ready_frames'],36)
        with s.lock:chunk=json.loads(gzip.decompress(s.chunks[0]))
        self.assertEqual((chunk['start_frame'],len(chunk['frames'])),(0,12))
        self.assertTrue(all(len(frame.split('\n'))==17 for frame in chunk['frames']))
        self.assertTrue(all(len(line)==40 for frame in chunk['frames'] for line in frame.split('\n')))
    def test_final_partial_chunk(self):
        app=self.app(seconds=2.5);s=app.get(app.begin(0)['id'])
        wait_for(lambda:s.snapshot()['state']=='complete')
        self.assertEqual(s.snapshot()['total_frames'],15)
        with s.lock:chunk=json.loads(gzip.decompress(s.chunks[1]))
        self.assertEqual((chunk['start_frame'],len(chunk['frames'])),(12,3))
    def test_explicit_stop_reaps_process(self):
        app=self.app();s=app.get(app.begin(2)['id']);wait_for(lambda:s.process is not None)
        s.stop();self.assertFalse(s.thread.is_alive());self.assertIsNotNone(s.process.poll())
        self.assertEqual(s.snapshot()['state'],'cancelled')
    def test_replacement_stops_previous_worker(self):
        app=self.app();old=app.get(app.begin(1)['id']);wait_for(lambda:old.process is not None)
        new=app.begin(0)
        self.assertNotEqual(old.id,new['id']);self.assertFalse(old.thread.is_alive())
    def test_lease_expiry(self):
        app=self.app(lease=.3);s=app.get(app.begin(2)['id'])
        wait_for(lambda:s.event.is_set(),2);wait_for(lambda:not s.thread.is_alive(),2)
        self.assertEqual(s.snapshot()['state'],'cancelled')
    def test_backpressure_and_eviction(self):
        app=self.app(seconds=40);s=app.get(app.begin(0)['id'])
        wait_for(lambda:s.snapshot()['generated_chunks']==15)
        time.sleep(.1);self.assertEqual(s.snapshot()['generated_chunks'],15)
        s.pulse(120,False)
        wait_for(lambda:s.snapshot()['state']=='complete')
        with s.lock:self.assertNotIn(0,s.chunks);self.assertLessEqual(len(s.chunks),15)
    def test_pause_holds_generation(self):
        app=self.app();s=app.get(app.begin(.1)['id'])
        s.pulse(0,True);time.sleep(.4);count=s.snapshot()['generated_chunks']
        time.sleep(.2);self.assertEqual(s.snapshot()['generated_chunks'],count)
        s.pulse(0,False);wait_for(lambda:s.snapshot()['generated_chunks']>count)
    def test_invalid_configuration(self):
        for start,seconds in ((-1,1),(0,121),(float('nan'),1)):
            with self.assertRaises(ValueError):App(self.video,start,seconds)
        app=self.app()
        for delay in (-1,6,float('nan'),True):
            with self.assertRaises(ValueError):app.begin(delay)
    def test_http_protocol(self):
        app=self.app();server=TestServer(('127.0.0.1',0),make_handler(app))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        def post(path,data,token=None):
            return urlopen(Request(url+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Wapflix-Test':token or app.token}),timeout=3)
        try:
            with self.assertRaises(HTTPError) as caught:post('/api/start',{'delay':0},'wrong')
            self.assertEqual(caught.exception.code,403)
            with post('/api/start',{'delay':.2}) as response:manifest=json.load(response)
            ident=manifest['id']
            chunk_url=url+'/api/chunk?id='+ident+'&n=0'
            with urlopen(Request(chunk_url,headers={'X-Wapflix-Test':app.token}),timeout=3) as response:self.assertEqual(response.status,204)
            wait_for(lambda:app.get(ident).snapshot()['generated_chunks']>=1)
            with urlopen(Request(chunk_url,headers={'X-Wapflix-Test':app.token}),timeout=3) as response:
                self.assertEqual(response.headers['Content-Encoding'],'gzip')
                self.assertEqual(len(json.loads(gzip.decompress(response.read()))['frames']),12)
            with post('/api/pulse',{'id':ident,'frame':0,'paused':False}) as response:self.assertEqual(json.load(response)['id'],ident)
            with post('/api/stop',{'id':ident}) as response:self.assertTrue(json.load(response)['stopped'])
        finally:server.shutdown();server.server_close();thread.join(timeout=1)

if __name__=='__main__':unittest.main()
