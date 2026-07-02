#!/usr/bin/env python3
"""Fetch all tracks for a Spotify artist and merge into songs-db.json."""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import uuid
import requests
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_PATH = Path(__file__).parent.parent / 'songs-db.json'
REDIRECT_URI = 'https://localhost'


# ---------------------------------------------------------------------------
# OAuth PKCE (needed for popularity/top-tracks data — Spotify restricts these
# to user-authorized tokens, client-credentials tokens get 403)
# ---------------------------------------------------------------------------

def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return verifier, challenge


def get_user_token(client_id):
    verifier, challenge = _pkce_pair()
    state = secrets.token_hex(8)

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'state': state,
        'code_challenge_method': 'S256',
        'code_challenge': challenge,
    }
    url = 'https://accounts.spotify.com/authorize?' + urlencode(params)
    print(f'\nOpen this URL in your browser to log in:\n\n  {url}\n')
    print('After login, Spotify redirects to play.html — copy the full URL')
    print('from the address bar and paste it here.')
    redirect_url = input('\nPaste redirect URL: ').strip()

    qs = parse_qs(urlparse(redirect_url).query)
    if qs.get('state', [None])[0] != state:
        print('State mismatch — possible CSRF. Aborting.')
        sys.exit(1)
    if 'code' not in qs:
        print('No code found in redirect URL.')
        sys.exit(1)

    res = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'authorization_code',
        'code': qs['code'][0],
        'redirect_uri': REDIRECT_URI,
        'client_id': client_id,
        'code_verifier': verifier,
    }, timeout=10)
    res.raise_for_status()
    return res.json()['access_token']


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
    params = {'include_groups': 'album,single', 'limit': 10}
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
        year_str = album.get('release_date', '')[:4]
        year = int(year_str) if year_str.isdigit() else 0
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


def fetch_popularity(token, tracks):
    """Annotate tracks in-place with a 'popularity' field (0-100).

    Uses the single-track endpoint one at a time — Spotify's batch
    'Get Several Tracks' endpoint (GET /v1/tracks?ids=...) returns 403 for
    Development Mode apps as of their Nov 2024 API access changes.
    """
    for t in tracks:
        res = requests.get(
            f'https://api.spotify.com/v1/tracks/{t["serviceId"]}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )
        res.raise_for_status()
        t['popularity'] = res.json()['popularity']


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
    parser = argparse.ArgumentParser(description='Fetch tracks for a Spotify artist and merge into songs-db.json')
    parser.add_argument('query', help='Artist name, Spotify artist URL, or URI')
    parser.add_argument('--top', type=int, metavar='N',
                         help='Only keep the N most popular tracks (by Spotify popularity score)')
    args = parser.parse_args()

    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        print('Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env')
        sys.exit(1)

    token = get_token(client_id, client_secret)
    artist_id = resolve_artist_id(token, args.query)
    tracks = fetch_all_tracks(token, artist_id)

    if args.top:
        user_token = get_user_token(client_id)
        fetch_popularity(user_token, tracks)
        tracks.sort(key=lambda t: t['popularity'], reverse=True)
        tracks = tracks[:args.top]

    added, skipped = merge_into_db(tracks)
    print(f'Done. Added {added} new tracks, skipped {skipped} duplicates.')
    print(f'Database: {DB_PATH}')


if __name__ == '__main__':
    main()
