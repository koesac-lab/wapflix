# 5A.2R2A: Start ownership fence core

Status: core implementation/test checkpoint only. The R1 fix is present on main at 32d042177b0e2eb71fb778deff5de0854cc29e1f. This archive adds tools/start_fence.py and tests/test_start_fence.py plus this document. No existing adapter, server, handset, media, Pages or workflow files are changed. Nothing is auto-committed or uploaded.

## Scope and evidence

StartFence is a framework-independent in-memory state machine. It does not expose HTTP routes, launch or terminate workers, probe media or change the running viewer. Twenty-three standard-library unit/concurrency tests passed after extracting the archive. This is not live HTTP/FFmpeg/browser/host validation, and the complete 5A.2R2 requirement is NOT fixed until backend and adapter integration pass.

## Install and test

Extract the archive into the repo root with tar --keep-old-files -xzf and its filename. Stop on extraction errors rather than replacing unknown existing work.

```sh
cd ~/wapflix
python3 -m unittest discover -s tests -p 'test_start_fence.py' -v
```

Existing services can remain running: these tests have no network/media effects.

## Core contract

- open_client() creates an opaque server-issued handle before any Start. Unknown/expired handles are never implicitly recreated by request() or cancel(). Default bounded registry: 32 clients; control lease: 60 seconds. These are not browser authentication. Future HTTP calls must still enforce the real capability/Host/Origin boundary.
- request(client, revision) accepts positive safe-integer revisions, creates a server ticket and invalidates older prepared requests. Duplicate current requests are idempotent. A later accepted request must be checked again immediately before admission, not only before slow preparation.
- Client registration has a monotonic era. Opening a handle alone does not stop playback. Once a newer registered client has an accepted Start, delayed requests from older client eras are refused. Reclaiming control from an old tab requires a fresh explicitly requested handle; do not automatically renew/retry in response to stale network replies.
- cancel(client, through_revision) records a watermark even if that Start has not reached request() yet. A later arrival through that revision cannot admit. Cancellation is client/revision scoped and never cancels a newer revision or another current client.
- admit(ticket, action) rechecks the ticket and reserves exactly one owner. The action receives a generated owner_id and runs once for that accepted operation. Duplicate admission returns its prior owner without repeating the action. No replacement admits while another owner remains reserved.
- Admission action must be short, synchronous and nonblocking: no metadata probing, network I/O, worker stop/wait or re-entry into the fence. Source preparation happens outside the fence; the manager serializes replacement and performs stop/reap before final admission.
- If an admission action raises, AdmissionFailed exposes the reserved owner. Ownership stays reserved and the action cannot silently retry. The caller must clean up any partial worker and finish(owner_id), then require new user intent/revision for retry.
- cancel() returns the matching active owner needing cleanup, or None. It does NOT perform cleanup. finish(owner_id) releases only a matching current owner after confirmed stop/reap. A delayed finish for an old owner cannot release a newer one.
- touch(client) renews only a valid control handle. Backend integration must renew it from the matching active session/legitimate control traffic, not let unrelated stale clients impersonate an owner.
- expired_owner() exposes an expired active owner for the manager's cleanup sweep; it is not silently removed by pruning. Idle nonowners expire and are reclaimed. The existing shorter playback lease remains a separate backend policy.
- close() invalidates clients/tickets and returns any active owner still requiring cleanup. finish() remains available for that cleanup. Server epochs prevent foreign/prior-process tickets being accepted.

StartTicket is internal server state, not a trusted browser-submitted object or a serialised authority. The future route layer validates handle/revision requests and obtains tickets from the fence. No source paths, full metadata/frame arrays or unbounded replay-result history are stored in the core.

## Integration steps still required

R2B (next): wire this core into the EXISTING real M4 session API in a narrow change. Resolve the final endpoint/body contract and conformance fixtures before changing the adapter. Authenticate client-handle creation, record cancellation before slow preparation, check again under replacement/admission, bind generated owner IDs to actual navigation/session IDs and stop/reap only matching owners. Preserve the original real-media diagnostic fallback. Legacy requests lacking fencing identity must not bypass fenced ownership; isolate or refuse such requests under the new mode rather than silently weakening it.

Do not wire this into the simulated dispatch_stream_api as if it were a real backend. That separate handset-host issue remains outstanding. Core unit-test callbacks are test fixtures, not runtime placeholder jobs.

R2B tests: real HTTP cancel-before-ack, delayed old request after newer acceptance, bounded client admission, replay/idempotency, cancellation during preparation, source/probe failure, actual FFmpeg replacement/cleanup, expiry sweep and compatibility of the existing response shapes. Keep all filesystem/probe/cleanup waits outside the short core lock and recheck ownership under the backend lifecycle lock before applying delayed cleanup.

R2C: integrate server handles/revisions into stream-source.js. Stop and newer intent must send the scoped fence before a navigation acknowledgement is known, not sit behind the very Start being cancelled. Preserve queue ownership, request deadlines, stale response guards, reset-on-generation and R1 readiness. Refuse unsupported fencing instead of silently falling back to weaker Start semantics. Test API and adapter together before marking R2 passed.

Completion of these three passes is the prerequisite for repairing/finishing the real 5A.3 handset connection. No UI feature or later phase is completed by this archive.

## Commit only this checkpoint

```sh
git add -- tools/start_fence.py tests/test_start_fence.py CHECKPOINT_5A2R2A.md
git diff --cached --stat
git commit -m "Add bounded Start ownership fence core and tests" -- tools/start_fence.py tests/test_start_fence.py CHECKPOINT_5A2R2A.md
git push origin main
```

Review other local work before committing. Do not stage archives, source media, output or backup files with git add . for this checkpoint.
