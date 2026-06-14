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
    """Return the single MOST RECENT upload that hasn't been clipped yet.

    Each run grabs at most one video per channel — the newest one not already
    in `seen`. If the latest upload was already clipped, returns nothing (no
    pointless re-clipping). Any older un-clipped videos are marked seen so we
    only ever move forward, never backwards into stale uploads.

    `process_backlog` is accepted for compatibility but no longer changes
    behavior: we always target the most-recent un-clipped upload.
    """
    seen = _load_seen()
    feed = fetch_feed(channel_id)  # newest-first
    if not feed:
        print("[monitor] empty feed.")
        return []

    # newest-first scan → first video not yet clipped is the most recent new one
    target = next((v for v in feed if v["id"] not in seen["ids"]), None)

    if target is None:
        print("[monitor] most recent upload already clipped — nothing new.")
        return []

    # Seed everything else (older uploads + already-seen) so we never revisit
    # older videos; only the target gets clipped (marked done after posting).
    others = [v["id"] for v in feed if v["id"] != target["id"] and v["id"] not in seen["ids"]]
    if others:
        seen["ids"].extend(others)
        _save_seen(seen)

    print(f"[monitor] new upload to clip: {target['title'][:70]}")
    return [target]


def mark_done(video_id):
    seen = _load_seen()
    if video_id not in seen["ids"]:
        seen["ids"].append(video_id)
        _save_seen(seen)
