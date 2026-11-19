
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
OUTPUT = ROOT / "output"

ATTRIBUTE_PATTERN = re.compile(r'([\w-]+)="([^"]*)"')


def load_config():
    with CONFIG.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_url(url):
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


def parse_entry(line):
    metadata, separator, name = line.partition(",")

    attributes = {
        key.lower(): value
        for key, value in ATTRIBUTE_PATTERN.findall(metadata)
    }

    return {
        "tvg_id": attributes.get("tvg-id", ""),
        "tvg_name": attributes.get("tvg-name", ""),
        "name": name.strip() if separator else "",
        "country": attributes.get("tvg-country", ""),
        "group": attributes.get("group-title", ""),
        "logo": attributes.get("tvg-logo", "")
    }


def discover_sources(config):
    playlists = []

    for source in config["sources"]:
        if not source.get("enabled", True):
            continue

        folder = (ROOT / source["path"]).resolve()

        if not folder.exists():
            print(f"[WARNING] Missing source: {folder}")
            continue

        extensions = {x.lower() for x in source["extensions"]}

        iterator = (
            folder.rglob("*")
            if source.get("recursive", True)
            else folder.glob("*")
        )

        for file in iterator:
            if not file.is_file() or file.suffix.lower() not in extensions:
                continue

            includes = source.get("include", [])

            if includes and not any(file.match(p) for p in includes):
                continue

            playlists.append({
                "source": source["name"],
                "priority": source.get("priority", 999),
                "file": file
            })

    return playlists


def read_playlist(source):
    entries = []
    current = None

    try:
        with source["file"].open(
            "r", encoding="utf-8-sig", errors="replace"
        ) as f:

            for raw in f:
                line = raw.strip()

                if not line:
                    continue

                if line.startswith("#EXTINF"):
                    current = parse_entry(line)

                elif not line.startswith("#") and current is not None:
                    current.update({
                        "url": line,
                        "normalized_url": normalize_url(line),
                        "source": source["source"],
                        "priority": source["priority"],
                        "playlist": str(
                            source["file"].relative_to(ROOT.parent)
                        )
                    })

                    entries.append(current)
                    current = None

    except OSError as error:
        print(f"[ERROR] {source['file']}: {error}")

    return entries


def main():
    config = load_config()
    sources = discover_sources(config)

    all_entries = []

    print(f"\nFound {len(sources)} playlists.\n")

    for index, source in enumerate(sources, 1):
        print(
            f"[{index}/{len(sources)}] "
            f"{source['source']}: {source['file'].name}"
        )

        all_entries.extend(read_playlist(source))

    print(f"\nTotal parsed entries: {len(all_entries)}")

    by_id = defaultdict(list)
    by_url = defaultdict(list)

    for entry in all_entries:
        if entry["tvg_id"]:
            by_id[entry["tvg_id"]].append(entry)

        if entry["normalized_url"]:
            by_url[entry["normalized_url"]].append(entry)

    duplicate_ids = {
        key: entries
        for key, entries in by_id.items()
        if len(entries) > 1
    }

    duplicate_urls = {
        key: entries
        for key, entries in by_url.items()
        if len(entries) > 1
    }

    report_rows = []

    for tvg_id, entries in duplicate_ids.items():
        unique_urls = {
            entry["normalized_url"] for entry in entries
        }

        for entry in entries:
            report_rows.append({
                "duplicate_type": "TVG_ID",
                "duplicate_key": tvg_id,
                "unique_streams": len(unique_urls),
                **entry
            })

    for url, entries in duplicate_urls.items():
        for entry in entries:
            report_rows.append({
                "duplicate_type": "URL",
                "duplicate_key": url,
                "unique_streams": 1,
                **entry
            })

    OUTPUT.mkdir(parents=True, exist_ok=True)

    csv_file = OUTPUT / "global-duplicates.csv"

    fields = [
        "duplicate_type",
        "duplicate_key",
        "unique_streams",
        "tvg_id",
        "tvg_name",
        "name",
        "country",
        "group",
        "source",
        "priority",
        "playlist",
        "url"
    ]

    with csv_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in report_rows:
            writer.writerow({
                key: row.get(key, "")
                for key in fields
            })

    summary = {
        "total_entries": len(all_entries),
        "unique_tvg_ids": len(by_id),
        "missing_tvg_id": sum(
            not entry["tvg_id"] for entry in all_entries
        ),
        "missing_tvg_name_attribute": sum(
            not entry["tvg_name"] for entry in all_entries
        ),
        "missing_display_name": sum(
            not entry["name"] for entry in all_entries
        ),
        "duplicate_id_groups": len(duplicate_ids),
        "duplicate_id_entries": sum(
            len(v) for v in duplicate_ids.values()
        ),
        "duplicate_id_extra_entries": sum(
            len(v) - 1 for v in duplicate_ids.values()
        ),
        "duplicate_ids_with_multiple_streams": sum(
            len({e["normalized_url"] for e in v}) > 1
            for v in duplicate_ids.values()
        ),
        "duplicate_url_groups": len(duplicate_urls),
        "duplicate_url_entries": sum(
            len(v) for v in duplicate_urls.values()
        ),
        "duplicate_url_extra_entries": sum(
            len(v) - 1 for v in duplicate_urls.values()
        )
    }

    with (OUTPUT / "global-summary.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, indent=4)

    print("\n========== GLOBAL SUMMARY ==========")

    for key, value in summary.items():
        print(f"{key:40}: {value}")

    print(f"\nDuplicate report: {csv_file}")
    print("Analysis complete.")


if __name__ == "__main__":
    main()
