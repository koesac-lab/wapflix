#!/usr/bin/env python3
"""Bounded offline MP4/SRT diagnostic; never modifies the Pages catalogue."""
import argparse
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from srt import parse_srt

RAMP = " .,:;irsXA253hMHGS#9B&@"
TABLE = bytes(ord(RAMP[value * (len(RAMP) - 1) // 255]) for value in range(256))

def handset_rows(columns, width, height):
    if not 2 <= columns <= 120 or not all(math.isfinite(x) and x > 0 for x in (width, height)):
        raise ValueError("invalid geometry")
    rows = max(2, round(columns * 6 * height / (8 * width)))
    if rows > 160:
        raise ValueError("aspect ratio exceeds 160-row limit")
    return rows

def brightness_to_ascii(data, columns, rows):
    if columns <= 0 or rows <= 0 or len(data) != columns * rows:
        raise ValueError("grayscale frame size mismatch")
    text = data.translate(TABLE).decode("ascii")
    return "\n".join(text[n:n + columns] for n in range(0, len(text), columns))

def validate_options(start, seconds, columns, fps):
    if not math.isfinite(start) or start < 0:
        raise ValueError("start must be finite and non-negative")
    if not math.isfinite(seconds) or not 0 < seconds <= 120:
        raise ValueError("seconds must be greater than 0 and at most 120")
    if not 2 <= columns <= 120 or not 1 <= fps <= 24:
        raise ValueError("columns must be 2-120; fps must be 1-24")

def run_tool(command, timeout=30):
    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=log,
                                    timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"{command[0]} timed out after {timeout}s") from error
        if result.returncode:
            log.seek(0, 2)
            size = log.tell()
            log.seek(max(0, size - 4096))
            raise RuntimeError(f"{command[0]} failed: " + log.read().decode(errors="replace"))
        return result.stdout

def probe_source(video):
    data = json.loads(run_tool([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=codec_name,width,height,sample_aspect_ratio,avg_frame_rate,pix_fmt:"
        "stream_tags=rotate:stream_side_data=rotation:format=duration,size,format_name",
        "-of", "json", str(video.resolve())]))
    if not data.get("streams"):
        raise ValueError("no video stream found")
    stream = data["streams"][0]
    width, height = float(stream["width"]), float(stream["height"])
    sar = stream.get("sample_aspect_ratio", "1:1")
    if sar not in (None, "N/A", "0:1"):
        numerator, denominator = map(int, sar.split(":"))
        if numerator > 0 and denominator > 0:
            width *= numerator / denominator
    rotation = float(stream.get("tags", {}).get("rotate", 0))
    for side in stream.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation))
    if not math.isfinite(rotation) or abs(rotation / 90 - round(rotation / 90)) > .001:
        raise ValueError("only right-angle rotation is supported")
    if round(rotation) % 180:
        width, height = height, width
    return {"codec": stream.get("codec_name"), "width": stream["width"], "height": stream["height"],
            "display_width": width, "display_height": height, "rotation": rotation,
            "sample_aspect_ratio": sar, "pixel_format": stream.get("pix_fmt"),
            "frame_rate": stream.get("avg_frame_rate"),
            "duration": data.get("format", {}).get("duration")}

