# Handset 5A.3: fixed on-demand stream integration plan

Status: planning only. This document does not implement live handset playback. Runtime code, media, existing milestones and the Pages workflow are unchanged.

## Goal

Connect one server-configured video to the existing handset interface so selecting it starts on-demand conversion and displays LCD frames inside the phone. Support starting, initial buffering, progressive frame display, rebuffering, Stop/Back, natural completion and errors. Preserve all existing static playback.

The M4 diagnostic viewer remains the working fallback. Do not rebuild the M1-M4 stack as part of this milestone.

## 1. Scope

| Included | Deferred |
| --- | --- |
| One fixed local streaming entry | Plex or filesystem browsing |
| Same-origin handset and API hosting | Docker or reverse-proxy deployment |
| Existing 240-pixel LCD profile | Quality switching |
| Start, render and Stop | User-facing Pause |
| Buffering and natural completion | Caption display |
| Back/Home cleanup | Seeking controls |
| Existing static entries still work | Live resume, progress persistence and autoplay-next |

Caption metadata may still arrive from the backend, but this checkpoint does not display it. Do not expose controls that appear to support live seeking, quality changes or ASCII mode.

## 2. Integration constraint: static clips are not rolling streams

The reviewed player.js reads clip.frames directly and derives duration from clip.frames.length / clip.fps. The reviewed streaming.js uses that duration for progress saving, completion and autoplay-next. Making a rolling stream pretend to be a complete static clip would expand the task substantially.

Recommended approach: introduce a distinct live playback view, such as live-player, while preserving the static player view. For live playback:

- Keep clip unset instead of fabricating a complete frame array.
- Use the existing 5A.2 adapter as the source.
- Use the existing handset canvas and controls.
- Capture the launch screen for the return path.
- Bypass static progress persistence, completion detection and autoplay-next.

For every static item, delegate to the existing implementation unchanged. Do not create placeholder asset URLs, dummy frame arrays or a growing whole-video clip.frames list.

Source review baseline: player.js d6f971a2b7487d286e0264a7b74a64ec3206a0ba; streaming.js 01aef733a4dbdf716f42f3f678b20427320b51d7; tools/handset_static_preview.py 2b1d146dffa5c562a98cc2feccebd775eb260d01. Check actual local files and local-only milestone work before implementation; these are reviewed blob IDs, not a claim that every later checkout remains identical.

## 3. Same-origin local host

The 5A.1 preview on port 8102 and API on 8101 are different browser origins. Solve this through hosting rather than disabling CORS, Host or Origin checks.

Proposed new entry point: tools/handset_live_preview.py. Proposed independent default port: 8103, so existing diagnostic and static servers can remain available.

| Route | Purpose |
| --- | --- |
| / | Existing handset page with local-only integration scripts |
| /assets/catalogue.json | Existing catalogue plus one in-memory live entry |
| Existing frontend and referenced asset routes | Static handset functionality |
| /stream-source.js | Existing 5A.2 adapter |
| /handset-live.js | New handset bridge |
| /api/start | Existing session creation |
| /api/pulse | Existing heartbeat/status |
| /api/chunk | Existing chunk delivery |
| /api/navigation/stop | Existing navigation cancellation |

Hosting rules:

- Reuse the M4 API handler and session implementation.
- Reuse the 5A.1 static-file allowlisting approach.
- Do not expose the repository as an unrestricted directory.
- Do not edit the public catalogue or Pages workflow.
- Do not regenerate video assets.
- Preserve LAN binding, trusted hostname aliases and Host/Origin checks.
- Keep static .gz assets without Content-Encoding because the static player decompresses them explicitly. API chunks retain ordinary HTTP gzip Content-Encoding. Test both paths.

### Capability and CSP

Inject the API capability into a namespaced, local-only configuration object. Do not add a global variable named token: the existing handset already uses a numeric token to invalidate older static loads.

