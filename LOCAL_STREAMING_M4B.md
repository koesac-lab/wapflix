# Milestone 4B: browser controls for the verified restart-seek API

Adds tools/lcd_stream_seek_viewer.py, tools/lcd_seek_controls.js, tests/test_lcd_seek_viewer.py, tests/test_lcd_seek_viewer.cjs and this document. Does not overwrite M1-M4A, the caption viewer, handset UI, Pages or media. Requires the working M4A API files installed locally; they need not already be pushed to GitHub. No slider, cached-position fast path, persistent cache, Docker, Plex or audio is included.

## Install and run

Stop the running server with Ctrl-C. Receive this archive into the repo root and extract with tar --keep-old-files -xzf and its filename; stop on errors.

```sh
cd ~/wapflix
python3 -m unittest discover -s tests -p 'test_lcd_seek_api.py' -v
python3 -m unittest discover -s tests -p 'test_lcd_seek_viewer.py' -v
node tests/test_lcd_seek_viewer.cjs
python3 tools/lcd_stream_seek_viewer.py --bind 0.0.0.0 --port 8101
```

Refresh http://YOUR_MINI_PC_LAN_IP:8101/ and click Start. The new entry point reuses the M4A handler and creates the seek controls in its served copy of the M3 page. Original files remain unchanged. Default source, SRT detection, --video, --srt, --start, --seconds, --delay, --no-srt and --allow-host remain available.

## Controls

- -10 sec / +10 sec move relative to the displayed source position (or the latest target while a seek is pending).
- Source seconds + Go or Enter seeks to an absolute source timestamp.
- Input is clamped to the configured extract's last frame. The M4A server snaps to its 8 fps grid. Defaults still cover source seconds 30..90, not the full source video; the earlier 120-second maximum extract length remains.
- A seek resets the rolling browser buffer and starts a new server session. Every seek currently restarts FFmpeg; this is not a cache-reuse implementation.
- Paused seeks remain paused once the target frame arrives. The worker is allowed to produce an initial buffer before a paused heartbeat parks it, avoiding startup deadlock.
- Caption on/off preference survives seeking. Old text clears immediately; new cues use the returned absolute source times and actual displayed frame.
- Stop invalidates the navigation, aborts pending client work and calls the M4A navigation-stop endpoint. Late seek replies cannot restore the old picture/captions. New Start resets the original configured extract.

The client uses generation counters plus increasing seek revisions; the server's revision checks remain unchanged. Rapid seeks retain the latest target. Hiding the tab while a seek is pending does not auto-start background playback when it completes. Page navigation sends a best-effort navigation-stop beacon; inherited lease expiry remains the fallback when a request has not been acknowledged or network delivery fails.

## Focused validation

Four Python unit tests cover guarded injection, nonce/single-script preservation, backend constructor forwarding and cleanup on incompatible viewer HTML. Node VM state checks use the repository M2 viewer/M3 caption scripts (blob IDs 6c4a25b14dcbb06df43ed488ed14f3e6529549dd and 59c3a0344d4d72a009958b9e7cf66b66805b554d) with fake DOM/transport: playing seek, paused target preview, caption preference, warmup/paused pulses, invalid/clamped input, out-of-order responses, Stop during seek, hidden tab, seek failure, delayed Stop failure, unload cancellation and input focus. This is not a real-browser rendering or M4B live-HTTP/FFmpeg end-to-end test. Run the unchanged M4A backend regression tests locally as listed above and complete the browser acceptance checks.

## Acceptance gate

1. Start; +10 then -10. Verify the displayed source position and captions move together.
2. Pause; Go to source second 55. The new frame must appear but remain paused. Toggle captions off, seek again and confirm they stay off.
3. Click +10 rapidly a few times. Only the latest target should take effect.
4. Seek, then immediately Stop. No late picture, caption or playback should reappear.
5. Start again; confirm normal playback. Repeat with --delay 3 if needed to expose buffering transitions.

This is still a single-user trusted LAN/Tailscale development service, not public authentication. Nothing is auto-committed or uploaded. Return to python3 tools/lcd_stream_captions.py --bind 0.0.0.0 --port 8101 for the untouched caption-only fallback. Verify these controls before proceeding to handset integration; cache-reuse seeking should be a separate change.
