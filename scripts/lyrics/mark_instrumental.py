#!/usr/bin/env python3
"""Manually mark or unmark songs as instrumental."""
import os
from mutagen.id3 import ID3, TXXX

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")


def _is_instrumental(tags):
    return bool(tags.get("TXXX:Instrumental"))


def main():
    songs = sorted(f for f in os.listdir(ALL_SONGS_DIR) if f.endswith(".mp3"))

    print("\n=== Mark / Unmark Instrumental ===")
    print("  1) Mark a song as instrumental   (skip lyrics search, no writers expected)")
    print("  2) Unmark a song                 (restore to normal)")
    print("  3) Show all currently marked instrumentals")
    choice = input("\nChoose (or Enter to cancel): ").strip()

    if choice == "3":
        marked = []
        for f in songs:
            try:
                if _is_instrumental(ID3(os.path.join(ALL_SONGS_DIR, f))):
                    marked.append(f)
            except Exception:
                pass
        if marked:
            print(f"\n🎸 {len(marked)} instrumental song(s):")
            for m in marked:
                print(f"  • {m}")
        else:
            print("\nNo songs currently marked as instrumental.")
        return

    if choice not in ("1", "2"):
        print("Cancelled.")
        return

    keyword = input("Enter part of the filename to search: ").strip().lower()
    if not keyword:
        print("Cancelled.")
        return

    matches = [f for f in songs if keyword in f.lower()]
    if not matches:
        print("No matches found.")
        return

    if len(matches) == 1:
        selected = matches[0]
    else:
        print(f"\n{len(matches)} matches:")
        for i, m in enumerate(matches, 1):
            try:
                flag = " 🎸" if _is_instrumental(ID3(os.path.join(ALL_SONGS_DIR, m))) else ""
            except Exception:
                flag = ""
            print(f"  {i}) {m}{flag}")
        sel = input("Choose number (or Enter to cancel): ").strip()
        if not sel.isdigit() or not (1 <= int(sel) <= len(matches)):
            print("Cancelled.")
            return
        selected = matches[int(sel) - 1]

    path = os.path.join(ALL_SONGS_DIR, selected)
    try:
        tags = ID3(path)
    except Exception as e:
        print(f"⚠️  Can't read tags: {e}")
        return

    if choice == "1":
        tags.add(TXXX(encoding=3, desc="Instrumental", text=["yes"]))
        tags.save()
        print(f"✅ Marked as instrumental: {selected}")
        print(f"   Option 8 will now skip lyrics search for this song.")
    else:
        if "TXXX:Instrumental" in tags:
            del tags["TXXX:Instrumental"]
            tags.save()
            print(f"✅ Unmarked: {selected}")
            print(f"   Option 8 will now search for lyrics next time.")
        else:
            print(f"ℹ️  {selected} is not currently marked as instrumental.")


if __name__ == "__main__":
    main()
