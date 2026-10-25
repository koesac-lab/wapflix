# Checkpoint 6.1 — Configurable ASCII dimensions

## Scope

Adds explicit ASCII canvas dimensions to the M4 streaming path.

- `lcd_chunker.py` gains `resolve_ascii_dimensions()` and optional `ascii_width` / `ascii_height` arguments on `LCDStream`.
- `lcd_stream_server.py` gains `--ascii-width` and `--ascii-height`.
- Both values must be supplied together.
- Valid ranges are width 8–240 and height 2–200.
- The deployed Compose configuration uses 120 × 54.

## Not included

This checkpoint does not implement persistent `/cache` writes, cache accounting, or the 32 MiB ceiling.

## Acceptance

1. Run the ASCII dimension tests.
2. Rebuild and restart Compose.
3. Start Season 1 Episode 1.
4. Confirm the rendered canvas is 120 columns by 54 rows.
5. Confirm pause, resume, stop, and a second Start still work.
