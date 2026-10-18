#!/usr/bin/env python3
"""Use verified episode metadata with explicitly fictional ASCII demo playback."""
import json
from pathlib import Path
import fiction


def main():
    metadata = json.loads(Path(__file__).with_name('episodes.json').read_text())
    old_dialogue = {(theme, season): [dialogue for _, dialogue in episodes]
                    for theme, _, season, _, episodes in fiction.SERIES}
    rows = {}
    collections = []
    for collection in metadata['collections']:
        theme, season = collection['theme'], collection['season']
        episodes = []
        for episode in collection['episodes']:
            number = episode['episode']
            ident = f'fiction-{theme}-s{season:02}e{number:02}'
            if ident in rows:
                raise ValueError(f'Duplicate episode identifier: {ident}')
            rows[ident] = (collection, episode)
            dialogue = old_dialogue[(theme, season)]
            episodes.append((episode['title'], dialogue[(number-1) % len(dialogue)]))
        collections.append((theme, collection['series'], season, collection['location'], episodes))
    fiction.SERIES = collections
    fiction.main()
    parser = fiction.argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('assets'))
    args = parser.parse_args()
    path = args.output / 'catalogue.json'
    catalogue = json.loads(path.read_text())
    for item in catalogue:
        if item['id'] not in rows:
            continue
        collection, episode = rows[item['id']]
        item.update(description=episode['description'] + ' ASCII demo, not episode footage.',
                    label=f"REAL LISTING / ASCII DEMO / S{collection['season']:02}E{episode['episode']:02}",
                    episode_title=episode['title'],
                    metadata_source=collection['source'], metadata_as_of=metadata['as_of'],
                    metadata_is_fictional=False, description_style=metadata['description_style'],
                    footage_is_fictional=True, fictional=True, overseerr=collection['overseerr'])
        for field in ('title_alternatives', 'title_note', 'alternative_source'):
            if field in episode:
                item[field] = episode[field]
    path.write_text(json.dumps(catalogue, indent=2))
    print(f'Applied sourced episode metadata to {len(rows)} ASCII demos.')


if __name__ == '__main__':
    main()
