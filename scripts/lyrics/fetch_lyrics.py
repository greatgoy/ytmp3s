#!/usr/bin/env python3
import os
import sys
import re
import json
import eyed3
import requests
from bs4 import BeautifulSoup, Comment
from datetime import datetime

eyed3.log.setLevel("ERROR")

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lyrics_overrides.json')
GENIUS_RETRY_QUEUE_PATH = os.path.join(BASE_DIR, "genius_retry_queue.json")

# Load .env from project root
_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

_run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
_MISSING_LOG = os.path.join(LOGS_DIR, f"missing_lyrics_{_run_ts}.txt")

# Flips to True the moment Genius returns 429 — resets each new run
_genius_rate_limited = False

# Set via --force: re-fetch lyrics even if already embedded
_force_reembed = False

# --- Overrides & retry queue ---

def load_overrides():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("genius_url", {})
            data.setdefault("azlyrics", {})
            return data
    return {"songlyrics": {}, "ovh": {}, "genius_url": {}, "azlyrics": {}}

def load_retry_queue():
    if os.path.exists(GENIUS_RETRY_QUEUE_PATH):
        with open(GENIUS_RETRY_QUEUE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return []

def save_to_retry_queue(artist, title, file_path):
    queue = load_retry_queue()
    entry = {"artist": artist, "title": title, "file": file_path}
    if entry not in queue:
        queue.append(entry)
    with open(GENIUS_RETRY_QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

# --- Helpers ---

def normalize(text):
    return re.sub(r"\s+", " ", text.lower().replace("\u2019", "'").strip())

def _norm_match(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

def _genius_hit_matches(result, artist, title):
    r_artist = _norm_match(result.get("primary_artist", {}).get("name", ""))
    r_title  = _norm_match(result.get("title", ""))
    s_artist = _norm_match(artist)
    s_title  = _norm_match(title)
    stop = {"the", "a", "an"}
    a_words = set(s_artist.split()) - stop
    r_words = set(r_artist.split()) - stop
    artist_ok = bool(a_words & r_words) if a_words else True
    title_ok  = s_title in r_title or r_title in s_title
    if not title_ok and len(s_title) >= 6:
        title_ok = s_title[:6] in r_title
    return artist_ok and title_ok

def normalize_for_key(artist, title):
    a = artist.strip().lower()
    t = re.sub(r"\s+", " ", title.strip().lower().replace("\u2019", "'"))
    return f"{a} - {t}"

# --- Genius API helpers (search + metadata embed) ---

def _genius_search(artist, title):
    """Search Genius API. Returns (song_id, page_url, headers) or None."""
    global _genius_rate_limited
    if _genius_rate_limited:
        return None
    token = os.environ.get("GENIUS_ACCESS_TOKEN", "")
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(
            "https://api.genius.com/search",
            params={"q": f"{artist} {title}"},
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 429:
            _genius_rate_limited = True
            print(f"⚠️  Genius rate limit reached — queuing song for later, falling back to other sources")
            return None
        hits = resp.json().get("response", {}).get("hits", [])
        if not hits:
            print(f"🎭 Genius: no results for '{artist} – {title}'")
            return None
        candidates = [h["result"] for h in hits[:5]]
        matched = next((r for r in candidates if _genius_hit_matches(r, artist, title)), None)
        if not matched:
            print(f"⚠️  No exact Genius match — trying first result anyway")
        result = matched or candidates[0]
        return result["id"], result["url"], headers
    except Exception as e:
        print(f"⚠️ Genius error: {e}")
        return None


def _is_instrumental(mp3_path):
    """Return True if the file is tagged as instrumental."""
    try:
        from mutagen.id3 import ID3 as _MutID3
        return bool(_MutID3(mp3_path).get("TXXX:Instrumental"))
    except Exception:
        return False


def _embed_genius_metadata(mp3_path, song_id, headers):
    """Fetch /songs/{id} from Genius and embed year, track#, writers, producers.
    Also sets TXXX:Instrumental if Genius marks the song as instrumental.
    Returns True if the song is instrumental (so caller can skip lyrics scraping)."""
    try:
        resp = requests.get(
            f"https://api.genius.com/songs/{song_id}",
            params={"text_format": "plain"},
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return False
        song = resp.json().get("response", {}).get("song", {})
        if not song:
            return False
        from mutagen.mp3 import MP3 as _MP3
        from mutagen.id3 import (ID3 as _ID3, TYER as _TYER, TCOM as _TCOM,
                                  TRCK as _TRCK, TXXX as _TXXX, error as _ID3Err)
        mp3 = _MP3(mp3_path, ID3=_ID3)
        try:
            mp3.add_tags()
        except _ID3Err:
            pass
        tags = mp3.tags
        changed = []
        is_instrumental = bool(song.get("instrumental"))
        if is_instrumental and "TXXX:Instrumental" not in tags:
            tags.add(_TXXX(encoding=3, desc="Instrumental", text=["yes"]))
            changed.append("instrumental=yes")
        rel = song.get("release_date_components") or {}
        year = rel.get("year")
        if year and not (tags.get("TYER") or tags.get("TDRC")):
            tags.add(_TYER(encoding=3, text=[str(year)]))
            changed.append(f"year={year}")
        track_num = song.get("track_number")
        if track_num and not tags.get("TRCK"):
            tags.add(_TRCK(encoding=3, text=[str(track_num)]))
            changed.append(f"track={track_num}")
        writers = [w["name"] for w in song.get("writer_artists", [])]
        if writers and not tags.get("TCOM"):
            tags.add(_TCOM(encoding=3, text=[", ".join(writers)]))
            changed.append("writers")
        producers = [p["name"] for p in song.get("producer_artists", [])]
        if producers and not tags.get("TXXX:Producers"):
            tags.add(_TXXX(encoding=3, desc="Producers", text=[", ".join(producers)]))
            changed.append("producers")
        if changed:
            mp3.save()
            label = "🎸 Instrumental + metadata" if is_instrumental else "📋 Metadata"
            print(f"  {label}: {', '.join(changed)}")
        return is_instrumental
    except Exception as e:
        print(f"  ⚠️  Metadata embed error: {e}")
    return False

def strip_remaster_tags(text):
    return re.sub(r"\(([^)]*(remaster|radio edit)[^)]*)\)", "", text, flags=re.IGNORECASE).strip()

def has_lyrics(audio):
    if audio.tag and audio.tag.lyrics:
        for lyric in audio.tag.lyrics:
            if lyric.text:
                return True
    return False

def log_missing(file_name):
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(_MISSING_LOG, "a", encoding="utf-8") as f:
        f.write(file_name + "\n")

def slugify(text):
    text = text.lower().strip()
    text = text.replace("'", "").replace("\u2019", "")
    text = text.replace("(", "").replace(")", "")
    text = text.replace("[", "").replace("]", "")
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"\s+", "-", text)

def map_artist(artist):
    remap = {"r.e.m.": "r-e-m", "kid rock": "rock-kid", "lipps inc.": "lipps-inc"}
    return remap.get(artist.lower(), slugify(artist))

def embed_lyrics(mp3_path, lyrics):
    audio = eyed3.load(mp3_path)
    if audio.tag is None:
        audio.initTag(version=(2, 3, 0))
    audio.tag.frame_set.pop("USLT", None)
    audio.tag.lyrics.set(lyrics, lang=b"eng")
    audio.tag.save(version=(2, 3, 0))
    print(f"{os.path.basename(mp3_path)}: ✅ Lyrics embedded")

# --- Genius page scraper ---

def _make_genius_fetcher():
    # curl_cffi impersonates Chrome's TLS fingerprint — best Cloudflare bypass
    try:
        from curl_cffi import requests as _cffi
        def _fetch(url):
            return _cffi.get(url, impersonate="chrome120", timeout=15)
        return _fetch, "curl_cffi"
    except ImportError:
        pass
    # cloudscraper handles JS challenges but not TLS fingerprinting
    try:
        import cloudscraper as _cs
        _session = _cs.create_scraper()
        def _fetch(url):
            return _session.get(url, timeout=15)
        return _fetch, "cloudscraper"
    except ImportError:
        pass
    # Plain requests — likely blocked by Cloudflare
    _hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    def _fetch(url):
        return requests.get(url, timeout=15, headers=_hdrs)
    return _fetch, "requests"

_genius_page_get, _genius_fetcher = _make_genius_fetcher()

def _scrape_genius_page(url):
    try:
        page = _genius_page_get(url)
        if page.status_code == 403:
            if _genius_fetcher == "curl_cffi":
                print(f"⚠️  Genius 403 — Cloudflare blocked even curl_cffi")
            elif _genius_fetcher == "cloudscraper":
                print(f"⚠️  Genius 403 — cloudscraper can't bypass TLS fingerprint; install curl-cffi: pip install curl-cffi")
            else:
                print(f"⚠️  Genius 403 — install curl-cffi for Cloudflare bypass: pip install curl-cffi")
            return None
        if page.status_code != 200:
            print(f"⚠️  Genius returned HTTP {page.status_code}")
            return None

        soup = BeautifulSoup(page.text, "lxml")

        # Modern format
        containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
        if containers:
            parts = []
            for c in containers:
                for br in c.find_all("br"):
                    br.replace_with("\n")
                parts.append(c.get_text())
            lyrics = "\n".join(parts).strip()
            if lyrics:
                return lyrics

        # Older format: <div class="lyrics">
        old_div = soup.find("div", class_="lyrics")
        if old_div:
            return old_div.get_text(separator="\n").strip() or None

        # React CSS-module class fallback
        css_div = soup.find("div", class_=re.compile(r"Lyrics__Container"))
        if css_div:
            for br in css_div.find_all("br"):
                br.replace_with("\n")
            return css_div.get_text().strip() or None

        print(f"⚠️  Genius page loaded but no lyrics container found: {url}")
        return None
    except Exception as e:
        print(f"⚠️  Genius scrape error: {e}")
        return None

# --- Source 1: Genius API (primary) ---

def fetch_lyrics_from_genius(artist, title, mp3_path=None):
    # Check for a direct Genius URL override (bypasses search + metadata)
    genius_url_overrides = load_overrides().get("genius_url", {})
    override_key = normalize_for_key(artist, title)
    if override_key in genius_url_overrides:
        override_url = genius_url_overrides[override_key]
        print(f"🎯 Using Genius URL override: {override_url}")
        return _scrape_genius_page(override_url)

    found = _genius_search(artist, title)
    if found is None:
        return None
    song_id, url, headers = found
    if mp3_path:
        if _embed_genius_metadata(mp3_path, song_id, headers):
            return "INSTRUMENTAL"
    print(f"🎭 Trying Genius: {url}")
    return _scrape_genius_page(url)

# --- Source 2: songlyrics.com ---

def fetch_lyrics_from_songlyrics(artist, title):
    overrides = load_overrides().get("songlyrics", {})
    full_key = normalize_for_key(artist, title)
    print(f"🧪 songlyrics key: '{full_key}'")

    if full_key in overrides:
        url = overrides[full_key]
        print(f"✅ Using songlyrics override")
    else:
        stripped = strip_remaster_tags(title)
        if stripped.lower() != title.lower():
            fallback_key = normalize_for_key(artist, stripped)
            if fallback_key in overrides:
                url = overrides[fallback_key]
                print(f"✅ Using fallback songlyrics override")
            else:
                url = f"https://www.songlyrics.com/{map_artist(artist)}/{slugify(stripped)}-lyrics/"
        else:
            url = f"https://www.songlyrics.com/{map_artist(artist)}/{slugify(title)}-lyrics/"

    print(f"🌐 Trying songlyrics: {url}")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_div = soup.find("p", id="songLyricsDiv")
        if lyrics_div and "we do not have" not in lyrics_div.text.lower():
            return lyrics_div.get_text(separator="\n").strip()
    except Exception:
        pass
    return None

# --- Source 3: lyrics.ovh ---

def fetch_lyrics_from_lyrics_ovh(artist, title):
    artist_clean = re.split(r",?\s+(?:feat\.?|ft\.?|featuring|with)\s+", artist, flags=re.IGNORECASE)[0].strip()
    title_clean = re.sub(r"\(.*?(feat\.?|with|remaster|edit)[^)]*\)", "", title, flags=re.IGNORECASE).strip()
    print(f"🎵 Trying lyrics.ovh: {artist_clean} – {title_clean}")
    try:
        response = requests.get(
            f"https://api.lyrics.ovh/v1/{artist_clean}/{title_clean}", timeout=10
        )
        if response.status_code == 200 and "lyrics" in response.json():
            return response.json()["lyrics"].strip()
    except Exception:
        pass
    return None

def try_ovh_with_overrides(artist, title):
    overrides = load_overrides().get("ovh", {})
    raw_key = normalize(title)
    clean_key = re.sub(r"\(.*?\)|\[.*?\]", "", raw_key).strip()

    for key in [raw_key, clean_key]:
        if key in overrides:
            oa, ot = overrides[key]
            print(f"🎯 Using OVH override: {oa} – {ot}")
            lyrics = fetch_lyrics_from_lyrics_ovh(oa, ot)
            if lyrics:
                return lyrics

    variants = [
        title, title.lower(), clean_key,
        title.replace("Smokeshow", "Smoke Show"),
        title.replace("smokeshow", "smoke show"),
        title.replace("-", " "),
        title.replace("\u2019", "'"),
    ]
    tried = set()
    for variant in variants:
        v = variant.strip()
        if not v or v.lower() in tried:
            continue
        tried.add(v.lower())
        lyrics = fetch_lyrics_from_lyrics_ovh(artist, v)
        if lyrics:
            return lyrics
    return None

# --- Source 4: lrclib.net (free, no key, aggregated) ---

def fetch_lyrics_from_lrclib(artist, title):
    title_clean = re.sub(r"\(.*?(feat\.?|with|remaster|edit)[^)]*\)", "", title, flags=re.IGNORECASE).strip()
    print(f"🎵 Trying lrclib: {artist} – {title_clean}")
    try:
        resp = requests.get(
            "https://lrclib.net/api/get",
            params={"artist_name": artist, "track_name": title_clean},
            timeout=10,
            headers={"User-Agent": "ytmp3-lyrics/1.0"},
        )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        lyrics = data.get("plainLyrics") or ""
        if not lyrics:
            synced = data.get("syncedLyrics") or ""
            if synced:
                lyrics = re.sub(r"\[\d+:\d+\.\d+\]\s*", "", synced).strip()
        return lyrics if lyrics else None
    except Exception as e:
        print(f"⚠️  lrclib error: {e}")
    return None

# --- Source 5: AZLyrics ---

def fetch_lyrics_from_azlyrics(artist, title):
    overrides = load_overrides().get("azlyrics", {})
    key = normalize_for_key(artist, title)
    if key in overrides:
        url = overrides[key]
        print(f"🎯 Using AZLyrics override: {url}")
    else:
        artist_slug = re.sub(r"[^a-z0-9]", "", artist.lower())
        title_slug  = re.sub(r"[^a-z0-9]", "", strip_remaster_tags(title).lower())
        url = f"https://www.azlyrics.com/lyrics/{artist_slug}/{title_slug}.html"
        print(f"📝 Trying AZLyrics: {url}")
    try:
        resp = _genius_page_get(url)  # uses curl_cffi/cloudscraper/requests
        if resp.status_code == 404:
            print(f"⚠️  AZLyrics: song not in their database")
            return None
        if resp.status_code == 403:
            print(f"⚠️  AZLyrics: blocked (403)")
            return None
        if resp.status_code != 200:
            print(f"⚠️  AZLyrics returned HTTP {resp.status_code}")
            return None
        html = resp.text

        # Bot/captcha detection
        if "verify you are human" in html.lower() or "ddos-guard" in html.lower() or "cf-browser-verification" in html.lower():
            print(f"⚠️  AZLyrics: bot detection page (200 but not real lyrics)")
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Comment-based (legacy — AZLyrics may have removed this)
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            if "Usage of azlyrics.com" in str(comment):
                div = comment.parent
                if div:
                    lyrics = div.get_text(separator="\n").strip()
                    if lyrics:
                        return lyrics

        # Strategy 2: Find the div with the most direct <br> children — that's the lyrics block
        best_div, best_br_count = None, 0
        for div in soup.find_all("div"):
            # Skip divs with classes/ids (nav, footer, sharing buttons, etc.)
            if div.get("class") or div.get("id"):
                continue
            # Skip divs that contain other class-bearing divs (containers)
            if div.find("div", class_=True):
                continue
            br_count = len(div.find_all("br", recursive=False))
            if br_count > best_br_count:
                best_br_count = br_count
                best_div = div
        if best_div and best_br_count >= 4:
            lyrics = best_div.get_text(separator="\n").strip()
            if len(lyrics) > 80:
                return lyrics

        # Strategy 3: Div after .ringtone (older structure)
        ringtone = soup.find("div", class_="ringtone")
        if ringtone:
            next_div = ringtone.find_next_sibling("div")
            if next_div:
                text = next_div.get_text(separator="\n").strip()
                if len(text) > 100:
                    return text

        print(f"⚠️  AZLyrics: page loaded but no lyrics found")
    except Exception as e:
        print(f"⚠️  AZLyrics error: {e}")
    return None

# --- Genius retry queue ---

def retry_genius_queue():
    global _genius_rate_limited
    _genius_rate_limited = False  # Reset so we actually try

    queue = load_retry_queue()
    if not queue:
        print("✅ Genius retry queue is empty — nothing to do.")
        return

    print(f"🎭 Retrying Genius for {len(queue)} queued song(s)...\n")
    remaining = []

    for i, entry in enumerate(queue):
        artist    = entry["artist"]
        title     = entry["title"]
        file_path = entry["file"]

        if not os.path.exists(file_path):
            print(f"⚠️  File not found, dropping from queue: {os.path.basename(file_path)}")
            continue

        print(f"🎵 ({i+1}/{len(queue)}) {artist} – {title}")
        lyrics = fetch_lyrics_from_genius(artist, title, mp3_path=file_path)

        if _genius_rate_limited:
            print(f"⚠️  Still rate-limited. Stopping — try again later.")
            remaining.append(entry)
            remaining.extend(queue[i + 1:])
            break

        if lyrics:
            embed_lyrics(file_path, lyrics)
        else:
            print(f"❌ Genius still has no lyrics for: {title}")
            remaining.append(entry)

    with open(GENIUS_RETRY_QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(remaining, f, indent=2, ensure_ascii=False)

    if remaining:
        print(f"\n⏳ {len(remaining)} song(s) still in queue. Run option r again when ready.")
    else:
        print(f"\n✅ Genius retry queue cleared!")

# --- Main processing ---

def process_file(file_path):
    if not file_path.lower().endswith(".mp3"):
        return
    audio = eyed3.load(file_path)
    if audio is None or audio.tag is None:
        print(f"{os.path.basename(file_path)}: ⚠️ No metadata")
        return
    if has_lyrics(audio) and not _force_reembed:
        print(f"{os.path.basename(file_path)}: ✅ Already has lyrics")
        return

    title = audio.tag.title or ""
    artist = (audio.tag.artist or "").strip()
    if not title or not artist:
        print(f"{os.path.basename(file_path)}: ⚠️ Missing title or artist tag")
        log_missing(file_path)
        return

    # If already tagged as instrumental, still run metadata enrichment but skip lyrics
    if _is_instrumental(file_path):
        print(f"{os.path.basename(file_path)}: 🎸 Instrumental — skipping lyrics, checking metadata")
        found = _genius_search(artist, title)
        if found:
            song_id, url, headers = found
            _embed_genius_metadata(file_path, song_id, headers)
        return

    # Only split on / outside of parentheses (avoid breaking "Title (A / B)" style tags)
    title_outer = re.sub(r'\([^)]*\)', '', title)
    sub_titles = [t.strip() for t in title.split("/")] if "/" in title_outer else [title]
    collected_lyrics = []

    for i, sub_title in enumerate(sub_titles):
        lyrics = fetch_lyrics_from_genius(artist, sub_title, mp3_path=file_path if i == 0 else None)
        if lyrics == "INSTRUMENTAL":
            print(f"{os.path.basename(file_path)}: 🎸 Instrumental (Genius confirmed) — no lyrics needed")
            return
        if not lyrics:
            if _genius_rate_limited:
                save_to_retry_queue(artist, sub_title, file_path)
            print(f"🔁 Genius failed — trying lrclib...")
            lyrics = fetch_lyrics_from_lrclib(artist, sub_title)
        if not lyrics:
            print(f"🔁 lrclib failed — trying AZLyrics...")
            lyrics = fetch_lyrics_from_azlyrics(artist, sub_title)
        if not lyrics:
            print(f"🔁 AZLyrics failed — trying songlyrics.com...")
            lyrics = fetch_lyrics_from_songlyrics(artist, sub_title)
        if not lyrics:
            print(f"🔁 songlyrics.com failed — trying lyrics.ovh...")
            lyrics = try_ovh_with_overrides(artist, sub_title)
        if lyrics:
            collected_lyrics.append(lyrics)

    if collected_lyrics:
        embed_lyrics(file_path, "\n\n---\n\n".join(collected_lyrics))
    else:
        print(f"{os.path.basename(file_path)}: ❌ No lyrics found")
        log_missing(file_path)

def process_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for name in files:
            process_file(os.path.join(root, name))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fetch_lyrics.py <folder or file path> [--force] | --retry-genius")
        sys.exit(1)

    if "--force" in sys.argv:
        _force_reembed = True
        print("⚡ Force mode — re-fetching lyrics even if already embedded")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--retry-genius" in sys.argv:
        retry_genius_queue()
    elif args and os.path.isdir(args[0]):
        process_folder(args[0])
    elif args and os.path.isfile(args[0]):
        process_file(args[0])
    else:
        print(f"Not a valid file or folder: {args[0] if args else '(none)'}")
