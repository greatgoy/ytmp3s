#!/usr/bin/env python3
"""Fetch rich metadata from Genius API and embed it into MP3 ID3 tags.
Falls back to MusicBrainz, then iTunes when Genius doesn't find a song."""
import os
import sys
import re
import time
import urllib.parse
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TYER, TCOM, TCON, TPUB, TRCK, TXXX, error as ID3Error

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")

# Load .env
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

GENIUS_TOKEN = os.environ.get("GENIUS_ACCESS_TOKEN", "")
GENIUS_HEADERS = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
_MB_HEADERS = {"User-Agent": "ytmp3-enrich/1.0 ( ytmp3 )"}


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


# ── Genius ────────────────────────────────────────────────────────────────────

def _hit_matches(result, artist, title):
    r_artist = _norm(result.get("primary_artist", {}).get("name", ""))
    r_title  = _norm(result.get("title", ""))
    s_artist = _norm(artist)
    s_title  = _norm(title)
    stop = {"the", "a", "an"}
    a_words = set(s_artist.split()) - stop
    r_words = set(r_artist.split()) - stop
    artist_ok = bool(a_words & r_words) if a_words else True
    title_ok  = s_title in r_title or r_title in s_title
    if not title_ok and len(s_title) >= 6:
        title_ok = s_title[:6] in r_title
    return artist_ok and title_ok


def search_genius(artist, title):
    if not GENIUS_TOKEN:
        print("❌ No Genius token found in .env")
        return None
    try:
        resp = requests.get(
            "https://api.genius.com/search",
            params={"q": f"{artist} {title}"},
            headers=GENIUS_HEADERS,
            timeout=10,
        )
        if resp.status_code == 429:
            print("⚠️  Genius rate limit hit — skipping")
            return None
        hits = resp.json().get("response", {}).get("hits", [])
        if not hits:
            return None
        candidates = [h["result"] for h in hits[:5]]
        matched = next((r for r in candidates if _hit_matches(r, artist, title)), None)
        return (matched or candidates[0])["id"]
    except Exception as e:
        print(f"⚠️  Genius search error: {e}")
        return None


