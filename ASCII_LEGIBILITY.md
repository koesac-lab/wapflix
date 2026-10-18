# ASCII legibility tuning lab

This is a **local experiment**, not part of the deployed WAPFLIX site.

Its purpose is to establish why real-video ASCII output is difficult to read and to compare conversion settings on identical frames.

## Scope

The lab deliberately excludes:

- The caption-enabled progressive playback server.
- Seeking and playback transport changes.
- The downloaded source video.
- Any automatic enhancement that changes the public site without review.

## What it compares

For a user-selected video, the lab extracts a bounded set of preview frames and renders four synchronised views:

1. Original frame.
2. Processed grayscale frame.
3. Low-resolution pixel-grid version.
4. ASCII conversion.

This separates source-detail loss from character-mapping loss.

## Tunable settings

- Columns: 40, 60, 80, 96.
- Crop: none, centre, or adjustable subject crop.
- Brightness, contrast, gamma, black point and white point.
- Invert polarity.
- Character ramp: short density-calibrated or longer ramp.
- Tonal levels: 4, 6 or 10.
- Display scale: native or enlarged.
- Frame rate comparison: 6, 8 or 12 fps.

## Baseline issue

The initial progressive test mapped dark source pixels to spaces and bright pixels to dense characters, while drawing dark glyphs on a light display. That can reverse perceived brightness.

The lab makes polarity explicit and provides a black-to-white calibration strip.

## Presets

`tools/ascii_presets.json` contains comparison presets only. They are not claimed to be final quality settings.

- `baseline-current`: retained for comparison.
- `corrected-polarity`: dark source pixels map to dense glyphs.
- `wide-80`: 80-column comparison.
- `subject-crop`: centre crop with moderate contrast adjustment.

## Test procedure

1. Run the lab locally against a licence-cleared test clip.
2. Pause on a representative frame.
3. Compare the four views.
4. Adjust one setting at a time.
5. Save the best candidate as a preset.
6. Only then consider applying it to the progressive converter.

## Acceptance criteria

A conversion setting is worth promoting only when:

- A face or principal subject is recognisable in the low-resolution pixel view.
- The ASCII version preserves the same broad light/dark structure.
- Motion remains stable enough to follow.
- Captions remain readable beneath the image.
- The setting does not require an impractical number of characters or processing cost.

## Test-video policy

Do not commit downloaded third-party video unless its licence explicitly permits redistribution.

Prefer a generated synthetic fixture, a public-domain clip, or a short licence-cleared excerpt with documented provenance.
