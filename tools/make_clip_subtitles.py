#!/usr/bin/env python3
"""Convert an SRT file into clip-relative subtitle JSON for WAPFLIX static assets.

This tool does not download, store, or redistribute media. It reads a local
SRT file and writes a small JSON array suitable for tools/build.py --subtitles.

Example:
  python3 tools/make_clip_subtitles.py source.srt \
    --start 30 --seconds 15 --output subtitles.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import srt


def clip_subtitles(path: Path, start: float, seconds: float) -> list[dict]:
    if start < 0:
        raise ValueError("start must be non-negative")
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    parsed = srt.parse_srt(path)
    cues = srt.cues_for_window(parsed, start, start + seconds)
    return [
        {"start": round(cue.start, 3), "end": round(cue.end, 3), "text": cue.text}
        for cue in cues
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("srt", type=Path)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        subtitles = clip_subtitles(args.srt, args.start, args.seconds)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(subtitles, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(subtitles)} subtitle cue(s) to {args.output}")
        return 0
    except (ValueError, srt.SubtitleError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