The generated handset HTML, configuration script and CSP header must agree on their script nonce. Do not combine the static preview's nonce and backend nonce without reconciling the response headers.

The capability belongs in the dynamically served page, not Git, the catalogue or local storage. This remains trusted-network development access, not public-user authentication. No arbitrary media path or URL is accepted from the browser.

## 4. One virtual catalogue entry

Append one entry to the local host's served catalogue copy:

- ID: local-stream-test
- Title: Local stream test
- Playback type: local-stream
- Source identity: configured-test

Use the existing navigation path: Home -> Original Transmissions -> Local stream test -> Play.

The backend source remains configured on the server. The entry has an explicit playback discriminator, not fake static variants. Do not infer streaming from an ID substring or replace the existing static test entry. The original catalogue stays unchanged on disk.

If a required bridge or adapter is absent, fail startup clearly rather than exposing a broken live entry. Public Pages and the standalone static preview must not receive this entry.

## 5. Handset bridge

Proposed new script: handset-live.js. Load it after the existing wrappers so static delegation preserves their final behaviour.

Proposed script order:

1. Existing inline handset bootstrap.
2. player.js
3. streaming.js
4. theme.js
5. sharing.js
6. stream-source.js
7. handset-live.js

The bridge owns only:

- Recognition of the live entry and capture of its return screen.
- Adapter start/stop and live playback state.
- Adapter polling and frame presentation on the existing canvas.
- Live-only control restrictions.
- Rejection of callbacks belonging to an abandoned live view.

It must not take over the entire catalogue or replace the navigation system.

### State model

Idle -> Starting -> Buffering -> Playing. Playing may return to Buffering. Natural completion leads to Ended. Active states may lead to Error or Stopping, followed by the previous navigation screen.

Ended and Error must provide a clear return path. Starting again from the details page creates a fresh session. No automatic retry or next-item playback.

## 6. One playback clock and one animation chain

The adapter has no playback clock. Retain the handset's existing relative playback position and convert it for adapter calls:

source time = stream source_start + relative playback position

Use the returned frame timestamp as the authoritative displayed-frame position. Advance only when the required frame is available. Freeze during startup, buffering and stopping. Reset timing references when entering or leaving live playback.

There must be exactly one requestAnimationFrame scheduling chain. Add a live branch around the existing tick path; do not leave the original loop running alongside a second loop. The static tick must not also advance the position during live playback. Tests should count scheduled callbacks.

### Network polling

Use one active heartbeat/prefetch timer, initially around the established 250 ms cadence. Start it for an acknowledged live session, keep it running during buffering, let the adapter coalesce overlapping requests and clear it on exit. Repeated Play must not accumulate intervals.

### Hidden pages

For this limited checkpoint, hiding the page stops the live session and returns to its details screen rather than adding hidden-tab pause/resume behaviour. Browsers commonly suspend animation callbacks in hidden tabs, so cleanup must not depend on continued rendering. Manual Play is required again on return.

## 7. Buffering, rendering and completion

### Startup

Use the existing four-second initial buffer. Begin motion when four seconds of contiguous footage are available, or when a shorter extract has completed and at least one frame is available.

### Rebuffering

When the next required frame is absent:

- Hold the last displayed image.
- Stop advancing playback position.
- Show BUFFERING and continue polling.
- Resume after a small contiguous buffer is available, initially one two-second chunk.

Do not clear the picture repeatedly or restart FFmpeg for every gap.

### Rendering

Use the current canvas, scene area, ink colour, LCD background and nearest-neighbour scaling rules. Decode only the selected frame with the existing hex-msb interpretation. Preserve transparent background/backlight behaviour. Avoid rewriting the static renderer just to share a short bit-decoding loop.

Memory should comprise the adapter's bounded chunk window, one currently presented frame and the existing canvas image buffer. Never accumulate all received frames into clip.frames.

### Completion

Use the configured duration initially, then the final frame count once reported. Detect EOF separately from a missing future chunk. At completion, present the final frame, stop clock/polling, release the session and show TRANSMISSION ENDED with Back. No autoplay-next.

