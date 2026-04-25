#!/usr/bin/env python3
"""Manually mark or unmark songs as instrumental."""
import os
from mutagen.id3 import ID3, TXXX

BASE_DIR      = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")


def _is_instrumental(tags):
    return bool(tags.get("TXXX:Instrumental"))


def _list_songs(filter_fn, label):
    """Return [(filename, path)] matching filter_fn, or None if none found."""
    try:
        all_songs = sorted(f for f in os.listdir(ALL_SONGS_DIR) if f.endswith(".mp3"))
    except FileNotFoundError:
        print(f"❌ All Songs folder not found: {ALL_SONGS_DIR}")
        return None

    result = []
    for f in all_songs:
        path = os.path.join(ALL_SONGS_DIR, f)
        try:
            tags = ID3(path)
            if filter_fn(tags):
                result.append((f, path))
        except Exception:
            pass

    if not result:
        print(f"\nNo songs found for: {label}")
        return None

    print(f"\n  {label} ({len(result)}):")
    for i, (f, _) in enumerate(result, 1):
        print(f"  {i:3}) {f}")
    return result


def _pick_from(items):
    print()
    choice = input("Pick a number (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
        return None
    return items[int(choice) - 1]


def main():
    print("\n=== Mark / Unmark Instrumental ===")
    print("  1) Mark a song as instrumental   (skip lyrics search, no writers expected)")
    print("  2) Unmark a song                 (restore to normal)")
    print("  3) Show all currently marked instrumentals")
    choice = input("\nChoose (or Enter to cancel): ").strip()

    if choice == "3":
        items = _list_songs(_is_instrumental, "Marked instrumentals")
        if not items:
            print("\nNo songs currently marked as instrumental.")
        return

    if choice == "1":
        # Show songs missing lyrics — those are the most likely candidates
        def _missing_lyrics(tags):
            if _is_instrumental(tags):
                return False
            return not any(t.FrameID == "USLT" for t in tags.values())

        items = _list_songs(_missing_lyrics, "Songs missing lyrics (likely instrumental candidates)")
        if not items:
            print("All songs either have lyrics or are already marked instrumental.")
            return

        picked = _pick_from(items)
        if not picked:
            print("Cancelled.")
            return

        filename, path = picked
        try:
            tags = ID3(path)
        except Exception as e:
            print(f"⚠️  Can't read tags: {e}")
            return

        tags.add(TXXX(encoding=3, desc="Instrumental", text=["yes"]))
        tags.save()
        print(f"✅ Marked as instrumental: {filename}")
        print(f"   Option 8 will now skip lyrics search for this song.")

    elif choice == "2":
        items = _list_songs(_is_instrumental, "Marked instrumentals")
        if not items:
            return

        picked = _pick_from(items)
        if not picked:
            print("Cancelled.")
            return

        filename, path = picked
        try:
            tags = ID3(path)
        except Exception as e:
            print(f"⚠️  Can't read tags: {e}")
            return

        if "TXXX:Instrumental" in tags:
            del tags["TXXX:Instrumental"]
            tags.save()
            print(f"✅ Unmarked: {filename}")
            print(f"   Option 8 will now search for lyrics next time.")
        else:
            print(f"ℹ️  {filename} is not currently marked as instrumental.")

    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
