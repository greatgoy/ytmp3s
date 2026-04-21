#!/bin/bash

BASE_DIR=~/Downloads/YTmp3s
ALL_SONGS_DIR="$BASE_DIR/All Songs"
SCRIPTS_DIR="$BASE_DIR/scripts"
YTMP3_SCRIPT="$SCRIPTS_DIR/ytmp3.sh"
PYTHON_ENV="$BASE_DIR/venv/bin/python3"

# Color codes
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
CYAN="\033[0;36m"
NC="\033[0m"

mkdir -p "$ALL_SONGS_DIR" "$BASE_DIR/logs"

# Dependency check
if [[ ! -x "$PYTHON_ENV" ]]; then
    echo -e "${RED}Error: Python virtual environment not found at $PYTHON_ENV${NC}"
    exit 1
fi

for script in \
    "$SCRIPTS_DIR/metadata/audit_metadata.py" \
    "$SCRIPTS_DIR/library/deduplicate_songs.py" \
    "$SCRIPTS_DIR/library/generate_m3u.py" \
    "$SCRIPTS_DIR/metadata/metadata_summary.py" \
    "$SCRIPTS_DIR/metadata/repair_metadata.py" \
    "$SCRIPTS_DIR/metadata/enrich_metadata.py" \
    "$SCRIPTS_DIR/metadata/clean_filenames.py" \
    "$SCRIPTS_DIR/lyrics/fetch_lyrics.py" \
    "$SCRIPTS_DIR/art/fetch_album_art.py" \
    "$SCRIPTS_DIR/lyrics/add_lyric_override.py" \
    "$SCRIPTS_DIR/lyrics/embed_lyrics_manual.py" \
    "$SCRIPTS_DIR/art/add_art_override.py" \
    "$SCRIPTS_DIR/lyrics/remove_lyrics.py" \
    "$SCRIPTS_DIR/metadata/cleanrepair_script.py" \
    "$SCRIPTS_DIR/sync/test_sync_restore.py"
do
    if [[ ! -f "$script" ]]; then
        echo -e "${RED}Error: Missing script: $script${NC}"
        exit 1
    fi
done

# Status summary
status_summary() {
    echo -e "${BLUE}Scanning All Songs for metadata status...${NC}"
    stats=$($PYTHON_ENV - <<EOF
import os
from mutagen.id3 import ID3

all_dir = os.path.expanduser("$ALL_SONGS_DIR")
total, missing_lyrics, missing_art = 0, 0, 0

for f in os.listdir(all_dir):
    if not f.endswith(".mp3"): continue
    total += 1
    path = os.path.join(all_dir, f)
    try:
        tags = ID3(path)
        if not any(t.FrameID == "USLT" for t in tags.values()):
            missing_lyrics += 1
        if not any(t.FrameID == "APIC" for t in tags.values()):
            missing_art += 1
    except:
        missing_lyrics += 1
        missing_art += 1

print(f"{total},{missing_lyrics},{missing_art}")
EOF
)
    IFS=',' read -r total_files missing_lyrics missing_art <<< "$stats"
    echo -e "${CYAN}Total MP3s: ${total_files}${NC}"
    echo -e "${CYAN}Missing Lyrics: ${missing_lyrics}${NC}"
    echo -e "${CYAN}Missing Album Art: ${missing_art}${NC}"

    # Show Genius retry queue size if non-empty
    queue_file="$BASE_DIR/genius_retry_queue.json"
    if [[ -f "$queue_file" ]]; then
        queue_count=$($PYTHON_ENV -c "import json; q=json.load(open('$queue_file')); print(len(q))" 2>/dev/null)
        if [[ "$queue_count" -gt 0 ]]; then
            echo -e "${YELLOW}Genius retry queue: ${queue_count} song(s) waiting${NC}"
        fi
    fi
    echo ""
}

