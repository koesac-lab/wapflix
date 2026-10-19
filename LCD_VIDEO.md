# One-bit LCD playback

The published handset player defaults to dithered bitmap frames. Press 7 during playback to switch to ASCII; the choice persists locally. Info (1) shows the active mode; captions (2), seeking, resume and next-item navigation keep their existing controls. ASCII-only custom clips still work.

The Pages workflow runs tools/lcd_video.py after phone_video.py. It adds lcd_variants to the built catalogue without replacing ASCII variants. Original procedural greyscale illustrations supply the demo frames, not rasterised characters or actual episode footage. Existing catalogue posters and social artwork are unchanged. The progressive-test server is unchanged and remains ASCII-only.

## Real video

Create an ASCII entry, then add LCD variants from the same interval:

```sh
python tools/build.py input.mp4 --output assets --id night-walk --title "Night walk" --start 35 --seconds 15
python tools/lcd_video.py --output . --video input.mp4 --id night-walk --start 35 --seconds 15
```

Both commands need FFmpeg/ffprobe. Use matching intervals. Subtitle timestamps must already be relative to the extracted clip; LCD variants inherit them. For a built site use --output _site/assets on build.py and --output _site on lcd_video.py.

## Format and limits

Presets: 60 pixels wide/4 fps, 80/6, 120/8. Pixels are square and enlarged by integer factors when they fit. A fixed 4x4 Bayer matrix produces apparent grey using only dark ink and transparent LCD background.

Frames use layout lcd-1bit, encoding hex-msb, cols, rows, fps, frames and subtitles. Bits are row-major, MSB first, 1 = ink; rows have no padding, only the final byte does. Hex JSON is gzip-compressed. This remains whole-clip buffered playback, not progressive transport or an efficiency claim against video codecs. It is fictional cinema on an enlarged display, not historical WAP video support.

Run python -m unittest discover -s tests and node tests/test_lcd_player.cjs. Automated checks do not replace visual browser testing.
