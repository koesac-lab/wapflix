# Fictional catalogue samples

These are invented 24-second ASCII art clips, not real footage, dialogue, episode titles, summaries or claims about released seasons. No affiliation with the referenced programmes is implied.

Three invented samples are provided for each requested collection:

- Love Is Blind season 11 — Boston [search](https://overseerr.alexkoester.com/search?query=Love%20Is%20Blind): A Connection Without Bars; The Longest Pause; Commitment Pending.
- The Haunted Hotel season 1 [search](https://overseerr.alexkoester.com/search?query=The%20Haunted%20Hotel): Do Not Disturb the Dead; Room Service from Beyond; Late Checkout.
- The Haunted Hotel season 2 [search](https://overseerr.alexkoester.com/search?query=The%20Haunted%20Hotel): Under New Possession; The Lift to Nowhere; Five Stars, No Survivors.

Generate locally after the original demos:

```sh
python3 tools/build.py
python3 tools/fiction.py
python3 -m http.server 8000
```

The Pages workflow runs both generators automatically. All nine new samples have low, medium and high variants, invented subtitles, and a fictional-sample notice on every frame. Running the generator again replaces its own catalogue entries without duplicating them or deleting unrelated clips. The initial implementation uses individual episode cards, not a series/season navigation screen.
