import os
import subprocess

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import threading
import time
from flask import Flask, request, jsonify, send_from_directory

YTDLP = os.environ.get('YTDLP_BIN', 'yt-dlp')
CACHE_TTL = 5 * 3600

app = Flask(__name__)
_cache = {}
_cache_lock = threading.Lock()


def resolve_url(yt_id):
    with _cache_lock:
        entry = _cache.get(yt_id)
    if entry and time.time() - entry[1] < CACHE_TTL:
        return entry[0], None

    result = subprocess.run(
        [YTDLP, '-f', 'bestaudio[ext=m4a]/bestaudio', '--get-url', f'https://youtube.com/watch?v={yt_id}'],
        capture_output=True, text=True, timeout=15
    )
    url = result.stdout.strip().split('\n')[0]
    if not url:
        return None, result.stderr.strip()

    with _cache_lock:
        _cache[yt_id] = (url, time.time())
    return url, None


@app.route('/ping')
def ping():
    return '', 204


@app.route('/config')
def config():
    client_id = os.environ.get('SPOTIFY_CLIENT_ID', '')
    return jsonify({'spotifyClientId': client_id})


@app.route('/')
@app.route('/<path:filename>')
def static_files(filename='play.html'):
    return send_from_directory('.', filename)


@app.route('/audio')
def audio():
    yt_id = request.args.get('ytId', '').strip()
    if not yt_id or not yt_id.replace('-', '').replace('_', '').isalnum():
        return jsonify({'error': 'invalid ytId'}), 400

    url, err = resolve_url(yt_id)
    if err:
        return jsonify({'error': err}), 500

    return jsonify({'url': url})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
