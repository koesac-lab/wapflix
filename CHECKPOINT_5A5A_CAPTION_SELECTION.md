# 5A.5A — pure source-time caption selection

Prepared 2026-10-25. This is the narrow selection pass specified by
HANDSET_STAGE5_REMAINING_PLAN.md section 5, not complete handset captions.
Save the successful 5A.4A/B/C lifecycle work before applying this separate pass.

## Scope

Five new files only:
- live-captions.js
- tests/test_live_captions.cjs
- tools/apply_handset_5a5a.py
- CHECKPOINT_5A5A_CAPTION_SELECTION.md
- MANIFEST_5A5A.json

No existing file is changed. The helper is not loaded by the host or public
Pages, and the bridge does not call it yet. There is no visible browser change,
no caption toggle, renderer, wrapping/layout change, request, timer, clock,
storage or SRT parsing. The next pass (5A.5B) wires presentation and numeric 2.

## Metadata basis checked against the repository

M3 CaptionApp.caption_data emits:

    captions = {
      timebase: 'source', cues: [{start, end, text}],
      selected_cue_count, parse_error_count, track_found
    }

M4Candidate.snapshot reuses that producer for fenced session metadata.
Reviewed blobs:
- tools/lcd_stream_captions.py: 7e4d8ec73b1938517e6463990004cf8bc15e9bdd
- tools/lcd_m4_factory.py: b052d78b10319ded5f4b3558fe58f7beb5198aea
- HANDSET_STAGE5_REMAINING_PLAN.md: b7b3057ac40d8d25501d02ecdc4083783d92d771

Cue times are absolute source seconds and already clipped to the current
source window. Never subtract/re-add source_start in this selector or use the
smooth clock/request time as a substitute for the frame actually drawn.

## API

```js
const track = WapflixLiveCaptions.prepare(metadata.captions);
const selected = WapflixLiveCaptions.selectFrame(track, presentedFrame);
// selected: {status, sourceTime, activeCueIndices, lines, text}
```

CommonJS exports the same three pure functions: prepare, selectFrame, selectAt.
The browser global is only created if this standalone script is explicitly
loaded later; this pass does not add a script tag or host route.

- prepare expects the existing captions metadata object, not a raw cue array.
- status=missing distinguishes absent metadata/track_found=false from a ready
  track with zero cues in this extract or no active cue at this frame.
- status=invalid and warning codes distinguish malformed metadata/unsupported
  timebase without converting an empty cue list into a video failure.
- Invalid cue entries are skipped and indexed warnings retained. Server
  parse_error_count remains separate and visible; valid neighbours still select.
- Selected intervals are start inclusive, end exclusive, without an epsilon.
- Incoming overlap order is preserved; there is no time sort or hidden FPS snap.
- Deduplicate repeated exact lines, preserving the first occurrence and case.
  Normalise CRLF/CR to LF, trim line edges and drop blank lines; preserve internal
  spacing, punctuation, Unicode and markup-looking strings as literal text.
- Prepared inputs and owned output arrays/objects are immutable snapshots. No
  reference to a mutable raw cue remains in the prepared data.
- selectFrame(null/undefined frame) returns empty text with sourceTime=null.
- selectAt validates explicit finite non-negative source time. Incorrect caller
  time/frame/prepared-track arguments throw rather than guessing an offset.
- Holding the presented frame naturally holds the selected cue during Pause or
  rebuffering. Generation ownership, cleanup and cue announcements remain the
  bridge's integration responsibility in later passes. Do not mistake a pure
  selector test for implemented lifecycle wiring.

Caption strings must later go to canvas text/textContent, never innerHTML.
A prepared track may expose literal markup but this module never interprets it.
Line wrapping/truncation is deliberately deferred to 5A.5B rather than silently
removing overlapping lines from this pure selector.

## Verification

- 50/50 pure Node selection tests passed.
- Source offsets, exact/adjacent/fractional boundaries, frame-vs-smooth time,
  overlaps/order/dedup, empty/missing/invalid tracks, parser warnings, malformed
  cues, mutation/freeze, literal markup and side-effect-free browser export.
- JavaScript syntax checks passed.
- No browser rendering, real-video caption sync, SRT load or live lifecycle test
  is claimed by this pass. Existing lifecycle source files are untouched.

## Apply from the repo root after committing lifecycle work

Download the tar into the repo root. No preview restart is needed for this
unused additive module; it is not injected into the running application.

```sh
STAGE=$(mktemp -d)
tar -xzf wapflix-5a5a-caption-selection.tar.gz -C "$STAGE"
python3 "$STAGE/tools/apply_handset_5a5a.py" --root "$PWD"
python3 "$STAGE/tools/apply_handset_5a5a.py" --root "$PWD" --apply
node --test tests/test_live_captions.cjs
```

The helper validates package checksums and lifecycle prerequisite files. It
adds only absent files, refuses conflicting existing files, and supports an
identical no-op reapply. It performs no Git action and does not verify your
commit/push result. Do not call this pass committed until Git confirms it.

## Save as its own checkpoint after the test passes

```sh
git add -- live-captions.js tests/test_live_captions.cjs \
  tools/apply_handset_5a5a.py CHECKPOINT_5A5A_CAPTION_SELECTION.md MANIFEST_5A5A.json
git diff --cached --stat
git commit -m "Add pure source-time live caption selection"
git push origin main
```

Keep source media, full SRTs, archives, capabilities and backups out of Git.

## Rollback / next

This package replaces no files. To roll back, remove only its new files listed
in the apply helper's installed-files.json; leave unrelated work untouched.
Next is 5A.5B: in-handset caption drawing, numeric-2 toggle, and page-local live
preference, with physical Up/roller movement still kept distinct. 5A.5C follows
with pause/buffer/replacement and actual browser acceptance.
