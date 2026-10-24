# Checkpoint 5A.3: implementation present, integration not accepted

Corrected status, 2026-10-24. This replaces earlier overoptimistic completion/prerequisite claims; it does not change runtime code. The former text remains available in Git history. See [docs/START_HERE.md](docs/START_HERE.md) for the current task.

## Saved work

- d09e2b0b5905926565f1bc40a79913ba365879b0 added the handset host/bridge and their tests.
- 113eda9ea1b3691b7901f2601a27ca7d26b317c6 added pause-related bridge/test changes.

Those commits establish code presence, not end-to-end streaming acceptance. Earlier reports of 21 bridge tests and 24 host/routing tests are historical reports, not tests rerun by this documentation cleanup or proof of real conversion.

## Why 5A.3 is not complete

The reviewed tools/handset_live_preview.py uses a simulated dispatch_stream_api: it advances readiness counters and fabricates chunks rather than invoking the real M4 converter/session manager. Its GET-chunk/body handling and pulse/gzip responses do not satisfy the real transport contract. A runtime mock must not be described as a working on-demand backend. Keep simulations in tests only.

The reviewed bridge also needs recovery/verification of lifecycle and rendering: Stop during startup, stale callbacks, independent generation counters, animation/timing ownership, held-frame drawing, aspect/clearing behaviour, conversion-complete versus playback-complete, actual handset state access and consistent select/key-5/Back actions. The partial Pause change is not acceptance of 5A.4.

These are code-review findings on the saved implementation, not a claim that every failure has been reproduced in a real browser. Do not expand captions/seeking or deployment on top of an unverified integration.

## Correct prerequisite status

| Requirement | Evidence/status |
| --- | --- |
| 5A.2R1 | Fix committed at 32d042177b0e2eb71fb778deff5de0854cc29e1f; 24 adapter tests were reported passing with the patch. Not rerun by this docs-only cleanup. |
| R2A ownership core | Committed at fe442e669c64f3af3c358a71ceda6328e548643b; isolated 23-test core checkpoint, no HTTP/worker integration. |
| Full 5A.2R2 | Incomplete until R2B and R2C pass their actual gates. Earlier blanket verified claim is withdrawn. |
| Full 5A.3 | Incomplete: real backend and browser acceptance outstanding. |

## Recovery order

Follow [docs/plans/R2B_BACKEND_CONTRACT.md](docs/plans/R2B_BACKEND_CONTRACT.md): contract, small backend passes, real worker/HTTP gate, then adapter R2C. Afterwards replace the simulated handset-host API with the accepted real implementation and repair the bridge in small tested passes. Do not reconstruct M1-M4 or duplicate a backend per feature.

5A.3 acceptance is Start/buffer/render/Stop/Back/Home, correct EOF tails, safe source switching, one clock/animation chain/poll timer, real worker cleanup and static regression. Caption display and handset seek integration remain later Stage 5 requirements, not completed by mock test counts. No new test or host acceptance is asserted here.
