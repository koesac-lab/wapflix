import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from wapflix_captions import english_track,load_captions
from fetch_test_subtitles import fetch
from progressive_captions import CaptionApp,caption_html,make_handler
import progressive_test as base

SAMPLE='1\n00:00:29,000 --> 00:00:31,000\nAlready active\n\n2\n00:00:33,500 --> 00:00:35,500\nAcross buffering\n\n3\n00:00:38,000 --> 00:00:40,000\nOutside'

class CaptionHelpersTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_uploaded_preferred_to_auto(self):
        self.assertEqual(english_track({'subtitles':{'en-GB':[{}]},'automatic_captions':{'en':[{}]}}),('en-GB','subtitles'))
    def test_language_selection(self):
        self.assertEqual(english_track({'automatic_captions':{'en-orig':[{}],'fr':[{}]}}),('en-orig','automatic_captions'))
    def test_missing_english_fails(self):
        with self.assertRaisesRegex(ValueError,'No English'):english_track({'subtitles':{'fr':[{}]}})
    def test_offset_overlap_and_clipping(self):
        srt=self.root/'sample.srt';srt.write_text(SAMPLE)
        result=load_captions(srt,30,6)
        self.assertEqual(result['selected_cue_count'],2)
        self.assertEqual((result['cues'][0]['start'],result['cues'][0]['end']),(0,1))
        self.assertEqual((result['cues'][1]['start'],result['cues'][1]['end']),(3.5,5.5))
    def test_clip_end_and_entities(self):
        srt=self.root/'sample.srt';srt.write_text('1\n00:00:35,000 --> 00:00:40,000\nA &amp; B\nA &amp; B')
        result=load_captions(srt,30,6)
        self.assertEqual(result['cues'],[{'start':5,'end':6,'text':'A & B'}])
    def test_empty_subtitles_rejected(self):
        srt=self.root/'empty.srt';srt.write_text('')
        with self.assertRaises(ValueError):load_captions(srt,30,6)
    def test_html_compatibility_guard(self):
        result=caption_html(base.HTML)
        self.assertIn('id="captionText"',result)
        self.assertIn('captionText.textContent',result)
        with self.assertRaises(ValueError):caption_html('<html>different source</html>')
    def test_download_pipeline_and_cached_provenance(self):
        output=self.root/'source.youtube.en.srt';calls=[]
        def fake(arguments):
            calls.append(arguments)
            if '--dump-single-json' in arguments:return json.dumps({'id':'dQw4w9WgXcQ','subtitles':{'en':[{'ext':'vtt'}]}})
            template=arguments[arguments.index('-o')+1]
            Path(template.replace('%(ext)s','en.srt')).write_text(SAMPLE)
            return ''
        with patch('fetch_test_subtitles.shutil.which',return_value='/usr/bin/fake'),patch('fetch_test_subtitles.run_ytdlp',side_effect=fake),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            record=fetch(output)
            self.assertEqual(record['track_type'],'subtitles')
            self.assertTrue(output.is_file());self.assertIn('--skip-download',calls[1]);self.assertIn('--no-write-auto-subs',calls[1])
            fetch(output);self.assertEqual(len(calls),2)
    def test_no_subtitle_file_is_not_success(self):
        def fake(arguments):
            if '--dump-single-json' in arguments:return json.dumps({'id':'dQw4w9WgXcQ','subtitles':{'en':[{}]}})
            return ''
        with patch('fetch_test_subtitles.shutil.which',return_value='/usr/bin/fake'),patch('fetch_test_subtitles.run_ytdlp',side_effect=fake),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ValueError):fetch(self.root/'not-downloaded.srt')
        self.assertFalse((self.root/'not-downloaded.srt').exists())
    def test_tampered_cache_rejected(self):
        output=self.root/'source.youtube.en.srt';output.write_text(SAMPLE)
        output.with_suffix('.json').write_text(json.dumps({'video_id':'dQw4w9WgXcQ','sha256':'wrong'}))
        with self.assertRaises(ValueError):fetch(output)

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class CaptionServerTests(unittest.TestCase):
    def test_real_worker_and_caption_api(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=root/'source.mp4';srt=root/'source.srt';srt.write_text(SAMPLE)
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=12:duration=2','-c:v','mpeg4','-threads','1',str(video)],check=True,capture_output=True,timeout=20)
            app=CaptionApp(video,srt,0,2);server=base.TestServer(('127.0.0.1',0),make_handler(app))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(url,timeout=3) as response:self.assertIn(b'id="captionText"',response.read())
                start=Request(url+'/api/start',data=b'{"delay":0}',headers={'X-Wapflix-Test':app.token,'Content-Type':'application/json'})
                with urlopen(start,timeout=3) as response:ident=json.load(response)['id']
                endpoint=url+'/api/captions?id='+ident
                with self.assertRaises(HTTPError) as error:urlopen(endpoint,timeout=3)
                self.assertEqual(error.exception.code,403)
                with urlopen(Request(endpoint,headers={'X-Wapflix-Test':app.token}),timeout=3) as response:
                    data=json.load(response);self.assertEqual(data['source_cue_count'],3);self.assertEqual(data['selected_cue_count'],0)
            finally:server.shutdown();server.server_close();app.close();thread.join(timeout=1)

if __name__=='__main__':unittest.main()
