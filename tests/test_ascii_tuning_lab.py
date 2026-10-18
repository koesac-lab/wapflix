import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ascii_tuning_lab as lab


class AsciiTuningLabTests(unittest.TestCase):
    def test_presets_are_valid(self):
        presets = lab.load_presets(ROOT / "tools" / "ascii_presets.json")
        self.assertLessEqual(
            {"baseline-current", "corrected-polarity", "wide-80", "subject-crop"},
            set(presets),
        )

    def test_inverted_polarity_maps_black_to_dense_glyph(self):
        preset = lab.load_presets(ROOT / "tools" / "ascii_presets.json")["corrected-polarity"]
        self.assertGreater(lab.tone_map(0.0, preset), lab.tone_map(1.0, preset))

    def test_non_inverted_polarity_maps_white_to_dense_glyph(self):
        preset = dict(lab.load_presets(ROOT / "tools" / "ascii_presets.json")["baseline-current"])
        self.assertGreater(lab.tone_map(1.0, preset), lab.tone_map(0.0, preset))

    def test_ascii_output_uses_requested_grid(self):
        preset = lab.load_presets(ROOT / "tools" / "ascii_presets.json")["corrected-polarity"]
        values = [[0.25, 0.5, 0.75] for _ in range(4)]
        output = lab.to_ascii(values, preset)
        self.assertEqual(len(output), 4)
        self.assertTrue(all(len(row) == 3 for row in output))

    def test_calibration_strip_is_not_blank(self):
        preset = lab.load_presets(ROOT / "tools" / "ascii_presets.json")["corrected-polarity"]
        strip = lab.calibration_strip(preset)
        self.assertTrue(strip)
        self.assertEqual(len(strip[0]), 40)
        self.assertGreater(len(set(strip[0])), 1)

    def test_invalid_preset_is_rejected(self):
        with self.assertRaises(lab.LabError):
            lab.validate_preset("bad", {"columns": 41})

    def test_missing_video_is_rejected(self):
        with self.assertRaises(lab.LabError):
            lab.probe_video(Path("/nonexistent/video.mp4"), "ffprobe")

    def test_cli_reports_missing_video(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ascii_tuning_lab.py"),
             "--video", "/nonexistent/video.mp4"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
