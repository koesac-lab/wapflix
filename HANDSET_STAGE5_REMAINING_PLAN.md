# Remaining Stage 5: reviewed lifecycle, captions and seeking roadmap

Status: reviewed plan, 2026-10-20. Documentation only; no runtime fixes, implementation or new host/browser test result is claimed. This revision complements HANDSET_5A3_PLAN.md and incorporates the subsequent code/contract review.

## 1. Roadmap

| Step | Scope | Pass condition |
| --- | --- | --- |
| 5A.1 | Local handset with static assets | LAN phone UI/static playback work |
| 5A.2 | Independent browser source adapter | Adapter tests pass; no UI change |
| 5A.2R1 | Persistent per-stream readiness correction | Pause remains honoured after old chunks are evicted |
| 5A.2R2 | Unacknowledged-Start ordering/cancellation contract | Delayed old work cannot replace or resurrect newer/cancelled intent |
| 5A.3 | One fixed live entry; Start/render/Stop | Progressive frames inside the handset, static playback preserved |
| 5A.4 | Pause/Resume and lifecycle | Position holds; navigation/replacement/expiry are safe |
| 5A.5 | Source-time handset captions | Captions follow presented frames through pause/buffering |
| 5A.6 | Handset restart-seeking | Latest seek wins; Stop prevents stale restoration |

Files/docs existing is not proof of host acceptance. Verify actual local versions, including local-only work, before each pass. Finish the reviewed prerequisites and 5A.3 before using later features to compensate for a missing basic connection. Related documents: HANDSET_5A1.md, HANDSET_5A2.md, LOCAL_STREAMING_M3.md, LOCAL_STREAMING_M4A.md and LOCAL_STREAMING_M4B.md.

## 2. Review prerequisites: separate fixes, not implied completed work

### 5A.2R1: readiness must survive eviction

The reviewed stream-source.js determines startup warmth from cached chunks 0 and 1. A focused harness using its poll method reproduced: initial cache 0/1/2/3; advance from source 30 to 34; cache becomes 1/2/3/4/5; a subsequent paused=true request sends paused=false. This is a confirmed logic defect in the reviewed algorithm, not a claim that it was observed on the user's host.

Plan a small adapter fix: readiness persists for the current stream generation after initial prefill. Reset it on Start/replacement/seek, not normal cache eviction. Do not retain old initial chunks forever merely to satisfy the predicate.

Regression gate: advance far enough to evict chunk 0, pause and assert the outgoing API flag remains true and generation parks within existing in-flight/look-ahead bounds. Also preserve paused-before-first-frame prefill, partial completed clips and reset-on-new-stream behaviour.

### 5A.2R2: fence unacknowledged Starts

A controlled timeout/late-handler simulation using the adapter lifecycle showed the client owning a newer navigation while a delayed old Start replaced it server-side. The reviewed Start API creates a new navigation without pre-acknowledgement client request ordering/cancellation. Client serialization and fetch abort alone do not establish the desired server-side guarantee. This is a reproduced protocol risk, not a reported production/mini-PC incident.

Before handset integration, specify a narrow client/server identity and ordering contract for Start work before its navigation ID is acknowledged. If required, add server generation fencing and cancellation/tombstone handling as a separate compatibility-tested API patch. Do not prescribe unreviewed endpoint names in this roadmap, weaken Host/Origin checks or rebuild the backend.

Required tests: Stop before Start acknowledgement; timeout then a newer Start; delayed old handler arriving/finishing after newer intent; cancelled request retry; stale cancellation after a fresh Start. An old request must not stop newer playback or spawn abandoned replacement work. Verify both controlled transport ordering and real HTTP behaviour where applicable.

The inherited lease is eventual cleanup for unreachable work, not a guarantee that old Starts cannot supersede newer ones. Do not declare this gate passed by waiting for expiry. Neither prerequisite is fixed merely by committing these plans.

## 3. Shared boundaries and timing contract