def convert_segment(video, start=0, seconds=30, columns=40, fps=6):
    validate_options(start, seconds, columns, fps)
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} is required on PATH")
    if not video.is_file():
        raise ValueError("video is not a file")
    probe = probe_source(video)
    rows = handset_rows(columns, probe["display_width"], probe["display_height"])
    count_limit = math.ceil(seconds * fps)
    if columns * rows * count_limit > 16 * 1024 * 1024:
        raise ValueError("request exceeds 16 MiB raw-frame limit")
    started = time.perf_counter()
    raw = run_tool([
        "ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", str(video.resolve()),
        "-t", str(seconds), "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", f"fps={fps},scale={columns}:{rows}:flags=area,setsar=1",
        "-frames:v", str(count_limit), "-threads:v", "1", "-f", "rawvideo",
        "-pix_fmt", "gray", "pipe:1"], timeout=300)
    size = columns * rows
    if not raw or len(raw) % size:
        raise ValueError("no frames or incomplete grayscale frame")
    frames = [brightness_to_ascii(raw[n:n + size], columns, rows) for n in range(0, len(raw), size)]
    conversion_seconds = time.perf_counter() - started
    packed_started = time.perf_counter()
    packed_bytes = 0
    for offset in range(0, len(frames), fps * 2):
        chunk = {"version": 1, "start_frame": offset, "cols": columns, "rows": rows,
                 "fps": fps, "frames": frames[offset:offset + fps * 2]}
        packed_bytes += len(gzip.compress(json.dumps(chunk, separators=(",", ":")).encode(),
                                          compresslevel=6, mtime=0))
    packing_seconds = time.perf_counter() - packed_started
    duration = len(frames) / fps
    return frames, {**probe, "decoder": "software", "columns": columns, "rows": rows,
                    "fps": fps, "start_seconds": start, "requested_seconds": seconds,
                    "converted_seconds": duration, "frame_count": len(frames),
                    "conversion_seconds": conversion_seconds, "packing_seconds": packing_seconds,
                    "media_seconds_per_wall_second": duration / (conversion_seconds + packing_seconds),
                    "compressed_chunk_bytes": packed_bytes, "chunk_seconds": 2, "gzip_level": 6,
                    "compressed_bytes_per_media_second": packed_bytes / duration}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--subtitles", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--columns", type=int, default=40)
    parser.add_argument("--fps", type=int, default=6)
    args = parser.parse_args()
    validate_options(args.start, args.seconds, args.columns, args.fps)
    inputs = {path.resolve() for path in (args.video, args.subtitles) if path}
    outputs = [path.resolve() for path in (args.report, args.preview) if path]
    if any(path in inputs for path in outputs) or len(set(outputs)) != len(outputs):
        raise ValueError("output paths must be distinct and must not overwrite inputs")
    if any(path.exists() for path in outputs):
        raise ValueError("output already exists; choose new report and preview paths")
    subtitles = parse_srt(args.subtitles) if args.subtitles else None
    frames, metrics = convert_segment(args.video, args.start, args.seconds, args.columns, args.fps)
    cues = subtitles.cues if subtitles else []
    selected = [cue for cue in cues if cue.start < args.start + metrics["converted_seconds"] and cue.end > args.start]
    report = {"version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "host": {"platform": platform.platform(), "python": platform.python_version(),
                       "ffmpeg": run_tool(["ffmpeg", "-version"]).decode(errors="replace").splitlines()[0]},
              "profile": {"columns": metrics["columns"], "rows": metrics["rows"], "fps": metrics["fps"],
                          "cell_width": 6, "cell_height": 8},
              "benchmark": metrics,
              "subtitles": {"cue_count": len(cues), "cues_overlapping_segment": len(selected),
                            "encoding": subtitles.encoding if subtitles else None,
                            "errors": subtitles.errors if subtitles else []},
              "limitations": ["Offline short segment retained in memory; not progressive playback.",
                              "Timing excludes probing, subtitle parsing and report writes.",
                              "No CPU/RSS, first-chunk latency, hardware decode or browser validation."]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        with args.preview.open("x", encoding="utf-8") as handle:
            handle.write(frames[0] + "\n")
    print(json.dumps({"frames": len(frames), "converted_seconds": metrics["converted_seconds"],
                      "media_seconds_per_wall_second": round(metrics["media_seconds_per_wall_second"], 3),
                      "compressed_kib_per_media_second": round(metrics["compressed_bytes_per_media_second"] / 1024, 3),
                      "subtitle_errors": len(subtitles.errors) if subtitles else 0}))

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"diagnostic failed: {error}", file=sys.stderr)
        raise SystemExit(2)
