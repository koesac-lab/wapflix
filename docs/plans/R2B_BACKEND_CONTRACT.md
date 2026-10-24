# R2B.0: small backend Start-fencing contract

Status: planning baseline, 2026-10-24. No routes or worker behaviour are implemented by this document. Prerequisite: committed R2A tools/start_fence.py and its tests. Preserve real M4 playback, R1 readiness, existing capability/Host/Origin checks and fixed-source configuration. No handset, adapter, Docker or Plex work in R2B.

## 1. Identity and mode

Use opaque server-issued control handles from StartFence.open_client(), not browser-created StartTicket objects. Initial core limits remain 32 handles/60-second control lease. The separate playback lease remains unchanged. Unknown/expired handles are never implicitly registered by Start/cancel.

Freeze these mode boundaries before route coding: legacy diagnostic mode keeps its real-media fallback; control-only mode exposes registration/cancellation for R2B.1 but refuses Start/conversion; fenced mode enables admitted Starts only after real wiring passes. There is no weaker legacy Start fallback inside a fenced instance. Reuse the existing real M4 code through explicit mode/manager hooks, not a copied or synthetic backend.

## 2. Wire contract

All routes below are POST, capability-authenticated and same-origin checked, with existing bounded JSON bodies. No source paths or URLs are accepted. Names are deliberately distinct from the existing seek revision.

| Route | Request | Result |
| --- | --- | --- |
| /api/control/open | {} | 200: control_protocol=start-fence-v1, control_client_id, control_lease_seconds=60 |
| /api/control/cancel | control_client_id, cancel_through | Record cancellation immediately; then report cleanup truthfully |
| /api/start in fenced mode | control_client_id, start_revision | Existing real M4 metadata plus control_protocol, control_client_id and start_revision |

control_client_id is the core's 48-character lowercase hex handle. start_revision is an integer excluding booleans, 1..2**53-1; cancel_through allows zero..2**53-1. Cancellation applies to Start revisions, not M4 seek revisions. Preserve the existing navigation_id, session id, captions and seek revision response semantics.

Successful cancel returns 200 with fence_recorded=true and cleanup=not_required or confirmed. confirmed means the matching worker has actually stopped/reaped and ownership was released. An unconfirmed cleanup is a failure response, not a successful stopped claim: 503 with error string, code=cleanup_unconfirmed, fence_recorded=true and cleanup=unconfirmed. Retain ownership for safe retry.

Unknown/expired nonowner handles return 404/control_client_gone without recreating them. An expired active owner must still be cancellable/cleaned under the core contract. Stale/cancelled/superseded requests return 409 with a reason code; capacity returns 429; malformed fields return 400; authentication/origin failures return 403. Keep error as a string with additive code fields, not an incompatible nested error object.

In control-only mode, Start returns 409/fenced_admission_unavailable before any probe or worker. In fenced mode, missing identity returns 409/fencing_required; do not invoke the legacy begin() path. Do not advertise start-fence-v1 admission support until R2B's full gate passes.

## 3. Preparation, admission and idempotency

Record/validate a request with fence.request(handle, start_revision) before slow preparation. Prepare a real candidate from an immutable fixed-source/window snapshot outside the fence and backend lifecycle locks. Do not obtain Start's source by reading app.start while another seek mutates it. Bound preparation/admission; no unbounded queue.

Before replacement check the ticket, then under the backend lifecycle lock stop/reap the old owner and release it only after confirmation. Recheck via fence.admit() immediately before assigning/starting the prepared session. Its callback is short/nonblocking: no ffprobe, network or stop/wait. Cancellation arriving during preparation or cleanup must still prevent admission. Failed admission reserves its owner until explicit cleanup/finish.

A duplicate accepted handle/revision must return the existing active navigation/snapshot without probing, stopping or launching again. Check the replay record BEFORE replacement cleanup; relying on admit() alone after stopping the old session is not sufficient. If its old result is no longer active, return 409/start_no_longer_active rather than replay the conversion. Keep only bounded owner/navigation/state references per client's latest operation, not copied frame/cue payloads or unbounded history.

## 4. Ownership and lock order

Bind the core owner_id to an admitted navigation, not merely one FFmpeg process. Seeking can change the session ID/worker while retaining that navigation owner. Do not release the fence merely because conversion completed: playback may still consume buffered data.

The backend lifecycle lock may call short fence methods. Never hold the fence lock while acquiring/waiting for the lifecycle lock, probing media or reaping a process. Cancel first records its fence, releases the core lock, then acquires lifecycle ownership and rechecks the exact owner before cleanup. Delayed cleanup/finish of an old owner cannot affect a replacement.

All exit paths participate: control-cancel, navigation-stop, legacy session-stop where allowed, playback expiry and shutdown. Integrate the existing seek path with the same navigation owner. Renew control leases only from validated matching-session activity; sweep expired_owner() and clean/reap before finish(). Client registration alone never starts or stops media. Older client eras require fresh explicit user registration to regain control; no automatic renew/retry prompted by a stale reply.

## 5. Small implementation passes

| Pass | Only deliver | Gate |
| --- | --- | --- |
| R2B.0 | This contract and planning/status reconciliation | Reviewable agreed wire/lifecycle rules; no implementation claim |
| R2B.1 | Authenticated control routes in isolated control-only mode | Real HTTP open/cancel/bounds/security; no probe, Start admission or conversion |
| R2B.2 | Admission/replacement coordinator with injected controlled workers in tests only | Cancel/supersede/replay/cleanup ordering; no synthetic runtime fallback |
| R2B.3 | Required real M4 session/FFmpeg factory | Real chunks, cancelled preparation creates no converter, replacement reaps old worker |
| R2B.4 | Failure/expiry/legacy/HTTP integration gate | Full backend contract passes; still no browser adapter edits |

Runtime admission requires the real factory and fails clearly if absent. A fake injected worker is only a unit fixture, never shipped responses. R2B is not wired into the simulated handset-host dispatch.

Focused test gates include cancel-before-request and before-ack; late old preparation after newer acceptance; newer registered client takeover; duplicate active Start; cancelled retry; partial admission failure; Stop/expiry/shutdown and seek-owner continuity; cleanup failure; lease/registry bounds; valid real GET-chunk query and HTTP gzip; full pulse fields; retained legacy fallback without fenced bypass. Preserve existing request/probe/cleanup budgets and never extend them merely to hide a race.

## 6. Next work and release boundary

Implement R2B.1 only next, normally one implementation module plus one focused test file. Save each passing pass before advancing. Record baseline, versions, exact commands, actual results, limits and rollback. No full-stack rebuild or all-passes archive in one response.

After R2B passes, R2C updates stream-source.js for registration, identity and out-of-band cancellation before Start acknowledgement. It must validate protocol support rather than silently downgrade, keep existing generation/timeout/cleanup guards and R1 readiness, and pass combined backend/adapter tests. No R2 completion claim until that integration passes.

Then recover 5A.3 real hosting/rendering and browser acceptance under the existing phase plans. Current checkpoint/status is in [START_HERE](../START_HERE.md); product direction is in [ROADMAP](../../ROADMAP.md).