Keep one server-configured source, current LCD profile, configured extract bounds and existing maximum request length. No Plex, Docker, audio, new qualities, live ASCII mode, public authentication, persistent live resume, autoplay-next, persistent cache or cache-reuse seeking. Preserve static/Pages functionality and local-only entry/script isolation.

One bridge clock, one animation chain, one active polling timer and a bounded rolling source cache. The adapter owns transport, not time or rendering. Reuse saved modules. An actual prerequisite defect gets its own small fix and regression test.

Maintain three distinct values:

- Relative playback position: smooth position within the current stream. Do not re-quantise this clock on every render.
- Presented source time: actual frame timestamp, authoritative for captions and held-picture state.
- Original-extract progress: source position minus the original range_start, with duration original range_end minus range_start.

On every stream, requested source time equals current source_start plus current relative position. After seeking, reset only the current-stream clock, not the user's original-extract progress basis.

Normal buffering targets remain four seconds at startup and about two seconds on recovery. Both need an EOF-tail exception: if conversion is complete and playable contiguous footage remains, play the shorter tail instead of waiting for a target that cannot be reached. Test sub-chunk and one-frame tails while rebuffering.

## 4. 5A.4: Pause/Resume and playback lifecycle

5A.3 already requires minimum Stop/Back cleanup. Extend and verify that controller rather than creating a second lifecycle implementation. New work is Pause/Resume plus safe navigation, replacement and visibility interactions.

### State and controls

Separate user intent from readiness. Paused holds relative position, frame and eventual caption time. Resume changes intent without a new session or FFmpeg restart; an already completed conversion can resume from retained data without creating a replacement worker.

| State | Select/key 5 | Back/Home |
| --- | --- | --- |
| Starting, before metadata | Stop/cancel | Stop/cancel and leave |
| Buffering with play intent | Pause | Stop and leave |
| Playing | Pause | Stop and leave |
| Paused | Resume | Stop and leave |
| Ended/error | Honestly labelled return/restart | Leave safely |

Footer/accessibility labels must match every model's actual action. Do not present a restart-from-beginning as Resume.

### Buffer and lifecycle rules

Freeze the bridge clock immediately on Pause. Keep foreground heartbeats with paused intent. Preserve the corrected initial-prefill exception so the first frame can arrive before parking the worker. Once warmed, honour pause after ordinary eviction; allow one in-flight chunk and pipe buffers, not an instant-zero-work promise.

Resume at the same position. If more data is needed, buffer without advancing or creating another session. Apply the short-tail/EOF rules from section 3.

Capture the launch page/focus. Back/Home, repeated Play, replay and live/static switching invalidate bridge generations before asynchronous cleanup. The source queue owns acknowledged release. No stale repaint or state replacement, duplicate timers/animation loops, competing live sources or writes into static progress storage. The Start prerequisite also applies to these flows.

### Visibility and terminal reasons

Once 5A.4 passes, it replaces 5A.3's provisional stop-on-hide policy: hiding pauses immediately; returning to a valid session leaves it paused until explicit Resume. Background heartbeat timers may stop, so lease expiry remains possible. Do not weaken the lease to disguise this.

Only show SESSION EXPIRED when a reason is verified. Current generic stopped/404 responses do not by themselves distinguish expiry, explicit stop or replacement. Either add a narrow structured reason or use SESSION ENDED - RESTART when ambiguous. Transport timeout and conversion failure remain separate.

Recovery from an ended/expired session is an explicit restart from the configured beginning. No false position-preserving resume, silent seek or automatic new worker. Page exit still attempts cleanup; beacons/lease are fallback mechanisms, not confirmed network delivery.

### Input identity

Freeze an explicit input-origin/action matrix before wiring controls: numeric keypad, keyboard arrows, physical rocker, and 7110 roller click/movement/wheel. Do not map all of these solely by their final numeric digit. Use a narrow local bridge action layer so physical Up cannot later toggle numeric-2 captions or accidentally seek; static handlers remain delegated unchanged.

### Passes and acceptance

