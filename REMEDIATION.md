# Remediation and improvement plan

## Incident summary

Between commits `1a5ef07` and `2ee3b8f`, four files on `main` were overwritten with literal placeholder text instead of the intended streaming-navigation implementation:

- `streaming.js` -> `PLACEHOLDER_STREAMING`
- `sharing.js` -> `PLACEHOLDER_SHARING`
- `NAVIGATION.md` -> `PLACEHOLDER_NAV`
- `tools/phone_video.py` -> `PLACEHOLDER_PHONE_VIDEO`

The affected commits are:

- `1a5ef07`
- `74b1f60`
- `6758632`
- `2ee3b8f`

The last known-good commit is `e0d7534` ("Recompose ASCII scenes for native handset playback and remove frame banners"). Its playback changes remain intact in Git history, but the four later commits must be treated as broken and must not be deployed or built from.

## Immediate rule

Do not make another remote commit or push until the replacement files have been written locally, inspected with `git diff`, and verified by the checks below.

No further corrective push should be made from this chat session. The repair should be performed from a local clone where file contents can be read before committing.

## Recovery steps

1. Clone or update a local copy of `koesac-lab/wapflix`.
2. Confirm the broken range:

```bash
git log --oneline -8
git show 1a5ef07 --stat
git show 2ee3b8f --stat
```

3. Create a repair branch from the last good commit:

```bash
git checkout -b repair/streaming-navigation e0d7534
```

4. Restore the affected paths from the good commit:

```bash
git checkout e0d7534 -- sharing.js tools/phone_video.py
```

This intentionally restores the pre-streaming versions of `sharing.js` and `tools/phone_video.py`. Do not restore placeholder files.

5. Remove the broken placeholder files from the working tree:

```bash
rm -f streaming.js NAVIGATION.md
```

6. Copy the repaired files from this kit into the repository root:

```bash
cp streaming.js sharing.js NAVIGATION.md .
cp tools/phone_video.py tools/phone_video.py
```

7. Inspect every file before staging:

```bash
git diff
grep -R "PLACEHOLDER_" . || true
```

The grep command must return no matches.

8. Run the local checks in the next section.

9. Commit on the repair branch:

```bash
git add streaming.js sharing.js NAVIGATION.md tools/phone_video.py tests/test_phone_video.py
git commit -m "Repair streaming navigation sources and add regression safeguards"
```

10. Open a pull request. Do not merge until CI and the manual checks pass.

11. After review, merge the pull request. Avoid directly pushing to `main` until the repair has been verified.

## Required behaviour

### streaming.js

- Home view with Continue Watching, Series, Original Transmissions, My List and Options.
- Continue Watching entries limited to three, showing saved progress percentages.
- Local progress storage with elapsed time, duration and last-watched timestamp.
- Finished transmissions removed from Continue Watching.
- Series list, series detail, episode list and transmission details views.
- Episode progress percentage, progress bar and SEEN state.
- Play and Resume actions that buffer before starting playback.
- My List add/remove action.
- Options for Autoplay Next, connection quality, backlight and About.
- Five-second next-episode countdown after an episode ends.
- Play Now and Cancel actions on the end card.
- No autoplay for shared links.
- `*` returns Home.
- Existing keypad shortcuts remain working.

### sharing.js

- Sharing works from both the player and details views.
- Shared episode links open without autoplay.
- A shared playback position is restored when present.
- The station-sharing fallback remains available.

### tools/phone_video.py

- Copies `streaming.js` into the build output.
- Loads scripts in this order:

```html
<script src="./player.js?v=lcd2" defer></script>
<script src="./streaming.js?v=1" defer></script>
<script src="./sharing.js" defer></script>
```

- Keeps the existing sharing integration anchor intact.
- Keeps the native 240 x 200 handset scene composition from `e0d7534`.

## Checks before commit

```bash
node --check streaming.js
node --check sharing.js
node --check player.js
python -m py_compile tools/phone_video.py
python -m unittest discover -s tests
grep -R "PLACEHOLDER_" . || true
```

All syntax checks and unit tests must pass. The placeholder search must return no matches.

Then run the behavioural smoke test covering:

- Home renders.
- Continue Watching appears after meaningful progress.
- Series navigation reaches the episode list.
- Play starts after buffering.
- Ending an episode shows the countdown.
- Countdown completion loads the next episode.
- Back returns to the episode list.
- My List add/remove works.
- Progress persists.
- Shared links open without autoplay.

## Deployment checks

After merging, inspect the GitHub Actions run before treating the deployment as successful.

Verify:

1. The Pages workflow completes.
2. The deployed `streaming.js` contains the real implementation.
3. The built `index.html` loads scripts in the order shown above.
4. Home shows Continue Watching only when progress exists.
5. A series can be opened, an episode selected, and playback started.
6. Pausing, resuming, seeking, Info, captions, quality, sharing and backlight still work.
7. Ending an episode shows the countdown and can load the next episode.
8. A shared episode link opens paused at the shared position.

## Process improvements

1. No direct pushes to `main`; use short-lived branches and pull requests.
2. Require CI before merge.
3. Add a placeholder guard to CI that fails if `PLACEHOLDER_STREAMING`, `PLACEHOLDER_SHARING`, `PLACEHOLDER_NAV` or `PLACEHOLDER_PHONE_VIDEO` appears anywhere.
4. Require a local build and smoke test before merge.
5. Use file uploads or a local Git commit for large source changes; do not pass whole source files as inline text through a remote-commit tool.
6. Verify the commit immediately after pushing by reading back the changed files and comparing hashes or key markers.
7. Protect `main` with required checks and review.
8. Keep this recovery plan in the repository until the repair is deployed and verified.

## Acceptance criteria

- `main` contains no `PLACEHOLDER_*` text.
- `streaming.js`, `sharing.js`, `NAVIGATION.md` and `tools/phone_video.py` contain their real implementations.
- The Pages deployment succeeds.
- The live site loads Home, plays a transmission, saves progress, resumes it, and offers the next-episode countdown.
- Shared links open without autoplay.
- The playback improvements from `e0d7534` still work.
- A pull request, rather than a direct push, introduced the repaired files.
