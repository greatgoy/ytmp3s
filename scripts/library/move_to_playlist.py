#!/usr/bin/env python3
"""Move processed songs from All Songs into their tracked playlist folder."""
import os
import json
import shutil

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")
PLAYLISTS_DIR = os.path.join(BASE_DIR, "playlists")


def load_manifests():
    if not os.path.exists(PLAYLISTS_DIR):
        return []
    manifests = []
    for f in sorted(os.listdir(PLAYLISTS_DIR)):
        if not f.endswith(".json"):
            continue
        path = os.path.join(PLAYLISTS_DIR, f)
        try:
            with open(path) as fp:
                data = json.load(fp)
            data["_manifest_path"] = path
            manifests.append(data)
        except Exception:
            pass
    return manifests


def songs_still_in_all(manifest):
    return [s for s in manifest.get("songs", [])
            if os.path.exists(os.path.join(ALL_SONGS_DIR, s))]


def main():
    manifests = load_manifests()

    if not manifests:
        print("\nNo playlist manifests found.")
        print("Download a playlist with option 1 first, then run the pipeline")
        print("(option 6), and come back here to move the songs.")
        return

    print("\n=== Move Songs to Playlist Folder ===\n")

    pending = [(m, songs_still_in_all(m)) for m in manifests]

    for i, (m, in_all) in enumerate(pending, 1):
        folder_name = os.path.basename(m.get("folder", "Unknown"))
        total = len(m.get("songs", []))
        if in_all:
            status = f"{len(in_all)}/{total} songs still in All Songs"
        else:
            status = f"✅ all {total} song(s) already moved"
        print(f"  {i}) {folder_name}  —  {status}")

    print()
    choice = input("Choose a playlist (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(pending)):
        print("Cancelled.")
        return

    manifest, in_all = pending[int(choice) - 1]
    playlist_folder = manifest["folder"]
    playlist_name = manifest["playlist_name"]

    if not in_all:
        print(f"\n✅ All songs from '{playlist_name}' have already been moved.")
        remove = input("Remove from tracking? (y/n): ").strip().lower()
        if remove == "y":
            os.remove(manifest["_manifest_path"])
            print("📋 Removed from tracking.")
        return

    print(f"\nDestination: {playlist_folder}")
    print(f"\n{len(in_all)} song(s) to move:")
    for s in in_all:
        print(f"  • {s}")

    print()
    confirm = input(
        f"Move {len(in_all)} song(s) to '{os.path.basename(playlist_folder)}'? (y/n): "
    ).strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    os.makedirs(playlist_folder, exist_ok=True)
    moved = 0
    for song in in_all:
        src = os.path.join(ALL_SONGS_DIR, song)
        dst = os.path.join(playlist_folder, song)
        if os.path.exists(dst):
            print(f"  ⚠️  Already in destination, skipping: {song}")
            continue
        shutil.move(src, dst)
        print(f"  ✅ Moved: {song}")
        moved += 1

    print(f"\n✅ {moved} song(s) moved to: {playlist_folder}")

    if not songs_still_in_all(manifest):
        os.remove(manifest["_manifest_path"])
        print("📋 Playlist removed from tracking (all songs moved).")


if __name__ == "__main__":
    main()