1. 5A.4A: intent/state and Pause/Resume tests only.
2. 5A.4B: navigation/replacement, input mapping, action labels and timer ownership.
3. 5A.4C: visibility/terminal reason handling and live-server/browser acceptance.

Gate: pause after buffer eviction, resume with the same session, pause while buffering and near EOF, leave during Start/play/buffering, switch to static and play live again. Verify focus, held position, cleanup, bounded memory, timer/worker counts and expiry recovery.

## 5. 5A.5: source-time handset captions

Connect existing SRT metadata to the frame actually displayed inside the handset. Do not rebuild the parser, download tracks, add per-frame caption requests or put the diagnostic DOM subtitle panel below the phone.

### Selection and presentation

M3/M4 cue times are absolute source seconds. Match using the presented frame's sourceTime, not smooth target time, wall time or response timing. Start is inclusive; end is exclusive. Matching is quantised to video frames, not an audio-sync or sub-frame guarantee. Never add source_start twice or mix source cues with static clip-relative timestamps.

Pause and rebuffering hold the caption with the held frame, including a missing-chunk boundary. Use a small pure cue selector if useful; the bridge retains display ownership. Render with existing handset text/palette, bounded wrapping and a sensible line limit. Preserve overlap order and suppress duplicate repeated lines without a typography redesign.

Numeric 2 toggles captions only in live playback. Physical scroll/ArrowUp is distinct under the 5A.4 matrix. Toggling does not change position or picture. Default live preference is on per page; preserve it across live plays, pauses and seeks until reload without changing static preferences or adding persistent settings.

Missing track, no cue in the window and malformed-cue warnings stay distinct; an empty list is not a playback failure. Treat all caption content as text; any diagnostic/accessibility DOM uses textContent, not innerHTML. Announce changed cues, not every animation frame.

### Lifetime

Cue metadata belongs to the active generation. Clear on Stop, replacement, terminal errors and EOF. Late responses cannot restore another session's text. Source/SRT edits still require the documented server restart; no track-selection API or watcher.

### Passes and acceptance

1. 5A.5A: pure selection tests for offsets, boundaries, overlaps and empty tracks.
2. 5A.5B: handset rendering, numeric toggle and page-local preference.
3. 5A.5C: pause/buffer/replacement and actual browser checks.

Gate: pause during a cue, toggle off/on without movement, force buffering at a cue boundary, Stop/Start and return to static. Text must match the presented frame, wrap correctly, clear safely and never execute markup.

## 6. 5A.6: handset restart-seeking

The current adapter has no seek() method. Add and test that transport operation before wiring handset controls. No ad-hoc parallel fetch implementation in the bridge. This remains restart-seeking even for recent targets; cached fast paths, persistent cache, thumbnails and desktop sliders are excluded.

### Source adapter contract

- Retain navigation identity/original allowed range while invalidating visible metadata, old chunks and client generations.
- Assign increasing safe-integer revisions; serialize lifecycle work and skip queued requests already superseded.
- Use /api/seek with navigation_id, revision and absolute source position. Do not navigation-stop before a normal seek; it would invalidate the navigation being sought.
- Adopt the returned session ID, snapped source_start, geometry and caption window only for the latest generation/revision. New chunk indices start at zero. Never mix session caches.
- Preserve acknowledged ownership on errors so failed cleanup cannot be bypassed by Start. Existing timeouts and reviewed Start fencing still apply.

Stop uses /api/navigation/stop. A Stop during seek must invalidate that navigation and release any replacement, even when responses are pending. A new Start creates a new navigation ID; stale cancellation cannot stop it.

### Rejection handling

HTTP 409 is not automatically harmless. Ignore only responses already known to be superseded by local generation/revision. A 409 for the latest active operation must leave the seeking state, show an actionable error and allow safe cleanup/restart. Never suppress every 409 or leave an endless seeking overlay.

### Intent and time

A playing seek resumes only after buffering. A paused seek presents the target but stays paused, using corrected prefill before parking. Preserve caption preference; clear old text immediately and show target cues only when a target frame is presented. A hidden page cannot auto-start when the seek finishes.

