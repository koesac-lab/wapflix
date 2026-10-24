# WAPFLIX — cinema, reduced

A retro-handset LCD/ASCII cinema project, with an independent public static demo and a private on-demand conversion application under development. A modern browser is required; this is not an application for original WAP hardware.

## Development: start here

Read [docs/START_HERE.md](docs/START_HERE.md) for current verified status, document precedence and the next bounded task. Read [ROADMAP.md](ROADMAP.md) for product direction, not implementation completion.

Current next work is R2B.1 under [the R2B backend contract](docs/plans/R2B_BACKEND_CONTRACT.md). R1 and the isolated R2A core are committed; full Start fencing is not wired into the backend/adapter. The existing handset-live host is an unaccepted integration scaffold, not proof of real conversion. The corrected [5A.3 checkpoint](CHECKPOINT_5A3.md) explains the limitations.

Do not use older milestone prose or reported mock-test counts as evidence that later work is finished. Keep implementation patches small and stage intended files explicitly rather than archives/backups/output with git add .

## Public demo

The GitHub Pages workflow builds and deploys the static experience from main. It must remain independent of local APIs, credentials and personal library data. Successful deployment and browser verification are separate from a successful commit. See [LCD_VIDEO.md](LCD_VIDEO.md) and [SAMPLE_GENERATION.md](SAMPLE_GENERATION.md).

## Local static handset preview

With the existing converted assets in place:

```sh
python3 tools/handset_static_preview.py --bind 0.0.0.0 --port 8102
```

Open http://YOUR_MINI_PC_LAN_IP:8102/. This is static playback only and does not rebuild video or connect to the streaming API. See [HANDSET_5A1.md](HANDSET_5A1.md). Keep development servers on a trusted network, not publicly port-forwarded.

The original root-only preview remains a simpler legacy path:

```sh
python3 tools/build.py
python3 -m http.server 8000
```

Do not open index.html as a file. This root-only path does not assemble all enhanced handset modules.

## Conversion and diagnostic tools

- [SAMPLE_GENERATION.md](SAMPLE_GENERATION.md): current fine-LCD presets and repeatable snippet/full generation using tools/regenerate_samples.py.
- [LCD_VIDEO.md](LCD_VIDEO.md): legacy LCD converter and format; its old presets are not the current fine-profile defaults.
- [LOCAL_STREAMING_M2.md](LOCAL_STREAMING_M2.md), [M2_LAN_ACCESS.md](M2_LAN_ACCESS.md), [LOCAL_STREAMING_M3.md](LOCAL_STREAMING_M3.md): local LCD diagnostic server/caption checkpoints.
- [LOCAL_STREAMING_M4A.md](LOCAL_STREAMING_M4A.md), [LOCAL_STREAMING_M4B.md](LOCAL_STREAMING_M4B.md): diagnostic seek API/viewer, not the full handset integration.
- [HANDSET_5A2.md](HANDSET_5A2.md): standalone browser transport adapter.

Install FFmpeg/ffprobe for video conversion. Source media and full SRT files belong outside the public assets/repository. Converted frames and caption text are also redistributable media content: publish only what you may redistribute. Reserve drive, orbit and rain for procedural demo IDs.

## Playback limitations and compression

Public/static clips download in full before playback. The real local diagnostic pipeline delivers progressive chunks. The handset integration remains gated and must not be confused with either. Clips are silent; modem labels are fictional and do not throttle bandwidth. Neither ASCII nor one-bit frames are automatically more efficient than modern video codecs.

Static .gz assets deliberately have no Content-Encoding because the static loader decompresses explicitly; plain JSON is its fallback. API gzip chunks use ordinary HTTP Content-Encoding. Do not interchange the two behaviours. Automated syntax/state tests do not replace browser/host validation.

## Plans and history

Active status and task: [docs/START_HERE.md](docs/START_HERE.md). Detailed phase requirements and historical records are indexed there. Existing runtime, archives, backups and media are not removed by this documentation cleanup.

Research references only; no code/assets from these are bundled:

- https://github.com/brainphreak/html5-ascii-video-player
- https://wonger.dev/posts/chafa-ffmpeg-progress
- https://docs.asciinema.org/manual/asciicast/v2/

Code and original generated demo clips are MIT licensed.
