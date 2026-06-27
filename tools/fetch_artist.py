#!/usr/bin/env python3
"""Fetch all tracks for a Spotify artist and merge into songs-db.json."""

import json
import os
import sys
import uuid
import re
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_PATH = Path(__file__).parent.parent / 'songs-db.json'


def get_token(client_id, client_secret):
    res = requests.post(
        'https://accounts.spotify.com/api/token',
        data={'grant_type': 'client_credentials'},
        auth=(client_id, client_secret),
        timeout=10,
    )
    res.raise_for_status()
    return res.json()['access_token']


def resolve_artist_id(token, query):
    """Accept Spotify artist URL/URI or a plain name."""
    m = re.search(r'spotify\.com/artist/([A-Za-z0-9]+)', query)
    if m:
        return m.group(1)
    m = re.search(r'spotify:artist:([A-Za-z0-9]+)', query)
    if m:
        return m.group(1)
    # Search by name
    res = requests.get(
        'https://api.spotify.com/v1/search',
        headers={'Authorization': f'Bearer {token}'},
        params={'q': query, 'type': 'artist', 'limit': 1},
        timeout=10,
    )
    res.raise_for_status()
    items = res.json()['artists']['items']
    if not items:
        raise ValueError(f'Artist not found: {query}')
    artist = items[0]
    print(f'Found artist: {artist["name"]} ({artist["id"]})')
    return artist['id']


def fetch_all_tracks(token, artist_id):
    """Return list of {title, artist, year, serviceId}."""
    tracks = []
    seen_ids = set()

    # Fetch albums
    albums = []
    url = f'https://api.spotify.com/v1/artists/{artist_id}/albums'
    params = {'include_groups': 'album,single', 'limit': 50, 'market': 'US'}
    while url:
        res = requests.get(url, headers={'Authorization': f'Bearer {token}'}, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        albums.extend(data['items'])
        url = data.get('next')
        params = {}  # next URL already has params

    print(f'Found {len(albums)} albums/singles')

    # Fetch tracks from each album
    for album in albums:
        year = int(album['release_date'][:4])
        url = f'https://api.spotify.com/v1/albums/{album["id"]}/tracks'
        params = {'limit': 50}
        while url:
            res = requests.get(url, headers={'Authorization': f'Bearer {token}'}, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            for t in data['items']:
                if t['id'] in seen_ids:
                    continue
                seen_ids.add(t['id'])
                tracks.append({
                    'title': t['name'],
                    'artist': ', '.join(a['name'] for a in t['artists']),
                    'year': year,
                    'serviceId': t['id'],
                })
            url = data.get('next')
            params = {}

    return tracks


def merge_into_db(new_tracks, service='spotify'):
    db = json.loads(DB_PATH.read_text()) if DB_PATH.exists() else []
    existing_ids = {e['serviceId'] for e in db if e.get('service') == service}

    added = 0
    for t in new_tracks:
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
    return added, len(new_tracks) - added


def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/fetch_artist.py "Artist Name"')
        print('       python tools/fetch_artist.py https://open.spotify.com/artist/ID')
        sys.exit(1)

    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        print('Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env')
        sys.exit(1)

    query = sys.argv[1]
    token = get_token(client_id, client_secret)
    artist_id = resolve_artist_id(token, query)
    tracks = fetch_all_tracks(token, artist_id)
    added, skipped = merge_into_db(tracks)
    print(f'Done. Added {added} new tracks, skipped {skipped} duplicates.')
    print(f'Database: {DB_PATH}')


if __name__ == '__main__':
    main()
