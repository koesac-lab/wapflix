import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ascii_tuning_lab as lab


def test_presets_are_valid():
    presets = lab.load_presets(ROOT / "tools" / "ascii_presets.json")
    assert {"baseline-current", "corrected-polarity", "wide-80", "subject-crop"} <= set(presets)


def test_inverted_polarity_maps_black_to_dense_glyph():
    preset = lab.load_presets(ROOT / "tools" / "ascii_presets.json")["corrected-polarity"]
    assert lab.tone_map(0.0, preset) > lab.tone_map(1.0, preset)


def test_non_inverted_polarity_maps_white_to_dense_glyph():
    preset = dict(lab.load_presets(ROOT / "tools" / "ascii_presets.json")["baseline-current"])
    assert lab.tone_map(1.0, preset) > lab.tone_map(0.0, preset)


def test_ascii_output_uses_requested_grid():
    preset = lab.load_presets(ROOT / "tools" / "ascii_presets.json")["corrected-polarity"]
    values = [[0.25, 0.5, 0.75] for _ in range(4)]
    output = lab.to_ascii(values, preset)
    assert len(output) == 4
    assert all(len(row) == 3 for row in output)


def test_calibration_strip_is_not_blank():
    preset = lab.load_presets(ROOT / "tools" / "ascii_presets.json")["corrected-polarity"]
    strip = lab.calibration_strip(preset)
    assert strip and len(strip[0]) == 40
    assert len(set(strip[0])) > 1


def test_invalid_preset_is_rejected():
    with pytest.raises(lab.LabError):
        lab.validate_preset("bad", {"columns": 41})


def test_missing_video_is_rejected(tmp_path):
    with pytest.raises(lab.LabError):
        lab.probe_video(tmp_path / "missing.mp4", "ffprobe")


def test_cli_reports_missing_video(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ascii_tuning_lab.py"),
         "--video", str(tmp_path / "missing.mp4")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "Error:" in result.stderr
