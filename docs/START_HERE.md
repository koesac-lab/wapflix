# Start here: Wapflix development

Updated 2026-10-24. This is the current-status and next-task entry point, not a runtime implementation. Documentation cleanup does not fix code or rerun earlier tests.

## Next task

Implement R2B.1 only under [the backend contract](plans/R2B_BACKEND_CONTRACT.md): authenticated client registration and cancellation recording, without wiring Start admission or launching conversion. Use an isolated control-only mode and focused HTTP tests. Do not attempt all of R2B in one response.

R2B.0 is the contract in that document. Its commitment is a planning baseline, not backend completion. R2B.2 admission coordination, R2B.3 real worker wiring and R2B.4 integration follow as separate saved passes. Adapter R2C comes after the backend gate.

## Current evidence

| Checkpoint | Recorded evidence | What it does not prove |
| --- | --- | --- |
| R1 readiness | 32d042177b0e2eb71fb778deff5de0854cc29e1f; user reported successful local tests/commit; patch reported 24 adapter tests | No backend fencing or real handset acceptance |
| R2A fence core | fe442e669c64f3af3c358a71ceda6328e548643b; [core checkpoint](../CHECKPOINT_5A2R2A.md) reports 23 unit/concurrency tests | No HTTP routes, converter wiring or adapter integration |
| R2B | Contract/implementation passes planned | Not implemented or accepted by these docs |
| R2C | Adapter wiring deferred | Existing adapter is not yet fully Start-fenced |
| 5A.3 host/bridge | Implementation commits exist; [corrected checkpoint](../CHECKPOINT_5A3.md) | Runtime simulated API and bridge issues prevent completion claim |
| Phase 6/7 | Detailed plans committed | No deployment/Plex completion |

The only evidence checked for this cleanup is repository content/history and earlier recorded results. Existing tests were not rerun as part of a documentation-only commit. Verify local-only changes before implementation and retain runtime error logs rather than guessing their cause.

## Reading order and precedence

1. This file owns current completion status and next work.
2. [R2B_BACKEND_CONTRACT.md](plans/R2B_BACKEND_CONTRACT.md) owns the active R2B scope, wire fields and small gates. It must remain compatible with the tested R2A core; stop/review a conflict instead of silently changing either.
3. [5A.3 plan](../HANDSET_5A3_PLAN.md) and [remaining Stage 5 plan](../HANDSET_STAGE5_REMAINING_PLAN.md) own future handset requirements. Their original defect descriptions are dated review records, not a claim R1 is still unfixed. The newly split R2B contract refines their general fencing task.
4. [ROADMAP.md](../ROADMAP.md) is product direction and phase navigation, not a progress certificate.
5. [Phase 6](../PHASE6_DEPLOYMENT_PLAN.md) and [Phase 7](../PHASE7_PLEX_PLAN.md) remain gated future specifications.

## Working boundaries

Use the existing real M4 source/session/worker path for backend integration. The simulated dispatch in tools/handset_live_preview.py is not that backend. Mocks are permitted in unit fixtures, never as shipped conversion responses.

Keep the local diagnostics, static handset preview and public Pages independent until deliberate integration gates pass. Preserve capability/Host/Origin protections, source-time semantics, bounded buffers, single-owner cleanup and the distinction between static explicit-gzip assets and HTTP-gzip API chunks. Do not add Docker/Plex or UI features to an R2B pass.

Before each coding pass record the baseline, the one behaviour being changed, one/two implementation targets, focused tests and a rollback. Save the pass before advancing. Tests with fake data, real HTTP/FFmpeg, browser interactions and host measurements are different evidence.

## Design/history index

- [BUILD_PLAN.md](../BUILD_PLAN.md): early architecture draft. Its old ASCII profile, proposed API and original milestone numbering are historical; do not implement them over newer accepted contracts.
- [LOCAL_STREAMING_STEPS.md](../LOCAL_STREAMING_STEPS.md), [M2](../LOCAL_STREAMING_M2.md), [M3](../LOCAL_STREAMING_M3.md), [M4A](../LOCAL_STREAMING_M4A.md), [M4B](../LOCAL_STREAMING_M4B.md): earlier diagnostic/checkpoint records, not cumulative certification.
- [5A.1](../HANDSET_5A1.md), [5A.2](../HANDSET_5A2.md): static handset/source-adapter records.
- [HANDSETS.md](../HANDSETS.md), [NAVIGATION.md](../NAVIGATION.md), [NAVIGATION_V3.md](../NAVIGATION_V3.md), visual V4-V7 notes and docs/PROGRESSIVE_*: reference/history within their stated scope.
- [SAMPLE_GENERATION.md](../SAMPLE_GENERATION.md): current offline sample regeneration.

This cleanup does not move/delete runtime, media, archives, backups or old documentation, and does not rewrite Git history. Physical repository-artifact cleanup is a separate explicit task; do not git add . to sweep unrelated files into implementation commits.
