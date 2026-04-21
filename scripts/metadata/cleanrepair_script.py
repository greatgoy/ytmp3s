#!/usr/bin/env python3

import os
import sys
import eyed3

# Mapping of keywords in filename → (Title, Artist)
manual_metadata = {
    "wild thing": ("Wild Thing", "X"),
    "sandstorm": ("Sandstorm (Radio Edit)", "Darude"),
    "sultans of swing": ("Sultans Of Swing", "Dire Straits"),
    "ain't no rest for the wicked": ("Ain't No Rest for the Wicked", "Cage the Elephant"),
    "cigarette daydreams": ("Cigarette Daydreams", "Cage the Elephant"),
    "i melt with you": ("I Melt with You (7\" Mix)", "Modern English"),
    "diablo": ("Diablo (Remix)", "Mac Miller"),
    "can't hold us": ("Can't Hold Us (feat. Ray Dalton)", "Macklemore, Ryan Lewis, Ray Dalton"),  # ✅ NEW
}

def clean_and_repair_metadata(folder):
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if not filename.lower().endswith(".mp3"):
            continue

        lower_name = filename.lower()
        matched = False

        for keyword, (title, artist) in manual_metadata.items():
            if keyword in lower_name:
                matched = True
                new_filename = f"{title} ({artist}).mp3"
                new_filepath = os.path.join(folder, new_filename)

                print(f"🛠 Renaming '{filename}' → '{new_filename}'")
                try:
                    os.rename(filepath, new_filepath)
                except Exception as e:
                    print(f"❌ Rename failed: {e}")
                    continue

                audio = eyed3.load(new_filepath)
                if not audio:
                    print(f"❌ Failed to load '{new_filename}'")
                    continue

                if not audio.tag:
                    audio.initTag()

                audio.tag.title = title
                audio.tag.artist = artist

                try:
                    audio.tag.save()
                    print(f"✅ Updated metadata: Title = '{title}', Artist = '{artist}'")
                except Exception as e:
                    print(f"❌ Failed to save metadata for '{new_filename}': {e}")
                break

        if not matched:
            print(f"⚠️ No matching pattern found in filename: {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 cleanrepair_script.py <full_path_to_folder>")
    else:
        clean_and_repair_metadata(sys.argv[1])


