import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ascii_tuning_lab as lab
import srt


SRT = """1
00:00:30,500 --> 00:00:31,800
Hello caption

2
00:00:32,000 --> 00:00:33,000
Second caption
"""


class AsciiSrtIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def test_srt_window_is_rebased_for_preview(self):
        source = self.path / "sample.srt"
        source.write_text(SRT, encoding="utf-8")
        result = srt.parse_srt(source)
        cues = srt.cues_for_window(result, 30.0, 45.0)
        self.assertEqual(len(cues), 2)
        self.assertAlmostEqual(cues[0].start, 0.5)
        self.assertEqual(cues[0].text, "Hello caption")
        self.assertAlmostEqual(cues[1].start, 2.0)

    def test_active_cue_finds_current_text(self):
        cue = srt.SubtitleCue(0.5, 1.8, "Hello caption")
        self.assertEqual(lab.active_cue((cue,), 1.0), "Hello caption")
        self.assertIsNone(lab.active_cue((cue,), 2.0))

    def test_cli_accepts_srt_and_seconds(self):
        video = self.path / "video.mp4"
        video.write_bytes(b"not a real video")
        subtitle = self.path / "video.srt"
        subtitle.write_text(SRT, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ascii_tuning_lab.py"),
             "--video", str(video), "--srt", str(subtitle),
             "--start", "30", "--seconds", "15", "--frames", "4"],
            capture_output=True, text=True,
        )
        self.assertNotIn("--srt", result.stderr)
        self.assertNotIn("unrecognized arguments", result.stderr)

    def test_cli_rejects_mismatched_frame_count(self):
        video = self.path / "video.mp4"
        video.write_bytes(b"not a real video")
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ascii_tuning_lab.py"),
             "--video", str(video), "--start", "30", "--seconds", "15", "--frames", "4"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--frames must be", result.stderr)


if __name__ == "__main__":
    unittest.main()
