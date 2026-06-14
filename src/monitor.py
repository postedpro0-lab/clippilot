"""Watch a YouTube channel's RSS feed for new uploads. No API key needed."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .config import STATE

RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
SEEN_FILE = STATE / "seen.json"


def _load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {"ids": []}


def _save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def fetch_feed(channel_id):
    """Return list of {id, title, url, published} newest-first."""
    r = requests.get(RSS.format(cid=channel_id), timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    videos = []
    for entry in root.findall("atom:entry", NS):
        vid = entry.find("yt:videoId", NS).text
        title = entry.find("atom:title", NS).text
        published = entry.find("atom:published", NS).text
        videos.append(
            {
                "id": vid,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "published": published,
            }
        )
    return videos


def find_new_videos(channel_id, process_backlog=False):
    """Return new (unseen) videos. On first run, optionally seed without processing."""
    seen = _load_seen()
    feed = fetch_feed(channel_id)
    first_run = len(seen["ids"]) == 0

    if first_run:
        if not process_backlog:
            # Mark everything currently in the feed as seen and make nothing.
            seen["ids"] = [v["id"] for v in feed]
            _save_seen(seen)
            print(f"[monitor] First run: seeded {len(seen['ids'])} existing videos as seen. "
                  "Future uploads will be clipped.")
            return []
        # process_backlog: clip only the single most recent upload, seed the rest
        # as seen so we don't flood with the entire back catalog.
        newest = feed[:1]  # feed is newest-first
        seen["ids"] = [v["id"] for v in feed[1:]]
        _save_seen(seen)
        print(f"[monitor] First run (backlog): processing most recent upload, "
              f"seeded {len(seen['ids'])} older videos as seen.")
        return newest

    new = [v for v in feed if v["id"] not in seen["ids"]]
    # newest first in the feed; process oldest-of-the-new first so order is natural
    new = list(reversed(new))
    print(f"[monitor] {len(new)} new video(s) found.")
    return new


def mark_done(video_id):
    seen = _load_seen()
    if video_id not in seen["ids"]:
        seen["ids"].append(video_id)
        _save_seen(seen)
