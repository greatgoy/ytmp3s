import os
import sys
import re
import time
import threading
import requests
import urllib.parse
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ART_OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art_overrides.json')

# Load .env
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")

_MB_HEADERS = {"User-Agent": "ytmp3-art/1.0 ( ytmp3 )"}
_LASTFM_DEFAULT_IMG = "2a96cbd8b46e442fc41c2b86b821562f.png"

# Limit concurrent iTunes requests — too many threads hitting it simultaneously causes 429s
_ITUNES_SEMAPHORE = threading.Semaphore(2)


def load_art_overrides():
    import json
    if os.path.exists(ART_OVERRIDES_PATH):
        with open(ART_OVERRIDES_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def normalize_album(album):
    return album.replace('&', '').replace('  ', ' ').strip()


def search_itunes(album, artist):
    if not album or not artist:
        return None
    query = urllib.parse.quote_plus(f"{normalize_album(album)} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1"
    with _ITUNES_SEMAPHORE:
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 429:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    print(f"   ⚠️  iTunes rate limited — retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                results = response.json().get('results')
                if results:
                    return results[0]['artworkUrl100'].replace('100x100bb.jpg', '600x600bb.jpg')
                return None
            except Exception as e:
                print(f"   ⚠️  iTunes error: {e}")
                return None
    return None


def search_musicbrainz(artist, title):
    try:
        query = f'recording:"{title}" AND artist:"{artist}"'
        resp = requests.get(
            "https://musicbrainz.org/ws/2/recording",
            params={"query": query, "limit": 5, "fmt": "json"},
            headers=_MB_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        recordings = resp.json().get("recordings", [])
        release_mbids = []
        for rec in recordings:
            for rel in rec.get("releases", []):
                mbid = rel.get("id")
                if mbid:
                    release_mbids.append(mbid)
        for mbid in release_mbids[:3]:
            try:
                art_resp = requests.get(
                    f"https://coverartarchive.org/release/{mbid}/front",
                    headers=_MB_HEADERS,
                    timeout=10,
                    allow_redirects=True,
                )
                if art_resp.status_code == 200 and "image" in art_resp.headers.get("content-type", ""):
                    return f"https://coverartarchive.org/release/{mbid}/front"
            except Exception:
                continue
    except Exception as e:
        print(f"   ⚠️  MusicBrainz error: {e}")
    return None


def search_deezer(artist, title):
    try:
        resp = requests.get(
            "https://api.deezer.com/search",
            params={"q": f'artist:"{artist}" track:"{title}"', "limit": 1},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        tracks = resp.json().get("data", [])
        if tracks:
            album = tracks[0].get("album", {})
            return album.get("cover_xl") or album.get("cover_big") or album.get("cover")
    except Exception as e:
        print(f"   ⚠️  Deezer error: {e}")
    return None


def search_lastfm(artist, album, title):
    if not LASTFM_API_KEY:
        return None
    try:
        if album and album != "Unknown Album":
            resp = requests.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "album.getInfo",
                    "artist": artist,
                    "album": album,
                    "api_key": LASTFM_API_KEY,
                    "format": "json",
                },
                timeout=10,
            )
            images = resp.json().get("album", {}).get("image", [])
            for img in reversed(images):
                url = img.get("#text", "")
                if url and _LASTFM_DEFAULT_IMG not in url:
                    return url

        # Fallback: track.getInfo (returns album art too)
        resp = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "track.getInfo",
                "artist": artist,
                "track": title,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=10,
        )
        images = resp.json().get("track", {}).get("album", {}).get("image", [])
        for img in reversed(images):
            url = img.get("#text", "")
            if url and _LASTFM_DEFAULT_IMG not in url:
                return url
    except Exception as e:
        print(f"   ⚠️  Last.fm error: {e}")
    return None


def find_art_url(album, artist, title):
    sources = [
        ("iTunes",       lambda: search_itunes(album, artist)),
        ("MusicBrainz",  lambda: search_musicbrainz(artist, title)),
        ("Deezer",       lambda: search_deezer(artist, title)),
        ("Last.fm",      lambda: search_lastfm(artist, album, title)),
    ]
    for name, fn in sources:
        print(f"   🔍 Trying {name}...")
        url = fn()
        if url:
            print(f"   ✅ Found on {name}")
            return url
    return None


def embed_album_art(mp3_path, album, artist, title, override_url=None):
    mp3 = MP3(mp3_path, ID3=ID3)
    try:
        mp3.add_tags()
    except error:
        pass

    if override_url:
        print(f"{title}: 📎 Using override URL...")
        cover_url = override_url
    else:
        cover_url = find_art_url(album, artist, title)

    if not cover_url:
        print(f"{title}: ❌ No album art found on any source")
        return False

    temp_cover = f"cover_{re.sub(r'[^a-zA-Z0-9]', '_', str(title))}.jpg"

    try:
        response = requests.get(cover_url, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        if 'image' not in content_type:
            print(f"{title}: ⚠️ URL may not be a direct image (Content-Type: {content_type})")

        with open(temp_cover, 'wb') as f:
            f.write(response.content)

        with open(temp_cover, 'rb') as albumart:
            mp3.tags.add(
                APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=albumart.read())
            )
        mp3.save()
        print(f"{title}: ✅ Album art embedded")
        return True

    except Exception as e:
        print(f"{title}: ❌ Error embedding art: {e}")
        return False

    finally:
        try:
            if os.path.exists(temp_cover):
                os.remove(temp_cover)
        except FileNotFoundError:
            pass


def process_file(mp3_path, redo_existing):
    try:
        filename = os.path.basename(mp3_path)
        audio = MP3(mp3_path, ID3=ID3)
        overrides = load_art_overrides()
        has_art = any(key.startswith('APIC') for key in audio.tags.keys())
        is_override = filename in overrides

        if has_art and not redo_existing and not is_override:
            print(f"{filename}: 🎵 Skipped (already has album art)")
            return

        artist = audio.tags.get('TPE1')
        title  = audio.tags.get('TIT2')
        album  = audio.tags.get('TALB')

        artist_text = artist.text[0] if artist else "Unknown Artist"
        title_text  = title.text[0]  if title  else filename
        album_text  = album.text[0]  if album  else "Unknown Album"

        override_url = overrides.get(filename)

        if artist_text or override_url:
            print(f"\n🎯 Processing: {filename}")
            if not override_url:
                print(f"   Artist: {artist_text} | Album: {album_text}")
            embed_album_art(mp3_path, album_text, artist_text, title_text, override_url)

    except Exception as e:
        print(f"{os.path.basename(mp3_path)}: ❌ Error: {e}")


def process_all_files(folder, redo_existing=False):
    if not os.path.exists(folder):
        print("❌ Folder not found!")
        return

    threads = []
    print(f"📂 Scanning folder: {folder}")
    for filename in os.listdir(folder):
        if filename.lower().endswith('.mp3'):
            mp3_path = os.path.join(folder, filename)
            t = threading.Thread(target=process_file, args=(mp3_path, redo_existing))
            t.start()
            threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = sys.argv[1]
        redo = "--redo" in sys.argv
    else:
        folder = input("🎵 Enter folder path: ").strip().strip('"').strip("'")
        redo = input("🛠 Re-embed existing album art? (y/n): ").lower() == 'y'

    process_all_files(folder, redo)
