import http.client
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from tools.lcd_stream_captions import CaptionApp, caption_html, find_subtitles, base

ROOT=Path(__file__).resolve().parents[1]
SRT='1\n00:00:00,000 --> 00:00:00,900\nBefore\n\n2\n00:00:01,000 --> 00:00:02,000\n<i>Crossing</i>\n\n3\n00:00:02,000 --> 00:00:03,000\nNext\n\n4\n00:00:03,500 --> 00:00:04,500\nLater\n'

class InjectionTests(unittest.TestCase):
    def test_guarded_html_and_single_script(self):
        original=(ROOT/'tools/lcd_stream_viewer.html').read_text()
        result=caption_html(original)
        self.assertEqual(result.count('id="captionText"'),1)
        self.assertEqual(result.count('<script'),1)
        self.assertIn('nonce="__TOKEN__"',result)
        self.assertNotIn('id="captionText"',original)
        with self.assertRaises(ValueError): caption_html(result)
        with self.assertRaises(ValueError): caption_html(original.replace('function draw(){','function changed(){'))
    def test_detection_and_disable(self):
        with tempfile.TemporaryDirectory() as tmp:
            video=Path(tmp)/'source.mp4';srt=video.with_suffix('.youtube.en.srt');srt.write_text(SRT)
            self.assertEqual(find_subtitles(video),srt)
            self.assertIsNone(find_subtitles(video,disabled=True))
            missing=Path(tmp)/'missing.srt';self.assertEqual(find_subtitles(video,missing),missing)

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
class CaptionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.video=cls.root/'source.mkv'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=8',
            '-t','8','-c:v','ffv1',str(cls.video)],check=True,capture_output=True)
        cls.subtitle=cls.video.with_suffix('.youtube.en.srt');cls.subtitle.write_text(SRT)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_absolute_source_times_and_clipped_extract(self):
        app=CaptionApp(self.video,start=1.5,seconds=2)
        try:
            result=app.begin();data=result['captions']
            self.assertEqual(data['timebase'],'source')
            self.assertEqual(data['selected_cue_count'],2)
            self.assertEqual(data['cues'][0],{'start':1.5,'end':2.0,'text':'Crossing'})
            self.assertEqual(data['cues'][1],{'start':2.0,'end':3.0,'text':'Next'})
            self.assertNotIn('captions',app.current.pulse(0,False))
        finally: app.close()
    def test_actual_eof_clips_cues(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'end.srt';path.write_text('1\n00:00:07,000 --> 00:00:10,000\nAt end\n')
            app=CaptionApp(self.video,start=7,seconds=10,subtitles=path)
            try:
                result=app.begin();self.assertEqual(result['captions']['cues'][0]['end'],8)
            finally: app.close()
    def test_disabled_missing_and_warnings(self):
        app=CaptionApp(self.video,start=0,seconds=4,no_srt=True)
        try: self.assertEqual(app.begin()['captions']['track_found'],False)
        finally: app.close()
        with self.assertRaises(ValueError): CaptionApp(self.video,start=0,seconds=4,subtitles=self.root/'missing.srt')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mixed.srt';path.write_text(SRT+'\n5\nbad --> bad\nBroken\n')
            app=CaptionApp(self.video,start=0,seconds=4,subtitles=path)
            try:
                data=app.begin()['captions'];self.assertEqual(data['parse_error_count'],1);self.assertGreater(data['selected_cue_count'],0)
            finally: app.close()
    def test_http_caption_metadata_and_original_security(self):
        app=CaptionApp(self.video,start=1.5,seconds=2);app.allowed_hosts={'mini.local'}
        server=base.Server(('127.0.0.1',0),base.make_handler(app))
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.02),daemon=True);thread.start()
        def request(path,body=None,token=True,host=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'X-Wapflix-Test':app.token} if token else {}
            if host: headers['Host']=host
            if body is not None: headers['Content-Type']='application/json'
            try:
                conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
                response=conn.getresponse();raw=response.read();return response.status,raw
            finally: conn.close()
        try:
            status,raw=request('/api/start',{},token=False);self.assertEqual(status,403)
            status,raw=request('/',token=False,host='evil.example:'+str(server.server_port));self.assertEqual(status,403)
            status,raw=request('/',token=False,host='mini.local:'+str(server.server_port))
            self.assertEqual(status,200);self.assertIn(b'id="captions"',raw);self.assertNotIn(b'__TOKEN__',raw)
            status,raw=request('/api/start',{});self.assertEqual(status,200)
            data=json.loads(raw);self.assertEqual(data['captions']['cues'][0]['start'],1.5)
            first=app.current
            status,raw=request('/api/start',{});self.assertEqual(status,200)
            self.assertFalse(first.thread.is_alive())
            status,raw=request('/api/stop',{'id':json.loads(raw)['id']});self.assertEqual(status,200)
            self.assertFalse(app.current.thread.is_alive())
        finally:
            server.shutdown();app.close();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
