# First watchable ASCII clip: isolated local test

This patch adds only tools/export_ascii_test.py, tests/test_export_ascii_test.py
and this document. Existing diagnostics, player, navigation, styles and GitHub
Pages workflow are not modified. No remote writes or commits are made.

## Apply

From the WAPFLIX root after placing the tar there:

    tar --keep-old-files -xzf wapflix-first-playback.tar.gz

Stop if tar reports an existing file. Do not force an overwrite.
Python 3.10+ and ffmpeg/ffprobe on PATH are required. No pip dependencies.

## Step 1: export ten seconds

The default source is the previously downloaded test MP4 at
~/.local/share/wapflix/test-media/dQw4w9WgXcQ/source.mp4.
The default extract starts at 30 seconds and lasts 10 seconds.

    PLAY_DIR=$(mktemp -d /tmp/wapflix-first-play.XXXXXX)
    python3 tools/export_ascii_test.py --output "$PLAY_DIR"

Successful output reports 60 frames, a 10-second duration and the output folder.
The output folder contains clip.json and index.html. Output must be new or empty.
For a different source, supply --video /path/to/video.mp4, --start and --seconds
(maximum 30). This is an offline short clip, not a progressive converter.
The standalone exporter intentionally avoids a dependency on diagnostic revisions.

## Step 2: view it

Same terminal, preserving PLAY_DIR:

    python3 -m http.server 8099 --bind 0.0.0.0 --directory "$PLAY_DIR"

Open http://YOUR_SERVER_LAN_OR_TAILSCALE_IP:8099 in your browser. The console
message 0.0.0.0 is the listen address, not the address to browse on another device.
For browser and server on the same machine, use http://127.0.0.1:8099.
Trusted LAN/Tailscale test only: this temporary HTTP server has no authentication.
Do not expose the port through a public tunnel or router forwarding. It serves
only the generated output folder, not the repository. Ctrl-C stops the server.
If port 8099 is busy, use 8100 in both the command and browser URL.

## Scope and acceptance

Click Play: ASCII motion should run for ten seconds. Pause, Restart and seek
should work. The page pauses when hidden. It uses browser monospace glyphs in
6x8 cells, not the final handset bitmap renderer: visual equivalence is not
claimed. No audio, subtitles, handset integration, streaming API, Docker or Plex.
The whole clip loads before playback. Nothing is added to public assets.

Generated clip frames are private runtime media. Do not stage them, the archive
or temporary folders. Commit only the three patch files after local review.

## Verification

Four Python exporter tests passed with actual FFmpeg-generated footage. Browser
checks in headless Chromium passed: load, canvas dimensions, play, pause, seek,
end-of-clip, restart, missing-clip error and no uncaught JavaScript errors.
JavaScript syntax was checked with Node. These checks use generated fixtures,
not the user's N5105, downloaded source or live Pages. No performance guarantee.

    python3 -m unittest discover -s tests -p test_export_ascii_test.py -v
