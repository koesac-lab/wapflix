# Wapflix 5A.3B bridge recovery — apply package

Prepared 2026-10-25. Local source patch only; not committed or deployed.

## Scope

Replace handset-live.js and tools/handset_fenced_preview.py. Replace the old
bridge test suite with assertion-bearing lifecycle/clock/render/input tests.
Add served-route publication tests and this checkpoint. Include an optional
baseline-checking installer and its checksum manifest.

No adapter, converter, fenced API, on-disk catalogue, static assets, Docker
configuration or public Pages workflow is changed. The repaired bridge is only
loaded by the real fenced host when --enable-live is supplied.

## Verification of this archive

- node --check handset-live.js: passed.
- 34/34 deterministic bridge tests: passed, including the corrected event.type
  mock fixture, wheel-over-roller press, and fractional EOF endpoint.
- 6/6 dependency-free served-route publication tests: passed.
- Python syntax parsing: passed.
- These are mock/isolated publication results, not real-browser or full HTTP
  integration results. Existing fenced host, adapter and real-media regression
  suites still need to run in the complete checkout. No N5105 result is claimed.

## Apply safely from the repository root

Set PATCH to the archive you downloaded, then stage outside the checkout:

```sh
PATCH=/absolute/path/to/downloaded-archive.tar.gz
STAGE=$(mktemp -d)
tar -xzf "$PATCH" -C "$STAGE"
python3 "$STAGE/tools/apply_handset_5a3b.py" --root "$PWD"
python3 "$STAGE/tools/apply_handset_5a3b.py" --root "$PWD" --apply
```

The first invocation is check-only. The second verifies package checksums and
known baseline Git blob hashes before replacing files, backs up originals under
.wapflix-patch-backups, and reports the backup location. It refuses unexpected
local versions and collisions with new files. Unrelated checkout changes are
left alone. Reapplying identical contents is a no-op. Stop any running handset
preview before applying so an existing process cannot keep old Python code in
memory while serving new JavaScript. The helper does not stop services for you.
Do not extract directly over the checkout if you want the baseline safeguards.

## Verify in the checkout

```sh
node --check handset-live.js
node --test tests/test_handset_live_bridge.cjs
python3 -B -m unittest discover -s tests -p 'test_handset_live_publication.py' -v
python3 -B -m unittest discover -s tests -p 'test_handset_fenced_preview.py' -v
node tests/test_stream_source.cjs
python3 -B -m unittest discover -s tests -p 'test_stream_source_http.py' -v
```

The last three commands exercise existing checkout tests; they were not run in
the isolated packaging environment. Do not substitute the legacy simulated
handset_live_preview dispatcher for the real fenced host.

## Start the browser-acceptance host

Use the same source path, source range and trusted hostname flags as your
working 5A.3A command, and add --enable-live. Example only:

```sh
python3 -m tools.handset_fenced_preview \
  --enable-fenced --enable-live \
  --video '/absolute/path/to/your/source.mp4' \
  --start 30 --seconds 60 --port 8104
```

Open http://YOUR-MINI-PC-IP:8104/ on the trusted LAN/Tailscale network.
Home -> Original Transmissions -> Local stream test -> Play.
Without --enable-live the host stays static-only. A hostname needs the existing
--allow-host flag. This patch does not introduce public exposure, HTTPS proxy
support or a new Docker deployment.

## Behaviour

- One pre-existing animation chain; one 250 ms poll interval after Start ack.
- Stop/Back during pending Start invalidates the bridge immediately and invokes
  adapter Stop, preserving the R2C out-of-band cancellation/fencing contract.
- No private adapter lifecycle calls, growing whole-video frame arrays, static
  resume writes, live pause feature or autoplay-next.
- Four-second startup target, or a short completed extract with a playable
  frame. Underflow holds the smooth position and last picture. Recovery waits
  for one chunk, except a completed shorter contiguous tail can drain to EOF.
- Conversion completion does not immediately end playback. The final frame is
  presented before terminal cleanup. Configured fractional endpoints remain
  inside the adapter's valid source-time range.
- Select/key 5 stops and returns; Back returns; * returns Home; # retains the
  existing backlight. Quality/info/caption/share/seek/mode controls are honestly
  unavailable in live mode. Physical navigation, wheel and keyboard-arrow
  origins are intercepted separately from numeric keypad digits.
- Known transport timeout and verified client-expired code are distinguished.
  Ambiguous failures use SESSION ENDED - RESTART, not a false expiry diagnosis.
- Cleanup failures remain unconfirmed; static switching awaits successful Stop.
  The adapter remains responsible for confirming cleanup before a new Start.

## Browser acceptance — pending

1. First moving picture arrives before the whole extract is converted.
2. Stop/Back/Home work during startup, buffering and playback.
3. Repeated Start does not accumulate timers/workers; late callbacks do not reopen
   playback after navigation.
4. Hide the page; verify Stop and return to the launch screen.
5. Verify underflow holding, completed sub-chunk/one-frame tails and natural EOF.
6. Check input/labels on all five handset models, including roller wheel/press.
7. Play an existing static sample afterwards, including a persisted ASCII
   preference. Verify static progress and preferences remain intact.

No browser session, first-picture result or mini-PC visual acceptance is claimed.

## Rollback

Without changing the installed files, remove --enable-live and restart the host
to disable the live entry. For source rollback, stop the host, copy replaced
files from the backup location printed by the apply helper, and remove only the
new files listed as existed=false in that backup's installed-files.json. Keep
unrelated work intact; do not use git reset --hard or git clean.
