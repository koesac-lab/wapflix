# Sharing and app identity

Press 3 / SHARE from the handset. The green sharing dialog can share the selected transmission or the whole station, optionally including the current playback position. Playback pauses when sharing opens and does not resume automatically. Device share calls the native Web Share API only after a button press; unsupported or blocked browsers retain Copy link, WhatsApp and Email options. Clipboard failures select the URL for manual copying. No link is sent automatically.

Each transmission has a static share/<id>/ page with its own server-rendered Open Graph and Twitter tags and a 1200x630 PNG preview. These pages open the corresponding clip in the handset; a normal link remains available without JavaScript. Root previews use the project's original green-screen artwork. Third-party preview caching and rendering are controlled by the sharing platform, not this application.

The build generates a pixel-film/play favicon in SVG and multi-size ICO formats, 16/32px PNGs, a 180px Apple touch icon, 192/512px app icons and an opaque safe-zone maskable icon. The manifest sets a project-relative start URL and scope, standalone display and matching colours. No service worker, offline playback or guaranteed install prompt is implied.

The Pages workflow runs tools/presentation.py after generating the catalogue. It enriches the source index.html at build time; integration anchors are checked so incompatible source changes fail clearly. No image/font dependencies or remote services are needed for asset generation.

Local published-site preview:

```sh
python3 tools/build.py --output _site/assets
python3 tools/catalogue.py --output _site/assets
python3 tools/presentation.py --output _site --base-url http://localhost:8000/
python3 -m http.server 8000 --directory _site
```

Production defaults to https://koesac-lab.github.io/wapflix/ . Pass --base-url when changing the public hostname or project path. Native sharing, clipboard and home-screen behaviour still depend on browser and platform support.
