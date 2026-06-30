#!/usr/bin/env python3
"""Fetch tracks from a Spotify playlist and merge into songs-db.json.

Uses OAuth Authorization Code flow (opens browser) to authenticate as the user,
which allows reading private/saved playlists. Falls back to no-API scraping
if credentials are unavailable.
"""

import base64
import hashlib
import json
import os
import re
import secrets
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / 'songs-db.json'
HCG_SRC = REPO_ROOT / 'hitster-card-generator' / 'src'
sys.path.insert(0, str(HCG_SRC))

REDIRECT_URI = 'https://localhost'
SCOPES = 'playlist-read-private playlist-read-collaborative'


# ---------------------------------------------------------------------------
# OAuth PKCE helpers
# ---------------------------------------------------------------------------

def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return verifier, challenge


def _get_user_token(client_id):
    verifier, challenge = _pkce_pair()
    state = secrets.token_hex(8)

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
        'state': state,
        'code_challenge_method': 'S256',
        'code_challenge': challenge,
    }
    url = 'https://accounts.spotify.com/authorize?' + urlencode(params)
    print(f'\nOpen this URL in your browser to log in:\n\n  {url}\n')
    print(f'After login, Spotify redirects to play.html — copy the full URL')
    print(f'from the address bar and paste it here.')
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


# ---------------------------------------------------------------------------
# Playlist fetch
# ---------------------------------------------------------------------------

def fetch_playlist_tracks_api(token, playlist_id):
    tracks = []
    url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
    params = {'limit': 100}
    while url:
        res = requests.get(url, headers={'Authorization': f'Bearer {token}'},
                           params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        for item in data.get('items', []):
            t = item.get('track')
            if not t or not t.get('id'):
                continue
            year_str = t['album'].get('release_date', '')[:4]
            tracks.append({
                'id': t['id'],
                'name': t['name'],
                'artist': ', '.join(a['name'] for a in t['artists']),
                'year': int(year_str) if year_str.isdigit() else 0,
            })
        url = data.get('next')
        params = {}
    return tracks


def merge_into_db(tracks, service='spotify'):
    db = json.loads(DB_PATH.read_text()) if DB_PATH.exists() else []
    existing_ids = {e['serviceId'] for e in db if e.get('service') == service}
    added = 0
    for t in tracks:
        sid = t.get('id') or t.get('link', '').rstrip('/').split('/')[-1]
        if sid in existing_ids:
            continue
        db.append({
            'id': str(uuid.uuid4())[:8],
            'title': t.get('name', ''),
            'artist': t.get('artist', ''),
            'year': t.get('year') or 0,
            'service': service,
            'serviceId': sid,
        })
        existing_ids.add(sid)
        added += 1
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    return added


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/fetch_playlist.py <spotify-playlist-url>')
        sys.exit(1)

    playlist_url = sys.argv[1]
    m = re.search(r'playlist/([A-Za-z0-9]+)', playlist_url)
    playlist_id = m.group(1) if m else playlist_url

    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    if not client_id:
        print('SPOTIFY_CLIENT_ID not set in .env')
        sys.exit(1)

    token = _get_user_token(client_id)

    print(f'\nFetching playlist tracks...')
    tracks = fetch_playlist_tracks_api(token, playlist_id)
    print(f'Found {len(tracks)} tracks.')

    added = merge_into_db(tracks)
    print(f'Added {added} new tracks ({len(tracks) - added} already in DB).')


if __name__ == '__main__':
    main()
