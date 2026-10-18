# WAPFLIX — cinema, reduced

An ASCII cinema artwork for an alternative 1999. Static, dependency-free browser player; three original silent procedural studies; real compressed text-frame assets; offline video conversion.

## GitHub Pages

The included workflow generates the demo assets and deploys on pushes to main. It attempts to enable Pages automatically. If repository policy prevents this, choose Settings → Pages → Source: GitHub Actions, then rerun Publish WAPFLIX. A successful deployment is required before the site is live.

## Local preview

Python 3.9+ is required; demo generation needs no third-party packages.

```sh
python3 tools/build.py
python3 -m http.server 8000
```

Open http://localhost:8000. Do not open index.html directly as a file. For branch-based Pages hosting, generate and commit assets first, then choose main / root instead of the workflow.

## Convert your footage

Install FFmpeg, including ffprobe. From the repository root:

```sh
python3 tools/build.py input.mp4 --id night-walk --title "Night walk" --start 35 --seconds 15 --description "One street. A little less detail."
```

Commit the generated assets directory. The workflow retains custom clips and regenerates only the three demos. Reserve IDs drive, orbit and rain for demos. Source videos are not published automatically; use footage you have permission to redistribute.

Pipeline: video → FFmpeg grayscale frames → brightness-to-ASCII mapping → compact JSON → gzip → static hosting → browser decompression → text playback. Qualities are 48 columns/4 fps, 72/6 and 96/8. Character cells are assumed twice as tall as wide; display aspect ratio is preserved approximately.

Optional `--subtitles subtitles.json` accepts a JSON array like `[{"start":2,"end":6,"text":"We waited for the signal."}]`, timed relative to the extracted clip.

## Honest limitations

This is buffered clip playback, not progressive streaming: each clip downloads before playing. Quality selection downloads a genuinely different asset; modem labels are fictional and do not throttle network speed. Clips are silent, and animation never auto-starts. A modern browser is required; this is not a WML application for old WAP phones.

The included simple, repetitive 12-second demos are roughly 2.5–16 KiB compressed per variant. Actual footage can be much larger. ASCII is not automatically more bandwidth-efficient than modern video. Displayed KiB is the downloaded clip asset size, not total page traffic. Browsers without DecompressionStream download the larger JSON fallback. Do not serve .gz assets with a Content-Encoding header: the player explicitly decompresses them.

For long-form playback, use short independent chunks, buffered prefetching and measured delta encoding. The current prototype loads whole clips into memory. Syntax and conversion tests are not a substitute for visual browser testing.

## Related work

- https://github.com/brainphreak/html5-ascii-video-player — browser-side video-to-ASCII rendering, a different delivery model.
- https://wonger.dev/posts/chafa-ffmpeg-progress — FFmpeg decoding combined with Chafa symbol rendering.
- https://docs.asciinema.org/manual/asciicast/v2/ — timed terminal-output format.

Research references only; no code or assets from these projects are bundled. Code and original generated demo clips are MIT licensed.
