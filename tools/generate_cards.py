#!/usr/bin/env python3
"""Generate printable cards from songs-db.json using hitster-card-generator."""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / 'songs-db.json'
CARD_GEN_SRC = REPO_ROOT / 'hitster-card-generator' / 'src'
CARD_GEN_OUTPUT = REPO_ROOT / 'hitster-card-generator' / 'output'

# Add hitster-card-generator/src to path so its imports work
sys.path.insert(0, str(CARD_GEN_SRC))
import hitster_card_creator
import utils as hcg_utils


def build_db_config():
    font_dir = REPO_ROOT / 'hitster-card-generator' / 'fonts'
    db = {
        'fonts_dict': {
            'year': str(font_dir / 'Montserrat-Bold.ttf'),
            'artist': str(font_dir / 'Montserrat-SemiBold.ttf'),
            'song': str(font_dir / 'Montserrat-MediumItalic.ttf'),
        },
        'color_gradient': hitster_card_creator.COLOR_GRADIENT,
        'card_size': hitster_card_creator.CARD_SIZE,
        'neon_colors': hitster_card_creator.NEON_COLORS,
        'ink_saving_mode': False,
        'card_draw_border': False,
        'card_background_color': 'black',
        'card_border_color': 'white',
        'card_label': None,
        'qr_background_mode': 'solid',
        'qr_background_color': '#FFFFFF',
        'qr_module_color': '#000000',
        'qr_size_ratio': 0.45,
        'qr_bg_type': 'neon_rings',
        'qr_title': '',
        'qr_title_pos': 'top',
        'qr_title_enabled': False,
    }
    hcg_utils.db = db
    return db


def load_songs(artist_filter=None, title_include=None, title_exclude=None):
    import re
    db = json.loads(DB_PATH.read_text())
    songs = [e for e in db if e.get('service') == 'spotify']
    if artist_filter:
        songs = [s for s in songs if artist_filter.lower() in s['artist'].lower()]
    if title_include:
        songs = [s for s in songs if re.search(title_include, s['title'], re.IGNORECASE)]
    if title_exclude:
        songs = [s for s in songs if not re.search(title_exclude, s['title'], re.IGNORECASE)]
    return songs


def to_hitster_format(songs):
    return [
        {
            'name': s['title'],
            'artist': s['artist'],
            'year': s['year'],
            'link': f"https://open.spotify.com/track/{s['serviceId']}",
        }
        for s in songs
    ]


def write_songs_json(hitster_songs, output_dir):
    """Write the songs.json that hitster_card_creator reads when not re-fetching."""
    songs_json_path = CARD_GEN_OUTPUT / output_dir / 'songs.json'
    songs_json_path.parent.mkdir(parents=True, exist_ok=True)
    songs_json_path.write_text(json.dumps(hitster_songs, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description='Generate Hitster cards from songs-db.json')
    parser.add_argument('--artist', default=None, help='Filter by artist name (substring)')
    parser.add_argument('--output', default='hitster_cards', help='Output directory name')
    parser.add_argument('--title-include', default=None, metavar='REGEX',
                        help='Only include songs whose title matches this regex')
    parser.add_argument('--title-exclude', default=None, metavar='REGEX',
                        help='Exclude songs whose title matches this regex')
    args = parser.parse_args()

    songs = load_songs(artist_filter=args.artist, title_include=args.title_include,
                       title_exclude=args.title_exclude)
    if not songs:
        print('No matching songs found in songs-db.json')
        sys.exit(1)

    print(f'Generating cards for {len(songs)} songs...')
    hitster_songs = to_hitster_format(songs)

    # Write songs.json so hitster_card_creator loads from it (fetch=False path)
    write_songs_json(hitster_songs, args.output)

    db = build_db_config()
    # Override OUTPUT_DIR to point inside our submodule
    hitster_card_creator.OUTPUT_DIR = str(CARD_GEN_OUTPUT)

    hitster_card_creator.generate_hitster_cards(
        db,
        output_dir=args.output,
        fetch=False,
    )


if __name__ == '__main__':
    main()
