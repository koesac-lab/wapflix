# Local video diagnostic

Python 3.10+, ffmpeg and ffprobe on PATH; no pip dependencies. This adds an
offline short-segment diagnostic, not Docker, Plex integration or a server.
The Pages workflow, catalogue, navigation, themes and player are unchanged.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

FFmpeg integration tests explicitly skip if the tools are missing. Existing
repository tests are separate from this package's isolated verification.

## Download the agreed test fixture

The following Bash block runs from the repository root. Media stays outside Git.
It selects video-only H.264 MP4 up to 720p; audio is not used by the diagnostic.
Captions are optional and failure does not block the video test.

```bash
bash <<'BASH'
set -euo pipefail
TEST_DIR="$HOME/.local/share/wapflix/test-media/dQw4w9WgXcQ"
URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
mkdir -p "$TEST_DIR"
yt-dlp --ignore-config --no-playlist --no-overwrites \
  -f 'bv[ext=mp4][vcodec^=avc1][height<=720]/b[ext=mp4][vcodec^=avc1][height<=720]' \
  -o "$TEST_DIR/source.%(ext)s" "$URL"
if ! yt-dlp --ignore-config --no-playlist --skip-download --write-subs \
  --write-auto-subs --sub-langs en --sub-format 'vtt/best' --convert-subs srt \
  -o "$TEST_DIR/source.%(ext)s" "$URL"; then
  echo "Caption download failed; continuing without captions if necessary."
fi
SRT=$(find "$TEST_DIR" -maxdepth 1 -type f -name 'source*.srt' -print -quit)
SUB_ARGS=()
if [ -n "$SRT" ]; then SUB_ARGS=(--subtitles "$SRT"); fi
RUN_DIR=$(mktemp -d "$TEST_DIR/run.XXXXXX")
python3 tools/diagnose.py --video "$TEST_DIR/source.mp4" "${SUB_ARGS[@]}" \
  --start 30 --seconds 60 --report "$RUN_DIR/report.json" --preview "$RUN_DIR/preview.txt"
printf '\nReport: %s\nPreview: %s\n' "$RUN_DIR/report.json" "$RUN_DIR/preview.txt"
BASH
```

Download availability and yt-dlp's extractor requirements are not guaranteed.
No network download was performed in the package build environment. If it fails,
retain the error rather than silently choosing a different codec. The home
folder may not be on the USB HDD: repeat later with representative HDD media.

## Use your own local media

```sh
python3 tools/diagnose.py --video "/path/to/episode.mp4" \
  --subtitles "/path/to/episode.srt" --start 120 --seconds 60 \
  --report /tmp/wapflix-report-1.json --preview /tmp/wapflix-preview-1.txt
```

Omit --subtitles when absent. Output paths must be new, distinct and not inputs.
Defaults: 40 columns, 6 fps, aspect-correct rows for 6x8 cells (17 for 16:9).
The optional preview is a single frame, not playable video or a subtitle test.

## Interpretation and limits

media_seconds_per_wall_second measures segment duration divided by decode,
ASCII mapping and independent two-second JSON/gzip packing time. About 2x is
an initial headroom target, not a real-time playback guarantee. Below 1x will
require a cheaper profile or advance conversion for sustained playback.
compressed_kib_per_media_second excludes HTTP, subtitles and page overhead.

Reports include codec, resolution, pixel format, profile, subtitle counts and
errors, Python/FFmpeg versions and the timings. Source filenames/paths and cue
text are omitted, but reports still contain host/media details; review before
sharing. Do not commit downloaded video, subtitles, reports or previews.

Limits: at most 120 seconds, 2-120 columns, 1-24 fps, 160 rows and 16 MiB raw
frames, with a 300-second FFmpeg timeout. This diagnostic buffers the segment
in memory; it does not implement the planned progressive chunk pipeline.
No first-chunk latency, CPU/RSS, hardware decode, browser or live Pages tests.
Timing excludes probing, subtitle parsing, version lookup and output writes.
SRT times remain episode-relative; UTF-8/BOM, UTF-16/BOM and CP1252 fallback
are supported. Malformed cues are reported; overlapping cues are retained.
See BUILD_PLAN.md for the remaining streaming and Plex milestones.
