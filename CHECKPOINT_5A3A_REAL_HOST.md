# 5A.3A recovery: real same-origin handset host

Scope: host/static/API composition ONLY. Live catalogue entry and bridge execution
remain disabled until the bridge state/rendering recovery gate. This follows the
three small passes in HANDSET_5A3_PLAN.md, rather than enabling the known-defective
saved bridge merely because R2C now passes.

User reported the R2C rerun successful after isolating the timeout fixture on
2026-10-24. This is user-reported host evidence, not an independent browser run.
Save the successful R2C source/tests and its timeout correction in their own
checkpoint commit before staging this host pass.

Reviewed baselines:
- tools/handset_static_preview.py 2b1d146dffa5c562a98cc2feccebd775eb260d01
- tools/handset_live_preview.py cac9222a7e413c112469a25275ea180713a33d72
- handset-live.js d03114c51f460137e8b0004cf16e6bc6f7b9890d
- HANDSET_5A3_PLAN.md 259ac0af9b6f67cbe9afa118a8705eef6004c315
- CHECKPOINT_5A3.md eef29b01c59b5744c7dccde8436168ac83bfa31b
- docs/START_HERE.md 664af3c8d7b6768b03335d9ffe7910f6bd2b3e5e (older planning status)
The older START_HERE planning/status document has not been silently treated as
current runtime evidence; the subsequent user-reported implementation gates are
recorded above. This pass does not rewrite historical acceptance claims.

Adds ONLY:
- tools/handset_fenced_preview.py
- tests/test_handset_fenced_preview.py
- CHECKPOINT_5A3A_REAL_HOST.md

Architecture:
- Reuse the existing static Preview, safe allowlist, bootstrap and static dispatch.
- Reuse the accepted FencedApp and its GET/POST routes, not a second backend or
  proxy. Never import/call tools/handset_live_preview.py or simulated dispatch.
- Same HTTP origin serves the handset and the real fenced API. Default staged
  port 8104 keeps existing 8101/8102/8103 diagnostic fallbacks independent.
- One preview nonce is normalized across static/API/error/redirect CSP headers;
  exactly one CSP header per response. Capability remains distinct and is printed
  in the trusted terminal, NOT injected into global numeric token or catalogue.
- Static explicit-gzip asset semantics unchanged. API gzip remains HTTP-encoded.
- Required adapter/bridge files are allowlisted and validated before backend
  monitor creation. They are NOT loaded into the page yet.
- On-disk and served catalogue remain byte-identical, without local-stream-test.
- No arbitrary repository directories, source media, tools or backups published.
- Host/Origin/capability/request limits inherited; no CORS or proxy weakening.
- HEAD APIs reject without executing an operation or emitting a response body.
- No conversion at host construction or static browsing. One real configured
  source remains fixed server-side; explicit authenticated Start is required.

Actual delivery validation:
- AST syntax parsing of both new Python files.
- Nine isolated composition/routing tests passed with transcribed existing static
  serving functions and an API stand-in fixture. The stand-in is NOT included in
  this delivery and is NOT evidence that the real backend integration has passed.
- The delivered ten-test suite runs against actual repository components and
  includes a generated-video real FFmpeg/chunk/cancel test. That full suite has
  NOT been run here. No browser, LAN/TS, N5105 throughput or model-controls result
  is claimed. Static sample content in the fixture is test-only.

Apply from repo root with tar --keep-old-files; all paths are new. Do not overwrite
unknown local files on collisions. No existing R2C or runtime files are changed.

Gate on the mini-PC (FFmpeg/ffprobe required; a media skip is not a pass):

    python3 -m unittest discover -s tests -p 'test_handset_fenced_preview.py' -v
    python3 -m unittest discover -s tests -p 'test_handset_static_preview.py' -v
    python3 -m unittest discover -s tests -p 'test_fenced_api.py' -v
    python3 -m unittest discover -s tests -p 'test_stream_source_http.py' -v
    node tests/test_stream_source.cjs

The ten host tests cover bootstrap/static invariance; consistent nonce on root,
script, API and error; both HEAD boundaries; explicit-gzip static data; unchanged
catalogue; asset allowlisting; Host/Origin/capability/identity; trusted aliases;
missing script before backend creation; no probing on static access; real HTTP
gzip LCD chunk + confirmed cancellation sharing origin with static assets.
The media test uses a temporary generated FFV1 source, not private source media.

After automated gates pass, from repo root:

    python3 -m tools.handset_fenced_preview --enable-fenced --bind 0.0.0.0 --port 8104

Use the SAME --video/--start/--seconds/--srt or --no-srt arguments as your real
fenced API if not using defaults. For a hostname add --allow-host NAME (no port).
Open http://<mini-PC-LAN-or-Tailscale-IP>:8104/ on the phone. Confirm the ordinary
static handset and a static sample still work. There is deliberately NO live
entry. The real API is on this same port for automated/admin checks. This is
plain trusted LAN/Tailscale HTTP, not public authentication/HTTPS proxy support.
Do not publish the printed capability or forward this port publicly.

Save after pass: stage only the three added paths. Leave archives and R2C.patch
unstaged. Rollback: stop only this staged host and remove/revert these additions;
existing static/legacy/fenced entry points are unchanged.

Next gate: 5A.3B bridge recovery in isolation (actual state access, Start/Stop,
stale generations, one clock/animation chain/timer, frame clearing/aspect, held
buffering/short EOF tails, controls/static delegation). Only after that passes,
enable the virtual entry and run 5A.3C actual browser acceptance. Do not count the
old partial Pause implementation as a passed 5A.4 milestone; captions and seek
UI remain deferred. Host composition alone does not complete 5A.3.
