#!/bin/bash

# ytmp3.sh - Download directly into All Songs and copy to playlist folder

set -e

# ===== CONFIGURATION =====
BASE_DIR="$HOME/Downloads/YTmp3s"
SCRIPTS_DIR="$BASE_DIR/scripts"
ALL_SONGS_DIR="$BASE_DIR/All Songs"
VENV_PYTHON="$BASE_DIR/venv/bin/python3"
ARCHIVE_FILE="$BASE_DIR/download_archive.txt"

METADATA_SCRIPT="$SCRIPTS_DIR/metadata/repair_metadata.py"
CLEAN_SCRIPT="$SCRIPTS_DIR/metadata/clean_filenames.py"
ALBUM_ART_SCRIPT="$SCRIPTS_DIR/art/fetch_album_art.py"
LYRICS_SCRIPT="$SCRIPTS_DIR/lyrics/fetch_lyrics.py"

# ===== FUNCTIONS =====
function check_dependency() {
    command -v "$1" >/dev/null 2>&1 || { echo >&2 "❌ $1 is not installed. Aborting."; exit 1; }
}

function run_step() {
    local description="$1"
    local command="$2"
    echo "➡️  $description..."
    eval "$command"
    echo "✅ Done: $description"
}

function sanitize_filename() {
    echo "$1" | sed -e 's/[^A-Za-z0-9._ -]/_/g'
}

# ===== CHECK DEPENDENCIES =====
check_dependency yt-dlp
check_dependency python3

# ===== INPUT VALIDATION =====
if [ -z "$1" ]; then
    echo "Usage: $0 <YouTube Playlist URL>"
    exit 1
fi

PLAYLIST_URL="$1"

# ===== GET PLAYLIST TITLE =====
PLAYLIST_TITLE=$(yt-dlp --flat-playlist --print "%(playlist_title)s" "$PLAYLIST_URL" | head -n 1)
SANITIZED_TITLE=$(sanitize_filename "$PLAYLIST_TITLE")
PLAYLIST_FOLDER="$BASE_DIR/$SANITIZED_TITLE"
mkdir -p "$ALL_SONGS_DIR" "$PLAYLIST_FOLDER"

# ===== DOWNLOAD =====
run_step "Downloading playlist audio as MP3" \
    "yt-dlp -x --audio-format mp3 --embed-metadata --output '$ALL_SONGS_DIR/%(title)s.%(ext)s' --download-archive '$ARCHIVE_FILE' '$PLAYLIST_URL'"

shopt -s nullglob
FILES=("$ALL_SONGS_DIR"/*.mp3)
if [ ${#FILES[@]} -eq 0 ]; then
    echo "✅ No new songs to download. Everything is already processed."
    exit 0
fi

# ===== POST-PROCESSING =====
run_step "Cleaning filenames"      "$VENV_PYTHON '$CLEAN_SCRIPT'"
run_step "Repairing metadata"      "$VENV_PYTHON '$METADATA_SCRIPT' '$ALL_SONGS_DIR'"
run_step "Fetching album art"      "$VENV_PYTHON '$ALBUM_ART_SCRIPT' '$ALL_SONGS_DIR'"
run_step "Fetching lyrics"         "$VENV_PYTHON '$LYRICS_SCRIPT' '$ALL_SONGS_DIR'"

# ===== COPY TO PLAYLIST FOLDER =====
echo "➡️  Copying songs to playlist folder: $SANITIZED_TITLE"
for file in "$ALL_SONGS_DIR"/*.mp3; do
    [ -f "$file" ] || continue
    filename=$(basename "$file")
    playlist_path="$PLAYLIST_FOLDER/$filename"
    if [ ! -f "$playlist_path" ]; then
        cp "$file" "$playlist_path"
    fi
done
echo "✅ Done: Songs copied to $PLAYLIST_FOLDER"
echo "🎉 All done! MP3s are in: $ALL_SONGS_DIR and $PLAYLIST_FOLDER"
