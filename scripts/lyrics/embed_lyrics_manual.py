#!/usr/bin/env python3
import os
import sys
import eyed3

eyed3.log.setLevel("ERROR")

ALL_SONGS_DIR = os.path.expanduser("~/Downloads/YTmp3s/All Songs")


def embed_lyrics(mp3_path, lyrics):
    audio = eyed3.load(mp3_path)
    if audio.tag is None:
        audio.initTag(version=(2, 3, 0))
    audio.tag.frame_set.pop("USLT", None)
    audio.tag.lyrics.set(lyrics, lang=b"eng")
    audio.tag.save(version=(2, 3, 0))
    print(f"✅ Lyrics embedded into: {os.path.basename(mp3_path)}")


def pick_song(songs):
    print(f"\nSongs in All Songs ({len(songs)} total):\n")
    for i, s in enumerate(songs, 1):
        print(f"  {i:3}. {s}")
    print()

    choice = input("Enter number or partial filename: ").strip()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(songs):
            return os.path.join(ALL_SONGS_DIR, songs[idx])
        print("❌ Number out of range.")
        return None

    matches = [s for s in songs if choice.lower() in s.lower()]
    if not matches:
        print("❌ No matching song found.")
        return None
    if len(matches) == 1:
        return os.path.join(ALL_SONGS_DIR, matches[0])

    print("\nMultiple matches:")
    for i, m in enumerate(matches, 1):
        print(f"  {i}. {m}")
    sub = input("Pick one (number): ").strip()
    if sub.isdigit():
        idx = int(sub) - 1
        if 0 <= idx < len(matches):
            return os.path.join(ALL_SONGS_DIR, matches[idx])

    print("❌ Invalid selection.")
    return None


def main():
    print("\n=== Manual Lyrics Embed ===")

    try:
        songs = sorted(f for f in os.listdir(ALL_SONGS_DIR) if f.lower().endswith(".mp3"))
    except FileNotFoundError:
        print(f"❌ Folder not found: {ALL_SONGS_DIR}")
        sys.exit(1)

    if not songs:
        print("No MP3 files found.")
        return

    mp3_path = pick_song(songs)
    if not mp3_path:
        return

    print(f"\n🎵 Selected: {os.path.basename(mp3_path)}")
    print("\nPaste lyrics below. When done, press Enter then Ctrl+D:")
    print("─" * 50)

    try:
        lines = sys.stdin.readlines()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    lyrics = "".join(lines).strip()
    print("─" * 50)

    if not lyrics:
        print("❌ No lyrics entered. Cancelled.")
        return

    print(f"\n📝 {len(lyrics.splitlines())} lines captured.")
    confirm = input("Embed these lyrics? (y/n): ").strip().lower()
    if confirm == "y":
        embed_lyrics(mp3_path, lyrics)
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
