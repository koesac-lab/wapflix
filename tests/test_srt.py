import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import srt


SRT = """1
00:00:01,000 --> 00:00:02,500
Hello

2
00:00:03,000 --> 00:00:04,000
Second line
"""

BAD_SRT = """1
00:00:05,000 --> 00:00:04,000
Backwards

2
00:00:06,000 --> 00:00:07,000
Good
"""


class SrtTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def write(self, name, content):
        target = self.path / name
        target.write_text(content, encoding="utf-8")
        return target

    def test_parses_valid_cues(self):
        result = srt.parse_srt(self.write("sample.srt", SRT))
        self.assertEqual(len(result.cues), 2)
        self.assertEqual(result.cues[0].start, 1.0)
        self.assertEqual(result.cues[0].text, "Hello")
        self.assertEqual(result.errors, ())

    def test_reports_but_survives_invalid_cue(self):
        result = srt.parse_srt(self.write("mixed.srt", BAD_SRT))
        self.assertEqual(len(result.cues), 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("cue 1", result.errors[0])

    def test_window_selection_rebases_times(self):
        result = srt.parse_srt(self.write("sample.srt", SRT))
        cues = srt.cues_for_window(result, 2.0, 4.0)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0].start, 0.0)
        self.assertAlmostEqual(cues[0].end, 0.5)
        self.assertAlmostEqual(cues[1].start, 1.0)
        self.assertAlmostEqual(cues[1].end, 2.0)

    def test_window_excludes_non_overlapping_cues(self):
        result = srt.parse_srt(self.write("sample.srt", SRT))
        self.assertEqual(srt.cues_for_window(result, 10.0, 12.0), ())

    def test_invalid_window_is_rejected(self):
        result = srt.parse_srt(self.write("sample.srt", SRT))
        with self.assertRaises(srt.SubtitleError):
            srt.cues_for_window(result, 4.0, 2.0)

    def test_missing_file_is_rejected(self):
        with self.assertRaises(srt.SubtitleError):
            srt.parse_srt(self.path / "missing.srt")


if __name__ == "__main__":
    unittest.main()