def fetch_song_details(song_id):
    try:
        resp = requests.get(
            f"https://api.genius.com/songs/{song_id}",
            params={"text_format": "plain"},
            headers=GENIUS_HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("response", {}).get("song", {})
    except Exception as e:
        print(f"⚠️  Genius song detail error: {e}")
    return None


def embed_enriched_metadata(mp3_path, song, overwrite=False):
    mp3 = MP3(mp3_path, ID3=ID3)
    try:
        mp3.add_tags()
    except ID3Error:
        pass
    tags = mp3.tags
    changed = []

    def _has(key):
        return bool(tags.get(key))

    def _set_text(frame_cls, text, desc=None, label=None):
        key = f"TXXX:{desc}" if desc else frame_cls.__name__
        if _has(key) and not overwrite:
            return
        if desc:
            tags.add(frame_cls(encoding=3, desc=desc, text=[text]))
        else:
            tags.add(frame_cls(encoding=3, text=[text]))
        changed.append(label or key)

    rel = song.get("release_date_components") or {}
    year = rel.get("year")
    if year and not (_has("TYER") or _has("TDRC")) or (year and overwrite):
        tags.add(TYER(encoding=3, text=[str(year)]))
        changed.append(f"Year: {year}")

    track_num = song.get("track_number")
    if track_num:
        _set_text(TRCK, str(track_num), label=f"Track #: {track_num}")

    writers = [w["name"] for w in song.get("writer_artists", [])]
    if writers:
        _set_text(TCOM, ", ".join(writers), label=f"Writers: {', '.join(writers)}")

    producers = [p["name"] for p in song.get("producer_artists", [])]
    if producers:
        _set_text(TXXX, ", ".join(producers), desc="Producers",
                  label=f"Producers: {', '.join(producers)}")

    featured = [a["name"] for a in song.get("featured_artists", [])]
    if featured:
        _set_text(TXXX, ", ".join(featured), desc="Featured Artists",
                  label=f"Featured: {', '.join(featured)}")

    eng_roles = {"engineer", "mixing", "mastering", "recorded", "recording", "mixed", "produced"}
    engineer_credits = []
    for perf in song.get("custom_performances", []):
        label = perf.get("label", "")
        artists = [a["name"] for a in perf.get("artists", [])]
        if not artists:
            continue
        label_lower = label.lower()
        if any(r in label_lower for r in eng_roles):
            engineer_credits.append(f"{label}: {', '.join(artists)}")
        elif "label" in label_lower:
            _set_text(TPUB, ", ".join(artists), label=f"Label: {', '.join(artists)}")
        elif "copyright" in label_lower or "phonographic" in label_lower:
            _set_text(TXXX, ", ".join(artists), desc="Phonographic Copyright",
                      label=f"Copyright: {', '.join(artists)}")
        elif "distributor" in label_lower or "distributed" in label_lower:
            _set_text(TXXX, ", ".join(artists), desc="Distributor",
                      label=f"Distributor: {', '.join(artists)}")

    if engineer_credits:
        _set_text(TXXX, " | ".join(engineer_credits), desc="Engineering Credits",
                  label=f"Engineering: {len(engineer_credits)} credit(s)")

    tag_names = [t["name"] for t in song.get("tags", [])]
    if tag_names:
        _set_text(TXXX, ", ".join(tag_names), desc="Genius Tags",
                  label=f"Tags: {', '.join(tag_names)}")

    rel_map = {
        "samples":              "Samples",
        "sampled_in":           "Sampled By",
        "interpolates":         "Interpolates",
        "interpolated_by":      "Interpolated By",
        "cover_of":             "Cover Of",
        "covered_by":           "Covered By",
        "remix_of":             "Remix Of",
        "remixed_by":           "Remixed By",
        "live_version_of":      "Live Version Of",
        "has_live_version":     "Has Live Version",
        "translation_of":       "Translation Of",
        "alternate_version_of": "Alternate Version Of",
        "original_version_of":  "Original Version Of",
    }
    for rel_type, rel_label in rel_map.items():
        related = []
        for rel_entry in song.get("song_relationships", []):
            if rel_entry.get("relationship_type") == rel_type:
                for s in rel_entry.get("songs", []):
                    a = s.get("primary_artist", {}).get("name", "Unknown")
                    related.append(f"{s['title']} – {a}")
        if related:
            _set_text(TXXX, " | ".join(related), desc=rel_label,
                      label=f"{rel_label}: {', '.join(related[:2])}{'...' if len(related) > 2 else ''}")

    if changed:
        mp3.save()
    return changed


# ── MusicBrainz ───────────────────────────────────────────────────────────────

def search_musicbrainz(artist, title):
    try:
        resp = requests.get(
            "https://musicbrainz.org/ws/2/recording",
            params={"query": f'recording:"{title}" AND artist:"{artist}"', "limit": 5, "fmt": "json"},
            headers=_MB_HEADERS,
            timeout=10,
        )
        time.sleep(1)  # MusicBrainz rate limit: 1 req/sec
        if resp.status_code != 200:
            return None
        recordings = resp.json().get("recordings", [])
        if not recordings:
            return None
        return recordings[0].get("id")
    except Exception as e:
        print(f"⚠️  MusicBrainz search error: {e}")
    return None


def fetch_musicbrainz_details(mbid):
    try:
        resp = requests.get(
            f"https://musicbrainz.org/ws/2/recording/{mbid}",
            params={"inc": "artist-rels+releases+work-rels", "fmt": "json"},
            headers=_MB_HEADERS,
            timeout=10,
        )
        time.sleep(1)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"⚠️  MusicBrainz fetch error: {e}")
    return None


def fetch_musicbrainz_work(work_id):
    try:
        resp = requests.get(
            f"https://musicbrainz.org/ws/2/work/{work_id}",
            params={"inc": "artist-rels", "fmt": "json"},
            headers=_MB_HEADERS,
            timeout=10,
        )
        time.sleep(1)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"⚠️  MusicBrainz work fetch error: {e}")
    return None


