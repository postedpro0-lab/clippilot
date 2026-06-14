"""Post a clip to TikTok via the Content Posting API (PULL_FROM_URL).

NOTE: This only works once your TikTok developer app is approved for the
`video.publish` scope and you have a valid access token. Until then, keep
post_to.tiktok = false in config.yaml. See README "TikTok setup".
"""
import time

import requests

from ..config import env
from . import host

BASE = "https://open.tiktokapis.com/v2"


def post(clip_path, caption):
    token = env("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("TikTok needs TIKTOK_ACCESS_TOKEN (approved app required).")

    video_url = host.publish(clip_path)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    r = requests.post(
        f"{BASE}/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title": caption[:150],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_comment": False,
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            },
        },
        timeout=60,
    )
    r.raise_for_status()
    publish_id = r.json()["data"]["publish_id"]

    # poll status
    for _ in range(30):
        s = requests.post(
            f"{BASE}/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
            timeout=30,
        ).json()
        status = s.get("data", {}).get("status")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            break
        if status == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {s}")
        time.sleep(5)

    print(f"[tiktok] posted {publish_id}")
    return publish_id
