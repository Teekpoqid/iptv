
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "sources.json"
REPORT_FILE = ROOT / "output" / "analysis-report.json"


def load_config():
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def discover_playlists(config):
    playlists = []

    for source in config["sources"]:
        if not source.get("enabled", True):
            continue

        source_path = (ROOT / source["path"]).resolve()
        extensions = {ext.lower() for ext in source["extensions"]}

        if not source_path.exists():
            print(f"[WARNING] Source not found: {source_path}")
            continue

        iterator = (
            source_path.rglob("*")
            if source.get("recursive", True)
            else source_path.glob("*")
        )

        includes = source.get("include", [])

        for file in iterator:
            if not file.is_file():
                continue

            if file.suffix.lower() not in extensions:
                continue

            if includes and not any(file.match(pattern) for pattern in includes):
                continue

            playlists.append({
                "source": source["name"],
                "priority": source.get("priority", 999),
                "file": file
            })

    return playlists


def normalize_url(url):
    """Normalize URLs without removing meaningful query parameters."""
    try:
        parts = urlsplit(url.strip())

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            parts.query,
            ""
        ))
    except ValueError:
        return url.strip()


def parse_attributes(line):
    attributes = {}

    pattern = r'([\w-]+)="([^"]*)"'

    for key, value in re.findall(pattern, line):
        attributes[key.lower()] = value

    return attributes


def analyze_playlist(playlist):
    file = playlist["file"]

    stats = {
        "source": playlist["source"],
        "file": str(file.relative_to(ROOT.parent)),
        "channels": 0,
        "missing_tvg_id": 0,
        "missing_tvg_name": 0,
        "duplicate_ids": 0,
        "duplicate_urls": 0
    }

    channel_ids = Counter()
    stream_urls = Counter()

    current_entry = None

    try:
        with file.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()

                if not line:
                    continue

                if line.startswith("#EXTINF"):
                    current_entry = parse_attributes(line)

                    stats["channels"] += 1

                    if not current_entry.get("tvg-id"):
                        stats["missing_tvg_id"] += 1
                    else:
                        channel_ids[current_entry["tvg-id"]] += 1

                    if not current_entry.get("tvg-name"):
                        stats["missing_tvg_name"] += 1

                elif not line.startswith("#") and current_entry is not None:
                    stream_urls[normalize_url(line)] += 1
                    current_entry = None

    except OSError as error:
        print(f"[ERROR] {file}: {error}")

    stats["duplicate_ids"] = sum(
        count - 1 for count in channel_ids.values() if count > 1
    )

    stats["duplicate_urls"] = sum(
        count - 1 for count in stream_urls.values() if count > 1
    )

    return stats


def main():
    config = load_config()

    print("\nDiscovering playlists...\n")

    playlists = discover_playlists(config)

    print(f"Discovered {len(playlists)} playlists.\n")

    results = []

    for index, playlist in enumerate(playlists, start=1):
        print(
            f"[{index}/{len(playlists)}] "
            f"{playlist['source']}: {playlist['file'].name}"
        )

        results.append(analyze_playlist(playlist))

    totals = Counter()

    for result in results:
        for key in (
            "channels",
            "missing_tvg_id",
            "missing_tvg_name",
            "duplicate_ids",
            "duplicate_urls"
        ):
            totals[key] += result[key]

    report = {
        "playlist_count": len(playlists),
        "totals": dict(totals),
        "playlists": results
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with REPORT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    print("\n========== SUMMARY ==========")
    print(f"Playlists:       {len(playlists)}")
    print(f"Channels:        {totals['channels']}")
    print(f"Missing tvg-id:  {totals['missing_tvg_id']}")
    print(f"Missing tvg-name:{totals['missing_tvg_name']}")
    print(f"Duplicate IDs:   {totals['duplicate_ids']}")
    print(f"Duplicate URLs:  {totals['duplicate_urls']}")

    print(f"\nReport saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
