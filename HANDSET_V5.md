# WAPFLIX faithful handset refinement v5

Builds on handset-authenticity-v4 (already applied and working). No JavaScript,
player, catalogue, streaming or workflow changes. Only themes.css is replaced.

## Apply from repository root

    git status --short
    git switch -c handset-faithful-v5
    tar -xzf wapflix-handset-faithful-v5.tar.gz
    sha256sum -c HANDSET_V5.sha256
    git diff --check
    node --check theme.js
    python -m unittest discover -s tests
    git add themes.css HANDSET_V5.md HANDSET_V5.sha256
    git commit -m "Refine handset themes for closer model fidelity"
    git switch main
    git pull --ff-only origin main
    git merge handset-faithful-v5
    git push origin main

## What changed

- 3310: deeper navy shell, paler shield bezel, blue Navi key, lighter fanned keys.
- 3210: broader shoulders retained, warmer silver fascia, straighter rubber keys.
- 8210: compact red shell, smaller screen surround, compact separate keys.
- 6310: taller graphite body, metallic face, elongated keys, narrow rocker.
- 7110: olive metallic surround, antenna stub, ridged roller, sliding cover.
- Overall: stronger gradients, rim highlights, key edge shadows and per-model
  screen-surround shapes for a closer original-era read.

## Verification

Same browser regression suite as v4 passes: 20 handset/viewport combinations,
control overlap, overflow, roller, slider, persistence and blocked storage.
CSS top-level parse and node --check theme.js pass. This is still a shell-level
check, not a full playback integration test or visual sign-off on every device.

## Rollback

    git restore --source=HEAD~1 -- themes.css
