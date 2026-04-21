import os
import csv
from mutagen.id3 import ID3

ALL_SONGS_DIR = os.path.expanduser("~/Downloads/YTmp3s/All Songs")
CSV_PATH = os.path.join(ALL_SONGS_DIR, "metadata_summary.csv")

def summarize(file):
    try:
        tags = ID3(file)
        title = tags.get("TIT2", "—").text[0] if tags.get("TIT2") else "—"
        artist = tags.get("TPE1", "—").text[0] if tags.get("TPE1") else "—"
        album = tags.get("TALB", "—").text[0] if tags.get("TALB") else "—"
        has_lyrics = "Yes" if any(f.FrameID == "USLT" for f in tags.values()) else "No"
        has_art = "Yes" if any(f.FrameID == "APIC" for f in tags.values()) else "No"
        return [os.path.basename(file), title, artist, album, has_lyrics, has_art]
    except:
        return [os.path.basename(file), "ERROR", "ERROR", "ERROR", "No", "No"]

if __name__ == "__main__":
    print(f"{'File':30} {'Title':30} {'Artist':20} {'Album':20} Lyrics  Art")
    print("-" * 130)
    with open(CSV_PATH, "w", newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["File", "Title", "Artist", "Album", "Has Lyrics", "Has Album Art"])
        for f in sorted(os.listdir(ALL_SONGS_DIR)):
            if f.endswith(".mp3"):
                path = os.path.join(ALL_SONGS_DIR, f)
                data = summarize(path)
                print(f"{data[0]:30.30} {data[1]:30.30} {data[2]:20.20} {data[3]:20.20}   {data[4]}     {data[5]}")
                writer.writerow(data)
    print(f"\n📄 Metadata CSV written to: {CSV_PATH}")

