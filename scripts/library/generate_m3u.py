import os

ALL_SONGS_DIR = os.path.expanduser("~/Downloads/YTmp3s/All Songs")
M3U_PATH = os.path.join(ALL_SONGS_DIR, "All_Songs_Full.m3u")

if __name__ == "__main__":
    with open(M3U_PATH, "w", encoding="utf-8") as m3u:
        for filename in sorted(os.listdir(ALL_SONGS_DIR)):
            if filename.endswith(".mp3"):
                full_path = os.path.join(ALL_SONGS_DIR, filename)
                m3u.write(f"{full_path}\n")

    print(f"🎵 Full path M3U playlist created: {M3U_PATH}")

