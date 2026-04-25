#!/usr/bin/env python3
"""View and retry songs that failed to download in a previous playlist run."""
import os
import json
import subprocess
import time

BASE_DIR    = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS   = os.path.join(BASE_DIR, "All Songs")
PLAYLISTS   = os.path.join(BASE_DIR, "playlists")
ARCHIVE     = os.path.join(BASE_DIR, "download_archive.txt")


def _in_archive(vid_id):
    if not os.path.exists(ARCHIVE):
        return False
    with open(ARCHIVE) as f:
        return any(line.strip() == f"youtube {vid_id}" for line in f)


def _load_failure_logs():
    if not os.path.exists(PLAYLISTS):
        return []
    logs = []
    for fname in sorted(os.listdir(PLAYLISTS)):
        if not fname.endswith("_failed.json"):
            continue
        path = os.path.join(PLAYLISTS, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            data["_path"] = path
            # Filter out any that have since been successfully downloaded
            data["failed"] = [e for e in data.get("failed", []) if not _in_archive(e["id"])]
            if data["failed"]:
                logs.append(data)
            else:
                os.remove(path)   # all resolved — clean up
        except Exception:
            pass
    return logs


def _retry_entries(entries):
    before = set(f for f in os.listdir(ALL_SONGS) if f.endswith(".mp3"))

    for entry in entries:
        print(f"\n⬇️  Retrying: {entry['title']}")
        result = subprocess.run([
            "yt-dlp", "-x", "--audio-format", "mp3", "--embed-metadata",
            "--output", f"{ALL_SONGS}/%(title)s.%(ext)s",
            "--download-archive", ARCHIVE,
            entry["url"],
        ])
        if result.returncode == 0 and _in_archive(entry["id"]):
            print(f"  ✅ Downloaded")
        else:
            print(f"  ❌ Still failed — video may be unavailable or region-locked")
        time.sleep(1)

    after = set(f for f in os.listdir(ALL_SONGS) if f.endswith(".mp3"))
    return sorted(after - before)


def main():
    logs = _load_failure_logs()

    if not logs:
        print("\nNo pending download failures found.")
        print("Failure logs are created automatically when yt-dlp can't fetch a song.")
        print("They're also cleared automatically once you've retried successfully.")
        return

    print("\n=== Retry Failed Downloads ===\n")
    for i, log in enumerate(logs, 1):
        name  = log.get("playlist_name", log["_path"])
        count = len(log["failed"])
        print(f"  {i}) {name}  —  {count} failed song(s)")

    print()
    choice = input("Choose a playlist (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(logs)):
        print("Cancelled.")
        return

    log = logs[int(choice) - 1]
    failed = log["failed"]

    print(f"\nFailed songs ({len(failed)}):")
    for i, entry in enumerate(failed, 1):
        print(f"  {i}) {entry['title']}")
        print(f"     {entry['url']}")

    print()
    print("  a) Retry all")
    print("  n) Retry specific song(s)  (enter number(s), e.g. 1 or 1,3)")
    action = input("\nChoose (or Enter to cancel): ").strip().lower()

    if not action:
        print("Cancelled.")
        return

    if action == "a":
        targets = failed
    elif action == "n":
        nums_raw = input("Enter song number(s): ").strip()
        targets = []
        for n in nums_raw.split(","):
            n = n.strip()
            if n.isdigit() and 1 <= int(n) <= len(failed):
                targets.append(failed[int(n) - 1])
        if not targets:
            print("No valid selection.")
            return
    else:
        print("Cancelled.")
        return

    newly_downloaded = _retry_entries(targets)

    if newly_downloaded:
        print(f"\n✅ {len(newly_downloaded)} song(s) now in All Songs:")
        for s in newly_downloaded:
            print(f"  • {s}")

        # Update the main manifest with newly downloaded songs
        sanitized = os.path.splitext(os.path.basename(log["_path"]))[0].replace("_failed", "")
        manifest_path = os.path.join(PLAYLISTS, f"{sanitized}.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            manifest["songs"] = sorted(set(manifest.get("songs", [])) | set(newly_downloaded))
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            print("📋 Manifest updated with newly downloaded songs.")

        print("\n💡 Run option 6 (full pipeline) to add lyrics, art, and metadata.")

    # Update failure log — remove entries that are now in the archive
    still_failed = [e for e in failed if not _in_archive(e["id"])]
    if still_failed:
        log["failed"] = still_failed
        with open(log["_path"], "w") as f:
            json.dump({"playlist_name": log.get("playlist_name", ""),
                       "playlist_url":  log.get("playlist_url", ""),
                       "failed":        still_failed}, f, indent=2)
        print(f"\n⚠️  {len(still_failed)} song(s) still unavailable — may be private or region-locked.")
    else:
        os.remove(log["_path"])
        print("\n📋 All failures resolved — failure log cleared.")


if __name__ == "__main__":
    main()
