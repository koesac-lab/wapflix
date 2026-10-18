import sys
from pathlib import Path

import pytest

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


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_valid_cues(tmp_path):
    result = srt.parse_srt(write(tmp_path, "sample.srt", SRT))
    assert len(result.cues) == 2
    assert result.cues[0].start == 1.0
    assert result.cues[0].text == "Hello"
    assert result.errors == ()


def test_reports_but_survives_invalid_cue(tmp_path):
    result = srt.parse_srt(write(tmp_path, "mixed.srt", BAD_SRT))
    assert len(result.cues) == 1
    assert len(result.errors) == 1
    assert "cue 1" in result.errors[0]


def test_window_selection_rebases_times(tmp_path):
    result = srt.parse_srt(write(tmp_path, "sample.srt", SRT))
    cues = srt.cues_for_window(result, 2.0, 4.0)
    assert len(cues) == 2
    assert cues[0].start == 0.0
    assert cues[0].end == pytest.approx(0.5)
    assert cues[1].start == pytest.approx(1.0)
    assert cues[1].end == pytest.approx(2.0)


def test_window_excludes_non_overlapping_cues(tmp_path):
    result = srt.parse_srt(write(tmp_path, "sample.srt", SRT))
    assert srt.cues_for_window(result, 10.0, 12.0) == ()


def test_invalid_window_is_rejected(tmp_path):
    result = srt.parse_srt(write(tmp_path, "sample.srt", SRT))
    with pytest.raises(srt.SubtitleError):
        srt.cues_for_window(result, 4.0, 2.0)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(srt.SubtitleError):
        srt.parse_srt(tmp_path / "missing.srt")
