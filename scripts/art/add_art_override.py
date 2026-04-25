#!/usr/bin/env python3
"""Add an album art override to art_overrides.json without editing source code."""
import json
import os
from mutagen.id3 import ID3

BASE_DIR       = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR  = os.path.join(BASE_DIR, "All Songs")
OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art_overrides.json')


def load():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save(data):
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _has_art(path):
    try:
        return any(t.FrameID == "APIC" for t in ID3(path).values())
    except Exception:
        return False


def _pick_song(overrides):
    try:
        all_songs = sorted(f for f in os.listdir(ALL_SONGS_DIR) if f.endswith(".mp3"))
    except FileNotFoundError:
        print(f"❌ All Songs folder not found: {ALL_SONGS_DIR}")
        return None

    missing = [f for f in all_songs if not _has_art(os.path.join(ALL_SONGS_DIR, f))]
    has_art = [f for f in all_songs if _has_art(os.path.join(ALL_SONGS_DIR, f))]

    display = []
    if missing:
        print(f"\n  Songs missing art ({len(missing)}) — most likely candidates:")
        for f in missing:
            flag = "  ⚠️ override already set" if f in overrides else ""
            display.append(f)
            print(f"  {len(display):3}) {f}{flag}")
    if has_art:
        print(f"\n  Songs with art ({len(has_art)}) — override replaces existing:")
        for f in has_art:
            flag = "  ⚠️ override already set" if f in overrides else ""
            display.append(f)
            print(f"  {len(display):3}) {f}{flag}")

    if not display:
        print("No MP3 files found.")
        return None

    print()
    choice = input("Pick a number (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(display)):
        return None
    return display[int(choice) - 1]


def main():
    data = load()
    print("\n=== Add Album Art Override ===")
    print("Tip: use a direct image URL ending in .jpg or .png")
    print("     Good sources: Genius (images.genius.com), Spotify CDN, Apple Music")

    filename = _pick_song(data)
    if not filename:
        print("Cancelled.")
        return

    print(f"\n🎵 Selected: {filename}")
    url = input("Paste direct image URL: ").strip()
    if not url:
        print("Cancelled — nothing saved.")
        return

    data[filename] = url
    save(data)
    print(f"✅ Saved: '{filename}' → {url}")
    print(f"   Re-run option 9 to fetch and embed the art.")


if __name__ == "__main__":
    main()
