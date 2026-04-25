#!/usr/bin/env python3
"""View and manage the yt-dlp download archive."""
import os
import shutil

BASE_DIR        = os.path.expanduser("~/Downloads/YTmp3s")
ARCHIVE         = os.path.join(BASE_DIR, "download_archive.txt")
ARCHIVE_BACKUP  = os.path.join(BASE_DIR, "download_archive_pre_claude.txt")


def _count(path):
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        return sum(1 for l in f if l.strip())


def main():
    current_count = _count(ARCHIVE)
    backup_count  = _count(ARCHIVE_BACKUP)

    print("\n=== Manage Download Archive ===")
    print("The archive tells yt-dlp which videos it has already downloaded,")
    print("preventing duplicate downloads across playlists.\n")

    print(f"  Active archive:     {current_count} entries  ({ARCHIVE})")
    if backup_count:
        print(f"  Pre-claude backup:  {backup_count} entries  ({ARCHIVE_BACKUP})")
    print()
    print("  1) Archive current entries as pre-claude and start fresh")
    print("     → Moves active archive to download_archive_pre_claude.txt")
    print("     → New archive starts empty so re-runs won't be blocked")
    print("     → Existing songs in your library are safe — they won't be re-downloaded")
    print("       unless you pass their playlist URL to option 1 again")
    print()
    print("  2) Clear active archive entirely")
    print("     ⚠️  This lets yt-dlp re-download everything — only use if you need")
    print("        to fully re-fetch songs that are no longer on disk")
    print()
    print("  3) View recent archive entries")
    print()
    print("  4) Show archive stats by extractor (YouTube, SoundCloud, etc.)")

    choice = input("\nChoose (or Enter to cancel): ").strip()

    if choice == "1":
        if current_count == 0:
            print("\nActive archive is already empty — nothing to move.")
            return
        confirm = input(f"\nMove {current_count} entries to pre-claude backup and start fresh? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return
        # Append to backup (preserves any existing backup)
        with open(ARCHIVE) as src, open(ARCHIVE_BACKUP, "a") as dst:
            dst.write(src.read())
        # Clear active
        open(ARCHIVE, "w").close()
        print(f"\n✅ {current_count} entries moved to download_archive_pre_claude.txt")
        print("   Active archive is now fresh — new downloads will be tracked from here.")
        print("   Your existing music files are untouched.")

    elif choice == "2":
        if current_count == 0:
            print("\nActive archive is already empty.")
            return
        print(f"\n⚠️  This will clear all {current_count} entries.")
        print("   yt-dlp will no longer know what it has downloaded — re-running any")
        print("   playlist will attempt to download every song again.")
        confirm = input("\nClear archive? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return
        # Keep a timestamped backup just in case
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BASE_DIR, f"download_archive_backup_{ts}.txt")
        shutil.copy2(ARCHIVE, backup_path)
        open(ARCHIVE, "w").close()
        print(f"\n✅ Archive cleared. Safety backup saved to: {os.path.basename(backup_path)}")

    elif choice == "3":
        if current_count == 0:
            print("\nActive archive is empty.")
            return
        with open(ARCHIVE) as f:
            lines = [l.strip() for l in f if l.strip()]
        recent = lines[-30:]
        print(f"\nLast {len(recent)} of {current_count} entries:")
        for line in recent:
            print(f"  {line}")

    elif choice == "4":
        if current_count == 0:
            print("\nActive archive is empty.")
            return
        from collections import Counter
        with open(ARCHIVE) as f:
            extractors = Counter()
            for line in f:
                parts = line.strip().split(" ", 1)
                if parts:
                    extractors[parts[0]] += 1
        print(f"\nArchive breakdown ({current_count} total):")
        for extractor, count in extractors.most_common():
            print(f"  {extractor:<20} {count} entries")

    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
