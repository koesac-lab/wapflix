# 5A.4B — navigation, replacement, focus and live input labels

Prepared 2026-10-25. Builds on the locally applied 5A.4A patch, whose bridge Git
blob is cea962bff9dfb78ad3aae2d25b3aa4c959e6b396 (12,082 bytes). At review time
GitHub main still held 5A.3B, 5f2afc2149184930c5737d43ffddbf0999736ae6. The
installer intentionally refuses that older runtime: do not reset local 5A.4A.

The user reports the prior pass succeeded. This does not claim independent
verification of its full browser/worker acceptance matrix.

## Scope

One runtime file changes: handset-live.js. Add tests/test_handset_live_navigation.cjs,
this checkpoint, a checksum manifest, and a guarded apply helper. No theme.js,
streaming.js, static catalogue, host, adapter, fenced API or converter changes.
The 5A.4A tests and prior bridge test updates stay installed, not overwritten.

## Changes

1. Capture the launch control and launch accessibility summary. Back restores
   the existing launch screen and DOM focus immediately, without waiting for
   asynchronous cleanup. Disconnected, disabled or inert controls fall back to
   the stable left control. Home focuses the stable Home select control.
2. All static loads wait on pending or previously failed cleanup, including a
   static selection made AFTER leaving live with Back. A new explicit selection
   may retry Stop; failed cleanup cannot silently delegate static playback.
3. Only the latest queued static selection delegates after cleanup. A genuine
   later navigation/live Start cancels an older queued switch. Backlight alone
   is not navigation and no longer cancels the chosen load.
4. Stale cleanup failure announcements are generation-guarded so they cannot
   overwrite a newer navigation message.
5. Live-only labels now cover numeric controls, physical call/end, rocker and
   roller controls. Cancel/Pause/Resume/Return matches actual state. Numeric 2
   remains distinct from physical Up/roller movement. Unsupported controls are
   labelled unavailable with aria-disabled, but remain able to announce why.
6. Save/restore each overridden label and aria-disabled attribute verbatim on
   exit, preserving static behaviour. Drop detached model controls from the
   saved map so repeated model changes do not accumulate them.
7. A single narrow model-structure observer refreshes replacement buttons. It
   watches child lists and data-handset only, not the aria labels it writes.
   No new poll or animation chain is introduced.
8. Expose a frozen diagnostic inputMatrix beside the existing read-only snapshot.

## Deliberately unchanged

Pause/Resume intent, startup and completed-tail rules remain from 5A.4A. Hiding
still stops and returns; pagehide still attempts cleanup. Foreground polling
still uses one 250 ms interval. Visibility/expiry changes belong to 5A.4C.
No captions, seeking, persistent live progress, worker restart on Resume, public
exposure or Docker deployment is added. Existing adapter ownership/fencing
remains authoritative; a mocked Start cannot prove real worker ownership.

## Verified here

- Syntax check passed.
- 38/38 new isolated Node navigation/focus/control tests passed. Fixture model
  controls cover all five layouts' action classes, but these are NOT real DOM
  theme.js execution or visual browser results.
- Focused pending-Stop/static, backlight and stale-announcement regressions fail
  against the previous 5A.4A bridge and pass after this change.
- Full old 34 bridge + 29 Pause/Resume suites were not rerun in this turn;
  run all three suites in your complete local checkout with the commands below.
- No live HTTP/FFmpeg worker, real timer throttling, real-device focus or browser
  observer result is claimed. Existing real-server tests remain required.

## Apply after downloading the tar into the repo root

Stop the handset preview first. Keep the successful local 5A.4A files.

```sh
STAGE=$(mktemp -d)
tar -xzf wapflix-5a4b-navigation-controls.tar.gz -C "$STAGE"
python3 "$STAGE/tools/apply_handset_5a4b.py" --root "$PWD"
python3 "$STAGE/tools/apply_handset_5a4b.py" --root "$PWD" --apply
```

Preflight checks the 5A.4A bridge, unchanged adapter/navigation/theme versions,
required local test files, package checksums and collisions with new files.
It refuses unexpected edits, backs up replaced files, and supports no-op
reapplication. It does not commit, restart services or run tests for you.

## Tests in the complete checkout

```sh
node --check handset-live.js
node --test tests/test_handset_live_bridge.cjs \
  tests/test_handset_live_pause.cjs tests/test_handset_live_navigation.cjs
node tests/test_stream_source.cjs
python3 -B -m unittest discover -s tests -p 'test_handset_fenced_preview.py' -v
```

The three Node suites should report 101 tests if the preceding packages are
unchanged. Do not equate that count with browser or real-worker acceptance.

## Restart the working preview

```sh
python3 -m tools.handset_fenced_preview \
  --enable-fenced --enable-live \
  --video "$HOME/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4" \
  --start 30 --seconds 60 --port 8104
```

Keep any previously required --allow-host/subtitle arguments. Reload the page.

## Browser acceptance — pending

- Start from details or catalogue selection; Back returns to the right screen
  with the original control/focus. Home must not refocus a stale launch button.
- Repeat Start -> Pause -> model switch -> Resume -> Back on all five models.
- On 7110, wheel/roller movement never selects or toggles numeric-2 captions;
  press selects. Check keypad labels and unsupported announcements independently.
- Back during Start/buffering/playing/paused, then choose static immediately.
  Confirm Stop ownership cleanup and no old callback repaint.
- Choose two static loads while Stop is delayed; only latest intent proceeds.
  Toggle backlight during cleanup without losing the selected load.
- Live -> static -> live and terminal replay; one animation chain, at most one
  live poll timer, no orphan FFmpeg worker or static live-progress writes.
- Verify static labels/controls/preferences restore after changing models live.
- Hiding still stops. Do not test background retention as if 5A.4C were present.

## Saving both local passes

If 5A.4A is not yet committed, include its intended files when saving this pass:

```sh
git add -- handset-live.js \
  tests/test_handset_live_bridge.cjs tests/test_handset_live_pause.cjs \
  tools/apply_handset_5a4a.py CHECKPOINT_5A4A_PAUSE_RESUME.md MANIFEST_5A4A.json \
  tests/test_handset_live_navigation.cjs tools/apply_handset_5a4b.py \
  CHECKPOINT_5A4B_NAVIGATION_CONTROLS.md MANIFEST_5A4B.json
git diff --cached --stat
git commit -m "Add live pause-resume and harden handset navigation controls"
git push origin main
```

Do not stage downloaded archives, source media or patch backups. Historical
5A.3B/5A.4A manifests record their own patch snapshots; they are not rewritten.
Nothing was committed by the assistant.

## Rollback

Stop the preview, restore the replaced bridge from the backup printed by the
installer and remove only the newly installed paths marked existed=false in
its installed-files.json. This returns to local 5A.4A without resetting unrelated
work. Restart the previous host. Next pass: 5A.4C visibility/terminal handling.
