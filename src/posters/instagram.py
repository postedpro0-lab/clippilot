"""Post a clip as an Instagram Reel (Graph API).

Two-step: create a media container pointing at the public video URL, poll until
Instagram finishes ingesting it, then publish.
"""
import time

import requests

from ..config import env
from . import host

GRAPH = "https://graph.facebook.com/v21.0"


def post(clip_path, caption):
    ig_user = env("IG_USER_ID")
    token = env("IG_ACCESS_TOKEN")
    if not ig_user or not token:
        raise RuntimeError("Instagram needs IG_USER_ID and IG_ACCESS_TOKEN.")

    video_url = host.publish(clip_path)

    # 1) create container
    r = requests.post(
        f"{GRAPH}/{ig_user}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        },
        timeout=60,
    )
    r.raise_for_status()
    container_id = r.json()["id"]

    # 2) wait for ingestion (FINISHED) before publishing
    for _ in range(30):
        s = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        ).json()
        status = s.get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram ingestion error: {s}")
        time.sleep(5)

    # 3) publish
    p = requests.post(
        f"{GRAPH}/{ig_user}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    p.raise_for_status()
    media_id = p.json()["id"]
    print(f"[instagram] posted reel {media_id}")
    return media_id
