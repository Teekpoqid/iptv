import os
os.chdir(r"C:\Users\Parteek\Documents\Coding\z_GithubVScode\IPTV.org--epg")


import re
import xml.etree.ElementTree as ET
from pathlib import Path

playlist = Path("../iptv/output/combined.m3u")
sites = Path("sites")

playlist_ids = set()

with playlist.open(encoding="utf-8-sig", errors="replace") as f:
    for line in f:
        if line.startswith("#EXTINF"):
            match = re.search(r'tvg-id="([^"]*)"', line)
            if match and match.group(1):
                playlist_ids.add(match.group(1))

epg_ids = set()

for file in sites.rglob("*.channels.xml"):
    try:
        root = ET.parse(file).getroot()
        for channel in root.findall("channel"):
            xmltv_id = channel.get("xmltv_id")
            if xmltv_id:
                epg_ids.add(xmltv_id)
    except ET.ParseError:
        pass

matched = playlist_ids & epg_ids

print(f"Unique playlist tvg-ids: {len(playlist_ids)}")
print(f"Unique EPG xmltv-ids:    {len(epg_ids)}")
print(f"Matching channel IDs:    {len(matched)}")
print(f"Playlist IDs unmatched:  {len(playlist_ids - epg_ids)}")

print("\nSample matches:")
for channel_id in sorted(matched)[:20]:
    print(channel_id)
import re
import xml.etree.ElementTree as ET
from pathlib import Path

playlist = Path("../iptv/output/combined.m3u")
sites = Path("sites")
output = Path("../iptv/output/epg-channels.xml")

playlist_ids = set()

with playlist.open(encoding="utf-8-sig", errors="replace") as f:
    for line in f:
        if line.startswith("#EXTINF"):
            match = re.search(r'tvg-id="([^"]*)"', line)
            if match and match.group(1):
                playlist_ids.add(match.group(1))

root = ET.Element("channels")
seen = set()
matched_ids = set()
total = 0

for file in sorted(sites.rglob("*.channels.xml")):
    try:
        source_root = ET.parse(file).getroot()

        for channel in source_root.findall("channel"):
            xmltv_id = channel.get("xmltv_id")

            if xmltv_id not in playlist_ids:
                continue

            key = (
                channel.get("site"),
                channel.get("site_id"),
                channel.get("lang"),
                xmltv_id,
                channel.text
            )

            if key in seen:
                continue

            seen.add(key)
            root.append(channel)
            matched_ids.add(xmltv_id)
            total += 1

    except ET.ParseError as error:
        print(f"[WARNING] Could not parse {file}: {error}")

output.parent.mkdir(parents=True, exist_ok=True)
ET.indent(root, space="  ")

ET.ElementTree(root).write(
    output,
    encoding="UTF-8",
    xml_declaration=True
)

print(f"Matched channel IDs: {len(matched_ids)}")
print(f"Provider definitions: {total}")
print(f"Output: {output.resolve()}")



