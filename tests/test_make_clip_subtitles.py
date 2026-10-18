import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_clip_subtitles as clip


SRT = """1
00:00:30,500 --> 00:00:31,800
Hello caption

2
00:00:32,000 --> 00:00:33,000
Second caption

3
00:01:00,000 --> 00:01:01,000
Outside window
"""


class MakeClipSubtitlesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def write_srt(self):
        source = self.path / "sample.srt"
        source.write_text(SRT, encoding="utf-8")
        return source

    def test_converts_and_rebases_cues(self):
        source = self.write_srt()
        result = clip.clip_subtitles(source, 30.0, 15.0)
        self.assertEqual(result, [
            {"start": 0.5, "end": 1.8, "text": "Hello caption"},
            {"start": 2.0, "end": 3.0, "text": "Second caption"},
        ])

    def test_excludes_cues_outside_clip(self):
        source = self.write_srt()
        result = clip.clip_subtitles(source, 55.0, 5.0)
        self.assertEqual(result, [])

    def test_cli_writes_json(self):
        source = self.write_srt()
        output = self.path / "subtitles.json"
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "make_clip_subtitles.py"),
             str(source), "--start", "30", "--seconds", "15",
             "--output", str(output)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["text"], "Hello caption")

    def test_cli_rejects_invalid_duration(self):
        source = self.write_srt()
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "make_clip_subtitles.py"),
             str(source), "--start", "30", "--seconds", "0",
             "--output", str(self.path / "out.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
