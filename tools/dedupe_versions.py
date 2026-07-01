#!/usr/bin/env python3
"""Collapse same-song duplicates (re-releases, acoustic/version-suffix variants,
punctuation/case differences) in songs-db.json down to one entry per song.

Within each duplicate group, keeps the entry with the earliest (original)
year, treating an unknown year (0) as worse than any known year. If the
winner's title carries an 'Акустика'/'Version YYYY' suffix, that suffix is
stripped so the kept title stays clean.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'songs-db.json'

VARIANT_SUFFIX_RE = re.compile(r'\s*-\s*(акустика|version\s*\d{4})\s*$', re.I)
PUNCT_RE = re.compile(r'[!,.]')


def normalize(title):
    t = VARIANT_SUFFIX_RE.sub('', title.lower())
    t = PUNCT_RE.sub('', t)
    return re.sub(r'\s+', ' ', t).strip()


def is_variant(entry):
    return bool(VARIANT_SUFFIX_RE.search(entry['title']))


def dedupe(db, artist=None):
    groups = defaultdict(list)
    for e in db:
        if artist and e.get('artist') != artist:
            continue
        groups[(e.get('artist'), normalize(e['title']))].append(e)

    removed = []
    for entries in groups.values():
        if len(entries) == 1:
            continue
        ranked = sorted(entries, key=lambda e: (e['year'] or float('inf'), is_variant(e), len(e['title'])))
        winner = ranked[0]
        if is_variant(winner):
            winner['title'] = VARIANT_SUFFIX_RE.sub('', winner['title']).strip()
        removed.extend(ranked[1:])

    removed_ids = {id(e) for e in removed}
    kept = [e for e in db if id(e) not in removed_ids]
    return kept, removed


def main():
    parser = argparse.ArgumentParser(description='Collapse duplicate song versions in songs-db.json')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be removed without modifying the file')
    parser.add_argument('--artist', help='Only dedupe entries for this artist (default: whole database)')
    args = parser.parse_args()

    db = json.loads(DB_PATH.read_text())
    kept, removed = dedupe(db, artist=args.artist)

    for e in removed:
        print(f'  [dup] {e["artist"]} — {e["title"]} ({e["year"]})')

    if args.dry_run:
        print(f'\nDry run — no changes written. Would remove {len(removed)} entries, keep {len(kept)}.')
        return

    DB_PATH.write_text(json.dumps(kept, indent=2, ensure_ascii=False))
    print(f'\nDone. Removed {len(removed)} entries, {len(kept)} remaining.')


if __name__ == '__main__':
    main()
