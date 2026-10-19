import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tools.lcd_video import dither, read_frame, scene, write_variant

ROOT = Path(__file__).resolve().parents[1]

class LCDTests(unittest.TestCase):
    def test_black_white_polarity_and_padding(self):
        self.assertEqual(dither(bytes([0])*9, 3, 3), 'ff80')
        self.assertEqual(dither(bytes([255])*9, 3, 3), '0000')
        self.assertEqual(dither(bytes([0, 255, 0, 255, 255, 0, 255, 0]), 4, 2), 'a5')
        with self.assertRaises(ValueError): dither(b'\\0', 2, 2)
    def test_fixed_half_tone(self):
        a = dither(bytes([128])*16, 4, 4)
        self.assertEqual(sum(int(c, 16).bit_count() for c in a), 8)
        self.assertEqual(a, dither(bytes([128])*16, 4, 4))
    def test_read_frame(self):
        self.assertEqual(read_frame(io.BytesIO(b'abc'), 3), b'abc')
        self.assertEqual(read_frame(io.BytesIO(), 3), b'')
        with self.assertRaises(ValueError): read_frame(io.BytesIO(b'a'), 3)
    def test_scenes_are_luminance_not_glyphs(self):
        for kind in ('drive', 'orbit', 'rain', 'pods', 'hotel'):
            frames = [scene(kind, t, 60, 50) for t in (0, .25, .625, 8.125, 12.375, 16.25, 21.5)]
            self.assertTrue(all(len(f) == 3000 for f in frames))
            self.assertTrue(all(len(set(f)) >= 3 for f in frames))
            self.assertGreater(len({dither(f, 60, 50) for f in frames}), 2)
    def test_format_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            frame = dither(bytes([128])*15, 5, 3)
            subtitles = [dict(start=0, end=1, text='A signal.')]
            v = write_variant(assets, 'test', 'low', 5, 3, 4, [frame], subtitles)
            raw = (assets/Path(v['fallback']).name).read_bytes()
            self.assertEqual(gzip.decompress((assets/Path(v['path']).name).read_bytes()), raw)
            data = json.loads(raw)
            self.assertEqual(data['layout'], 'lcd-1bit')
            self.assertEqual(data['encoding'], 'hex-msb')
            self.assertEqual(data['subtitles'], subtitles)
            self.assertEqual(data['frames'], [frame])
    def fixture(self, root, ident):
        assets = root/'assets'; assets.mkdir()
        variants = {}
        for level in ('low', 'medium', 'high'):
            name = 'test-'+level+'.json'
            (assets/name).write_text(json.dumps(dict(fps=4, frames=['A']*4,
                subtitles=[dict(start=0, end=1, text='A signal.')])) )
            variants[level] = dict(path='assets/'+name+'.gz', fallback='assets/'+name)
        (assets/'catalogue.json').write_text(json.dumps([dict(id=ident, variants=variants)]))
        return assets, variants
    def test_cli_preserves_ascii_and_skips_unknown_custom_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); assets, original = self.fixture(root, 'orbit')
            subprocess.run([sys.executable, str(ROOT/'tools/lcd_video.py'), '--output', str(root)], check=True, capture_output=True)
            item = json.loads((assets/'catalogue.json').read_text())[0]
            self.assertEqual(item['variants'], original)
            self.assertEqual(set(item['lcd_variants']), {'low', 'medium', 'high'})
            self.assertTrue(all((assets/Path(v['fallback']).name).is_file() for v in item['lcd_variants'].values()))
            item['id'] = 'custom'; item.pop('lcd_variants')
            (assets/'catalogue.json').write_text(json.dumps([item]))
            subprocess.run([sys.executable, str(ROOT/'tools/lcd_video.py'), '--output', str(root)], check=True, capture_output=True)
            self.assertNotIn('lcd_variants', json.loads((assets/'catalogue.json').read_text())[0])
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg unavailable')
    def test_real_video_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); assets, original = self.fixture(root, 'own-clip')
            video = root/'source.mkv'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                'testsrc2=size=64x48:rate=8', '-t', '1', '-c:v', 'ffv1', str(video)], check=True, capture_output=True)
            subprocess.run([sys.executable, str(ROOT/'tools/lcd_video.py'), '--output', str(root),
                '--video', str(video), '--id', 'own-clip', '--seconds', '1'], check=True, capture_output=True)
            item = json.loads((assets/'catalogue.json').read_text())[0]
            self.assertEqual(item['variants'], original)
            for level, v in item['lcd_variants'].items():
                data = json.loads((assets/Path(v['fallback']).name).read_text())
                self.assertEqual(len(data['frames']), data['fps'])
                self.assertAlmostEqual(data['cols']/data['rows'], 4/3, delta=.03)
                self.assertEqual(data['subtitles'][0]['text'], 'A signal.')
                self.assertTrue(all(len(f) == ((data['cols']*data['rows']+7)//8)*2 for f in data['frames']))

if __name__ == '__main__': unittest.main()
