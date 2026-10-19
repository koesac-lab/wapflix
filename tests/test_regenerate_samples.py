import gzip
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tools.regenerate_samples import profiles, pack_variant

ROOT=Path(__file__).resolve().parents[1]

class FineLCDTests(unittest.TestCase):
    def test_profiles(self):
        self.assertEqual(profiles(240,9/16),{'low':(120,68,6),'medium':(240,135,8),'high':(240,135,12)})
        self.assertTrue(all(w<=240 and h<=200 and w%8==0 for w,h,f in profiles(240,2).values()))
    def test_streamed_packing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=root/'frame.raw'; raw.write_bytes(bytes.fromhex('a55a'))
            target=root/'clip.json'
            self.assertEqual(pack_variant(raw,target,8,2,8,[]),1)
            data=json.loads(target.read_text())
            self.assertEqual(data['frames'],['a55a'])
            self.assertEqual(gzip.decompress((root/'clip.json.gz').read_bytes()),target.read_bytes())
            raw.write_bytes(b'')
            with self.assertRaises(ValueError): pack_variant(raw,target,8,2,8,[])
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
    def test_both_captions_durations_cache_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); video=root/'source.mkv'; site=root/'site'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                'testsrc2=size=320x180:rate=24','-t','2','-c:v','ffv1',str(video)],check=True,capture_output=True)
            video.with_suffix('.youtube.en.srt').write_text('1\n00:00:00,100 --> 00:00:00,600\nEarly\n\n2\n00:00:01,300 --> 00:00:01,800\nLater\n')
            command=[sys.executable,str(ROOT/'tools/regenerate_samples.py'),'both','--video',str(video),
                '--output',str(site),'--start','.25','--seconds','.75']
            first=subprocess.run(command,check=True,capture_output=True,text=True)
            catalogue=site/'assets/catalogue.json'; original=catalogue.read_bytes()
            items=json.loads(original); self.assertEqual({e['id'] for e in items},{'test-video','test-video-full'})
            for item in items:
                duration=.75 if item['id']=='test-video' else 2
                for v in item['lcd_variants'].values():
                    data=json.loads((site/v['fallback']).read_text())
                    self.assertLessEqual(abs(len(data['frames'])/data['fps']-duration),1/data['fps'])
                    self.assertEqual(len(data['frames'][0]),data['cols']*data['rows']//4)
                    self.assertEqual(gzip.decompress((site/v['path']).read_bytes()),(site/v['fallback']).read_bytes())
                    self.assertEqual(data['subtitles'][0]['text'],'Early')
                    if duration==.75:
                        self.assertEqual(len(data['subtitles']),1)
                        self.assertEqual(data['subtitles'][0]['start'],0)
                        self.assertAlmostEqual(data['subtitles'][0]['end'],.35)
                    else: self.assertEqual(len(data['subtitles']),2)
                self.assertTrue(item['lcd_only'])
            before={p:p.stat().st_mtime_ns for p in (site/'assets').glob('*.json*')}
            second=subprocess.run(command,check=True,capture_output=True,text=True)
            self.assertEqual(second.stdout.count('cached assets retained'),2)
            self.assertEqual(before,{p:p.stat().st_mtime_ns for p in before})
            forced=subprocess.run(command+['--force'],check=True,capture_output=True,text=True)
            self.assertIn('converting',forced.stdout)
            bad=command.copy(); bad[bad.index('--start')+1]='999'
            self.assertNotEqual(subprocess.run(bad,capture_output=True).returncode,0)
            self.assertEqual(catalogue.read_bytes(),original)
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_monob_polarity_and_fixed_ordered_dither(self):
        with tempfile.TemporaryDirectory() as tmp:
            for value,expected in [(0,'ff'),(255,'00'),(128,None)]:
                output=Path(tmp)/f'{value}.raw'
                subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                    f'nullsrc=size=240x136:rate=1,format=gray,geq=lum={value}',
                    '-frames:v','2','-vf','negate,scale=240:136:flags=area:sws_dither=bayer,format=monob',
                    '-c:v','rawvideo','-threads:v','1','-f','rawvideo',str(output)],check=True,capture_output=True)
                raw=output.read_bytes(); size=240*136//8
                self.assertEqual(raw[:size],raw[size:])
                if expected: self.assertEqual(set(raw),{int(expected,16)})
                else:
                    coverage=sum(bin(x).count('1') for x in raw[:size])/(240*136)
                    self.assertTrue(.45<coverage<.55)
                    self.assertEqual(raw[:30],raw[8*30:9*30])

if __name__=='__main__': unittest.main()
