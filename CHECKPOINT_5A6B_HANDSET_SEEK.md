# 5A.6B — handset restart-seeking

Prepared against main d2b2cd0040782335821e26f7c46748df5b739e65.

## Runtime changes

- Numeric 4/6 seek -/+5 source seconds. Rocker, arrows and roller movement remain navigation-only and unavailable in live mode.
- UI intent coalesces while one adapter seek is in flight. A stale success is not presented; the next seek uses the latest accumulated destination.
- A failed in-flight seek fails closed even if its UI target was superseded. No silent restart or retry after an ownership failure.
- Paused seeks prefill a target frame and remain paused. Select during a seek changes post-seek play intent. Hidden pages cannot auto-resume.
- Clear old picture and captions on seek. Preserve the page-local caption preference and select captions from the presented source frame.
- Clamp to original extract bounds/last frame; preserve original-extract progress in the diagnostic snapshot. Replacement-relative position resets to zero.
- Back/Home/pagehide/static replacement invalidate pending UI work. Keep one existing RAF chain and at most one active poll interval.

## Explicit 5A.6A prerequisite repair

The old seek implementation calculated a destination but sent /api/start with no position. The fenced server's begin() restarts at its configured start. It did not provide true position-based restart-seeking.

This patch changes only seek() in stream-source.js to call existing /api/seek with navigation_id, seek revision and clamped absolute position. Keep the original Start intent/owner during seek; never cancel that owner before seeking. Existing Stop/Start cancellation tombstones the original owner and all pending/replacement seeks. No server API or converter changes.

Server-returned metadata/source_start is authoritative. Validate navigation, revision, range, fps and frame-grid position. Send the request once, without client pre-snapping, to avoid double-rounding fractional offsets. The returned result.frame is the frame index relative to the original range_start; replacement frameAt().frameIndex starts at zero.

## Regression correction

Remove numeric 4/6 only from the old unsupported-actions test. Its remaining unsupported-input assertions stay intact. New integrated tests exercise 4/6 through the real adapter, bridge and caption modules. The former 15-case adapter seek suite asserted replacement Starts; replace it with 17 cases for the actual /api/seek protocol, cancellation and ownership.

## Validation performed here

- 34 existing bridge regressions passed.
- 27 new bridge/adapter/caption integration cases passed against synthetic DOM and controlled fetch (including five simulated handset control layouts).
- 17 corrected adapter seek cases passed.
- Total: 78/78 controlled JavaScript tests passed.
- Syntax checks passed for changed JavaScript and the Python installer.
- Installer fixture checks are recorded in the archive validation report.

These are NOT real-browser, socket HTTP, FFmpeg, LAN throughput, worker-reaping or security acceptance results. The full repository suite was not run here. Run broader checkout tests below, then real-host/browser acceptance before declaring 5A.6 complete.

## Local checkout regression gate

```sh
node --test tests/test_stream_source_seek.cjs tests/test_handset_live_seek.cjs tests/test_handset_live_bridge.cjs
node tests/test_stream_source.cjs
node tests/test_stream_source_terminal.cjs
node --test tests/test_handset_live_pause.cjs tests/test_handset_live_navigation.cjs tests/test_handset_live_visibility.cjs tests/test_handset_captions.cjs tests/test_live_captions.cjs
python3 -m unittest discover -s tests -p 'test_fenced_api.py'
```

## Real-host/browser acceptance — not yet run

Use the existing fenced handset preview with its usual fixed video/subtitle arguments and --enable-fenced --enable-live. No Docker, Pages or public-access changes are part of this milestone.

1. Playing: 6 then 4 move forward/backward five seconds and continue only after buffering.
2. Paused: seek and confirm a target frame appears without resuming.
3. Rapid 4/6: final intended target wins; no intermediate caption/picture flashes.
4. Back/Home during a delayed seek: immediate exit, no late image/caption or worker resurrection.
5. Hide during a seek: target may prefill but stays paused on return until explicit Resume.
6. Beginning/end/fractional/one-frame tail: safe clamping and normal EOF, not endless buffering.
7. Captions follow displayed frame; numeric 2 preference persists. Physical navigation/roller movement never seeks or toggles captions.
8. Exercise all five models, then static playback, then live again. Check labels/focus, one timer/RAF, and worker cleanup on the real host.

## Commit after local and browser acceptance

```sh
git add -- handset-live.js stream-source.js tests/test_handset_live_bridge.cjs tests/test_stream_source_seek.cjs tests/test_handset_live_seek.cjs tests/helpers/fenced_seek_harness.cjs tools/apply_handset_5a6b.py CHECKPOINT_5A6B_HANDSET_SEEK.md MANIFEST_5A6B.json
git diff --cached --check
git diff --cached --stat
git commit -m "Add handset restart-seeking with fenced position-based transport"
git push origin main
```

Do not stage archives, backup directories, capabilities, source media or unrelated patch installers.