def embed_musicbrainz_metadata(mp3_path, data, overwrite=False):
    mp3 = MP3(mp3_path, ID3=ID3)
    try:
        mp3.add_tags()
    except ID3Error:
        pass
    tags = mp3.tags
    changed = []

    def _has(key):
        return bool(tags.get(key))

    # Year from earliest release
    releases = sorted(data.get("releases", []), key=lambda r: r.get("date", "9999"))
    for rel in releases:
        date = rel.get("date", "")
        if date and len(date) >= 4:
            year = date[:4]
            if not (_has("TYER") or _has("TDRC")) or overwrite:
                tags.add(TYER(encoding=3, text=[year]))
                changed.append(f"Year: {year}")
            break

    # Recording-level artist relations: producers (and sometimes writers)
    writers, producers = [], []
    for rel in data.get("relations", []):
        if rel.get("target-type") != "artist":
            continue
        aname = rel.get("artist", {}).get("name", "")
        rtype = rel.get("type", "").lower()
        if not aname:
            continue
        if rtype in ("lyricist", "writer", "composer"):
            writers.append(aname)
        elif rtype == "producer":
            producers.append(aname)

    # Work-level credits: MusicBrainz works (abstract compositions) carry more complete
    # composer/lyricist data than recordings. Follow the work-rel link to get them.
    if not writers:
        for rel in data.get("relations", []):
            if rel.get("target-type") == "work":
                work_id = rel.get("work", {}).get("id")
                if work_id:
                    work_data = fetch_musicbrainz_work(work_id)
                    if work_data:
                        for wrel in work_data.get("relations", []):
                            if wrel.get("target-type") != "artist":
                                continue
                            wtype = wrel.get("type", "").lower()
                            aname = wrel.get("artist", {}).get("name", "")
                            if aname and wtype in ("composer", "lyricist", "writer"):
                                if aname not in writers:
                                    writers.append(aname)
                break  # one work per recording is the norm

    if writers and (not _has("TCOM") or overwrite):
        tags.add(TCOM(encoding=3, text=[", ".join(writers)]))
        changed.append(f"Writers: {', '.join(writers)}")
    if producers and (not _has("TXXX:Producers") or overwrite):
        tags.add(TXXX(encoding=3, desc="Producers", text=[", ".join(producers)]))
        changed.append(f"Producers: {', '.join(producers)}")

    if changed:
        mp3.save()
    return changed


# ── iTunes ────────────────────────────────────────────────────────────────────

