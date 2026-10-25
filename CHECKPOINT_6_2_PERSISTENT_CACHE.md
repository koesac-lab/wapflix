# Checkpoint 6.2 — Bounded persistent LCD chunk cache

## Scope

Adds an optional disk-backed cache for generated LCD chunks.

- New `tools/chunk_cache.py` provides identity-scoped persistence beneath `/cache`.
- The default ceiling is 32 MiB.
- Cache identity includes resolved source path, start, seconds, columns, rows, and FPS.
- Generated gzip chunks are written atomically to `/cache`.
- A chunk evicted from memory can be served again from disk.
- `/state/cache-state.json` records the ceiling, total cached bytes, entry count, and update time.
- Eviction is oldest-first and skips chunks protected by the active playback window.
- Cache failures fall back to the existing memory-only path rather than interrupting playback.

## Not included

This checkpoint does not add Plex integration, multiple viewers, background conversion, cross-device resume, or partial-cache reuse after source or dimension changes.

## Acceptance

1. Run `python3 -m unittest discover -s tests -p 'test_chunk_cache.py' -v`.
2. Rebuild and restart Compose.
3. Start Season 1 Episode 1 and play beyond the first chunks.
4. Confirm `~/wapflix-deploy/data/cache` receives chunk files.
5. Confirm `~/wapflix-deploy/data/state/cache-state.json` reports usage at or below 33554432 bytes.
6. Pause, resume, stop, and start again without stale frames or conversion failure.
