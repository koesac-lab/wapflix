# 5A.5B — captions inside the handset

Prepared 2026-10-25 after confirming 5A.5A on main.

## Scope

New handset-captions.js supplies bounded LCD layout and a page-local controller.
Guarded transforms wire the existing handset-live.js and real fenced host, plus
update three older control/harness suites. The selector live-captions.js is reused
unchanged. No adapter/API/converter/static renderer/theme/SRT parser changes.

The archive carries new files plus a manifest of precise transforms, NOT full
replacement copies of every existing file. Always use its staged apply helper.
Direct extraction over the checkout would omit the required transforms.

## Behaviour

- Select from the actually presented frame.sourceTime. Never add source_start,
  use the smooth requested clock, or fetch per-frame captions.
- Draw up to three 38-column wrapped lines on the LCD, hard-wrap long words and
  mark truncation with three dots. Panel ends at y=178, above live status rows.
  Use existing ink and lit/dim palette. Existing glyph/font limitations remain.
- Numeric 2 toggles while live Start/play/buffer/pause is active. It changes no
  position, session, clock, worker or transport. Physical Up/rocker/roller/wheel/
  keyboard arrows retain their separate navigation identity.
- Default enabled on page load. Preserve preference across live Stop/Start and
  static/live transitions until reload, without reading/writing static settings
  or localStorage. Clear only track/selection on Stop/replacement/error/EOF.
- Missing track, present empty window, invalid metadata and parser warnings have
  separate diagnostics in wapflixLive.snapshot().captions. Toggle announcements
  honestly report absent/invalid metadata rather than treating it as video failure.
- Accessibility cue text is a visually hidden status node INSIDE the LCD. Only
  textContent is written, and only when selected text changes; it is not a
  diagnostic panel below the phone. No innerHTML or subtitle markup execution.
- Caption preference labels and aria-pressed are live-only and restored exactly
  on return to static controls. Model replacement reuses the saved narrow observer.
- Host loads stream-source -> live-captions -> handset-captions -> handset-live
  after the existing frontend. Caption assets are allowlisted only in --enable-live
  mode and required before backend creation. Static-only host does not need them.
- Existing host nonce/CSP/capability boundaries remain. On-disk catalogue and
  public Pages scripts are not changed. Served live description matches controls.

## Baselines

- handset-live.js: 4c5f733cbc08d25c720e339acbc7ef7ac2118335
- tools/handset_fenced_preview.py: 918304b88b9742aedaf4d4cc66d8dd6a5e24f804
- unchanged live-captions.js: 9ad48646ed6bc79e4fa4fcba85645de355c568c4
- existing test source blobs are recorded per-file in MANIFEST_5A5B.json.

Unexpected local edits fail before any write. Reapply reverses transforms to
verify the known baseline and is a no-op. Originals are backed up, including
migrated test files. A manifest existing by itself is NOT an installation check;
the helper validates every file on every invocation.

## Tests and limitations

- 36 new Node layout/controller/real-bridge-with-mock-adapter tests passed.
- 8 isolated Python host publication/constructor tests passed.
- Reviewed bridge, host and selector source reconstructions matched Git blobs.
- Syntax checks passed. No test cases are removed/skipped: the old numeric-2
  unavailable expectations and VM script-loading harnesses are updated explicitly.
- Prior full lifecycle/selector/adapter/HTTP suites were NOT rerun in full here;
  run the checkout commands below. The new integration fixture reuses the saved
  model harness prefix, not actual theme.js/browser DOM execution.
- No real browser/FFmpeg/video-SRT sync, physical-device typography, network
  cancellation or host-throughput result is claimed. Those remain 5A.5C acceptance.

## Apply from the repo root

Stop the running preview. Download the tar there, stage separately and ALWAYS
run the helper, even if a manifest was downloaded separately.

```sh
STAGE=$(mktemp -d)
tar -xzf wapflix-5a5b-handset-captions.tar.gz -C "$STAGE"
python3 "$STAGE/tools/apply_handset_5a5b.py" --root "$PWD"
python3 "$STAGE/tools/apply_handset_5a5b.py" --root "$PWD" --apply
```

## Checkout regressions

```sh
node --test tests/test_live_captions.cjs tests/test_handset_captions.cjs \
  tests/test_handset_live_bridge.cjs tests/test_handset_live_pause.cjs \
  tests/test_handset_live_navigation.cjs tests/test_handset_live_visibility.cjs \
  tests/test_stream_source_terminal.cjs
python3 -B -m unittest discover -s tests -p 'test_handset_caption_host.py' -v
python3 -B -m unittest discover -s tests -p 'test_handset_fenced_preview.py' -v
python3 -B -m unittest discover -s tests -p 'test_handset_live_publication.py' -v
node tests/test_stream_source.cjs
```

The listed seven Node suites should total 226 cases with unchanged prior packages:
50 selector + 36 new UI + 140 previous lifecycle/terminal cases. The count is not
browser acceptance. Run existing real adapter HTTP tests too if shared regressions fail.

## Run the known test source with its known English SRT

```sh
python3 -m tools.handset_fenced_preview \
  --enable-fenced --enable-live \
  --video "$HOME/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4" \
  --srt "$HOME/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.youtube.en.srt" \
  --start 30 --seconds 60 --port 8104
```

The SRT path is the previously used local test track, not a newly downloaded file.
Check it exists before starting. Retain any trusted --allow-host arguments.
Server source/SRT edits require restart; reload the browser after host changes.

## Browser acceptance — pending

1. First picture/caption inside LCD. Test light/dim and three-line wrapping.
2. Pause on a cue; wait; toggle 2 off/on without picture/position changes.
3. Force buffering near cue boundary: caption must follow held frame, not target
   time. Resume with no caption jump ahead of displayed footage.
4. Change models. Physical Up/roller movement/wheel must not toggle; numeric 2 must.
5. Stop/Start retains preference but clears old text; reload defaults to enabled.
6. Back/Home/EOF/error clear text. Static sample afterwards keeps static controls,
   caption settings, rendering mode and progress untouched.
7. Hide/return remains paused under 5A.4C validation, with caption held to picture.

## Commit after acceptance

```sh
git add -- handset-captions.js handset-live.js tools/handset_fenced_preview.py \
  tests/test_handset_captions.cjs tests/test_handset_caption_host.py \
  tests/test_handset_live_bridge.cjs tests/test_handset_live_pause.cjs \
  tests/test_handset_live_navigation.cjs tools/apply_handset_5a5b.py \
  CHECKPOINT_5A5B_HANDSET_CAPTIONS.md MANIFEST_5A5B.json
git diff --cached --stat
git commit -m "Render source-time captions inside the live handset"
git push origin main
```

No Git action was performed by the assistant. Do not stage archives, media,
SRTs, capabilities or backups. Rollback: restore five transformed originals from
the helper's backup and remove only new paths marked existed=false in its record.
Next is 5A.5C: complete caption lifecycle and real-server/browser acceptance.
