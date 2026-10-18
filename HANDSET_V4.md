# WAPFLIX handset authenticity patch v4

Prepared against main 46eb39fccb48e1bd148811f7055a979756e7545d.

## Apply from your repository root

Start with a clean working tree; extraction overwrites theme.js and themes.css.

    git status --short
    git switch -c handset-authenticity-v4
    tar -tzf wapflix-handset-authenticity-v4.tar.gz
    tar -xzf wapflix-handset-authenticity-v4.tar.gz
    sha256sum -c HANDSET_V4.sha256
    git diff --check
    node --check theme.js
    python -m unittest discover -s tests
    git diff -- theme.js themes.css

The archive includes complete replacement assets, not an installer. Extract it at
the repository root with no --strip-components option. It does not modify the
player, catalogue, streaming navigation state, build workflow or Docker setup.
The existing tools/phone_video.py copies these two assets into _site, so deploy
through the normal Pages build. Do not edit _site manually. Hard-refresh after
deployment: this patch intentionally does not change existing asset URL versions.

Commit the two runtime files plus the new test fixture, browser check and notes.
Use your normal PR/merge process; no remote writes have been made by this patch.

## What changed

- 3310: navy shell, pale shield bezel, blue Navi key, C back key, right-hand
  up/down rocker and subtly fanned pale number keys.
- 3210: broader shoulder profile, warm silver fascia, grey-green Navi key,
  C/back, separate scroll keys and straighter rubber-style number keys.
- 8210: smaller red shell, short earpiece, pale screen insert, two selection
  keys, up/down rocker, call/end controls and compact separate number keys.
- 6310: taller graphite/olive shell, metallic face, two selection keys, narrow
  up/down rocker and elongated number keys. Not a modern four-way D-pad.
- 7110: olive metallic surround, antenna stub, two selection keys, a ridged
  clickable roller and functional sliding keypad cover. The roller's small
  upper/lower zones scroll; its middle selects. Mouse/trackpad wheel works over
  the roller. Ctrl-wheel is left alone for browser zoom.
- A native handset picker below the phone makes direct comparisons easy.
  Options > HANDSET and existing saved choices continue to work.
- Original left/back DOM nodes stay in place so canvas footer labels continue
  updating them. For single-Navi models C always goes back, with an accessible
  label protected from conflicting footer updates. The original dual-softkey
  context action remains on 8210/6310/7110.
- Call selects/plays; end returns home. Numeric WAPFLIX shortcuts stay intact.
- Number-key legends show ABC/DEF/etc rather than app-specific INFO/QUALITY.
- Reduced-motion preference disables cover movement. Hidden keypad controls are
  inert and removed from accessibility navigation while the cover is closed.

## Deliberate compromises

These are recognisable original-era interpretations, not museum-grade replicas.
The 240x224 cinema canvas is deliberately retained. Display aspect ratios, handset
scale and exact moulding details are not historical reproductions. Compact keys
are smaller than a modern 44px touch-target ideal; keyboard navigation and the
existing numeric shortcuts remain available. The roller's upper/lower click
zones are web usability additions, not three claimed physical buttons.

## Verification

Executed successfully in headless Chromium:

    python tools/check_handsets.py

20 combinations: five models at 320, 375, 768 and 1440 CSS pixels wide.
Checks: distinct control rectangles, no horizontal page overflow, 12 numeric keys,
left/right actions, C label consistency, up/down dispatch, numeric shortcuts,
call/end dispatch, roller click/wheel, cover visibility/inertness, saved selection,
blocked storage, keyboard isolation in the picker and repeated cycling.
JavaScript syntax (node --check) and CSS top-level parsing also passed.

The browser check uses tests/fixtures/handset-shell.html, with the existing DOM
contract and instrumented application callbacks. It is NOT a complete application
or playback integration test. No deployed visual screenshot review, Safari,
Firefox or real touch-device test was performed.

Optional browser-test dependencies (not needed at runtime or by the Pages build):

    python -m pip install playwright
    python -m playwright install chromium
    python tools/check_handsets.py

To inspect just the shell locally:

    python -m http.server 8000

Open /tests/fixtures/handset-shell.html on that local server. Its LCD is a test
placeholder, not the actual cinema UI.

After deploying, manually check Home > Options > HANDSET, all five themes,
Back, opening a transmission, play/pause, seeking with 4/6, sharing with 3,
backlight with #, the 7110 cover and an actual reload preserving the model.

## Reference basis

Original-era model references, not modern HMD namesakes:
https://en.wikipedia.org/wiki/Nokia_3310 (Navi, C, up/down)
https://www.manualslib.com/manual/112225/Nokia-8210.html (scroll keys)
https://www.manualslib.com/manual/112158/Nokia-6310.html (selection/scroll keys)
https://en.wikipedia.org/wiki/Nokia_7110 (roller and sliding cover)

## Rollback (after committing, with a clean working tree)

    git restore --source=46eb39fccb48e1bd148811f7055a979756e7545d -- theme.js themes.css

Then commit that restoration and redeploy normally. Existing saved handset IDs
are compatible with the previous implementation.
