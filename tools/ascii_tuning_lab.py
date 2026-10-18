#!/usr/bin/env python3
"""Local ASCII legibility tuning lab for WAPFLIX.

This is an offline comparison tool. It does not modify the deployed WAPFLIX
site, the progressive playback server, or any committed scene assets.

Usage:
  python3 tools/ascii_tuning_lab.py --video path/to/video.mp4 --preset corrected-polarity
  python3 tools/ascii_tuning_lab.py --video video.mp4 --srt video.srt --start 30 --seconds 15
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import srt

PRESETS_PATH = Path(__file__).with_name("ascii_presets.json")
MAX_PREVIEW_FRAMES = 240
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_PREVIEW_SECONDS = 30


class LabError(ValueError):
    """Raised for invalid user input or an unusable media file."""


def load_presets(path: Path = PRESETS_PATH) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LabError(f"Could not read presets: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise LabError("Presets file must contain a non-empty object")
    for name, preset in data.items():
        validate_preset(name, preset)
    return data


def validate_preset(name: str, preset: object) -> None:
    if not isinstance(name, str) or not name.strip():
        raise LabError("Preset names must be non-empty strings")
    if not isinstance(preset, dict):
        raise LabError(f"Preset {name!r} must be an object")
    columns = preset.get("columns")
    if type(columns) is not int or columns not in (40, 60, 80, 96):
        raise LabError(f"Preset {name!r} has an unsupported column count")
    fps = preset.get("fps")
    if type(fps) is not int or fps not in (6, 8, 12):
        raise LabError(f"Preset {name!r} has an unsupported frame rate")
    levels = preset.get("levels")
    if type(levels) is not int or not 2 <= levels <= 16:
        raise LabError(f"Preset {name!r} has an invalid level count")
    ramp = preset.get("ramp")
    if not isinstance(ramp, str) or len(set(ramp)) != len(ramp) or len(ramp) < levels:
        raise LabError(f"Preset {name!r} needs at least {levels} unique ramp characters")
    for key in ("brightness", "contrast", "gamma", "black_point", "white_point"):
        value = preset.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise LabError(f"Preset {name!r} has invalid {key}")
    if preset["contrast"] <= 0 or preset["gamma"] <= 0:
        raise LabError(f"Preset {name!r} contrast and gamma must be positive")
    if not 0 <= preset["black_point"] < preset["white_point"] <= 1:
        raise LabError(f"Preset {name!r} has invalid black/white points")
    if not isinstance(preset.get("invert"), bool):
        raise LabError(f"Preset {name!r} invert must be boolean")
    if preset.get("crop") not in ("none", "centre"):
        raise LabError(f"Preset {name!r} has an unsupported crop mode")
    if preset["crop"] == "centre":
        for key in ("crop_width", "crop_height"):
            value = preset.get(key)
            if not isinstance(value, (int, float)) or not 0.1 <= value <= 1.0:
                raise LabError(f"Preset {name!r} has invalid {key}")


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise LabError(f"Required tool not found: {name}")
    return executable


def probe_video(video: Path, ffprobe: str) -> dict:
    if not video.is_file():
        raise LabError(f"Video not found: {video}")
    if video.stat().st_size > MAX_FILE_BYTES:
        raise LabError("Video is too large for the local tuning lab")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "json", str(video)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise LabError("ffprobe could not read the video")
    try:
        stream = json.loads(result.stdout)["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        duration = float(stream.get("duration") or 0)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LabError("Could not determine video dimensions") from exc
    if width <= 0 or height <= 0 or duration <= 0:
        raise LabError("Video has no usable video stream")
    return {"width": width, "height": height, "duration": duration}


def rows_for_columns(columns: int, width: int, height: int) -> int:
    rows = max(2, round(columns * height / (2 * width)))
    if rows > 120:
        raise LabError("Derived row count is too large for legible preview output")
    return rows


def extract_frame(video: Path, start: float, ffmpeg: str, columns: int, rows: int,
                  preset: dict, output: Path) -> None:
    filters = []
    if preset["crop"] == "centre":
        crop_w = max(16, int(preset["crop_width"] * 1000))
        crop_h = max(16, int(preset["crop_height"] * 1000))
        filters.append(f"crop=iw*{crop_w}/1000:ih*{crop_h}/1000")
    filters.extend([
        f"scale={columns}:{rows}:flags=area",
        "format=gray",
        f"eq=brightness={preset['brightness']}:contrast={preset['contrast']}:gamma={preset['gamma']}",
        "normalize=blackpt=black:whitept=white:smoothing=0",
    ])
    command = [
        ffmpeg, "-nostdin", "-v", "error",
        "-ss", f"{start:.3f}", "-i", str(video),
        "-frames:v", "1", "-vf", ",".join(filters),
        "-update", "1", "-y", str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode or not output.is_file():
        raise LabError("Could not extract the requested frame")


def tone_map(value: float, preset: dict) -> float:
    value = (value - preset["black_point"]) / max(1e-6, preset["white_point"] - preset["black_point"])
    value = min(1.0, max(0.0, value))
    value = value ** (1.0 / preset["gamma"])
    value = (value - 0.5) * preset["contrast"] + 0.5 + preset["brightness"]
    value = min(1.0, max(0.0, value))
    return 1.0 - value if preset["invert"] else value


def to_ascii(gray_values: list[list[float]], preset: dict) -> list[str]:
    ramp = preset["ramp"]
    levels = preset["levels"]
    step = (len(ramp) - 1) / max(1, levels - 1)
    output = []
    for row in gray_values:
        line = []
        for value in row:
            mapped = tone_map(value, preset)
            index = round(mapped * (levels - 1)) * round(step)
            line.append(ramp[min(len(ramp) - 1, index)])
        output.append("".join(line))
    return output


def calibration_strip(preset: dict, columns: int = 40) -> list[str]:
    values = [[i / max(1, columns - 1) for i in range(columns)]]
    return to_ascii(values, preset)


def active_cue(cues: tuple[srt.SubtitleCue, ...], position: float) -> str | None:
    for cue in cues:
        if cue.start <= position < cue.end:
            return cue.text
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="Local video file")
    parser.add_argument("--srt", type=Path, help="Optional local SRT subtitle file")
    parser.add_argument("--preset", default="corrected-polarity")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--seconds", type=float, help="Preview duration; defaults to frames divided by preset FPS")
    parser.add_argument("--frames", type=int, default=1)
    parser.add_argument("--presets", type=Path, default=PRESETS_PATH)
    parser.add_argument("--output-dir", type=Path, default=Path("output/ascii-lab"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        presets = load_presets(args.presets)
        if args.preset not in presets:
            raise LabError(f"Unknown preset: {args.preset}")
        preset = presets[args.preset]
        if type(args.frames) is not int or not 1 <= args.frames <= MAX_PREVIEW_FRAMES:
            raise LabError("Frame count must be between 1 and 240")
        if not math.isfinite(args.start) or args.start < 0:
            raise LabError("Start time must be non-negative")
        seconds = args.seconds if args.seconds is not None else args.frames / preset["fps"]
        if not math.isfinite(seconds) or not 0 < seconds <= MAX_PREVIEW_SECONDS:
            raise LabError(f"Preview duration must be between 0 and {MAX_PREVIEW_SECONDS} seconds")
        expected_frames = max(1, min(MAX_PREVIEW_FRAMES, math.ceil(seconds * preset["fps"])))
        if args.frames != expected_frames:
            raise LabError(f"--frames must be {expected_frames} for a {seconds:g}-second preview at {preset['fps']} fps")
        subtitles = None
        if args.srt is not None:
            subtitles = srt.parse_srt(args.srt)
            cues = srt.cues_for_window(subtitles, args.start, args.start + seconds)
        else:
            cues = ()
        ffmpeg, ffprobe = require_tool("ffmpeg"), require_tool("ffprobe")
        info = probe_video(args.video.resolve(), ffprobe)
        if args.start + seconds > info["duration"]:
            raise LabError("Requested preview extends beyond the end of the video")
        rows = rows_for_columns(preset["columns"], info["width"], info["height"])
        args.output_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": 1,
            "video": str(args.video.resolve()),
            "srt": str(args.srt.resolve()) if args.srt else None,
            "preset": args.preset,
            "start": args.start,
            "seconds": seconds,
            "fps": preset["fps"],
            "columns": preset["columns"],
            "rows": rows,
            "frames": [],
            "subtitle_errors": list(subtitles.errors) if subtitles else [],
        }
        with tempfile.TemporaryDirectory(prefix="wapflix-ascii-lab-") as temporary:
            frame_path = Path(temporary) / "frame.png"
            for index in range(args.frames):
                source_time = args.start + index / preset["fps"]
                extract_frame(args.video, source_time, ffmpeg,
                              preset["columns"], rows, preset, frame_path)
                destination = args.output_dir / f"frame-{index:04d}.png"
                shutil.copyfile(frame_path, destination)
                cue = active_cue(cues, index / preset["fps"])
                text_path = args.output_dir / f"frame-{index:04d}.txt"
                text_path.write_text((cue or ""), encoding="utf-8")
                manifest["frames"].append({
                    "file": destination.name,
                    "source_time": source_time,
                    "preview_time": index / preset["fps"],
                    "cue": cue,
                })
        manifest_path = args.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        strip = calibration_strip(preset)
        print(f"Preset: {args.preset}")
        print(f"Grid: {preset['columns']} x {rows}")
        print(f"Preview: {args.start:.3f}s for {seconds:.3f}s")
        print(f"Frames written: {args.frames}")
        print(f"Subtitles: {len(cues)} overlapping cue(s)")
        if subtitles and subtitles.errors:
            print(f"Subtitle warnings: {len(subtitles.errors)}")
        print(f"Output: {args.output_dir}")
        print("Calibration strip:")
        print("\n".join(strip))
        return 0
    except (LabError, srt.SubtitleError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
