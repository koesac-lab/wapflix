# Checkpoint 6.3 — LCD cache recovery and integrity

## Scope

Makes the persistent LCD chunk cache safe after interrupted writes or file corruption.

- Cached chunks are validated as complete gzip streams before being served.
- A corrupt chunk is moved to `/cache/.quarantine/` and treated as a cache miss.
- Abandoned `.chunk-*.tmp` files are removed during cache startup.
- Orphaned published chunk files are counted in cache usage and remain available for identity-scoped reads.
- `cache-state.json` is rebuilt from actual cache contents after startup reconciliation.
- The 32 MiB ceiling and active-window protection remain unchanged.

## Not included

This checkpoint does not add SQLite metadata, exact-window partial reuse, LRU eviction, capacity-error HTTP codes, or cross-window cache reuse.

## Acceptance

1. Run `python3 -m unittest discover -s tests -p 'test_chunk_cache.py' -v`.
2. Rebuild and restart Compose.
3. Play Season 1 Episode 1 and confirm chunks continue to appear in `/cache`.
4. Stop the container, corrupt one cached chunk, and restart it.
5. Requesting that chunk must not serve corrupt data; it becomes a miss and the corrupt file is quarantined.
6. Confirm `cache-state.json` remains at or below 33554432 bytes.
