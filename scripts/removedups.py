
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "sources.json"
OUTPUT_FILE = ROOT / "output" / "combined.m3u"


def load_config():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def discover_playlists(config):
    playlists = []

    for source in config["sources"]:
        if not source.get("enabled", True):
            continue

        folder = (ROOT / source["path"]).resolve()

        if not folder.exists():
            print(f"[WARNING] Source not found: {folder}")
            continue

        extensions = {
            ext.lower() for ext in source["extensions"]
        }

        iterator = (
            folder.rglob("*")
            if source.get("recursive", True)
            else folder.glob("*")
        )

        includes = source.get("include", [])

        for file in iterator:
            if not file.is_file():
                continue

            if file.suffix.lower() not in extensions:
                continue

            if includes and not any(file.match(p) for p in includes):
                continue

            playlists.append({
                "name": source["name"],
                "file": file
            })

    return playlists


def read_entries(playlist):
    entries = []
    current_entry = []

    with playlist["file"].open(
        "r", encoding="utf-8-sig", errors="replace"
    ) as f:

        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith("#EXTM3U"):
                continue

            if line.startswith("#EXTINF"):
                if current_entry:
                    print(
                        f"[WARNING] Incomplete entry in "
                        f"{playlist['file']}: {current_entry[0]}"
                    )

                current_entry = [line]

            elif line.startswith("#"):
                if current_entry:
                    current_entry.append(line)

            elif current_entry:
                current_entry.append(line)

                entries.append({
                    "url": line,
                    "content": current_entry.copy()
                })

                current_entry = []

    return entries


def main():
    config = load_config()
    playlists = discover_playlists(config)

    print(f"Found {len(playlists)} playlists.")

    seen_urls = set()
    combined_entries = []

    total_entries = 0
    duplicates_removed = 0

    for index, playlist in enumerate(playlists, 1):
        print(
            f"[{index}/{len(playlists)}] "
            f"{playlist['name']}: {playlist['file'].name}"
        )

        entries = read_entries(playlist)

        for entry in entries:
            total_entries += 1

            url = entry["url"]

            if url in seen_urls:
                duplicates_removed += 1
                continue

            seen_urls.add(url)
            combined_entries.append(entry["content"])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as f:
        f.write("#EXTM3U\n")

        for entry in combined_entries:
            for line in entry:
                f.write(line + "\n")

    print("\n========== SUMMARY ==========")
    print(f"Playlists processed: {len(playlists)}")
    print(f"Total entries:       {total_entries}")
    print(f"Duplicates removed:  {duplicates_removed}")
    print(f"Unique entries:      {len(combined_entries)}")
    print(f"Output:              {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
