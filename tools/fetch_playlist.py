#!/usr/bin/env python3
"""Fetch tracks from a Spotify playlist and merge into songs-db.json.

Uses the no-API scraper (BeautifulSoup) since the Spotify Client Credentials
flow returns 403 for playlist track endpoints.
"""

import json
import re
import sys
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / 'songs-db.json'
HCG_SRC = REPO_ROOT / 'hitster-card-generator' / 'src'
sys.path.insert(0, str(HCG_SRC))

import utils as hcg_utils


def merge_into_db(songs, service='spotify'):
    db = json.loads(DB_PATH.read_text()) if DB_PATH.exists() else []
    existing_ids = {e['serviceId'] for e in db if e.get('service') == service}
    added = 0
    for s in songs:
        track_id = s['link'].rstrip('/').split('/')[-1]
        if track_id in existing_ids:
            continue
        db.append({
            'id': str(uuid.uuid4())[:8],
            'title': s['name'],
            'artist': s['artist'],
            'year': s['year'] or 0,
            'service': service,
            'serviceId': track_id,
        })
        existing_ids.add(track_id)
        added += 1
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    return added


def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/fetch_playlist.py <spotify-playlist-url>')
        sys.exit(1)

    playlist_url = sys.argv[1]

    print(f'Scraping playlist page for track links...')
    links = hcg_utils.scrape_playlist_track_links(playlist_url)
    if not links:
        print('No track links found. The playlist may be private or Spotify changed its HTML.')
        sys.exit(1)
    print(f'Found {len(links)} track links. Scraping metadata...')

    songs = hcg_utils.fetch_no_api_data_from_list(links)
    if not songs:
        print('No track metadata retrieved.')
        sys.exit(1)

    added = merge_into_db(songs)
    print(f'\nAdded {added} new tracks ({len(songs) - added} already in DB).')


if __name__ == '__main__':
    main()
