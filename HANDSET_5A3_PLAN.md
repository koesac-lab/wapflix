# Handset 5A.3: fixed on-demand stream integration plan

Status: reviewed plan, 2026-10-20. Documentation only: no implementation, test deployment or host validation is claimed. This revision incorporates the Stage 5 review and must be read with HANDSET_STAGE5_REMAINING_PLAN.md.

## 0. Blocking prerequisite gates

Do not begin the handset connection until these narrow prerequisites have their own fixes and regression results:

1. 5A.2R1: correct adapter startup readiness after rolling-buffer eviction. The current poll logic depends on chunks 0 and 1 remaining cached. A focused reproduction showed a later Pause requesting true but sending paused=false after chunk 0 was evicted. Readiness must persist for the current stream generation and reset only for a new/replaced/seek stream, not ordinary eviction.
2. 5A.2R2: resolve the unacknowledged-Start cancellation contract. A timeout/late-handler simulation showed the client owning a newer Start while an older delayed Start replaced it server-side. This is a demonstrated protocol risk in a controlled simulation, not a reported N5105 incident. Specify and test pre-acknowledgement request identity, ordering and cancellation; make any required server fence a separate narrow change. A lease is eventual cleanup, not a latest-Start-wins guarantee.

Detailed requirements and tests are in HANDSET_STAGE5_REMAINING_PLAN.md. Neither issue is fixed merely by committing this plan. Do not bury these fixes inside the handset bridge or weaken the acceptance criteria to conceal them.

## 1. Goal and scope

Connect one server-configured source to the existing handset. Selecting its local entry starts on-demand conversion and displays progressive LCD frames inside the phone. Support Start, buffering, frame presentation, Stop/Back, natural completion and errors. Preserve static playback and the M4 diagnostic fallback.

| Included | Deferred |
| --- | --- |
| One fixed local streaming entry | Plex/filesystem browsing |
| Same-origin handset and API | Docker/reverse-proxy deployment |
| Current 240-pixel LCD profile | Quality switching or live ASCII mode |
| Start/render/Stop and buffering | User-facing Pause |
| Back/Home cleanup and EOF | Caption display and seeking controls |
| Static playback unchanged | Live resume/progress persistence and autoplay-next |

Caption metadata may arrive but is not displayed yet. Do not expose controls that promise unsupported features. Keep the existing extract limits; this milestone does not add unrestricted whole-video playback or rebuild M1-M4.

## 2. Static clips are not rolling streams

The reviewed player.js reads clip.frames and derives duration from clip.frames.length / clip.fps. streaming.js also uses that duration for progress, completion and autoplay-next. Do not make a rolling stream impersonate a complete static clip.

Use a distinct live view, such as live-player, and keep clip unset for it. The bridge uses the 5A.2 source adapter, current canvas/controls and captured return screen. It bypasses static persistence/completion/autoplay logic. Static items delegate to the existing path unchanged. No dummy arrays, placeholder variants or growing whole-video frame list.

Reviewed source baseline: player.js d6f971a2b7487d286e0264a7b74a64ec3206a0ba; streaming.js 01aef733a4dbdf716f42f3f678b20427320b51d7; tools/handset_static_preview.py 2b1d146dffa5c562a98cc2feccebd775eb260d01. Check actual local versions before implementation; these are review records, not a claim that later files remain identical.

## 3. Same-origin host and security boundaries

The 8102 handset preview and 8101 API are different browser origins. Add a local entry point, provisionally tools/handset_live_preview.py on port 8103, instead of disabling CORS/Host/Origin checks. Existing fallback servers can stay independent.

| Route | Purpose |
| --- | --- |
| / | Existing handset with local-only integration scripts |
| /assets/catalogue.json | Served catalogue copy with one virtual live entry |
| Existing allowlisted frontend/asset routes | Static playback |
| /stream-source.js | Existing transport adapter |
| /handset-live.js | New bridge |
| /api/start, /api/pulse, /api/chunk | Existing streaming operations, with reviewed prerequisite fixes where required |
| /api/navigation/stop | Acknowledged navigation cleanup |

Reuse the M4 API/session implementation and 5A.1 static allowlisting. Do not serve the repository as a directory or expose source media, tools, backups or Git internals. Do not rewrite the public catalogue, Pages workflow or generated assets. Preserve LAN binding and explicit trusted hostname aliases.

Static .gz assets must still omit Content-Encoding because their player decompresses explicitly. API gzip chunks retain ordinary HTTP Content-Encoding. Test both.

### Capability and CSP

Inject capability/configuration in a namespaced local object. Never add a global token variable: the handset already uses a numeric token for static-load invalidation.

Use a consistent nonce for served bootstrap/configuration and its CSP header. Do not mix independent preview/backend nonces without reconciling headers. Capability data is dynamic, not committed, included in catalogue files or persisted in local storage. This is trusted-network development access, not public-user authentication. The browser cannot choose arbitrary source paths or URLs.

## 4. One virtual entry

Proposed local-only entry: id local-stream-test; title Local stream test; explicit playback type local-stream; source identity configured-test. It appears at Home -> Original Transmissions -> Local stream test -> Play.

Append only to the served catalogue copy. Keep the original static test entry and on-disk catalogue intact. The entry must not contain fake static variants or be recognised through an ID substring. Source selection stays server-configured.

Fail startup clearly if a required bridge/adapter is missing. Do not expose a broken live entry or add it to public Pages/standalone static preview.

## 5. Local-only bridge

Proposed script: handset-live.js. Script order: existing inline bootstrap, player.js, streaming.js, theme.js, sharing.js, stream-source.js, handset-live.js.

The bridge owns live-entry recognition, return-screen capture, adapter lifecycle, live state, polling, frame presentation, live-only controls and callback invalidation. It does not replace the catalogue/navigation system.