# Menu
show_menu() {
    echo -e "${YELLOW}YTMP3 MENU:${NC}"
    echo -e "${RED}e)${NC} Exit"
    echo -e "${GREEN}1)${NC} Download playlist              ${CYAN}(with dry-run confirmation)${NC}"
    echo -e "${GREEN}2)${NC} Audit metadata                 ${CYAN}(full log to file)${NC}"
    echo -e "${GREEN}3)${NC} Deduplicate songs              ${CYAN}(logs deletions)${NC}"
    echo -e "${GREEN}4)${NC} Generate M3U playlist          ${CYAN}(with full paths)${NC}"
    echo -e "${GREEN}5)${NC} Create metadata summary        ${CYAN}(exports as CSV)${NC}"
    echo -e "${GREEN}6)${NC} Run full pipeline              ${CYAN}(clean filenames → lyrics → art → metadata)${NC}"
    echo -e "${GREEN}7)${NC} Clean filenames in All Songs"
    echo -e "${GREEN}8)${NC} Fetch Lyrics in All Songs"
    echo -e "${GREEN}9)${NC} Fetch Album Art in All Songs"
    echo -e "${GREEN}─────────────────────────────────────────────────────${NC}"
    echo -e "${GREEN}f)${NC} Show songs missing lyrics      ${CYAN}(show after running '6' or '8')${NC}"
    echo -e "${GREEN}g)${NC} Show songs missing album art   ${CYAN}(show after running '6' or '9')${NC}"
    echo -e "${GREEN}p)${NC} Show songs missing metadata    ${CYAN}(year, writers, track #, producers)${NC}"
    echo -e "${GREEN}─────────────────────────────────────────────────────${NC}"
    echo -e "${GREEN}a)${NC} Add lyric override             ${CYAN}(saves to lyrics_overrides.json; rerun '8' in menu after)${NC}"
    echo -e "${GREEN}m)${NC} Manually embed lyrics          ${CYAN}(paste lyrics directly into a specific song)${NC}"
    echo -e "${GREEN}i)${NC} Add album art override         ${CYAN}(saves to art_overrides.json; rerun '9' in menu after)${NC}"
    echo -e "${GREEN}r)${NC} Retry lyrics with Genius       ${CYAN}(for rate-limited songs)${NC}"
    echo -e "${GREEN}n)${NC} Enrich metadata from Genius      ${CYAN}(release date, track #, writers, producers, engineers, samples, tags...)${NC}"
    echo -e "${GREEN}─────────────────────────────────────────────────────${NC}"
    echo -e "${GREEN}b)${NC} Remove lyrics from All Songs"
    echo -e "${GREEN}c)${NC} Clean + repair specific songs  ${CYAN}(keyword match on filenames)${NC}"
    echo -e "${GREEN}d)${NC} Test sync/restore              ${CYAN}(interactive, single file)${NC}"
    echo -e "${CYAN}h) Help${NC}"
}

# Help
show_help() {
    echo -e "${BLUE}Help - Option Descriptions:${NC}"
    echo -e "1: Downloads a playlist. Prompts for dry-run or real run."
    echo -e "2: Full metadata audit — writes timestamped log to logs/."
    echo -e "3: Removes duplicate MP3s. Logs deleted files."
    echo -e "4: Builds an M3U playlist with full file paths."
    echo -e "5: Exports a CSV summary of all embedded metadata."
    echo -e "6: Full post-download pipeline — clean filenames, fetch lyrics (+ Genius metadata), fetch album art, enrich metadata (MusicBrainz/iTunes fallbacks)."
    echo -e "7: Cleans up messy MP3 filenames."
    echo -e "8: Embeds missing lyrics — tries Genius, then songlyrics.com, then lyrics.ovh."
    echo -e "9: Embeds album art from iTunes (or override URLs)."
    echo -e "f: Lists every song currently missing embedded lyrics."
    echo -e "g: Lists every song currently missing embedded album art."
    echo -e "p: Lists every song missing key metadata fields (year, writers, track #, producers)."
    echo -e "a: Add a lyric source override (saves to lyrics_overrides.json)."
    echo -e "m: Manually paste lyrics into a specific song. Browse or search by filename, paste lyrics, confirm to embed."
    echo -e "i: Add an album art override URL (saves to art_overrides.json)."
    echo -e "n: Enrich metadata from Genius API — embeds release year, track #, writers, producers, engineers, samples, covers, remixes, and tags. Skips fields already filled. Add --overwrite to replace existing values."
    echo -e "r: Retry Genius API for songs that hit the rate limit during a previous run."
    echo -e "b: Strips all embedded lyrics from every MP3 in All Songs."
    echo -e "c: Manually clean + repair metadata for specific songs by filename keyword."
    echo -e "d: Interactive test to backup/clear/restore tags on a single file."
    echo -e "e: Exit."
    echo ""
}

