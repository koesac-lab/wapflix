import contextlib
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tools.lcd_chunker import LCDStream, export, read_frame

class FrameTests(unittest.TestCase):
    def test_exact_read_and_eof(self):
        source=io.BytesIO(b'abc')
        self.assertEqual(read_frame(source,3),b'abc')
        self.assertEqual(read_frame(source,3),b'')
    def test_partial_read_fails(self):
        with self.assertRaises(ValueError): read_frame(io.BytesIO(b'ab'),3)
    def test_invalid_limits_before_source_access(self):
        for start,seconds in [(-1,1),(0,0),(0,121),(float('nan'),1),(0,float('inf'))]:
            with self.assertRaises(ValueError): LCDStream('missing.mp4',start,seconds)

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.video=cls.root/'source.mkv'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=24',
            '-t','10','-c:v','ffv1',str(cls.video)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_partial_final_chunk_and_timeline(self):
        with LCDStream(self.video,start=.25,seconds=2.625) as stream:
            chunks=list(stream)
        self.assertEqual([len(c['frames']) for c in chunks],[16,5])
        self.assertEqual([c['start_frame'] for c in chunks],[0,16])
        self.assertTrue(all(c['source_start']==.25 and c['cols']==240 and c['rows']==135 and c['fps']==8 for c in chunks))
        self.assertTrue(all(len(f)==8100 for c in chunks for f in c['frames']))
        self.assertEqual(stream.frames,21)
        self.assertIsNotNone(stream.process.poll())
    def test_first_chunk_precedes_worker_completion_and_close_reaps(self):
        with LCDStream(self.video,start=0,seconds=10) as stream:
            iterator=iter(stream);first=next(iterator)
            self.assertEqual(len(first['frames']),16)
            self.assertIsNone(stream.process.poll())
            iterator.close()
            self.assertTrue(stream.closed)
            self.assertIsNotNone(stream.process.poll())
        stream.close()
    def test_context_exception_reaps_worker(self):
        stream=LCDStream(self.video,start=0,seconds=10)
        with self.assertRaisesRegex(RuntimeError,'consumer failed'):
            with stream:
                iterator=iter(stream)
                next(iterator)
                self.assertIsNone(stream.process.poll())
                raise RuntimeError('consumer failed')
        self.assertIsNotNone(stream.process.poll())
    def test_export_manifest_and_gzip(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            output=Path(tmp)/'chunks'
            result=export(self.video,output,start=0,seconds=2.625)
            manifest=json.loads((output/'manifest.json').read_text())
            self.assertEqual(manifest['state'],'complete')
            self.assertEqual(manifest['generated_frames'],21)
            self.assertEqual(manifest['chunks'][1]['frames'],5)
            self.assertEqual(manifest,result)
            for c in manifest['chunks']:
                self.assertEqual(gzip.decompress((output/c['path']).read_bytes()),(output/c['fallback']).read_bytes())
            before=(output/'manifest.json').read_bytes()
            with self.assertRaises(FileExistsError): export(self.video,output,start=0,seconds=1)
            self.assertEqual((output/'manifest.json').read_bytes(),before)
    def test_source_end_limits_and_reuse_rejected(self):
        with self.assertRaises(ValueError): LCDStream(self.video,start=11,seconds=1)
        with LCDStream(self.video,start=9,seconds=10) as stream:
            self.assertAlmostEqual(stream.seconds,1)
            self.assertEqual(sum(len(c['frames']) for c in stream),8)
        with self.assertRaises(RuntimeError): next(iter(stream))
    def test_matches_fine_lcd_filter_bytes(self):
        command=['ffmpeg','-nostdin','-v','error','-ss','0.25','-i',str(self.video),
            '-vf','setpts=PTS-STARTPTS,trim=duration=2.625,format=gray,eq=contrast=1.08:gamma=1:brightness=0,negate,fps=8,scale=240:135:flags=area:sws_dither=bayer,setsar=1,format=monob',
            '-an','-sn','-dn','-c:v','rawvideo','-threads:v','1','-pix_fmt','monob','-f','rawvideo','pipe:1']
        expected=subprocess.check_output(command)
        with LCDStream(self.video,start=.25,seconds=2.625) as stream:
            actual=b''.join(bytes.fromhex(f) for c in stream for f in c['frames'])
        self.assertEqual(actual,expected)

if __name__=='__main__': unittest.main()
