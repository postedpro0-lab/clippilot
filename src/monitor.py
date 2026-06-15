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


def find_new_videos(channel_id, process_backlog=False, min_source_seconds=90):
    """Return the single MOST RECENT un-clipped LONG-FORM upload for a channel.

    Walks newest-first, skipping videos already clipped and Shorts (anything
    shorter than min_source_seconds — we want long videos to slice into many
    sub-60s clips). The chosen video is the only one returned; all skipped/older
    ones are marked seen so we only ever move forward and never re-probe them.
    """
    from . import download  # local import to avoid a circular import at load

    seen = _load_seen()
    feed = fetch_feed(channel_id)  # newest-first
    if not feed:
        print("[monitor] empty feed.")
        return []

    target = None
    seed_ids = []
    for v in feed:
        if v["id"] in seen["ids"]:
            continue
        dur = download.get_duration(v["url"])
        if dur is not None and dur < min_source_seconds:
            print(f"[monitor] skipping Short ({dur:.0f}s): {v['title'][:55]}")
            seed_ids.append(v["id"])
            continue
        target = v  # most recent un-clipped long-form video
        break

    # mark skipped Shorts + everything older than the target as seen
    if target is not None:
        cut = feed.index(target)
        seed_ids += [v["id"] for v in feed[cut + 1:] if v["id"] not in seen["ids"]]
    else:
        seed_ids += [v["id"] for v in feed if v["id"] not in seen["ids"]]
    seed_ids = [i for i in dict.fromkeys(seed_ids) if i not in seen["ids"]]
    if seed_ids:
        seen["ids"].extend(seed_ids)
        _save_seen(seen)

    if target is None:
        print("[monitor] no new long-form upload to clip.")
        return []

    print(f"[monitor] new long video to clip: {target['title'][:65]}")
    return [target]


def mark_done(video_id):
    seen = _load_seen()
    if video_id not in seen["ids"]:
        seen["ids"].append(video_id)
        _save_seen(seen)
