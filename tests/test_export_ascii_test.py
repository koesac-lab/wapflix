import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from export_ascii_test import export

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg tools required')
class FirstPlaybackExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.video=self.root/'fixture.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
            'testsrc2=size=160x90:rate=12:duration=2','-c:v','mpeg4','-threads','1',str(self.video)],
            check=True,capture_output=True,timeout=30)
    def tearDown(self):self.temp.cleanup()
    def test_export_is_playable_format(self):
        dest=self.root/'output'
        export(self.video,dest,start=0,seconds=1)
        clip=json.loads((dest/'clip.json').read_text())
        self.assertEqual((clip['cols'],clip['rows'],clip['fps'],len(clip['frames'])),(40,17,6,6))
        self.assertTrue(all(len(frame.split('\n'))==17 for frame in clip['frames']))
        self.assertTrue(all(len(line)==40 for frame in clip['frames'] for line in frame.split('\n')))
        self.assertIn("fetch('./clip.json')",(dest/'index.html').read_text())
    def test_refuses_nonempty_directory(self):
        dest=self.root/'output';dest.mkdir();(dest/'keep').write_text('unchanged')
        with self.assertRaises(ValueError):export(self.video,dest,start=0,seconds=1)
        self.assertEqual((dest/'keep').read_text(),'unchanged')
    def test_invalid_options(self):
        for start,seconds in ((-1,1),(0,31),(float('nan'),1),(0,float('inf'))):
            with self.assertRaises(ValueError):export(self.video,self.root/'output',start,seconds)
    def test_beyond_end(self):
        with self.assertRaises(ValueError):export(self.video,self.root/'output',start=99,seconds=1)
        self.assertFalse((self.root/'output').exists())

if __name__=='__main__':unittest.main()
