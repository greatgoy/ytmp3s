import eyed3
import os
import shutil

backup_data = {}

def backup_tags(audio):
    global backup_data
    print("🧪 Backing up lyrics, images, and metadata...")

    backup_data = {
        "lyrics": [(lyr.lang, lyr.text) for lyr in audio.tag.lyrics] if audio.tag.lyrics else [],
        "images": list(audio.tag.images) if audio.tag.images else [],
        "title": audio.tag.title,
        "artist": audio.tag.artist,
        "album": audio.tag.album
    }
    print("✅ Backup complete.")

def restore_tags(audio):
    global backup_data
    print("🔁 Restoring all backed-up info...")
    audio.tag.clear()

    audio.tag.title = backup_data["title"]
    audio.tag.artist = backup_data["artist"]
    audio.tag.album = backup_data["album"]

    for lang, text in backup_data["lyrics"]:
        audio.tag.lyrics.set(text, lang=lang)

    for image in backup_data["images"]:
        audio.tag.images.set(image.picture_type, image.image_data, image.mime_type)

    audio.tag.save(version=(2, 3, 0))
    print("✅ All restored.")

def clear_lyrics(audio):
    print("➡️ Removing lyrics...")
    audio.tag.lyrics.set("")
    audio.tag.save(version=(2, 3, 0))
    print("✅ Lyrics removed.")

def clear_album_art(audio):
    print("➡️ Removing album art...")
    audio.tag.images.remove("")
    audio.tag.save(version=(2, 3, 0))
    print("✅ Album art removed.")

def clear_all_metadata(audio):
    print("⚠️ Rebuilding tag with only basic metadata...")
    old_title = audio.tag.title or "Unknown Title"
    old_artist = audio.tag.artist or "Unknown Artist"
    old_album = audio.tag.album or "Unknown Album"

    audio.tag.clear()
    audio.tag.title = old_title
    audio.tag.artist = old_artist
    audio.tag.album = old_album
    audio.tag.save(version=(2, 3, 0))
    print("✅ Cleared extra metadata.")

def load_audio(file_path):
    if not file_path.endswith(".mp3"):
        print("🚫 Not an MP3 file.")
        return None
    audio = eyed3.load(file_path)
    if not audio:
        print("🚫 Could not load audio.")
    elif audio.tag is None:
        audio.initTag(version=(2, 3, 0))
    return audio

def main():
    file_path = input("🎵 Enter path to the MP3 file: ").strip()

    if not os.path.exists(file_path):
        print("🚫 File does not exist.")
        return

    # Create backup copy
    backup_path = file_path.replace(".mp3", "_backup.mp3")
    shutil.copy2(file_path, backup_path)
    print(f"🧩 Backup copy saved as: {os.path.basename(backup_path)}")

    audio = load_audio(file_path)
    if not audio:
        return

    print(f"\n🔍 Loaded: {os.path.basename(file_path)}")
    backup_tags(audio)

    input("\n1️⃣ Step 1: Press Enter to remove lyrics...")
    clear_lyrics(audio)

    input("🔁 Try syncing. Press Enter to remove album art...")
    clear_album_art(audio)

    input("🔁 Try syncing again. Press Enter to remove extra metadata...")
    clear_all_metadata(audio)

    input("\n🔙 Press Enter to restore all original tags...")
    restore_tags(audio)

    print("\n🎯 Test finished. You can now compare sync behavior.")

if __name__ == "__main__":
    main()

