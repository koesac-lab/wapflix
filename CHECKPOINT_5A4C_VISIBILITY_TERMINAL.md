# 5A.4C — visibility and terminal handling

Prepared 2026-10-25. Builds on the locally tested 5A.4B bridge:
08052b7f860e2ea4a2b26201ede3dd053f355b6c (15,931 bytes).
At review time GitHub main still had 5A.3B. Keep the applied local A/B files;
this package is not an instruction to reset them to remote main.

## Scope and behaviour

Runtime: handset-live.js and a narrow error-propagation change in stream-source.js.
No server, worker, media source, lease, Host/Origin/CSP, catalogue or Docker changes.

- Hiding now pauses immediately instead of returning to navigation. Hold smooth
  position and presented frame. Preserve pause intent even before Start ack.
- Existing heartbeat interval remains a single 250 ms best-effort timer. Browser
  throttling/suspension can stop its delivery; no lease survival is promised.
- If a playing poll is in flight at hide, request one current-intent follow-up
  after it finishes, without starting another interval or overlapping polls.
- On return, remain paused. Require a current visible-session pulse before
  accepting explicit Resume. A visibility epoch prevents an old pre-hide poll
  from satisfying that check. CHECK/Check session labels become RESUME only
  after successful validation. No automatic Resume, worker restart or seek.
- Clock guard handles a hidden flag observed before visibilitychange dispatch.
- pagehide still attempts scoped Stop and returns to navigation. Neither fetch
  delivery nor confirmed cleanup is guaranteed at browser exit; lease remains
  fallback. A bfcache return cannot silently restart playback.
- Ambiguous stopped/404/control disappearance: SESSION ENDED - RESTART. Never
  infer lease expiry from absence alone. A verified client_expired code can be
  labelled SESSION EXPIRED, but the current backend often exposes only neutral
  missing-session information; this patch does not invent an expiry reason.
- Timeout: TRANSPORT TIMEOUT. Explicit conversion error status: CONVERSION FAILED.
- Adapter delta only: preserve explicit state=error as code=conversion_failed,
  and use neutral Session ended for an unclassified stopped fallback. Existing
  fencing, ownership, timeouts, warm readiness and rolling cache are unchanged.
- Error offers RESTART; natural EOF offers REPLAY. Both are explicit new Starts
  from the configured beginning, not a false position-preserving Resume. Back/
  Home remain safe alternatives. Labels cover physical controls as in 5A.4B.

## Previous tests are migrated, not removed

The installer changes only the saved visibility-policy loop in each of:
- tests/test_handset_live_bridge.cjs (34 tests)
- tests/test_handset_live_pause.cjs (29 tests)

Visibilitychange now asserts Pause/retained session; pagehide continues to assert
Stop/exit. The helper validates original test checksums from the installed
MANIFEST_5A4A.json and unique replacement anchors before writing. Unexpected
local test edits fail the entire preflight. Reapply recognizes the exact reverse
migration and is a no-op. No prior cases are deleted or skipped.

## Verification here

- Baseline A reconstruction matched its saved Git blob; B reconstruction used
  the exact prior edits and size. Real adapter source matched GitHub blob
  2ee9ebe129943721556c1094cfcc27839ee4ca56 before its one-block change.
- 27 isolated visibility/terminal tests passed.
- 4 bridge + real-adapter/scripted-fetch integration tests passed. These are
  not real HTTP, real FFmpeg or proof of browser background timer behaviour.
- 8 focused terminal-propagation tests against the actual adapter passed.
- 39/39 new tests total passed; JS syntax checks passed.
- The prior 101 handset cases, full adapter suite and real host/HTTP suites were
  not rerun in the isolated packaging environment. Run them locally below.
- No browser or N5105 throughput/worker result is claimed. 5A.4C browser/host
  acceptance remains pending; this package implements the gate, not its result.

## Apply after downloading the tar to the repo root

