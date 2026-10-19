# Milestone 3: captions on the working LAN LCD viewer

This is an additive wrapper, not a replacement for the working server. Requires M1 tools/lcd_chunker.py, M2 tools/lcd_stream_server.py and lcd_stream_viewer.html, the applied M2 LAN update, and the repository tools/srt.py. Original files remain untouched. No seeking, Docker, Plex, audio, handset/Pages integration, source download or GitHub write is included.

## Install and run

Stop the current server with Ctrl-C. Receive this archive into the repo root and extract it with tar --keep-old-files -xzf and its filename. Stop on extraction errors. Five new files are added: tools/lcd_stream_captions.py, tools/lcd_caption_overlay.js, tests/test_lcd_stream_captions.py, tests/test_lcd_stream_captions.cjs and this document.

```sh
cd ~/wapflix
python3 -m unittest discover -s tests -p 'test_lcd_stream_captions.py' -v
node tests/test_lcd_stream_captions.cjs
python3 tools/lcd_stream_captions.py --bind 0.0.0.0 --port 8101
```

Open the same http://YOUR_MINI_PC_LAN_IP:8101/ URL, refresh and click Start. The command uses the existing source.mp4 under ~/.local/share/wapflix/test-media/dQw4w9WgXcQ/, the same 30-second start and 60-second extract as M2. No SSH tunnel is required. Optional trusted hostname aliases still use --allow-host hostname.local.

SRT auto-detection checks source.youtube.en.srt, source.en.srt, then source.srt beside the source file. --srt /path/to/subtitles.srt selects a specific file; --subtitles is an alias. Missing explicit files fail clearly. Missing auto-detected files leave the video usable and display a no-SRT notice. --no-srt disables captions. The file is parsed at server startup; restart the server after editing it. Malformed cues are skipped with a warning count; valid cues remain usable.

## Timeline contract

Caption metadata is added once to the session-start JSON, not repeated in every video chunk or heartbeat. Cue times remain absolute source seconds and are clipped to the actual extracted window, including EOF. The client matches source_start + painted_frame/fps, using the actual displayed frame from the existing player. This is intentionally quantised to the video frame rate. It avoids double offsets and prevents subtitles advancing over a held frame when the playback clock reaches a missing-chunk boundary. Pause, buffering and hidden-tab pauses do not advance displayed-frame time.

Caption toggle never changes playback position. Stop, restart, errors and end-of-clip clear the old caption. Late start responses from an earlier generation cannot restore stale cues. Overlapping cue lines are shown without duplicate lines; text is assigned through textContent, never innerHTML. Parser warnings and empty extract notices are visible below the video. The full original SRT and its filesystem path are not sent to the browser; only selected cues and counts are returned.

The inherited M2 worker, look-ahead, expiry, Host/Origin and capability-token behaviour are unchanged. This remains trusted-LAN/Tailscale development access, not public authentication; anyone who can open the page can control the single test session. Do not publicly port-forward it.

## Focused validation

Six Python tests cover guarded HTML injection, SRT detection/disable, source offsets, extract/EOF clipping, missing files, parser warnings, actual HTTP metadata, inherited Host/token checks, restart and worker cleanup using generated video. Node VM checks cover source offsets, held-frame buffering, pause/visibility, toggle, literal text, Stop/restart, final-frame clearing, no SRT and stale start responses. These are not a real browser visual test, full project regression suite, test-video caption accuracy result or N5105 benchmark.

## Acceptance gate

1. Play with captions visible. Pause for a few seconds; both frame and caption should hold.
2. Toggle captions off/on while paused; the position must not change.
3. Stop and Start again; old cues must not appear at the new start.
4. Restart with --delay 3 to force buffering; captions must not run ahead of held video.
5. Confirm the original M2 command still works as the caption-free fallback.

Only after this passes should milestone 4 add seeking. If needed, stop this wrapper and return to python3 tools/lcd_stream_server.py --bind 0.0.0.0 --port 8101. Nothing was overwritten.
