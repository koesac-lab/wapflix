# Navigation model

WAPFLIX borrows the useful structure of a streaming service while keeping the interaction model of a WAP browser: one focused card at a time, text-first navigation, an inverted selection highlight and context-sensitive soft keys.

## Home

Home shows up to three Continue Watching entries, followed by Series, Original Transmissions, My List and Options. Continue Watching only appears when a transmission has meaningful saved progress; it does not pad the screen with empty sections.

Progress is stored locally with the elapsed time, duration and last-watched timestamp. A transmission is considered finished once it is within two seconds of the end, so completed items leave Continue Watching.

## Browsing

The hierarchy is Home, Series, Series detail, Episodes, Details, then Player. Original transmissions go directly from Home to their episode list.

The series card shows the season, episode count, a short description and the next item to resume. The episode list shows per-episode progress as a percentage, a progress bar for the highlighted item, or SEEN once finished.

Details pauses nothing and loads nothing until the visitor chooses Play or Resume. It shows the description, saved position and the My List action.

## Playback

Choosing Play or Resume buffers the clip, then starts it without a second confirmation. Pressing 1 opens Info and pauses playback; Back closes Info without losing position.

When a clip ends, WAPFLIX shows a short end card. If Autoplay Next is on and another episode follows, it counts down from five seconds; Play Now starts immediately and Cancel returns to the episode list. Shared links never autoplay: they open the episode ready to play, restoring the shared position when one was included.

## Soft keys

The two labelled keys always match the current card:

- Home: Open and Options.
- Series list: Open and Back.
- Series: Select and Back.
- Episodes: Details and Back.
- Details: Select and Back.
- Playing: Pause and Back.
- End card: Play Now and Cancel.

The keypad keeps its shortcuts: 1 Info, 2/8 navigation, 4/6 seeking, 5 select, 0 connection quality, * home, # backlight and 3 sharing. Search is intentionally not part of this pass; it deserves its own keypad input design rather than a compromised shortcut.
