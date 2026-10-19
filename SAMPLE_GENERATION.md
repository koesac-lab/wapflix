# Fine LCD samples

From the repo root, run any of:

```sh
python3 tools/regenerate_samples.py snippet
python3 tools/regenerate_samples.py full
python3 tools/regenerate_samples.py both
```

Defaults use the existing source.mp4 under ~/.local/share/wapflix/test-media/dQw4w9WgXcQ/. Preview is 15 seconds from 30 seconds, ID test-video. Full starts at zero and runs to EOF, ID test-video-full. Adjacent source.youtube.en.srt, source.en.srt, or source.srt is detected automatically. Captions are rebased separately for each output. No download or upload is performed.

## Controls

```sh
python3 tools/regenerate_samples.py both --force
python3 tools/regenerate_samples.py snippet --start 45 --seconds 20
python3 tools/regenerate_samples.py both --video /media/own.mp4 --srt /media/own.srt --id my-video
python3 tools/regenerate_samples.py snippet --contrast 1.15 --gamma 1.05
python3 tools/regenerate_samples.py snippet --ascii
```

--no-srt disables captions. --ascii adds the original ASCII comparison (three extra decodes per clip); it is deliberately optional for fast full-video builds. LCD-only entries explain this when 7 is pressed. Existing ASCII-only assets and existing dual-format entries still work.

## Finer picture

For landscape sources: low = 120 pixels/6 fps; medium = 240/8; high = 240/12. Medium is now the player default. For 16:9, medium is 240x135, rendered 1:1 inside the 240x200 scene area, rather than enlarged blocks. It remains dark-ink, one-bit ordered dithering, not smooth greyscale. --width accepts 96..240 divisible by 16. Portrait/extreme sources fit within the scene height while keeping aspect ratio approximately; they may have fewer columns.

FFmpeg decodes each output clip once and creates three packed monochrome streams with Bayer dithering. Temporary raw streams occupy disk space; JSON/gzip packing reads one frame at a time, not a whole video frame list. Both mode needs one decode for the preview and another for the full source. The original procedural scenes are regenerated at finer resolution by the Pages workflow; this path uses the existing Python scene renderer.

Unchanged source size/mtime, subtitle size/mtime and recipe reuse existing outputs. Use --force if content changes without a metadata change. Filenames include a recipe/source fingerprint to prevent stale browser assets. Old fingerprinted assets are not automatically deleted; remove obsolete versions deliberately after checking the catalogue. Concurrent generators targeting the same assets directory are unsupported.

## Publish

Review git status and stage assets/catalogue.json plus only the new files for your chosen ID, then commit and push main. No script auto-commits or pushes, and original MP4/SRT files stay outside the repo. Pages publishes converted footage and caption text publicly: only publish material you may redistribute.

After deployment, open ?episode=test-video or ?episode=test-video-full. Existing committed test footage needs local regeneration to become finer; changing the player does not invent missing image detail.

Full playback still downloads/decompresses the selected whole clip into the browser. Bounded conversion memory does not mean bounded player memory. Long episodes should eventually use chunks; this update does not add progressive transport, sound, Plex integration, or a faithful hardware-resolution emulation. Visual comparison on the real handset page and timing on the N5105 remain necessary.
