import os
import sys
import hashlib
from datetime import datetime

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")
_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(BASE_DIR, "logs", f"deduplication_{_ts}.txt")

def hash_file(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def find_duplicates():
    seen = {}
    duplicates = []
    for filename in os.listdir(ALL_SONGS_DIR):
        if not filename.endswith(".mp3"):
            continue
        full_path = os.path.join(ALL_SONGS_DIR, filename)
        try:
            file_hash = hash_file(full_path)
            if file_hash in seen:
                duplicates.append(full_path)
            else:
                seen[file_hash] = full_path
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    return duplicates

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    dupes = find_duplicates()

    if not dupes:
        print("✅ No duplicates found.")
    else:
        print(f"🗑 Found {len(dupes)} duplicate(s):")
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as log:
            log.write(f"--- Deduplication run on {datetime.now()} ---\n")
            for f in dupes:
                print(f" - {os.path.basename(f)}")
                if dry_run:
                    log.write(f"Would delete: {f}\n")
                else:
                    log.write(f"Deleted: {f}\n")
                    os.remove(f)
        action = "Would remove" if dry_run else "Removed"
        print(f"✅ {action} duplicates. Log saved to: {LOG_FILE}")
