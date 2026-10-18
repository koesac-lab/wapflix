# Navigation v3: behaviour contract and review checklist

This patch replaces streaming.js instead of layering another correction around it. It leaves index.html, player.js, sharing.js, theme.js and themes.css unchanged. The only build change is a cache-busting streaming script URL, from v=1 to v=nav3.

## Scope and honest limits

This is a navigation and physical-control wiring repair, not a new handset replica. Existing theme colours and shapes remain. No claim is made that the current five skins accurately reproduce their historical handsets. Model-specific hardware layouts need a separate reviewed DOM/CSS implementation; stretching a generic nav cluster is not that implementation.

The automated tests use a Node VM with controlled player/DOM/storage fixtures, not a real browser. They check controller transitions, button dispatch, drawing coordinates, progress and frame scheduling. They do not prove visual appearance, a live Pages deployment, native share-sheet behaviour, or browser-specific keyboard defaults. The actual sharing script is left intact; shared-style load semantics are tested, not the native share dialog itself.

## Fixed controller defects

- Rebind the physical Back button through the current controller, rather than retaining an old function reference.
- Home's right soft key opens Options as its footer says. Escape on Home stays Home.
- Both soft keys leave About and empty lists. About now has its own content renderer.
- Back closes Info before leaving playback.
- A screen-history stack replaces stale returnView overrides. Playback returns to its launching screen; Details returns to the exact list page and selection.
- Six-row pagination applies to Home, series lists, episodes and My List; every menu clamps at its boundaries rather than mixing wrapping and clamping.
- Title and menu text have separate vertical bands, removing the first-row collision.
- Play/Resume from My List or Continue Watching resolves the real group and episode, avoiding a next episode from the wrong collection.
- Home and pagehide flush progress. Completed entries retain a complete flag for SEEN but do not appear in Continue Watching.
- Request/version checks prevent a cancelled or superseded load from starting playback.
- A shared-style load is paused unless autoplay was explicitly requested. A paused position at the end does not start the next-episode countdown.
- The countdown uses scheduled frames and pauses while the document is hidden.
- The dedicated up/down controls browse menus and do nothing during playback. They no longer trigger the numeric 2 caption shortcut accidentally.
- Quality changes preserve time and whether playback was playing or paused.

## Button contract

| Context | Left soft key / OK | Right soft key | Up/down | Left navigation key |
|---|---|---|---|---|
| Home | Open selected item | Options | Browse, bounded | Stay Home |
| List | Open selected item | Previous screen | Browse, bounded | Previous screen |
| Details / Series | Labelled action | Previous screen | Choose action | Previous screen |
| Options | Change / Open | Previous screen | Choose setting | Previous screen |
| About / Empty list | Back | Back | No action | Back |
| Playback | Play / Pause | Return to launcher | No action | Rewind five seconds |
| Info | Play | Close Info | No action | Rewind five seconds |
| End card | Play next / Replay | Episodes | No action | Episodes |

Numeric 2/8 browse menus; during playback numeric 2 keeps its caption shortcut. Numeric 4/6 seek only in playback. Numeric 0 changes connection quality. Numeric 1 retains Info. Numeric 3 retains the sharing integration. Star saves progress and returns Home; hash toggles backlight.

## Review before merge

- [ ] Inspect git diff; only the four listed files should be staged.
- [ ] Run node --check streaming.js.
- [ ] Run node tests/test_streaming_nav.cjs (17 fixture-based regression tests).
- [ ] Run python3 -m py_compile tools/phone_video.py.
- [ ] Run python3 -m unittest discover -s tests.
- [ ] Build with the existing Pages commands, starting from a clean _site directory; verify v=nav3 in generated index.html.
- [ ] In a browser, test physical Back as well as Escape and soft-key/OK selection.
- [ ] Open Options from Home's right soft key; Back restores the highlighted item.
- [ ] Open About from Options; both soft keys return to Options.
- [ ] Save more than six items and navigate every My List page.
- [ ] Start an item in a different collection from My List; next episode must stay in that collection.
- [ ] Enter Info while playing; Back closes only Info, a second Back returns to the launcher.
- [ ] Try both a normal and a position-bearing shared link: neither starts automatically.
- [ ] Start, cancel and complete the next-episode countdown; test switching tabs.
- [ ] Test all five existing themes at narrow width and short viewport height.

## Rollback

Before commit, the installer keeps original overwritten files in .wapflix-nav-v3-backup. Use those backups if needed and remove newly added test/document paths only after checking they were new. After merge, revert the repair commit in a new PR; do not force-push shared history.

## Next work, deliberately not bundled here

1. Add node tests/test_streaming_nav.cjs as a required CI command alongside the existing scene tests.
2. Replace generic handset controls with explicitly reviewed per-theme hardware layouts and large enough touch hit areas.
3. Add actual-browser interaction and screenshot tests for physical buttons, keyboard focus and each screen size.
4. Introduce a real show-to-season selector rather than labelling season collections as distinct shows.
5. Give series their own sourced description instead of borrowing an episode summary.
