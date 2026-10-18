# Sourced catalogue metadata / fictional ASCII playback

Episode titles are sourced; descriptions are concise source-based paraphrases, not verbatim platform copy. The 24-second animations and subtitle dialogue remain invented art samples, not reconstructions of the episodes. No affiliation is implied.

Metadata checked 18 October 2026:

- Love Is Blind season 11 — Boston [search](https://overseerr.alexkoester.com/search?query=Love%20Is%20Blind): verified listings for episodes 1–5 only. Source: https://www.rottentomatoes.com/tv/love_is_blind/s11 . Later episodes are not assigned invented titles or descriptions.
- Haunted Hotel season 1 [search](https://overseerr.alexkoester.com/search?query=Haunted%20Hotel): 10 episodes. Source: https://www.netflix.com/title/81674500 .
- Haunted Hotel season 2 [search](https://overseerr.alexkoester.com/search?query=Haunted%20Hotel): 8 episodes. Source: https://www.rottentomatoes.com/tv/haunted_hotel/s02 . Episode 5 uses that source's title, Astral Esther. IMDb, Metacritic and JustWatch instead list Astral Ether; this uncertainty is recorded in the metadata, not silently treated as settled.

The metadata file is tools/episodes.json. Edit it to add later verified listings; there is no automatic metadata synchronisation. The handset's 1 / INFO key displays the selected episode description.

Generate the published catalogue locally with:

```sh
python3 tools/build.py
python3 tools/catalogue.py
python3 -m http.server 8000
```

Use catalogue.py, not fiction.py directly, for the sourced catalogue. The latter is retained as the underlying original scene generator. The Pages workflow runs the sourced version automatically. Existing fictional clip IDs remain stable for the original nine entries; additional verified entries receive the same three quality variants. New entries reuse the demo scene templates and invented dialogue; they are not episode adaptations. Catalogue entries distinguish sourced metadata from fictional playback, and retain source URLs and the metadata snapshot date.
