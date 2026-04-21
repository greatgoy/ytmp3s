# repair_metadata.py
import os
import sys
import requests
import subprocess
import urllib.parse
from datetime import datetime
from mutagen.easyid3 import EasyID3
import re

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")
LOG_DIR = os.path.join(BASE_DIR, "logs")
_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
MISSING_ART_LOG = os.path.join(LOG_DIR, f"missing_art_{_ts}.txt")

os.makedirs(LOG_DIR, exist_ok=True)

def clean_title(title):
    return re.sub(r'\s*\([^)]*\)', '', title).strip()

def clean_artist(artist):
    artist = re.split(r'/|-|&', artist)[0]
    artist = re.sub(r'\(??(feat|ft)\..*', '', artist, flags=re.IGNORECASE)
    return artist.strip()

def get_metadata(mp3_path):
    try:
        audio = EasyID3(mp3_path)
        artist = audio.get("artist", [""])[0]
        title = audio.get("title", [""])[0]
        return artist, title
    except Exception as e:
        print(f"⚠️  Failed to read metadata from {mp3_path}: {e}")
        return "", ""

def fetch_album_art(artist, title):
    cleaned_artist = clean_artist(artist)
    cleaned_title = clean_title(title)
    query = urllib.parse.quote_plus(f"{cleaned_artist} {cleaned_title}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data["resultCount"] > 0:
            artwork_url = data["results"][0]["artworkUrl100"].replace("100x100bb", "600x600bb")
            image_data = requests.get(artwork_url, timeout=10).content
            with open("cover.jpg", "wb") as f:
                f.write(image_data)
            return True
    except Exception as e:
        print(f"❌ Failed to fetch album art: {e}")
    return False

def embed_album_art(mp3_path):
    temp_output = mp3_path.replace(".mp3", "_temp.mp3")
    command = [
        "ffmpeg", "-y", "-i", mp3_path, "-i", "cover.jpg",
        "-map", "0:a", "-map", "1:v", "-c", "copy", "-id3v2_version", "3",
        "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)",
        temp_output
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.path.exists(temp_output):
        os.replace(temp_output, mp3_path)
        return True
    return False

def process_file(mp3_path):
    artist, title = get_metadata(mp3_path)
    if not artist or not title:
        return False, "Missing metadata"

    success = fetch_album_art(artist, title)
    if success:
        embed_success = embed_album_art(mp3_path)
        os.remove("cover.jpg")
        return embed_success, "Album art embedded"
    else:
        with open(MISSING_ART_LOG, "a") as f:
            f.write(os.path.basename(mp3_path) + "\n")
        return False, "No album art found"

def process_directory(path):
    report = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.lower().endswith(".mp3"):
                mp3_path = os.path.join(root, file)
                success, message = process_file(mp3_path)
                report.append((mp3_path, success, message))
    return report

def main():
    if len(sys.argv) < 2:
        print("Usage: python repair_metadata.py <mp3 file | folder>")
        return

    path = sys.argv[1]
    if os.path.isdir(path):
        report = process_directory(path)
        for mp3_path, success, message in report:
            print(f"{mp3_path}: {'✅' if success else '❌'} {message}")
    elif os.path.isfile(path) and path.lower().endswith(".mp3"):
        success, message = process_file(path)
        print(f"{path}: {'✅' if success else '❌'} {message}")
    else:
        print("❌ Invalid input. Provide a valid .mp3 file or folder.")

if __name__ == "__main__":
    main()
