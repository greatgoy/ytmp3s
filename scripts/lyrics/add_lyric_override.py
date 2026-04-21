#!/usr/bin/env python3
"""Add a lyric override to lyrics_overrides.json without editing source code."""
import json
import os
import re

OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lyrics_overrides.json')

def load():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("genius_url", {})
            return data
    return {"songlyrics": {}, "ovh": {}, "genius_url": {}}

def save(data):
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def normalize_key(artist, title):
    a = artist.strip().lower()
    t = re.sub(r"\s+", " ", title.strip().lower().replace("\u2019", "'"))
    return f"{a} - {t}"

def main():
    data = load()

    print("\n=== Add Lyric Override ===")
    print("1) songlyrics.com  — I found the right URL on songlyrics.com")
    print("2) lyrics.ovh      — The artist/title just needs a correction")
    print("3) Genius URL      — Paste the exact Genius page URL to scrape directly")
    choice = input("\nChoose 1, 2, or 3 (or Enter to cancel): ").strip()

    if choice == "1":
        print("\nUse the artist and title exactly as stored in your MP3 tags.")
        artist = input("Artist (from MP3 tag): ").strip()
        title  = input("Title  (from MP3 tag): ").strip()
        url    = input("Paste songlyrics.com URL: ").strip()
        if not artist or not title or not url:
            print("Cancelled — nothing saved.")
            return
        key = normalize_key(artist, title)
        data["songlyrics"][key] = url
        save(data)
        print(f"✅ Saved songlyrics override")
        print(f"   Key: '{key}'")
        print(f"   URL: {url}")

    elif choice == "2":
        print("\nUse the title exactly as stored in your MP3 tag (case doesn't matter).")
        title          = input("Song title (from MP3 tag): ").strip().lower()
        artist_correct = input("Corrected artist for lyrics.ovh: ").strip()
        title_correct  = input("Corrected title for lyrics.ovh: ").strip()
        if not title or not artist_correct or not title_correct:
            print("Cancelled — nothing saved.")
            return
        data["ovh"][title] = [artist_correct, title_correct]
        save(data)
        print(f"✅ Saved lyrics.ovh override")
        print(f"   Key: '{title}' → ({artist_correct}, {title_correct})")

    elif choice == "3":
        print("\nUse the artist and title exactly as stored in your MP3 tags.")
        artist = input("Artist (from MP3 tag): ").strip()
        title  = input("Title  (from MP3 tag): ").strip()
        url    = input("Paste Genius page URL (e.g. https://genius.com/...): ").strip()
        if not artist or not title or not url:
            print("Cancelled — nothing saved.")
            return
        key = normalize_key(artist, title)
        data["genius_url"][key] = url
        save(data)
        print(f"✅ Saved Genius URL override")
        print(f"   Key: '{key}'")
        print(f"   URL: {url}")
        print(f"   Re-run option '8' to fetch and embed the lyrics.")

    else:
        print("Cancelled.")

if __name__ == "__main__":
    main()