## 8. Live-only control contract

| Control | Live behaviour |
| --- | --- |
| Select / key 5 | Stop and return |
| Back / physical back control | Stop and return to launch screen |
| * | Stop, then Home |
| # | Existing backlight behaviour |
| 4 / 6 | No seek; announce unavailable in this checkpoint |
| 0 | No quality change |
| 2 | No caption toggle |
| 7 | No ASCII/LCD switch |
| Info / sharing | Do not invoke static clip-dependent behaviour |

The live footer must describe actual actions, such as STOP / BACK, instead of promising Pause. Verify the different handset layouts. If a model-specific footer policy overrides the label, use a narrow live-view exception rather than a global navigation redesign.

Static items retain their existing controls and persisted renderer preference. A saved ASCII preference must not prevent this fixed LCD live source from displaying; returning to static playback must preserve the user's original preference.

## 9. Cleanup and races

### Back during startup

Return the UI immediately. Let the adapter release any acknowledged navigation through its serialized lifecycle. A late Start response must not reopen the live screen.

### Repeated Play

Invalidate the old bridge generation and use the adapter lifecycle queue. Do not create independent adapter instances racing to own the backend.

### Live to static

Stop the live source, invalidate its callbacks, reset timing/rendering state and delegate the static load to the existing loader. No late live frame may paint over static playback.

### Static to live

Invalidate the handset's existing static-load token before starting the live source. An earlier static download must not restore the static player over the live view.

### Network or cleanup failure

Show an actionable error and keep Back usable. Do not silently create another session if acknowledged cleanup failed. Preserve the backend lease fallback for unacknowledged or unreachable work. Never claim confirmed immediate cleanup when the network request failed.

Live playback must not write resume/completion records into the static progress store.

## 10. Proposed implementation files

Target two new implementation files:

| File | Role |
| --- | --- |
| tools/handset_live_preview.py | Same-origin host, capability/configuration and virtual entry |
| handset-live.js | Live-view bridge using the existing adapter |

Supporting files cover host/routing tests, bridge timing/state tests, browser integration checks and installation/acceptance/rollback notes.

Keep stream-source.js, the conversion engine and M4 API unchanged unless baseline validation finds a specific blocking defect. Fix any such defect separately instead of burying it in the integration. Final filenames and exact file count should be confirmed during implementation, not treated as already created.

## 11. Three small implementation passes

### 5A.3A: hosting only

Implement the new host and HTTP tests. Gate: static handset playback still works; handset/API share an origin; capability/CSP and both gzip paths are correct; no live entry is exposed before its bridge is available.

### 5A.3B: bridge in isolation

Implement the bridge with controlled adapter responses. Gate: correct state transitions; buffering freezes time; exactly one animation chain and polling timer; Stop/source switching reject stale callbacks; static playback remains unaffected.

### 5A.3C: connect and verify

Enable the virtual entry and perform actual browser tests. Gate: selecting it shows converted frames inside the phone before the entire extract converts; Stop/Back/Home, hidden-page cleanup and EOF work; static playback works afterwards; handset labels/actions remain correct.

Save each pass before starting the next. Do not reconstruct M1-M4 or turn this into one large rewrite.

## 12. Definition of done

On the mini PC:

1. Open the local handset over the LAN.
2. Select Local stream test.
3. Observe startup/buffering followed by moving LCD footage inside the phone.
4. Stop and return to the correct screen.
5. Start again without accumulating workers or timers.
6. Leave during startup without a late response reopening playback.
7. Reach EOF without permanent buffering.
8. Play an existing static sample afterwards.

Automated state tests do not replace the browser check. If headless browser tooling is unavailable, explicitly mark visual verification pending until manually checked. No implementation, browser result or deployment is claimed by committing this plan.

## Browser references

- Same-origin policy: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Same-origin_policy
- requestAnimationFrame and hidden tabs: https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame
