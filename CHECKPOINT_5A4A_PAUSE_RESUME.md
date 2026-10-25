# 5A.4A — Pause/Resume intent and state

Prepared 2026-10-25 against main:
- handset-live.js: 5f2afc2149184930c5737d43ffddbf0999736ae6
- tests/test_handset_live_bridge.cjs: 6c3da31242bda6464173084461ca87b496fe6ba9

The user reports the live handset path is working. This records that report,
not independent verification of every 5A.3C browser/worker acceptance case.

## Changes

Only runtime change: handset-live.js. The saved fenced host, adapter, conversion
engine, API, catalogue and static player remain untouched. Add 29 pause tests;
update three prior control expectations in the 34-test bridge suite because
acknowledged live Select now means Pause/Resume rather than Stop.

- Separate play intent from transport readiness; Paused is an active session.
- Select/key 5: cancel before Start acknowledgement; otherwise Pause/Resume.
- Back/Home still Stop and leave. Terminal Select still returns safely.
- Pause immediately holds the smooth clock and presented frame. Resume resets
  its wall-clock reference, without another Start or worker replacement.
- Polling remains one foreground 250 ms interval. Requests carry paused intent;
  the existing adapter owns its initial-prefill exception and server warmth.
- Paused-before-first-picture can show one initial frame; later chunks do not
  change the held picture. A separate startup-warm latch prevents that early
  picture from weakening the four-second startup readiness target.
- Completed conversion can remain paused; a completed short rebuffer tail can
  resume and drain through the final frame without waiting for impossible data.
- Footer/accessibility labels match STOP during Start, PAUSE while playing or
  buffering, RESUME while paused, and BACK for terminal states.
- Pause/Resume does not replace stream generations; asynchronous polls adopt
  the current user intent rather than restoring an older play/pause decision.

No captions, seeking, quality changes, Docker or persistence added.

## Explicit visibility boundary

This is 5A.4A only. Hiding the page still STOPS and returns, including from
Paused. Page exit still attempts Stop. Do not test background retention as if
it were implemented. The stop-on-hide policy changes in 5A.4C after separate
visibility/lease/terminal acceptance. 5A.4B covers remaining navigation/focus,
replacement/model/input checks; this pass preserves the existing local input
layer and supplies only labels needed by the new action.

## Verified in isolated Node harness

- Source reconstructed from GitHub and checked against the two Git blob hashes
  above before changing it.
- 34/34 bridge regressions passed after three explicit control updates.
- 29/29 new pause/intent tests passed.
- node --check passed.
- These use the saved mock DOM/adapter harness: no real browser, HTTP session,
  real eviction, FFmpeg worker parking, throughput or actual same-session server
  result is claimed by those tests. The existing adapter readiness/eviction
  regression suite and full host tests must still be run in the checkout.

## Apply from repo root after downloading the tar there

Stop the running handset preview first.

```sh
PATCH="$PWD/wapflix-5a4a-pause-resume.tar.gz"
STAGE=$(mktemp -d)
tar -xzf "$PATCH" -C "$STAGE"
python3 "$STAGE/tools/apply_handset_5a4a.py" --root "$PWD"
python3 "$STAGE/tools/apply_handset_5a4a.py" --root "$PWD" --apply
```

The helper checks package checksums and baseline source hashes before writing,
refuses unexpected local versions, backs up replaced files, and supports an
identical no-op reapply. It does not stop services, run tests or commit anything.
The historical MANIFEST_5A3B.json is not rewritten; do not reapply 5A.3B over this
new version. The new MANIFEST_5A4A.json describes this patch.

## Checkout tests

```sh
node --check handset-live.js
node --test tests/test_handset_live_bridge.cjs tests/test_handset_live_pause.cjs
node tests/test_stream_source.cjs
python3 -B -m unittest discover -s tests -p 'test_handset_fenced_preview.py' -v
```

## Existing test source / preview command

```sh
python3 -m tools.handset_fenced_preview \
  --enable-fenced --enable-live \
  --video "$HOME/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4" \
  --start 30 --seconds 60 --port 8104
```

Retain your trusted --allow-host or subtitle arguments if previously used.
Reload the browser after restarting the host.

## Foreground browser acceptance for this pass — pending

1. Play, pause, wait, resume: held picture/position and no jump or new session.
2. Pause before first picture and during buffering: bounded prefill, no auto-play.
3. Play beyond the initial chunks (at least six seconds), pause, verify current
   session /api/pulse has paused=true and conversion parks within existing
   in-flight/look-ahead limits; resume the same session. Mock tests do not prove
   real buffer eviction or instantaneous zero work.
4. Pause near EOF and resume through final frame and TRANSMISSION ENDED.
5. Back/Home while paused; static sample; live again. No orphan worker/timer.
6. Confirm labels/input on handset controls. Hiding still stops in this pass.

No GitHub commit or deployment has been performed by the assistant.

## Commit after local checks

```sh
git add -- handset-live.js tests/test_handset_live_bridge.cjs \
  tests/test_handset_live_pause.cjs tools/apply_handset_5a4a.py \
  CHECKPOINT_5A4A_PAUSE_RESUME.md MANIFEST_5A4A.json
git diff --cached --stat
git commit -m "Add 5A.4A live handset pause and resume intent"
git push origin main
```

## Rollback

Stop the preview. Restore replaced files from the backup path printed by the
installer, and remove only new paths marked existed=false in its
installed-files.json. Restart the prior host. Do not reset unrelated work.
