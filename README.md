# My Music Game

Hitster-style card game built from a local song database. Cards have Spotify QR codes on the front and year-based colour-coded backs.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
```

## Generating Cards

### 1 — Populate the database

Fetch all tracks for an artist and merge into `songs-db.json`:

```bash
python tools/fetch_artist.py "Taylor Swift"
# or by Spotify URL:
python tools/fetch_artist.py https://open.spotify.com/artist/06HL4z0CvFAxyc27GXpf02
```

Requires `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`.

### 2 — Generate the PDF

```bash
python tools/generate_cards.py
# Filter to one artist:
python tools/generate_cards.py --artist "Taylor Swift"
# Custom output directory:
python tools/generate_cards.py --output my_deck
```

Output lands in `hitster-card-generator/output/<name>/`:

| File | Contents |
|---|---|
| `card_NNN_qr.png` | QR-side images |
| `card_NNN_solution.png` | Solution-side images |
| `songs.json` | Song metadata (editable) |
| `../<name>.pdf` | Print-ready A4 PDF |

### 3 — Print

Print double-sided, flip on long edge. Each card is **5 × 5 cm**. Use "Actual size" (not "Fit to page") so QR codes scan reliably.

## Fix Wrong Years

Edit `hitster-card-generator/output/<name>/songs.json`, then re-run `generate_cards.py` (it skips the fetch step when `songs.json` already exists).
