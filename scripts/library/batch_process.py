#!/usr/bin/env python3
"""Run the full pipeline on one or more existing music library folders."""
import os
import subprocess

BASE_DIR   = os.path.expanduser("~/Downloads/YTmp3s")
MUSIC_DIR  = os.path.join(BASE_DIR, "all downloaded music")
SCRIPTS    = os.path.join(BASE_DIR, "scripts")
PYTHON     = os.path.join(BASE_DIR, "venv", "bin", "python3")


def _mp3_count(folder):
    try:
        return sum(1 for f in os.listdir(folder) if f.lower().endswith(".mp3"))
    except Exception:
        return 0


def _run_pipeline(folder):
    steps = [
        ("Cleaning filenames", [PYTHON, f"{SCRIPTS}/metadata/clean_filenames.py", folder]),
        ("Fetching lyrics",    [PYTHON, f"{SCRIPTS}/lyrics/fetch_lyrics.py",      folder]),
        ("Fetching album art", [PYTHON, f"{SCRIPTS}/art/fetch_album_art.py",      folder]),
        ("Enriching metadata", [PYTHON, f"{SCRIPTS}/metadata/enrich_metadata.py", folder]),
    ]
    for label, cmd in steps:
        print(f"\n  ➡️  {label}...")
        subprocess.run(cmd)
    print(f"\n  ✅ Done: {os.path.basename(folder)}")


def _gather_folders():
    """Return list of (group_label, folder_name, full_path, mp3_count) for all music folders."""
    folders = []
    if not os.path.exists(MUSIC_DIR):
        return folders
    for group in ["pre-claude", "with claude"]:
        parent = os.path.join(MUSIC_DIR, group)
        if not os.path.isdir(parent):
            continue
        for name in sorted(os.listdir(parent)):
            path = os.path.join(parent, name)
            if not os.path.isdir(path):
                continue
            count = _mp3_count(path)
            if count > 0:
                folders.append((group, name, path, count))
    return folders


def main():
    folders = _gather_folders()

    if not folders:
        print("\nNo music folders with MP3s found in 'all downloaded music/'.")
        print("Run option 1 to download a playlist first.")
        return

    print("\n=== Batch Process Existing Folders ===")
    print("Runs: clean filenames → lyrics → art → metadata enrichment\n")
    print("Songs stay in their folder — nothing is moved to All Songs.\n")

    pre      = [(n, p, c) for g, n, p, c in folders if g == "pre-claude"]
    with_cl  = [(n, p, c) for g, n, p, c in folders if g == "with claude"]
    all_paths = [p for _, _, p, _ in folders]

    idx = 1
    pre_indices = []
    if pre:
        print(f"  pre-claude  ({len(pre)} folders)")
        for name, path, count in pre:
            print(f"    {idx}) {name}  [{count} songs]")
            pre_indices.append(idx)
            idx += 1

    with_cl_indices = []
    if with_cl:
        print(f"\n  with claude  ({len(with_cl)} folders)")
        for name, path, count in with_cl:
            print(f"    {idx}) {name}  [{count} songs]")
            with_cl_indices.append(idx)
            idx += 1

    total_pre = sum(c for _, _, c in pre)
    print()
    if pre:
        print(f"  A) All pre-claude  ({len(pre)} folders, {total_pre} songs)")
    print(f"  B) Enter number(s)  (comma-separated, e.g.  1  or  1,3,5)")
    print()

    choice = input("Choose (or Enter to cancel): ").strip()
    if not choice:
        print("Cancelled.")
        return

    targets = []
    if choice.upper() == "A" and pre:
        targets = [p for _, p, _ in pre]
    else:
        for part in choice.split(","):
            part = part.strip()
            if part.isdigit():
                n = int(part)
                if 1 <= n <= len(all_paths):
                    targets.append(all_paths[n - 1])
                else:
                    print(f"  Skipping out-of-range selection: {n}")
            else:
                print(f"  Skipping invalid input: {part!r}")

    if not targets:
        print("No valid folders selected.")
        return

    print(f"\nWill run full pipeline on {len(targets)} folder(s):")
    for t in targets:
        count = _mp3_count(t)
        print(f"  • {os.path.basename(t)}  [{count} songs]")

    confirm = input(f"\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    for i, folder in enumerate(targets, 1):
        print(f"\n{'─' * 54}")
        print(f"📂  [{i}/{len(targets)}] {os.path.basename(folder)}")
        print(f"{'─' * 54}")
        _run_pipeline(folder)

    print(f"\n{'═' * 54}")
    print(f"✅  Batch complete — {len(targets)} folder(s) processed.")


if __name__ == "__main__":
    main()
