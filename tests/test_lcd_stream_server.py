import gzip
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from tools.lcd_stream_server import App, Server, make_handler

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.video=Path(cls.temp.name)/'source.mkv'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=8',
            '-t','30','-c:v','ffv1',str(cls.video)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        self.app=App(self.video,start=0,seconds=30)
        self.server=Server(('127.0.0.1',0),make_handler(self.app))
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.02),daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.app.close();self.server.server_close();self.thread.join(timeout=1)
    def request(self,path,body=None,token=True,extra=None):
        headers={}
        if token: headers['X-Wapflix-Test']=self.app.token
        if extra: headers.update(extra)
        data=None
        if body is not None: data=json.dumps(body);headers['Content-Type']='application/json'
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            conn.request('POST' if body is not None else 'GET',path,body=data,headers=headers)
            response=conn.getresponse();raw=response.read();status=response.status
            if response.getheader('Content-Encoding')=='gzip': raw=gzip.decompress(raw)
            content=raw.decode() if response.getheader('Content-Type','').startswith('text/html') else json.loads(raw) if raw else None
            return status,content
        finally: conn.close()
    def begin(self):
        status,data=self.request('/api/start',{})
        self.assertEqual(status,200);return self.app.get(data['id'])
    def wait(self,session,predicate):
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            state=session.snapshot()
            if predicate(state): return state
            if state['state']=='error': self.fail(state['error'])
            time.sleep(.02)
        self.fail('Timed out: '+str(session.snapshot()))
    def test_page_security_and_validation(self):
        status,page=self.request('/',token=False)
        self.assertEqual(status,200);self.assertIn(self.app.token,page);self.assertNotIn('__TOKEN__',page)
        self.assertEqual(self.request('/api/start',{},token=False)[0],403)
        self.assertEqual(self.request('/',extra={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('/api/start',{},extra={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/start',[])[0],400)
        session=self.begin()
        self.assertEqual(self.request('/api/pulse',{'id':session.id,'frame':1.5,'paused':False})[0],400)
        self.assertEqual(self.request('/api/chunk?id='+session.id+'&n=-1')[0],400)
    def test_http_chunks_progress_and_stop(self):
        session=self.begin();state=self.wait(session,lambda s:s['generated_chunks']>=2)
        self.assertEqual(state['state'],'running')
        status,chunk=self.request('/api/chunk?id='+session.id+'&n=0')
        self.assertEqual(status,200);self.assertEqual(chunk['cols'],240);self.assertEqual(chunk['rows'],135)
        self.assertEqual(chunk['layout'],'lcd-1bit');self.assertEqual(len(chunk['frames']),16)
        self.assertEqual(len(chunk['frames'][0]),8100)
        self.assertEqual(self.request('/api/stop',{'id':session.id})[0],200)
        self.assertEqual(session.snapshot()['retained_chunks'],0)
        self.assertFalse(session.thread.is_alive());self.assertIsNotNone(session.stream.process.poll())
    def test_bounded_lookahead_pause_eviction_and_resume(self):
        session=self.begin();state=self.wait(session,lambda s:s['generated_chunks']==8)
        self.assertEqual(state['retained_chunks'],8)
        self.request('/api/pulse',{'id':session.id,'frame':0,'paused':True})
        time.sleep(.15);self.assertEqual(session.snapshot()['generated_chunks'],8)
        self.request('/api/pulse',{'id':session.id,'frame':64,'paused':False})
        state=self.wait(session,lambda s:s['generated_chunks']==12)
        self.assertLessEqual(state['retained_chunks'],9)
        self.assertEqual(self.request('/api/chunk?id='+session.id+'&n=0')[0],410)
    def test_replacement_reaps_old_worker(self):
        first=self.begin();self.wait(first,lambda s:s['generated_chunks']>=1)
        second=self.begin();self.wait(second,lambda s:s['generated_chunks']>=1)
        self.assertFalse(first.thread.is_alive());self.assertIsNotNone(first.stream.process.poll())
        self.assertEqual(self.request('/api/chunk?id='+first.id+'&n=0')[0],404)
    def test_abandoned_session_expires(self):
        self.app.lease=.25;session=self.begin()
        self.wait(session,lambda s:s['state']=='stopped')
        self.assertFalse(session.thread.is_alive())
        if session.stream.process: self.assertIsNotNone(session.stream.process.poll())
    def test_partial_final_chunk(self):
        self.app.seconds=1;session=self.begin();state=self.wait(session,lambda s:s['state']=='complete')
        self.assertEqual(state['total_frames'],8)
        status,chunk=self.request('/api/chunk?id='+session.id+'&n=0')
        self.assertEqual(status,200);self.assertEqual(len(chunk['frames']),8)
    def test_immediate_repeated_replacement(self):
        old=[]
        for _ in range(3):
            session=self.begin();old.append(session)
        self.request('/api/stop',{'id':old[-1].id})
        self.assertTrue(all(not session.thread.is_alive() for session in old))
        self.assertTrue(all(session.stream.process is None or session.stream.process.poll() is not None for session in old))

if __name__=='__main__': unittest.main()