States: Idle -> Starting -> Buffering -> Playing; Playing can return to Buffering; EOF leads to Ended; active states can enter Error or Stopping and return to navigation. Ended/Error have a clear Back path. Re-entering Play creates a fresh session; no automatic retry or next-item start.

## 6. Clock, presented frames and polling

Keep three concepts distinct:

- Relative playback position: smooth position within the current stream, advanced by the bridge's single clock only when appropriate.
- Presented source time: timestamp of the frame actually drawn; authoritative for visual state and later captions.
- Extract progress: position relative to the original configured range; becomes important after seeking in 5A.6.

For this milestone: requested source time = stream source_start + relative playback position. frameAt() returns the actual quantised presented time. Do not repeatedly quantise the smooth clock itself to frame boundaries, double-add offsets or use request/wall time for display synchronisation.

Exactly one requestAnimationFrame chain must remain. The static tick must not also advance live position. Tests count scheduled callbacks. Reset timing references at view changes; freeze during startup, rebuffering and stopping.

Use one heartbeat/prefetch timer around the established 250 ms cadence, active only for the acknowledged live session and during buffering. Let the adapter coalesce requests. Clear it on exit; repeated Play cannot accumulate intervals.

For 5A.3 only, hiding the page stops live playback and returns to details. Do not depend on continued background rendering. 5A.4 explicitly replaces this provisional policy with Pause/Resume after that checkpoint passes.

## 7. Buffering and EOF

Startup target: four seconds of contiguous footage, with a short-completed-extract exception when at least one playable frame exists.

On underflow, hold the last image and position, show BUFFERING and keep polling. Normal recovery target is one two-second chunk. Crucially, if conversion is complete and less than that target remains, play the available contiguous tail through EOF. Never wait for two seconds that cannot exist. Test sub-chunk and one-frame tails during rebuffering, not only at initial startup.

Use configured duration initially and the final frame count when available. EOF is a separate state transition, not an indefinitely missing future chunk. Present the final frame, stop clock/polling, release ownership and show TRANSMISSION ENDED with Back. No autoplay-next.

## 8. Rendering and controls

Use the current canvas, scene area, ink/LCD palette, nearest-neighbour scaling and transparent background/backlight behaviour. Decode only the chosen hex-msb frame. Do not refactor the static renderer merely to share a short pixel loop. Memory remains the bounded adapter window, current frame and canvas buffers.

| Input | Live behaviour |
| --- | --- |
| Select/key 5 | Stop and return |
| Back | Stop and return to launch screen |
| * | Stop, then Home |
| # | Existing backlight |
| 4/6 | Seek unavailable |
| 0 | Quality change unavailable |
| 2 | Caption toggle unavailable |
| 7 | ASCII/LCD switch unavailable |
| Info/sharing | Do not enter static clip-dependent handlers |

Unsupported actions must be honestly labelled/announced rather than silently performing another action. Live footer actions such as STOP/BACK must match all handset models. Use narrow local exceptions if footer policies override them, not a global navigation redesign.

Static controls/preferences remain unchanged. A persisted ASCII preference must not prevent fixed LCD streaming; returning to static playback preserves that preference. Record an input-origin/action matrix for numeric keys, keyboard arrows, physical rockers and 7110 roller click/movement/wheel. Do not infer all actions from the final numeric digit.

## 9. Cleanup and terminal states

- Back during startup leaves immediately; late responses must not reopen the live view.
- Repeated Play uses bridge generations and the adapter lifecycle queue, not competing adapter instances.
- Live -> static invalidates callbacks and resets timing/rendering before delegating the static load.
- Static -> live invalidates the handset's numeric static-load token so an old download cannot restore the static player.
- Failed acknowledged cleanup blocks silent replacement. Follow the prerequisite Start contract for unacknowledged work; the lease alone is not proof of latest-intent cancellation.
- Live playback never writes static resume/completion records.

Distinguish known terminal causes where supported. Do not label every 404, stopped state or timeout SESSION EXPIRED. If the cause is ambiguous, use SESSION ENDED - RESTART. SESSION EXPIRED requires a verified reason; transport timeout and conversion failure are different errors. Keep Back usable and do not claim confirmed cleanup when the network request failed.

## 10. Deliverables and small passes

Target two new implementation files: tools/handset_live_preview.py and handset-live.js. Add focused host/routing, bridge state/timing and browser integration tests plus checkpoint notes. Final filenames/count are proposals, not files already created.

After prerequisite fixes pass:

1. 5A.3A: host/static/API composition only. Gate: existing static handset works; same origin, capability/CSP, safe routing and both gzip paths are correct; no premature live entry.
2. 5A.3B: bridge in isolation. Gate: state transitions, held buffering, smooth clock versus presented-frame time, one animation chain/timer, stale callback rejection and static delegation.
3. 5A.3C: enable the virtual entry and verify in a browser. Gate: first live picture before full conversion, Stop/Back/Home, hidden-page cleanup, EOF tails, source switching and model labels.

Save each pass. Do not reconstruct the earlier stack. Outside the separately approved prerequisite fixes, leave the adapter, conversion engine and M4 API unchanged unless a proven defect needs an isolated regression fix.

## 11. Definition of done

On the mini PC, open the local handset over LAN, select the live entry, observe buffering then motion, Stop to the correct page, start again without accumulating workers/timers, leave during startup without resurrection, complete short tails without permanent buffering, and play a static sample afterwards.

Mock/state tests are not a real-browser result. If headless tooling is unavailable, visual acceptance remains pending until manually checked. No code fix, implementation, deployment or host result is claimed by this documentation revision.

## Browser references

- https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Same-origin_policy
- https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame
