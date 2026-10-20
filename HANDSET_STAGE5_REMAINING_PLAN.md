# Remaining Stage 5: handset lifecycle, captions and seeking

Status: planning only. This document adds no runtime implementation, tests, deployment or validation claim. It complements HANDSET_5A3_PLAN.md without replacing or modifying that approved plan.

## 1. Roadmap and prerequisites

| Step | Only deliver this | Pass condition |
| --- | --- | --- |
| 5A.1 | Existing handset served over the LAN with static assets | Local phone UI and static playback work |
| 5A.2 | Independently tested browser source adapter | Adapter tests pass; no interface change |
| 5A.3 | One fixed on-demand entry inside the handset; Start/render/Stop | Converted frames appear inside the phone |
| 5A.4 | Pause/resume, navigation lifecycle and replacement handling | Position holds; leaving releases the worker; starting again works |
| 5A.5 | Source-time captions in the handset | Captions follow displayed frames through pause and buffering |
| 5A.6 | Handset controls connected to the M4A seek API | Rapid seeks and Stop cannot restore stale frames or captions |

The existence of earlier files or documentation is not proof that every checkpoint has passed on the host. Record actual local versions and results before continuing. 5A.3 remains a planned prerequisite until its acceptance gate passes. Do not start 5A.4 as a substitute for finishing the live start/render/stop connection.

Related documents: HANDSET_5A1.md, HANDSET_5A2.md, HANDSET_5A3_PLAN.md, LOCAL_STREAMING_M3.md, LOCAL_STREAMING_M4A.md and LOCAL_STREAMING_M4B.md.

## 2. Shared boundaries

- Keep one server-configured source, the current LCD profile and the existing extract limits. This stage does not remove the current maximum request length or add whole-library browsing.
- Preserve the single worker/session model, same-origin hosting, LAN access and existing capability/Host/Origin checks. No CORS bypass or public exposure.
- Preserve static playback and the public Pages build. Local-only scripts and the virtual live entry must not enter the public catalogue.
- Use one bridge playback clock, one animation chain and one active polling timer. The source adapter owns transport, not rendering or time advancement.
- Keep rolling memory bounded. No whole-video frame list, persistent disk cache or cache-reuse seeking.
- Do not add Plex, Docker, audio, quality switching, live ASCII mode, persistent live resume or autoplay-next.
- Reuse and extend saved modules instead of reconstructing M1-M4. Fix a discovered prerequisite defect separately with a focused regression test.
- Save each small implementation pass before advancing. Stage only intended source/test/docs files, not new source videos, full SRT files, capability tokens, backups, debug output or archives. Existing repository cleanup is a separate task.

## 3. 5A.4: playback lifecycle

### Goal and overlap with 5A.3

5A.3 already requires minimum Stop/Back cleanup. 5A.4 must verify and extend it, not introduce a second lifecycle controller. Its new feature is user-facing Pause/Resume plus robust interaction among buffering, navigation, replacement and visibility changes.

In the live view, Select/key 5 changes from Stop to Pause/Resume. Back still stops and returns; * still stops then goes Home. Static controls remain unchanged.

### State and intent contract

Separate user intent from transport readiness. A buffered frame does not imply that playback should run. Paused means the relative position, displayed frame and future caption time all hold. Resume changes intent without creating a new session or restarting FFmpeg.

| State | Select action | Back/Home |
| --- | --- | --- |
| Starting, before metadata | Stop/cancel | Stop/cancel and leave |
| Buffering with play intent | Pause | Stop and leave |
| Playing | Pause | Stop and leave |
| Paused | Resume | Stop and leave |
| Ended or unrecoverable error | Clearly labelled return/restart action | Leave safely |

Footer text and accessible labels must match the actual action on each handset. Do not show PLAY or RESUME when the action will silently restart from the beginning.

### Pause and buffering

