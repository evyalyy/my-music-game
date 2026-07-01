#!/usr/bin/env python3
"""Fetch tracks listed in a CSV (Artist,Title,Year columns) from Spotify and
merge into songs-db.json. Flags entries whose title and/or artist look German.
"""

import argparse
import csv
import json
import os
import re
import uuid
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_PATH = Path(__file__).parent.parent / 'songs-db.json'

UMLAUT_RE = re.compile(r'[äöüßÄÖÜ]')
GERMAN_WORDS_RE = re.compile(
    r'\b(der|die|das|und|ist|nicht|mit|wie|für|auf|ich|du|wir|kein|keine|eine|ein|'
    r'noch|schon|wenn|kann|kommt|kommst|geht|kommen|über|immer|liebe|leben|welt|'
    r'nach|von|zum|zur|sind|hat|haben|wird|werden|mal|mehr|alles|nie)\b',
    re.I,
)


def looks_german(text):
    return bool(UMLAUT_RE.search(text) or GERMAN_WORDS_RE.search(text))


def get_token(client_id, client_secret):
    res = requests.post(
        'https://accounts.spotify.com/api/token',
        data={'grant_type': 'client_credentials'},
        auth=(client_id, client_secret),
        timeout=10,
    )
    res.raise_for_status()
    return res.json()['access_token']


def search_track(token, title, artist):
    for query in (f'track:{title} artist:{artist}', f'{title} {artist}'):
        res = requests.get(
            'https://api.spotify.com/v1/search',
            headers={'Authorization': f'Bearer {token}'},
            params={'q': query, 'type': 'track', 'limit': 1},
            timeout=10,
        )
        res.raise_for_status()
        items = res.json()['tracks']['items']
        if items:
            return items[0]
    return None


def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [
            {'artist': row['Artist'].strip(), 'title': row['Title'].strip(), 'year': int(row['Year'])}
            for row in reader if row.get('Artist') and row.get('Title')
        ]


def merge_into_db(tracks, service='spotify'):
    db = json.loads(DB_PATH.read_text()) if DB_PATH.exists() else []
    existing_ids = {e['serviceId'] for e in db if e.get('service') == service}

    added = 0
    for t in tracks:
        if t['serviceId'] in existing_ids:
            continue
        db.append({
            'id': str(uuid.uuid4())[:8],
            'title': t['title'],
            'artist': t['artist'],
            'year': t['year'],
            'service': service,
            'serviceId': t['serviceId'],
        })
        existing_ids.add(t['serviceId'])
        added += 1

    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    return added, len(tracks) - added


def main():
    parser = argparse.ArgumentParser(description='Fetch tracks from a CSV into songs-db.json')
    parser.add_argument('csv_path', help='Path to CSV with Artist,Title,Year columns')
    args = parser.parse_args()

    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        print('Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env')
        raise SystemExit(1)

    token = get_token(client_id, client_secret)
    rows = read_csv_rows(args.csv_path)
    print(f'Read {len(rows)} rows from {args.csv_path}')

    tracks = []
    german_flagged = []
    not_found = []
    for row in rows:
        match = search_track(token, row['title'], row['artist'])
        if not match:
            not_found.append(row)
            continue
        tracks.append({
            'title': match['name'],
            'artist': ', '.join(a['name'] for a in match['artists']),
            'year': row['year'],
            'serviceId': match['id'],
        })
        if looks_german(row['title']) or looks_german(row['artist']):
            german_flagged.append(row)

    added, skipped = merge_into_db(tracks)
    print(f'Done. Added {added} new tracks, skipped {skipped} duplicates.')
    if not_found:
        print(f'\nNo Spotify match found for {len(not_found)} rows:')
        for row in not_found:
            print(f'  {row["artist"]} — {row["title"]} ({row["year"]})')

    print(f'\nFlagged as German (title/artist) — {len(german_flagged)} rows:')
    for row in german_flagged:
        print(f'  {row["artist"]} — {row["title"]} ({row["year"]})')


if __name__ == '__main__':
    main()