def search_itunes_metadata(artist, title):
    try:
        query = urllib.parse.quote_plus(f"{artist} {title}")
        resp = requests.get(
            f"https://itunes.apple.com/search?term={query}&entity=song&limit=5",
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        a_norm = _norm(artist)
        t_norm = _norm(title)
        for r in results:
            r_artist = _norm(r.get("artistName", ""))
            r_track  = _norm(r.get("trackName", ""))
            if any(w in r_artist for w in a_norm.split() if len(w) > 3) and \
               (t_norm in r_track or r_track in t_norm):
                return r
        return results[0]
    except Exception as e:
        print(f"⚠️  iTunes search error: {e}")
    return None


def embed_itunes_metadata(mp3_path, result, overwrite=False):
    mp3 = MP3(mp3_path, ID3=ID3)
    try:
        mp3.add_tags()
    except ID3Error:
        pass
    tags = mp3.tags
    changed = []

    release_date = result.get("releaseDate", "")
    if release_date and len(release_date) >= 4:
        year = release_date[:4]
        if not (tags.get("TYER") or tags.get("TDRC")) or overwrite:
            tags.add(TYER(encoding=3, text=[year]))
            changed.append(f"Year: {year}")

    track_num = result.get("trackNumber")
    if track_num and (not tags.get("TRCK") or overwrite):
        tags.add(TRCK(encoding=3, text=[str(track_num)]))
        changed.append(f"Track #: {track_num}")

    genre = result.get("primaryGenreName")
    if genre and (not tags.get("TCON") or overwrite):
        tags.add(TCON(encoding=3, text=[genre]))
        changed.append(f"Genre: {genre}")

    if changed:
        mp3.save()
    return changed


# ── Per-file processing ───────────────────────────────────────────────────────

def _core_complete(mp3_path):
    """Return True if year, track #, and genre are all filled with real values."""
    try:
        t = ID3(mp3_path)
        return (bool(t.get("TYER") or t.get("TDRC")) and
                bool(t.get("TRCK")) and
                bool(t.get("TCON")))
    except Exception:
        return False


def process_file(mp3_path, overwrite=False):
    filename = os.path.basename(mp3_path)
    try:
        tags = ID3(mp3_path)
    except Exception:
        print(f"{filename}: ⚠️  Can't read tags — skipping")
        return

    title_tag  = tags.get("TIT2")
    artist_tag = tags.get("TPE1")
    if not title_tag or not artist_tag:
        print(f"{filename}: ⚠️  Missing title or artist tag — skipping")
        return

    title  = title_tag.text[0].strip()
    artist = artist_tag.text[0].strip()

    print(f"\n🔍 {filename}")

    # Step 1: Genius — credits, relationships, labels, engineering (richest data)
    genius_found = False
    song_id = search_genius(artist, title)
    if song_id:
        song = fetch_song_details(song_id)
        if song:
            changed = embed_enriched_metadata(mp3_path, song, overwrite=overwrite)
            if changed:
                for item in changed:
                    print(f"  ✅ {item}")
            else:
                print(f"  ℹ️  Genius: no new credits/relationship data")
            genius_found = True

    # Step 2: iTunes — always run for year/track#/genre if any core field is missing.
    # Genius frequently lacks release_date_components, so don't rely on it for core fields.
    if not _core_complete(mp3_path) or overwrite:
        itunes_result = search_itunes_metadata(artist, title)
        if itunes_result:
            changed = embed_itunes_metadata(mp3_path, itunes_result, overwrite=overwrite)
            if changed:
                for item in changed:
                    print(f"  ✅ {item} (iTunes)")

    # Step 3: MusicBrainz — runs when Genius didn't find the song, OR when Genius found
    # it but returned no writer/producer credits. MusicBrainz has solid composer data.
    t = ID3(mp3_path)
    has_credits = bool(t.get("TCOM")) or bool(t.get("TXXX:Producers"))
    if not genius_found or not has_credits or overwrite:
        if not genius_found:
            print(f"  ↩️  Not found on Genius — trying MusicBrainz...")
        else:
            print(f"  ↩️  No credits from Genius — trying MusicBrainz for writers...")
        mb_id = search_musicbrainz(artist, title)
        if mb_id:
            mb_data = fetch_musicbrainz_details(mb_id)
            if mb_data:
                changed = embed_musicbrainz_metadata(mp3_path, mb_data, overwrite=overwrite)
                if changed:
                    for item in changed:
                        print(f"  ✅ {item} (MusicBrainz)")
                elif not genius_found:
                    print(f"  ℹ️  MusicBrainz found song but no new fields to add")

        if not genius_found and not _core_complete(mp3_path):
            print(f"  ❌ Not found on Genius, MusicBrainz, or iTunes")


def process_folder(folder, overwrite=False):
    if not os.path.exists(folder):
        print(f"❌ Folder not found: {folder}")
        return
    songs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".mp3"))
    print(f"📂 Enriching metadata for {len(songs)} song(s)...\n")
    for name in songs:
        process_file(os.path.join(folder, name), overwrite=overwrite)
    print(f"\n✅ Done.")


if __name__ == "__main__":
    overwrite = "--overwrite" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = args[0] if args else ALL_SONGS_DIR

    if os.path.isdir(target):
        process_folder(target, overwrite=overwrite)
    elif os.path.isfile(target):
        process_file(target, overwrite=overwrite)
    else:
        print(f"❌ Invalid path: {target}")
        sys.exit(1)
