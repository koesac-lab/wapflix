import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_converts_and_rebases_cues(tmp_path):
    source = tmp_path / "sample.srt"
    source.write_text(SRT, encoding="utf-8")
    result = clip.clip_subtitles(source, 30.0, 15.0)
    assert result == [
        {"start": 0.5, "end": 1.8, "text": "Hello caption"},
        {"start": 2.0, "end": 3.0, "text": "Second caption"},
    ]


def test_excludes_cues_outside_clip(tmp_path):
    source = tmp_path / "sample.srt"
    source.write_text(SRT, encoding="utf-8")
    result = clip.clip_subtitles(source, 55.0, 5.0)
    assert result == []


def test_cli_writes_json(tmp_path):
    source = tmp_path / "sample.srt"
    source.write_text(SRT, encoding="utf-8")
    output = tmp_path / "subtitles.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "make_clip_subtitles.py"),
         str(source), "--start", "30", "--seconds", "15", "--output", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["text"] == "Hello caption"


def test_cli_rejects_invalid_duration(tmp_path):
    source = tmp_path / "sample.srt"
    source.write_text(SRT, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "make_clip_subtitles.py"),
         str(source), "--start", "30", "--seconds", "0", "--output", str(tmp_path / "out.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "Error:" in result.stderr
