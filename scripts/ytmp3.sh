#!/bin/bash

# ytmp3.sh - Download playlist to All Songs; track songs and detect failures

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

# Fetch full playlist video list (id + title) for failure detection later
PLAYLIST_TSV="/tmp/ytmp3_playlist_$$.tsv"
echo "📋 Scanning playlist: $PLAYLIST_TITLE"
yt-dlp --flat-playlist --print "%(id)s	%(title)s" "$PLAYLIST_URL" > "$PLAYLIST_TSV" 2>/dev/null
PLAYLIST_TOTAL=$(wc -l < "$PLAYLIST_TSV" | tr -d ' ')
echo "   $PLAYLIST_TOTAL video(s) in playlist"

# Snapshot All Songs before download to identify new files afterward
BEFORE_FILE="/tmp/ytmp3_before_$$.txt"
ls "$ALL_SONGS_DIR"/*.mp3 2>/dev/null | xargs -n1 basename > "$BEFORE_FILE" || touch "$BEFORE_FILE"

run_step "Downloading playlist audio as MP3" \
    "yt-dlp -x --audio-format mp3 --embed-metadata \
     --output '$ALL_SONGS_DIR/%(title)s.%(ext)s' \
     --download-archive '$ARCHIVE_FILE' \
     --no-abort-on-error \
     '$PLAYLIST_URL'"

shopt -s nullglob
FILES=("$ALL_SONGS_DIR"/*.mp3)
if [ ${#FILES[@]} -eq 0 ]; then
    echo "✅ No new songs downloaded — everything is already in the archive."
    rm -f "$BEFORE_FILE" "$PLAYLIST_TSV"
    exit 0
fi

if ! $SKIP_METADATA; then
    run_step "Cleaning filenames"  "$VENV_PYTHON '$CLEAN_SCRIPT' '$ALL_SONGS_DIR'"
    run_step "Repairing metadata"  "$VENV_PYTHON '$METADATA_SCRIPT' '$ALL_SONGS_DIR'"
    run_step "Fetching album art"  "$VENV_PYTHON '$ALBUM_ART_SCRIPT' '$ALL_SONGS_DIR'"
    run_step "Fetching lyrics"     "$VENV_PYTHON '$LYRICS_SCRIPT' '$ALL_SONGS_DIR'"
fi

# Save manifest and detect failures
export YTMP3_PLAYLIST_TITLE="$PLAYLIST_TITLE"
export YTMP3_PLAYLIST_URL="$PLAYLIST_URL"
export YTMP3_PLAYLIST_FOLDER="$PLAYLIST_FOLDER"
export YTMP3_SANITIZED="$SANITIZED_TITLE"
export YTMP3_BASE="$BASE_DIR"
export YTMP3_ALL_SONGS="$ALL_SONGS_DIR"
export YTMP3_BEFORE_FILE="$BEFORE_FILE"
export YTMP3_PLAYLIST_TSV="$PLAYLIST_TSV"
export YTMP3_ARCHIVE="$ARCHIVE_FILE"

$VENV_PYTHON - <<'PYEOF'
import json, os

base_dir      = os.environ['YTMP3_BASE']
all_songs_dir = os.environ['YTMP3_ALL_SONGS']
before_file   = os.environ['YTMP3_BEFORE_FILE']
playlist_tsv  = os.environ['YTMP3_PLAYLIST_TSV']
archive_file  = os.environ['YTMP3_ARCHIVE']
playlist_title  = os.environ['YTMP3_PLAYLIST_TITLE']
playlist_url    = os.environ['YTMP3_PLAYLIST_URL']
playlist_folder = os.environ['YTMP3_PLAYLIST_FOLDER']
sanitized       = os.environ['YTMP3_SANITIZED']

# ── Manifest: which files are new ─────────────────────────────────────────────
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
    'playlist_url':  playlist_url,
    'folder':        playlist_folder,
    'songs':         new_songs,
}
with open(os.path.join(playlists_dir, f'{sanitized}.json'), 'w') as f:
    json.dump(manifest, f, indent=2)
print(f"📋 Tracked {len(new_songs)} new song(s) for '{playlist_title}'")

# ── Failure detection: playlist videos not found in archive ───────────────────
archive_ids = set()
if os.path.exists(archive_file):
    with open(archive_file) as f:
        for line in f:
            parts = line.strip().split(' ', 1)
            if len(parts) == 2:
                archive_ids.add(parts[1])

failed = []
total  = 0
with open(playlist_tsv) as f:
    for line in f:
        line = line.strip()
        if '\t' not in line:
            continue
        vid_id, title = line.split('\t', 1)
        total += 1
        if vid_id not in archive_ids:
            failed.append({
                'id':    vid_id,
                'title': title,
                'url':   f'https://www.youtube.com/watch?v={vid_id}',
            })

if failed:
    failed_path = os.path.join(playlists_dir, f'{sanitized}_failed.json')
    with open(failed_path, 'w') as f:
        json.dump({'playlist_name': playlist_title,
                   'playlist_url':  playlist_url,
                   'failed':        failed}, f, indent=2)
    print(f"\n⚠️  {len(failed)}/{total} song(s) failed to download:")
    for entry in failed:
        print(f"   • {entry['title']}")
    print(f"\n   Run option t to view details and retry.")
else:
    print(f"✅ All {total} song(s) downloaded successfully")
PYEOF

rm -f "$BEFORE_FILE" "$PLAYLIST_TSV"

echo ""
echo "🎉 Download complete! Songs are in All Songs."
echo "   Next: run the full pipeline (option 6), then option s to move them to:"
echo "   $PLAYLIST_FOLDER"