Stop the running preview first. Do not extract directly over the checkout,
which would bypass the test migrations and safeguards.

```sh
STAGE=$(mktemp -d)
tar -xzf wapflix-5a4c-visibility-terminal.tar.gz -C "$STAGE"
python3 "$STAGE/tools/apply_handset_5a4c.py" --root "$PWD"
python3 "$STAGE/tools/apply_handset_5a4c.py" --root "$PWD" --apply
```

Preflight checks local B, original adapter and original test checksums. It refuses
unknown files, unexpected local changes or colliding new paths. Originals are
backed up under .wapflix-patch-backups; the path is printed. It does not commit,
run tests, modify leases, restart the host or claim browser success.

Historical manifests are immutable patch snapshots, not current-tree inventories.
5A.4C adds its own manifest with explicit migrations; A/B are not rewritten.

## Run complete checkout regressions

```sh
node --check handset-live.js
node --check stream-source.js
node --test tests/test_handset_live_bridge.cjs \
  tests/test_handset_live_pause.cjs \
  tests/test_handset_live_navigation.cjs \
  tests/test_handset_live_visibility.cjs \
  tests/test_stream_source_terminal.cjs
node tests/test_stream_source.cjs
python3 -B -m unittest discover -s tests -p 'test_stream_source_http.py' -v
python3 -B -m unittest discover -s tests -p 'test_handset_fenced_preview.py' -v
```

The five Node suites should total 140 tests with unchanged prior packages.
That count is not a real-server/browser result. Do not skip the adapter or host
regressions merely because the new focused tests pass.

## Restart with the existing test source

```sh
python3 -m tools.handset_fenced_preview \
  --enable-fenced --enable-live \
  --video "$HOME/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4" \
  --start 30 --seconds 60 --port 8104
```

Retain previous trusted --allow-host/subtitle flags, then reload the browser.

## Browser/host acceptance — still pending

1. Play for several seconds, hide, return promptly. It must hold position and
   picture and remain Paused. CHECK may appear during return validation.
2. Explicit Resume continues the same healthy session, with no paused-time jump,
   new Start or new worker. Inspect /api/pulse paused flags and session IDs.
3. Hide during startup and buffering, then return. First picture may prefill,
   but no response may auto-start movement. Back/Home still cancel safely.
4. Pause after initial buffer eviction; verify paused=true reaches the server
   and generation parks within existing in-flight/look-ahead limits. This is
   not an instantaneous-zero-work promise.
5. Suspend the tab/browser long enough that heartbeat delivery actually stops
   and the existing lease can lapse, then return. A plain tab hide may continue
   heartbeats and keep the session healthy: do not equate elapsed wall time with
   proven expiry. Missing/ambiguous session -> neutral RESTART; no automatic
   replacement. Explicit Restart begins at source_start, not the old position.
6. Transport outage/timeout must remain distinct from verified conversion error.
   Do not claim SESSION EXPIRED merely because a request timed out.
7. Completed short tail: Pause -> hide/return -> Resume -> final frame/EOF.
8. Page exit/Back/Home during validation; live/static/live; repeat controls and
   labels across five handsets. Confirm bounded cache and no orphan worker/timer.

Use window.wapflixLive.snapshot() for read-only state/position/check diagnostics.
Actual worker ownership and lease validation still need server/network evidence.

## Save local work deliberately

This patch is not committed by the assistant. If A/B have not been committed,
include their intended source/tests/docs/helpers alongside C rather than staging
only the latest runtime and omitting its dependencies. Never stage tar files,
source media or backups. Do not force-push or reset unrelated changes.

## Rollback

Stop the preview. Restore all replaced runtime and migrated test files from the
backup path printed by the helper. Remove only new paths marked existed=false
in its installed-files.json. This restores 5A.4B and stop-on-hide. Restart the
previous host. Do not reapply A/B blindly over modified newer sources.

Next, after actual lifecycle acceptance: 5A.5A pure source-time caption selection.
