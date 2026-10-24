# R2B.2 admission/replacement coordinator

Scope: framework-independent coordinator plus controlled unit fixtures only.
No HTTP, handset, adapter, M4 runtime or StartFence source modifications.
No synthetic runtime factory is included. Constructor rejects a missing factory.
R2B.1 remains control-only; starting its server still cannot play media.

Reviewed inputs: docs/plans/R2B_BACKEND_CONTRACT.md blob
c633324e89530c407abb065e19b84c58ea60dbf2 and tools/start_fence.py blob
1ad91736143c8f9ed02ccf75566cebd81d9f4ef6, retrieved from main.

Files:
- tools/start_coordinator.py
- tests/test_start_coordinator.py
- CHECKPOINT_R2B2.md

Behaviour:
- Fence intent before preparation, preparation outside lifecycle/core locks.
- At most four concurrent preparations by default; nonqueued capacity rejection.
- Pending duplicate is rejected as start_in_progress; active duplicate snapshots
  the same navigation before any cleanup/probe. Retired/failed current ticket
  cannot silently start again. Older tickets fail core ordering checks.
- Replacement stops/reaps the bound owner before admission and rechecks in admit.
- Cancellation records the watermark before waiting for lifecycle cleanup.
- Partial publish failure retains the bound owner for explicit cleanup.
- Unconfirmed cleanup blocks replacement; exact-owner stop prevents stale teardown.
- Expiry rechecked after lifecycle wait; shutdown fences pending preparations.
- Only bounded ticket/owner references are retained, not snapshot histories.

Factory boundary for R2B.3:
prepare(spec, ticket) must consume an immutable fixed-source/window snapshot,
perform bounded probing outside locks, create no running converter and leave no
live resources on return/failure. candidate.publish(owner_id) is a SHORT synchronous
nonblocking admission callback; no probe, network, cleanup or fence reentry.
It binds a navigation, not one seek worker. candidate.snapshot() reads current
metadata. candidate.stop() returns literal True only after stop/reap.
This module does not enforce wall-clock deadlines on arbitrary Python callbacks:
the required real factory MUST enforce existing probe/cleanup budgets. Lifecycle
lock waits are separately bounded (default five seconds). No runtime admission
support is advertised or routed until the subsequent real-factory/HTTP gates.
A busy cancellation still leaves its watermark recorded; route mapping and the
cleanup_unconfirmed HTTP body remain for R2B.4 integration.

Validation performed here: 21 coordinator tests passed in a temporary Python
workspace using the retrieved StartFence implementation transcribed without its
docstrings/comments; no semantic core changes were made. This is NOT a cloned
full-repository test run. Re-run against actual repository files before commit:

    python3 -m unittest discover -s tests -p 'test_start_fence.py' -v
    python3 -m unittest discover -s tests -p 'test_control_api.py' -v
    python3 -m unittest discover -s tests -p 'test_start_coordinator.py' -v

Tests use deterministic threading events with deadlines, not FFmpeg or media.
They cover cancel-before-request, preparation cancellation/supersession,
newer-client takeover, cancellation during replacement cleanup, active and pending
duplicates, failed/retired replay, cleanup refusal/retry, partial publication,
scoped stale teardown, preparation failure/capacity, expiry, owner touch,
shutdown during preparation and failed shutdown cleanup, and cancellation fence
recording before lifecycle wait timeout. No real media, HTTP coordinator wiring,
browser or mini-PC throughput acceptance is claimed.

Install with tar --keep-old-files at repo root; stop on collisions. Run the three
test commands above. Stage only these three added files. Existing services do
not import this module, so no restart or LAN/TS change is needed for this pass.
Rollback is removal of these three files; no running entry point was modified.
Next: R2B.3 real M4 factory, then R2B.4 lifecycle/HTTP compatibility gate.
