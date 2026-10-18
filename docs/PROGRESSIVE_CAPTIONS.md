# Actual YouTube captions on the progressive test

This adds a caption-enabled wrapper; it does not overwrite the known-working
progressive_test.py, srt.py, diagnostic, existing player or Pages workflow.
Dependencies: the previously installed progressive test and SRT parser,
Python 3.10+, FFmpeg/ffprobe, and yt-dlp for the download step. No new pip packages.

## 1. Apply

Place the archive in the WAPFLIX root, then run:

    tar --keep-old-files -xzf wapflix-progressive-captions.tar.gz

Stop on an extraction error. No files should be forcibly overwritten.

## 2. Source the subtitles from YouTube

    python3 tools/fetch_test_subtitles.py

The helper uses the exact video already used for the MP4:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
It extracts metadata, selects one English track, requests only subtitles and
converts the selected track to SRT through yt-dlp/FFmpeg. Uploaded captions are
preferred over automatic captions; automatic English is a fallback, not a claim
that it is a human transcript. Priority within each type is en, en-orig, en-US,
en-GB, then another English locale. It does not download the MP4 again.

Output stays outside the repo:

    ~/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.youtube.en.srt
    ~/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.youtube.en.json

The JSON records source URL, video ID, selected language/type, cue count, fetch
time and a SHA-256 hash. It contains no caption text. A successful existing pair
is reused; mismatched files are rejected. To fetch anew explicitly:

    python3 tools/fetch_test_subtitles.py --refresh

Refresh preserves backups of old SRT/JSON files. Download staging is temporary.
If there is no English track, yt-dlp fails, or no valid SRT is produced, the helper
stops with an error. It never substitutes invented captions. No updates, cookies,
login bypasses or transcription services are invoked. Network availability and
current YouTube extractor behaviour are not guaranteed; retain the actual error
if download fails. Metadata lookup and track download make separate requests.

The download has NOT been performed in the patch-build environment. Downloader
control-flow tests use synthetic metadata/caption fixtures. A real successful
helper run on the host is required before claiming the video captions were sourced.

## 3. Start the caption-enabled server

Stop the old progressive server with Ctrl-C in its terminal, then run:

    python3 tools/progressive_captions.py --bind 0.0.0.0 --port 8100

Open the same server LAN/Tailscale address on port 8100. Reload, then press Start.
The default extract is still source seconds 30-90. Captions display beneath the
picture, with an on/off button. The console and page report overlap count and
parser warning count. This is still a silent test; no audio has been added.

Keep this port private on a trusted LAN/Tailscale network. There is no login.
Do not publish it through a tunnel/router forwarding. Default bind without the
flag is loopback. Existing base API token protections are preserved, but they are
not user authentication. Ctrl-C stops the worker and server.

To use another local SRT or source, supply explicit --video and --subtitles paths.
SRT must be timed to the complete source, not already shifted to the extract.
A valid file with no cues in the extract is reported as such, not a successful
caption playback assertion. The default expected filename is source.youtube.en.srt
beside the configured video. Running the wrapper never downloads anything.

## Timing and behaviour

A source cue from 35-37 seconds maps to playback seconds 5-7 for an extract
starting at 30. Cues crossing the extract start/end are clipped appropriately.
Captions use the progressive player's existing media clock, NOT wall time or
worker progress. Therefore pause/buffering freezes both picture and captions.
Stop clears captions; Start resets timing. Overlapping cues remain supported;
identical displayed lines are deduplicated. Automatic rolling captions may still
look more repetitive than uploaded captions: no semantic rewriting is attempted.

Subtitle text uses textContent, not HTML rendering. Unknown tags display as text;
common formatting is handled by the existing SRT parser. HTML entities are decoded.
Captions are fetched once per session from a token-protected endpoint, not copied
into each video chunk or repeatedly transmitted on every heartbeat.

## Test in two passes

1. Set delay 0 and Start. Check captions appear and change with the picture.
2. Pause: caption should stay fixed. Toggle off/on while paused.
3. Stop then Start: first captions must reset to the extract's beginning.
4. Set delay 5 and Start. Initial buffering takes around ten seconds. When the
   video catches up, its clock and any active caption must freeze and resume
   together when another chunk arrives. Blank intervals between actual cues
   are normal; no cue is prolonged just to keep text visible.

YouTube subtitle timing is not a ground-truth sync guarantee. The same video ID
keeps sources aligned, but the downloaded track itself may have imperfect timing,
especially for automatic captions. Report source/type and an observed offset
before adding an artificial sync adjustment.

## Verification and limitations

    python3 -m unittest discover -s tests -p test_progressive_captions.py -v

Eleven Python tests passed in the isolated build environment. They cover uploaded
vs automatic selection, language fallback, missing-English failure, time offsets,
overlap/clipping, entities, cache provenance, missing subtitle output, compatibility
checks and a real FFmpeg-worker caption endpoint. External yt-dlp calls in download
tests are mocked; they do not verify the current live YouTube track.

Chromium tests used synthetic original SRT cues and real FFmpeg-generated video,
with a fixture reconstruction of the previously supplied progressive revision.
Checks passed for a cue already active at extract start, safe literal text,
pause/toggle, a cue spanning a forced underrun, clock/caption freeze and recovery,
Stop clearing captions, restart reset and no uncaught JavaScript errors.
Python/JavaScript syntax and the final archive contents were checked.
The working runtime dependency files are NOT bundled or overwritten.

Not verified here: the user's N5105, actual downloaded YouTube captions, every
browser, complete current repository, live Pages, seek/Docker/Plex integration.
A compatibility guard refuses to inject into an unexpected progressive page shape.

No media, captions, credentials, caches or fixture dependency files are shipped.
Do not commit fetched captions, provenance/backups, the archive or runtime media.
Review and stage only the five new patch files if committing locally.
