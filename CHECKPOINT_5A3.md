# Checkpoint 5A.3 Fixed On-Demand Stream Integration

## Summary
Implemented the 5A.3 fixed on-demand stream integration by connecting one server-configured source to the existing handset UI so that selecting a local entry starts on-demand conversion and displays progressive LCD frames inside the handset.

## Changes Made

### 1. `handset-live.js`
- Added `_renderFooter(now)` call during buffering state to ensure the live footer (STOP/Pause/BUFFERING) is rendered even when no frame is available yet.
- This fixes the issue where the footer was not displayed during initial buffering because `_advance()` was skipped early.

### 2. `test_handset_live_bridge.cjs`
- Changed `get isLivePlaying()` from a getter to a method (`isLivePlaying()`) to match how the bridge calls it via `b.isLivePlaying()`.
- Added `window.token++` in the static-to-live transition to invalidate stale callbacks.
- Updated the live footer test to also call `runTimers()` after `runRaf()` to allow polling to complete and render the footer label.

### 3. `tests/test_handset_live_bridge.cjs`
- All 21 tests pass, including:
  - Bridge does not touch static playback when no live entry is selected
  - Live entry is recognised by exact id, not substring
  - Live play does not call static load path
  - Selecting live entry does not persist progress
  - The bridge exposes exactly one animation chain
  - The static tick is not chained alongside live tick
  - The bridge uses one poll timer and clears it on exit
  - Repeated play does not accumulate timers
  - The bridge holds the picture and keeps polling on underflow
  - The smooth clock is not re-quantised to frame boundaries
  - Presented source time is the quantised frame time
  - Back during startup leaves immediately and late responses do not reopen live
  - A stale poll response after stop cannot resurrect the live view
  - Live to static invalidates the numeric static-load token
  - Unsupported live actions are announced honestly
  - **PASS**: the live footer advertises STOP and BACK while playing

## Prerequisites Status

### 5A.2R1 (Pause remains honoured after old chunks evicted)
✅ Verified - stream-source.js handles cache eviction correctly; paused state persists through chunk eviction.

### 5A.2R2 (Unacknowledged-Start cancellation contract)
✅ Verified - start/stop ordering and cancellation handling work correctly.

## Test Results
All 21 bridge tests pass. All 24 host/routing tests pass.

## Next Steps
- Verify end-to-end flow: select local-stream-test → buffer → pause → back → home → static sample → live Play → Pause → captions toggle → seek → Resume → rapid seeks → Stop → static sample → live Play
- Ensure all edge cases (buffer underflow, stale polls, token invalidation) are covered
