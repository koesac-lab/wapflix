# 5A.2: standalone browser streaming source

Adds stream-source.js, tests/test_stream_source.cjs and this document. No existing server, handset, Pages, static preview or video assets are modified. There is intentionally no new page or URL in this checkpoint. The adapter is not loaded by the 5A.1 preview yet.

## Install and validate

Extract this archive into the repo root using tar --keep-old-files -xzf with its filename. Stop on an extraction conflict; do not overwrite unknown earlier work.

```sh
cd ~/wapflix
node --check stream-source.js
node tests/test_stream_source.cjs
```

Expected final line: 17 standalone adapter tests passed. These tests use fake HTTP responses, not a running server, FFmpeg or browser. Existing services can stay running. No conversion or uploads occur during the tests.

## Browser API contract for the next checkpoint

The classic script exports globalThis.WapflixStreamSource. CommonJS export is also provided for Node tests. Constructor options: token (required local-server capability), baseUrl (same-origin API root, default /), fetchImpl (optional injected transport), timeoutMs (default 10000).

Illustrative future integration, not a command to run on the current 8102 page:

```js
const source = new WapflixStreamSource({ token: SERVER_INJECTED_TOKEN });
const metadata = await source.start();
await source.poll({ sourceTime: metadata.source_start, paused: false });
const frame = source.frameAt(metadata.source_start);
const availableUntil = source.bufferedUntil(metadata.source_start);
await source.stop();
```

start() creates an M4A session and returns its metadata; it does not start a renderer or advance time. poll() sends the consumer's absolute source time, renews the session lease and fetches at most four chunks ahead. It keeps at most one previous chunk plus four current/ahead chunks. Concurrent polls coalesce; a later poll must supply the latest position/pause intent. Call poll repeatedly from the future owner (roughly the existing heartbeat cadence) while active, including during pause; the module creates no background polling timer itself.

frameAt(sourceTime) returns null for a missing frame, otherwise {hex, cols, rows, fps, frameIndex, sourceTime}. The returned sourceTime is the actual quantised frame time. bufferedUntil(sourceTime) returns the end of contiguous available footage, or the requested time if nothing is available. A partial completed clip clamps final-frame lookup appropriately. The adapter does not decide whether to play, buffer or render.

A paused initial poll temporarily permits bounded prefill until two chunks are available (or a short clip has completed), so the target image can be fetched without deadlocking the worker. Later paused pulses park generation. This does not advance a playback clock.

stop() clears visible client metadata/cache immediately, invalidates old polling generations and cancels its navigation server-side. Lifecycle requests are serialized: an acknowledged old Start is cleaned up before a newer Start can become active. Start itself is allowed to finish so its navigation identity can be released after Stop. Requests have a bounded timeout; if a Start never acknowledges, the server's inherited session lease is the fallback for unknown server work. Failed acknowledged cleanup retains ownership so a subsequent Start cannot bypass a failed Stop. Call stop() after a polling error; there is no automatic retry or error-recovery loop.

Getters: state (idle/starting/ready/stopping/stopped/error), error, metadata, status, retainedChunks. Metadata/status snapshots are shallow frozen. Caption metadata is carried through but not displayed or interpreted. No seek method exists yet; random jumps outside the retained window are not a substitute for the M4A seek protocol.

## Compatibility and next step

Uses the saved M4A start/navigation-stop endpoints plus inherited pulse/chunk endpoints. The API uses ordinary HTTP gzip Content-Encoding, so fetch(...).json() handles it; this is not the Pages explicit-.gz asset format. The token is passed by the caller and is never hardcoded, discovered from another origin or persisted by this module.

The 5A.1 preview on port 8102 and existing API on 8101 are different browser origins. Do not disable CORS/Host checks or point the current page at the other port. In 5A.3, the local host will serve the handset and API from the same origin and provide the capability. This milestone does not add that routing or token injection.

17 tests cover side-effect-free construction, start/frame/stop, rolling-cache bounds, paused prefill, poll coalescing, stale chunks/status, pending-Start cleanup, replacement ordering, malformed chunks/metadata, failed-stop ownership, partial final chunks, validation, timeout recovery, missing frames and browser same-origin enforcement. No real browser, live HTTP/FFmpeg, N5105 throughput or full repository regression result is claimed here.

Next checkpoint: one fixed live catalogue item, start/render/stop in the handset only. Keep captions, seeking controls, resume/catalogue expansion and Docker out of that first connection patch. Nothing in this archive is auto-committed or uploaded.