- Freeze the existing bridge clock immediately on Pause. Keep the last frame visible.
- Continue foreground heartbeats with paused intent so the session lease remains valid.
- Reuse the adapter's initial prefill rule: a pause before the first picture must not prevent the target frame/buffer from being generated.
- Once warmed, pause generation using the existing API flag. Allow for one in-flight chunk and pipe buffers; do not assert instant zero work.
- Resume from the same position. If data is missing, remain in buffering until ready rather than advancing the clock or creating another worker.
- A paused final frame must not become a false buffering loop; preserve explicit EOF handling.

### Navigation and replacement

Capture the launch page and focus so Back returns to the correct details/collection rather than an unrelated Home screen. Invalidate bridge generations before asynchronous cleanup. The adapter's queue remains responsible for acknowledged ownership release.

Live-to-static, static-to-live, repeated Play and replay must leave only one active live source, timer and animation chain. Late callbacks cannot repaint a menu, change static playback or overwrite the state of a replacement session. Do not write live progress/completion into the static progress store.

### Visibility and expiry policy

5A.4 deliberately supersedes 5A.3's provisional stop-on-hide policy: hiding the page pauses live playback immediately. Returning to a still-valid session leaves it paused until the user explicitly resumes.

Do not assume background heartbeat timers always run. If the inherited lease expires, show SESSION EXPIRED and offer an explicit restart from the configured beginning. Do not claim a position-preserving resume or silently seek; that recovery is not implemented in 5A.4. Do not weaken the server lease merely to hide the issue.

Stop, Home and page exit still release the navigation. A best-effort beacon and the existing lease remain fallback mechanisms, not proof of confirmed cleanup after network failure.

### Physical control identity

Resolve semantic actions from the actual keyboard/DOM input, not only the final numeric key value. Arrow-up, a physical rocker/roller and numeric 2 must not accidentally become the same live action. Use a narrow local bridge action mapping/delegation; do not redesign the public handset controls. This distinction is required for captions and seeking in the following checkpoints.

### Small passes and gate

1. 5A.4A: state/intent tests and Pause/Resume; no caption or seek logic.
2. 5A.4B: navigation/replacement, model-specific action labels and timer ownership.
3. 5A.4C: visibility/lease expiry, live-server and browser acceptance.

Gate: pause for several seconds, resume without a new session ID/worker, leave during startup/buffering/playing, switch to static and start live again. Confirm correct focus, no stale repaint, bounded buffers and one timer/worker. Test expiry rather than only the happy path.

## 4. 5A.5: source-time handset captions

### Goal

Connect the already available SRT metadata to the actual frame displayed inside the handset. Do not rebuild the parser, download subtitles, add per-frame caption requests or attach the diagnostic DOM caption panel below the phone.

### Timebase contract

M3/M4 metadata uses absolute source seconds. Select cues using the presented frame's sourceTime from the adapter, not wall time, an uncommitted playback target, request completion time or a second offset calculation.

- Cue start is inclusive; cue end is exclusive.
- Matching is quantised to the actual video frame rate. No audio-sync or sub-frame accuracy claim.
- A held frame during pause/rebuffering holds its caption, including at a missing-chunk boundary.
- Do not add source_start twice or compare source-time cues with static clip-relative subtitles.

### Presentation and controls

Render through the existing handset text style/palette and wrapping constraints, not a second external player. Use a small pure cue-selection helper if needed, with the bridge owning display integration. Keep the picture unchanged when caption visibility toggles.

- Numeric key 2 toggles captions only in live playback. Physical scroll controls/ArrowUp must not accidentally toggle them. Menus and static playback retain their current behaviour.
- Default live caption preference is on when the page loads. Keep this page-local preference across live plays, pauses and seeks until reload; do not overwrite static caption preferences or introduce persistent settings in this checkpoint.
- Missing track, no cues in the extract and malformed-cue warnings must remain distinct. An empty cue list is not a playback error.
- Use the existing compact subtitle area, bounded wrapping and a sensible line limit. Preserve overlap order and avoid duplicate repeated lines. Do not expand into a general typography/layout project.
- Treat caption content as text. Debug/accessibility DOM output uses textContent, never innerHTML. Do not announce unchanged text on every animation frame.

