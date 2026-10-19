# Milestone 4A: restart-seek backend checkpoint

This is intentionally not all of milestone 4. Adds tools/lcd_stream_seek_api.py, tools/lcd_seek_smoke.py, tests/test_lcd_seek_api.py and this document. Existing M1-M3 files, LAN patch, caption viewer and public Pages remain unchanged. No seek buttons/slider, client seek-response handling, disk cache, cache-reuse seeking, Docker, Plex or audio are included. The original M3 command remains your working fallback.

Baseline interfaces checked on GitHub main: lcd_chunker.py blob 173aed02e4f2c12c527dd288ff7aeb2ee739b398; lcd_stream_server.py 0e111b62f413d2f46b1bdba70a7a2437dfc8fc23; lcd_stream_captions.py 7e4d8ec73b1938517e6463990004cf8bc15e9bdd. Run local tests before starting the new entry point. Stop rather than overwrite any partially installed same-named files.

## Install and validate

Extract the attached archive in the repo root using tar --keep-old-files -xzf and its filename, then:

```sh
cd ~/wapflix
python3 -m unittest discover -s tests -p 'test_lcd_seek_api.py' -v
```

Close the browser viewer and stop the previous server with Ctrl-C. Start the new backend:

```sh
python3 tools/lcd_stream_seek_api.py --bind 0.0.0.0 --port 8101
```

The normal video/SRT auto-detection and --video, --srt, --start, --seconds, --delay and --allow-host options are preserved. Defaults still select the existing test source and the 30..90-second extract. The server is LAN-accessible but remains a trusted-network development service, not public authentication.

In another terminal on the mini PC, run:

```sh
cd ~/wapflix
python3 tools/lcd_seek_smoke.py
```

Or pass --url http://YOUR_MINI_PC_LAN_IP:8101 from a machine with the repo/utility. No SSH tunnel is required. Keep the browser closed during this probe because it owns and replaces the single session.

The probe reads the page capability token, starts playback, seeks forward/back/forward, fetches the first chunk after each move, verifies source position/caption timebase and stops the session. Expect three seek-ok JSON lines followed by m4a-complete with session_stopped true. It is an active test, not a read-only diagnostic; it replaces any current playback. No source media or captions are uploaded or committed.

## API contract

POST /api/start resets to the configured extract start and returns the existing M3 metadata plus navigation_id, revision=0, range_start, range_end, seek_position and seek_mode=restart.

POST /api/seek accepts navigation_id, a monotonically increasing positive integer revision, and position in absolute source seconds. The valid interval is range_start <= position < range_end. Position snaps down to the 8 fps grid relative to range_start. A seek returns a new session ID and updated absolute-time captions for the remaining extract; its chunks restart at index/start_frame zero with source_start set to the seek position. Always use the returned session ID for subsequent pulse/chunk calls.

All seeks stop/reap the previous worker before creating a replacement. Revisions lower than or equal to the latest accepted one return 409, including requests arriving out of order. A new Start replaces the navigation ID, invalidating old seeks. A stopped/expired session cannot be resurrected by a delayed seek.

POST /api/navigation/stop accepts navigation_id, invalidates that navigation and stops its worker. Delayed seeks on that navigation then return 409. Stopping an obsolete navigation does not stop a newer Start. Existing /api/stop remains usable and also prevents later seeks on that stopped session; the navigation-level endpoint is preferred for future client cancellation while seek responses are pending.

Existing token, Host, Origin and request-size checks are retained for both new endpoints. There is still only one session globally. Original worker look-ahead and lease expiry are reused. No automatic background completion, persistent cache or cached-position fast path has been introduced.

## Validation and next gate

Seven focused tests passed with generated video and SRT cues: forward/back source positions and captions; out-of-order revisions; new Start/cancellation invalidation; legacy Stop protection; invalid inputs/last frame; concurrent latest-revision behaviour and worker reaping; actual HTTP security/contract plus the probe. The served page was a fixture in backend tests; no browser seeking or full-project regression is claimed.

M4B will add small forward/back controls and client generation guards on top of this tested API. The current page has no seek controls; do not mistake API completion for a shipped seek UI. Run the probe locally and save its result before advancing. If an earlier failed attempt produced a runtime error, retain its traceback; this clean additive checkpoint does not diagnose an unseen error log.
