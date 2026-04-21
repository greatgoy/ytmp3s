# YTmp3s

A personal music library toolkit for downloading YouTube playlists as MP3s and automatically enriching them with lyrics, album art, and metadata.

## Features

- **Download** YouTube playlists via yt-dlp with dry-run confirmation
- **Lyrics** — fetches and embeds lyrics from Genius, lrclib.net, AZLyrics, songlyrics.com, and lyrics.ovh
- **Album art** — fetches and embeds art from iTunes, MusicBrainz/Cover Art Archive, Deezer, and Last.fm
- **Metadata enrichment** — embeds year, track #, writers, producers, featured artists, label, samples, covers, remixes, and more via Genius API; falls back to MusicBrainz and iTunes
- **Filename cleaning** — strips YouTube cruft ("Official Video", "Lyrics", etc.) from filenames
- **Deduplication** — removes duplicate MP3s
- **M3U playlist generation** — builds a playlist file with full paths
- **Manual overrides** — add specific lyrics URLs or album art URLs for stubborn songs
- **Interactive menu** — single `ytmp3_ui.sh` entry point for everything

## Prerequisites

- macOS (paths are hardcoded to `~/Downloads/YTmp3s` — adjust as needed)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/)
- Python 3.9+

## Setup

**1. Clone the repo into `~/Downloads/YTmp3s`:**
```bash
git clone https://github.com/YOUR_USERNAME/ytmp3s ~/Downloads/YTmp3s
cd ~/Downloads/YTmp3s
```

**2. Create the Python virtual environment and install dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install yt-dlp mutagen eyed3 requests beautifulsoup4 lxml cloudscraper curl_cffi
```

**3. Set up API keys:**
```bash
cp .env.example .env
# Edit .env and fill in your keys
```

- **Genius API token** — free at [genius.com/api-clients](https://genius.com/api-clients) (create a client, use the Client Access Token)
- **Last.fm API key** — free at [last.fm/api/account/create](https://www.last.fm/api/account/create)

**4. Create the `All Songs` folder:**
```bash
mkdir -p "All Songs"
```

**5. Make scripts executable:**
```bash
chmod +x ytmp3_ui.sh scripts/ytmp3.sh
```

**6. Launch:**
```bash
./ytmp3_ui.sh
```

## Menu Options

| Option | Description |
|--------|-------------|
| `1` | Download a YouTube playlist |
| `2` | Audit metadata (writes log) |
| `3` | Deduplicate songs |
| `4` | Generate M3U playlist |
| `5` | Export metadata CSV |
| `6` | **Full pipeline** — clean filenames → lyrics → art → metadata |
| `7` | Clean filenames only |
| `8` | Fetch lyrics only |
| `9` | Fetch album art only |
| `f` | Show songs missing lyrics |
| `g` | Show songs missing album art |
| `p` | Show songs missing metadata (year, writers, track #, producers) |
| `a` | Add lyric source override |
| `m` | Manually paste and embed lyrics |
| `i` | Add album art override URL |
| `n` | Enrich metadata from Genius (standalone, with MusicBrainz/iTunes fallbacks) |
| `r` | Retry Genius rate-limited songs |
| `b` | Remove all embedded lyrics |
| `c` | Clean + repair specific songs by filename keyword |
| `d` | Test sync/restore on a single file |

## Lyrics source priority

Genius → lrclib.net → AZLyrics → songlyrics.com → lyrics.ovh

## Metadata source priority

Genius (richest) → MusicBrainz → iTunes

## Album art source priority

iTunes → MusicBrainz/Cover Art Archive → Deezer → Last.fm

## Notes

- MP3s are stored in `All Songs/` (gitignored — not part of the repo)
- API keys go in `.env` (gitignored — never committed)
- Lyric and art overrides are stored in `scripts/lyrics/lyrics_overrides.json` and `scripts/art/art_overrides.json`
- Genius page scraping uses `curl_cffi` for Cloudflare bypass if installed
