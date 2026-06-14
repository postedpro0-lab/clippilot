"""Post a clip to Snapchat (Stories / Spotlight) via the official API.

⚠️ Ships DORMANT. Snapchat has no open, instant organic-posting API: you must
have a **Public Profile** and an app approved for content publishing through
Snapchat Business / Marketing API. Until then keep post_to.snapchat = false.
See README "Snapchat setup".

The flow mirrors TikTok: publish the clip to a public URL, hand that URL to
Snapchat, then poll until it finishes. Endpoint paths/field names below follow
Snapchat's content-publishing pattern — confirm them against the docs for the
exact app/scope you get approved for, since access tiers differ. Everything
else (clipping, hosting, scheduling) is already done for you.
"""
import time

import requests

from ..config import env
from . import host

# Base host for Snapchat's API. The exact content-publish path depends on the
# access tier granted to your approved app (Public Profile content vs Spotlight).
BASE = "https://adsapi.snapchat.com/v1"


def post(clip_path, caption, target="SPOTLIGHT"):
    token = env("SNAPCHAT_ACCESS_TOKEN")
    profile_id = env("SNAPCHAT_PROFILE_ID")
    if not token or not profile_id:
        raise RuntimeError(
            "Snapchat needs SNAPCHAT_ACCESS_TOKEN and SNAPCHAT_PROFILE_ID "
            "(approved Public Profile required)."
        )

    video_url = host.publish(clip_path)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1) submit the content for publishing
    r = requests.post(
        f"{BASE}/public_profiles/{profile_id}/content",
        headers=headers,
        json={
            "content": {
                "media_type": "VIDEO",
                "media_url": video_url,
                "caption": caption[:250],
                "destination": target,  # "SPOTLIGHT" or "STORY"
            }
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    content_id = data.get("content", {}).get("id") or data.get("id")

    # 2) poll until processed (Snapchat ingests the URL asynchronously)
    for _ in range(30):
        s = requests.get(
            f"{BASE}/public_profiles/{profile_id}/content/{content_id}",
            headers=headers,
            timeout=30,
        ).json()
        status = (s.get("content", {}) or s).get("status")
        if status in ("PUBLISHED", "LIVE", "SUCCESS"):
            break
        if status in ("FAILED", "ERROR"):
            raise RuntimeError(f"Snapchat publish failed: {s}")
        time.sleep(5)

    print(f"[snapchat] posted {content_id}")
    return content_id