Clamp to the original configured range and last renderable frame, never an invalid EOF start. The server-returned snapped position is authoritative. Test fractional offsets, boundary rounding and one-frame tails. Do not extend extract limits.

Reset current-stream relative position for the returned source_start, but preserve the section 3 progress basis. Progress must not restart at zero or shrink its total duration after every seek. EOF must not become buffering.

### Handset mapping

Numeric 4/6 retain the handset convention of minus/plus five source seconds; diagnostic buttons may remain ten seconds. Labels and accessibility text must agree. Select/key 5 stays Pause/Resume; numeric 2 stays captions; Back/Home cancel and leave. Quality/ASCII changes remain unavailable.

Use the explicit model/input matrix from 5A.4. In particular, 7110 roller movement must not pass through the numeric-2 caption action. Preserve menus/static behaviour and avoid duplicate controls outside the phone.

### Passes and acceptance

1. 5A.6A: adapter extension with ordering, timeout, cancellation, active/stale 409 and ownership tests.
2. 5A.6B: bridge position/intent/caption reset and progress accounting.
3. 5A.6C: model mapping plus real-server/browser regressions.

Gate: forward/back playing and paused seeks, rapid repeats, seek then Stop/Home, seek then new Start/static, hidden seek, latest and stale rejection, fractional/boundary/final-frame targets. Latest intent wins; picture/caption agree; superseded workers are reaped before replacement.

## 7. Failure and regression matrix

| Situation | Required result |
| --- | --- |
| Pause before first picture | Bounded prefill, held clock |
| Pause after original chunks are evicted | Server receives paused=true |
| Completed tail shorter than buffer target | Play remaining frames and finish |
| Hidden page with surviving lease | Remain paused on return |
| Unknown stopped/404 reason | Neutral ended/restart message, not invented expiry |
| Start timeout followed by delayed old work | Reviewed server ordering/cancellation protects latest intent |
| Back/Home during Start | Immediate UI exit; no late resurrection; ownership cleanup |
| Old seek response | Ignore only when locally superseded |
| Latest seek 409 | Exit seeking, expose error and cleanup |
| Stop during seek or cancellation after new Start | Cancel correct navigation only |
| Cleanup fails | No silent replacement; explicit error/fallback |
| Static playback after live | Original controls, clock and preferences work |

## 8. Delivery and completion discipline

Normally touch one or two implementation files plus focused tests per pass. Save each pass before advancing; record file versions, exact tests/results, limitations and next gate. Do not rebuild M1-M4 or equate file presence with success. Stage only intended source/test/docs, not new source media, full SRTs, tokens, backups, debug output or archives; existing repository cleanup is separate.

Validate in layers: controlled adapter/cue/state tests; real HTTP/FFmpeg with generated video and deterministic SRT; real browser inside all five handset control layouts; N5105/LAN manual acceptance with forced delay and Stop/restart. Distinguish mocked, browser, host throughput and security results. Browser acceptance stays pending if not run. Screenshots alone do not prove cleanup or timing.

Keep current M1-M4, 5A.1/5A.2 and completed 5A.3 regressions where shared behaviour changes. Preserve fallback entry points and narrow rollback. No public Pages catalogue/script changes unless separately required.

Expected code locations remain handset-live.js, stream-source.js, a small cue helper if useful and focused tests. Backend changes are restricted to isolated reviewed prerequisite fixes or demonstrated defects, not a fresh server per feature.

Stage 5 completion requires one fixed source inside the handset with Start, Pause/Resume, source-time captions, restart-seeking, Back/Home and reliable replacement/cleanup, while static playback remains intact. Demonstrate Play -> Pause -> caption toggle -> paused seek -> Resume -> rapid seeks -> Stop -> static sample -> live Play, across model controls and with buffering/timeout cases. Record actual browser/host results and limits. Docker, library browsing, persistent resume, cached seeking, qualities, public authentication and audio remain later milestones.
