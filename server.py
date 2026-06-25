import os
import subprocess
from flask import Flask, request, jsonify, send_from_directory

# Allow overriding yt-dlp path for local dev
YTDLP = os.environ.get('YTDLP_BIN', 'yt-dlp')

app = Flask(__name__)


@app.route('/')
@app.route('/<path:filename>')
def static_files(filename='play.html'):
    return send_from_directory('.', filename)


@app.route('/audio')
def audio():
    yt_id = request.args.get('ytId', '').strip()
    if not yt_id or not yt_id.replace('-', '').replace('_', '').isalnum():
        return jsonify({'error': 'invalid ytId'}), 400

    result = subprocess.run(
        [YTDLP, '-f', 'bestaudio[ext=m4a]/bestaudio', '--get-url', f'https://youtube.com/watch?v={yt_id}'],
        capture_output=True, text=True, timeout=15
    )
    url = result.stdout.strip().split('\n')[0]
    if not url:
        return jsonify({'error': result.stderr.strip()}), 500

    return jsonify({'url': url})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
