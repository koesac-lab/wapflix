import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diagnose import brightness_to_ascii, convert_segment, handset_rows, probe_source, run_tool, validate_options

class DiagnoseTests(unittest.TestCase):
    def test_geometry(self):
        self.assertEqual(handset_rows(40, 16, 9), 17)
        self.assertEqual(handset_rows(40, 4, 3), 22)
    def test_bad_geometry(self):
        for values in ((0, 16, 9), (40, 0, 9), (40, float("nan"), 9), (40, 1, 1000)):
            with self.assertRaises(ValueError):
                handset_rows(*values)
    def test_frame_mapping(self):
        self.assertEqual(brightness_to_ascii(bytes([0, 128, 255, 64]), 2, 2), " 5\n@i")
        with self.assertRaises(ValueError):
            brightness_to_ascii(b"abc", 2, 2)
    def test_option_limits(self):
        for values in ((-1, 30, 40, 6), (0, 121, 40, 6), (0, 1, 40, 0), (float("nan"), 1, 40, 6)):
            with self.assertRaises(ValueError):
                validate_options(*values)
    def test_probe_rotation_and_aspect(self):
        value = {"streams": [{"width": 720, "height": 576, "sample_aspect_ratio": "16:15", "side_data_list": [{"rotation": 90}]}]}
        with patch("diagnose.run_tool", return_value=json.dumps(value).encode()):
            result = probe_source(Path("example.mp4"))
        self.assertEqual((result["display_width"], result["display_height"]), (576, 768))
    def test_process_errors(self):
        with self.assertRaises(RuntimeError):
            run_tool([sys.executable, "-c", "import time; time.sleep(3)"], .05)
        with self.assertRaises(RuntimeError):
            run_tool([sys.executable, "-c", "raise SystemExit(3)"], 3)

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools missing")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.video = cls.folder / "sample.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=160x90:rate=12:duration=2", "-an", "-c:v", "mpeg4", "-threads", "1", str(cls.video)],
                       check=True, capture_output=True, timeout=30)
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    def test_real_conversion(self):
        frames, report = convert_segment(self.video, seconds=1)
        self.assertEqual(len(frames), 6)
        self.assertTrue(all(len(frame.splitlines()) == 17 for frame in frames))
        self.assertTrue(all(len(line) == 40 for frame in frames for line in frame.splitlines()))
        self.assertGreater(report["compressed_chunk_bytes"], 0)
    def test_past_eof(self):
        with self.assertRaises(ValueError):
            convert_segment(self.video, start=99, seconds=1)
    def test_cli_and_overwrite_protection(self):
        script = Path(__file__).resolve().parents[1] / "tools/diagnose.py"
        report, preview = self.folder / "report.json", self.folder / "preview.txt"
        args = [sys.executable, str(script), "--video", str(self.video), "--seconds", "1", "--report", str(report), "--preview", str(preview)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(report.read_text())["benchmark"]["frame_count"], 6)
        self.assertEqual(len(preview.read_text().splitlines()), 17)
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2)
        before = self.video.read_bytes()
        result = subprocess.run([sys.executable, str(script), "--video", str(self.video), "--report", str(self.video)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.video.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
