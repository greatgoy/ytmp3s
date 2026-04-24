#!/bin/bash

# ytmp3.sh - Download playlist to All Songs and track which songs belong to it

set -e

BASE_DIR="$HOME/Downloads/YTmp3s"
SCRIPTS_DIR="$BASE_DIR/scripts"
ALL_SONGS_DIR="$BASE_DIR/All Songs"
VENV_PYTHON="$BASE_DIR/venv/bin/python3"
ARCHIVE_FILE="$BASE_DIR/download_archive.txt"

METADATA_SCRIPT="$SCRIPTS_DIR/metadata/repair_metadata.py"
CLEAN_SCRIPT="$SCRIPTS_DIR/metadata/clean_filenames.py"
ALBUM_ART_SCRIPT="$SCRIPTS_DIR/art/fetch_album_art.py"
LYRICS_SCRIPT="$SCRIPTS_DIR/lyrics/fetch_lyrics.py"

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

check_dependency yt-dlp
check_dependency python3

if [ -z "$1" ]; then
    echo "Usage: $0 <YouTube Playlist URL> [--dry-run] [--skip-metadata]"
    exit 1
fi

PLAYLIST_URL="$1"
shift

DRY_RUN=false
SKIP_METADATA=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
    [[ "$arg" == "--skip-metadata" ]] && SKIP_METADATA=true
done

PLAYLIST_TITLE=$(yt-dlp --flat-playlist --print "%(playlist_title)s" "$PLAYLIST_URL" | head -n 1)
SANITIZED_TITLE=$(sanitize_filename "$PLAYLIST_TITLE")
PLAYLIST_FOLDER="$BASE_DIR/all downloaded music/with claude/$SANITIZED_TITLE"

if $DRY_RUN; then
    echo ""
    echo "🔍 Dry run — songs that would be downloaded from: $PLAYLIST_TITLE"
    echo ""
    yt-dlp --flat-playlist --print "  • %(title)s" "$PLAYLIST_URL"
    echo ""
    echo "📁 Playlist folder would be created at:"
    echo "   $PLAYLIST_FOLDER"
    echo ""
    echo "(Nothing downloaded or moved. Run again without dry-run to proceed.)"
    exit 0
fi

mkdir -p "$ALL_SONGS_DIR" "$PLAYLIST_FOLDER"

# Snapshot All Songs before download so we can identify new files afterward
ls "$ALL_SONGS_DIR"/*.mp3 2>/dev/null | xargs -n1 basename > /tmp/ytmp3_before_$$.txt || touch /tmp/ytmp3_before_$$.txt

run_step "Downloading playlist audio as MP3" \
    "yt-dlp -x --audio-format mp3 --embed-metadata \
     --output '$ALL_SONGS_DIR/%(title)s.%(ext)s' \
     --download-archive '$ARCHIVE_FILE' \
     '$PLAYLIST_URL'"

shopt -s nullglob
FILES=("$ALL_SONGS_DIR"/*.mp3)
if [ ${#FILES[@]} -eq 0 ]; then
    echo "✅ No new songs downloaded — everything is already in the archive."
    rm -f /tmp/ytmp3_before_$$.txt
    exit 0
fi

if ! $SKIP_METADATA; then
    run_step "Cleaning filenames"  "$VENV_PYTHON '$CLEAN_SCRIPT' '$ALL_SONGS_DIR'"
    run_step "Repairing metadata"  "$VENV_PYTHON '$METADATA_SCRIPT' '$ALL_SONGS_DIR'"
    run_step "Fetching album art"  "$VENV_PYTHON '$ALBUM_ART_SCRIPT' '$ALL_SONGS_DIR'"
    run_step "Fetching lyrics"     "$VENV_PYTHON '$LYRICS_SCRIPT' '$ALL_SONGS_DIR'"
fi

# Save manifest: records which songs were newly downloaded in this session
export YTMP3_PLAYLIST_TITLE="$PLAYLIST_TITLE"
export YTMP3_PLAYLIST_URL="$PLAYLIST_URL"
export YTMP3_PLAYLIST_FOLDER="$PLAYLIST_FOLDER"
export YTMP3_SANITIZED="$SANITIZED_TITLE"
export YTMP3_BASE="$BASE_DIR"
export YTMP3_ALL_SONGS="$ALL_SONGS_DIR"
export YTMP3_BEFORE_FILE="/tmp/ytmp3_before_$$.txt"

$VENV_PYTHON - <<'PYEOF'
import json, os

before_file = os.environ['YTMP3_BEFORE_FILE']
all_songs_dir = os.environ['YTMP3_ALL_SONGS']
base_dir = os.environ['YTMP3_BASE']
playlist_title = os.environ['YTMP3_PLAYLIST_TITLE']
playlist_url = os.environ['YTMP3_PLAYLIST_URL']
playlist_folder = os.environ['YTMP3_PLAYLIST_FOLDER']
sanitized = os.environ['YTMP3_SANITIZED']

before = set()
if os.path.exists(before_file):
    with open(before_file) as f:
        before = {l.strip() for l in f if l.strip()}

after = set(f for f in os.listdir(all_songs_dir) if f.endswith('.mp3'))
new_songs = sorted(after - before)

playlists_dir = os.path.join(base_dir, 'playlists')
os.makedirs(playlists_dir, exist_ok=True)
manifest = {
    'playlist_name': playlist_title,
    'playlist_url': playlist_url,
    'folder': playlist_folder,
    'songs': new_songs,
}
with open(os.path.join(playlists_dir, f'{sanitized}.json'), 'w') as f:
    json.dump(manifest, f, indent=2)
print(f"📋 Tracked {len(new_songs)} new song(s) for '{playlist_title}'")
PYEOF

rm -f /tmp/ytmp3_before_$$.txt

echo ""
echo "🎉 Download complete! Songs are in All Songs."
echo "   Next: run the full pipeline (option 6), then option s to move them to:"
echo "   $PLAYLIST_FOLDER"