### Lifetime and races

Caption metadata belongs to the active source generation. Stop, replacement, errors and end-of-clip clear old text. A new session cannot inherit another session's cue list. A late response cannot restore old captions after leaving playback. Source file/SRT changes still require the documented server restart; no file watcher or track-selection API is added.

### Small passes and gate

1. 5A.5A: pure source-time cue selection tests, including clip offsets, boundaries, overlaps and empty tracks.
2. 5A.5B: handset rendering, numeric-key toggle and page-local preference.
3. 5A.5C: pause/buffering/replacement integration and browser checks.

Gate: pause in an active cue, toggle off/on while paused, force rebuffering, Stop/Start and switch to static playback. The cue must stay with the held picture, toggle without moving position, clear on exit and never execute markup. Verify actual handset wrapping and source-offset timing in a browser.

## 5. 5A.6: handset restart-seeking

### Goal and prerequisite gap

Connect handset seek controls to the existing M4A API, including paused seeking, captions and cancellation. The 5A.2 adapter currently has no seek() method: explicitly plan and test that extension first. Do not issue ad-hoc seek fetches from the handset bridge or create a second transport/lifecycle implementation.

This is restart-seeking only. Even a recently buffered target may restart conversion. Cached-position seeking, persistent cache and preview thumbnails stay out of scope.

### Adapter extension

Add a source-time seek operation to stream-source.js with a documented return contract. It must:

- Retain the navigation identity and original allowed range while clearing old visible metadata/chunks.
- Invalidate client generations immediately so old pulse/chunk replies cannot be adopted.
- Assign increasing safe-integer seek revisions and serialize lifecycle operations. Skip queued seek work that is already superseded instead of needlessly spawning it.
- Call /api/seek with navigation_id, revision and absolute source position. Do not call navigation-stop before an ordinary seek: that would invalidate the navigation being sought.
- Adopt the returned session ID, authoritative snapped source_start, frame geometry and caption window only for the latest generation/revision. Chunk indices restart at zero for that returned stream.
- Clear/rebuild the bounded rolling buffer; never mix chunks from old session IDs.
- Keep acknowledged ownership through failures so a new Start cannot bypass failed cleanup. A failed or expired navigation requires explicit recovery, not silent new-session creation.

Stop remains /api/navigation/stop. If Stop occurs during an in-flight seek, the final queued cancellation must release the current navigation and prevent late work/replies from restoring playback. A newer Start gets a new navigation ID; stale cancellation of the old navigation must not stop the new one. Preserve existing request timeouts and lease fallbacks.

### Seek intent and timeline

- A seek while playing resumes only after the new buffer is ready.
- A seek while paused shows the target frame but stays paused. Use initial prefill so paused generation cannot deadlock before the frame arrives.
- Preserve the page-local caption on/off preference. Clear old caption text immediately and display target captions only after the target frame is actually presented.
- If the page becomes hidden during a seek, do not auto-start playback when its response arrives.
- Treat the server-returned position as authoritative; M4A snaps on its grid relative to the configured extract start.
- Clamp controls to the allowed extract and last renderable frame, never exactly to an invalid EOF start. Do not expand beyond the configured extract or alter the engine duration limit.

The bridge's relative clock resets for the returned stream, but the user's displayed progress remains relative to the original configured extract:

source time = current stream source_start + current stream relative position

presentation position = source time - original range_start

presentation duration = original range_end - original range_start

Do not make the progress display jump back to zero or shrink its total duration after every seek. Distinguish EOF from buffering, including one-frame tails.

### Handset control mapping

Retain the existing handset convention: numeric 4/6 seek backward/forward five source seconds. The diagnostic viewer may keep its separate ten-second buttons. Keep labels/accessibility text consistent with the actual handset increment.

