#!/usr/bin/env python3
"""Add a lyric override to lyrics_overrides.json without editing source code."""
import json
import os
import re
from mutagen.id3 import ID3

BASE_DIR       = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR  = os.path.join(BASE_DIR, "All Songs")
OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lyrics_overrides.json')


def load():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("genius_url", {})
            data.setdefault("azlyrics", {})
            return data
    return {"songlyrics": {}, "ovh": {}, "genius_url": {}, "azlyrics": {}}


def save(data):
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_key(artist, title):
    a = artist.strip().lower()
    t = re.sub(r"\s+", " ", title.strip().lower().replace("’", "'"))
    return f"{a} - {t}"


def _pick_missing_song():
    """Show songs missing lyrics; return (artist, title, filename) or None."""
    try:
        all_songs = sorted(f for f in os.listdir(ALL_SONGS_DIR) if f.endswith(".mp3"))
    except FileNotFoundError:
        print(f"❌ All Songs folder not found: {ALL_SONGS_DIR}")
        return None

    candidates = []
    for f in all_songs:
        path = os.path.join(ALL_SONGS_DIR, f)
        try:
            tags = ID3(path)
            if tags.get("TXXX:Instrumental"):
                continue
            if not any(t.FrameID == "USLT" for t in tags.values()):
                artist = tags["TPE1"].text[0] if "TPE1" in tags else ""
                title  = tags["TIT2"].text[0] if "TIT2" in tags else ""
                candidates.append((f, artist, title))
        except Exception:
            candidates.append((f, "", ""))

    if not candidates:
        print("✅ No songs missing lyrics — nothing to override.")
        return None

    print(f"\n  Songs missing lyrics ({len(candidates)}):")
    for i, (f, artist, title) in enumerate(candidates, 1):
        label = f"{artist} – {title}" if artist and title else f
        print(f"  {i:3}) {label}")

    print()
    choice = input("Pick a number (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
        return None

    f, artist, title = candidates[int(choice) - 1]
    return artist, title, f


def main():
    data = load()
    print("\n=== Add Lyric Override ===")

    # Step 1: pick which song needs fixing
    song = _pick_missing_song()
    if not song:
        print("Cancelled.")
        return

    artist, title, filename = song
    print(f"\n🎵 Selected: {filename}")
    if artist or title:
        print(f"   Artist: {artist}")
        print(f"   Title:  {title}")

    # Step 2: pick the override source
    print()
    print("  1) songlyrics.com  — I found the right URL on songlyrics.com")
    print("  2) lyrics.ovh      — The artist/title just needs a spelling correction")
    print("  3) AZLyrics URL    — Paste the AZLyrics page URL directly")
    print("  4) Genius page URL — Scrapes the Genius page (needs curl_cffi; may be blocked)")
    choice = input("\nChoose 1–4 (or Enter to cancel): ").strip()

    if choice == "1":
        url = input("\nPaste songlyrics.com URL: ").strip()
        if not url:
            print("Cancelled — nothing saved.")
            return
        key = normalize_key(artist, title)
        data["songlyrics"][key] = url
        save(data)
        print(f"✅ Saved songlyrics override")
        print(f"   Key: '{key}'")
        print(f"   URL: {url}")

    elif choice == "2":
        print(f"\nEnter corrected values for lyrics.ovh (press Enter to keep current):")
        artist_correct = input(f"  Corrected artist [{artist}]: ").strip() or artist
        title_correct  = input(f"  Corrected title  [{title}]: ").strip() or title
        if not artist_correct or not title_correct:
            print("Cancelled — nothing saved.")
            return
        key = title.strip().lower()
        data["ovh"][key] = [artist_correct, title_correct]
        save(data)
        print(f"✅ Saved lyrics.ovh override")
        print(f"   Key: '{key}' → ({artist_correct}, {title_correct})")

    elif choice == "3":
        url = input("\nPaste AZLyrics page URL (e.g. https://www.azlyrics.com/lyrics/...): ").strip()
        if not url:
            print("Cancelled — nothing saved.")
            return
        key = normalize_key(artist, title)
        data["azlyrics"][key] = url
        save(data)
        print(f"✅ Saved AZLyrics override")
        print(f"   Key: '{key}'")
        print(f"   URL: {url}")
        print(f"   Re-run option 8 to fetch and embed the lyrics.")

    elif choice == "4":
        print()
        print("  Note: this scrapes the Genius page HTML for lyrics.")
        print("  It does NOT use the Genius API — it requires curl_cffi to bypass")
        print("  Cloudflare, and may still get blocked. If it fails, try AZLyrics instead.")
        url = input("\nPaste Genius page URL (e.g. https://genius.com/...): ").strip()
        if not url:
            print("Cancelled — nothing saved.")
            return
        key = normalize_key(artist, title)
        data["genius_url"][key] = url
        save(data)
        print(f"✅ Saved Genius URL override")
        print(f"   Key: '{key}'")
        print(f"   URL: {url}")
        print(f"   Re-run option 8 to fetch and embed the lyrics.")

    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