# Loop
while true; do
    echo ""
    status_summary
    show_menu
    echo ""
    read -p "Choose an option: " choice
    case "$choice" in
        1)
            read -p "Paste playlist URL: " url
            read -p "Dry run first? (y/n): " dryrun
            read -p "Skip embedding metadata? (y/n): " skip_meta
            MODE=""
            [[ "$dryrun" == "y" ]] && MODE+="--dry-run "
            [[ "$skip_meta" == "y" ]] && MODE+="--skip-metadata"
            bash "$YTMP3_SCRIPT" "$url" $MODE
            ;;
        2) $PYTHON_ENV "$SCRIPTS_DIR/metadata/audit_metadata.py" ;;
        3)
            read -p "Dry run? (y/n): " dry
            if [[ "$dry" == "y" ]]; then
                $PYTHON_ENV "$SCRIPTS_DIR/library/deduplicate_songs.py" --dry-run
            else
                $PYTHON_ENV "$SCRIPTS_DIR/library/deduplicate_songs.py"
            fi
            ;;
        4) $PYTHON_ENV "$SCRIPTS_DIR/library/generate_m3u.py" ;;
        5) $PYTHON_ENV "$SCRIPTS_DIR/metadata/metadata_summary.py" ;;
        6)
            echo -e "${BLUE}Running full pipeline on All Songs...${NC}"
            echo -e "${CYAN}Step 1/4: Cleaning filenames${NC}"
            $PYTHON_ENV "$SCRIPTS_DIR/metadata/clean_filenames.py"
            echo -e "${CYAN}Step 2/4: Fetching lyrics (+ Genius metadata)${NC}"
            $PYTHON_ENV "$SCRIPTS_DIR/lyrics/fetch_lyrics.py" "$ALL_SONGS_DIR"
            echo -e "${CYAN}Step 3/4: Fetching album art${NC}"
            $PYTHON_ENV "$SCRIPTS_DIR/art/fetch_album_art.py" "$ALL_SONGS_DIR"
            echo -e "${CYAN}Step 4/4: Enriching metadata (MusicBrainz/iTunes fallbacks)${NC}"
            $PYTHON_ENV "$SCRIPTS_DIR/metadata/enrich_metadata.py" "$ALL_SONGS_DIR"
            echo -e "${GREEN}✅ Pipeline complete.${NC}"
            ;;
        7) $PYTHON_ENV "$SCRIPTS_DIR/metadata/clean_filenames.py" ;;
        8) $PYTHON_ENV "$SCRIPTS_DIR/lyrics/fetch_lyrics.py" "$ALL_SONGS_DIR" ;;
        9) $PYTHON_ENV "$SCRIPTS_DIR/art/fetch_album_art.py" "$ALL_SONGS_DIR" ;;
        f|F)
            echo ""
            $PYTHON_ENV - <<EOF
import os
from mutagen.id3 import ID3
folder = os.path.expanduser("$ALL_SONGS_DIR")
missing = []
for f in sorted(os.listdir(folder)):
    if not f.endswith(".mp3"): continue
    try:
        tags = ID3(os.path.join(folder, f))
        if not any(t.FrameID == "USLT" for t in tags.values()):
            missing.append(f)
    except:
        missing.append(f)
if missing:
    print(f"❌ {len(missing)} song(s) missing lyrics:")
    for s in missing: print(f"  • {s}")
else:
    print("✅ All songs have lyrics!")
EOF
            ;;
        g|G)
            echo ""
            $PYTHON_ENV - <<EOF
import os
from mutagen.id3 import ID3
folder = os.path.expanduser("$ALL_SONGS_DIR")
missing = []
for f in sorted(os.listdir(folder)):
    if not f.endswith(".mp3"): continue
    try:
        tags = ID3(os.path.join(folder, f))
        if not any(t.FrameID == "APIC" for t in tags.values()):
            missing.append(f)
    except:
        missing.append(f)
if missing:
    print(f"❌ {len(missing)} song(s) missing album art:")
    for s in missing: print(f"  • {s}")
else:
    print("✅ All songs have album art!")
EOF
            ;;
        p|P)
            echo ""
            $PYTHON_ENV - <<EOF
import os
from mutagen.id3 import ID3
folder = os.path.expanduser("$ALL_SONGS_DIR")
results = []
for f in sorted(os.listdir(folder)):
    if not f.endswith(".mp3"): continue
    missing = []
    try:
        tags = ID3(os.path.join(folder, f))
        if not tags.get("TYER") and not tags.get("TDRC"):
            missing.append("year")
        if not tags.get("TCOM"):
            missing.append("writers")
        if not tags.get("TRCK"):
            missing.append("track#")
        if not tags.get("TXXX:Producers"):
            missing.append("producers")
    except:
        missing = ["year", "writers", "track#", "producers"]
    if missing:
        results.append((f, missing))
if results:
    print(f"❌ {len(results)} song(s) with incomplete metadata:")
    for name, fields in results:
        print(f"  • {name}  [{', '.join(fields)}]")
else:
    print("✅ All songs have complete metadata!")
EOF
            ;;
        a|A) $PYTHON_ENV "$SCRIPTS_DIR/lyrics/add_lyric_override.py" ;;
        m|M) $PYTHON_ENV "$SCRIPTS_DIR/lyrics/embed_lyrics_manual.py" ;;
        i|I) $PYTHON_ENV "$SCRIPTS_DIR/art/add_art_override.py" ;;
        r|R) $PYTHON_ENV "$SCRIPTS_DIR/lyrics/fetch_lyrics.py" --retry-genius ;;
        n|N) $PYTHON_ENV "$SCRIPTS_DIR/metadata/enrich_metadata.py" "$ALL_SONGS_DIR" ;;
        b|B) $PYTHON_ENV "$SCRIPTS_DIR/lyrics/remove_lyrics.py" "$ALL_SONGS_DIR" ;;
        c|C) $PYTHON_ENV "$SCRIPTS_DIR/metadata/cleanrepair_script.py" "$ALL_SONGS_DIR" ;;
        d|D) $PYTHON_ENV "$SCRIPTS_DIR/sync/test_sync_restore.py" ;;
        h|H) show_help ;;
        e|E) echo -e "${GREEN}Goodbye!${NC}"; exit 0 ;;
        *) echo -e "${RED}Invalid option. Try again.${NC}" ;;
    esac
done
