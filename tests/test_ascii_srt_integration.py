import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_srt_window_is_rebased_for_preview(tmp_path):
    path = tmp_path / "sample.srt"
    path.write_text(SRT, encoding="utf-8")
    result = srt.parse_srt(path)
    cues = srt.cues_for_window(result, 30.0, 45.0)
    assert len(cues) == 2
    assert cues[0].start == pytest.approx(0.5)
    assert cues[0].text == "Hello caption"
    assert cues[1].start == pytest.approx(2.0)


def test_active_cue_finds_current_text():
    cue = srt.SubtitleCue(0.5, 1.8, "Hello caption")
    assert lab.active_cue((cue,), 1.0) == "Hello caption"
    assert lab.active_cue((cue,), 2.0) is None


def test_cli_accepts_srt_and_seconds(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not a real video")
    subtitle = tmp_path / "video.srt"
    subtitle.write_text(SRT, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ascii_tuning_lab.py"),
         "--video", str(video), "--srt", str(subtitle),
         "--start", "30", "--seconds", "15", "--frames", "4"],
        capture_output=True, text=True,
    )
    assert "--srt" not in result.stderr
    assert "unrecognized arguments" not in result.stderr


def test_cli_rejects_mismatched_frame_count(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not a real video")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ascii_tuning_lab.py"),
         "--video", str(video), "--start", "30", "--seconds", "15", "--frames", "4"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "--frames must be" in result.stderr
