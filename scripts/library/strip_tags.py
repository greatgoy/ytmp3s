#!/usr/bin/env python3
"""Strip embedded data (lyrics, art, metadata) from MP3 files."""
import os
from mutagen.id3 import ID3

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")

# Frame prefix lists — all keys starting with these will be removed
STRIP_SETS = {
    "lyrics":  ["USLT"],
    "art":     ["APIC"],
    "core":    ["TYER", "TDRC", "TRCK", "TCON"],
    "credits": ["TCOM", "TXXX:Producers", "TXXX:Featured Artists", "TPUB"],
    "relationships": [
        "TXXX:Samples", "TXXX:Sampled By",
        "TXXX:Interpolates", "TXXX:Interpolated By",
        "TXXX:Cover Of", "TXXX:Covered By",
        "TXXX:Remix Of", "TXXX:Remixed By",
    ],
    "extra": [
        "TXXX:Engineering Credits", "TXXX:Phonographic Copyright",
        "TXXX:Distributor", "TXXX:Genius Tags",
    ],
}

# "All non-essential" keeps only TIT2, TPE1, TALB, TPE2, TXXX:Instrumental
KEEP_ALWAYS = {"TIT2", "TPE1", "TALB", "TPE2", "TXXX:Instrumental"}


def _matches_prefix(key, prefixes):
    for p in prefixes:
        if key == p or key.startswith(p + ":") or key.startswith(p + "::"):
            return True
    return False


def strip_frames(mp3_path, prefixes):
    """Remove all frames matching any prefix. Returns count removed."""
    try:
        tags = ID3(mp3_path)
        to_delete = [k for k in list(tags.keys()) if _matches_prefix(k, prefixes)]
        for k in to_delete:
            del tags[k]
        if to_delete:
            tags.save()
        return len(to_delete)
    except Exception as e:
        print(f"  ⚠️  {os.path.basename(mp3_path)}: {e}")
        return 0


def strip_all_nonfundamental(mp3_path):
    """Remove everything except title, artist, album, and instrumental flag."""
    try:
        tags = ID3(mp3_path)
        to_delete = [k for k in list(tags.keys()) if k not in KEEP_ALWAYS]
        for k in to_delete:
            del tags[k]
        if to_delete:
            tags.save()
        return len(to_delete)
    except Exception as e:
        print(f"  ⚠️  {os.path.basename(mp3_path)}: {e}")
        return 0


def strip_everything(mp3_path):
    """Delete all ID3 tags entirely."""
    try:
        tags = ID3(mp3_path)
        tags.delete()
        return 1
    except Exception as e:
        print(f"  ⚠️  {os.path.basename(mp3_path)}: {e}")
        return 0


def select_files(folder):
    print("\nApply to:")
    print("  1) All songs in All Songs folder")
    print("  2) Specific song (search by name)")
    choice = input("Choose: ").strip()

    if choice == "1":
        return [os.path.join(folder, f)
                for f in sorted(os.listdir(folder)) if f.endswith(".mp3")]

    if choice == "2":
        keyword = input("Enter part of the filename: ").strip().lower()
        matches = [f for f in sorted(os.listdir(folder))
                   if f.endswith(".mp3") and keyword in f.lower()]
        if not matches:
            print("No matches found.")
            return []
        if len(matches) == 1:
            print(f"Matched: {matches[0]}")
            return [os.path.join(folder, matches[0])]
        print(f"\n{len(matches)} matches:")
        for i, m in enumerate(matches, 1):
            print(f"  {i}) {m}")
        sel = input("Choose number (or Enter to cancel): ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(matches):
            return [os.path.join(folder, matches[int(sel) - 1])]

    return []


def main():
    print("\n=== Strip Embedded Data ===")
    print("  1) Lyrics")
    print("  2) Album art")
    print("  3) Metadata — Core           (year, track #, genre)")
    print("  4) Metadata — Credits        (writers, producers, featured, label)")
    print("  5) Metadata — Relationships  (samples, covers, remixes, interpolations)")
    print("  6) Metadata — All enriched   (keeps title, artist, album + instrumental flag)")
    print("  7) ⚠️  Everything             (wipes all tags — nuclear option)")
    choice = input("\nChoose (or Enter to cancel): ").strip()

    strip_map = {
        "1": (STRIP_SETS["lyrics"],                                    "lyrics"),
        "2": (STRIP_SETS["art"],                                       "album art"),
        "3": (STRIP_SETS["core"],                                      "core metadata"),
        "4": (STRIP_SETS["credits"],                                   "credits metadata"),
        "5": (STRIP_SETS["relationships"],                             "relationship metadata"),
        "6": None,   # special: strip_all_nonfundamental
        "7": None,   # special: strip_everything
    }

    if choice not in strip_map:
        print("Cancelled.")
        return

    files = select_files(ALL_SONGS_DIR)
    if not files:
        print("No files selected.")
        return

    scope = f"1 song" if len(files) == 1 else f"{len(files)} songs"
    label = strip_map[choice][1] if strip_map[choice] else ("all enriched metadata" if choice == "6" else "ALL tags")

    confirm = input(f"\n⚠️  Strip {label} from {scope}? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    total_modified = 0
    for path in files:
        name = os.path.basename(path)
        if choice == "6":
            n = strip_all_nonfundamental(path)
        elif choice == "7":
            n = strip_everything(path)
        else:
            prefixes, _ = strip_map[choice]
            n = strip_frames(path, prefixes)

        if n:
            print(f"  ✅ {name}: removed {n} field(s)")
            total_modified += 1
        else:
            print(f"  – {name}: nothing to remove")

    print(f"\n✅ Done. {total_modified}/{len(files)} file(s) modified.")


if __name__ == "__main__":
    main()
