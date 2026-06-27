#!/usr/bin/env python3
"""Remove alternate versions and live recordings from songs-db.json."""

import argparse
import json
import re
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'songs-db.json'

# Title ends with 'version', but NOT Taylor's Version (handles Unicode apostrophe)
VERSION_RE = re.compile(r'\bversion\b\s*\)?\s*$', re.I)
TAYLORS_RE = re.compile(r'taylor.s version', re.I)

# Live recordings: ' - Live', '(Live...', 'Live/YYYY'
LIVE_RE = re.compile(r'\s-\s[Ll]ive\b|\([Ll]ive\b|\b[Ll]ive/\d{4}', re.I)


def should_remove(entry):
    title = entry.get('title', '')
    if VERSION_RE.search(title) and not TAYLORS_RE.search(title):
        return 'version'
    if LIVE_RE.search(title):
        return 'live'
    return None


def main():
    parser = argparse.ArgumentParser(description='Clean alternate versions and live tracks from songs-db.json')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be removed without modifying the file')
    args = parser.parse_args()

    db = json.loads(DB_PATH.read_text())
    keep, removed = [], []
    for entry in db:
        reason = should_remove(entry)
        if reason:
            removed.append((reason, entry))
        else:
            keep.append(entry)

    print(f'Removing {len(removed)} entries ({len(db)} → {len(keep)}):')
    for reason, e in removed:
        print(f'  [{reason}] {e["artist"]} — {e["title"]}')

    if args.dry_run:
        print('\nDry run — no changes written.')
        return

    DB_PATH.write_text(json.dumps(keep, indent=2, ensure_ascii=False))
    print(f'\nDone. {len(keep)} entries remaining.')


if __name__ == '__main__':
    main()
