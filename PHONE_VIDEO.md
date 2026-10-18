# Handset playback composition

Episode demo scenes are generated as 40 columns by 25 rows, rendered at 6x8 pixels per character: a native 240x200 scene on the 240x224 LCD. All three quality levels share that composition; their real text assets differ in frame rate (4/6/8 fps). The modem labels remain fictional product labels, not speed measurements.

The scenes contain no title cards, branding banners, duration labels or fictional-footage warnings. Instead, the episode description, Info screen, catalogue metadata and social previews explain that playback is invented ASCII art, not episode footage. Actual clip durations remain in the data for scheduling and seeking.

During playback, the picture uses the full scene area. Only active subtitles, a thin progress indicator and the two soft-key labels appear. Pausing reveals the episode title and clock. Press 1 for Info, 2 to toggle captions, and 3 for sharing. Info pauses playback; Back closes Info without losing position, while Play returns to the picture and resumes.

Original non-episode transmissions and imported clips retain their source composition and are fitted without cropping; the renderer assumes their original 1:2 character-cell aspect ratio. ASCII drawing no longer uppercases brightness-ramp characters. Handset-native frames use the bitmap font at integer size, avoiding the old shrinking of 48/72/96-column scenes into a small video window.

The build order is build.py, catalogue.py, presentation.py, then phone_video.py. The last step recomposes episode demos, updates clip sizes/posters in the catalogue, copies player.js and loads it before sharing.js. It does not change source episode metadata or the sharing integration anchors in index.html. For local previews, run phone_video.py --output _site after presentation.py and before serving _site.
