# WAPFLIX screen/control consistency v7

## What this changes

- 3210/3310: screen labels become SELECT / BACK. The central Navi key selects or plays/pauses; C goes Back.
- 8210/6310: contextual softkeys remain, matching their on-screen labels.
- 7110: roller press selects; rocker up/down seeks during playback, avoiding the captions conflict.
- Menus: tighter 18px rows and a compact 8-segment progress indicator.
- No catalogue, Plex, transcoding, Docker, Tailscale or Cloudflare changes.

## Apply from repository root

    git status --short
    git switch -c screen-consistency-v7
    tar -xzf wapflix-screen-consistency-v7.tar.gz
    python apply_v7.py
    node --check streaming.js
    node --check theme.js
    python -m unittest discover -s tests
    git diff --check

Review, then commit only the two runtime files:

    git add streaming.js theme.js
    git commit -m "Align screen labels with handset controls and tighten menus"
    git switch main
    git pull --ff-only origin main
    git merge screen-consistency-v7
    git push origin main

## Restore

    python apply_v7.py --restore

Then delete the .v7.bak files after confirming.

## Verification

This patch was generated against current main and uses exact anchors. It does not
include a browser test in this archive; run the existing checks and manually verify:
Home, collection, details, playback, Back, resume, captions, seek, quality,
sharing, backlight, all five handsets and the 7110 cover.

## Known limitation

The 240x224 cinema canvas remains enlarged for readability. This is not a faithful
84x48 original 3310 screen emulation; that would require a separate renderer.