Select/key 5 remains Pause/Resume from 5A.4. Numeric 2 remains captions from 5A.5. Back/Home remain cancellation/exit. Quality and ASCII switching are still unavailable for the fixed live profile.

Confirm physical rocker/roller/keyboard mappings against the actual current DOM and model API. In particular, 7110 roller movement during live playback must not be routed through the numeric-2 caption shortcut. Use the local semantic-action mapping established in 5A.4; preserve model behaviour outside the live view. Do not add a desktop seek slider or duplicate controls outside the phone in this milestone.

### Small passes and gate

1. 5A.6A: adapter seek extension with mocked ordering, cancellation and cleanup tests; no UI change.
2. 5A.6B: bridge position/intent/caption reset and source-time progress accounting.
3. 5A.6C: handset control mapping and live-server/browser regression checks.

Gate: forward/back seeks while playing and paused; rapid repeated seeks; seek then immediate Stop/Home; seek then new Start/static selection; hidden-page seek; timeout/stale 409 response; final-frame target. Latest intent must win, captions must match the presented target frame, and superseded workers must be reaped before replacement.

## 6. Cross-checkpoint failure matrix

| Situation | Required result |
| --- | --- |
| Pause before first frame | Bounded prefill, target picture, no clock advance |
| Pause during rebuffering | Remain paused when more data arrives |
| Hidden page with valid lease | Pause; remain paused on return |
| Hidden page after lease expiry | Clear expiry/restart state; no false resume |
| Back/Home during Start | Leave immediately; reject late UI work; clean acknowledged ownership |
| Rapid seeks or out-of-order response | Latest generation/revision only |
| Stop while seek is pending | Navigation invalidated; no late frame/caption resurrection |
| Old cancellation after a new Start | New navigation remains unaffected |
| Cleanup request fails | No silent replacement worker; explicit error and lease fallback |
| End of stream or partial final chunk | Final picture/completion, not infinite buffering |
| Static item opened after live | Original static clock, controls and preferences work |

## 7. Test and release discipline

Each sub-pass should normally touch one or two implementation files plus focused tests. Record the exact changed files, baseline versions, test commands/results, known limitations and next gate. Do not claim a passed test solely because a file exists or a previous checkpoint passed.

Use layered validation:

1. Pure adapter/cue/state tests with controlled timing and transport.
2. Real HTTP/FFmpeg integration with generated footage and deterministic SRT cues.
3. Browser interaction inside the actual handset, including all five model control layouts.
4. Manual verification on the N5105/LAN setup, including buffering and Stop/restart.

Keep fake-DOM tests, real-browser tests, host throughput and production/security validation clearly distinct. If browser tooling is unavailable, mark that gate pending rather than bundling an unverified completion claim. Screenshots alone do not prove worker cleanup or timing.

Check current regression suites for M1-M4, 5A.1/5A.2 and the completed 5A.3 connection where shared behaviour is affected. Keep a working fallback entry point and make it easy to revert only the current narrow checkpoint. No public Pages script/catalogue changes without a specific separate requirement.

Proposed code locations are the established handset-live.js controller, stream-source.js adapter, a small source-time caption helper if useful, and focused tests. Do not create new server generations or copy entire earlier stacks for each feature. Keep backend changes isolated to a proven defect or missing API requirement.

## 8. Stage 5 completion gate

Stage 5 is complete only when one fixed on-demand source works inside the handset with Start, Pause/Resume, source-time captions, restart-seeking, Back/Home and reliable replacement/cleanup, while static playback remains intact.

Demonstrate the full sequence: Play -> Pause -> caption toggle -> paused seek -> Resume -> rapid seeks -> Stop -> static sample -> live Play again. Repeat across the supported handset controls, exercise a slow connection/forced delay and verify worker/timer/cache bounds.

The final record must list what was actually tested on the host/browser and what remains limited. Docker, Plex/library browsing, persistent resume, cache-reuse seeking, new qualities, public authentication and audio remain later milestones, not implied Stage 5 functionality.
