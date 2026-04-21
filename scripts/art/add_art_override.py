#!/usr/bin/env python3
"""Add an album art override to art_overrides.json without editing source code."""
import json
import os

OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art_overrides.json')

def load():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save(data):
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    data = load()
    print("\n=== Add Album Art Override ===")
    print("Tip: use a direct image URL ending in .jpg or .png")
    print("     Good sources: Genius (images.genius.com), Spotify CDN, Apple Music\n")

    filename = input("Exact MP3 filename (e.g. 'Song Name (Artist).mp3'): ").strip()
    url      = input("Paste direct image URL: ").strip()

    if not filename or not url:
        print("Cancelled — nothing saved.")
        return

    data[filename] = url
    save(data)
    print(f"✅ Saved: '{filename}' → {url}")

if __name__ == "__main__":
    main()
