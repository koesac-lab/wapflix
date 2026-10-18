# WAPFLIX handset study v6

## Scope and verified baseline

Prepared after reading current main. Baseline Git blob IDs:
- theme.js: 393c6672d4acff389df8ad050c4ebb1ad13aeaaf (working v4 controls)
- themes.css: 098845ff8c8fa916e860eeca1b8721fcb0fa9a4d (v5 styling)
- index.html: 068d6d66116044346e1abb87d703b90428aa2d41
- tools/phone_video.py: fe535c051aed4dadc2d5994a746ce4db912b8858

Two runtime replacements: theme.js, themes.css. Also replaces the optional browser
check and its fixture; adds these notes and a checksum manifest. No network
requests, downloaded fonts, external images, package additions or build changes.
No repository writes were performed by the assistant.

## Apply at the repository root, with a clean working tree

    git status --short
    git switch -c handset-study-v6
    tar -tzf wapflix-handset-study-v6.tar.gz
    tar -xzf wapflix-handset-study-v6.tar.gz
    sha256sum -c HANDSET_V6.sha256
    git diff --check
    node --check theme.js
    python -m unittest discover -s tests
    git diff --stat

Optional browser checks (requires Playwright and its Chromium browser):

    python tools/check_handsets.py

Review, commit, then merge using the normal project process. Explicit staging
avoids accidentally adding downloaded patch archives or unrelated changes:

    git add theme.js themes.css tools/check_handsets.py \
      tests/fixtures/handset-shell.html HANDSET_V6.md HANDSET_V6.sha256
    git commit -m "Rebuild handset faceplates and refine original-era details"
    git switch main
    git pull --ff-only origin main
    git merge handset-study-v6
    git push origin main

Stop if checks fail, there are conflicts, or branch protection rejects the push.
Do not force-push. The current Pages build already copies both runtime files into
_site. Hard-refresh after deployment; asset URL versions remain unchanged.

## Actual changes from v5

1. Rebuilt upper housing. Speaker, brand, LCD and navigation form one head
   assembly. Its continuous faceplate extends under the controls, rather than
   looking like a separate generic screen box glued to every model.
2. NOKIA text on the casing instead of WAPFLIX/model text. This is a system-font
   approximation, not a claimed exact vector reproduction of the Nokia wordmark.
   WAPFLIX remains on the app's actual canvas, and the model picker stays outside.
3. Shortcut legend moved off the casing into an accessible collapsible help
   section. No loss of numeric shortcut functions or original button handlers.
4. 3210: silver/grey body, broad shoulders, dark display lens, dark Navi button,
   larger straight rectangular rubber-style keys and distinct C/scroll cluster.
5. 3310: navy perimeter and continuous pale shield, curved screen lens, pale keys
   with a restrained fan angle, centre Navi and separate C/up/down keys.
6. 8210: red perimeter with black upper mask, light ivory compact oval keys,
   smaller earpiece and selection/call keys around the narrow scroll control.
7. 6310: champagne/graphite treatment, long dark centre panel, narrow rocker and
   dark elongated business-style keys with pale legends, rather than pale keys
   on the previous generic olive body.
8. 7110: antenna, olive metallic mask, one visual knurled wheel with accessible
   scroll tap zones, and a rigid full-height slide. The cover translates down
   outside the housing; it no longer stretches/collapses into a thin strip.
   Space is reserved underneath to prevent overlap with the external picker.
9. Smaller details: recessed earpieces, key recess/edge shading, lower-case letter
   legends, voicemail marking, microphone slots and narrow selection-key marks.
10. A top-edge hardware-style button toggles the existing backlight; it does NOT
    pretend to power the application off. Accessible pressed state tracks #.

## Deliberate limitations

This is an original-era visual study, not a perfect photographic replica or an
original firmware emulator. The 240x224 cinema canvas is unchanged: the originals'
smaller, differently proportioned LCDs would need a separate renderer/menu redesign
to reproduce faithfully without squashing or making the existing UI illegible.
No cropping, aspect-ratio distortion, hidden menu rows or resolution fakery has
been introduced. Exact colourway, mould tooling and Nokia logotype are not claimed.
Modern web usability adaptations remain: call selects/plays, end goes Home,
Navi/roller selects, and extra roller tap zones work on touchscreens.
The top button is a backlight control. Sliding is click/tap, not drag/gesture.

## Reference basis

Original models, not the later HMD namesakes:
- https://www.mobilephonemuseum.com/phone-detail/nokia-3310
  Original-era model, Navi key and Xpress-on cover family.
- https://www.mobilephonemuseum.com/phone-detail/nokia-8210
  Original-era 8210 reference.
- https://www.mobilephonemuseum.com/phone-detail/nokia-7110
  Spring-loaded slide, antenna and clickable multifunction NaviRoller.
- https://collection.sciencemuseumgroup.org.uk/objects/co8226988/nokia-3210-mobile-cellular-telephone
  Silver original-era 3210 reference photograph.
- https://en.wikipedia.org/wiki/Nokia_6310
  Original 6310 front reference, not a modern remake.
- https://www.olimex.com/Products/Components/LCD/LCD-DISPLAY-NOKIA3310/
  84x48 display reference, explaining the intentionally retained cinema compromise.

References informed the interpretation; their photos are not redistributed.

## Executed verification

- node --check theme.js: PASS.
- CSS top-level rules and declaration parsing: PASS.
- Headless Chromium: 25 combinations (five phones at 280x640, 320x568, 375x812,
  768x900 and 1440x1000 CSS pixels).
- No horizontal overflow or overlapping main/numeric control rectangles.
- Original canvas, left/back elements and every numeric onclick handler preserved.
- Correct C/back accessible label after application footer updates.
- Numeric controls, call/end, up/down, top backlight and roller click/wheel dispatch.
- Slide remains rigid; open cover clears every key; closed keypad is hidden/inert.
- Saved model selection, denied storage, no duplicate structures on repeated cycles.
- Picker keyboard isolation and layout after a viewport resize.
- Normal and reduced-motion slide operation, plus Chromium emulated-touch tapping.

This uses the checked-in shell fixture with the original base CSS and instrumented
application callbacks. It is NOT the full catalogue/playback application. The
project's full Python tests and deployment were not run in this environment.
Safari, Firefox, real mobile hardware, and a human visual comparison are unverified.
The standalone comparison preview is a mock screen for visual inspection only.

## Preview and post-deploy checks

Open the separately supplied offline HTML comparison preview. It contains the same
runtime CSS/JS with a labelled demo canvas, not live catalogue content.
Alternatively serve the repo with python -m http.server 8000 and open
/tests/fixtures/handset-shell.html to inspect the individual model picker.

After the normal Pages deployment, check model switching via both picker and
Options, Home/Back, opening a transmission, play/pause, 4/6 seek, 3 sharing,
# backlight, screen-reader labels and the 7110 cover. Reload to verify persistence.

## Rollback

After a clean commit, use git revert on that v6 commit, then redeploy normally.
Do not assume HEAD~1 is the correct restore target after other work or merges.
