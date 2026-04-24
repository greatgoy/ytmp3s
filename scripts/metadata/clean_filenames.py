#!/usr/bin/env python3
import os
import re
import sys
from datetime import datetime
from mutagen.easyid3 import EasyID3

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "All Songs")
_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(BASE_DIR, "logs", f"rename_{_ts}.txt")

JUNK_PATTERNS = [
    r"\s*-\s*official( music)? video\b.*",
    r"\s*-\s*lyrics\b.*",
    r"\s*\(.*?HD.*?\)",
    r"\s*\(.*?audio only.*?\)",
]

KEEP_PATTERNS = [
    r"\(\d{4} Remaster\)",
    r"\(Piano Version\)",
    r"\(Live at.*?\)",
    r"\(Original Mix\)"
]

def clean_title(title):
    keep_fragments = []
    for pattern in KEEP_PATTERNS:
        match = re.search(pattern, title, flags=re.IGNORECASE)
        if match:
            keep_fragments.append(match.group())

    for pattern in JUNK_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s*\(.*?\)", "", title)
    cleaned = cleaned.strip(" -_.")
    return cleaned + (" " + " ".join(keep_fragments) if keep_fragments else "")

def get_clean_filename(mp3_path):
    try:
        audio = EasyID3(mp3_path)
        title = audio.get("title", [None])[0]
        artist = audio.get("artist", [None])[0]
        if not title or not artist:
            return None

        is_radio_edit = re.search(r"\(official( music)? video\)", title, re.IGNORECASE)
        cleaned_title = clean_title(title)

        if is_radio_edit:
            cleaned_title = f"{cleaned_title} (Radio Edit)"

        if "⧸" not in title and "/" in cleaned_title:
            return None

        final_name = f"{cleaned_title.strip()} ({artist.strip()})"
        return f"{final_name}.mp3"

    except Exception:
        return None

def embed_track_number(mp3_path, track_num, log):
    try:
        audio = EasyID3(mp3_path)
        if not audio.get("tracknumber"):
            audio["tracknumber"] = [str(track_num)]
            audio.save()
            msg = f"🔢 Set track #{track_num} for: {os.path.basename(mp3_path)}"
            log.write(msg + "\n")
            print(msg)
    except Exception as e:
        log.write(f"⚠️  Could not set track number for {os.path.basename(mp3_path)}: {e}\n")

def main():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w") as log:
        for file in os.listdir(ALL_SONGS_DIR):
            if not file.lower().endswith(".mp3"):
                continue

            full_path = os.path.join(ALL_SONGS_DIR, file)

            # Handle Apple Music track-number prefix: "63 Song Name.mp3"
            prefix_match = re.match(r'^(\d+)\s+(.+)$', os.path.splitext(file)[0])
            if prefix_match:
                embed_track_number(full_path, prefix_match.group(1), log)

            new_name = get_clean_filename(full_path)
            if not new_name or new_name == file:
                continue

            new_path = os.path.join(ALL_SONGS_DIR, new_name)
            try:
                os.rename(full_path, new_path)
                log.write(f"✅ Renamed: {file} → {new_name}\n")
                print(f"🧼 {file} → {new_name}")
            except Exception as e:
                log.write(f"❌ Failed: {file} → {new_name} ({e})\n")

    print(f"\n✅ Renaming complete. Log saved to: {LOG_FILE}")

if __name__ == "__main__":
    main()
