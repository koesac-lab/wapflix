# Milestone 2: local HTTP LCD test viewer

## Scope

Adds a loopback-only HTTP server and a standalone browser viewer around the M1 chunk engine. Requires tools/lcd_chunker.py from milestone 1; this archive does not replace it. Existing Pages, handset, sample converters and source files remain untouched. Nothing is auto-committed, downloaded or uploaded.

Fixed 240px maximum width, 8 fps, two-second chunks, four-second startup buffer, 60-second default extract starting at source time 30. M1 still limits requested extracts to 120 seconds. No captions, audio, seeking, Docker, persistent cache, full-library browsing or Plex integration yet.

## Install

Receive this archive into the repository root and extract it using tar --keep-old-files -xzf and its filename. Stop if extraction reports an error. The five added files are tools/lcd_stream_server.py, tools/lcd_stream_viewer.html, tests/test_lcd_stream_server.py, tests/test_lcd_stream_viewer.cjs, and this document.

```sh
cd ~/wapflix
python3 -m unittest discover -s tests -p 'test_lcd_chunker.py' -v
python3 -m unittest discover -s tests -p 'test_lcd_stream_server.py' -v
node tests/test_lcd_stream_viewer.cjs
python3 tools/lcd_stream_server.py
```

Uses the existing source.mp4 under ~/.local/share/wapflix/test-media/dQw4w9WgXcQ/. Override --video /path/to/own.mp4, --start, --seconds, or --port as required. Open http://127.0.0.1:8101/ on the server machine and click Start. Start replaces the current session; Pause holds playback; Stop releases the worker. Hiding the tab pauses playback. Reopening the page and starting again replaces its previous session.

To open from a different computer, keep the server bound to loopback and forward the same port over SSH, using your real mini-PC hostname/IP:

```sh
ssh -N -L 127.0.0.1:8101:127.0.0.1:8101 koesac@YOUR_MINI_PC_TAILSCALE_IP
```

Then open http://127.0.0.1:8101/ on that computer. Requires working SSH access. Leave this tunnel terminal open. Forward the same numbered port because Host validation checks it. There is deliberately no --bind 0.0.0.0 option; direct LAN access, Tailscale Serve/reverse-proxy hostnames and public tunnels are not configured in this milestone.

## Behaviour and limits

One session and one FFmpeg worker at a time. Generation pauses at eight chunks ahead of the reported playback position. Retained server cache is at most nine published chunks (one previous plus eight ahead), plus an unpublished chunk/pipe buffers. The browser retains a small rolling window. Everything is in memory; Stop or server shutdown drops it. There is no persistent cache or cache reuse across sessions yet.

The client pulses every 250ms while active. Sessions without a heartbeat expire after 15 seconds, releasing the worker; background-tab timer suspension or a disconnected tunnel can therefore require Start again. Successful Stop requests and normal Ctrl-C also stop the worker. Page navigation sends a best-effort stop beacon, with lease expiry as fallback.

Use --delay 3 to deliberately generate only two seconds of footage every three seconds and exercise buffering. This is artificial slowdown, not a real performance measurement. The player clock must hold during buffering and resume when more frames arrive. The displayed first-chunk time is the converter's timing, not time-to-first-browser-picture, and excludes source probing.

API paths are fixed to the source configured at startup. There is no arbitrary file/path/URL API or static directory listing. The page receives a random capability token; APIs require it. Host/Origin checks restrict the local test origin. Gzip chunks use HTTP Content-Encoding and browser automatic decompression, unlike the static Pages explicit-gzip asset path. This standard-library HTTP server is a private development checkpoint, not a production service or security boundary for public deployment.

## Acceptance test

1. Start with delay 0. For a long-enough extract, playback should begin while server state is running rather than after the whole source converts.
2. Pause for several seconds and resume. Position must hold; published look-ahead must stay bounded.
3. Stop. Server worker must terminate and retained chunks must clear.
4. Start again, then refresh/start again. The previous worker must be reaped before replacement.
5. Restart the server with --delay 3 and observe buffering freeze/recovery.
6. Close the page. The stop beacon or 15-second lease must release its worker.

Seven HTTP integration tests with generated video passed, including actual chunk delivery, look-ahead, expiry, replacement, partial final chunks and input/host/origin checks. Node VM checks passed for playback clock, buffering freeze/recovery, pause, hidden tabs, final-frame handling and late responses after Stop. These are not a real-browser rendering test, N5105 throughput result, full repo regression run or production security audit.

Next checkpoint: source-time captions on this viewer. Do not combine it with seeking or handset integration.
