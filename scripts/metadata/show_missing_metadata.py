#!/usr/bin/env python3
"""Show songs missing metadata fields, grouped by importance tier."""
import os
import sys
from mutagen.id3 import ID3

BASE_DIR = os.path.expanduser("~/Downloads/YTmp3s")
ALL_SONGS_DIR = os.path.join(BASE_DIR, "All Songs")

# Each tier: field_label → (frame_keys_to_check, skip_for_instrumentals)
# "require_any": song passes the tier if at least one of these field names is present.
#   Other fields in the tier are still shown as missing but don't count against completion.
TIERS = {
    "core": {
        "label": "Core  (year, track #, genre)",
        "fields": {
            "year":    (["TYER", "TDRC"], False),
            "track #": (["TRCK"],         False),
            "genre":   (["TCON"],         False),
        },
    },
    "credits": {
        "label": "Credits  (writers, producers, featured, label)",
        "require_any": ["writers", "producers"],
        "fields": {
            "writers":   (["TCOM"],                   True),   # skip for instrumentals
            "producers": (["TXXX:Producers"],         False),
            "featured":  (["TXXX:Featured Artists"],  True),
            "label":     (["TPUB"],                   False),
        },
    },
    "relationships": {
        "label": "Relationships  (samples, covers, remixes)",
        "fields": {
            "samples":    (["TXXX:Samples", "TXXX:Sampled By"],       False),
            "covers":     (["TXXX:Cover Of", "TXXX:Covered By"],      False),
            "remixes":    (["TXXX:Remix Of", "TXXX:Remixed By"],      False),
            "interpols.": (["TXXX:Interpolates", "TXXX:Interpolated By"], False),
        },
    },
}


def _any_present(tags, keys):
    return any(tags.get(k) for k in keys)


def check_songs(folder, tier_keys):
    results = []
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".mp3"):
            continue
        path = os.path.join(folder, f)
        missing = []
        try:
            tags = ID3(path)
            is_instrumental = bool(tags.get("TXXX:Instrumental"))
            for tk in tier_keys:
                tier = TIERS[tk]
                require_any = tier.get("require_any", [])

                if require_any:
                    # Applicable = require_any fields that aren't skipped for this song
                    applicable = [
                        fn for fn in require_any
                        if not (tier["fields"][fn][1] and is_instrumental)
                    ]
                    satisfied = not applicable or any(
                        _any_present(tags, tier["fields"][fn][0]) for fn in applicable
                    )
                    if not satisfied:
                        for field_label, (frame_keys, skip_instr) in tier["fields"].items():
                            if skip_instr and is_instrumental:
                                continue
                            if not _any_present(tags, frame_keys):
                                missing.append(field_label)
                else:
                    for field_label, (frame_keys, skip_instr) in tier["fields"].items():
                        if skip_instr and is_instrumental:
                            continue
                        if not _any_present(tags, frame_keys):
                            missing.append(field_label)
        except Exception:
            missing = [fl for tk in tier_keys for fl in TIERS[tk]["fields"]]
        if missing:
            results.append((f, missing))
    return results


def main():
    folder = ALL_SONGS_DIR
    if len(sys.argv) > 1:
        folder = sys.argv[1]

    all_mp3s = [f for f in os.listdir(folder) if f.endswith(".mp3")]

    print("\n=== Show Songs Missing Metadata ===")
    print("Tiers reflect what's realistically available from our metadata sources.")
    print()
    for key, tier in TIERS.items():
        print(f"  {list(TIERS).index(key) + 1}) {tier['label']}")
    print(f"  4) All tiers")
    print()
    choice = input("Choose (or Enter to cancel): ").strip()

    tier_map = {
        "1": ["core"],
        "2": ["credits"],
        "3": ["relationships"],
        "4": list(TIERS.keys()),
    }
    if choice not in tier_map:
        print("Cancelled.")
        return

    tier_keys = tier_map[choice]
    results = check_songs(folder, tier_keys)

    tier_labels = " + ".join(TIERS[k]["label"].split("(")[0].strip() for k in tier_keys)
    print(f"\n── {tier_labels} ──")

    if not results:
        print("✅ All songs have complete metadata for the selected tier(s)!")
        return

    print(f"❌ {len(results)}/{len(all_mp3s)} song(s) with incomplete metadata:\n")
    for name, fields in results:
        print(f"  • {name}")
        print(f"    missing: {', '.join(fields)}")

    complete = len(all_mp3s) - len(results)
    print(f"\n  {complete}/{len(all_mp3s)} songs complete  ({len(results)} need attention)")

    if tier_keys == ["core"]:
        print("\n  💡 Core fields come from Genius, MusicBrainz, and iTunes.")
        print("     Run option n to retry enrichment for songs still missing these.")
    elif "credits" in tier_keys:
        print("\n  💡 A song passes Credits if it has writers OR producers.")
        print("     Featured artists and label are shown when missing but don't count against you.")
        print("     Run option n to pull writer credits from Genius + MusicBrainz.")
    if "relationships" in tier_keys:
        print("\n  💡 Relationships (samples/covers/remixes) are Genius-only and only")
        print("     exist when Genius editors have documented them — not always available.")


if __name__ == "__main__":
    main()
