# 5A.6A — adapter restart-seeking

Prepared after 5A.5B/5A.5C caption acceptance. Adds explicit seek support to
stream-source.js only. No handset UI, server, converter, static player or
caption selector changes.

## Behaviour

- seek(sourceTime) requires an active ready stream and a finite time.
- Requested time is clamped to the configured range, quantised down to a frame,
  and restarted through the existing Start fence.
- The result reports requested time, quantised destination, frame index and the
  replacement metadata.
- A seek immediately invalidates the current generation: pending polls/chunks
  return null, cache and readiness clear, and the old session is fenced.
- A second seek issued before the first completes is rejected with
  "Seek requires an active stream". This is deliberate fail-closed behaviour;
  5A.6B UI must await/supersede through its own generation boundary.
- Stop during a pending seek tombstones it; its late Start cannot admit.
- Failures release acquired navigation, preserve cleanup details and do not
  silently retry. Superseded/gone handles are not silently renewed.
- Existing Start, Stop, poll, chunk validation, cache and frame APIs unchanged.

## Baseline and tests

- stream-source.js baseline Git blob:
  a908970423716fbb395c200aadebc2edbe3c9f2d
- 15 new seek tests pass.
- A focused regression smoke covering existing Start/poll/frame/cache plus one
  seek passed against the patched module.
- The full existing 50-case standalone adapter suite must be run in the checkout;
  it was not rerun in full in this preparation environment.

## Install

Stop the preview. Extract this archive separately, then always use its helper:

```sh
STAGE=$(mktemp -d)
tar -xzf wapflix-5a6a-adapter-seek.tar.gz -C "$STAGE"
python3 "$STAGE/tools/apply_stream_5a6a.py" --root "$PWD"
python3 "$STAGE/tools/apply_stream_5a6a.py" --root "$PWD" --apply
```

## Checkout tests

```sh
node tests/test_stream_source.cjs
node tests/test_stream_source_seek.cjs
node tests/test_stream_source_http.cjs
node tests/test_stream_source_terminal.cjs
```

## Browser acceptance — pending 5A.6B

This milestone does not wire numeric 4/6 or expose a seek bar. It establishes
the safe adapter operation only. After 5A.6B, verify forward/backward seeks,
paused seeks, rapid UI seeks, end clamping, cancellation and caption behaviour.

## Commit after acceptance

```sh
git add -- stream-source.js tests/test_stream_source_seek.cjs \
  tools/apply_stream_5a6a.py CHECKPOINT_5A6A_ADAPTER_SEEK.md MANIFEST_5A6A.json
git commit -m "Add fenced restart-seeking to the stream adapter"
git push origin main
```
