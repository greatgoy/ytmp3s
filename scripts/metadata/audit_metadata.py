import sys
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, USLT, APIC
from pathlib import Path
from datetime import datetime
import os

BASE_DIR = Path(os.path.expanduser("~/Downloads/YTmp3s"))
ALL_SONGS_DIR = BASE_DIR / "All Songs"
_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = BASE_DIR / "logs" / f"metadata_audit_{_ts}.txt"

def is_youtube_thumbnail(album_art):
    try:
        if 'youtube' in album_art.data.decode('utf-8', errors='ignore').lower():
            return True
    except Exception:
        pass
    return False

def audit_mp3(file_path, log_file):
    try:
        audio = MP3(file_path, ID3=ID3)
        tags = audio.tags
        has_lyrics = any(isinstance(frame, USLT) for frame in tags.values())
        has_art = any(isinstance(frame, APIC) for frame in tags.values())
        is_youtube_art = False
        if has_art:
            for tag in tags.values():
                if isinstance(tag, APIC) and is_youtube_thumbnail(tag):
                    is_youtube_art = True
                    break

        lyrics_status = '✅' if has_lyrics else '❌'
        art_status = '✅' if has_art and not is_youtube_art else ('❌ (YouTube thumbnail)' if is_youtube_art else '❌')

        result = f"{file_path.name} → Lyrics: {lyrics_status}, Album Art: {art_status}\n"
        print(result, end="")
        log_file.write(result)

    except Exception as e:
        error_message = f"{file_path.name} → Error reading tags: {e}\n"
        print(error_message, end="")
        log_file.write(error_message)

if __name__ == "__main__":
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w") as log_file:
        for mp3_file in ALL_SONGS_DIR.glob("*.mp3"):
            audit_mp3(mp3_file, log_file)
    print(f"\n✅ Metadata audit complete. Log saved to: {LOG_FILE}")
