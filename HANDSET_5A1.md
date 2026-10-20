# 5A.1: existing handset, local static playback only

Adds tools/handset_static_preview.py, tests/test_handset_static_preview.py and this document. No files from milestones 1-4, Pages workflows, player scripts, themes or media are modified. The server does not run FFmpeg, generate video, rebuild Pages or connect to the streaming API. It serves the static samples already present in assets/catalogue.json and their referenced JSON/gzip assets.

## Install and run

Extract this archive into the repository root with tar --keep-old-files -xzf and its filename. Stop on extraction errors.

```sh
cd ~/wapflix
python3 -m unittest discover -s tests -p 'test_handset_static_preview.py' -v
python3 tools/handset_static_preview.py --bind 0.0.0.0 --port 8102
```

Open http://YOUR_MINI_PC_LAN_IP:8102/. Your existing M4 server can remain on 8101; the two are independent at this checkpoint. --allow-host mini-pc.local accepts an explicit local hostname alias. --root /path/to/wapflix selects another checkout. Stop this preview with Ctrl-C. Nothing is auto-committed or uploaded.

The served HTML is assembled in memory from the source index.html with the existing player.js, streaming.js, theme.js, themes.css, sharing.js and sharing.css. It preserves the same script order/readiness hooks as the current presentation and phone build. Original HTML, scripts and catalogue files are not rewritten. Catalogue/assets are validated before serving; missing referenced files fail clearly instead of silently generating replacements. Restart this preview after changing the catalogue.

Only the handset page, six frontend files and catalogue-referenced converted JSON assets are served. There is no directory listing or API proxy. Source video, tools, backups and Git internals are not exposed as static routes. Catalogue IDs get local /share/ID/ redirects to ?episode=ID, but full social-preview generation and browser clipboard/share behaviour on insecure LAN HTTP are not acceptance goals here.

Gzip files deliberately have no Content-Encoding header because the existing static player decompresses them explicitly. A restrictive CSP allows its inline bootstrap via a nonce and same-origin scripts/assets. This is still a trusted-LAN development preview, not public authentication or a production service.

## Acceptance gate

1. The local URL shows the existing handset housing, theme selector and catalogue.
2. Open Video test or another existing static title. Play/pause and Back work as before.
3. Change handset model and confirm controls remain usable.
4. The M4 streaming viewer on its separate port is unaffected.

Six focused tests passed: guarded bootstrap/order/readiness; unchanged source files; HTTP routes/MIME and explicit gzip; missing assets; path/symlink safety; no directory/source exposure; Host checks and local share redirect. Node syntax checking is included when Node is present. These tests use a small frontend/asset fixture, not a real-browser visual or full catalogue test. The current repository source bootstrap anchors were inspected before building this patch.

If this passes, 5A.2 should add only the independent browser source adapter. Do not combine that with handset controls, seeking, Docker or catalogue expansion. This archive implements 5A.1 only.
