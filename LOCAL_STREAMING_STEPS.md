# Local streaming: small, independently testable milestones

## M1: LCD chunk engine (this archive)

Adds tools/lcd_chunker.py and tests/test_lcd_chunker.py. Existing converters, player, navigation, Pages workflow and media assets are untouched. No HTTP server or Docker setup is included.

Fixed first profile: same fine-LCD filter settings as the approved generator, width up to 240, 8 fps, 16 frames per chunk (2 seconds). Portrait sources fit within 200 rows. Maximum request length is deliberately 120 seconds at this checkpoint; default is 60 seconds starting at source time 30. No captions, seeking, sessions, quality switching, cache eviction or network access yet.

FFmpeg writes packed monochrome frames through stdout. One chunk is collected at a time and published as independent JSON and gzip files, followed by an atomic manifest update. Memory does not hold a full clip frame list. Disk output grows with the requested clip; this is not the eventual bounded cache. The first chunk can be consumed before conversion completes. Closing the iterator or context stops and reaps its FFmpeg process.

Chunk start_frame is relative to the requested extract; source_start records its source offset. A frame's source time is source_start + (start_frame + frame_index)/fps. One=ink, hex-msb, row-major packed bits; width is divisible by eight. Layout matches the existing lcd-1bit pixel encoding, but the existing static handset loader does not yet fetch this chunk format.

### Install and test

Extract the archive into the repository root using tar --keep-old-files -xzf with its filename. Stop on an extraction error. It only adds three files.

```sh
python3 -m unittest discover -s tests -p 'test_lcd_chunker.py' -v
RUN_DIR=$(mktemp -d /tmp/wapflix-lcd-m1.XXXXXX)
python3 tools/lcd_chunker.py --output "$RUN_DIR/chunks"
```

The default video is ~/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4. Override --video if needed. --start and --seconds are optional. The output directory must not already exist; mktemp creates a parent, while the command creates its chunks child. Source videos are read only and no footage is uploaded or committed.

The last JSON line has event complete, chunk/frame counts, time to first chunk, whether FFmpeg was still running when that first chunk was published, total conversion time and output location. Startup timing excludes ffprobe. Treat timings as source/host-specific, not a guarantee. manifest.json records complete/error/cancelled state; failed runs retain produced chunks for inspection. Use a new output directory on retry.

Nine automated tests cover frame framing, duration limits, partial final chunks, source-relative timeline metadata, early chunk production, process cleanup, fine-filter byte parity, manifest/gzip correctness and refusal to overwrite prior output. Host-side testing and browser streaming are separate future gates. No N5105 performance or browser validation is claimed from these tests.

## Next checkpoints (do not implement together)

M2: loopback-only HTTP delivery and a minimal test viewer. Gate: picture starts before full conversion completes; buffer/pause/stop behave correctly. No handset edits.

M3: source-time captions. Gate: pause/buffering do not move subtitles ahead of the picture.

M4: seek/restart lifecycle. Gate: repeated seeks leave one worker, stale chunks are ignored, cached positions can be reused.

M5: handset source adapter. Gate: local streams use the existing interface while Pages retains static playback.

M6: Docker Compose, private access and bounded persistent cache. Gate: clean start/stop/restart with read-only media mounts and enforced cache/session limits.

Plex browsing and audio follow separately. Each completed checkpoint should have its own test result and commit before advancing. This file and archive implement M1 only.
