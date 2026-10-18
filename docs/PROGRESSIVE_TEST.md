# Progressive local playback experiment

This additive patch contains tools/progressive_test.py, its tests and this document.
It changes no existing Pages build, handset, navigation or offline exporter files.
It uses Python 3.10+ standard library and FFmpeg/ffprobe, no pip dependencies.

## Apply and run

From the WAPFLIX repository root, with the archive copied here:

    tar --keep-old-files -xzf wapflix-progressive-test.tar.gz

Stop on an extraction error; do not force overwrites. The prior offline exporter
remains the known-working fallback. Start the new server (separate port from 8099):

    python3 tools/progressive_test.py --bind 0.0.0.0 --port 8100

The default source is the already downloaded MP4:
~/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4
The extract starts at 30 seconds and lasts 60 seconds. Override with --video,
--start and --seconds (maximum 120). Fixed quality: 40 columns, 6 fps,
aspect-correct rows for 6x8 cells. Software decoding only.

Open http://YOUR_SERVER_LAN_OR_TAILSCALE_IP:8100 and press Start.
For server/browser on the same machine use http://127.0.0.1:8100.
The listening address 0.0.0.0 is not the address to browse from another device.
If port 8100 is busy, change the port in both places. Ctrl-C stops the server
and reaps its FFmpeg process. No second static HTTP server is needed.

IMPORTANT: 0.0.0.0 listens on all interfaces. Use only a trusted LAN/Tailscale
network with appropriate firewall rules. No login or public-access protection
is implemented. Do not forward this port or expose it through a public tunnel.
The default bind without --bind is loopback-only. API tokens reduce cross-site
request risks but are NOT user authentication. This is a private experiment.

## Acceptance checks

1. Leave artificial delay at 0 and press Start. Watch real ASCII motion.
2. Pause/Resume should freeze/resume the playback clock and pause generation
   after a bounded amount of already in-flight work.
3. Press Stop. Generation and playback stop; another Start begins at the start
   of the configured extract (not the source file's beginning).
4. Set artificial delay to 3 seconds and Start again. Each two-second chunk
   now costs at least three seconds: observe buffering and automatic recovery.
5. To make the under-run very obvious, set delay to 5 seconds. Initial buffering
   takes roughly 10 seconds; playback should later stall and resume as chunks
   arrive. The media clock must not run on during buffering.
6. Watch generated chunk count while playback starts. The default zero-delay
   path may convert faster than you can see, so use delay for this check.
7. Stop or navigate away. The page sends a best-effort cancellation beacon;
   if a browser/tab disappears without sending it, a 10-second lease timeout
   stops the worker. Cancellation is not universally immediate on abrupt close.

## Architecture and bounds

One FFmpeg process supplies grayscale frames incrementally. Python holds at most
one chunk of uncompressed ASCII frames, gzip-compresses independent two-second
JSON chunks, then publishes the complete bytes under a lock. HTTP Content-Encoding
is gzip, so the browser decompresses exactly once. Pending chunks return 204.
Final partial chunks and actual EOF are explicit; no partial JSON is served.

The browser starts after two chunks (four seconds) are decoded, or after a shorter
complete clip is available. It prefetches four chunks from the current position
and drops older decoded data, retaining the previous chunk. The worker stops
reading from FFmpeg when roughly 30 seconds ahead; bounded subprocess pipes may
contain additional data. Old compressed chunks are pruned on playback heartbeats.
No disk cache, pre-converted full episode or whole-episode frame array is built.

Only one session is supported. Start replaces the previous worker. The HTTP
server and worker are separate threads; a lease-monitor thread kills blocked or
abandoned work, including while FFmpeg is producing no frames. Individual test
sessions are capped at 120 seconds, and a 300-second worker lifetime is a further
safety limit. Chunk frames are kept only in memory and dropped on stop.

The browser reports progress every ~0.7 seconds. Background tabs pause playback;
if browser throttling interrupts heartbeats for 10 seconds, the session may expire
and need a fresh Start. This behaviour is acceptable for this experiment, not the
final production lease policy. Reports display first-chunk latency including
artificial delay, not an inference from the earlier offline benchmark.

Only fixed application routes and the configured source are exposed. No arbitrary
client filesystem paths, directory listing, Plex tokens or source-media downloads.
No persistent cache, seeking, subtitles, audio, Docker, Plex, quality switching or
handset integration. Browser monospace cells are a test renderer, not the final
handset bitmap renderer. Existing Pages deployment remains independent.

## Tests and status

    python3 -m unittest discover -s tests -p test_progressive_test.py -v

Nine Python tests with generated real video cover early chunks, exact frame layout,
partial EOF, cancellation/process reaping, worker replacement, lease expiry,
backpressure/eviction, pause and HTTP gzip/pending/auth handling. Integration tests
skip explicitly if FFmpeg tools are missing. Run the full repo suite separately.

Headless Chromium checks passed for initial buffering, playback before conversion
completion, forced underrun with frozen clock, automatic recovery, pause/resume,
Stop, navigation-away cancellation, final completion and no uncaught JS errors.
Python and JavaScript syntax checks passed. These are isolated generated-fixture
tests: the N5105, actual downloaded source, real-device browsers, complete existing
repo test suite and deployed GitHub Pages have not been validated by this package.

Do not commit the archive or generated runtime media. Review and stage only the
three patch files if committing locally. No remote commits are made by this kit.
