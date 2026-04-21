import os
import sys
import eyed3

def remove_lyrics_from_folder(folder_path):
    removed_files = []
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(".mp3"):
            full_path = os.path.join(folder_path, file_name)
            audio = eyed3.load(full_path)
            if audio is not None and audio.tag is not None and audio.tag.lyrics:
                audio.tag.lyrics.set("", lang=b"eng")
                audio.tag.save(version=(2, 3, 0))
                print(f"✅ Removed lyrics: {file_name}")
                removed_files.append(file_name)
            else:
                print(f"⏩ Skipped (no lyrics): {file_name}")
    return removed_files

if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("📁 Enter the path to the folder containing MP3s: ").strip()

    if not os.path.isdir(folder_path):
        print("❌ That folder does not exist. Please check the path.")
    else:
        print(f"🔍 Processing files in: {folder_path}")
        remove_lyrics_from_folder(folder_path)
